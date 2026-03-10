from core.models import FlightRequest, StandAllocation, GateAllocation, CheckInAllocation
from core.services.allocation import allocate_resources_for_flight

def run():
    print("Clearing all resource allocations...")
    StandAllocation.objects.all().delete()
    GateAllocation.objects.all().delete()
    CheckInAllocation.objects.all().delete()

    flights = FlightRequest.objects.all()
    flights.update(status='pending')
    print(f"Reset {flights.count()} flights to pending... Starting reallocation...")

    allocated_count = 0
    conflict_count = 0
    
    alloc_cache = {}

    for flight in flights:
        res = allocate_resources_for_flight(flight, alloc_cache)
        if flight.status == 'allocated':
            allocated_count += 1
        elif flight.status == 'conflict':
            conflict_count += 1

    print(f"Done! {allocated_count} allocated, {conflict_count} with conflicts.")

if __name__ == '__main__':
    run()
