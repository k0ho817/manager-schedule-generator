# 매니저 근무표 자동 생성기

여러 매장의 월간 시프트를 대상으로 후보 근무표를 만들고, 규칙 위반·미배정·근무 편중을 평가한 뒤 Excel 파일로 내보내는 Python 도구입니다.

## 구성

- `schedule_config.py`: 월, 매장, 매니저, 휴무, 고정 배정 등 입력 예시
- `schedule_engine.py`, `schedule_rules.py`: 후보 생성 및 근무 가능 규칙
- `schedule_selector.py`: 후보 점수화와 최종 선택
- `schedule_validation.py`: 생성 결과 검증
- `schedule_excel.py`: Excel 출력
- `manager_schedule_generator.py`: 실행 진입점

## 실행

Python 3과 `openpyxl`을 설치한 뒤 `schedule_config.py`의 예시 입력을 자신의 조건에 맞게 바꾸고 `python manager_schedule_generator.py`를 실행합니다. 출력 경로는 `OUTPUT_FILE`에서 설정합니다. 생성 후 콘솔의 미배정·규칙 위반 보고와 Excel 내용을 함께 확인하세요.

## 데이터 범위

게시본에는 실제 근무표 파일을 넣지 않았고, 직원 표시 이름은 예시 값으로 바꿨습니다. 매장 이름과 직원 이름은 예시 값입니다. 원래 사용 사례의 일부 규칙이 남아 있으므로, 다른 운영 환경에 적용할 때는 `schedule_rules.py`와 설정을 같이 수정해야 합니다. 자동 생성 결과는 최종 관리자 검토를 대신하지 않습니다.
