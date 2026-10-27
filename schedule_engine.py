# -*- coding: utf-8 -*-
"""STL/고정/자동 배정을 처리하는 greedy 스케줄 생성 엔진."""

from datetime import date, timedelta

from schedule_models import (
    AUTO,
    FIXED,
    STL,
    SUPPORT,
    UNASSIGNED,
    ALL_STAT_SHIFTS,
    CLOSING_SHIFT,
    NIGHT_SHIFT,
    OPEN_SHIFT,
    make_assignment,
)
from schedule_rules import can_work
from schedule_rules import can_work_konkuk_night
from schedule_utils import date_to_str, get_month_dates, is_weekend_or_holiday


DEFAULT_SHIFT_PRIORITY = {
    "나이트": 0,
    "오픈": 1,
    "데일리": 2,
    "마감": 3,
}


def _empty_work_count(managers):
    """매니저별 통계 기본값을 만든다."""
    counts = {}
    for manager_id in managers:
        counts[manager_id] = {
            "전체": 0,
            "오픈": 0,
            "마감": 0,
            "데일리": 0,
            "나이트": 0,
            "주말/공휴일": 0,
        }
    return counts


def _initialize_schedule(year, month, stores):
    """월 전체 날짜/매장/시프트 칸을 None으로 초기화한다."""
    schedule = {}
    for work_date in get_month_dates(year, month):
        date_str = date_to_str(work_date)
        schedule[date_str] = {}
        for store, shifts in stores.items():
            schedule[date_str][store] = {shift: None for shift in shifts}
    return schedule


def _assignment_shift_order(shifts, shift_priority=None):
    """자동 배정 시 사용할 시프트 처리 순서.

    Excel 출력 순서는 STORES에 정의된 순서를 유지하되, 자동 배정은 제약이 강한 시프트를
    먼저 채운다. 여러 후보 스케줄을 만들 때는 shift_priority를 바꿔 서로 다른 경우를
    탐색할 수 있다.
    """
    priority = shift_priority or DEFAULT_SHIFT_PRIORITY
    return sorted(shifts, key=lambda shift: (priority.get(shift, 99), shift))


def _assignment_store_order(stores, store_order=None):
    """자동 배정 시 사용할 매장 처리 순서를 반환한다."""
    if not store_order:
        return list(stores.items())

    ordered = []
    used = set()
    for store in store_order:
        if store in stores:
            ordered.append((store, stores[store]))
            used.add(store)
    for store, shifts in stores.items():
        if store not in used:
            ordered.append((store, shifts))
    return ordered


def add_work_count(work_counts, worker_id, shift, work_date, holidays):
    """매니저 근무 통계를 1건 더한다. STL과 미배정은 호출하지 않는다."""
    if worker_id not in work_counts:
        return
    work_counts[worker_id]["전체"] += 1
    if shift in ALL_STAT_SHIFTS:
        work_counts[worker_id][shift] += 1
    if is_weekend_or_holiday(work_date, holidays):
        work_counts[worker_id]["주말/공휴일"] += 1


def _recalculate_work_counts(schedule, managers, holidays):
    """고정/자동 배정 전체를 기준으로 통계를 다시 계산한다."""
    counts = _empty_work_count(managers)
    for date_str, stores in schedule.items():
        year, month, day = map(int, date_str.split("-"))
        work_date = date(year, month, day)
        for shifts in stores.values():
            for shift, assignment in shifts.items():
                if assignment and assignment.get("worker_id") in managers:
                    add_work_count(counts, assignment["worker_id"], shift, work_date, holidays)
    return counts


def _iter_schedule_slots(schedule):
    for date_str, store_map in schedule.items():
        for store, shift_map in store_map.items():
            for shift, assignment in shift_map.items():
                yield date_str, store, shift, assignment


def _is_valid_slot(schedule, item, stores):
    """입력된 날짜/매장/시프트가 현재 스케줄 범위 안에 있는지 확인한다."""
    date_str = item.get("date")
    store = item.get("store")
    shift = item.get("shift")
    return date_str in schedule and store in stores and shift in stores[store]


