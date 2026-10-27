# -*- coding: utf-8 -*-
"""3개 매장 매니저 월간 근무 스케줄 자동 생성기 실행 파일."""

from schedule_config import (
    FIXED_ASSIGNMENTS,
    HOLIDAYS,
    MANAGERS,
    MONTH,
    OFF_REQUESTS,
    OUTPUT_FILE,
    SCHEDULE_OPTION_COUNT,
    SELECTED_OPTION_INDEX,
    STORES,
    STL_FIXED,
    SUPPORT_ASSIGNMENTS,
    YEAR,
)
from schedule_excel import create_excel
from schedule_selector import generate_schedule_options, select_best_schedule_option
from schedule_validation import validate_schedule


def _print_option_summary(options, limit=10):
    """콘솔에 후보 스케줄 요약을 출력한다."""
    print("\n[후보 스케줄 요약]")
    print("순위 | 후보 | 점수 | 미배정 | 규칙위반 | 쏠림")
    for rank, option in enumerate(options[:limit], start=1):
        print(
            f"{rank:>2} | "
            f"{option['index']:>3} | "
            f"{option['score']:>6} | "
            f"{option['unassigned_count']:>3} | "
            f"{option['violation_count']:>4} | "
            f"{option['imbalance_score']:>3}"
        )


def main():
    options = generate_schedule_options(
        YEAR,
        MONTH,
        STORES,
        MANAGERS,
        HOLIDAYS,
        OFF_REQUESTS,
        STL_FIXED,
        FIXED_ASSIGNMENTS,
        SUPPORT_ASSIGNMENTS,
        max_candidates=SCHEDULE_OPTION_COUNT,
    )
    selected = select_best_schedule_option(options, SELECTED_OPTION_INDEX)

    schedule = selected["schedule"]
    work_counts = selected["work_counts"]
    notes = list(selected["notes"])
    notes.append(
        "선택된 후보: "
        f"{selected['index']}번, 점수 {selected['score']}, "
        f"미배정 {selected['unassigned_count']}건, "
        f"규칙위반 {selected['violation_count']}건, "
        f"쏠림 {selected['imbalance_score']}"
    )

    validation_issues = selected["validation_issues"]

    create_excel(
        schedule,
        work_counts,
        validation_issues,
        notes,
        YEAR,
        MONTH,
        STORES,
        MANAGERS,
        HOLIDAYS,
        OUTPUT_FILE,
        schedule_options=options,
        selected_option_index=selected["index"],
    )

    excel_check = validate_schedule(
        schedule,
        YEAR,
        MONTH,
        STORES,
        MANAGERS,
        OFF_REQUESTS,
        output_file=OUTPUT_FILE,
    )

    print("=" * 60)
    print(f"스케줄 생성 완료: {OUTPUT_FILE}")
    print("=" * 60)
    print(f"생성 후보 수: {len(options)}")
    print(
        "최종 선택: "
        f"{selected['index']}번 후보 "
        f"(점수 {selected['score']}, 미배정 {selected['unassigned_count']}건, "
        f"규칙위반 {selected['violation_count']}건, 쏠림 {selected['imbalance_score']})"
    )
    _print_option_summary(options)

    if notes:
        print("\n[예외/입력 처리]")
        for note in notes:
            print(f"- {note}")

    print("\n[검증 결과]")
    for issue in excel_check:
        print(f"- {issue}")


if __name__ == "__main__":
    main()
