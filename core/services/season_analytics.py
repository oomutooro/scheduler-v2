"""Daily-schedule and season-analytics data for the reports section.

Every flight request is expanded into dated movements (arrivals and departures) in local (EAT) time.
A departure that lands on a later day than its inbound (ground_days > 0) is placed on that later day.
"""

from collections import Counter
from datetime import date, time, timedelta
from typing import Any, Optional

from core.models import (
    CheckInAllocation, CheckInCounter, FlightRequest, Gate, GateAllocation,
    ParkingStand, StandAllocation,
)
from core.services.season import last_sunday_of_march

WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MAX_RANGE_DAYS = 400


def last_sunday_of_october(year: int) -> date:
    day = date(year, 10, 31)
    while day.weekday() != 6:
        day -= timedelta(days=1)
    return day


def season_window(season: str, year: int) -> tuple[date, date]:
    """IATA season window: last Sunday of March/October through the day before the next change."""
    if season == 'summer':
        return last_sunday_of_march(year), last_sunday_of_october(year) - timedelta(days=1)
    return last_sunday_of_october(year), last_sunday_of_march(year + 1) - timedelta(days=1)


def _day_bit(day: date) -> int:
    """Bitmask used by FlightRequest.days_of_operation (Sunday = 1 ... Saturday = 64)."""
    return 1 << ((day.weekday() + 1) % 7)


def _movement(f: FlightRequest, day: date, op_date: date, at: time, kind: str, number: str, route: str) -> dict[str, Any]:
    return {
        'date': day,
        'op_date': op_date,
        'time': at,
        'kind': kind,
        'flight': number or '-',
        'flight_id': int(f.pk),
        'airline_code': f.airline.iata_code,
        'airline': f.airline.name,
        'aircraft': f.aircraft_type.code,
        'aircraft_name': f.aircraft_type.name,
        'size': f.aircraft_type.size_code,
        'wide_body': f.aircraft_type.is_wide_body,
        'route': route,
        'stand': '',
        'gate': '',
        'counters': '',
    }


def build_movements(season: str, year: int, start: date, end: date) -> list[dict[str, Any]]:
    """Return all arrival/departure movements of a season that fall within [start, end]."""
    flights = (
        FlightRequest.objects.filter(season=season, year=year)
        .exclude(status='cancelled')
        .select_related('airline', 'aircraft_type', 'origin', 'destination')
    )
    movements: list[dict[str, Any]] = []
    for f in flights:
        origin = f.origin.iata_code if f.origin else '—'
        destination = f.destination.iata_code if f.destination else '—'
        first = max(f.valid_from or start, start - timedelta(days=f.ground_days))
        last = min(f.valid_to or end, end)
        day = first
        while day <= last:
            if f.days_of_operation & _day_bit(day):
                if f.operation_type in ('arrival', 'turnaround') and f.arrival_time:
                    movements.append(_movement(f, day, day, f.arrival_time, 'ARR', f.arrival_flight_number, f'{origin} → EBB'))
                if f.operation_type in ('departure', 'turnaround') and f.departure_time:
                    departs = day + timedelta(days=f.ground_days)
                    movements.append(_movement(f, departs, day, f.departure_time, 'DEP', f.departure_flight_number, f'EBB → {destination}'))
            day += timedelta(days=1)
    return [m for m in movements if start <= m['date'] <= end]


def weekly_schedule(season: str, year: int, start: date, end: date, direction: str = '') -> list[dict[str, Any]]:
    """Monday-Sunday flight pattern: one row per flight request, ordered 00:00 -> 23:59 within each day.

    Turnarounds are one row (arrival and departure side by side); one-way flights stand alone.
    A departure that leaves the day after its inbound is flagged with next_day.
    """
    days: list[list[dict[str, Any]]] = [[] for _ in WEEKDAYS]
    flights = (
        FlightRequest.objects.filter(season=season, year=year)
        .exclude(status='cancelled')
        .select_related('airline', 'origin', 'destination')
    )
    for f in flights:
        has_arrival = f.operation_type in ('arrival', 'turnaround') and f.arrival_time is not None
        has_departure = f.operation_type in ('departure', 'turnaround') and f.departure_time is not None
        if direction == 'ARR':
            has_departure = False
        elif direction == 'DEP':
            has_arrival = False
        if not (has_arrival or has_departure):
            continue

        weekdays: set[int] = set()
        day, last = max(f.valid_from or start, start), min(f.valid_to or end, end)
        while day <= last and len(weekdays) < 7:
            if f.days_of_operation & _day_bit(day):
                weekdays.add(day.weekday())
            day += timedelta(days=1)

        row = {
            'airline': f.airline.name,
            'arr_flight': f.arrival_flight_number if has_arrival else '',
            'arr_time': f.arrival_time if has_arrival else None,
            'origin': f.origin.iata_code if has_arrival and f.origin else '',
            'dep_flight': f.departure_flight_number if has_departure else '',
            'dep_time': f.departure_time if has_departure else None,
            'destination': f.destination.iata_code if has_departure and f.destination else '',
            'next_day': has_arrival and has_departure and f.ground_days > 0,
        }
        for weekday in weekdays:
            days[weekday].append(row)

    result = []
    for index, name in enumerate(WEEKDAYS):
        rows = sorted(days[index], key=lambda r: (r['arr_time'] or r['dep_time'], r['airline'], r['arr_flight'] or r['dep_flight']))
        result.append({
            'weekday': name,
            'rows': rows,
            'arrivals': sum(1 for r in rows if r['arr_time']),
            'departures': sum(1 for r in rows if r['dep_time']),
        })
    return result


