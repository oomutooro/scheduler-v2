from datetime import date, time
from core.models import FlightRequest, Airline, Airport, AircraftType, StandAllocation
from core.services.allocation import allocate_resources_for_flight

FlightRequest.objects.all().delete()
airline = Airline.objects.first()
origin = Airport.objects.first()
dest = Airport.objects.last()
aircraft_narrow = AircraftType.objects.filter(is_wide_body=False, size_code='C').first()

f3 = FlightRequest.objects.create(airline=airline, arrival_flight_number="333", departure_flight_number="334", aircraft_type=aircraft_narrow, season="summer", year=2026, arrival_time=time(19, 0), departure_time=time(6, 0), origin=origin, destination=dest, valid_from=date(2026,6,1), valid_to=date(2026,6,1), ground_days=1)

print(f"ground_days is {f3.ground_days}, is_overnight is {f3.is_overnight}")
print(f"Aircraft code is {f3.aircraft_type.size_code}")

from core.services.allocation import allocate_stand
print("Allocating stand...")
alloc = allocate_stand(f3, date(2026,6,1))
print(f"Result: {alloc}")
if alloc:
    print(f"Stand: {alloc.stand.stand_number} (Apron: {alloc.stand.apron}, Remote: {alloc.stand.is_remote})")

allocs = StandAllocation.objects.filter(flight_request=f3).order_by('date')
print(f"Total StandAllocations in DB: {allocs.count()}")
for a in allocs:
    print(f"  {a.date}: {a.start_time} - {a.end_time}")
