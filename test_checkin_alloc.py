from datetime import date, time
from core.models import FlightRequest, Airline, Airport, AircraftType, CheckInAllocation
from core.services.allocation import allocate_checkin

FlightRequest.objects.all().delete()
airline_home = Airline.objects.get(iata_code='UR')
airline_other = Airline.objects.exclude(iata_code='UR').first()
origin = Airport.objects.first()
dest = Airport.objects.last()

ac_c = AircraftType.objects.filter(is_wide_body=False, size_code='C').first()
ac_e = AircraftType.objects.filter(is_wide_body=True).first()

# 1. UR small aircraft
f1 = FlightRequest.objects.create(airline=airline_home, arrival_flight_number="UR1", departure_flight_number="UR2", aircraft_type=ac_c, season="summer", year=2026, arrival_time=time(10, 0), departure_time=time(12, 0), origin=origin, destination=dest, valid_from=date(2026,6,1), valid_to=date(2026,6,1), ground_days=0)
alloc1 = allocate_checkin(f1, date(2026,6,1))
print(f"UR small aircraft alloc: {alloc1.counter_from}-{alloc1.counter_to} (Expected 1-4)")

# 2. Another UR small aircraft at same time to ensure it shares 1-4
f2 = FlightRequest.objects.create(airline=airline_home, arrival_flight_number="UR3", departure_flight_number="UR4", aircraft_type=ac_c, season="summer", year=2026, arrival_time=time(10, 30), departure_time=time(12, 30), origin=origin, destination=dest, valid_from=date(2026,6,1), valid_to=date(2026,6,1), ground_days=0)
alloc2 = allocate_checkin(f2, date(2026,6,1))
print(f"UR small aircraft 2 alloc: {alloc2.counter_from}-{alloc2.counter_to} (Expected 1-4)")

# 3. Other airline small aircraft 
f3 = FlightRequest.objects.create(airline=airline_other, arrival_flight_number="OT1", departure_flight_number="OT2", aircraft_type=ac_c, season="summer", year=2026, arrival_time=time(11, 0), departure_time=time(13, 0), origin=origin, destination=dest, valid_from=date(2026,6,1), valid_to=date(2026,6,1), ground_days=0)
alloc3 = allocate_checkin(f3, date(2026,6,1))
print(f"Other airline small aircraft alloc: {alloc3.counter_from}-{alloc3.counter_to} (Expected 4 counters, starting >= 5)")

# 4. Other airline wide body
f4 = FlightRequest.objects.create(airline=airline_other, arrival_flight_number="OT3", departure_flight_number="OT4", aircraft_type=ac_e, season="summer", year=2026, arrival_time=time(12, 0), departure_time=time(14, 0), origin=origin, destination=dest, valid_from=date(2026,6,1), valid_to=date(2026,6,1), ground_days=0)
alloc4 = allocate_checkin(f4, date(2026,6,1))
print(f"Other airline wide aircraft alloc: {alloc4.counter_from}-{alloc4.counter_to} (Expected 6 counters)")

