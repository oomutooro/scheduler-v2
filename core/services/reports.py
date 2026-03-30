from django.db.models import Count
from collections import defaultdict
from typing import Any
from core.models import FlightRequest

def generate_report_data(season: str, year: int) -> dict[str, Any]:
    """Generate all analytical data required for the reports dashboard."""
    flights = FlightRequest.objects.filter(season=season, year=year)
    total_flights = flights.count()
    
    # clear model ordering before calling distinct so the SQL doesn't
    # silently include an ORDER BY column (created_at) which defeats the
    # DISTINCT clause and returns one entry per flight.  see ticket about
    # duplicate season buttons.
    available_seasons = list(
        FlightRequest.objects
            .order_by('season', 'year')
            .values('season', 'year')
            .distinct()
    )

    if total_flights == 0:
        return {'total_flights': 0, 'season': season, 'year': year, 'available_seasons': available_seasons}

    # 1. Flight Statistics
    ops_breakdown = flights.values('operation_type').annotate(count=Count('id'))
    ops_dict = {item['operation_type']: item['count'] for item in ops_breakdown}

    size_breakdown = flights.values('aircraft_type__size_code').annotate(count=Count('id'))
    size_dict = {item['aircraft_type__size_code']: item['count'] for item in size_breakdown}

    airline_breakdown = flights.values('airline__name', 'airline__iata_code').annotate(count=Count('id')).order_by('-count')

    # Calculate day of week frequency based on bitmask
    day_counts = {'Sunday': 0, 'Monday': 0, 'Tuesday': 0, 'Wednesday': 0, 'Thursday': 0, 'Friday': 0, 'Saturday': 0}
    day_masks = [
        ('Sunday', 1), ('Monday', 2), ('Tuesday', 4), ('Wednesday', 8),
        ('Thursday', 16), ('Friday', 32), ('Saturday', 64)
    ]
    
    for f in flights:
        for day_name, pos in day_masks:
            if f.days_of_operation & pos:
                day_counts[day_name] += 1

    # 2. Time-of-Day Analysis
    hourly_arrivals = [0] * 24
    hourly_departures = [0] * 24
    
    for f in flights:
        if f.arrival_time:
            hourly_arrivals[f.arrival_time.hour] += 1
        if f.departure_time:
            hourly_departures[f.departure_time.hour] += 1

    peak_arr_hour = hourly_arrivals.index(max(hourly_arrivals)) if max(hourly_arrivals) > 0 else None
    peak_dep_hour = hourly_departures.index(max(hourly_departures)) if max(hourly_departures) > 0 else None
    
    busiest_day = max(day_counts.items(), key=lambda x: x[1])[0] if any(day_counts.values()) else "N/A"

    # 3. Airline Performance
    airline_perf = []
    for ab in airline_breakdown:
        qs = flights.filter(airline__iata_code=ab['airline__iata_code'])
        # Estimate daily pax: sum of capacity * frequency per week / 7
        total_pax = 0
        fleet = set()
        routes = defaultdict(int)
        
        for f in qs:
            freq = sum(1 for _, pos in day_masks if f.days_of_operation & pos)
            total_pax += (f.aircraft_type.pax_capacity * freq)
            fleet.add(f.aircraft_type.code)
            if f.origin: routes[f.origin.iata_code] += 1
            if f.destination: routes[f.destination.iata_code] += 1
        
        top_route = max(routes.items(), key=lambda x: x[1])[0] if routes else "N/A"
        
        airline_perf.append({
            'airline': ab['airline__name'],
            'code': ab['airline__iata_code'],
            'flights': ab['count'],
            'weekly_pax_est': total_pax,
            'fleet_types': list(fleet),
            'top_route': top_route
        })

    # Sort airline perf by pax
    airline_perf.sort(key=lambda x: x['weekly_pax_est'], reverse=True)

    # prepare chart arrays for airline performance visualization
    airline_chart_labels = [f"{p['code']} {p['airline']}" for p in airline_perf]
    airline_chart_values = [p['weekly_pax_est'] for p in airline_perf]

    # 4. Resource Utilization & Passenger Load (Daily Estimates)
    # Estimate average daily flights
    total_weekly_freq = sum(
        sum(1 for _, pos in day_masks if f.days_of_operation & pos)
        for f in flights
    )
    avg_daily_flights = total_weekly_freq / 7.0
    
    # Estimate average daily pax
    avg_daily_pax = sum(p['weekly_pax_est'] for p in airline_perf) / 7.0
    
    # Estimate vehicles arriving at toll
    avg_daily_vehicles = avg_daily_pax * 0.3
    
    # Hourly load curves (Pax and vehicles)
    hourly_pax = [0.0] * 24
    for f in flights:
        freq = sum(1 for _, pos in day_masks if f.days_of_operation & pos)
        daily_freq = freq / 7.0
        pax = f.aircraft_type.pax_capacity * daily_freq
        
        if f.arrival_time:
            # People arriving
            hr = f.arrival_time.hour
            hourly_pax[hr] += pax
        if f.departure_time:
            # People departing (typically at terminal 2 hrs prior)
            hr = max(0, f.departure_time.hour - 2)
            hourly_pax[hr] += pax

    hourly_vehicles = [p * 0.3 for p in hourly_pax]

    # Overnight flights count
    overnight_flights = flights.filter(ground_days__gt=0).count()

    return {
        'season': season,
        'year': year,
        'total_flights': total_flights,
        'total_weekly_freq': total_weekly_freq,
        'avg_daily_flights': avg_daily_flights,
        
        'available_seasons': available_seasons,
        
        'ops_dict': ops_dict,
        'size_dict': size_dict,
        'day_counts': day_counts,
        
        'hourly_arrivals': hourly_arrivals,
        'hourly_departures': hourly_departures,
        'peak_arr_hour': peak_arr_hour,
        'peak_dep_hour': peak_dep_hour,
        'busiest_day': busiest_day,
        
        'airline_perf': airline_perf,
        'airline_chart_labels': airline_chart_labels,
        'airline_chart_values': airline_chart_values,
        
        'avg_daily_pax': avg_daily_pax,
        'avg_daily_vehicles': avg_daily_vehicles,
        'hourly_pax': hourly_pax,
        'hourly_vehicles': hourly_vehicles,
        
        'overnight_flights': overnight_flights,
    }


