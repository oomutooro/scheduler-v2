"""Import the non-Uganda-Airlines Winter 2026 schedule requests that are not yet in the system."""

from datetime import date, datetime, timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from core.models import AircraftType, Airline, Airport, DAY_MASK, FlightRequest

ALL_DAYS = '1234567'
EAT_OFFSET_MINUTES = 180
WEEKDAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')

# (iata, icao, name) for airlines that are not yet in the system.
NEW_AIRLINES = {
    'A8': ('XAU', 'Aerolink Uganda'),
}

# iata -> (icao or None, city, country) for airports that are not yet in the system.
NEW_AIRPORTS = {
    'KSR': (None, 'Kisoro', 'Uganda'),
    'KHX': (None, 'Kihihi', 'Uganda'),
    'KSE': (None, 'Kasese', 'Uganda'),
    'GOM': ('FZNA', 'Goma', 'DR Congo'),
    'BGF': ('FEFF', 'Bangui', 'Central African Republic'),
}

# Each row: airline, arrival flight, departure flight, aircraft, arrival time, departure time,
# origin, destination, effective, discontinue, frequency (Mon..Sun, 1-7), timezone ('UTC' | 'EAT'), notes.
# Arrival/departure may be None for one-way movements.
WINTER_START = date(2026, 10, 25)
WINTER_END = date(2027, 3, 27)

ROWS: list[tuple[Any, ...]] = [
    # Air Arabia (UTC)
    ('G9', 'G9691', 'G9692', 'A320', '10:30', '11:20', 'SHJ', 'SHJ', WINTER_START, WINTER_END, ALL_DAYS, 'UTC', ''),

    # EgyptAir (UTC; MS837/MS838 times are adjusted by 15 minutes)
    ('MS', 'MS835', 'MS835', 'A20N', '03:00', '03:45', 'CAI', 'CAI', WINTER_START, WINTER_END, '1..4.6.', 'UTC', 'Via KGL'),
    ('MS', 'MS837', None, 'A20N', '00:30', None, 'CAI', 'EBB', WINTER_START, WINTER_END, '....5.7', 'UTC', ''),
    ('MS', None, 'MS838', 'A20N', None, '01:30', 'EBB', 'CAI', WINTER_START, WINTER_END, '1....6.', 'UTC', ''),

    # Safarilink (letter gives local times; run Daily 25 Oct 2026 - 31 Mar 2027)
    ('F2', 'F2191', 'F2192', 'DH8C', '06:30', '07:00', 'NBO', 'NBO', WINTER_START, date(2027, 3, 31), ALL_DAYS, 'EAT', 'Printed as XLK191/XLK192'),
    ('F2', 'F2083', 'F2084', 'DH8C', '10:30', '11:15', 'KIS', 'KIS', WINTER_START, date(2027, 3, 31), ALL_DAYS, 'EAT', 'Printed as XLK083/XLK084'),
    ('F2', 'F2087', 'F2088', 'DH8C', '17:00', '18:00', 'NBO', 'NBO', WINTER_START, date(2027, 3, 31), ALL_DAYS, 'EAT', 'Printed as XLK087/XLK088'),
    ('F2', 'F2189', 'F2190', 'DH8C', '21:30', '22:00', 'NBO', 'NBO', WINTER_START, date(2027, 3, 31), ALL_DAYS, 'EAT', 'Printed as XLK189/XLK190'),

    # Turkish Airlines cargo (UTC, Thursday pattern, 29 Oct 2026 - 25 Mar 2027)
    ('TK', 'TK6146', 'TK6146', 'A332', '21:05', '23:05', 'IST', 'NBO', date(2026, 10, 29), date(2027, 3, 25), '...4...', 'UTC', 'Cargo freighter (A330F)'),

    # Emirates freighter (local times; EBB departure is the early hours of the following day)
    ('EK', 'EK9663', 'EK9663', 'B777', '21:45', '01:00', 'ADD', 'AMS', WINTER_START, date(2027, 3, 21), '......7', 'EAT', 'Cargo freighter; departs 01:00 the next day'),

    # Kenya Airways freighters (UTC; freighter aircraft type is not stated, B738F assumed)
    ('KQ', 'KQ2313', 'KQ2313', 'B738F', '05:30', '13:00', 'SHJ', 'NBO', WINTER_START, WINTER_END, '..3..6.', 'UTC', 'Cargo freighter'),
    ('KQ', 'KQ2412', 'KQ2413', 'B738F', '10:30', '12:00', 'NBO', 'NBO', WINTER_START, WINTER_END, '1.3.5..', 'UTC', 'Cargo freighter'),
    ('KQ', 'KQ2414', 'KQ2415', 'B738F', '15:30', '17:00', 'NBO', 'NBO', WINTER_START, WINTER_END, '.2.4..7', 'UTC', 'Cargo freighter'),
    ('KQ', 'KQ2354', 'KQ2354', 'B738F', '08:40', '10:10', 'JUB', 'NBO', WINTER_START, WINTER_END, '.2...6.', 'UTC', 'Cargo freighter'),
    ('KQ', 'KQ2356', 'KQ2356', 'B738F', '10:30', '12:00', 'NBO', 'JUB', WINTER_START, WINTER_END, '1..4...', 'UTC', 'Cargo freighter'),
    ('KQ', 'KQ2436', 'KQ2436', 'B738F', '08:15', '09:45', 'NBO', 'GOM', WINTER_START, WINTER_END, '..3..6.', 'UTC', 'Cargo freighter'),
    ('KQ', 'KQ2572', 'KQ2572', 'B738F', '11:20', '12:50', 'BGF', 'NBO', WINTER_START, WINTER_END, '1..4..7', 'UTC', 'Cargo freighter'),
    ('KQ', 'KQ2712', 'KQ2712', 'B738F', '11:00', '12:20', 'LUN', 'NBO', WINTER_START, WINTER_END, '1.3..6.', 'UTC',
     'Cargo freighter; PDF lists the onward leg as LUN-NBO, read as EBB-NBO'),

    # RwandAir cargo (local times, 738-F)
    ('WB', 'WB9309', 'WB9309', 'B738F', '18:00', '19:00', 'KGL', 'NBO', WINTER_START, WINTER_END, '.....6.', 'EAT', 'Cargo freighter'),
    ('WB', 'WB9464', 'WB9464', 'B738F', '13:30', '14:30', 'KGL', 'NBO', WINTER_START, WINTER_END, ALL_DAYS, 'EAT',
     'Cargo freighter; times from the request letter (attached freighter plan differs)'),
    ('WB', 'WB9434', 'WB9435', 'B738F', '17:00', '18:00', 'KGL', 'KGL', WINTER_START, WINTER_END, ALL_DAYS, 'EAT', 'Cargo freighter'),

    # Ethiopian code-share permit routed ADD-KGL-EBB (local times)
    ('ET', 'ET2338', 'ET2339', 'B38M', '03:35', '04:25', 'KGL', 'ADD', WINTER_START, WINTER_END, ALL_DAYS, 'EAT',
     'Code-share operating permit; inbound ADD-KGL-EBB, outbound EBB-ADD'),
]

