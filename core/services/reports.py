from django.db.models import Count, Q, Sum
from collections import defaultdict
from core.models import FlightRequest, Airline, CheckInAllocation, GateAllocation, StandAllocation

def generate_report_data(season: str, year: int) -> dict:
    """Generate all analytical data required for the reports dashboard."""
    flights = FlightRequest.objects.filter(season=season, year=year)
    total_flights = flights.count()
    
    available_seasons = list(FlightRequest.objects.values('season', 'year').distinct())

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
    hourly_pax = [0] * 24
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
        
        'avg_daily_pax': avg_daily_pax,
        'avg_daily_vehicles': avg_daily_vehicles,
        'hourly_pax': hourly_pax,
        'hourly_vehicles': hourly_vehicles,
        
        'overnight_flights': overnight_flights,
    }
