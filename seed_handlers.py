import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scheduler.settings')
django.setup()

from core.models import Airline, Airport, ParkingStand, Gate, GroundHandler, AirlineGatePreference, AirlineStandPreference

# 1. Clear existing handlers/preferences if any
GroundHandler.objects.all().delete()
AirlineGatePreference.objects.all().delete()
AirlineStandPreference.objects.all().delete()

# 2. Get airlines
kqa = Airline.objects.filter(iata_code='KQ').first()
atc = Airline.objects.filter(iata_code='TC').first()
fje = Airline.objects.filter(iata_code='7F').first()
ur = Airline.objects.filter(iata_code='UR').first()

other_airlines = Airline.objects.exclude(iata_code__in=['KQ', 'TC', '7F', 'UR'])

# 3. Create Handlers
das = GroundHandler.objects.create(name='DAS Handling', short_code='DAS')
if kqa: das.airlines.add(kqa)
if atc: das.airlines.add(atc)
if fje: das.airlines.add(fje)

mnz = GroundHandler.objects.create(name='Menzies Aviation', short_code='MNZ')
mnz.airlines.add(*other_airlines)

ug_handler = GroundHandler.objects.create(name='Uganda Airlines', short_code='UG')
if ur: ug_handler.airlines.add(ur)

# 4. Create Preferences for Uganda Airlines (UR)
if ur:
    lgw = Airport.objects.filter(iata_code='LGW').first()
    bom = Airport.objects.filter(iata_code='BOM').first()
    dxb = Airport.objects.filter(iata_code='DXB').first()
    
    gate_4 = Gate.objects.filter(gate_number='4').first()
    gate_3a = Gate.objects.filter(gate_number='3A').first()
    gate_3b = Gate.objects.filter(gate_number='3B').first()

    # Gate 4 for LGW (hard block)
    if gate_4 and lgw:
        AirlineGatePreference.objects.create(
            airline=ur,
            preferred_gate=gate_4,
            destination=lgw,
            is_hard_block=True,
            notes='Strictly Gate 4 for London (LGW)'
        )
    
    # Gate 3B for BOM
    if gate_3b and bom:
         AirlineGatePreference.objects.create(
            airline=ur,
            preferred_gate=gate_3b,
            destination=bom,
            is_hard_block=False,
            notes='Gate 3B for BOM (bridge corridor)'
        )

    # Gate 3A for all other flights
    if gate_3a:
        AirlineGatePreference.objects.create(
            airline=ur,
            preferred_gate=gate_3a,
            destination=None,
            is_hard_block=False,
            notes='Default gate for other UR flights'
        )

    # Stand preferences: Bridge required for LGW, BOM, DXB
    if lgw:
        AirlineStandPreference.objects.create(
            airline=ur,
            requires_bridge=True,
            destination=lgw,
            notes='Requires bridge stand'
        )
    if bom:
        AirlineStandPreference.objects.create(
            airline=ur,
            requires_bridge=True,
            destination=bom,
            notes='Requires bridge stand'
        )
    if dxb:
        AirlineStandPreference.objects.create(
            airline=ur,
            requires_bridge=True,
            destination=dxb,
            notes='Requires bridge stand'
        )

print("Successfully seeded Handlers and Preferences!")
