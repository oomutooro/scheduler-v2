"""
Unit tests in this module inherit from ``django.test.TestCase``.
Django's test runner automatically creates a separate temporary database
(``test_<name>``) for each test run, runs migrations against it, and then
tears it down when finished. The development database (``db.sqlite3``
or whatever you configure in ``DATABASES``) is left untouched. This is why
it appears that a database is "deleted" after every test – it's simply the
isolated test database being created and destroyed. If you'd like to retain
that test database between runs, invoke the test command with ``--keepdb``.

The tests themselves only create records they need and never directly
reference the production data file.
"""

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
        # suggestions should be generated for the flight at peak
        self.assertTrue(ctx.get('suggestions'))
        sug = ctx['suggestions'][0]
        self.assertEqual(sug['flight'], 'XX 100/1')
        self.assertNotEqual(sug['recommend_hour'], sug['current_hour'])

        # template should render our new suggestions table structure
        html = response.content.decode()
        self.assertIn('class="suggestions-table"', html)

    def test_suggestions_distribution(self):
        # create another non-home flight at same busiest hour
        from datetime import time
        from core.models import FlightRequest
        FlightRequest.objects.create(
            airline=self.airline,
            arrival_flight_number='300',
            departure_flight_number='301',
            aircraft_type=self.aircraft,
            operation_type='turnaround',
            season='summer',
            year=2026,
            arrival_time=time(12,0),
            departure_time=time(14,0),
            days_of_operation=2
        )
        response = self.client.get('/reports/daily-analysis/?season=summer&year=2026&day=monday')
        ctx = response.context
        if len(ctx.get('suggestions', [])) > 1:
            hours = [s['recommend_hour'] for s in ctx['suggestions']]
            # expect at least two different recommendation hours
            self.assertNotEqual(hours[0], hours[1])


class ReportsTest(TestCase):
    def setUp(self):
        from datetime import time
        from core.models import Airline, AircraftType, FlightRequest
        self.airline = Airline.objects.create(iata_code='YY', icao_code='YYY', name='Test2', is_home_airline=False)
        self.aircraft = AircraftType.objects.create(
            code='T2', name='Testjet2', manufacturer='Test',
            category='narrow_body', size_code='C', is_wide_body=False, pax_capacity=150
        )
        # add a single flight so charts have data
        FlightRequest.objects.create(
            airline=self.airline,
            arrival_flight_number='200',
            departure_flight_number='201',
            aircraft_type=self.aircraft,
            operation_type='turnaround',
            season='summer',
            year=2026,
            arrival_time=time(12,0),
            departure_time=time(14,0),
            days_of_operation=2
        )

    def test_reports_context_contains_chart_arrays(self):
        response = self.client.get('/reports/?season=summer&year=2026')
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertIn('airline_chart_labels', ctx)
        self.assertIn('airline_chart_values', ctx)
        self.assertEqual(len(ctx['airline_chart_labels']), 1)
        self.assertEqual(len(ctx['airline_chart_values']), 1)


