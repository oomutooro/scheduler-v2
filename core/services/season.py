"""
Season calculation utilities for Entebbe Airport.

Uganda seasons:
- Summer: Last Sunday of March → Last Saturday of October (same year)
- Winter: Last Sunday of October (last Sat + 1) → Last Sunday of March (next year)
"""

from datetime import date, timedelta


def last_sunday_of_march(year: int) -> date:
    """Last Sunday of March in the given year."""
    d = date(year, 3, 31)
    while d.weekday() != 6:  # Sunday = 6
        d -= timedelta(days=1)
    return d


def last_saturday_of_october(year: int) -> date:
    """Last Saturday of October in the given year."""
    d = date(year, 10, 31)
    while d.weekday() != 5:  # Saturday = 5
        d -= timedelta(days=1)
    return d


def get_summer_dates(year: int) -> tuple[date, date]:
    """Return (start, end) for the Summer season of the given year."""
    start = last_sunday_of_march(year)
    end = last_saturday_of_october(year)
    return start, end


def get_winter_dates(year: int) -> tuple[date, date]:
    """Return (start, end) for the Winter season starting in Oct of year, ending March of year+1."""
    start = last_saturday_of_october(year) + timedelta(days=1)  # Sunday after last Sat of Oct
    end = last_sunday_of_march(year + 1) - timedelta(days=1)    # Saturday before last Sun of March
    return start, end


def get_season_for_date(check_date: date) -> tuple[str, int]:
    """Return ('summer'|'winter', year) for the given date."""
    year = check_date.year
    summer_start, summer_end = get_summer_dates(year)
    if summer_start <= check_date <= summer_end:
        return 'summer', year
    # Check if in winter (this year or next year's winter)
    return 'winter', year


def get_current_season() -> tuple[str, int, date, date]:
    """Return (season_name, year, start_date, end_date) for today."""
    today = date.today()
    season, year = get_season_for_date(today)
    if season == 'summer':
        start, end = get_summer_dates(year)
    else:
        start, end = get_winter_dates(year)
    return season, year, start, end


def get_season_dates(season: str, year: int) -> tuple[date, date]:
    """Return (start, end) for the specified season and year."""
    if season == 'summer':
        return get_summer_dates(year)
    else:
        return get_winter_dates(year)


def is_date_in_season(check_date: date, season: str, year: int) -> bool:
    """Check if a date falls within the given season/year."""
    start, end = get_season_dates(season, year)
    return start <= check_date <= end
