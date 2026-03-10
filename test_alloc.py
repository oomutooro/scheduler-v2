from datetime import date, time
from core.models import FlightRequest, Airline, Airport, AircraftType, StandAllocation
from core.services.allocation import allocate_resources_for_flight

FlightRequest.objects.all().delete()
airline = Airline.objects.first()
origin = Airport.objects.first()
dest = Airport.objects.last()
aircraft = AircraftType.objects.filter(is_wide_body=True).first()

f1 = FlightRequest.objects.create(airline=airline, arrival_flight_number="111", departure_flight_number="112", aircraft_type=aircraft, season="summer", year=2026, arrival_time=time(10, 0), departure_time=time(12, 0), origin=origin, destination=dest, valid_from=date(2026,6,1), valid_to=date(2026,6,1), ground_days=0)
res1 = allocate_resources_for_flight(f1)
s1 = StandAllocation.objects.filter(flight_request=f1).first()

f2 = FlightRequest.objects.create(airline=airline, arrival_flight_number="222", departure_flight_number="223", aircraft_type=aircraft, season="summer", year=2026, arrival_time=time(19, 0), departure_time=time(6, 0), origin=origin, destination=dest, valid_from=date(2026,6,1), valid_to=date(2026,6,1), ground_days=1)
res2 = allocate_resources_for_flight(f2)
s2_allocs = StandAllocation.objects.filter(flight_request=f2).order_by('date')

print(f"\n--- SAME DAY ---")
print(f"Allocations: {res1}, Stand: {s1.stand.stand_number} (Main apron? {not s1.stand.is_remote})")
print(f"Dates: {s1.date} {s1.start_time}-{s1.end_time}")

print(f"\n--- OVERNIGHT ---")
print(f"Allocations: {res2}")
for a in s2_allocs:
    print(f"Stand {a.stand.stand_number} (is_remote={a.stand.is_remote}) on {a.date}: {a.start_time}-{a.end_time}")
