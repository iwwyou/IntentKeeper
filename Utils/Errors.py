"""분석 오류 분류 (2026-10-22, 사용자 결정 — 증분 편집 트랜잭션).

SourceError = **사용자 소스가 언어 규칙을 어긴다는 확실한 근거가 있는** 오류(예: 어디에도 선언되지 않은 타입).
  편집 중에는 흔히 생기므로 세션을 망가뜨리지 않는다 — 그 업데이트만 반영하지 않고 진단으로 돌려준다.
그 외 예외 = 엔진 내부 실패로 본다(애매하면 이쪽이 기본값 — 엔진 버그가 사용자 오류로 위장하면 발견되지 않는다).

ValueError 를 상속한다: 기존 호출부의 `except ValueError` 계약을 깨지 않기 위해서다.
"""


class SourceError(ValueError):
    def __init__(self, message: str, line: int | None = None):
        super().__init__(message)
        self.line = line