def apply_stl_fixed(schedule, stl_fixed, stores):
    """STL 고정 근무를 먼저 반영한다.

    STL은 매니저가 아닌 별도 인원이다. 따라서 근무 통계에 포함하지 않고,
    STL이 들어간 시프트는 자동 배정 대상에서 제외한다.
    """
    notes = []
    for item in stl_fixed:
        if not _is_valid_slot(schedule, item, stores):
            notes.append(f"STL 입력 무시: 잘못된 날짜/매장/시프트 {item}")
            continue

        date_str = item["date"]
        store = item["store"]
        shift = item["shift"]
        existing = schedule[date_str][store][shift]
        if existing:
            notes.append(f"{date_str} {store} {shift}: 기존 배정 위에 STL 입력이 있어 STL로 덮어씀")

        schedule[date_str][store][shift] = make_assignment("STL", STL, "STL 고정")
    return notes


def apply_support_assignments(schedule, support_assignments, stores):
    """외부 매장 지원 근무를 반영한다.

    외부 지원은 현재 MANAGERS에 속한 사람이 아니므로 매니저 통계에 포함하지 않고,
    입력한 날짜/매장/시프트 칸은 자동 배정 대상에서 제외한다.
    """
    notes = []
    for item in support_assignments:
        if not _is_valid_slot(schedule, item, stores):
            notes.append(f"외부 지원 입력 무시: 잘못된 날짜/매장/시프트 {item}")
            continue

        date_str = item["date"]
        store = item["store"]
        shift = item["shift"]
        existing = schedule[date_str][store][shift]
        if existing:
            notes.append(f"{date_str} {store} {shift}: 기존 배정 위에 외부 지원 입력이 있어 외부 지원으로 덮어씀")

        schedule[date_str][store][shift] = make_assignment("외부지원", SUPPORT, "외부 매장 지원")
    return notes


def apply_fixed_assignments(schedule, fixed_assignments, stores):
    """예외 고정 배정을 반영한다.

    고정 배정은 자동 배정보다 우선한다. 규칙 위반 여부는 여기서 막지 않고
    validate_schedule()에서 별도로 출력한다.
    """
    notes = []
    for item in fixed_assignments:
        if not _is_valid_slot(schedule, item, stores):
            notes.append(f"고정 배정 입력 무시: 잘못된 날짜/매장/시프트 {item}")
            continue

        date_str = item["date"]
        store = item["store"]
        shift = item["shift"]
        existing = schedule[date_str][store][shift]
        if existing and existing.get("type") == STL:
            notes.append(f"{date_str} {store} {shift}: STL 배정과 고정 배정 충돌, 고정 배정으로 덮어씀")
        elif existing:
            notes.append(f"{date_str} {store} {shift}: 기존 배정을 고정 배정으로 덮어씀")

        schedule[date_str][store][shift] = make_assignment(
            item.get("worker_id"),
            FIXED,
            item.get("reason", "예외 고정 배정"),
        )
    return notes


def _consecutive_days_before(schedule, work_date, worker_id, managers):
    count = 0
    cursor = work_date - timedelta(days=1)
    while True:
        date_str = date_to_str(cursor)
        worked = False
        for shift_map in schedule.get(date_str, {}).values():
            for assignment in shift_map.values():
                if assignment and assignment.get("worker_id") == worker_id and worker_id in managers:
                    worked = True
                    break
            if worked:
                break
        if not worked:
            return count
        count += 1
        cursor -= timedelta(days=1)


def _has_work_on_date(schedule, date_str, worker_id, managers):
    for _slot_date, _store, _shift, assignment in _iter_schedule_slots({date_str: schedule.get(date_str, {})}):
        if assignment and assignment.get("worker_id") == worker_id and worker_id in managers:
            return True
    return False


def _worked_shift_on_date(schedule, date_str, worker_id, shift_names, managers):
    for _slot_date, _store, shift, assignment in _iter_schedule_slots({date_str: schedule.get(date_str, {})}):
        if (
            assignment
            and assignment.get("worker_id") == worker_id
            and worker_id in managers
            and shift in shift_names
        ):
            return True
    return False


