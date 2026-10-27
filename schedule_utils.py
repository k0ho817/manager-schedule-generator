# -*- coding: utf-8 -*-
"""날짜와 표시 관련 유틸리티 함수."""

import calendar
from datetime import date


def get_month_dates(year, month):
    """지정한 연월의 모든 날짜를 date 객체 리스트로 반환한다."""
    last_day = calendar.monthrange(year, month)[1]
    return [date(year, month, day) for day in range(1, last_day + 1)]


def date_to_str(work_date):
    """date 객체를 YYYY-MM-DD 문자열로 변환한다."""
    return work_date.strftime("%Y-%m-%d")


def weekday_kr(work_date):
    """date 객체의 요일을 한국어 한 글자로 반환한다."""
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    return weekdays[work_date.weekday()]


def is_weekend_or_holiday(work_date, holidays):
    """토요일/일요일 또는 사용자가 입력한 공휴일인지 확인한다."""
    return work_date.weekday() >= 5 or date_to_str(work_date) in set(holidays)


def manager_display_name(worker_id, managers):
    """Excel에 표시할 이름을 반환한다.

    같은 이름의 B, C가 매장마다 존재하므로 ID를 함께 보여줘 혼동을 줄인다.
    """
    if not worker_id:
        return ""
    if worker_id == "미배정":
        return "미배정"
    if worker_id.startswith("STL"):
        return worker_id
    manager = managers.get(worker_id)
    if not manager:
        return worker_id
    if worker_id == "A":
        return "A"
    return f"{manager['name']}({worker_id})"
