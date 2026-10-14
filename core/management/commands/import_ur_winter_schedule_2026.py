"""Import Uganda Airlines' 2026 winter schedule for EBB movements."""

from datetime import datetime, timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Airport, Airline, AircraftType, DAY_MASK, FlightRequest


# Flight number, effective date, discontinue date, frequency (Mon-Sun),
# departure airport/time, arrival airport/time, aircraft configuration.
SCHEDULE_ROWS = [
    ('UR110', '25-Oct-26', '28-Mar-27', '.2.....', 'EBB', '10:30', 'LGW', '16:10', 'A338'),
    ('UR111', '25-Oct-26', '28-Mar-27', '.2.....', 'LGW', '19:10', 'EBB', '06:50', 'A338'),
    ('UR110', '25-Oct-26', '28-Mar-27', '....5..', 'EBB', '11:35', 'LGW', '17:15', 'A338'),
    ('UR111', '25-Oct-26', '28-Mar-27', '....5..', 'LGW', '19:10', 'EBB', '06:50', 'A338'),
    ('UR110', '25-Oct-26', '28-Mar-27', '......7', 'EBB', '10:00', 'LGW', '15:40', 'A338'),
    ('UR111', '25-Oct-26', '28-Mar-27', '......7', 'LGW', '18:40', 'EBB', '06:20', 'A338'),
    ('UR122', '25-Oct-26', '30-Oct-26', '1......', 'EBB', '09:00', 'JUB', '09:25', 'CRJ9'),
    ('UR123', '25-Oct-26', '30-Oct-26', '1......', 'JUB', '10:10', 'EBB', '12:35', 'CRJ9'),
    ('UR120', '25-Oct-26', '30-Oct-26', '.2.4567', 'EBB', '12:30', 'JUB', '12:55', 'CRJ9'),
    ('UR121', '25-Oct-26', '30-Oct-26', '.2.4567', 'JUB', '13:40', 'EBB', '16:05', 'CRJ9'),
    ('UR122', '25-Oct-26', '30-Oct-26', '..3....', 'EBB', '07:00', 'JUB', '07:25', 'CRJ9'),
    ('UR123', '25-Oct-26', '30-Oct-26', '..3....', 'JUB', '08:10', 'EBB', '10:35', 'CRJ9'),
    ('UR122', '01-Nov-26', '28-Mar-27', '1......', 'EBB', '07:00', 'JUB', '07:25', 'CRJ9'),
    ('UR123', '01-Nov-26', '28-Mar-27', '1......', 'JUB', '08:10', 'EBB', '10:35', 'CRJ9'),
    ('UR122', '01-Nov-26', '28-Mar-27', '.234567', 'EBB', '14:20', 'JUB', '14:45', 'CRJ9'),
    ('UR123', '01-Nov-26', '28-Mar-27', '.234567', 'JUB', '15:30', 'EBB', '17:55', 'CRJ9'),
    ('UR200', '25-Oct-26', '28-Mar-27', '1234567', 'EBB', '08:00', 'NBO', '09:15', 'CRJ9'),
    ('UR201', '25-Oct-26', '28-Mar-27', '1234567', 'NBO', '10:00', 'EBB', '11:15', 'CRJ9'),
    ('UR202', '01-Nov-26', '28-Mar-27', '12.4..7', 'EBB', '12:00', 'NBO', '13:15', 'CRJ9'),
    ('UR203', '01-Nov-26', '28-Mar-27', '12.4..7', 'NBO', '14:00', 'EBB', '15:15', 'CRJ9'),
    ('UR204', '25-Oct-26', '28-Mar-27', '1234567', 'EBB', '21:30', 'NBO', '22:45', 'CRJ9'),
    ('UR205', '25-Oct-26', '28-Mar-27', '1234567', 'NBO', '23:30', 'EBB', '00:45', 'CRJ9'),
    ('UR206', '25-Oct-26', '30-Oct-26', '.2...67', 'EBB', '17:10', 'NBO', '18:25', 'CRJ9'),
    ('UR207', '25-Oct-26', '30-Oct-26', '.2...67', 'NBO', '19:10', 'EBB', '20:25', 'CRJ9'),
    ('UR320', '25-Oct-26', '28-Mar-27', '1....6.', 'EBB', '12:00', 'DAR', '13:50', 'CRJ9'),
    ('UR321', '25-Oct-26', '28-Mar-27', '1....6.', 'DAR', '14:35', 'EBB', '16:25', 'CRJ9'),
    ('UR322', '25-Oct-26', '30-Oct-26', '1.3456.', 'EBB', '22:10', 'DAR', '00:00', 'CRJ9'),
    ('UR323', '25-Oct-26', '30-Oct-26', '.2.4567', 'DAR', '00:45', 'EBB', '02:35', 'CRJ9'),
    ('UR322', '25-Oct-26', '30-Oct-26', '......7', 'EBB', '23:30', 'DAR', '01:20', 'CRJ9'),
    ('UR323', '25-Oct-26', '30-Oct-26', '1......', 'DAR', '02:05', 'EBB', '03:55', 'CRJ9'),
    ('UR322', '01-Nov-26', '28-Mar-27', '12345.7', 'EBB', '19:40', 'DAR', '21:30', 'CRJ9'),
    ('UR323', '01-Nov-26', '28-Mar-27', '12345.7', 'DAR', '22:15', 'EBB', '00:05', 'CRJ9'),
    ('UR334', '25-Oct-26', '28-Mar-27', '..3.5.7', 'EBB', '12:00', 'ZNZ', '13:50', 'CRJ9'),
    ('UR334', '25-Oct-26', '28-Mar-27', '..3.5.7', 'JRO', '16:20', 'EBB', '17:35', 'CRJ9'),
    ('UR342', '25-Oct-26', '30-Oct-26', '..3...7', 'EBB', '18:20', 'MBA', '20:10', 'CRJ9'),
    ('UR343', '25-Oct-26', '30-Oct-26', '..3...7', 'MBA', '20:55', 'EBB', '22:45', 'CRJ9'),
    ('UR342', '25-Oct-26', '30-Oct-26', '....5..', 'EBB', '07:00', 'MBA', '08:50', 'CRJ9'),
    ('UR343', '25-Oct-26', '30-Oct-26', '....5..', 'MBA', '09:35', 'EBB', '11:25', 'CRJ9'),
    ('UR342', '01-Nov-26', '28-Mar-27', '..3.5.7', 'EBB', '09:00', 'MBA', '10:50', 'CRJ9'),
    ('UR343', '01-Nov-26', '28-Mar-27', '..3.5.7', 'MBA', '11:35', 'EBB', '13:25', 'CRJ9'),
    ('UR360', '25-Oct-26', '28-Mar-27', '12.45.7', 'EBB', '17:10', 'BJM', '17:25', 'CRJ9'),
    ('UR361', '25-Oct-26', '28-Mar-27', '12.45.7', 'BJM', '18:10', 'EBB', '20:25', 'CRJ9'),
    ('UR360', '25-Oct-26', '30-Oct-26', '..3....', 'EBB', '17:10', 'BJM', '17:25', 'CRJ9'),
    ('UR361', '25-Oct-26', '30-Oct-26', '..3....', 'BJM', '18:10', 'EBB', '20:25', 'CRJ9'),
    ('UR360', '01-Nov-26', '28-Mar-27', '.....6.', 'EBB', '17:10', 'BJM', '17:25', 'CRJ9'),
    ('UR361', '01-Nov-26', '28-Mar-27', '.....6.', 'BJM', '18:10', 'EBB', '20:25', 'CRJ9'),
    ('UR380', '18-Nov-26', '28-Mar-27', '.2..5.7', 'EBB', '04:00', 'KGL', '04:00', 'CRJ9'),
    ('UR381', '18-Nov-26', '28-Mar-27', '.2..5.7', 'KGL', '04:45', 'EBB', '06:45', 'CRJ9'),
    ('UR382', '18-Nov-26', '28-Mar-27', '1.34.6.', 'EBB', '08:15', 'KGL', '08:15', 'CRJ9'),
    ('UR383', '18-Nov-26', '28-Mar-27', '1.34.6.', 'KGL', '09:00', 'EBB', '11:00', 'CRJ9'),
    ('UR430', '25-Oct-26', '28-Mar-27', '..3....', 'EBB', '21:15', 'BOM', '06:45', 'A338'),
    ('UR431', '25-Oct-26', '28-Mar-27', '...4...', 'BOM', '07:45', 'EBB', '11:00', 'A338'),
    ('UR430', '25-Oct-26', '30-Oct-26', '.....6.', 'EBB', '13:00', 'BOM', '23:00', 'A338'),
    ('UR431', '25-Oct-26', '30-Oct-26', '......7', 'BOM', '01:01', 'EBB', '05:10', 'A338'),
    ('UR444', '01-Nov-26', '28-Mar-27', '..3.5.7', 'EBB', '22:00', 'DXB', '04:30', 'A338'),
    ('UR445', '01-Nov-26', '28-Mar-27', '1.4.6..', 'DXB', '06:30', 'EBB', '11:00', 'A338'),
    ('UR520', '25-Oct-26', '28-Mar-27', '.2.4.67', 'EBB', '05:15', 'MGQ', '07:45', 'CRJ9'),
    ('UR521', '25-Oct-26', '28-Mar-27', '.2.4.67', 'MGQ', '08:30', 'EBB', '11:00', 'CRJ9'),
    ('UR710', '25-Oct-26', '28-Mar-27', '1.3.56.', 'EBB', '09:30', 'JNB', '12:45', 'B738'),
    ('UR711', '25-Oct-26', '28-Mar-27', '1.3.56.', 'JNB', '13:45', 'EBB', '19:00', 'B738'),
    ('UR712', '25-Oct-26', '28-Mar-27', '12.4..7', 'EBB', '22:45', 'JNB', '02:00', 'B738'),
    ('UR713', '25-Oct-26', '28-Mar-27', '12.4..7', 'JNB', '03:00', 'EBB', '08:15', 'B738'),
    ('UR720', '25-Oct-26', '28-Mar-27', '....5.7', 'EBB', '21:10', 'LUN', '22:55', 'CRJ9'),
    ('UR720', '25-Oct-26', '28-Mar-27', '1....6.', 'HRE', '01:25', 'EBB', '05:25', 'CRJ9'),
    ('UR722', '25-Oct-26', '28-Mar-27', '.234...', 'EBB', '12:00', 'HRE', '14:00', 'CRJ9'),
    ('UR722', '25-Oct-26', '28-Mar-27', '.234...', 'LUN', '16:30', 'EBB', '20:15', 'CRJ9'),
    ('UR724', '25-Oct-26', '28-Mar-27', '1....6.', 'EBB', '12:00', 'HRE', '14:00', 'CRJ9'),
    ('UR725', '25-Oct-26', '28-Mar-27', '.2....7', 'HRE', '02:45', 'EBB', '06:45', 'CRJ9'),
    ('UR880', '01-Nov-26', '28-Mar-27', '.23.567', 'EBB', '09:00', 'FIH', '10:00', 'B738'),
    ('UR881', '01-Nov-26', '28-Mar-27', '.23.567', 'FIH', '10:45', 'EBB', '15:45', 'B738'),
    ('UR882', '01-Nov-26', '28-Mar-27', '1..4...', 'EBB', '12:00', 'FIH', '13:00', 'B738'),
    ('UR883', '01-Nov-26', '28-Mar-27', '1..4...', 'FIH', '13:45', 'EBB', '18:45', 'B738'),
    ('UR900', '25-Oct-26', '28-Mar-27', '.2.45.7', 'EBB', '12:00', 'LOS', '14:30', 'B738'),
    ('UR901', '25-Oct-26', '28-Mar-27', '.2.45.7', 'LOS', '22:25', 'EBB', '04:55', 'B738'),
]