def _relaxed_assignment_score(schedule, work_date, store, shift, worker_id, managers, off_requests, work_counts, holidays):
    date_str = date_to_str(work_date)
    yesterday_str = date_to_str(work_date - timedelta(days=1))
    tomorrow_str = date_to_str(work_date + timedelta(days=1))
    score = 0

    if _has_work_on_date(schedule, date_str, worker_id, managers):
        score += 100000
    if date_str in set(off_requests.get(worker_id, [])):
        score += 50000
    if store == "매장A" and shift == NIGHT_SHIFT and not can_work_konkuk_night(worker_id, managers):
        score += 100000
    if _worked_shift_on_date(schedule, yesterday_str, worker_id, {NIGHT_SHIFT}, managers):
        score += 10000
    if shift == OPEN_SHIFT and _worked_shift_on_date(schedule, yesterday_str, worker_id, {CLOSING_SHIFT, NIGHT_SHIFT}, managers):
        score += 5000
    if shift in (CLOSING_SHIFT, NIGHT_SHIFT) and _worked_shift_on_date(schedule, tomorrow_str, worker_id, {OPEN_SHIFT}, managers):
        score += 5000
    consecutive_days = _consecutive_days_before(schedule, work_date, worker_id, managers)
    if consecutive_days >= 5:
        score += 5000

    manager = managers[worker_id]
    home_priority = 0 if manager.get("home_store") == store else 1
    weekend_count = work_counts[worker_id]["주말/공휴일"] if is_weekend_or_holiday(work_date, holidays) else 0
    return (
        score,
        home_priority,
        work_counts[worker_id]["전체"],
        weekend_count,
        work_counts[worker_id].get(shift, 0),
        worker_id,
    )


def fill_unassigned_relaxed(schedule, managers, holidays, off_requests):
    """남은 미배정 칸을 강제 배정한다.

    이 단계는 미배정 0건을 만들기 위한 마지막 보정이다. 가능한 한 기존 규칙을 덜 깨는
    사람을 고르지만, 위반이 생기면 validate_schedule()에서 그대로 드러난다.
    """
    notes = []
    work_counts = _recalculate_work_counts(schedule, managers, holidays)
    for date_str, store, shift, assignment in list(_iter_schedule_slots(schedule)):
        if not assignment or assignment.get("type") != UNASSIGNED:
            continue

        year, month, day = map(int, date_str.split("-"))
        work_date = date(year, month, day)
        candidates = sorted(
            managers,
            key=lambda worker_id: _relaxed_assignment_score(
                schedule, work_date, store, shift, worker_id, managers, off_requests, work_counts, holidays
            ),
        )
        selected = candidates[0]
        schedule[date_str][store][shift] = make_assignment(selected, AUTO, "미배정 방지 강제 배정")
        add_work_count(work_counts, selected, shift, work_date, holidays)
        notes.append(f"{date_str} {store} {shift}: 미배정 방지를 위해 {selected} 강제 배정")

    return notes


def _candidate_sort_key(worker_id, store, shift, work_date, managers, work_counts, holidays, id_order=None, schedule=None):
    """후보 배정 우선순위 정렬 키.

    1. 직전 연속근무 일수가 적은 인원 우선
    2. 본인 소속 매장 인원 우선
    3. 주말/공휴일이면 주말/공휴일 근무 수가 적은 인원 우선
    4. 전체 근무 수가 적은 인원 우선
    5. 해당 시프트 근무 수가 적은 인원 우선
    6. ID 기준 정렬

    모든 매니저는 3개 매장 근무가 가능하지만 특정 매장 소속 인원을 먼저 배치한다.
    id_order는 여러 후보 스케줄을 만들 때 동률 후보의 순서를 바꾸기 위한 값이다.
    """
    manager = managers[worker_id]
    is_home_store = manager.get("home_store") == store
    is_global = manager.get("is_global", False)
    home_priority = 0 if is_home_store else 1 if is_global else 2
    weekend_count = work_counts[worker_id]["주말/공휴일"] if is_weekend_or_holiday(work_date, holidays) else 0
    id_priority = id_order.get(worker_id, worker_id) if id_order else worker_id
    consecutive_days = _consecutive_days_before(schedule, work_date, worker_id, managers) if schedule else 0

    return (
        consecutive_days,
        work_counts[worker_id].get(shift, 0),
        home_priority,
        weekend_count,
        work_counts[worker_id]["전체"],
        id_priority,
    )