def _is_cargo(f: FlightRequest) -> bool:
    return f.aircraft_type.code.endswith('F') or 'cargo' in (f.notes or '').lower()


def _days_text(weekdays: set[int]) -> str:
    if len(weekdays) == 7:
        return 'Daily'
    return ' '.join(WEEKDAYS[i][:3] for i in sorted(weekdays))


def summary_schedule(season: str, year: int, start: date, end: date) -> dict[str, list[dict[str, Any]]]:
    """All slotted flights ordered by time, split into passenger and cargo, with their operating days.

    Identical flights (same numbers, times and route) are merged and their operating days combined.
    Days follow the arrival (or the departure for one-way departures).
    """
    flights = (
        FlightRequest.objects.filter(season=season, year=year)
        .exclude(status='cancelled')
        .select_related('airline', 'aircraft_type', 'origin', 'destination')
    )
    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    for f in flights:
        has_arrival = f.operation_type in ('arrival', 'turnaround') and f.arrival_time is not None
        has_departure = f.operation_type in ('departure', 'turnaround') and f.departure_time is not None
        if not (has_arrival or has_departure):
            continue

        weekdays: set[int] = set()
        first, last = max(f.valid_from or start, start), min(f.valid_to or end, end)
        day, seen_from, seen_to = first, None, None
        while day <= last:
            if f.days_of_operation & _day_bit(day):
                weekdays.add(day.weekday())
                seen_from = seen_from or day
                seen_to = day
            day += timedelta(days=1)
        if not weekdays:
            continue

        row = {
            'airline': f.airline.name,
            'type': 'Cargo' if _is_cargo(f) else 'Pax',
            'arr_flight': f.arrival_flight_number if has_arrival else '',
            'arr_time': f.arrival_time if has_arrival else None,
            'origin': f.origin.iata_code if has_arrival and f.origin else '',
            'dep_flight': f.departure_flight_number if has_departure else '',
            'dep_time': f.departure_time if has_departure else None,
            'destination': f.destination.iata_code if has_departure and f.destination else '',
            'next_day': has_arrival and has_departure and f.ground_days > 0,
        }
        key = (row['airline'], row['type'], row['arr_flight'], row['arr_time'], row['origin'],
               row['dep_flight'], row['dep_time'], row['destination'])
        entry = merged.setdefault(key, {**row, 'weekdays': set(), 'from': seen_from, 'to': seen_to})
        entry['weekdays'] |= weekdays
        entry['from'] = min(entry['from'], seen_from)
        entry['to'] = max(entry['to'], seen_to)

    result: dict[str, list[dict[str, Any]]] = {'Pax': [], 'Cargo': []}
    for entry in merged.values():
        entry['days'] = _days_text(entry['weekdays'])
        entry['period'] = f"{entry['from']:%d %b %Y} – {entry['to']:%d %b %Y}"
        result[entry['type']].append(entry)
    for rows in result.values():
        rows.sort(key=lambda r: (r['arr_time'] or r['dep_time'], r['airline'], r['arr_flight'] or r['dep_flight']))
    return result


