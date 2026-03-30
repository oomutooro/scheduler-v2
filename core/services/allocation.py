"""
Resource allocation service for Entebbe Airport.
Handles stand, gate, and check-in counter assignments for flights.
"""

from datetime import date, time, datetime, timedelta
from typing import Any, Optional, cast
from core.models import (
    FlightRequest, ParkingStand, Gate,
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

def interval_minutes(t: time) -> int:
    return t.hour * 60 + t.minute

def times_overlap(start1: Optional[time], end1: Optional[time], start2: Optional[time], end2: Optional[time]) -> bool:
    """Check if two time intervals overlap. Handles cross-midnight."""
    if any(t is None for t in (start1, end1, start2, end2)):
        return False
    start1 = cast(time, start1)
    end1 = cast(time, end1)
    start2 = cast(time, start2)
    end2 = cast(time, end2)
    s1 = interval_minutes(start1)
    e1 = interval_minutes(end1)
    if e1 <= s1: e1 += 1440

    s2 = interval_minutes(start2)
    e2 = interval_minutes(end2)
    if e2 <= s2: e2 += 1440

    return s1 < e2 and e1 > s2


def get_allocated_stands_on_date(date_: date, alloc_cache: Optional[dict[str, Any]] = None) -> list[tuple[int, time, time]]:
    """Return list of (stand_id, start_time, end_time) already allocated on given date."""
    if alloc_cache is not None:
        key = f"stand_{date_}"
        if key not in alloc_cache:
            alloc_cache[key] = list(StandAllocation.objects.filter(date=date_).values_list('stand_id', 'start_time', 'end_time'))
        return alloc_cache[key]
    return list(StandAllocation.objects.filter(date=date_).values_list('stand_id', 'start_time', 'end_time'))


def get_allocated_gates_on_date(date_: date, alloc_cache: Optional[dict[str, Any]] = None) -> list[tuple[int, time, time]]:
    """Return list of (gate_id, start_time, end_time) already allocated on given date."""
    if alloc_cache is not None:
        key = f"gate_{date_}"
        if key not in alloc_cache:
            alloc_cache[key] = list(GateAllocation.objects.filter(date=date_).values_list('gate_id', 'start_time', 'end_time'))
        return alloc_cache[key]
    return list(GateAllocation.objects.filter(date=date_).values_list('gate_id', 'start_time', 'end_time'))


def get_allocated_counters_on_date(date_: date, alloc_cache: Optional[dict[str, Any]] = None) -> list[CheckInAllocation]:
    """Return all CheckInAllocations on a given date as a list."""
    if alloc_cache is not None:
        key = f"checkin_{date_}"
        if key not in alloc_cache:
            alloc_cache[key] = list(CheckInAllocation.objects.filter(date=date_).select_related('flight_request'))
        return alloc_cache[key]
    return list(CheckInAllocation.objects.filter(date=date_).select_related('flight_request'))


def find_previous_allocation_for_flight(
    flight: FlightRequest,
    date_: date,
) -> tuple[Optional[StandAllocation], Optional[GateAllocation]]:
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


def get_airline_counter_usage_on_date(
    airline_id: int,
    date_: date,
    exclude_checkin_id: Optional[int] = None,
) -> dict[str, list[tuple[time, time, int]]]:
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
        usage[key].append((alloc.start_time, alloc.end_time, int(alloc.flight_request.pk)))
    return usage


def get_simultaneous_airline_flights(flight: FlightRequest, date_: date) -> list[FlightRequest]:
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
    ).exclude(id=int(flight.pk))
    
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


import random


