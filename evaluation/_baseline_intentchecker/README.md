# IntentChecker 기준선 스냅샷 (2026-10-21) — 읽기 전용, 수정 금지

(b) 재구성(원본 기반 자동 contraction + 프로젝트 단위 pkl + 어노테이션 재배치)으로 케이스가 바뀐 뒤,
**기존 것과 무엇이 왜 달라졌는지 비교**하기 위한 기준선이다.

| 경로 | 내용 | 출처 |
|---|---|---|
| `evaluation/RQ1/cases/` | IntentChecker 수동 케이스 레코드 JSON (48 + 메타·중복 초안) | git HEAD `4f27c15` (= Guardian 사본, 2026-10-21 데이터 수정 **이전**) |
| `evaluation/Dataset/target_contraction/` | IntentChecker 수동 contraction (.sol 16 + 레코드 .json) | git HEAD `4f27c15` |
| `results_before.json` | 위 케이스를 현재 엔진으로 돌린 판정 — 2026-10-20 코어 수정(⊤ 기본값) **이전** | `run_cases.py --tag before` |
| `results_after.json` | 같은 케이스 — ⊤ 기본값 수정 **이후**, 정상 종료 합치기·리터럴·폴백 수정 **이전** | `run_cases.py --tag after` |

비교 축(재구성 후 작성 예정): 소스 차이(수동 평탄화 vs 원본 상속), 남긴 함수 집합, 어노테이션 위치 대응, 판정 변화와 원인.