def _hours_touched(start_t: time, end_t: time) -> set[int]:
    s = start_t.hour * 60 + start_t.minute
    e = end_t.hour * 60 + end_t.minute
    if e <= s:
        e += 1440
    return {h % 24 for h in range(s // 60, (e + 59) // 60)}


def _heat_style(value: float, peak: float) -> tuple[float, str]:
    intensity = value / peak if peak else 0.0
    alpha = 0.05 + 0.95 * intensity if value else 0.0
    return intensity, f'background: rgba(26, 86, 219, {alpha:.2f});'


def _resource_usage(labels: list[str], allocations: list[tuple[list[str], date, time, time]], total_days: int) -> dict[str, Any]:
    dates: dict[str, list[set[date]]] = {label: [set() for _ in range(24)] for label in labels}
    counts: Counter[str] = Counter()
    for keys, day, start_t, end_t in allocations:
        hours = _hours_touched(start_t, end_t)
        for key in keys:
            if key not in dates:
                continue
            counts[key] += 1
            for hour in hours:
                dates[key][hour].add(day)

    peak = max((len(cell) for rows in dates.values() for cell in rows), default=0)
    rows = []
    for label in labels:
        cells = []
        for hour, days_used in enumerate(dates[label]):
            percent = round(100 * len(days_used) / total_days, 1) if total_days else 0.0
            intensity, style = _heat_style(len(days_used), peak)
            cells.append({'hour': hour, 'percent': percent, 'days': len(days_used), 'intensity': intensity, 'style': style})
        busiest = max(range(24), key=lambda h: len(dates[label][h])) if counts[label] else None
        rows.append({
            'label': label,
            'allocations': counts[label],
            'busiest_hour': f'{busiest:02d}:00' if busiest is not None else '—',
            'cells': cells,
        })
    return {'rows': rows, 'chart_labels': labels, 'chart_values': [counts[label] for label in labels]}


def resource_usage(start: date, end: date, total_days: int) -> dict[str, Any]:
    gate_labels = [f'Gate {g.gate_number}' for g in Gate.objects.filter(is_active=True)]
    counter_labels = [f'C{c.counter_number}' for c in CheckInCounter.objects.filter(is_active=True)]
    stand_labels = [f'Stand {s.stand_number}' for s in ParkingStand.objects.filter(is_active=True)]

    gate_rows = [
        ([f'Gate {a.gate.gate_number}'], a.date, a.start_time, a.end_time)
        for a in GateAllocation.objects.filter(date__range=(start, end)).select_related('gate')
    ]
    stand_rows = [
        ([f'Stand {a.stand.stand_number}'], a.date, a.start_time, a.end_time)
        for a in StandAllocation.objects.filter(date__range=(start, end)).select_related('stand')
    ]
    counter_rows = [
        ([f'C{n}' for n in range(a.counter_from, a.counter_to + 1)], a.date, a.start_time, a.end_time)
        for a in CheckInAllocation.objects.filter(date__range=(start, end))
    ]
    return {
        'gates': _resource_usage(gate_labels, gate_rows, total_days),
        'counters': _resource_usage(counter_labels, counter_rows, total_days),
        'stands': _resource_usage(stand_labels, stand_rows, total_days),
        'gate_allocation_count': len(gate_rows),
    }


def season_analytics(season: str, year: int, start: date, end: date) -> dict[str, Any]:
    movements = build_movements(season, year, start, end)
    total_days = (end - start).days + 1
    all_days = [start + timedelta(days=i) for i in range(total_days)]
    weekday_dates = Counter(d.weekday() for d in all_days)

    by_weekday = {'ARR': [0] * 7, 'DEP': [0] * 7}
    by_hour = {'ARR': [0] * 24, 'DEP': [0] * 24}
    heat = [[0] * 24 for _ in range(7)]
    per_date: dict[date, dict[str, int]] = {d: {'ARR': 0, 'DEP': 0} for d in all_days}
    aircraft: dict[str, dict[str, Any]] = {}
    sizes: Counter[str] = Counter()
    airlines: dict[str, dict[str, Any]] = {}

    for m in movements:
        weekday, hour = m['date'].weekday(), m['time'].hour
        by_weekday[m['kind']][weekday] += 1
        by_hour[m['kind']][hour] += 1
        heat[weekday][hour] += 1
        per_date[m['date']][m['kind']] += 1
        entry = aircraft.setdefault(m['aircraft'], {'code': m['aircraft'], 'name': m['aircraft_name'], 'size': m['size'], 'movements': 0})
        entry['movements'] += 1
        sizes[f"Code {m['size']}"] += 1
        airline = airlines.setdefault(m['airline_code'], {'code': m['airline_code'], 'name': m['airline'], 'movements': 0})
        airline['movements'] += 1

    total = len(movements)

    weekday_rows = []
    for i, name in enumerate(WEEKDAYS):
        dates = weekday_dates[i] or 1
        arr, dep = by_weekday['ARR'][i], by_weekday['DEP'][i]
        weekday_rows.append({
            'name': name, 'dates': weekday_dates[i], 'arr_total': arr, 'dep_total': dep,
            'arr': round(arr / dates, 1), 'dep': round(dep / dates, 1), 'total': round((arr + dep) / dates, 1),
        })

    hour_rows = []
    for h in range(24):
        arr, dep = by_hour['ARR'][h], by_hour['DEP'][h]
        hour_rows.append({
            'hour': h, 'label': f'{h:02d}:00', 'arr_total': arr, 'dep_total': dep, 'total': arr + dep,
            'arr': round(arr / total_days, 2), 'dep': round(dep / total_days, 2), 'avg': round((arr + dep) / total_days, 2),
        })

    heat_values = [[heat[w][h] / (weekday_dates[w] or 1) for h in range(24)] for w in range(7)]
    heat_peak = max((v for row in heat_values for v in row), default=0.0)
    heat_rows = []
    for w, name in enumerate(WEEKDAYS):
        cells = []
        for h in range(24):
            intensity, style = _heat_style(heat_values[w][h], heat_peak)
            cells.append({'hour': h, 'value': round(heat_values[w][h], 1), 'intensity': intensity, 'style': style})
        heat_rows.append({'name': name, 'cells': cells})

    daily = [
        {'date': d, 'weekday': WEEKDAYS[d.weekday()], 'arr': c['ARR'], 'dep': c['DEP'], 'total': c['ARR'] + c['DEP']}
        for d, c in sorted(per_date.items())
    ]
    busiest_dates = sorted(daily, key=lambda r: (-r['total'], r['date']))[:10]
    quietest_dates = sorted(daily, key=lambda r: (r['total'], r['date']))[:5]

    ranked_hours = sorted(hour_rows, key=lambda r: (-r['total'], r['hour']))
    quiet_min = min((r['total'] for r in hour_rows), default=0)
    quiet_hours = [r['label'] for r in hour_rows if r['total'] == quiet_min]

    aircraft_rows = sorted(aircraft.values(), key=lambda r: (-r['movements'], r['code']))
    for row in aircraft_rows:
        row['share'] = round(100 * row['movements'] / total, 1) if total else 0.0
    airline_rows = sorted(airlines.values(), key=lambda r: (-r['movements'], r['code']))
    for row in airline_rows:
        row['share'] = round(100 * row['movements'] / total, 1) if total else 0.0
    size_rows = [{'label': label, 'movements': count} for label, count in sorted(sizes.items())]

    resources = resource_usage(start, end, total_days)
    departures = sum(by_hour['DEP'])
    busiest_weekday = max(weekday_rows, key=lambda r: r['total']) if total else None
    quietest_weekday = min(weekday_rows, key=lambda r: r['total']) if total else None
    busiest_day = busiest_dates[0] if total else None
    quietest_day = quietest_dates[0] if total else None

    return {
        'season': season, 'year': year, 'start': start, 'end': end, 'total_days': total_days,
        'total_movements': total, 'arrivals': sum(by_hour['ARR']), 'departures': departures,
        'avg_per_day': round(total / total_days, 1) if total_days else 0.0,
        'flight_requests': len({m['flight_id'] for m in movements}),
        'busiest_weekday': busiest_weekday, 'quietest_weekday': quietest_weekday,
        'busiest_day': busiest_day, 'quietest_day': quietest_day,
        'busiest_hours': ranked_hours[:3], 'quiet_hours': quiet_hours, 'quiet_hours_count': quiet_min,
        'weekday_rows': weekday_rows, 'hour_rows': hour_rows, 'heat_rows': heat_rows, 'heat_peak': round(heat_peak, 1),
        'daily': daily, 'busiest_dates': busiest_dates, 'quietest_dates': quietest_dates,
        'aircraft_rows': aircraft_rows, 'size_rows': size_rows, 'airline_rows': airline_rows,
        'resources': resources,
        'allocation_coverage': round(100 * resources['gate_allocation_count'] / departures, 1) if departures else 0.0,
    }


def default_year(season: str) -> int:
    from django.db.models import Max
    latest = FlightRequest.objects.filter(season=season).aggregate(latest=Max('year'))['latest']
    return latest or date.today().year


def clamp_range(start: Optional[date], end: Optional[date], default: tuple[date, date]) -> tuple[date, date]:
    start = start or default[0]
    end = end or default[1]
    if end < start:
        start, end = end, start
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        end = start + timedelta(days=MAX_RANGE_DAYS - 1)
    return start, end