def allocate_stand(
    flight: FlightRequest,
    date_: date,
    alloc_cache: Optional[dict[str, Any]] = None,
    shuffle: bool = False,
    all_day_flights: Optional[list[FlightRequest]] = None,
) -> Optional[StandAllocation]:
    """
    Allocate a suitable stand for the flight on the given date.

    * ``shuffle`` – when True the base list of stands is shuffled before
      priorities are applied.  This allows repeated auto-allocation runs to
      explore different assignments rather than always taking the same
      top‑priority stand.  The default is False to preserve deterministic
      behaviour for manual operations and tests.
    """
    actual_arrival = flight.arrival_time
    actual_departure = flight.departure_time

    if flight.operation_type == 'arrival' and actual_arrival:
        arrival = actual_arrival
        departure = time_add_minutes(actual_arrival, 90)  # Reduced to 90 mins duration on stand
    elif flight.operation_type == 'departure' and actual_departure:
        arrival = time_subtract_minutes(actual_departure, 90)
        departure = actual_departure
    else:
        arrival = actual_arrival or actual_departure
        departure = actual_departure or actual_arrival

    if arrival is None or departure is None:
        return None

    # Check if this flight already has an allocation on another date and try to reuse it
    prev_stand_alloc, _ = find_previous_allocation_for_flight(flight, date_)

    # Custom rule: If the flight has a strong preference for a specific stand 
    # and the previous allocation was elsewhere, we might want to skip reuse to 
    # move it to its preferred spot.
    is_preferred_stand = False
    if prev_stand_alloc:
        icao = flight.airline.icao_code
        ps_num = str(prev_stand_alloc.stand.stand_number)
        if ps_num == '5' and icao in ('QTR', 'BEL', 'ABY', 'MSR'): is_preferred_stand = True
        elif ps_num == '6' and icao == 'UAE': is_preferred_stand = True
        elif flight.airline.is_home_airline and ps_num in ('7', '8', '3A'): is_preferred_stand = True
        
        # If not on preferred stand, only reuse if no better option exists (handled by skipping reuse here)
        has_other_pref = icao in ('QTR', 'BEL', 'ABY', 'MSR', 'UAE')
        if has_other_pref and not is_preferred_stand:
            prev_stand_alloc = None # Skip reuse to favor preference
    
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

    def _check_conflict(stand_id: int) -> bool:
        # Find all related stands (parent and children)
        try:
            stand = ParkingStand.objects.get(id=stand_id)
            related_stand_ids = [int(stand.pk)]
            parent_stand_id = cast(Optional[int], getattr(stand, 'parent_stand_id', None))
            if parent_stand_id:
                related_stand_ids.append(parent_stand_id)
            # Add all sub-stands
            related_stand_ids.extend(list(ParkingStand.objects.filter(parent_stand_id=int(stand.pk)).values_list('id', flat=True)))
            # If the stand has a parent, also add its siblings
            if parent_stand_id:
                related_stand_ids.extend(list(ParkingStand.objects.filter(parent_stand_id=parent_stand_id).exclude(id=int(stand.pk)).values_list('id', flat=True)))
        except ParkingStand.DoesNotExist:
            related_stand_ids = [stand_id]

        # Must be free on all required date spans
        for d, s, e in date_spans:
            existing = get_allocated_stands_on_date(d, alloc_cache)
            for (sid, sstart, send) in existing:
                if sid in related_stand_ids and times_overlap(s, e, sstart, send):
                    return True
        return False

    # Try to reuse the same stand
    if prev_stand_alloc:
        prev_stand_id = cast(int, getattr(prev_stand_alloc, 'stand_id'))
        if not _check_conflict(prev_stand_id):
            # Create records for all spans
            for d, s, e in date_spans:
                StandAllocation.objects.create(
                    flight_request=flight,
                    stand=prev_stand_alloc.stand,
                    date=d,
                    start_time=s,
                    end_time=e,
                )
                if alloc_cache is not None:
                        alloc_cache.setdefault(f"stand_{d}", []).append((prev_stand_id, s, e))
            return prev_stand_alloc

    # Build preferred stand ordering (cached)
    if alloc_cache is not None and "all_stands" not in alloc_cache:
        alloc_cache["all_stands"] = list(ParkingStand.objects.filter(is_active=True, parent_stand__isnull=True))
        if shuffle:
            random.shuffle(alloc_cache["all_stands"])
    
    base_stands = alloc_cache["all_stands"] if alloc_cache is not None else list(ParkingStand.objects.filter(is_active=True, parent_stand__isnull=True))
    if shuffle and alloc_cache is not None and "all_stands" in alloc_cache:
        # if shuffle was requested after the cache exists, reshuffle it
        random.shuffle(alloc_cache["all_stands"])
    
    if is_overnight:
        if flight.airline.is_home_airline:
            # Uganda Airlines can be put anywhere, apart from stands 5 and 6 for small aircrafts
            all_stands = base_stands
            is_small_aircraft = not flight.aircraft_type.is_wide_body and flight.aircraft_type.size_code not in ('D', 'E', 'F')
            if is_small_aircraft:
                # Allowed to use 5/6 if it's a preferred airline, otherwise restricted
                preferred_for_5_6 = ('QTR', 'BEL', 'ABY', 'MSR', 'UAE')
                if flight.airline.icao_code not in preferred_for_5_6:
                    all_stands = [s for s in all_stands if str(s.stand_number) not in ['5', '5A', '5B', '6', '6A', '6B']]
        elif flight.aircraft_type.is_wide_body or flight.aircraft_type.size_code in ('D', 'E', 'F'):
            all_stands = base_stands
        else:
            all_stands = [s for s in base_stands if s.apron == 'apron1ext' or s.is_remote]
    else:
        all_stands = base_stands

    def stand_priority(stand: ParkingStand) -> int:
        score = 0
        airline_icao = flight.airline.icao_code
        airline_iata = flight.airline.iata_code

        # Stand specific preferences (source of truth: USER instructions)
        # Stand 5: QTR, BEL, ABY, MSR
        # Stand 6: UAE (Emirates)
        if str(stand.stand_number) == '5':
            if airline_icao in ('QTR', 'BEL', 'ABY', 'MSR'):
                score += 2000
        elif str(stand.stand_number) == '6':
            if airline_icao == 'UAE':
                score += 2000
            
        # Uganda Airlines small aircraft usually prefer stands 7 and 8
        is_small_aircraft = not flight.aircraft_type.is_wide_body and flight.aircraft_type.size_code not in ('D', 'E', 'F')
        if flight.airline.is_home_airline and is_small_aircraft:
            if str(stand.stand_number).startswith('7') or str(stand.stand_number).startswith('8'):
                score += 800
                
        # Bridge preferences
        bridge_preferred_airlines = ('ABY', 'QTR', 'UAE', 'FDB', 'THY', 'MSR', 'RWD', 'BEL', 'KLM')
        if airline_iata in bridge_preferred_airlines:
            if stand.has_boarding_bridge:
                score += 500

        # Code C Bridge Priority: Encourage smaller jets to use bridges if available
        if flight.aircraft_type.size_code == 'C' and stand.has_boarding_bridge:
            score += 300

        if flight.aircraft_type.is_wide_body:
            if stand.has_boarding_bridge:
                score += 100
            if stand.size_code in ('E', 'F'):
                score += 50
        else:
            if airline_iata not in bridge_preferred_airlines and not stand.has_boarding_bridge:
                score += 20
        if stand.is_remote and not is_overnight:
            score -= 10
        return -score

    # Future-awareness: if a stand is preferred by a LATER flight that overlaps with us,
    # penalize it for the current flight to "reserve" it.
    def get_future_penalty(stand: ParkingStand) -> int:
        if not all_day_flights: return 0
        penalty = 0
        current_arrival = flight.arrival_time or flight.departure_time
        
        for future_f in all_day_flights:
            if int(future_f.pk) == int(flight.pk):
                continue
            
            # Use same logic as allocate_stand to determine future flight's occupancy
            f_arr_orig = future_f.arrival_time
            f_dep_orig = future_f.departure_time
            if future_f.operation_type == 'arrival' and f_arr_orig:
                f_s, f_e = f_arr_orig, time_add_minutes(f_arr_orig, 90)
            elif future_f.operation_type == 'departure' and f_dep_orig:
                f_s, f_e = time_subtract_minutes(f_dep_orig, 90), f_dep_orig
            else:
                f_s, f_e = f_arr_orig or f_dep_orig, f_dep_orig or f_arr_orig

            if not f_s or not f_e: continue
            
            # We only care about flights arriving around or after us
            if f_s < (current_arrival or time(0,0)):
                continue
            
            # If they overlap
            if times_overlap(arrival, departure, f_s, f_e):
                # Check if future flight has a high preference for this stand
                f_icao = future_f.airline.icao_code
                s_num = str(stand.stand_number)
                if s_num == '5' and f_icao in ('QTR', 'BEL', 'ABY', 'MSR'): 
                    penalty += 3000
                elif s_num == '6' and f_icao == 'UAE':
                    penalty += 3000
        return penalty

    candidates = sorted(
        [s for s in all_stands if s.can_accommodate(flight.aircraft_type)],
        key=lambda s: stand_priority(s) + get_future_penalty(s)
    )

    for stand in candidates:
        stand_id = int(stand.pk)
        if not _check_conflict(stand_id):
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
                if alloc_cache is not None:
                    alloc_cache.setdefault(f"stand_{d}", []).append((stand_id, s, e))
                if not first_alloc:
                    first_alloc = alloc
            return first_alloc

    return None