def get_candidate_managers(
    schedule,
    work_date,
    store,
    shift,
    managers,
    off_requests,
    support_assignments,
    work_counts,
    holidays,
    id_order=None,
):
    """자동 배정 가능한 후보자를 필터링하고 우선순위대로 정렬한다."""
    candidates = []
    for worker_id in managers:
        if can_work(
            schedule,
            work_date,
            store,
            shift,
            worker_id,
            managers,
            off_requests,
            support_assignments,
        ):
            candidates.append(worker_id)

    return sorted(
        candidates,
        key=lambda worker_id: _candidate_sort_key(
            worker_id, store, shift, work_date, managers, work_counts, holidays, id_order
            , schedule=schedule
        ),
    )


def _manager_can_take_slot_from_state(
    worker_id,
    store,
    shift,
    date_str,
    managers,
    off_requests,
    previous_runs,
    previous_shifts,
    previous_stores,
    used_today,
):
    if worker_id in used_today:
        return False
    if date_str in set(off_requests.get(worker_id, [])):
        return False

    manager = managers[worker_id]
    if manager.get("home_store") != store and not manager.get("is_global"):
        return False

    if store == "매장A" and shift == NIGHT_SHIFT:
        if not can_work_konkuk_night(worker_id, managers):
            return False

    if previous_shifts.get(worker_id) == NIGHT_SHIFT and previous_stores.get(worker_id) == "매장A":
        return False

    if shift == OPEN_SHIFT and previous_shifts.get(worker_id) in (CLOSING_SHIFT, NIGHT_SHIFT):
        return False

    if previous_runs.get(worker_id, 0) >= 5:
        return False

    return True


def _fixed_manager_work_for_day(schedule, date_str, managers):
    daily_work = {}
    for store, shift_map in schedule.get(date_str, {}).items():
        for shift, assignment in shift_map.items():
            if assignment and assignment.get("worker_id") in managers:
                daily_work[assignment["worker_id"]] = (store, shift)
    return daily_work


def _day_slots(schedule, date_str, stores, store_order, shift_priority):
    slots = []
    for store, shifts in _assignment_store_order(stores, store_order):
        for shift in _assignment_shift_order(shifts, shift_priority):
            if schedule[date_str][store][shift] is None:
                slots.append((store, shift))
    return slots


def _day_assignment_sort_key(assignments, managers, work_counts, work_date, holidays):
    counts = {worker_id: work_counts[worker_id]["전체"] for worker_id in work_counts}
    weekend_counts = {worker_id: work_counts[worker_id]["주말/공휴일"] for worker_id in work_counts}
    home_miss = 0
    for store, _shift, worker_id in assignments:
        if managers[worker_id].get("home_store") != store:
            home_miss += 1
        counts[worker_id] += 1
        if is_weekend_or_holiday(work_date, holidays):
            weekend_counts[worker_id] += 1

    return (
        max(counts.values()) - min(counts.values()),
        max(weekend_counts.values()) - min(weekend_counts.values()),
        home_miss,
    )


def _generate_day_options(
    schedule,
    date_str,
    work_date,
    slots,
    managers,
    holidays,
    off_requests,
    work_counts,
    previous_runs,
    previous_shifts,
    previous_stores,
    id_order,
    limit,
):
    fixed_daily_work = _fixed_manager_work_for_day(schedule, date_str, managers)
    if len(fixed_daily_work) != len(set(fixed_daily_work)):
        return []

    options = []

    def recurse(remaining_slots, used_today, assignments):
        if len(options) >= limit:
            return
        if not remaining_slots:
            options.append(list(assignments))
            return

        best_index = None
        best_candidates = None
        for index, (store, shift) in enumerate(remaining_slots):
            candidates = [
                worker_id
                for worker_id in managers
                if _manager_can_take_slot_from_state(
                    worker_id,
                    store,
                    shift,
                    date_str,
                    managers,
                    off_requests,
                    previous_runs,
                    previous_shifts,
                    previous_stores,
                    used_today,
                )
            ]
            candidates = sorted(
                candidates,
                key=lambda worker_id: _candidate_sort_key(
                    worker_id, store, shift, work_date, managers, work_counts, holidays, id_order
                ),
            )
            if best_candidates is None or len(candidates) < len(best_candidates):
                best_index = index
                best_candidates = candidates
            if not candidates:
                return

        store, shift = remaining_slots[best_index]
        next_remaining = remaining_slots[:best_index] + remaining_slots[best_index + 1 :]
        for worker_id in best_candidates:
            used_today.add(worker_id)
            assignments.append((store, shift, worker_id))
            recurse(next_remaining, used_today, assignments)
            assignments.pop()
            used_today.remove(worker_id)

    recurse(slots, set(fixed_daily_work), [])
    return sorted(
        options,
        key=lambda assignments: _day_assignment_sort_key(assignments, managers, work_counts, work_date, holidays),
    )