# Aerolink (UTC, Cessna Caravan). Each tuple: departure flight, arrival flight, destination,
# EBB departure (UTC), EBB arrival (UTC), valid ranges.
_FULL = [(date(2026, 11, 1), date(2027, 3, 26))]
_MIDWINTER = [(date(2026, 12, 1), date(2027, 2, 28))]
_SHOULDER = [(date(2026, 11, 1), date(2026, 11, 30)), (date(2027, 3, 1), date(2027, 3, 26))]
AEROLINK_FLIGHTS = [
    ('A8111', 'A8112', 'KSR', '04:00', '08:25', _FULL, ''),
    ('A8113', 'A8114', 'KHX', '04:00', '08:25', _FULL, ''),
    ('A8115', 'A8116', 'KSE', '04:00', '08:25', _FULL, ''),
    ('A8117', 'A8118', 'KHX', '07:30', '11:25', _MIDWINTER, 'Daily except November and March; routing also serves Kasese/Kisoro'),
    ('A8119', 'A8120', 'KSE', '07:30', '11:25', _MIDWINTER, 'Daily except November and March; routing also serves Kihihi/Kisoro'),
    ('A8121', 'A8122', 'KHX', '10:00', '14:15', _MIDWINTER, 'Daily except November and March; may route via Bugungu/Pakuba/Chobe'),
    ('A8123', 'A8124', 'KSE', '10:00', '14:15', _MIDWINTER, 'Daily except November and March; may route via Bugungu/Pakuba/Chobe'),
    ('A8131', 'A8132', 'KHX', '10:00', '13:15', _SHOULDER, 'Daily only in November and March'),
    ('A8133', 'A8134', 'KSE', '10:00', '13:15', _SHOULDER, 'Daily only in November and March'),
]
for dep_no, arr_no, station, dep_utc, arr_utc, ranges, notes in AEROLINK_FLIGHTS:
    for start, end in ranges:
        ROWS.append(('A8', None, dep_no, 'C208', None, dep_utc, 'EBB', station, start, end, ALL_DAYS, 'UTC', notes))
        ROWS.append(('A8', arr_no, None, 'C208', arr_utc, None, station, 'EBB', start, end, ALL_DAYS, 'UTC', notes))


