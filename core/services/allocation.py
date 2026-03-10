"""
Resource allocation service for Entebbe Airport.
Handles stand, gate, and check-in counter assignments for flights.
"""

from datetime import date, time, datetime, timedelta
from typing import Optional
from django.db.models import Q
from core.models import (
    FlightRequest, ParkingStand, Gate, CheckInCounter,
    StandAllocation, GateAllocation, CheckInAllocation
)


def time_add_minutes(t: time, minutes: int) -> time:
    """Add minutes to a time object (handles midnight wrap)."""
    dt = datetime.combine(date.today(), t) + timedelta(minutes=minutes)
    return dt.time()


def time_subtract_minutes(t: time, minutes: int) -> time:
    """Subtract minutes from a time object."""
    dt = datetime.combine(date.today(), t) - timedelta(minutes=minutes)
    return dt.time()

def interval_minutes(t: time):
    return t.hour * 60 + t.minute

def times_overlap(start1: time, end1: time, start2: time, end2: time) -> bool:
    """Check if two time intervals overlap. Handles cross-midnight."""
    s1 = interval_minutes(start1)
    e1 = interval_minutes(end1)
    if e1 <= s1: e1 += 1440

    s2 = interval_minutes(start2)
    e2 = interval_minutes(end2)
    if e2 <= s2: e2 += 1440

    return s1 < e2 and e1 > s2


def get_allocated_stands_on_date(date_: date) -> list:
    """Return list of (stand_id, start_time, end_time) already allocated on given date."""
    return list(StandAllocation.objects.filter(date=date_).values_list('stand_id', 'start_time', 'end_time'))


def get_allocated_gates_on_date(date_: date) -> list:
    """Return list of (gate_id, start_time, end_time) already allocated on given date."""
    return list(GateAllocation.objects.filter(date=date_).values_list('gate_id', 'start_time', 'end_time'))


def get_allocated_counters_on_date(date_: date):
    """Return all CheckInAllocations on a given date."""
    return CheckInAllocation.objects.filter(date=date_)


def find_previous_allocation_for_flight(flight: FlightRequest, date_: date):
    """
    Check if this flight already has allocations on other dates.
    If so, return the stand and gate to reuse them.
    """
    # Find any previous date where this flight was allocated
    prev_stand = StandAllocation.objects.filter(
        flight_request=flight
    ).exclude(date=date_).first()
    
    prev_gate = GateAllocation.objects.filter(
        flight_request=flight
    ).exclude(date=date_).first()
    
    return prev_stand, prev_gate


def get_airline_counter_usage_on_date(airline_id, date_: date, exclude_checkin_id=None):
    """
    Get total counters allocated to an airline on a given date.
    Returns dict with {counter_range: [(start, end, flight_id), ...]}
    """
    allocs = CheckInAllocation.objects.filter(
        flight_request__airline_id=airline_id,
        date=date_
    )
    if exclude_checkin_id:
        allocs = allocs.exclude(id=exclude_checkin_id)
    
    usage = {}
    for alloc in allocs:
        key = f"{alloc.counter_from}-{alloc.counter_to}"
        if key not in usage:
            usage[key] = []
        usage[key].append((alloc.start_time, alloc.end_time, alloc.flight_request_id))
    return usage


def get_simultaneous_airline_flights(flight: FlightRequest, date_: date):
    """
    Find other flights from the same airline that check in at the same time on this date.
    """
    if flight.operation_type == 'arrival':
        return []
    
    departure = flight.departure_time
    if not departure:
        return []
    
    checkin_close = time_subtract_minutes(departure, 60)
    checkin_open = time_subtract_minutes(checkin_close, flight.checkin_duration_hours * 60)
    
    # Find other flights from same airline that overlap
    other_flights = FlightRequest.objects.filter(
        airline=flight.airline,
        season=flight.season,
        year=flight.year,
        operation_type__in=['turnaround', 'departure']
    ).exclude(id=flight.id)
    
    overlapping = []
    for other in other_flights:
        if not other.operates_on_date(date_):
            continue
        if not other.departure_time:
            continue
        
        other_checkin_close = time_subtract_minutes(other.departure_time, 60)
        other_checkin_open = time_subtract_minutes(other_checkin_close, other.checkin_duration_hours * 60)
        
        if times_overlap(checkin_open, checkin_close, other_checkin_open, other_checkin_close):
            overlapping.append(other)
    
    return overlapping