def _beam_state_score(state, managers):
    total_counts = [state["work_counts"][worker_id]["전체"] for worker_id in managers]
    weekend_counts = [state["work_counts"][worker_id]["주말/공휴일"] for worker_id in managers]
    run_risk = sum(max(0, state["runs"][worker_id] - 3) for worker_id in managers)
    return (
        (max(total_counts) - min(total_counts)) * 20
        + (max(weekend_counts) - min(weekend_counts)) * 10
        + run_risk * 5
        + state["home_miss"]
    )


def _apply_day_to_state(state, date_str, work_date, day_assignments, schedule, managers, holidays):
    next_state = {
        "assignments": state["assignments"] + [(date_str, store, shift, worker_id) for store, shift, worker_id in day_assignments],
        "runs": {},
        "previous_shifts": {},
        "previous_stores": {},
        "work_counts": {
            worker_id: dict(counts)
            for worker_id, counts in state["work_counts"].items()
        },
        "home_miss": state["home_miss"],
    }

    daily_work = _fixed_manager_work_for_day(schedule, date_str, managers)
    for store, shift, worker_id in day_assignments:
        daily_work[worker_id] = (store, shift)
        add_work_count(next_state["work_counts"], worker_id, shift, work_date, holidays)
        if managers[worker_id].get("home_store") != store:
            next_state["home_miss"] += 1

    for worker_id in managers:
        if worker_id in daily_work:
            store, shift = daily_work[worker_id]
            next_state["runs"][worker_id] = state["runs"].get(worker_id, 0) + 1
            next_state["previous_shifts"][worker_id] = shift
            next_state["previous_stores"][worker_id] = store
        else:
            next_state["runs"][worker_id] = 0
            next_state["previous_shifts"][worker_id] = None
            next_state["previous_stores"][worker_id] = None

    return next_state


def _generate_schedule_beam(
    year,
    month,
    stores,
    managers,
    holidays,
    off_requests,
    stl_fixed,
    fixed_assignments,
    support_assignments,
    strategy,
):
    schedule = _initialize_schedule(year, month, stores)
    notes = []
    notes.extend(apply_stl_fixed(schedule, stl_fixed, stores))
    notes.extend(apply_support_assignments(schedule, support_assignments, stores))
    notes.extend(apply_fixed_assignments(schedule, fixed_assignments, stores))

    initial_state = {
        "assignments": [],
        "runs": {worker_id: 0 for worker_id in managers},
        "previous_shifts": {worker_id: None for worker_id in managers},
        "previous_stores": {worker_id: None for worker_id in managers},
        "work_counts": _recalculate_work_counts(schedule, managers, holidays),
        "home_miss": 0,
    }

    beam = [initial_state]
    beam_width = strategy.get("beam_width", 1200)
    day_option_limit = strategy.get("day_option_limit", 1500)
    store_order = strategy.get("store_order")
    shift_priority = strategy.get("shift_priority")
    id_order = strategy.get("id_order")

    for work_date in get_month_dates(year, month):
        date_str = date_to_str(work_date)
        slots = _day_slots(schedule, date_str, stores, store_order, shift_priority)
        if not slots:
            beam = [
                _apply_day_to_state(state, date_str, work_date, [], schedule, managers, holidays)
                for state in beam
            ]
            continue

        next_beam = []
        for state in beam:
            options = _generate_day_options(
                schedule,
                date_str,
                work_date,
                slots,
                managers,
                holidays,
                off_requests,
                state["work_counts"],
                state["runs"],
                state["previous_shifts"],
                state["previous_stores"],
                id_order,
                day_option_limit,
            )
            for assignments in options:
                next_beam.append(
                    _apply_day_to_state(state, date_str, work_date, assignments, schedule, managers, holidays)
                )

        if not next_beam:
            notes.append(f"{date_str}: 엄격 규칙으로 미배정 0건 후보를 찾지 못해 greedy 배정으로 전환")
            return None, None, notes

        next_beam.sort(key=lambda state: _beam_state_score(state, managers))
        beam = next_beam[:beam_width]

    best_state = min(beam, key=lambda state: _beam_state_score(state, managers))
    for date_str, store, shift, worker_id in best_state["assignments"]:
        schedule[date_str][store][shift] = make_assignment(worker_id, AUTO, "")

    return schedule, _recalculate_work_counts(schedule, managers, holidays), notes


