from datetime import date, time
from core.models import FlightRequest, Airline, Airport, AircraftType, CheckInAllocation
from core.services.allocation import allocate_checkin

FlightRequest.objects.all().delete()
airline_other = Airline.objects.exclude(iata_code='UR').first()
origin = Airport.objects.first()
dest = Airport.objects.last()

ac_e = AircraftType.objects.filter(is_wide_body=True).first()

# 4. Other airline wide body (isolated)
f4 = FlightRequest.objects.create(airline=airline_other, arrival_flight_number="OT3", departure_flight_number="OT4", aircraft_type=ac_e, season="summer", year=2026, arrival_time=time(12, 0), departure_time=time(14, 0), origin=origin, destination=dest, valid_from=date(2026,6,1), valid_to=date(2026,6,1), ground_days=0)
alloc4 = allocate_checkin(f4, date(2026,6,1))
print(f"Other airline wide aircraft alloc: {alloc4.counter_from}-{alloc4.counter_to} (Expected 6 counters)")

