import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scheduler.settings')
django.setup()

from core.models import Airline, Airport, ParkingStand, Gate

print("Airlines:")
for a in Airline.objects.all():
    print(f"{a.iata_code} ({a.icao_code}): {a.name}")

print("\nAirports:")
for a in Airport.objects.filter(iata_code__in=['LGW', 'BOM', 'DXB']):
    print(f"{a.iata_code}: {a.city_name}")

print("\nStands:")
for s in ParkingStand.objects.all():
    print(f"Stand {s.stand_number} - Bridge: {s.has_boarding_bridge}")

print("\nGates:")
for g in Gate.objects.all():
    conn = g.connected_stand.stand_number if g.connected_stand else None
    print(f"Gate {g.gate_number} - Bridge: {g.has_boarding_bridge} - Connected to: {conn}")