def _generate_schedule_greedy(
    year,
    month,
    stores,
    managers,
    holidays,
    off_requests,
    stl_fixed,
    fixed_assignments,
    support_assignments,
    strategy=None,
):
    """한 달치 스케줄을 greedy 방식으로 생성한다.

    처리 순서:
    1. 빈 스케줄 생성
    2. STL 고정 배정 반영
    3. 예외 고정 배정 반영
    4. 남은 칸을 날짜/매장/시프트 순으로 자동 배정

    strategy를 넘기면 매장 처리 순서, 시프트 처리 순서, 동률 후보 ID 순서를 바꿔
    서로 다른 후보 스케줄을 만들 수 있다. 전수 탐색은 아니지만 실제 운영에서 비교 가능한
    여러 경우의 수를 빠르게 만들어 선택하는 용도다.
    """
    strategy = strategy or {}
    schedule = _initialize_schedule(year, month, stores)
    notes = []
    notes.extend(apply_stl_fixed(schedule, stl_fixed, stores))
    notes.extend(apply_support_assignments(schedule, support_assignments, stores))
    notes.extend(apply_fixed_assignments(schedule, fixed_assignments, stores))

    work_counts = _recalculate_work_counts(schedule, managers, holidays)
    store_order = strategy.get("store_order")
    shift_priority = strategy.get("shift_priority")
    id_order = strategy.get("id_order")
    candidate_offset = strategy.get("candidate_offset", 0)

    for work_date in get_month_dates(year, month):
        date_str = date_to_str(work_date)
        for store, shifts in _assignment_store_order(stores, store_order):
            for shift in _assignment_shift_order(shifts, shift_priority):
                if schedule[date_str][store][shift] is not None:
                    continue

                candidates = get_candidate_managers(
                    schedule,
                    work_date,
                    store,
                    shift,
                    managers,
                    off_requests,
                    support_assignments,
                    work_counts,
                    holidays,
                    id_order=id_order,
                )

                if not candidates:
                    schedule[date_str][store][shift] = make_assignment("미배정", UNASSIGNED, "배정 가능한 후보 없음")
                    continue

                selected = candidates[candidate_offset % len(candidates)]
                schedule[date_str][store][shift] = make_assignment(selected, AUTO, "")
                add_work_count(work_counts, selected, shift, work_date, holidays)

    if strategy.get("relaxed_fill", True):
        notes.extend(fill_unassigned_relaxed(schedule, managers, holidays, off_requests))

    work_counts = _recalculate_work_counts(schedule, managers, holidays)
    return schedule, work_counts, notes


def generate_schedule(
    year,
    month,
    stores,
    managers,
    holidays,
    off_requests,
    stl_fixed,
    fixed_assignments,
    support_assignments,
    strategy=None,
):
    strategy = strategy or {}
    if strategy.get("engine") != "beam":
        return _generate_schedule_greedy(
            year,
            month,
            stores,
            managers,
            holidays,
            off_requests,
            stl_fixed,
            fixed_assignments,
            support_assignments,
            strategy,
        )

    schedule, work_counts, notes = _generate_schedule_beam(
        year,
        month,
        stores,
        managers,
        holidays,
        off_requests,
        stl_fixed,
        fixed_assignments,
        support_assignments,
        strategy,
    )
    if schedule is not None:
        return schedule, work_counts, notes

    fallback_schedule, fallback_counts, fallback_notes = _generate_schedule_greedy(
        year,
        month,
        stores,
        managers,
        holidays,
        off_requests,
        stl_fixed,
        fixed_assignments,
        support_assignments,
        strategy,
    )
    return fallback_schedule, fallback_counts, notes + fallback_notes
