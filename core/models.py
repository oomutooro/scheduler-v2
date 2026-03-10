from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


# ─── Reference Data ───────────────────────────────────────────────────────────

class Airline(models.Model):
    iata_code = models.CharField(max_length=2, unique=True)
    icao_code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=100)
    is_home_airline = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.iata_code} / {self.icao_code} — {self.name}"


class Airport(models.Model):
    iata_code = models.CharField(max_length=3, unique=True)
    icao_code = models.CharField(max_length=4, unique=True, null=True, blank=True)
    city_name = models.CharField(max_length=100)
    country = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['iata_code']

    def __str__(self):
        return f"{self.iata_code} — {self.city_name}"


SIZE_CODE_CHOICES = [
    ('A', 'Code A (< 15m)'),
    ('B', 'Code B (15–24m)'),
    ('C', 'Code C (24–36m)'),
    ('D', 'Code D (36–52m)'),
    ('E', 'Code E (52–65m)'),
    ('F', 'Code F (65–80m)'),
]

CATEGORY_CHOICES = [
    ('wide_body', 'Wide Body'),
    ('narrow_body', 'Narrow Body'),
    ('regional', 'Regional Jet'),
    ('turboprop', 'Turboprop'),
]


class AircraftType(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    manufacturer = models.CharField(max_length=50, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    size_code = models.CharField(max_length=1, choices=SIZE_CODE_CHOICES)
    is_wide_body = models.BooleanField(default=False)
    pax_capacity = models.IntegerField(default=0, blank=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} — {self.name} (Code {self.size_code})"

# ─── Ground Handlers & Preferences ────────────────────────────────────────────

class GroundHandler(models.Model):
    name = models.CharField(max_length=100)
    short_code = models.CharField(max_length=10, unique=True)
    airlines = models.ManyToManyField(Airline, related_name='handlers')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.short_code})"


class AirlineGatePreference(models.Model):
    airline = models.ForeignKey(Airline, on_delete=models.CASCADE, related_name='gate_preferences')
    preferred_gate = models.ForeignKey('Gate', on_delete=models.CASCADE)
    destination = models.ForeignKey(Airport, on_delete=models.CASCADE, null=True, blank=True)
    is_hard_block = models.BooleanField(default=False)
    notes = models.CharField(max_length=200, blank=True)

    def __str__(self):
        dest = f" to {self.destination.iata_code}" if self.destination else " (All)"
        return f"{self.airline.iata_code} -> Gate {self.preferred_gate.gate_number}{dest}"


class AirlineStandPreference(models.Model):
    airline = models.ForeignKey(Airline, on_delete=models.CASCADE, related_name='stand_preferences')
    requires_bridge = models.BooleanField(default=False)
    preferred_stand = models.ForeignKey('ParkingStand', on_delete=models.SET_NULL, null=True, blank=True)
    destination = models.ForeignKey(Airport, on_delete=models.CASCADE, null=True, blank=True)
    notes = models.CharField(max_length=200, blank=True)

    def __str__(self):
        dest = f" to {self.destination.iata_code}" if self.destination else " (All)"
        bridge = " [Bridge Req]" if self.requires_bridge else ""
        stand = f" Stand {self.preferred_stand.stand_number}" if self.preferred_stand else ""
        return f"{self.airline.iata_code}{dest}{bridge}{stand}"


# ─── Flight Requests ──────────────────────────────────────────────────────────

SEASON_CHOICES = [
    ('summer', 'Summer'),
    ('winter', 'Winter'),
]

OPERATION_TYPE_CHOICES = [
    ('turnaround', 'Turnaround (Arrival + Departure)'),
    ('arrival', 'Arrival Only'),
    ('departure', 'Departure Only'),
]

STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('allocated', 'Allocated'),
    ('conflict', 'Conflict'),
    ('cancelled', 'Cancelled'),
]

# Bitmask: bit 0 = Sunday, bit 1 = Monday, ..., bit 6 = Saturday
DAY_MASK = {
    'sunday': 1,
    'monday': 2,
    'tuesday': 4,
    'wednesday': 8,
    'thursday': 16,
    'friday': 32,
    'saturday': 64,
}


