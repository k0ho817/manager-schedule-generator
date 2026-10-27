# -*- coding: utf-8 -*-
"""생성된 스케줄의 규칙 위반과 미배정 여부를 검증한다."""

import os
from collections import defaultdict
from datetime import date, timedelta

from schedule_models import CLOSING_SHIFT, NIGHT_SHIFT, OPEN_SHIFT, UNASSIGNED
from schedule_rules import can_work_konkuk_night
from schedule_utils import date_to_str, get_month_dates


def _date_from_str(date_str):
    year, month, day = map(int, date_str.split("-"))
    return date(year, month, day)


def _manager_assignments_by_day(schedule, managers):
    by_day = defaultdict(list)
    for date_str, stores in schedule.items():
        for store, shifts in stores.items():
            for shift, assignment in shifts.items():
                if assignment and assignment.get("worker_id") in managers:
                    by_day[(date_str, assignment["worker_id"])].append((store, shift, assignment))
    return by_day


def _has_manager_work(schedule, date_str, worker_id, managers):
    for shifts in schedule.get(date_str, {}).values():
        for assignment in shifts.values():
            if assignment and assignment.get("worker_id") == worker_id and worker_id in managers:
                return True
    return False


def _worked_shift(schedule, date_str, worker_id, shift_names, managers):
    for shifts in schedule.get(date_str, {}).values():
        for shift, assignment in shifts.items():
            if (
                assignment
                and assignment.get("worker_id") == worker_id
                and worker_id in managers
                and shift in shift_names
            ):
                return True
    return False


def validate_schedule(schedule, year, month, stores, managers, off_requests, output_file=None):
    """스케줄의 규칙 위반과 미배정 내역을 문자열 리스트로 반환한다."""
    issues = []
    by_day = _manager_assignments_by_day(schedule, managers)

    # 같은 매니저 하루 2회 이상 배정 검사.
    for (date_str, worker_id), assignments in sorted(by_day.items()):
        if len(assignments) >= 2:
            detail = ", ".join(f"{store}/{shift}" for store, shift, _assignment in assignments)
            issues.append(f"{date_str} {worker_id}: 하루 2회 이상 배정됨 ({detail})")

    # 휴무/연차/교육일 배정 검사.
    for worker_id, off_dates in off_requests.items():
        for date_str in off_dates:
            if _has_manager_work(schedule, date_str, worker_id, managers):
                issues.append(f"{date_str} {worker_id}: 휴무/연차/교육일에 배정됨")

    # 미배정 및 매장A 나이트 소속 제한 검사.
    for date_str, store_map in schedule.items():
        for store, shift_map in store_map.items():
            for shift, assignment in shift_map.items():
                if not assignment:
                    issues.append(f"{date_str} {store} {shift}: 미배정")
                    continue
                if assignment.get("type") == UNASSIGNED or assignment.get("worker_id") == "미배정":
                    issues.append(f"{date_str} {store} {shift}: 미배정")
                    continue

                worker_id = assignment.get("worker_id")
                if store == "매장A" and shift == NIGHT_SHIFT and worker_id in managers:
                    if not can_work_konkuk_night(worker_id, managers):
                        issues.append(f"{date_str} 매장A 나이트: 매장A 나이트 불가 인원 {worker_id} 배정됨")

    # 매장A 나이트 다음날 휴무, 마감/나이트 다음날 오픈 검사.
    for work_date in get_month_dates(year, month):
        date_str = date_to_str(work_date)
        next_str = date_to_str(work_date + timedelta(days=1))

        night_assignment = schedule.get(date_str, {}).get("매장A", {}).get(NIGHT_SHIFT)
        if night_assignment and night_assignment.get("worker_id") in managers:
            worker_id = night_assignment["worker_id"]
            if _has_manager_work(schedule, next_str, worker_id, managers):
                issues.append(f"{next_str} {worker_id}: 매장A 나이트 다음날 휴무 위반")

        for worker_id in managers:
            if _worked_shift(schedule, date_str, worker_id, {CLOSING_SHIFT, NIGHT_SHIFT}, managers):
                if _worked_shift(schedule, next_str, worker_id, {OPEN_SHIFT}, managers):
                    issues.append(f"{next_str} {worker_id}: 마감/나이트 다음날 오픈 근무 위반")

    # 연속근무 5일 초과 검사.
    for worker_id in managers:
        current_run = []
        for work_date in get_month_dates(year, month):
            date_str = date_to_str(work_date)
            if _has_manager_work(schedule, date_str, worker_id, managers):
                current_run.append(date_str)
            else:
                if len(current_run) > 5:
                    issues.append(f"{current_run[0]}~{current_run[-1]} {worker_id}: 연속근무 {len(current_run)}일")
                current_run = []
        if len(current_run) > 5:
            issues.append(f"{current_run[0]}~{current_run[-1]} {worker_id}: 연속근무 {len(current_run)}일")

    # 연속 나이트 3회 초과 검사.
    for worker_id in managers:
        current_run = []
        for work_date in get_month_dates(year, month):
            date_str = date_to_str(work_date)
            assignment = schedule.get(date_str, {}).get("매장A", {}).get(NIGHT_SHIFT)
            if assignment and assignment.get("worker_id") == worker_id:
                current_run.append(date_str)
            else:
                if len(current_run) > 3:
                    issues.append(f"{current_run[0]}~{current_run[-1]} {worker_id}: 연속 나이트 {len(current_run)}회")
                current_run = []
        if len(current_run) > 3:
            issues.append(f"{current_run[0]}~{current_run[-1]} {worker_id}: 연속 나이트 {len(current_run)}회")

    # Excel 파일 생성 확인.
    if output_file is not None:
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            issues.append(f"Excel 파일 생성 확인: {output_file}")
        else:
            issues.append(f"Excel 파일 생성 실패 또는 파일 크기 0: {output_file}")

    return issues