NEW_AIRPORTS = {
    'HRE': {'icao_code': 'FVHA', 'city_name': 'Harare', 'country': 'Zimbabwe'},
    'LUN': {'icao_code': 'FLLS', 'city_name': 'Lusaka', 'country': 'Zambia'},
    'MGQ': {'icao_code': 'HCMM', 'city_name': 'Mogadishu', 'country': 'Somalia'},
}

AIRCRAFT_CONFIGS = {
    'A338': 'J20W28Y210',
    'B738': 'J16Y138',
    'CRJ9': 'J12Y64',
}


class Command(BaseCommand):
    help = 'Import Uganda Airlines Winter 2026 EBB arrivals and departures'

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument('--dry-run', action='store_true', help='Validate without writing records')

    def handle(self, *args: Any, **options: Any) -> None:
        airline = Airline.objects.filter(iata_code='UR').first()
        if airline is None:
            raise CommandError('Uganda Airlines (UR) is missing from the database.')

        missing_aircraft = sorted({row[8] for row in SCHEDULE_ROWS} - set(
            AircraftType.objects.filter(code__in=AIRCRAFT_CONFIGS).values_list('code', flat=True)
        ))
        if missing_aircraft:
            raise CommandError(f'Missing aircraft types: {", ".join(missing_aircraft)}')

        for flight_number, effective, discontinue, frequency, departure_code, departure, arrival_code, arrival, aircraft_code in SCHEDULE_ROWS:
            if len(frequency) != 7 or any(day not in '.1234567' for day in frequency):
                raise CommandError(f'Invalid frequency for {flight_number}: {frequency}')
            if (departure_code == 'EBB') == (arrival_code == 'EBB'):
                raise CommandError(f'{flight_number} is not a single EBB arrival or departure.')
            if aircraft_code not in AIRCRAFT_CONFIGS:
                raise CommandError(f'Unknown aircraft configuration for {flight_number}: {aircraft_code}')

        airport_codes = {
            code for row in SCHEDULE_ROWS for code in (row[4], row[6])
        }
        unknown_airports = sorted(
            airport_codes - set(Airport.objects.filter(iata_code__in=airport_codes).values_list('iata_code', flat=True))
            - set(NEW_AIRPORTS)
        )
        if unknown_airports:
            raise CommandError(f'Missing airport records: {", ".join(unknown_airports)}')

        if options['dry_run']:
            arrivals = sum(row[6] == 'EBB' for row in SCHEDULE_ROWS)
            departures = sum(row[4] == 'EBB' for row in SCHEDULE_ROWS)
            overnight_arrivals = sum(
                row[6] == 'EBB' and row[7] < row[5] for row in SCHEDULE_ROWS
            )
            self.stdout.write(
                f'Validated {len(SCHEDULE_ROWS)} rows: {departures} departures, '
                f'{arrivals} arrivals ({overnight_arrivals} cross midnight).'
            )
            return

        created_count = 0
        existing_count = 0
        with transaction.atomic():
            airports = {}
            for code in airport_codes:
                details = NEW_AIRPORTS.get(code)
                if details:
                    airport, _ = Airport.objects.get_or_create(iata_code=code, defaults=details)
                else:
                    airport = Airport.objects.get(iata_code=code)
                airports[code] = airport

            aircraft_types = {
                aircraft.code: aircraft
                for aircraft in AircraftType.objects.filter(code__in=AIRCRAFT_CONFIGS)
            }

            for row in SCHEDULE_ROWS:
                (
                    flight_number, effective, discontinue, frequency,
                    departure_code, departure_text, arrival_code, arrival_text,
                    aircraft_code,
                ) = row
                departure_time = datetime.strptime(departure_text, '%H:%M').time()
                arrival_time = datetime.strptime(arrival_text, '%H:%M').time()
                is_arrival = arrival_code == 'EBB'
                crosses_midnight = is_arrival and arrival_time < departure_time

                days_of_operation = 0
                for index, day in enumerate(frequency):
                    if day != '.':
                        day_name = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')[index]
                        days_of_operation |= DAY_MASK[day_name]
                if crosses_midnight:
                    days_of_operation = ((days_of_operation << 1) & 127) | (days_of_operation >> 6)

                valid_from = datetime.strptime(effective, '%d-%b-%y').date()
                valid_to = datetime.strptime(discontinue, '%d-%b-%y').date()
                if crosses_midnight:
                    valid_from += timedelta(days=1)
                    valid_to += timedelta(days=1)

                flight_fields = {
                    'airline': airline,
                    'arrival_flight_number': flight_number if is_arrival else '',
                    'departure_flight_number': '' if is_arrival else flight_number,
                    'aircraft_type': aircraft_types[aircraft_code],
                    'operation_type': 'arrival' if is_arrival else 'departure',
                    'season': 'winter',
                    'year': 2026,
                    'arrival_time': arrival_time if is_arrival else None,
                    'departure_time': None if is_arrival else departure_time,
                    'origin': airports[departure_code],
                    'destination': airports[arrival_code],
                    'valid_from': valid_from,
                    'valid_to': valid_to,
                    'days_of_operation': days_of_operation,
                    'ground_days': 0,
                    'notes': 'Uganda Airlines Winter 2026 schedule; times as printed in Uganda time.',
                }
                _, created = FlightRequest.objects.get_or_create(**flight_fields)
                created_count += int(created)
                existing_count += int(not created)

        self.stdout.write(self.style.SUCCESS(
            f'Uganda Airlines Winter 2026 import complete: '
            f'{created_count} created, {existing_count} already present.'
        ))