class FlightRequest(models.Model):
    airline = models.ForeignKey(Airline, on_delete=models.CASCADE, related_name='flight_requests')
    # Two flight numbers for turnarounds; single for arrival/departure only
    arrival_flight_number = models.CharField(max_length=10, blank=True)
    departure_flight_number = models.CharField(max_length=10, blank=True)
    aircraft_type = models.ForeignKey(AircraftType, on_delete=models.PROTECT, related_name='flight_requests')
    operation_type = models.CharField(max_length=20, choices=OPERATION_TYPE_CHOICES, default='turnaround')
    season = models.CharField(max_length=10, choices=SEASON_CHOICES)
    year = models.IntegerField(validators=[MinValueValidator(2020), MaxValueValidator(2099)])
    arrival_time = models.TimeField(null=True, blank=True)
    departure_time = models.TimeField(null=True, blank=True)
    origin = models.ForeignKey(Airport, on_delete=models.PROTECT, related_name='inbound_requests', null=True, blank=True)
    destination = models.ForeignKey(Airport, on_delete=models.PROTECT, related_name='outbound_requests', null=True, blank=True)
    # Season scope: null=full season, otherwise partial
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    # Days of the week bitmask
    days_of_operation = models.IntegerField(default=127)  # all 7 days by default
    # Number of nights on ground
    ground_days = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_overnight(self):
        """Return True if flight stays on ground overnight or longer."""
        return self.ground_days > 0

    @property
    def departure_date_offset(self):
        """Return timedelta for the departure date offset resulting from ground days."""
        import datetime
        return datetime.timedelta(days=self.ground_days)

    def __str__(self):
        nums = []
        if self.arrival_flight_number:
            nums.append(self.arrival_flight_number)
        if self.departure_flight_number:
            nums.append(self.departure_flight_number)
        return f"{'/'.join(nums) or 'N/A'} — {self.airline.iata_code} ({self.season.capitalize()} {self.year})"

    def get_days_list(self):
        """Return list of day names that are set in the bitmask."""
        days = []
        day_order = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
        for day in day_order:
            if self.days_of_operation & DAY_MASK[day]:
                days.append(day.capitalize())
        return days

    def operates_on_date(self, date):
        """Return True if this flight request operates on the given date."""
        import datetime
        # Check date range
        if self.valid_from and date < self.valid_from:
            return False
        if self.valid_to and date > self.valid_to:
            return False
        # Check day of week (weekday(): Mon=0..Sun=6 → we use Sun=0..Sat=6)
        dow = date.isoweekday() % 7  # Sun=0, Mon=1, ... Sat=6
        day_names = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
        return bool(self.days_of_operation & DAY_MASK[day_names[dow]])

    @property
    def display_flight_numbers(self):
        """Format flight numbers, abbreviating turnaround if they share a prefix."""
        arr = self.arrival_flight_number
        dep = self.departure_flight_number
        
        if self.operation_type == 'arrival':
            return arr or "-"
        elif self.operation_type == 'departure':
            return dep or "-"
        else:
            if not arr or not dep:
                return f"{arr or '-'} / {dep or '-'}"
            import os
            common = os.path.commonprefix([arr, dep])
            if common:
                return f"{arr}/{dep[len(common):]}"
            return f"{arr} / {dep}"

    @property
    def checkin_duration_hours(self):
        """Check-in window duration in hours."""
        return 3 if self.aircraft_type.is_wide_body else 2

    @property
    def min_counters(self):
        """Minimum check-in counters to start with."""
        if self.aircraft_type.is_wide_body or self.aircraft_type.size_code in ('D', 'E', 'F'):
            return 6
        return 4

    @property
    def max_counters(self):
        """Maximum check-in counters."""
        if self.aircraft_type.is_wide_body or self.aircraft_type.size_code in ('D', 'E', 'F'):
            return 8
        return 5

    @property
    def start_date(self):
        """Effective start date of the flight request."""
        if self.valid_from:
            return self.valid_from
        from core.services.season import get_season_dates
        start, _ = get_season_dates(self.season, self.year)
        return start

    @property
    def end_date(self):
        """Effective end date of the flight request."""
        if self.valid_to:
            return self.valid_to
        from core.services.season import get_season_dates
        _, end = get_season_dates(self.season, self.year)
        return end


