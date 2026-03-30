from datetime import datetime, date, time, timedelta
from typing import Any
from core.models import FlightRequest
from core.services.allocation import time_add_minutes, allocate_stand, allocate_gate, allocate_checkin
from core.services.season import get_season_dates

def _try_allocate_times(
    flight: FlightRequest,
    arrival: time | None,
    departure: time | None,
    test_dates: list[date],
) -> bool:
    """
    Simulate allocating resources for the flight at the given test times, across all test dates.
    We temporarily modify the flight's times, run the allocation logic, and roll back.
    Since allocate_* functions save directly to DB, we run this inside an atomic transaction block that we rollback later.
    """
    from django.db import transaction
    
    orig_arrival = flight.arrival_time
    orig_departure = flight.departure_time
    
    if flight.operation_type == 'arrival':
        flight.arrival_time = arrival
        flight.departure_time = None
    elif flight.operation_type == 'departure':
        flight.arrival_time = None
        flight.departure_time = departure
    else:
        flight.arrival_time = arrival
        flight.departure_time = departure

    success = True
    
    try:
        with transaction.atomic():
            for d in test_dates:
                # Stand
                if allocate_stand(flight, d) is None:
                    raise Exception("SimulationFailed")
                
                # Gate / Check-in on departure day
                dep_date = d + flight.departure_date_offset
                if flight.operation_type != 'arrival':
                    if allocate_gate(flight, dep_date) is None:
                        raise Exception("SimulationFailed")
                    if allocate_checkin(flight, dep_date) is None:
                        raise Exception("SimulationFailed")
            # Always rollback to avoid committing simulated allocations
            raise Exception("SimulationComplete")
    except Exception as e:
        if str(e) == "SimulationFailed":
            success = False
        elif str(e) != "SimulationComplete":
            raise e
            
    # Restore original times
    flight.arrival_time = orig_arrival
    flight.departure_time = orig_departure
    
    return success

def find_alternative_slots(
    flight: FlightRequest,
    max_hours_search: int = 4,
    interval_mins: int = 15,
) -> list[dict[str, Any]]:
    """
    Finds alternative arrival/departure times for a flight that resolve its conflicts.
    Searches forward and backward by max_hours_search, in steps of interval_mins.
    Returns a list of dicts with the suggested arrival and departure times.
    """
    if flight.arrival_time is None and flight.departure_time is None:
        return []
        
    range_start = flight.valid_from
    range_end = flight.valid_to
    
    if not range_start or not range_end:
        rs, re = get_season_dates(flight.season, flight.year)
        range_start = range_start or rs
        range_end = range_end or re
        
    # Find all operating dates
    operating_dates = []
    curr = range_start
    while curr <= range_end:
        if flight.operates_on_date(curr):
            operating_dates.append(curr)
        curr += timedelta(days=1)
        
    if not operating_dates:
        return []
        
    # Determine the anchor time for generating shifts
    orig_arrival = flight.arrival_time
    orig_departure = flight.departure_time
    anchor_time = orig_arrival or orig_departure
    assert anchor_time is not None
    
    # Calculate difference between arrival and departure if both exist
    duration_mins = 0
    if orig_arrival and orig_departure:
        arr_dt = datetime.combine(date.today(), orig_arrival)
        dep_dt = datetime.combine(date.today(), orig_departure)
        if dep_dt < arr_dt:
            dep_dt += timedelta(days=1)
        duration_mins = int((dep_dt - arr_dt).total_seconds() / 60)

    suggestions = []
    
    # Test shifts (e.g., +15, -15, +30, -30...)
    shifts = [0]
    for i in range(interval_mins, max_hours_search * 60 + 1, interval_mins):
        shifts.append(i)
        shifts.append(-i)
        
    for shift in shifts:
        if shift == 0:
            continue # We already know original time has conflicts
            
        test_anchor = time_add_minutes(anchor_time, shift)
        
        test_arrival = None
        test_departure = None
        
        if flight.operation_type == 'arrival':
            test_arrival = test_anchor
        elif flight.operation_type == 'departure':
            test_departure = test_anchor
        else:
            if orig_arrival:
                test_arrival = test_anchor
                test_departure = time_add_minutes(test_arrival, duration_mins)
            else:
                test_departure = test_anchor
                # Normally turnaround has both, but fallback just in case
                test_arrival = time_add_minutes(test_departure, -duration_mins)

        if _try_allocate_times(flight, test_arrival, test_departure, operating_dates):
            suggestions.append({
                'shift_mins': shift,
                'arrival_time': test_arrival,
                'departure_time': test_departure
            })
            
            # Stop after finding 3 good alternatives
            if len(suggestions) >= 3:
                break
                
    # Sort suggestions by magnitude of shift
    suggestions.sort(key=lambda x: abs(x['shift_mins']))
    
    return suggestions