def allocate_stand(flight: FlightRequest, date_: date) -> Optional[StandAllocation]:
    """
    Allocate a suitable stand for the flight on the given date.
    For overnight flights, it creates multiple StandAllocation records (arrival night,
    full intermediate days, departure morning) spanning the ground days, and restricts
    to remote/extended apron parking.
    """
    arrival = flight.arrival_time or flight.departure_time
    departure = flight.departure_time or flight.arrival_time
    if arrival is None or departure is None:
        return None

    # Check if this flight already has an allocation on another date and try to reuse it
    prev_stand_alloc, _ = find_previous_allocation_for_flight(flight, date_)

    is_overnight = flight.is_overnight
    ground_days = flight.ground_days

    # Define the date spans required for this stand allocation
    date_spans = []
    if is_overnight:
        # Arrival date: arrival_time to 23:59
        date_spans.append((date_, arrival, time(23, 59, 59)))
        # Intermediate days
        for d in range(1, ground_days):
            date_spans.append((date_ + timedelta(days=d), time(0, 0), time(23, 59, 59)))
        # Departure date: 00:00 to departure_time
        date_spans.append((date_ + timedelta(days=ground_days), time(0, 0), departure))
    else:
        date_spans.append((date_, arrival, departure))

    def _check_conflict(stand_id):
        # Must be free on all required date spans
        for d, s, e in date_spans:
            existing = get_allocated_stands_on_date(d)
            for (sid, sstart, send) in existing:
                if sid == stand_id and times_overlap(s, e, sstart, send):
                    return True
        return False

    # Try to reuse the same stand
    if prev_stand_alloc:
        if not _check_conflict(prev_stand_alloc.stand_id):
            # Create records for all spans
            for d, s, e in date_spans:
                StandAllocation.objects.create(
                    flight_request=flight,
                    stand=prev_stand_alloc.stand,
                    date=d,
                    start_time=s,
                    end_time=e,
                )
            return prev_stand_alloc

    # Build preferred stand ordering
    if is_overnight:
        if flight.aircraft_type.is_wide_body or flight.aircraft_type.size_code in ('D', 'E', 'F'):
            # Wide-bodies cannot fit on the remote apron (which is all Code C). 
            # They must use the main apron even overnight.
            all_stands = ParkingStand.objects.filter(is_active=True, parent_stand__isnull=True)
        else:
            # Policy: narrow-body overnight flights must use remote/extended apron
            all_stands = ParkingStand.objects.filter(is_active=True, parent_stand__isnull=True).filter(
                Q(apron='apron1ext') | Q(is_remote=True)
            )
    else:
        all_stands = ParkingStand.objects.filter(is_active=True, parent_stand__isnull=True)

    def stand_priority(stand):
        score = 0
        if flight.aircraft_type.is_wide_body:
            if stand.has_boarding_bridge:
                score += 100
            if stand.size_code in ('E', 'F'):
                score += 50
        else:
            if not stand.has_boarding_bridge:
                score += 20
        if stand.is_remote and not is_overnight:
            score -= 10
        return -score

    candidates = sorted(
        [s for s in all_stands if s.can_accommodate(flight.aircraft_type)],
        key=stand_priority
    )

    for stand in candidates:
        if not _check_conflict(stand.id):
            # Create all spans
            first_alloc = None
            for d, s, e in date_spans:
                alloc = StandAllocation.objects.create(
                    flight_request=flight,
                    stand=stand,
                    date=d,
                    start_time=s,
                    end_time=e,
                )
                if not first_alloc:
                    first_alloc = alloc
            return first_alloc

    return None


def allocate_gate(flight: FlightRequest, date_: date) -> Optional[GateAllocation]:
    """
    Allocate a gate for the flight.
    For recurring flights, try to reuse the same gate from a previous allocation.
    Gate closes 15 minutes before departure.
    Wide-body prefers bridge gates (2B, 4).
    """
    departure = flight.departure_time
    if departure is None:
        return None  # Arrival-only flights don't need a gate

    gate_close = time_subtract_minutes(departure, 15)
    # Gate opens when boarding starts (typically 45 mins before departure)
    gate_open = time_subtract_minutes(departure, 45)

    # Check if this flight already has an allocation on another date and try to reuse it
    _, prev_gate_alloc = find_previous_allocation_for_flight(flight, date_)
    if prev_gate_alloc:
        # Try to reuse the same gate
        existing = get_allocated_gates_on_date(date_)
        conflict = False
        for (gid, gstart, gend) in existing:
            if gid == prev_gate_alloc.gate_id and times_overlap(gate_open, gate_close, gstart, gend):
                conflict = True
                break
        
        if not conflict:
            alloc = GateAllocation(
                flight_request=flight,
                gate=prev_gate_alloc.gate,
                date=date_,
                start_time=gate_open,
                end_time=gate_close,
            )
            alloc.save()
            return alloc

    existing = get_allocated_gates_on_date(date_)
    all_gates = Gate.objects.filter(is_active=True)

    def gate_priority(gate):
        score = 0
        if flight.aircraft_type.is_wide_body and gate.has_boarding_bridge:
            score += 100
        return -score

    candidates = sorted(all_gates, key=gate_priority)

    for gate in candidates:
        conflict = False
        for (gid, gstart, gend) in existing:
            if gid == gate.id and times_overlap(gate_open, gate_close, gstart, gend):
                conflict = True
                break
        if not conflict:
            alloc = GateAllocation(
                flight_request=flight,
                gate=gate,
                date=date_,
                start_time=gate_open,
                end_time=gate_close,
            )
            alloc.save()
            return alloc

    return None


