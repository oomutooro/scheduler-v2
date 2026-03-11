from django.test import TestCase
from datetime import date

from core.services import season as season_utils


class SeasonUtilsTest(TestCase):
    def test_summer_and_winter_date_ranges(self):
        # Basic sanity checks: start < end and dates cover expected months
        s_start, s_end = season_utils.get_summer_dates(2026)
        self.assertLess(s_start, s_end)
        self.assertEqual(s_start.month, 3)
        self.assertEqual(s_end.month, 10)  # end is last Saturday of October

        w_start, w_end = season_utils.get_winter_dates(2026)
        self.assertLess(w_start, w_end)
        # Winter starts after last Sat of Oct, which is in Nov; ends in March of next year
        self.assertEqual(w_start.month, 11)
        self.assertEqual(w_end.month, 3)

    def test_get_season_for_date(self):
        # April 1 should be in summer for that year
        self.assertEqual(season_utils.get_season_for_date(date(2026, 4, 1)), ('summer', 2026))
        # November 1 should be in winter for that year
        self.assertEqual(season_utils.get_season_for_date(date(2026, 11, 1)), ('winter', 2026))

    def test_is_date_in_season(self):
        # April 15, 2026 should be inside summer 2026
        self.assertTrue(season_utils.is_date_in_season(date(2026, 4, 15), 'summer', 2026))
        # November 15, 2026 should be inside winter 2026
        self.assertTrue(season_utils.is_date_in_season(date(2026, 11, 15), 'winter', 2026))


class DailyAnalysisTest(TestCase):
    def setUp(self):
        from datetime import time
        from core.models import (
            Airline, AircraftType, ParkingStand, Gate, CheckInCounter,
            FlightRequest, StandAllocation, GateAllocation, CheckInAllocation
        )

        self.airline = Airline.objects.create(iata_code='XX', icao_code='XXX', name='Test', is_home_airline=False)
        self.aircraft = AircraftType.objects.create(
            code='T1', name='Testjet', manufacturer='Test',
            category='narrow_body', size_code='C', is_wide_body=False, pax_capacity=100
        )
        self.stand = ParkingStand.objects.create(stand_number='1', apron='apron1', size_code='C')
        self.gate = Gate.objects.create(gate_number='G1')
        self.counter = CheckInCounter.objects.create(counter_number=1)

        # choose a monday date for the allocations
        alloc_date = date(2026, 4, 6)  # April 6 2026 is a Monday

        # flight operates on Monday only
        self.flight = FlightRequest.objects.create(
            airline=self.airline,
            arrival_flight_number='100',
            departure_flight_number='101',
            aircraft_type=self.aircraft,
            operation_type='turnaround',
            season='summer',
            year=2026,
            arrival_time=time(8, 0),
            departure_time=time(10, 0),
            days_of_operation=2  # monday mask
        )

        StandAllocation.objects.create(
            flight_request=self.flight,
            stand=self.stand,
            date=alloc_date,
            start_time=time(8, 0),
            end_time=time(10, 0)
        )
        GateAllocation.objects.create(
            flight_request=self.flight,
            gate=self.gate,
            date=alloc_date,
            start_time=time(9, 0),
            end_time=time(9, 45)
        )
        CheckInAllocation.objects.create(
            flight_request=self.flight,
            counter_from=1,
            counter_to=2,
            date=alloc_date,
            start_time=time(7, 0),
            end_time=time(9, 0)
        )

    def test_daily_analysis_context(self):
        response = self.client.get('/reports/daily-analysis/?season=summer&year=2026&day=monday')
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        # basic stats
        self.assertEqual(ctx['total_flights'], 1)
        # debug logs
        if ctx['allocated_flights'] != 1:
            print('DEBUG CONTEXT:', ctx)
        self.assertEqual(ctx['allocated_flights'], 1)
        self.assertGreater(ctx['allocation_percentage'], 0)

        # hour buckets should reflect our allocations
        # flight present at 8:00 due to stand
        self.assertEqual(ctx['hourly_counts'][8], 1)
        # stand usage hour should mark 8 and 9
        self.assertEqual(ctx['hourly_stand'][8], 1)
        # gate usage should show at 9
        self.assertEqual(ctx['hourly_gate'][9], 1)
        # checkin should show at 7 and 8
        self.assertEqual(ctx['hourly_checkin'][7], 1)

        # totals
        self.assertEqual(ctx['total_stands'], 1)
        self.assertEqual(ctx['stand_usage_hours'], 2)
        # busiest hour should correspond to a time when at least one resource is active
        self.assertIn(ctx['busiest_hour'], [7,8,9])

