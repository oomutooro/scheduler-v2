"""
Shared utilities for the Entebbe slotting system.
"""
from datetime import time as dtime, timedelta

# EAT = East Africa Time = UTC + 3 (no DST).
EAT_OFFSET_HOURS = 3

# Days-of-week in the order used by the DAY_MASK bitmask (Sunday = bit 0).
DAY_ORDER = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
DAY_ORDER_TITLE = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

_MINUTES_IN_DAY = 24 * 60


def _to_minutes(t: dtime) -> int:
    return t.hour * 60 + t.minute


def _to_time(mins: int) -> dtime:
    mins %= _MINUTES_IN_DAY
    return dtime(mins // 60, mins % 60)


def utc_to_eat(utc: dtime | str) -> dtime:
    """
    Convert a UTC time to EAT (UTC + 3).

    Cross-midnight results are wrapped into the 00:00-23:59 range (the wrapping
    of the operating day is handled by the allocation logic / ground days).
    Accepts a ``datetime.time`` or an ``HH:MM`` string.
    """
    if isinstance(utc, str):
        h, m = (int(x) for x in utc.split(':'))
        utc = dtime(h % 24, m % 60)
    return _to_time(_to_minutes(utc) + EAT_OFFSET_HOURS * 60)


def eat_to_utc(eat: dtime | str) -> dtime:
    """Convert an EAT time back to UTC."""
    if isinstance(eat, str):
        h, m = (int(x) for x in eat.split(':'))
        eat = dtime(h % 24, m % 60)
    return _to_time(_to_minutes(eat) - EAT_OFFSET_HOURS * 60)


def expected_operation_type(airline) -> str:
    """
    Business rule for this airport:
      - Foreign (non-home) airlines file **turnaround** requests
        (an aircraft that arrives then departs from EBB).
      - Home airlines (Uganda's own domestic carriers) file **separate**
        arrival or departure requests, never turnarounds.
    """
    return 'arrival' if getattr(airline, 'is_home_airline', False) else 'turnaround'


def is_valid_operation(airline, operation_type: str) -> tuple[bool, str]:
    """
    Validate an operation type against the home / foreign turnaround rule.
    Returns (ok, message).
    """
    home = getattr(airline, 'is_home_airline', False)
    if home and operation_type == 'turnaround':
        return False, 'Home airlines file separate arrival/departure requests, not turnarounds.'
    if not home and operation_type in ('arrival', 'departure'):
        return False, 'Foreign airlines must file turnaround requests (arrival + departure).'
    return True, ''
