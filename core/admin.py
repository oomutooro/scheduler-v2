from django.contrib import admin
from .models import (
	Airline, Airport, AircraftType, FlightRequest,
	ParkingStand, Gate, CheckInCounter,
	StandAllocation, GateAllocation, CheckInAllocation,
)


@admin.register(Airline)
class AirlineAdmin(admin.ModelAdmin):
	list_display = ('iata_code', 'icao_code', 'name', 'is_home_airline')
	search_fields = ('iata_code', 'icao_code', 'name')


@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
	list_display = ('iata_code', 'city_name', 'country')
	search_fields = ('iata_code', 'city_name')


@admin.register(AircraftType)
class AircraftTypeAdmin(admin.ModelAdmin):
	list_display = ('code', 'name', 'category', 'size_code', 'is_wide_body')
	search_fields = ('code', 'name')


@admin.register(FlightRequest)
class FlightRequestAdmin(admin.ModelAdmin):
	list_display = ('__str__', 'airline', 'aircraft_type', 'season', 'year', 'status')
	list_filter = ('season', 'year', 'status', 'airline')
	search_fields = ('arrival_flight_number', 'departure_flight_number')


@admin.register(ParkingStand)
class ParkingStandAdmin(admin.ModelAdmin):
	list_display = ('stand_number', 'apron', 'size_code', 'has_boarding_bridge', 'is_remote', 'is_active')
	search_fields = ('stand_number',)


@admin.register(Gate)
class GateAdmin(admin.ModelAdmin):
	list_display = ('gate_number', 'has_boarding_bridge', 'connected_stand', 'is_active')
	search_fields = ('gate_number',)


@admin.register(CheckInCounter)
class CheckInCounterAdmin(admin.ModelAdmin):
	list_display = ('counter_number', 'is_dedicated_home_airline', 'is_active')
	list_filter = ('is_dedicated_home_airline',)


@admin.register(StandAllocation)
class StandAllocationAdmin(admin.ModelAdmin):
	list_display = ('flight_request', 'stand', 'date', 'start_time', 'end_time')
	list_filter = ('date',)


@admin.register(GateAllocation)
class GateAllocationAdmin(admin.ModelAdmin):
	list_display = ('flight_request', 'gate', 'date', 'start_time', 'end_time')
	list_filter = ('date',)


@admin.register(CheckInAllocation)
class CheckInAllocationAdmin(admin.ModelAdmin):
	list_display = ('flight_request', 'counter_from', 'counter_to', 'date', 'start_time', 'end_time')
	list_filter = ('date',)