def generate_daily_analysis(season: str, year: int, day_of_week: str) -> dict[str, Any]:
    """Compute metrics to support the daily resource utilisation dashboard.

    * `day_of_week` should be one of 'sunday'..'saturday' (lowercase).
    * Returns a dictionary suitable for passing straight to the template.
    """
    from core.models import (
        StandAllocation, GateAllocation, CheckInAllocation,
        ParkingStand, Gate, CheckInCounter
    )

    # normalise day name
    day_masks = {
        'sunday': 1, 'monday': 2, 'tuesday': 4, 'wednesday': 8,
        'thursday': 16, 'friday': 32, 'saturday': 64
    }
    if day_of_week not in day_masks:
        day_of_week = 'monday'
    mask = day_masks[day_of_week]

    # gather flights operating on that day
    flights = FlightRequest.objects.filter(season=season, year=year)
    day_flights = [f for f in flights if f.days_of_operation & mask]
    total_flights = len(day_flights)

    # gather allocations for those flights, then filter by weekday of allocation date
    flight_ids = [int(f.pk) for f in day_flights]
    stand_allocs = StandAllocation.objects.filter(flight_request_id__in=flight_ids).select_related('flight_request', 'stand')
    gate_allocs = GateAllocation.objects.filter(flight_request_id__in=flight_ids).select_related('flight_request', 'gate')
    checkin_allocs = CheckInAllocation.objects.filter(flight_request_id__in=flight_ids).select_related('flight_request')

    dow_mapping = {'sunday': 6, 'monday': 0, 'tuesday': 1, 'wednesday': 2,
                   'thursday': 3, 'friday': 4, 'saturday': 5}
    target_dow = dow_mapping[day_of_week]

    day_allocs_stand = [a for a in stand_allocs if a.date.weekday() == target_dow]
    day_allocs_gate = [a for a in gate_allocs if a.date.weekday() == target_dow]
    day_allocs_checkin = [a for a in checkin_allocs if a.date.weekday() == target_dow]

    # build gantt-like data (similar to view)
    gantt_data = []
    for flight in day_flights:
        flight_data = {
            'id': int(flight.pk),
            'name': f"{flight.airline.iata_code} {flight.display_flight_numbers}",
            'arrival_time': flight.arrival_time,
            'departure_time': flight.departure_time,
            'ground_days': flight.ground_days,
            'resources': []
        }

        for alloc_list, rtype, color in (
            (day_allocs_stand, 'stand', '#4CAF50'),
            (day_allocs_gate, 'gate', '#2196F3'),
            (day_allocs_checkin, 'checkin', '#FF9800'),
        ):
            alloc = next((a for a in alloc_list if a.flight_request == flight), None)
            if alloc:
                start_minutes = alloc.start_time.hour * 60 + alloc.start_time.minute
                end_minutes = alloc.end_time.hour * 60 + alloc.end_time.minute
                if end_minutes < start_minutes:
                    end_minutes += 24 * 60
                duration_hrs = (end_minutes - start_minutes) / 60
                left_percent = (start_minutes / (24 * 60)) * 100
                width_percent = (duration_hrs / 24) * 100

                resource_name = ''
                if rtype == 'stand':
                    resource_name = f"Stand {alloc.stand.stand_number}"
                elif rtype == 'gate':
                    resource_name = f"Gate {alloc.gate.gate_number}"
                else:
                    resource_name = f"Counters {alloc.counter_from}-{alloc.counter_to}"

                flight_data['resources'].append({
                    'type': rtype,
                    'resource': resource_name,
                    'start': alloc.start_time,
                    'end': alloc.end_time,
                    'left_percent': left_percent,
                    'width_percent': width_percent,
                    'color': color
                })
        gantt_data.append(flight_data)

    # utilisation counts per hour
    import math
    hourly_flight_set = {h: set() for h in range(24)}
    hourly_stand = [0] * 24
    hourly_gate = [0] * 24
    hourly_checkin = [0] * 24

    def mark_hours(alloc: Any, hour_list: list[int], flight_set: dict[int, set[int]]) -> None:
        start = alloc.start_time.hour + alloc.start_time.minute / 60
        end = alloc.end_time.hour + alloc.end_time.minute / 60
        if end < start:
            end += 24
        for h in range(int(math.floor(start)), int(math.ceil(end))):
            hour_list[h % 24] += 1
            flight_set[h % 24].add(int(alloc.flight_request.pk))

    for a in day_allocs_stand:
        mark_hours(a, hourly_stand, hourly_flight_set)
    for a in day_allocs_gate:
        mark_hours(a, hourly_gate, hourly_flight_set)
    for a in day_allocs_checkin:
        mark_hours(a, hourly_checkin, hourly_flight_set)

    hourly_counts = [len(hourly_flight_set[h]) for h in range(24)]

    # total resource hours
    def duration_hours(a: Any) -> float:
        s = a.start_time.hour * 60 + a.start_time.minute
        e = a.end_time.hour * 60 + a.end_time.minute
        if e < s:
            e += 24 * 60
        return (e - s) / 60

    stand_hours = sum(duration_hours(a) for a in day_allocs_stand)
    gate_hours = sum(duration_hours(a) for a in day_allocs_gate)
    checkin_hours = sum(duration_hours(a) for a in day_allocs_checkin)

    total_stands = ParkingStand.objects.filter(is_active=True, parent_stand__isnull=True).count()
    total_gates = Gate.objects.filter(is_active=True).count()
    total_counters = CheckInCounter.objects.filter(is_active=True).count()

    # number of distinct flights with at least one resource allocated on the selected day
    allocated_ids = set()
    for a in day_allocs_stand + day_allocs_gate + day_allocs_checkin:
        allocated_ids.add(int(a.flight_request.pk))
    allocated_flights = len(allocated_ids)
    allocation_percentage = (allocated_flights / total_flights * 100) if total_flights > 0 else 0

    busiest_hour = None
    if hourly_counts:
        maxcnt = max(hourly_counts)
        if maxcnt > 0:
            busiest_hour = hourly_counts.index(maxcnt)

    # compute day-of-week frequency across the season (for alternative day suggestions)
    day_counts_all = {'Sunday': 0, 'Monday': 0, 'Tuesday': 0,
                      'Wednesday': 0, 'Thursday': 0,
                      'Friday': 0, 'Saturday': 0}
    for f in flights:
        for day_name, mask_val in day_masks.items():
            if f.days_of_operation & mask_val:
                day_counts_all[day_name.capitalize()] += 1
    least_busy_day = min(day_counts_all.items(), key=lambda x: x[1])[0] if day_counts_all else None

    # choose busiest hour of non-home-airline flights for suggestion baseline
    nonhome_ids = [int(f.pk) for f in day_flights if not f.airline.is_home_airline]
    hourly_nonhome = [0] * 24
    for h in range(24):
        hourly_nonhome[h] = len([fid for fid in hourly_flight_set[h] if fid in nonhome_ids])
    nonhome_busiest = None
    if any(hourly_nonhome):
        nonhome_busiest = hourly_nonhome.index(max(hourly_nonhome))

    suggestions = []
    home_present = any(f.airline.is_home_airline for f in day_flights)
    if nonhome_busiest is not None and nonhome_busiest < len(hourly_flight_set):
        # prepare a rotating list of candidate hours sorted by nonhome traffic asc
        hour_order = sorted(range(24), key=lambda h: hourly_nonhome[h])
        # ensure busiest hour is excluded from recommendations
        hour_order = [h for h in hour_order if h != nonhome_busiest]
        hour_iter = iter(hour_order)

        for fid in hourly_flight_set[nonhome_busiest]:
            flight = next((f for f in day_flights if int(f.pk) == fid), None)
            if flight and not flight.airline.is_home_airline:
                try:
                    rec_hr = next(hour_iter)
                except StopIteration:
                    # wrap around if we run out
                    hour_iter = iter(hour_order)
                    rec_hr = next(hour_iter)
                suggestions.append({
                    'flight': f"{flight.airline.iata_code} {flight.display_flight_numbers}",
                    'current_hour': nonhome_busiest,
                    'recommend_hour': rec_hr,
                    'recommend_day': least_busy_day,
                })

    return {
        'season': season,
        'year': year,
        'day_of_week': day_of_week.capitalize(),
        'day_options': [d.capitalize() for d in day_masks.keys()],
        'gantt_data': gantt_data,
        'total_flights': total_flights,
        'allocated_flights': allocated_flights,
        'allocation_percentage': allocation_percentage,
        'hourly_counts': hourly_counts,
        'hourly_stand': hourly_stand,
        'hourly_gate': hourly_gate,
        'hourly_checkin': hourly_checkin,
        'resource_hours': [stand_hours, gate_hours, checkin_hours],
        'total_stands': total_stands,
        'total_gates': total_gates,
        'total_counters': total_counters,
        'stand_usage_hours': stand_hours,
        'gate_usage_hours': gate_hours,
        'checkin_usage_hours': checkin_hours,
        'busiest_hour': busiest_hour,
        'suggestions': suggestions,
        'least_busy_day': least_busy_day,
        'day_counts_all': day_counts_all,
        'home_present': home_present,
    }
