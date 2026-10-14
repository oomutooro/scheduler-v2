"""Allocate fixed resources to Uganda Airlines Winter 2026 departures."""

from collections import defaultdict
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import (
    Airline,
    CheckInAllocation,
    CheckInCounter,
    FlightRequest,
    Gate,
    GateAllocation,
    ParkingStand,
    StandAllocation,
)
from core.services.allocation import (
    get_related_stand_ids,
    time_subtract_minutes,
    times_overlap,
)


class Command(BaseCommand):
    help = 'Allocate Winter 2026 Uganda Airlines departure resources'

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument('--dry-run', action='store_true', help='Report assignments without writing them')

    def handle(self, *args: Any, **options: Any) -> None:
        airline = Airline.objects.filter(iata_code='UR').first()
        if airline is None:
            raise CommandError('Uganda Airlines (UR) is missing from the database.')

        flights = list(
            FlightRequest.objects.filter(
                airline=airline,
                season='winter',
                year=2026,
                operation_type='departure',
            ).select_related('aircraft_type', 'destination').order_by('id')
        )
        if not flights:
            raise CommandError('No Uganda Airlines Winter 2026 departure flights were found.')

        if any(not flight.valid_from or not flight.valid_to for flight in flights):
            raise CommandError('Every target departure must have explicit valid-from and valid-to dates.')

        stand_by_number = {
            stand.stand_number: stand
            for stand in ParkingStand.objects.filter(
                is_active=True,
                stand_number__in=('3', '6', '7', '8', '9'),
            )
        }
        gate_by_number = {
            gate.gate_number: gate
            for gate in Gate.objects.filter(is_active=True, gate_number__in=('3A', '4'))
        }
        active_counters = set(
            CheckInCounter.objects.filter(is_active=True, counter_number__lte=5)
            .values_list('counter_number', flat=True)
        )
        missing = []
        if any(number not in stand_by_number for number in ('3', '6', '7', '8', '9')):
            missing.append('stands 3, 6, 7, 8, and 9')
        if any(number not in gate_by_number for number in ('3A', '4')):
            missing.append('gates 3A and 4')
        if not {1, 2, 3, 4}.issubset(active_counters) or 5 not in active_counters:
            missing.append('active check-in counters 1 through 5')
        if missing:
            raise CommandError(f'Missing required resources: {", ".join(missing)}')

        occurrences_by_flight: dict[int, list[Any]] = {}
        inactive_flights = []
        for flight in flights:
            occurrences = []
            current = flight.valid_from
            while current <= flight.valid_to:
                if flight.operates_on_date(current):
                    occurrences.append(current)
                current += timedelta(days=1)
            if not occurrences:
                inactive_flights.append(flight)
            occurrences_by_flight[int(flight.pk)] = occurrences

        flight_ids = [int(flight.pk) for flight in flights]
        first_date = min(flight.valid_from for flight in flights)
        last_date = max(flight.valid_to for flight in flights)
        existing_stands = list(
            StandAllocation.objects.filter(date__range=(first_date, last_date))
            .exclude(flight_request_id__in=flight_ids)
            .select_related('stand')
        )
        existing_gates = list(
            GateAllocation.objects.filter(date__range=(first_date, last_date))
            .exclude(flight_request_id__in=flight_ids)
            .select_related('gate')
        )
        existing_counters = list(
            CheckInAllocation.objects.filter(date__range=(first_date, last_date))
            .exclude(flight_request_id__in=flight_ids)
            .select_related('flight_request__airline')
        )

        stands_by_date: dict[Any, list[Any]] = defaultdict(list)
        gates_by_date: dict[Any, list[Any]] = defaultdict(list)
        counters_by_date: dict[Any, list[Any]] = defaultdict(list)
        for allocation in existing_stands:
            stands_by_date[allocation.date].append(allocation)
        for allocation in existing_gates:
            gates_by_date[allocation.date].append(allocation)
        for allocation in existing_counters:
            counters_by_date[allocation.date].append(allocation)

        relationship_cache: dict[str, Any] = {}
        related_stand_ids = {
            int(stand.pk): set(get_related_stand_ids(int(stand.pk), relationship_cache))
            for stand in stand_by_number.values()
        }

        def stand_candidates(flight: FlightRequest) -> list[ParkingStand]:
            if flight.destination and flight.destination.iata_code == 'LGW':
                return [stand_by_number['6']]
            if flight.aircraft_type.size_code in ('A', 'B', 'C'):
                numbers = ('3', '8')
            elif flight.aircraft_type.size_code in ('D', 'E'):
                numbers = ('9', '7')
            else:
                numbers = ('7',)
            candidates = [stand_by_number[number] for number in numbers]
            return [stand for stand in candidates if stand.can_accommodate(flight.aircraft_type)]

        planned_stands: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        stand_for_flight: dict[int, ParkingStand] = {}
        ordered_flights = sorted(
            [flight for flight in flights if occurrences_by_flight[int(flight.pk)]],
            key=lambda flight: (
                len(stand_candidates(flight)),
                -len(occurrences_by_flight[int(flight.pk)]),
                int(flight.pk),
            ),
        )
        for flight in ordered_flights:
            candidates = stand_candidates(flight)
            if not candidates:
                raise CommandError(f'No size-appropriate stand is available for {flight.display_flight_numbers}.')

            def candidate_score(stand: ParkingStand) -> int:
                related = related_stand_ids[int(stand.pk)]
                conflicts = 0
                for day in occurrences_by_flight[int(flight.pk)]:
                    start = time_subtract_minutes(flight.departure_time, 90)
                    end = flight.departure_time
                    conflicts += sum(
                        1
                        for allocation in stands_by_date[day]
                        if int(allocation.stand_id) in related
                        and times_overlap(start, end, allocation.start_time, allocation.end_time)
                    )
                    conflicts += sum(
                        1
                        for allocation in planned_stands[day]
                        if related.intersection(allocation['related_stand_ids'])
                        and times_overlap(start, end, allocation['start_time'], allocation['end_time'])
                    )
                return conflicts

            chosen_stand = min(candidates, key=candidate_score)
            stand_for_flight[int(flight.pk)] = chosen_stand
            related = related_stand_ids[int(chosen_stand.pk)]
            for day in occurrences_by_flight[int(flight.pk)]:
                planned_stands[day].append({
                    'flight_id': int(flight.pk),
                    'stand_id': int(chosen_stand.pk),
                    'related_stand_ids': related,
                    'start_time': time_subtract_minutes(flight.departure_time, 90),
                    'end_time': flight.departure_time,
                })

        flights_by_id = {int(flight.pk): flight for flight in flights}
        stand_rows = []
        gate_rows = []
        counter_rows = []
        for flight in flights:
            is_lgw = bool(flight.destination and flight.destination.iata_code == 'LGW')
            gate = gate_by_number['4' if is_lgw else '3A']
            counter_to = 5 if is_lgw else 4
            for day in occurrences_by_flight[int(flight.pk)]:
                departure = flight.departure_time
                stand_rows.append({
                    'flight_request': flight,
                    'date': day,
                    'stand': stand_for_flight[int(flight.pk)],
                    'start_time': time_subtract_minutes(departure, 90),
                    'end_time': departure,
                })
                gate_rows.append({
                    'flight_request': flight,
                    'date': day,
                    'gate': gate,
                    'start_time': time_subtract_minutes(departure, 45),
                    'end_time': time_subtract_minutes(departure, 15),
                })
                checkin_close = time_subtract_minutes(departure, 60)
                counter_rows.append({
                    'flight_request': flight,
                    'date': day,
                    'counter_from': 1,
                    'counter_to': counter_to,
                    'start_time': time_subtract_minutes(
                        checkin_close,
                        flight.checkin_duration_hours * 60,
                    ),
                    'end_time': checkin_close,
                })

        stand_conflicts: set[tuple[int, Any]] = set()
        gate_conflicts: set[tuple[int, Any]] = set()
        counter_conflicts: set[tuple[int, Any]] = set()

        for row in stand_rows:
            flight_id, day = int(row['flight_request'].pk), row['date']
            related = related_stand_ids[int(row['stand'].pk)]
            for allocation in stands_by_date[day]:
                if int(allocation.stand_id) in related and times_overlap(
                    row['start_time'], row['end_time'], allocation.start_time, allocation.end_time
                ):
                    stand_conflicts.add((flight_id, day))
            for allocation in planned_stands[day]:
                if allocation['flight_id'] != flight_id and related.intersection(allocation['related_stand_ids']) and times_overlap(
                    row['start_time'], row['end_time'], allocation['start_time'], allocation['end_time']
                ):
                    stand_conflicts.add((flight_id, day))
                    stand_conflicts.add((allocation['flight_id'], day))

        planned_gates: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for row in gate_rows:
            day = row['date']
            for allocation in gates_by_date[day]:
                if int(allocation.gate_id) == int(row['gate'].pk) and times_overlap(
                    row['start_time'], row['end_time'], allocation.start_time, allocation.end_time
                ):
                    gate_conflicts.add((int(row['flight_request'].pk), day))
            for allocation in planned_gates[day]:
                if int(allocation['gate'].pk) == int(row['gate'].pk) and times_overlap(
                    row['start_time'], row['end_time'], allocation['start_time'], allocation['end_time']
                ):
                    gate_conflicts.add((int(row['flight_request'].pk), day))
                    gate_conflicts.add((allocation['flight_id'], day))
            planned_gates[day].append({
                'flight_id': int(row['flight_request'].pk),
                'gate': row['gate'],
                'start_time': row['start_time'],
                'end_time': row['end_time'],
            })

        for row in counter_rows:
            day = row['date']
            for allocation in counters_by_date[day]:
                if (
                    allocation.flight_request.airline.iata_code != 'UR'
                    and allocation.counter_from <= row['counter_to']
                    and allocation.counter_to >= row['counter_from']
                    and times_overlap(row['start_time'], row['end_time'], allocation.start_time, allocation.end_time)
                ):
                    counter_conflicts.add((int(row['flight_request'].pk), day))

        conflict_flight_ids = {
            flight_id
            for flight_id, _ in stand_conflicts | gate_conflicts | counter_conflicts
        }
        total_occurrences = len(stand_rows)
        self.stdout.write(
            f'Plan: {len(flights)} flights, {total_occurrences} operating dates; '
            f'{len(stand_rows)} stands, {len(gate_rows)} gates, {len(counter_rows)} counter allocations.'
        )
        self.stdout.write(
            f'Conflicted occurrences: stands {len(stand_conflicts)}, '
            f'gates {len(gate_conflicts)}, counters {len(counter_conflicts)}; '
            f'{len(conflict_flight_ids)} flights will be marked conflict.'
        )
        if inactive_flights:
            self.stdout.write('No operating dates; left pending: ' + ', '.join(
                f'{flight.display_flight_numbers} ({flight.valid_from} to {flight.valid_to})'
                for flight in inactive_flights
            ))
        self.stdout.write('Stand assignments: ' + ', '.join(
            f'{flight.display_flight_numbers} -> {stand_for_flight[int(flight.pk)].stand_number}'
            for flight in flights if int(flight.pk) in stand_for_flight
        ))
        if options['dry_run']:
            return

        def upsert_rows(model: Any, rows: list[dict[str, Any]], fields: tuple[str, ...]) -> tuple[int, int]:
            current = {
                (int(allocation.flight_request_id), allocation.date): allocation
                for allocation in model.objects.filter(flight_request_id__in=flight_ids)
            }
            to_create = []
            to_update = []
            for row in rows:
                key = (int(row['flight_request'].pk), row['date'])
                allocation = current.get(key)
                if allocation is None:
                    to_create.append(model(**row))
                else:
                    for field in fields:
                        setattr(allocation, field, row[field])
                    to_update.append(allocation)
            if to_create:
                model.objects.bulk_create(to_create, batch_size=500)
            if to_update:
                model.objects.bulk_update(to_update, fields, batch_size=500)
            return len(to_create), len(to_update)

        with transaction.atomic():
            stand_counts = upsert_rows(
                StandAllocation, stand_rows, ('stand', 'start_time', 'end_time')
            )
            gate_counts = upsert_rows(
                GateAllocation, gate_rows, ('gate', 'start_time', 'end_time')
            )
            counter_counts = upsert_rows(
                CheckInAllocation, counter_rows,
                ('counter_from', 'counter_to', 'start_time', 'end_time'),
            )
            for flight in flights:
                if not occurrences_by_flight[int(flight.pk)]:
                    flight.status = 'pending'
                else:
                    flight.status = 'conflict' if int(flight.pk) in conflict_flight_ids else 'allocated'
                flight.save(update_fields=['status', 'updated_at'])

        self.stdout.write(self.style.SUCCESS(
            'Assignments saved (created/updated): '
            f'stands {stand_counts}, gates {gate_counts}, counters {counter_counts}.'
        ))