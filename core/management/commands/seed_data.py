"""
Seed data management command.
Run with: python manage.py seed_data
"""

from django.core.management.base import BaseCommand
from typing import Any
from core.models import Airline, Airport, AircraftType, ParkingStand, Gate, CheckInCounter


AIRLINES = [
    {'iata_code': 'UR', 'icao_code': 'UGD', 'name': 'Uganda Airlines', 'is_home_airline': True},
    {'iata_code': 'EK', 'icao_code': 'UAE', 'name': 'Emirates', 'is_home_airline': False},
    {'iata_code': 'TK', 'icao_code': 'THY', 'name': 'Turkish Airlines', 'is_home_airline': False},
    {'iata_code': 'KQ', 'icao_code': 'KQA', 'name': 'Kenya Airways', 'is_home_airline': False},
    {'iata_code': 'QR', 'icao_code': 'QTR', 'name': 'Qatar Airways', 'is_home_airline': False},
    {'iata_code': '7F', 'icao_code': 'FJE', 'name': 'First Jet', 'is_home_airline': False},
    {'iata_code': 'WB', 'icao_code': 'RWD', 'name': 'RwandAir', 'is_home_airline': False},
    {'iata_code': 'ET', 'icao_code': 'ETH', 'name': 'Ethiopian Airlines', 'is_home_airline': False},
    {'iata_code': 'F2', 'icao_code': 'XLK', 'name': 'Safarilink', 'is_home_airline': False},
    {'iata_code': 'G9', 'icao_code': 'ABY', 'name': 'Air Arabia Abu Dhabi', 'is_home_airline': False},
    {'iata_code': 'TC', 'icao_code': 'ATC', 'name': 'Air Tanzania', 'is_home_airline': False},
    {'iata_code': 'FZ', 'icao_code': 'FDB', 'name': 'flydubai', 'is_home_airline': False},
    {'iata_code': 'MS', 'icao_code': 'MSR', 'name': 'EgyptAir', 'is_home_airline': False},
    {'iata_code': 'XY', 'icao_code': 'KNE', 'name': 'flynas', 'is_home_airline': False},
    {'iata_code': 'SN', 'icao_code': 'BEL', 'name': 'Brussels Airlines', 'is_home_airline': False},
    {'iata_code': 'KL', 'icao_code': 'KLM', 'name': 'KLM Royal Dutch Airlines', 'is_home_airline': False},
    {'iata_code': '3T', 'icao_code': 'TQQ', 'name': 'Tarco Air', 'is_home_airline': False},
]