# ─── Airport Resources (Static reference — stands, gates, counters) ───────────

APRON_CHOICES = [
    ('apron1', 'Apron 1 (Main, Nose-in)'),
    ('apron1ext', 'Apron 1 Extended (Remote, Nose-out)'),
]


class ParkingStand(models.Model):
    stand_number = models.CharField(max_length=5, unique=True)  # e.g. "2", "5A", "5B", "20"
    apron = models.CharField(max_length=20, choices=APRON_CHOICES)
    size_code = models.CharField(max_length=1, choices=SIZE_CODE_CHOICES)
    has_boarding_bridge = models.BooleanField(default=False)
    boarding_bridge_number = models.IntegerField(null=True, blank=True)
    parent_stand = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_stands')
    is_remote = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['stand_number']

    def __str__(self):
        bridge = f" (Bridge {self.boarding_bridge_number})" if self.has_boarding_bridge else ""
        return f"Stand {self.stand_number} — Code {self.size_code}{bridge}"

    def can_accommodate(self, aircraft_type):
        """Check if this stand can accommodate the given aircraft type based on size code."""
        size_order = ['A', 'B', 'C', 'D', 'E', 'F']
        stand_idx = size_order.index(self.size_code)
        aircraft_idx = size_order.index(aircraft_type.size_code)
        return stand_idx >= aircraft_idx


class Gate(models.Model):
    gate_number = models.CharField(max_length=5, unique=True)  # e.g. "1", "2A", "2B", "3A"
    has_boarding_bridge = models.BooleanField(default=False)
    connected_stand = models.ForeignKey(ParkingStand, on_delete=models.SET_NULL, null=True, blank=True, related_name='gates')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['gate_number']

    def __str__(self):
        bridge = " (Bridge)" if self.has_boarding_bridge else ""
        return f"Gate {self.gate_number}{bridge}"


class CheckInCounter(models.Model):
    counter_number = models.IntegerField(unique=True)
    is_dedicated_home_airline = models.BooleanField(default=False)  # True for counters 1-4
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['counter_number']

    def __str__(self):
        dedicated = " (Uganda Airlines Dedicated)" if self.is_dedicated_home_airline else ""
        return f"Counter {self.counter_number}{dedicated}"


# ─── Resource Allocations ─────────────────────────────────────────────────────

class StandAllocation(models.Model):
    flight_request = models.ForeignKey(FlightRequest, on_delete=models.CASCADE, related_name='stand_allocations')
    stand = models.ForeignKey(ParkingStand, on_delete=models.CASCADE, related_name='allocations')
    date = models.DateField()
    start_time = models.TimeField()  # = arrival_time
    end_time = models.TimeField()    # = departure_time

    class Meta:
        ordering = ['date', 'start_time']

    def __str__(self):
        return f"Stand {self.stand.stand_number} — {self.flight_request} on {self.date}"


class GateAllocation(models.Model):
    flight_request = models.ForeignKey(FlightRequest, on_delete=models.CASCADE, related_name='gate_allocations')
    gate = models.ForeignKey(Gate, on_delete=models.CASCADE, related_name='allocations')
    date = models.DateField()
    start_time = models.TimeField()   # when gate opens
    end_time = models.TimeField()     # 15 min before departure

    class Meta:
        ordering = ['date', 'start_time']

    def __str__(self):
        return f"Gate {self.gate.gate_number} — {self.flight_request} on {self.date}"


class CheckInAllocation(models.Model):
    flight_request = models.ForeignKey(FlightRequest, on_delete=models.CASCADE, related_name='checkin_allocations')
    counter_from = models.IntegerField()  # first counter number
    counter_to = models.IntegerField()    # last counter number
    date = models.DateField()
    start_time = models.TimeField()   # check-in opens
    end_time = models.TimeField()     # check-in closes (1hr before departure)

    class Meta:
        ordering = ['date', 'start_time']

    def __str__(self):
        return f"Counters {self.counter_from}-{self.counter_to} — {self.flight_request} on {self.date}"

    @property
    def counter_count(self):
        return self.counter_to - self.counter_from + 1