def allocate_gate(
    flight: FlightRequest,
    date_: date,
    alloc_cache: Optional[dict[str, Any]] = None,
    shuffle: bool = False,
) -> Optional[GateAllocation]:
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
        prev_gate_id = cast(int, getattr(prev_gate_alloc, 'gate_id'))
        # Try to reuse the same gate
        existing = get_allocated_gates_on_date(date_, alloc_cache)
        conflict = False
        for (gid, gstart, gend) in existing:
            if gid == prev_gate_id and times_overlap(gate_open, gate_close, gstart, gend):
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
            if alloc_cache is not None:
                alloc_cache.setdefault(f"gate_{date_}", []).append((prev_gate_id, gate_open, gate_close))
            return alloc

    existing = get_allocated_gates_on_date(date_, alloc_cache)
    if alloc_cache is not None and "all_gates" not in alloc_cache:
        alloc_cache["all_gates"] = list(Gate.objects.filter(is_active=True))
        if shuffle:
            random.shuffle(alloc_cache["all_gates"])
    all_gates = alloc_cache["all_gates"] if alloc_cache is not None else list(Gate.objects.filter(is_active=True))
    if shuffle and alloc_cache is not None and "all_gates" in alloc_cache:
        random.shuffle(alloc_cache["all_gates"])

    def gate_priority(gate: Gate) -> int:
        score = 0
        
        # Preferred gates (source of truth: USER instructions)
        # Stand 5 -> Gate 2B
        # Stand 6 -> Gate 4
        airline_icao = flight.airline.icao_code
        if str(gate.gate_number) == '2B' and airline_icao in ('QTR', 'BEL', 'ABY', 'MSR'):
            score += 2000
        elif str(gate.gate_number) == '4' and airline_icao == 'UAE':
            score += 2000

        # Uganda Airlines prefers Gate 3A except for LGW flights
        if flight.airline.is_home_airline:
            dest_code = flight.destination.iata_code if flight.destination else None
            if dest_code != 'LGW' and str(gate.gate_number) == '3A':
                score += 1000
                
        if flight.aircraft_type.is_wide_body and gate.has_boarding_bridge:
            score += 100
        return -score

    candidates = sorted(all_gates, key=gate_priority)

    # determine existing stand allocation for this flight/date (if any)
    stand_alloc = StandAllocation.objects.filter(flight_request=flight, date=date_).first()
    stand_has_bridge = bool(stand_alloc and stand_alloc.stand.has_boarding_bridge)
    for gate in candidates:
        gate_id = int(gate.pk)
        # enforce bridge rules: a gate with a boarding bridge may only be used
        # if the assigned stand also has a bridge and the two are connected.
        if gate.has_boarding_bridge:
            if not stand_has_bridge:
                # flight is not on a bridge-enabled stand – skip this gate
                continue
            if gate.connected_stand:
                # gate is tied to a specific parking stand instance
                if not stand_alloc:
                    continue
                if stand_alloc.stand != gate.connected_stand:
                    # allow subdivisions of the parent stand to count as match
                    parent = stand_alloc.stand.parent_stand if stand_alloc.stand.parent_stand else None
                    if not parent or parent != gate.connected_stand:
                        continue

        conflict = False
        for (gid, gstart, gend) in existing:
            if gid == gate_id and times_overlap(gate_open, gate_close, gstart, gend):
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
            if alloc_cache is not None:
                alloc_cache.setdefault(f"gate_{date_}", []).append((gate_id, gate_open, gate_close))
            return alloc

    return None