AIRPORTS = [
    {'iata_code': 'EBB', 'icao_code': 'HUEN', 'city_name': 'Entebbe', 'country': 'Uganda'},
    {'iata_code': 'DXB', 'icao_code': 'OMDB', 'city_name': 'Dubai', 'country': 'UAE'},
    {'iata_code': 'FIH', 'icao_code': 'FZAA', 'city_name': 'Kinshasa', 'country': 'DR Congo'},
    {'iata_code': 'JNB', 'icao_code': 'FAOR', 'city_name': 'Johannesburg', 'country': 'South Africa'},
    {'iata_code': 'NBO', 'icao_code': 'HKJK', 'city_name': 'Nairobi', 'country': 'Kenya'},
    {'iata_code': 'ZNZ', 'icao_code': 'HTZA', 'city_name': 'Zanzibar', 'country': 'Tanzania'},
    {'iata_code': 'DAR', 'icao_code': 'HTDA', 'city_name': 'Dar es Salaam', 'country': 'Tanzania'},
    {'iata_code': 'JRO', 'icao_code': 'HTKJ', 'city_name': 'Kilimanjaro', 'country': 'Tanzania'},
    {'iata_code': 'KGL', 'icao_code': 'HRYR', 'city_name': 'Kigali', 'country': 'Rwanda'},
    {'iata_code': 'LGW', 'icao_code': 'EGKK', 'city_name': 'London Gatwick', 'country': 'UK'},
    {'iata_code': 'LHR', 'icao_code': 'EGLL', 'city_name': 'London Heathrow', 'country': 'UK'},
    {'iata_code': 'ABV', 'icao_code': 'DNAA', 'city_name': 'Abuja', 'country': 'Nigeria'},
    {'iata_code': 'BOM', 'icao_code': 'VABB', 'city_name': 'Mumbai', 'country': 'India'},
    {'iata_code': 'JUB', 'icao_code': 'HSSJ', 'city_name': 'Juba', 'country': 'South Sudan'},
    {'iata_code': 'BJM', 'icao_code': 'HBBI', 'city_name': 'Bujumbura', 'country': 'Burundi'},
    {'iata_code': 'MBA', 'icao_code': 'HKMO', 'city_name': 'Mombasa', 'country': 'Kenya'},
    {'iata_code': 'BRU', 'icao_code': 'EBBR', 'city_name': 'Brussels', 'country': 'Belgium'},
    {'iata_code': 'CAI', 'icao_code': 'HECA', 'city_name': 'Cairo', 'country': 'Egypt'},
    {'iata_code': 'IST', 'icao_code': 'LTFM', 'city_name': 'Istanbul', 'country': 'Turkey'},
    {'iata_code': 'ADD', 'icao_code': 'HAAB', 'city_name': 'Addis Ababa', 'country': 'Ethiopia'},
    {'iata_code': 'AMS', 'icao_code': 'EHAM', 'city_name': 'Amsterdam', 'country': 'Netherlands'},
    {'iata_code': 'SHJ', 'icao_code': 'OMSJ', 'city_name': 'Sharjah', 'country': 'UAE'},
    {'iata_code': 'RUH', 'icao_code': 'OERK', 'city_name': 'Riyadh', 'country': 'Saudi Arabia'},
    {'iata_code': 'LLW', 'icao_code': 'FWKI', 'city_name': 'Lilongwe', 'country': 'Malawi'},
    {'iata_code': 'DOH', 'icao_code': 'OTHH', 'city_name': 'Doha', 'country': 'Qatar'},
    {'iata_code': 'CDG', 'icao_code': 'LFPG', 'city_name': 'Paris', 'country': 'France'},
    {'iata_code': 'FRA', 'icao_code': 'EDDF', 'city_name': 'Frankfurt', 'country': 'Germany'},
    {'iata_code': 'ACC', 'icao_code': 'DGAA', 'city_name': 'Accra', 'country': 'Ghana'},
    {'iata_code': 'LOS', 'icao_code': 'DNMM', 'city_name': 'Lagos', 'country': 'Nigeria'},
    {'iata_code': 'CPT', 'icao_code': 'FACT', 'city_name': 'Cape Town', 'country': 'South Africa'},
]

