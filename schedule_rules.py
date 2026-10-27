# -*- coding: utf-8 -*-
"""매니저 근무 가능 여부를 판단하는 규칙 모음."""

from datetime import timedelta

from schedule_models import (
    FIXED,
    NIGHT_SHIFT,
    OPEN_SHIFT,
    CLOSING_SHIFT,
    MAX_CONSECUTIVE_DAYS,
    MAX_CONSECUTIVE_NIGHTS,
)
from schedule_utils import date_to_str


def _iter_assignments_for_date(schedule, date_str):
    """특정 날짜의 모든 배정을 순회한다."""
    for store, shifts in schedule.get(date_str, {}).items():
        for shift, assignment in shifts.items():
            if assignment:
                yield store, shift, assignment


def _is_manager_assignment(assignment, managers):
    """STL/미배정을 제외한 매니저 배정인지 확인한다."""
    return bool(assignment and assignment.get("worker_id") in managers)


def already_working_that_day(schedule, work_date, worker_id, managers):
    """매니저는 매장과 무관하게 하루에 하나의 스케줄만 들어갈 수 있다."""
    date_str = date_to_str(work_date)
    for _store, _shift, assignment in _iter_assignments_for_date(schedule, date_str):
        if _is_manager_assignment(assignment, managers) and assignment["worker_id"] == worker_id:
            return True
    return False


def worked_shift_yesterday(schedule, work_date, worker_id, shift_name, managers):
    """전날 특정 시프트를 근무했는지 확인한다."""
    yesterday_str = date_to_str(work_date - timedelta(days=1))
    for _store, shift, assignment in _iter_assignments_for_date(schedule, yesterday_str):
        if (
            _is_manager_assignment(assignment, managers)
            and assignment["worker_id"] == worker_id
            and shift == shift_name
        ):
            return True
    return False


def worked_closing_or_night_yesterday(schedule, work_date, worker_id, managers):
    """마감 또는 나이트 근무 다음날 오픈 근무를 금지하기 위한 검사."""
    yesterday_str = date_to_str(work_date - timedelta(days=1))
    for _store, shift, assignment in _iter_assignments_for_date(schedule, yesterday_str):
        if (
            _is_manager_assignment(assignment, managers)
            and assignment["worker_id"] == worker_id
            and shift in (CLOSING_SHIFT, NIGHT_SHIFT)
        ):
            return True
    return False


def _worked_konkuk_night_yesterday(schedule, work_date, worker_id, managers):
    """매장A 나이트 근무자는 다음날 무조건 휴무 처리한다."""
    yesterday_str = date_to_str(work_date - timedelta(days=1))
    assignment = schedule.get(yesterday_str, {}).get("매장A", {}).get(NIGHT_SHIFT)
    return (
        _is_manager_assignment(assignment, managers)
        and assignment["worker_id"] == worker_id
    )


def is_support_assignment(manager_id, store, work_date, shift, support_assignments):
    """외부 지원은 별도 고정 배정으로 처리하므로 내부 매니저 지원은 허용하지 않는다."""
    return False


def _has_manager_work(schedule, work_date, worker_id, managers):
    """특정 날짜에 해당 매니저 근무가 하나라도 있는지 확인한다."""
    date_str = date_to_str(work_date)
    for _store, _shift, assignment in _iter_assignments_for_date(schedule, date_str):
        if _is_manager_assignment(assignment, managers) and assignment["worker_id"] == worker_id:
            return True
    return False


def would_exceed_consecutive_days(schedule, work_date, worker_id, managers):
    """오늘 배정했을 때 최대 연속근무 5일을 초과하는지 확인한다.

    자동 배정 로직에서 오늘을 아직 schedule에 넣기 전에 호출되므로,
    오늘 하루를 근무로 가정하고 앞뒤 연속근무를 함께 센다.
    """
    count = 1

    cursor = work_date - timedelta(days=1)
    while _has_manager_work(schedule, cursor, worker_id, managers):
        count += 1
        cursor -= timedelta(days=1)

    cursor = work_date + timedelta(days=1)
    while _has_manager_work(schedule, cursor, worker_id, managers):
        count += 1
        cursor += timedelta(days=1)

    return count > MAX_CONSECUTIVE_DAYS


