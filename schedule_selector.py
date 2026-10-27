# -*- coding: utf-8 -*-
"""여러 후보 스케줄을 생성하고 점수화해서 최종안을 선택한다."""

from itertools import permutations

from schedule_engine import generate_schedule
from schedule_models import NIGHT_SHIFT
from schedule_validation import validate_schedule


def _issue_counts(issues):
    """검증 메시지를 종류별 개수로 요약한다."""
    unassigned = sum(1 for issue in issues if "미배정" in issue)
    hard_violations = len(issues) - unassigned
    return unassigned, hard_violations


def _imbalance_score(work_counts, managers=None):
    """전체/주말/시프트별 근무 수의 쏠림 정도를 계산한다."""
    total_counts = [item["전체"] for item in work_counts.values()]
    weekend_counts = [item["주말/공휴일"] for item in work_counts.values()]
    if not total_counts:
        return 0

    shift_imbalance = 0
    for shift in ("오픈", "마감", "데일리", NIGHT_SHIFT):
        if shift == NIGHT_SHIFT and managers:
            shift_counts = [
                work_counts[worker_id][shift]
                for worker_id, manager in managers.items()
                if worker_id == "A" or manager.get("home_store") == "매장A"
            ]
        else:
            shift_counts = [item[shift] for item in work_counts.values()]
        if shift_counts:
            shift_imbalance += max(shift_counts) - min(shift_counts)

    return (
        (max(total_counts) - min(total_counts))
        + (max(weekend_counts) - min(weekend_counts))
        + (shift_imbalance * 3)
    )


def score_schedule(validation_issues, work_counts, managers=None):
    """낮을수록 좋은 점수.

    우선순위는 미배정 최소화, 규칙 위반 최소화, 근무/시프트 쏠림 최소화 순서다.
    고정 배정 때문에 생기는 위반은 막지 않고 점수에서 크게 불리하게만 처리한다.
    """
    unassigned, hard_violations = _issue_counts(validation_issues)
    imbalance = _imbalance_score(work_counts, managers)
    return (unassigned * 10000) + (hard_violations * 1000) + imbalance


def _rotated_id_order(manager_ids, offset):
    """동률 후보 ID 정렬 순서를 회전시켜 다른 후보안을 만든다."""
    rotated = manager_ids[offset:] + manager_ids[:offset]
    return {manager_id: index for index, manager_id in enumerate(rotated)}


def build_candidate_strategies(stores, managers, max_candidates):
    """여러 후보 생성을 위한 전략 목록을 만든다.

    전수 탐색은 현실적으로 너무 크기 때문에, 매장 순서/시프트 순서/동률 후보 순서를
    조금씩 바꿔 운영자가 비교할 만한 후보 스케줄을 만든다.
    """
    store_names = list(stores)
    manager_ids = list(managers)

    shift_profiles = [
        {"나이트": 0, "오픈": 1, "데일리": 2, "마감": 3},
        {"오픈": 0, "나이트": 1, "데일리": 2, "마감": 3},
        {"나이트": 0, "마감": 1, "오픈": 2, "데일리": 3},
    ]

    store_orders = list(permutations(store_names))
    strategies = []
    for store_order in store_orders:
        for shift_priority in shift_profiles:
            for offset in range(len(manager_ids)):
                strategies.append(
                    {
                        "name": f"stores={','.join(store_order)};profile={len(strategies) % len(shift_profiles)};offset={offset}",
                        "store_order": list(store_order),
                        "shift_priority": shift_priority,
                        "id_order": _rotated_id_order(manager_ids, offset),
                        "candidate_offset": 0,
                    }
                )
                if len(strategies) >= max_candidates:
                    return strategies
    return strategies


def generate_schedule_options(
    year,
    month,
    stores,
    managers,
    holidays,
    off_requests,
    stl_fixed,
    fixed_assignments,
    support_assignments,
    max_candidates=30,
):
    """후보 스케줄 여러 개를 만들고 점수순으로 반환한다."""
    options = []
    strategies = build_candidate_strategies(stores, managers, max_candidates)

    for index, strategy in enumerate(strategies, start=1):
        schedule, work_counts, notes = generate_schedule(
            year,
            month,
            stores,
            managers,
            holidays,
            off_requests,
            stl_fixed,
            fixed_assignments,
            support_assignments,
            strategy=strategy,
        )
        issues = validate_schedule(schedule, year, month, stores, managers, off_requests)
        unassigned, hard_violations = _issue_counts(issues)
        options.append(
            {
                "index": index,
                "strategy": strategy,
                "schedule": schedule,
                "work_counts": work_counts,
                "notes": notes,
                "validation_issues": issues,
                "score": score_schedule(issues, work_counts, managers),
                "unassigned_count": unassigned,
                "violation_count": hard_violations,
                "imbalance_score": _imbalance_score(work_counts, managers),
            }
        )

    return sorted(options, key=lambda item: (item["score"], item["unassigned_count"], item["imbalance_score"]))


def select_best_schedule_option(options, selected_option_index=None):
    """최종 후보를 선택한다.

    selected_option_index가 None이면 점수가 가장 낮은 후보를 자동 선택한다.
    숫자가 들어오면 해당 후보 번호를 우선 선택한다.
    """
    if not options:
        raise ValueError("생성된 후보 스케줄이 없습니다.")

    if selected_option_index is not None:
        for option in options:
            if option["index"] == selected_option_index:
                return option
        raise ValueError(f"{selected_option_index}번 후보를 찾을 수 없습니다.")

    return options[0]
