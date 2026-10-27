# -*- coding: utf-8 -*-
"""스케줄 생성에 공통으로 쓰는 상수와 데이터 생성 헬퍼."""

AUTO = "AUTO"
FIXED = "FIXED"
STL = "STL"
SUPPORT = "SUPPORT"
UNASSIGNED = "UNASSIGNED"

MAX_CONSECUTIVE_DAYS = 5
MAX_CONSECUTIVE_NIGHTS = 3

OPEN_SHIFT = "오픈"
CLOSING_SHIFT = "마감"
DAILY_SHIFT = "데일리"
NIGHT_SHIFT = "나이트"

ALL_STAT_SHIFTS = [OPEN_SHIFT, CLOSING_SHIFT, DAILY_SHIFT, NIGHT_SHIFT]


def make_assignment(worker_id, assignment_type, reason=""):
    """한 칸에 들어갈 배정 정보를 동일한 형태로 만든다."""
    return {
        "worker_id": worker_id,
        "type": assignment_type,
        "reason": reason or "",
    }
