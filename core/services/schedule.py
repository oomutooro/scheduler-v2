"""
Schedule service for Entebbe Airport Slotting System.
Provides helpers for generating daily flight lists from seasonal flight requests.
"""

from datetime import date
from typing import List
from core.models import FlightRequest
from core.services.season import get_season_for_date


def get_flights_for_date(selected_date: date) -> List[FlightRequest]:
    """
    Return all FlightRequest objects that operate on the given date.

    Filters by:
     - The season/year the date falls in
     - The days-of-operation bitmask (checks selected_date's weekday)
     - The optional valid_from/valid_to partial-season range
    """
    season, year = get_season_for_date(selected_date)

    candidates = FlightRequest.objects.filter(
        season=season, year=year
    ).select_related('airline', 'aircraft_type', 'origin', 'destination')

    return [f for f in candidates if f.operates_on_date(selected_date)]


def get_flights_for_date_sorted(selected_date: date) -> List[FlightRequest]:
    """
    Return flights for a date sorted by their earliest time (arrival or departure).
    """
    from datetime import time as time_type

    flights = get_flights_for_date(selected_date)

    def sort_key(f: FlightRequest):
        t = f.arrival_time or f.departure_time
        return t if t is not None else time_type(23, 59, 59)

    return sorted(flights, key=sort_key)