def get_ground_handlers_map() -> dict[int, Any]:
    """Build a mapping of Airline ID -> GroundHandler object."""
    from core.models import GroundHandler
    handlers = GroundHandler.objects.prefetch_related('airlines').all()
    h_map = {}
    for h in handlers:
        for airline in h.airlines.all():
            h_map[airline.id] = h
    return h_map


def allocate_checkin(
    flight: FlightRequest,
    date_: date,
    alloc_cache: Optional[dict[str, Any]] = None,
    shuffle: bool = False,
    all_day_flights: Optional[list[FlightRequest]] = None,
) -> Optional[CheckInAllocation]:
    """
    Allocate check-in counters with handler-aware look-ahead.
    
    Rules:
    1. Consolidation: Same airline shares counter blocks.
    2. Handler Transition: Flights with SAME handler can have a 45-min overlap 
       at the counters to facilitate smooth handover.
    3. Look-Ahead: Penalize counter blocks needed by future high-priority flights.
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
        if alloc_cache is not None:
            alloc_cache.setdefault(f"checkin_{date_}", []).append(alloc)
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
            if alloc_cache is not None:
                alloc_cache.setdefault(f"checkin_{date_}", []).append(alloc)
            return alloc
    
    existing_allocs = get_allocated_counters_on_date(date_, alloc_cache)
    if shuffle and alloc_cache is not None and "all_counters" in alloc_cache:
        random.shuffle(alloc_cache["all_counters"])
    # Get airline's current counter usage
    # Calculate how many counters this airline is already using
    airline_counters_in_use = set()
    for alloc in existing_allocs:
        if int(alloc.flight_request.airline.pk) == int(flight.airline.pk):
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
    
    # Sort counter preference
    if is_home:
        # Home airline blocks 1-4 first
        preferred_starts = list(range(1, 23)) 
    else:
        # Others start from 5
        preferred_starts = list(range(5, 23)) + list(range(1, 5))

    # Find contiguous block of free counters
    def is_counter_free(counter_num: int, start: time, end: time) -> bool:
        h_map = cast(dict[int, Any], alloc_cache.get('handlers_map')) if alloc_cache and alloc_cache.get('handlers_map') else get_ground_handlers_map()
        my_handler = h_map.get(int(flight.airline.pk))
        
        for alloc in existing_allocs:
            if alloc.counter_from <= counter_num <= alloc.counter_to:
                # Check for overlap
                if times_overlap(start, end, alloc.start_time, alloc.end_time):
                    # Exception: If same handler, allow a 45-min "soft" overlap
                    other_handler = h_map.get(int(alloc.flight_request.airline.pk))
                    if my_handler and other_handler and my_handler.id == other_handler.id:
                        # Calculate overlap duration
                        s_max = max(interval_minutes(start), interval_minutes(alloc.start_time))
                        e_min = min(interval_minutes(end), interval_minutes(alloc.end_time))
                        overlap_dur = e_min - s_max
                        if overlap_dur <= 45:
                            continue # Allow this specific overlap
                    return False
        return True

    # Future-awareness for counters
    def get_future_counter_penalty(_start_c: int, _end_c: int) -> int:
        if not all_day_flights: return 0
        penalty = 0
        for future_f in all_day_flights:
            if int(future_f.pk) == int(flight.pk) or future_f.operation_type == 'arrival':
                continue
            
            f_dep = future_f.departure_time
            if not f_dep: continue
            f_close = time_subtract_minutes(f_dep, 60)
            f_open = time_subtract_minutes(f_close, future_f.checkin_duration_hours * 60)
            
            if times_overlap(checkin_open, checkin_close, f_open, f_close):
                # If high priority airline needs these counters
                if future_f.airline.icao_code in ('QTR', 'BEL', 'ABY', 'MSR', 'UAE'):
                    penalty += 1000
        return penalty

    # Find first contiguous block of num_counters_needed free counters
    potential_blocks = []
    for start_counter in preferred_starts:
        end_counter = start_counter + num_counters_needed - 1
        if end_counter > 22: continue
        
        # Check if this block would exceed airline's max usage
        new_counters = set(range(start_counter, end_counter + 1))
        total_after = len(airline_counters_in_use | new_counters)
        if total_after > max_airline_counters:
            continue
            
        block_free = all(is_counter_free(c, checkin_open, checkin_close) for c in range(start_counter, end_counter + 1))
        if block_free:
            penalty = get_future_counter_penalty(start_counter, end_counter)
            potential_blocks.append((start_counter, end_counter, penalty))
            
    if not potential_blocks:
        return None
        
    # Pick block with lowest penalty (and then lowest counter number)
    potential_blocks.sort(key=lambda x: (x[2], x[0]))
    best_start, best_end, _ = potential_blocks[0]
    
    alloc = CheckInAllocation(
        flight_request=flight,
        counter_from=best_start,
        counter_to=best_end,
        date=date_,
        start_time=checkin_open,
        end_time=checkin_close,
    )
    alloc.save()
    if alloc_cache is not None:
        alloc_cache.setdefault(f"checkin_{date_}", []).append(alloc)
    return alloc

    return None  # No counters available


def allocate_resources_for_date(
    date_: date,
    alloc_cache: Optional[dict[str, Any]] = None,
) -> dict[str, int]:
    """
    Auto-allocate stands, gates, and check-in counters for all flights on a date.
    Returns a summary dict with counts of successful allocations and conflicts.
    """
    from core.services.season import get_season_for_date

    season, year = get_season_for_date(date_)
    flights = FlightRequest.objects.filter(
        season=season, year=year, status__in=['pending', 'conflict']
    ).select_related('airline', 'aircraft_type')

    # Sort flights by "Preference Priority" then by Time.
    # This ensures high-preference flights (EK, QR, etc.) get first pick of their stands,
    # effectively "reserving" them even if they arrive later in the day.
    def flight_priority_key(f: FlightRequest) -> tuple[int, time]:
        p_val = 0
        if f.airline.icao_code in ('QTR', 'BEL', 'ABY', 'MSR', 'UAE'):
            p_val = 2
        elif f.airline.is_home_airline:
            p_val = 1
        return (-p_val, f.arrival_time or time(0,0))
    
    flights = sorted(list(flights), key=flight_priority_key)

    results = {'allocated': 0, 'conflicts': 0, 'skipped': 0}

    for flight in flights:
        if not flight.operates_on_date(date_):
            results['skipped'] += 1
            continue

        # Run allocations
        # These functions have internal "already allocated" checks
        stand = allocate_stand(flight, date_, alloc_cache, all_day_flights=flights)
        gate = allocate_gate(flight, date_, alloc_cache)
        checkin = allocate_checkin(flight, date_, alloc_cache, all_day_flights=flights)

        # Determine if the flight was successfully allocated or already had allocations
        # A flight is considered 'allocated' if any new allocation was made,
        # or if all relevant allocations (stand, gate, checkin) already existed.
        
        # Check if any new allocation was made
        new_allocation_made = bool(stand or gate or checkin)

        # Check if allocations already existed (if no new ones were made)
        # We check for existence of StandAllocation as a proxy for overall allocation status
        # because StandAllocation is the most complex and critical.
        # The sub-functions (allocate_stand, allocate_gate, allocate_checkin)
        # will return None if an allocation already exists for that specific resource.
        # So, if all three return None, it means either they all already existed,
        # or they couldn't be allocated.
        
        # To differentiate, we explicitly check if a StandAllocation exists.
        # If it exists, we assume the flight was already handled for this date.
        stand_already_exists = StandAllocation.objects.filter(flight_request=flight, date=date_).exists()
        gate_already_exists = GateAllocation.objects.filter(flight_request=flight, date=date_).exists()
        checkin_already_exists = CheckInAllocation.objects.filter(flight_request=flight, date=date_).exists()

        # A flight is considered 'allocated' if:
        # 1. A new allocation was successfully made for any resource (stand, gate, or checkin).
        # OR
        # 2. All relevant resources (stand, gate, checkin) already had allocations.
        #    (We simplify this by checking if stand_already_exists is true,
        #     as stand allocation is usually the primary one and implies others might also exist or be handled.)
        
        # Refined logic:
        # If any new allocation was made, it's allocated.
        # Else, if all three (stand, gate, checkin) already existed, it's allocated.
        # Else, it's a conflict.

        if new_allocation_made:
            results['allocated'] += 1
            flight.status = 'allocated'
        elif stand_already_exists and gate_already_exists and checkin_already_exists:
            # All three already existed, so count as allocated
            results['allocated'] += 1
            flight.status = 'allocated'
        else:
            # No new allocation, and not all existing allocations found (or none at all)
            results['conflicts'] += 1
            flight.status = 'conflict'
        flight.save()

    return results


def get_conflicts_for_date(date_: date) -> list[FlightRequest]:
    """Return list of flights with conflicts on a given date."""
    return list(FlightRequest.objects.filter(status='conflict'))


def allocate_resources_for_flight(
    flight: FlightRequest,
    alloc_cache: Optional[dict[str, Any]] = None,
) -> dict[str, int]:
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

        stand = allocate_stand(flight, current, alloc_cache)
        
        # For overnight flights, allocate_stand handles all intermediate dates.
        # Gate and check-in are always allocated on the departure date.
        departure_date = current + flight.departure_date_offset
        gate = allocate_gate(flight, departure_date, alloc_cache)
        checkin = allocate_checkin(flight, departure_date, alloc_cache, all_day_flights=[flight]) # Minimal list for single flight

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