def count_consecutive_nights_before(schedule, work_date, worker_id, managers):
    """해당 날짜 직전까지 이어진 매장A 나이트 연속 횟수를 센다."""
    count = 0
    cursor = work_date - timedelta(days=1)
    while True:
        date_str = date_to_str(cursor)
        assignment = schedule.get(date_str, {}).get("매장A", {}).get(NIGHT_SHIFT)
        if _is_manager_assignment(assignment, managers) and assignment["worker_id"] == worker_id:
            count += 1
            cursor -= timedelta(days=1)
        else:
            break
    return count


def would_exceed_consecutive_nights(schedule, work_date, worker_id, shift, managers):
    """오늘 나이트 배정 시 연속 나이트 3회를 초과하는지 확인한다."""
    if shift != NIGHT_SHIFT:
        return False
    return count_consecutive_nights_before(schedule, work_date, worker_id, managers) + 1 > MAX_CONSECUTIVE_NIGHTS


def can_work_konkuk_night(worker_id, managers):
    """매장A 나이트 가능 여부. 매장A 소속 매니저와 A는 가능하다."""
    manager = managers[worker_id]
    return worker_id == "A" or manager.get("home_store") == "매장A"


def _belongs_to_store_or_allowed_support(worker_id, store, work_date, shift, managers, support_assignments):
    """소속 매장 또는 A 공통 인원인지 확인한다."""
    manager = managers[worker_id]
    if manager.get("home_store") == store:
        return True
    if manager.get("is_global"):
        return True
    return False


def can_work(
    schedule,
    work_date,
    store,
    shift,
    worker_id,
    managers,
    off_requests,
    support_assignments,
):
    """자동 배정에서 해당 매니저를 배정할 수 있는지 판단한다.

    고정 배정은 규칙 위반이 있어도 우선 반영해야 하므로 이 함수로 막지 않고,
    자동 배정 후보 필터링과 사후 검증에서 같은 규칙을 활용한다.
    """
    if worker_id not in managers:
        return False

    date_str = date_to_str(work_date)

    # 휴무/연차/교육 처리: 해당 날짜에는 어떤 매장/시프트에도 배정하지 않는다.
    if date_str in set(off_requests.get(worker_id, [])):
        return False

    # 하루 1근무 처리: 이미 다른 매장이나 다른 시프트에 배정되었다면 제외한다.
    if already_working_that_day(schedule, work_date, worker_id, managers):
        return False

    # 매장 처리: 소속 매장 또는 A가 아니면 자동 배정 후보에서 제외한다.
    # 외부 지원은 SUPPORT_ASSIGNMENTS로 해당 칸을 먼저 채우기 때문에 여기서 후보로 보지 않는다.
    if not _belongs_to_store_or_allowed_support(
        worker_id, store, work_date, shift, managers, support_assignments
    ):
        return False

    # 매장A 나이트는 매장A 소속 매니저와 A만 가능하다.
    if store == "매장A" and shift == NIGHT_SHIFT:
        if not can_work_konkuk_night(worker_id, managers):
            return False

    # 매장A 나이트 다음날 휴무 처리.
    if _worked_konkuk_night_yesterday(schedule, work_date, worker_id, managers):
        return False

    # 마감/나이트 다음날 오픈 금지 처리.
    if shift == OPEN_SHIFT and worked_closing_or_night_yesterday(schedule, work_date, worker_id, managers):
        return False

    # 연속근무 제한 처리.
    if would_exceed_consecutive_days(schedule, work_date, worker_id, managers):
        return False

    # 연속 나이트 제한 처리.
    if would_exceed_consecutive_nights(schedule, work_date, worker_id, shift, managers):
        return False

    return True


def is_forced_assignment(assignment):
    """검증 메시지에서 고정 배정인지 표시하기 위한 작은 헬퍼."""
    return bool(assignment and assignment.get("type") == FIXED)