AIRCRAFT_TYPES = [
    {'code': 'B777', 'name': 'Boeing 777', 'manufacturer': 'Boeing', 'category': 'wide_body', 'size_code': 'E', 'is_wide_body': True, 'pax_capacity': 396},
    {'code': 'B789', 'name': 'Boeing 787-9 Dreamliner', 'manufacturer': 'Boeing', 'category': 'wide_body', 'size_code': 'E', 'is_wide_body': True, 'pax_capacity': 296},
    {'code': 'B788', 'name': 'Boeing 787-8 Dreamliner', 'manufacturer': 'Boeing', 'category': 'wide_body', 'size_code': 'E', 'is_wide_body': True, 'pax_capacity': 248},
    {'code': 'A333', 'name': 'Airbus A330-300', 'manufacturer': 'Airbus', 'category': 'wide_body', 'size_code': 'E', 'is_wide_body': True, 'pax_capacity': 335},
    {'code': 'A338', 'name': 'Airbus A330-800neo', 'manufacturer': 'Airbus', 'category': 'wide_body', 'size_code': 'E', 'is_wide_body': True, 'pax_capacity': 257},
    {'code': 'A339', 'name': 'Airbus A330-900neo', 'manufacturer': 'Airbus', 'category': 'wide_body', 'size_code': 'E', 'is_wide_body': True, 'pax_capacity': 287},
    {'code': 'B772', 'name': 'Boeing 777-200', 'manufacturer': 'Boeing', 'category': 'wide_body', 'size_code': 'E', 'is_wide_body': True, 'pax_capacity': 364},
    {'code': 'B77W', 'name': 'Boeing 777-300ER', 'manufacturer': 'Boeing', 'category': 'wide_body', 'size_code': 'E', 'is_wide_body': True, 'pax_capacity': 396},
    {'code': 'B738', 'name': 'Boeing 737-800', 'manufacturer': 'Boeing', 'category': 'narrow_body', 'size_code': 'C', 'is_wide_body': False, 'pax_capacity': 162},
    {'code': 'B739', 'name': 'Boeing 737-900', 'manufacturer': 'Boeing', 'category': 'narrow_body', 'size_code': 'C', 'is_wide_body': False, 'pax_capacity': 177},
    {'code': 'A21N', 'name': 'Airbus A321neo', 'manufacturer': 'Airbus', 'category': 'narrow_body', 'size_code': 'C', 'is_wide_body': False, 'pax_capacity': 180},
    {'code': 'A320', 'name': 'Airbus A320', 'manufacturer': 'Airbus', 'category': 'narrow_body', 'size_code': 'C', 'is_wide_body': False, 'pax_capacity': 150},
    {'code': 'A20N', 'name': 'Airbus A320neo', 'manufacturer': 'Airbus', 'category': 'narrow_body', 'size_code': 'C', 'is_wide_body': False, 'pax_capacity': 150},
    {'code': 'B38M', 'name': 'Boeing 737 MAX 8', 'manufacturer': 'Boeing', 'category': 'narrow_body', 'size_code': 'C', 'is_wide_body': False, 'pax_capacity': 162},
    {'code': 'CRJ9', 'name': 'Bombardier CRJ-900', 'manufacturer': 'Bombardier', 'category': 'regional', 'size_code': 'C', 'is_wide_body': False, 'pax_capacity': 86},
    {'code': 'E190', 'name': 'Embraer E190', 'manufacturer': 'Embraer', 'category': 'regional', 'size_code': 'C', 'is_wide_body': False, 'pax_capacity': 97},
    {'code': 'DH8C', 'name': 'Dash 8-300', 'manufacturer': 'De Havilland', 'category': 'turboprop', 'size_code': 'B', 'is_wide_body': False, 'pax_capacity': 50},
    {'code': 'DH8D', 'name': 'Dash 8-400', 'manufacturer': 'De Havilland', 'category': 'turboprop', 'size_code': 'C', 'is_wide_body': False, 'pax_capacity': 78},
    {'code': 'C208', 'name': 'Cessna 208 Caravan', 'manufacturer': 'Cessna', 'category': 'turboprop', 'size_code': 'A', 'is_wide_body': False, 'pax_capacity': 9},
    {'code': 'AT76', 'name': 'ATR 72-600', 'manufacturer': 'ATR', 'category': 'turboprop', 'size_code': 'C', 'is_wide_body': False, 'pax_capacity': 70},
]