def allocate_checkin(flight: FlightRequest, date_: date) -> Optional[CheckInAllocation]:
    """
    Allocate check-in counters for the flight with smart airline consolidation.
    
    Rules:
    1. If another flight from the same airline is checking in at the same time,
       they share the same counter block (don't allocate separate blocks).
    2. An airline can get max 1-2 additional counters per day beyond their standard allocation.
    3. Wide-body: 3 hours check-in, 5-7 counters; start with min 4
    4. Narrow/regional: 2 hours check-in, 3-4 counters; start with min 2
    5. Counters 1-4 prioritized for Uganda Airlines (home airline)
    """
    if flight.operation_type == 'arrival':
        return None  # Arrival-only flights don't use check-in

    departure = flight.departure_time
    if departure is None:
        return None

    checkin_close = time_subtract_minutes(departure, 60)
    checkin_open = time_subtract_minutes(checkin_close, flight.checkin_duration_hours * 60)
    
    num_counters_needed = flight.min_counters
    is_home = flight.airline.is_home_airline

    # Special Rule: Uganda Airlines (home airline) small/narrow-body flights
    # exclusively share counters 1-4 regardless of overlaps or simultaneity.
    if is_home and not (flight.aircraft_type.is_wide_body or flight.aircraft_type.size_code in ('D', 'E', 'F')):
        alloc = CheckInAllocation(
            flight_request=flight,
            counter_from=1,
            counter_to=4,
            date=date_,
            start_time=checkin_open,
            end_time=checkin_close,
        )
        alloc.save()
        return alloc

    # Check if there are simultaneous flights from same airline
    simultaneous = get_simultaneous_airline_flights(flight, date_)
    
    # If there's a simultaneous flight that already has an allocation, reuse it
    for other_flight in simultaneous:
        other_alloc = CheckInAllocation.objects.filter(
            flight_request=other_flight,
            date=date_
        ).first()
        if other_alloc:
            # Create a new allocation with the same counter block
            alloc = CheckInAllocation(
                flight_request=flight,
                counter_from=other_alloc.counter_from,
                counter_to=other_alloc.counter_to,
                date=date_,
                start_time=checkin_open,
                end_time=checkin_close,
            )
            alloc.save()
            return alloc
    
    existing_allocs = list(get_allocated_counters_on_date(date_))

    # Get airline's current counter usage
    airline_usage = get_airline_counter_usage_on_date(flight.airline_id, date_)
    
    # Calculate how many counters this airline is already using
    airline_counters_in_use = set()
    for alloc in existing_allocs:
        if alloc.flight_request.airline_id == flight.airline_id:
            airline_counters_in_use.update(range(alloc.counter_from, alloc.counter_to + 1))
    
    # Determine total counters available for this airline
    # Home airline gets 1-4, others get 5-22
    if is_home:
        home_counters = list(range(1, 5))
        expansion_room = 2  # can expand by 1-2 more
    else:
        home_counters = list(range(5, 23))
        expansion_room = 2
    
    max_airline_counters = len(home_counters) + expansion_room

    # If this airline is already at max, cannot allocate
    if len(airline_counters_in_use) >= max_airline_counters:
        return None
    
    # Find contiguous block of free counters
    def is_counter_free(counter_num, start, end):
        for alloc in existing_allocs:
            if alloc.counter_from <= counter_num <= alloc.counter_to:
                if times_overlap(start, end, alloc.start_time, alloc.end_time):
                    return False
        return True

    # Sort counter preference
    if is_home:
        preferred = list(range(1, 5)) + list(range(5, 23))
    else:
        preferred = list(range(5, 23)) + list(range(1, 5))

    # Find first contiguous block of num_counters_needed free counters
    for start_counter in preferred:
        end_counter = start_counter + num_counters_needed - 1
        if end_counter > 22:
            continue
        
        # Check if this block would exceed airline's max usage
        new_counters = set(range(start_counter, end_counter + 1))
        total_after = len(airline_counters_in_use | new_counters)
        if total_after > max_airline_counters:
            continue
        
        # Check entire block is free
        block_free = all(
            is_counter_free(c, checkin_open, checkin_close)
            for c in range(start_counter, end_counter + 1)
        )
        if block_free:
            alloc = CheckInAllocation(
                flight_request=flight,
                counter_from=start_counter,
                counter_to=end_counter,
                date=date_,
                start_time=checkin_open,
                end_time=checkin_close,
            )
            alloc.save()
            return alloc

    return None  # No counters available


