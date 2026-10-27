# -*- coding: utf-8 -*-
"""사용자가 수정하는 입력값 모음.

첫 버전은 별도 UI 없이 이 파일의 딕셔너리/리스트를 수정해서 사용한다.
나중에 CSV 또는 Excel 입력을 붙일 때도 나머지 로직은 최대한 그대로 두기 위해
입력값을 이 파일에 모아둔다.
"""

YEAR = 2026
MONTH = 5

OUTPUT_FILE = f"manager_schedule_{YEAR}_{MONTH:02d}.xlsx"

# 여러 경우의 수를 비교하기 위해 생성할 후보 스케줄 개수.
# 숫자를 키우면 더 다양한 후보를 보지만 실행 시간이 늘어난다.
SCHEDULE_OPTION_COUNT = 30

# None이면 점수가 가장 좋은 후보를 자동 선택한다.
# 콘솔 또는 Excel의 "후보요약" 시트를 보고 특정 후보를 쓰고 싶으면 숫자로 지정한다.
# 예: SELECTED_OPTION_INDEX = 9
SELECTED_OPTION_INDEX = None

# 직접 입력하는 공휴일 목록.
HOLIDAYS = [
    "2026-05-01",
    "2026-05-05",
    "2026-05-24",
    "2026-05-25"
]

# 매장별 시프트.
STORES = {
    "매장A": ["오픈", "데일리", "나이트"],
    "매장B": ["오픈", "마감"],
    "매장C": ["오픈", "마감"],
}

# 매니저 정보.
# B, C는 매장마다 다른 사람이므로 내부 ID를 건대_B, 스타_B, 군자_B처럼 구분한다.
# 모든 매니저는 3개 매장 공통 근무 가능 인원이지만, 후보 정렬에서는 소속 매장 인원을 우선한다.
MANAGERS = {
    "A": {
        "name": "예시 매니저 1",
        "home_store": "전체",
        "is_global": True,
    },
    "건대_B": {
        "name": "예시 매니저 2",
        "home_store": "매장A",
        "is_global": True,
    },
    "건대_C": {
        "name": "예시 매니저 3",
        "home_store": "매장A",
        "is_global": True,
    },
    "건대_D": {
        "name": "예시 매니저 4",
        "home_store": "매장A",
        "is_global": True,
    },
    "스타_B": {
        "name": "예시 매니저 5",
        "home_store": "매장B",
        "is_global": True,
    },
    "스타_C": {
        "name": "예시 매니저 6",
        "home_store": "매장B",
        "is_global": True,
    },
    "군자_B": {
        "name": "예시 매니저 7",
        "home_store": "매장C",
        "is_global": True,
    },
    "군자_C": {
        "name": "예시 매니저 8",
        "home_store": "매장C",
        "is_global": True,
    },
}

# 휴무/연차/교육 일정.
# 해당 날짜에는 어떤 매장/시프트에도 자동 배정하지 않는다.
OFF_REQUESTS = {}

# STL 고정 근무.
# STL은 매니저 통계에 포함하지 않으며, STL이 들어간 시프트는 매니저 배정이 필요 없는 것으로 처리한다.
# 입력 항목은 date, store, shift만 사용한다.
STL_FIXED = []

# 특정 날짜/매장/시프트에 특정 매니저 또는 점장을 강제로 배정한다.
# 고정 배정은 규칙 위반이 있더라도 우선 반영하고, 위반 내역은 검증 결과에 출력한다.
FIXED_ASSIGNMENTS = []

# 외부 매장 지원 근무.
# 현재 관리하는 3개 매장 소속 매니저가 아니라, 외부 매장에서 지원받는 인원이다.
# 입력한 날짜/매장/시프트 칸은 외부 지원으로 채워지고 매니저 자동 배정 대상에서 제외된다.
# 입력 항목은 date, store, shift만 사용한다.
SUPPORT_ASSIGNMENTS = []
