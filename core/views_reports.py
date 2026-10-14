"""Views for the daily-schedule and season-analytics reports."""

from datetime import date
from typing import Any, Optional

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from core.models import FlightRequest
from core.services import report_exports
from core.services.season_analytics import (
    clamp_range, default_year, season_analytics, season_window, summary_schedule, weekly_schedule,
)

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
DIRECTIONS = {'arrival': 'ARR', 'departure': 'DEP'}


def _date_param(request: HttpRequest, name: str) -> Optional[date]:
    try:
        return date.fromisoformat(request.GET.get(name, ''))
    except ValueError:
        return None


def _scope(request: HttpRequest) -> dict[str, Any]:
    season = request.GET.get('season', 'winter')
    if season not in ('summer', 'winter'):
        season = 'winter'
    try:
        year = int(request.GET.get('year', ''))
    except ValueError:
        year = default_year(season)
    window = season_window(season, year)
    start, end = clamp_range(_date_param(request, 'start'), _date_param(request, 'end'), window)
    return {
        'season': season, 'year': year, 'start': start, 'end': end, 'window': window,
        'available_seasons': list(FlightRequest.objects.order_by('season', 'year').values('season', 'year').distinct()),
    }


def _daily(scope: dict[str, Any], direction: str) -> list[dict[str, Any]]:
    return weekly_schedule(scope['season'], scope['year'], scope['start'], scope['end'], DIRECTIONS.get(direction, ''))


def _label(scope: dict[str, Any], direction: str) -> tuple[str, str]:
    kind = {'arrival': 'Arrivals', 'departure': 'Departures'}.get(direction, 'Arrivals and departures')
    return (
        f"{scope['season'].title()} {scope['year']} Daily Flight Schedule",
        f"{kind} · Monday to Sunday, repeating weekly · ordered 00:00–23:59 · times in EAT",
    )


def daily_flights_report(request: HttpRequest) -> HttpResponse:
    scope = _scope(request)
    direction = request.GET.get('direction', '')
    days = _daily(scope, direction)
    scope.update({
        'days': days,
        'direction': direction if direction in DIRECTIONS else '',
        'total_rows': sum(len(d['rows']) for d in days),
        'active_page': 'reports',
    })
    return render(request, 'reports/daily_flights.html', scope)


def daily_flights_export(request: HttpRequest, fmt: str) -> HttpResponse:
    scope = _scope(request)
    direction = request.GET.get('direction', '')
    days = _daily(scope, direction)
    title, subtitle = _label(scope, direction)
    name = f"{scope['season'].title()}_{scope['year']}_daily_schedule"
    if fmt == 'xlsx':
        return _download(report_exports.daily_workbook(days, title, subtitle), XLSX, f'{name}.xlsx')
    if fmt == 'pdf':
        return _download(report_exports.daily_pdf(days, title, subtitle), 'application/pdf', f'{name}.pdf')
    raise Http404('Unknown export format')


def flight_summary_report(request: HttpRequest) -> HttpResponse:
    scope = _scope(request)
    tables = summary_schedule(scope['season'], scope['year'], scope['start'], scope['end'])
    scope.update({'tables': [('Passenger', tables['Pax']), ('Cargo', tables['Cargo'])], 'active_page': 'reports'})
    return render(request, 'reports/flight_summary.html', scope)


def flight_summary_export(request: HttpRequest) -> HttpResponse:
    scope = _scope(request)
    tables = summary_schedule(scope['season'], scope['year'], scope['start'], scope['end'])
    title = f"{scope['season'].title()} {scope['year']} Flight Summary"
    subtitle = f"{scope['start']:%d %b %Y} – {scope['end']:%d %b %Y} · ordered by time · times in EAT"
    return _download(
        report_exports.summary_workbook(tables, title, subtitle), XLSX,
        f"{scope['season'].title()}_{scope['year']}_flight_summary.xlsx",
    )


def season_analytics_report(request: HttpRequest) -> HttpResponse:
    scope = _scope(request)
    data = season_analytics(scope['season'], scope['year'], scope['start'], scope['end'])
    charts = {
        'weekdays': [r['name'][:3] for r in data['weekday_rows']],
        'weekday_arr': [r['arr'] for r in data['weekday_rows']],
        'weekday_dep': [r['dep'] for r in data['weekday_rows']],
        'hours': [r['label'] for r in data['hour_rows']],
        'hour_arr': [r['arr_total'] for r in data['hour_rows']],
        'hour_dep': [r['dep_total'] for r in data['hour_rows']],
        'dates': [r['date'].isoformat() for r in data['daily']],
        'date_arr': [r['arr'] for r in data['daily']],
        'date_dep': [r['dep'] for r in data['daily']],
        'aircraft': [r['code'] for r in data['aircraft_rows'][:10]],
        'aircraft_counts': [r['movements'] for r in data['aircraft_rows'][:10]],
        'sizes': [r['label'] for r in data['size_rows']],
        'size_counts': [r['movements'] for r in data['size_rows']],
        'airlines': [r['code'] for r in data['airline_rows'][:12]],
        'airline_counts': [r['movements'] for r in data['airline_rows'][:12]],
        'gate_labels': data['resources']['gates']['chart_labels'],
        'gate_counts': data['resources']['gates']['chart_values'],
        'counter_labels': data['resources']['counters']['chart_labels'],
        'counter_counts': data['resources']['counters']['chart_values'],
    }
    return render(request, 'reports/season_analytics.html', {**scope, **data, 'charts': charts, 'active_page': 'reports'})


def season_analytics_export(request: HttpRequest, fmt: str) -> HttpResponse:
    scope = _scope(request)
    data = season_analytics(scope['season'], scope['year'], scope['start'], scope['end'])
    name = f"{scope['season'].title()}_{scope['year']}_schedule_analytics"
    if fmt == 'xlsx':
        return _download(report_exports.analytics_workbook(data), XLSX, f'{name}.xlsx')
    if fmt == 'pdf':
        return _download(report_exports.analytics_pdf(data), 'application/pdf', f'{name}.pdf')
    raise Http404('Unknown export format')


def _download(content: bytes, content_type: str, filename: str) -> HttpResponse:
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