def allocate_resources_for_date(date_: date) -> dict:
    """
    Auto-allocate stands, gates, and check-in counters for all flights on a date.
    Returns a summary dict with counts of successful allocations and conflicts.
    """
    from core.services.season import get_season_for_date, get_season_dates, is_date_in_season

    season, year = get_season_for_date(date_)
    flights = FlightRequest.objects.filter(
        season=season, year=year, status__in=['pending', 'conflict']
    ).select_related('airline', 'aircraft_type')

    results = {'allocated': 0, 'conflicts': 0, 'skipped': 0}

    for flight in flights:
        if not flight.operates_on_date(date_):
            results['skipped'] += 1
            continue

        # Skip if already allocated for this date
        already_stand = StandAllocation.objects.filter(flight_request=flight, date=date_).exists()
        if already_stand:
            results['allocated'] += 1
            continue

        stand = allocate_stand(flight, date_)
        gate = allocate_gate(flight, date_)
        checkin = allocate_checkin(flight, date_)

        if stand or gate or checkin:
            results['allocated'] += 1
            flight.status = 'allocated'
        else:
            results['conflicts'] += 1
            flight.status = 'conflict'
        flight.save()

    return results


def get_conflicts_for_date(date_: date) -> list:
    """Return list of flights with conflicts on a given date."""
    return list(FlightRequest.objects.filter(status='conflict'))


def allocate_resources_for_flight(flight: FlightRequest) -> dict:
    """
    Auto-allocate stands, gates, and check-in counters for all operating
    dates of a single flight within its season (or valid_from/valid_to range).

    Returns a summary dict:
        {'allocated': N, 'conflicts': N, 'skipped': N, 'total_dates': N}

    Also updates flight.status:
        - 'allocated'  if every operating date got at least some resource
        - 'conflict'   if any operating date could not get a stand
        - 'pending'    if no times are set (nothing to allocate)
    """
    from core.services.season import get_season_dates
    from datetime import timedelta

    # Determine date range
    if flight.valid_from and flight.valid_to:
        range_start = flight.valid_from
        range_end = flight.valid_to
    else:
        range_start, range_end = get_season_dates(flight.season, flight.year)

    # Nothing to allocate without times
    if flight.arrival_time is None and flight.departure_time is None:
        return {'allocated': 0, 'conflicts': 0, 'skipped': 0, 'total_dates': 0}

    results = {'allocated': 0, 'conflicts': 0, 'skipped': 0, 'total_dates': 0}
    current = range_start

    while current <= range_end:
        results['total_dates'] += 1

        if not flight.operates_on_date(current):
            results['skipped'] += 1
            current += timedelta(days=1)
            continue

        # Skip if already allocated for this date
        if StandAllocation.objects.filter(flight_request=flight, date=current).exists():
            results['allocated'] += 1
            current += timedelta(days=1)
            continue

        stand = allocate_stand(flight, current)
        
        # For overnight flights, allocate_stand handles all intermediate dates.
        # Gate and check-in are always allocated on the departure date.
        departure_date = current + flight.departure_date_offset
        gate = allocate_gate(flight, departure_date)
        checkin = allocate_checkin(flight, departure_date)

        if stand or gate or checkin:
            results['allocated'] += 1
        else:
            results['conflicts'] += 1

        current += timedelta(days=1)

    # Set flight status based on results
    if results['allocated'] == 0 and results['conflicts'] == 0:
        # No operating dates found / no times
        flight.status = 'pending'
    elif results['conflicts'] > 0:
        flight.status = 'conflict'
    else:
        flight.status = 'allocated'
    flight.save(update_fields=['status', 'updated_at'])

    return results