class AllocationAutoTest(TestCase):
    """Verify bulk auto-allocation behaviour (clearing + recommendations)."""

    def setUp(self):
        from datetime import time
        from core.models import Airline, AircraftType, ParkingStand, FlightRequest

        self.airline = Airline.objects.create(
            iata_code='ZZ', icao_code='ZZZ', name='AutoTest', is_home_airline=False
        )
        self.aircraft = AircraftType.objects.create(
            code='A1', name='Autojet', manufacturer='Test',
            category='narrow_body', size_code='C', is_wide_body=False, pax_capacity=100
        )
        self.stand1 = ParkingStand.objects.create(stand_number='1', apron='apron1', size_code='C')
        self.stand2 = ParkingStand.objects.create(stand_number='2', apron='apron1', size_code='C')

        # monday flight
        self.flight = FlightRequest.objects.create(
            airline=self.airline,
            arrival_flight_number='500',
            departure_flight_number='501',
            aircraft_type=self.aircraft,
            operation_type='turnaround',
            season='summer',
            year=2026,
            arrival_time=time(10,0),
            departure_time=time(12,0),
            days_of_operation=2
        )

    def test_auto_allocation_clears_previous(self):
        from core.services.allocation import allocate_stand
        from core.models import StandAllocation
        from datetime import date

        alloc_date = date(2026, 4, 6)
        # create an existing allocation manually
        old_alloc = allocate_stand(self.flight, alloc_date, {})
        self.assertIsNotNone(old_alloc)
        old_id = old_alloc.id

        # run auto-allocate; selecting the same flight
        response = self.client.post(
            '/allocations/auto/',
            {'flight_ids': [str(self.flight.id)], 'season': 'summer'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        # verify old record was removed
        self.assertFalse(StandAllocation.objects.filter(id=old_id).exists())
        # a new one should exist (shuffle may choose a different stand)
        new_allocs = StandAllocation.objects.filter(flight_request=self.flight)
        self.assertTrue(new_allocs.exists())

        # now remove all resources so allocation truly cannot succeed
        from core.models import ParkingStand, Gate, CheckInCounter
        ParkingStand.objects.all().delete()
        Gate.objects.all().delete()
        # allocate_checkin uses a @property; temporarily override it on the class
        from core.models import FlightRequest
        FlightRequest.min_counters = property(lambda self: 50)
        # import time so our lambda can construct datetime objects
        from datetime import time
        # also monkeypatch the service helper so we know what will be shown
        from core.services import conflict_resolution
        conflict_resolution.find_alternative_slots = lambda flight, **kw: [
            {'arrival_time': time(15,0), 'departure_time': None},
            {'arrival_time': None, 'departure_time': time(18,0)}
        ]

        # run auto-allocate without following the redirect so the
        # session entry isn't popped yet.
        response2 = self.client.post(
            '/allocations/auto/',
            {'flight_ids': [str(self.flight.id)], 'season': 'summer'},
            follow=False
        )
        # after a failed allocation we expect a redirect to recommendations
        self.assertEqual(response2.status_code, 302)
        sess = self.client.session
        self.assertIn('auto_recommendations', sess)

        # now follow the redirect manually and inspect the page
        response3 = self.client.get(response2['Location'])
        body = response3.content.decode()
        self.assertContains(response3, 'Auto-allocation Recommendations')
        self.assertContains(response3, '500/1')
        # times are rendered with seconds by default
        self.assertTrue('15:00' in body or '15:00:00' in body)
        self.assertTrue('18:00' in body or '18:00:00' in body)
        # should have warning message about inability
        self.assertIn('could not be auto-allocated', body)
        # page should show explanatory note about UR exclusion
        self.assertIn('Uganda Airlines flights are excluded', body)

    def test_ur_flight_excluded_from_recommendations(self):
        """Uganda Airlines flights should not appear on the recommendations page."""
        from core.models import Airline, FlightRequest, AircraftType
        from datetime import time

        ur = Airline.objects.create(iata_code='UR', icao_code='UGD', name='Uganda Airlines', is_home_airline=True)
        # use a wide-body aircraft to avoid the 'home airline small aircraft'
        # check-in shortcut so that removal of counters makes allocation fail.
        wide = AircraftType.objects.create(
            code='W1', name='Widejet', manufacturer='Test',
            category='wide_body', size_code='D', is_wide_body=True, pax_capacity=300
        )
        ur_flight = FlightRequest.objects.create(
            airline=ur,
            arrival_flight_number='900',
            departure_flight_number='901',
            aircraft_type=wide,
            operation_type='turnaround',
            season='summer',
            year=2026,
            arrival_time=time(10,0),
            departure_time=time(12,0),
            days_of_operation=2
        )

        # force failure by removing all resources
        from core.models import ParkingStand, Gate, CheckInCounter
        ParkingStand.objects.all().delete()
        Gate.objects.all().delete()
        # arbitrarily high counter requirement
        from core.models import FlightRequest as FR
        FR.min_counters = property(lambda self: 50)
        # stub suggestions so we can detect if they're generated
        from datetime import time as dt_time
        from core.services import conflict_resolution
        conflict_resolution.find_alternative_slots = lambda flight, **kw: [
            {'arrival_time': dt_time(16,0), 'departure_time': None}
        ]

        resp = self.client.post(
            '/allocations/auto/',
            {'flight_ids': [str(ur_flight.id)], 'season': 'summer'},
            follow=True
        )
        # restore property to avoid leaking state
        del FR.min_counters

        body = resp.content.decode()
        # should not land on recommendations page since no non-UR suggestions exist
        self.assertNotContains(resp, 'Auto-allocation Recommendations')
        # session must have no auto_recommendations data
        sess = resp.wsgi_request.session
        self.assertNotIn('auto_recommendations', sess)
        # although flight failed, warning message should exist
        self.assertIn('could not be auto-allocated', body)


class AllocationRulesTest(TestCase):
    """Ensure gate assignments respect stand/bridge compatibility rules."""

    def setUp(self):
        from datetime import time
        from core.models import Airline, AircraftType, FlightRequest
        # non-home airline
        self.airline = Airline.objects.create(iata_code='XX', icao_code='XXX', name='Test', is_home_airline=False)
        self.aircraft = AircraftType.objects.create(
            code='T1', name='Testjet', manufacturer='Test',
            category='narrow_body', size_code='C', is_wide_body=False, pax_capacity=100
        )
        # create standard gate objects if not present; will be seeded in migrations but safe to ensure
        from core.management.commands import seed_data
        # seed_data handle already created gates/stands; rely on existing data

    def test_bridge_gate_skipped_without_bridge_stand(self):
        from datetime import date, time
        from core.models import FlightRequest, StandAllocation, Gate, ParkingStand
        from core.services.allocation import allocate_gate

        # prepare gate 4 only; we need a dummy stand 6 to satisfy FK
        Gate.objects.all().delete()
        stand6 = ParkingStand.objects.create(stand_number='6', apron='apron1', size_code='E', has_boarding_bridge=True)
        Gate.objects.create(gate_number='4', has_boarding_bridge=True, connected_stand=stand6)

        # create a stand without bridge (e.g., stand 9)
        stand9 = ParkingStand.objects.create(stand_number='9', apron='apron1', size_code='E', has_boarding_bridge=False)

        flight = FlightRequest.objects.create(
            airline=self.airline,
            arrival_flight_number='700',
            departure_flight_number='701',
            aircraft_type=self.aircraft,
            operation_type='turnaround',
            season='summer',
            year=2026,
            arrival_time=time(10,0),
            departure_time=time(12,0),
            days_of_operation=2
        )
        alloc_date = date(2026,4,6)
        # manually assign stand 9
        StandAllocation.objects.create(flight_request=flight, stand=stand9,
                                       date=alloc_date, start_time=time(10,0), end_time=time(12,0))
        # attempt gate allocation should fail
        result = allocate_gate(flight, alloc_date, alloc_cache={})
        self.assertIsNone(result)

    def test_bridge_gate_only_with_matching_stand(self):
        from datetime import date, time
        from core.models import FlightRequest, StandAllocation, Gate, ParkingStand
        from core.services.allocation import allocate_gate

        # put gate 2B connected to stand 5
        Gate.objects.all().delete()
        stand5 = ParkingStand.objects.create(stand_number='5', apron='apron1', size_code='E', has_boarding_bridge=True)
        Gate.objects.create(gate_number='2B', has_boarding_bridge=True, connected_stand=stand5)

        # create stand 5 with bridge (already created above)
        # stand5 already exists
        flight = FlightRequest.objects.create(
            airline=self.airline,
            arrival_flight_number='710',
            departure_flight_number='711',
            aircraft_type=self.aircraft,
            operation_type='turnaround',
            season='summer',
            year=2026,
            arrival_time=time(8,0),
            departure_time=time(10,0),
            days_of_operation=2
        )
        alloc_date = date(2026,4,6)
        StandAllocation.objects.create(flight_request=flight, stand=stand5,
                                       date=alloc_date, start_time=time(8,0), end_time=time(10,0))
        result = allocate_gate(flight, alloc_date, alloc_cache={})
        self.assertIsNotNone(result)
        self.assertEqual(result.gate.gate_number, '2B')

    def test_no_bridge_gate_for_mismatched_bridge_stand(self):
        from datetime import date, time
        from core.models import FlightRequest, StandAllocation, Gate, ParkingStand
        from core.services.allocation import allocate_gate

        # single bridge gate 4 connected to stand 6
        Gate.objects.all().delete()
        stand6 = ParkingStand.objects.create(stand_number='6', apron='apron1', size_code='E', has_boarding_bridge=True)
        Gate.objects.create(gate_number='4', has_boarding_bridge=True, connected_stand=stand6)
        # create stand 5 which has a bridge but not matching gate
        stand5 = ParkingStand.objects.create(stand_number='5', apron='apron1', size_code='E', has_boarding_bridge=True)

        flight = FlightRequest.objects.create(
            airline=self.airline,
            arrival_flight_number='720',
            departure_flight_number='721',
            aircraft_type=self.aircraft,
            operation_type='turnaround',
            season='summer',
            year=2026,
            arrival_time=time(9,0),
            departure_time=time(11,0),
            days_of_operation=2
        )
        alloc_date = date(2026,4,6)
        StandAllocation.objects.create(flight_request=flight, stand=stand5,
                                       date=alloc_date, start_time=time(9,0), end_time=time(11,0))
        # since gate 4 is for stand 6, it should not be assigned to stand 5
        result = allocate_gate(flight, alloc_date, alloc_cache={})
        self.assertIsNone(result)