# Apron 1: Nose-in, stands 2-9 plus stand 10
# Stands 5, 6, 7 can be subdivided into A and B (all Code C)
PARKING_STANDS = [
    # Apron 1 Main
    {'stand_number': '2',  'apron': 'apron1', 'size_code': 'E', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': False},
    {'stand_number': '3',  'apron': 'apron1', 'size_code': 'C', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': False},
    {'stand_number': '4',  'apron': 'apron1', 'size_code': 'E', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': False},
    {'stand_number': '5',  'apron': 'apron1', 'size_code': 'E', 'has_boarding_bridge': True,  'boarding_bridge_number': 1,    'is_remote': False},
    {'stand_number': '6',  'apron': 'apron1', 'size_code': 'E', 'has_boarding_bridge': True,  'boarding_bridge_number': 2,    'is_remote': False},
    {'stand_number': '7',  'apron': 'apron1', 'size_code': 'F', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': False},
    {'stand_number': '8',  'apron': 'apron1', 'size_code': 'C', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': False},
    {'stand_number': '9',  'apron': 'apron1', 'size_code': 'E', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': False},
    {'stand_number': '10', 'apron': 'apron1', 'size_code': 'B', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': False},
    # Subdivisions of stand 5 (parent=5)
    {'stand_number': '5A', 'apron': 'apron1', 'size_code': 'C', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': False, 'parent': '5'},
    {'stand_number': '5B', 'apron': 'apron1', 'size_code': 'C', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': False, 'parent': '5'},
    # Subdivisions of stand 6 (parent=6)
    {'stand_number': '6A', 'apron': 'apron1', 'size_code': 'C', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': False, 'parent': '6'},
    {'stand_number': '6B', 'apron': 'apron1', 'size_code': 'C', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': False, 'parent': '6'},
    # Subdivisions of stand 7 (parent=7)
    {'stand_number': '7A', 'apron': 'apron1', 'size_code': 'C', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': False, 'parent': '7'},
    {'stand_number': '7B', 'apron': 'apron1', 'size_code': 'C', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': False, 'parent': '7'},
    # Apron 1 Extended — Remote, Nose-out, all Code C
    {'stand_number': '20', 'apron': 'apron1ext', 'size_code': 'C', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': True},
    {'stand_number': '21', 'apron': 'apron1ext', 'size_code': 'C', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': True},
    {'stand_number': '22', 'apron': 'apron1ext', 'size_code': 'C', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': True},
    {'stand_number': '23', 'apron': 'apron1ext', 'size_code': 'C', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': True},
    {'stand_number': '24', 'apron': 'apron1ext', 'size_code': 'C', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': True},
    {'stand_number': '25', 'apron': 'apron1ext', 'size_code': 'C', 'has_boarding_bridge': False, 'boarding_bridge_number': None, 'is_remote': True},
]

GATES = [
    {'gate_number': '1',  'has_boarding_bridge': False, 'connected_stand': None},
    {'gate_number': '2A', 'has_boarding_bridge': False, 'connected_stand': None},
    {'gate_number': '2B', 'has_boarding_bridge': True,  'connected_stand': '5'},  # Bridge 1 → Stand 5
    {'gate_number': '3A', 'has_boarding_bridge': False, 'connected_stand': None},
    {'gate_number': '3B', 'has_boarding_bridge': False, 'connected_stand': None},
    {'gate_number': '4',  'has_boarding_bridge': True,  'connected_stand': '6'},  # Bridge 2 → Stand 6
]


class Command(BaseCommand):
    help = 'Seed initial reference data (airlines, airports, aircraft types, stands, gates, counters)'

    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write('Seeding airlines...')
        for data in AIRLINES:
            Airline.objects.get_or_create(iata_code=data['iata_code'], defaults=data)
        self.stdout.write(self.style.SUCCESS(f'  {len(AIRLINES)} airlines loaded'))

        self.stdout.write('Seeding airports...')
        for data in AIRPORTS:
            Airport.objects.get_or_create(iata_code=data['iata_code'], defaults=data)
        self.stdout.write(self.style.SUCCESS(f'  {len(AIRPORTS)} airports loaded'))

        self.stdout.write('Seeding aircraft types...')
        for data in AIRCRAFT_TYPES:
            AircraftType.objects.get_or_create(code=data['code'], defaults=data)
        self.stdout.write(self.style.SUCCESS(f'  {len(AIRCRAFT_TYPES)} aircraft types loaded'))

        self.stdout.write('Seeding parking stands...')
        # First pass: create parent stands
        parent_map = {}
        for data in PARKING_STANDS:
            if 'parent' not in data:
                stand_data = {k: v for k, v in data.items() if k != 'parent'}
                stand, _ = ParkingStand.objects.get_or_create(
                    stand_number=data['stand_number'], defaults=stand_data
                )
                parent_map[data['stand_number']] = stand

        # Second pass: create subdivisions
        for data in PARKING_STANDS:
            if 'parent' in data:
                parent = parent_map.get(data['parent'])
                stand_data = {k: v for k, v in data.items() if k != 'parent'}
                stand_data['parent_stand'] = parent
                ParkingStand.objects.get_or_create(
                    stand_number=data['stand_number'], defaults=stand_data
                )
        self.stdout.write(self.style.SUCCESS(f'  {len(PARKING_STANDS)} stands loaded'))

        self.stdout.write('Seeding gates...')
        for data in GATES:
            stand = None
            if data['connected_stand']:
                stand = ParkingStand.objects.filter(stand_number=data['connected_stand']).first()
            gate_data = {
                'gate_number': data['gate_number'],
                'has_boarding_bridge': data['has_boarding_bridge'],
                'connected_stand': stand,
            }
            Gate.objects.get_or_create(gate_number=data['gate_number'], defaults=gate_data)
        self.stdout.write(self.style.SUCCESS(f'  {len(GATES)} gates loaded'))

        self.stdout.write('Seeding check-in counters...')
        for i in range(1, 23):
            CheckInCounter.objects.get_or_create(
                counter_number=i,
                defaults={'is_dedicated_home_airline': i <= 4}
            )
        self.stdout.write(self.style.SUCCESS('  22 check-in counters loaded'))

        self.stdout.write(self.style.SUCCESS('\nAll seed data loaded successfully!'))