def _to_local(time_text: str | None, offset_minutes: int) -> tuple[Any, int]:
    """Return (time, day shift) after applying the offset to an HH:MM string."""
    if time_text is None:
        return None, 0
    base = datetime.strptime(time_text, '%H:%M')
    shifted = base + timedelta(minutes=offset_minutes)
    return shifted.time(), (shifted.date() - base.date()).days


def _frequency_mask(frequency: str, day_shift: int) -> int:
    mask = 0
    for index, char in enumerate(frequency):
        if char != '.':
            mask |= DAY_MASK[WEEKDAYS[(index + day_shift) % 7]]
    return mask


class Command(BaseCommand):
    help = 'Import missing Winter 2026 flight requests for airlines other than Uganda Airlines'

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument('--dry-run', action='store_true', help='Validate without writing records')

    def handle(self, *args: Any, **options: Any) -> None:
        aircraft = {a.code: a for a in AircraftType.objects.all()}
        missing_aircraft = sorted({row[3] for row in ROWS} - set(aircraft))
        if missing_aircraft:
            raise CommandError(f'Missing aircraft types: {", ".join(missing_aircraft)}')

        airline_codes = {row[0] for row in ROWS}
        existing_airlines = {a.iata_code: a for a in Airline.objects.filter(iata_code__in=airline_codes)}
        unknown_airlines = airline_codes - set(existing_airlines) - set(NEW_AIRLINES)
        if unknown_airlines:
            raise CommandError(f'Unknown airlines: {", ".join(sorted(unknown_airlines))}')

        airport_codes = {code for row in ROWS for code in (row[6], row[7])}
        existing_airports = {a.iata_code: a for a in Airport.objects.filter(iata_code__in=airport_codes)}
        unknown_airports = airport_codes - set(existing_airports) - set(NEW_AIRPORTS)
        if unknown_airports:
            raise CommandError(f'Unknown airports: {", ".join(sorted(unknown_airports))}')

        if options['dry_run']:
            self.stdout.write(f'Validated {len(ROWS)} flight requests.')
            return

        created = skipped = 0
        with transaction.atomic():
            for iata, (icao, name) in NEW_AIRLINES.items():
                if iata in airline_codes and iata not in existing_airlines:
                    existing_airlines[iata] = Airline.objects.create(iata_code=iata, icao_code=icao, name=name)
            for iata, (icao, city, country) in NEW_AIRPORTS.items():
                if iata in airport_codes and iata not in existing_airports:
                    existing_airports[iata] = Airport.objects.create(
                        iata_code=iata, icao_code=icao, city_name=city, country=country,
                    )

            for (airline_code, arr_no, dep_no, aircraft_code, arr_text, dep_text, origin, destination,
                 valid_from, valid_to, frequency, zone, notes) in ROWS:
                offset = EAT_OFFSET_MINUTES if zone == 'UTC' else 0
                arrival, arrival_shift = _to_local(arr_text, offset)
                departure, departure_shift = _to_local(dep_text, offset)
                day_shift = arrival_shift if arrival is not None else departure_shift
                if day_shift:
                    valid_from += timedelta(days=day_shift)
                    valid_to += timedelta(days=day_shift)

                if arr_no and dep_no:
                    operation = 'turnaround'
                else:
                    operation = 'arrival' if arr_no else 'departure'

                lookup = {
                    'airline': existing_airlines[airline_code],
                    'arrival_flight_number': arr_no or '',
                    'departure_flight_number': dep_no or '',
                    'aircraft_type': aircraft[aircraft_code],
                    'operation_type': operation,
                    'season': 'winter',
                    'year': 2026,
                    'arrival_time': arrival,
                    'departure_time': departure,
                    'origin': existing_airports[origin],
                    'destination': existing_airports[destination],
                    'valid_from': valid_from,
                    'valid_to': valid_to,
                    'days_of_operation': _frequency_mask(frequency, day_shift),
                    'ground_days': 1 if operation == 'turnaround' and departure < arrival else 0,
                }
                note = 'Winter 2026 schedule request.' + (f' {notes}.' if notes else '')
                if zone == 'UTC':
                    note += ' Converted from UTC to local time (UTC+3).'

                same_number = Q()
                if arr_no:
                    same_number |= Q(arrival_flight_number=arr_no)
                if dep_no:
                    same_number |= Q(departure_flight_number=dep_no)
                already_present = any(
                    existing.days_of_operation & lookup['days_of_operation']
                    and existing.start_date <= valid_to and existing.end_date >= valid_from
                    for existing in FlightRequest.objects.filter(
                        airline=lookup['airline'], season='winter', year=2026,
                    ).filter(same_number)
                )
                if already_present:
                    skipped += 1
                    continue
                FlightRequest.objects.create(**lookup, notes=note)
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Winter 2026 import complete: {created} created, {skipped} already present.'
        ))
