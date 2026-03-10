from datetime import date, time
from core.models import FlightRequest, Airline, Airport, AircraftType, StandAllocation
from core.services.allocation import allocate_resources_for_flight

FlightRequest.objects.all().delete()
airline = Airline.objects.first()
origin = Airport.objects.first()
dest = Airport.objects.last()
aircraft = AircraftType.objects.filter(is_wide_body=True).first()

f2 = FlightRequest.objects.create(airline=airline, arrival_flight_number="222", departure_flight_number="223", aircraft_type=aircraft, season="summer", year=2026, arrival_time=time(19, 0), departure_time=time(6, 0), origin=origin, destination=dest, valid_from=date(2026,6,1), valid_to=date(2026,6,1), ground_days=1)

print(f"ground_days is {f2.ground_days}, is_overnight is {f2.is_overnight}")
print(f"Aircraft code is {f2.aircraft_type.size_code}")

from core.services.allocation import allocate_stand
print("Allocating stand...")
alloc = allocate_stand(f2, date(2026,6,1))
print(f"Result: {alloc}")
if alloc:
    print(f"Stand: {alloc.stand.stand_number}")

allocs = StandAllocation.objects.filter(flight_request=f2)
print(f"Total StandAllocations in DB: {allocs.count()}")
