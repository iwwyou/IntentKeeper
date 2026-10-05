# IQDebug — 프로젝트 Handoff (PROGRESS2)

> **문서 분담**
> - `PROGRESS.md` = 엔진·구현의 시간순 로그(decisions #1–#41). 계속 append.
> - **이 문서** = 논문 방향의 **정본(authoritative) handoff**. 방향이 바뀌면 여기를 갱신한다.
>
> **§1–§20** 은 사용자가 ChatGPT 와 정리한 handoff 원문이다. **논리·claim 은 여기서 수정하지 않는다**
> (역할 분담: 논리/framing/문장 = ChatGPT, 구현/실험/LaTeX 삽입/문서 유지 = Claude).
> **§A–§C** 는 구현 담당이 붙인 리포지토리 현황·리스크 기록이며, 위 논리와 충돌하면 §1–§20 이 우선한다.
>
> 작성 2026-09-17. 이전 판(2026-09-17 오전, Plan 구분 없던 버전)은 이 문서로 대체됨.

---

# 1. 프로젝트 목적

IQDebug는 박사학위논문의 세 번째 컴포넌트로, 기존의 두 연구인 **SolQDebug**와 **IntentChecker**를 통합·확장하여 실제 디버깅 워크플로를 제공하는 것을 목표로 한다.

연구 계보는 다음과 같다.

* **SolQDebug**: 개발 중 Solidity 코드의 값 변화를 interval abstract interpretation으로 보여주는 edit-time debugging assistant.
* **IntentChecker**: 개발자가 선언한 value-level intent와 실제 프로그램 동작을 비교하여 `Satisfied / Warning / Violated`로 검증.
* **IQDebug**: 위 두 기능을 실제 debugging interaction으로 통합. 개발자가 interval 기반 프로그램 상태를 탐색하면서 intent validation 결과까지 확인할 수 있도록 한다.

핵심 흐름은 다음처럼 이해하면 된다.

`Observe values → Validate developer intent → Interactively debug the analyzed behavior`

IQDebug는 박사학위 논문의 capstone 성격이며, 반드시 SolQDebug/IntentChecker와 완전히 독립적인 새로운 논문급 알고리즘을 추가해야 한다는 전제를 두지는 않는다. 다만 시간이 허용되면 intent-guided debug input generation을 추가 연구기여로 확장하고 싶다.

---

# 2. LLM별 역할 분담

## ChatGPT와 주로 할 일

* 박사학위논문의 전체 논리 구조
* SolQDebug → IntentChecker → IQDebug의 연구 narrative
* IQDebug contribution framing
* Research Questions 및 Evaluation 구성
* Related Work / Motivation / Discussion / Limitations 논리
* 논문 문장 및 LaTeX 텍스트 초안 작성
* reviewer 관점에서 claim 검토
* 필요할 경우 알고리즘 설계에 대한 개념적 논의

즉, **research logic / writing / framing 담당**.

## 다른 LLM(Claude)과 주로 할 일

* 실제 코드 구현
* 엔진 수정 및 debugging
* experiment harness 작성
* 실험 실행 및 결과 정리
* 필요할 경우 알고리즘 구현
* ChatGPT와 작성한 LaTeX 텍스트를 실제 논문의 적절한 위치에 삽입
* 기존 `.tex` 구조 및 label/reference와의 정합성 유지
* 코드/논문 변경 사항을 PROGRESS 문서에 반영

즉, **implementation / experiment / repository maintenance 담당**.

---

# 3. 선행 연구

## 3.1 SolQDebug

SolQDebug는 이미 게재된 연구다.

핵심 특성:

* Solidity 개발 중 동작하는 **edit-time debugging assistant**
* single-contract / single-transaction 중심
* interval-domain abstract interpretation 사용
* 개발자가 symbolic interval 형태의 debugging annotation을 제공
* 하나의 concrete input이 아니라 여러 input scenario를 한 번에 분석
* interactive parser 및 incremental CFG update
* line-to-node indexing
* flow-sensitive, path-insensitive 분석
* responsiveness를 precision보다 우선시하는 설계

중요한 설계 철학:

* abstract interpretation을 사용하는 이유:
  * termination
  * bounded analysis time
  * statement-level explainability
* interval domain을 사용하는 이유:
  * relational domain보다 interactive responsiveness 유지
* path-insensitive인 이유:
  * path별 결과를 모두 사용자에게 보여주면 개발자가 다시 manual value tracing을 해야 하기 때문

SolQDebug가 하지 않는 것:

* step forward/backward
* breakpoint
* continue
* concrete-debugger 스타일 navigation

즉 SolQDebug는 기본적으로:

> “코드를 수정하면 각 program point의 abstract value를 보여준다.”

까지이고, 실제 debugger interaction은 없다.

Remix, Forge 등의 실무 debugging tool은 존재하지만, SolQDebug 게재 당시 조사 범위에서는 Solidity debugging을 학술적 debugging assistant 형태로 체계화한 선행 연구가 사실상 없었다. 따라서 논문 claim은 일반적인 “first smart-contract debugger”가 아니라 기존 SolQDebug의 peer-reviewed wording을 계승하는 것이 안전하다.

## 3.2 IntentChecker

IntentChecker는 현재 revision 심사 중인 연구다.

핵심:

* multi-contract / single-transaction
* interval abstract interpretation 기반
* 개발자가 직접 작성한 **value-level numeric intent**를 검증
* 취약점 패턴이 아니라 developer intent를 oracle로 사용

Intent 종류:

### `@During`

특정 program point에서의 관계를 표현한다. 예: `before`, `after`, `assign` 등의 snapshot reference 사용.

### `@Post`

함수 entry와 exit의 관계를 표현한다. 예:

```text
balance(Exit) == balance(Entry) - amount
```

현재 arithmetic grammar는 단순 비교 수준이 아니라 비교적 복잡하다. 지원되는 연산에는 다음 등이 있다.

```text
+ - * / % ** << >> >>>
```

그리고 snapshot-qualified reference가 arithmetic expression의 first-class term으로 사용된다.

IntentChecker의 판정:

* `Satisfied`
* `Warning`
* `Violated`

개념적 의미:

* **Satisfied**: abstract state 전체가 developer intent를 만족
* **Violated**: abstract state 전체가 developer intent를 위반
* **Warning**: 일부는 만족하고 일부는 위반하여 현재 abstraction으로 판정 불가
* **Unreachable**은 IQDebug 쪽에서 추가적으로 다루려는 상태이며, 해당 intent point 자체에 도달할 수 없는 경우를 의미

중요한 점: `Satisfied`와 `Violated`는 둘 다 definite verdict이다. 미결정 상태는 기본적으로 `Warning`이다.

---

# 4. IntentChecker가 남긴 Effort

IntentChecker에서는 intent 검증을 위해 개발자가 두 종류의 입력 부담을 갖는다.

## Effort 1: Intent 작성

개발자가 다음을 직접 결정한다.

* 어떤 관계를 검증할지
* 어느 program point에서 검증할지
* 어떤 intent syntax로 표현할지

IQDebug에서는 이 Effort 1을 자동화하지 않는다. 즉:

> **Intent는 실제 developer intent이며, 개발자가 작성한다고 가정한다.**

Intent auto-generation은 현재 범위에서 제외한다.

## Effort 2: Abstract Debug Input 제공

IntentChecker의 검증 결과는 개발자가 제공한 abstract debugging input에 의존한다.

문제:

```text
Input이 너무 좁음
→ 관심 동작이 포함되지 않음
→ violation을 못 볼 수 있음

Input이 너무 넓음
→ abstraction precision 감소
→ Warning 발생
```

IQDebug의 optional extension은 바로 이 Effort 2를 줄이는 방향이다.

---

# 5. IQDebug의 기본 방향: Plan A

현재 최우선 목표는 **Plan A**이다. Plan A에서는 새로운 복잡한 input-generation 알고리즘 없이도 IQDebug를 완성한다.

핵심은:

> **Intent-aware abstract debugging assistant**

사용자는 abstract input range를 제공하고, IQDebug는 interval abstract interpretation 결과를 실제 debugger처럼 탐색할 수 있게 한다.

## 5.1 Quick / Abstract Debugging

IQDebug는 concrete execution 하나를 따라가는 debugger가 아니다.

개발자가 예를 들어 다음과 같은 input range를 준다.

```text
amount = [10, 100]
balance = [50, 200]
```

엔진은 이 범위 아래 가능한 프로그램 동작을 abstract interpretation으로 분석한다. 결과는 program point별 abstract state이다. 즉:

```text
range in → range propagation → range out
```

형태의 debugging이다.

`Quick`의 의미는 가능한 한 edit-time / interactive responsiveness를 유지하는 것이다.

---

# 6. 실제 Debugging 기능

IQDebug에서는 SolQDebug에 없었던 실제 debugger interaction을 추가한다.

예상 기능:

* Step Forward
* Step Backward
* Step Into
* Step Out
* Breakpoint
* Continue
* Previous / Next Breakpoint
* State & Locals
* Verdict panel

단, concrete debugger의 의미를 그대로 사용할 수 없다. 분석 자체가 path-insensitive abstract interpretation이기 때문이다.

## 6.1 Step Forward

미리 계산된 CFG-with-abstract-states 위에서 다음 program point로 이동한다. navigation 자체는 새 engine analysis를 발생시키지 않는 방향이다.

## 6.2 Step Backward

concrete execution history rewind가 아니다. 개념적으로:

> **provenance / predecessor navigation**

이미 각 program point의 abstract state가 계산되어 있기 때문에 이전 program point를 탐색한다.

## 6.3 Merge Point

path-insensitive analysis에서는 여러 predecessor가 merge된다. backward navigation 시 하나의 arbitrary predecessor만 따라가지 않고:

* non-bottom predecessor들을 보여주거나 highlight
* bottom predecessor는 dead branch로 표시

하는 방식이 고려되어 있다.

## 6.4 Loop

iteration별 concrete stepping은 하지 않는다. 루프는 abstract interpretation의 fixpoint로 처리된다. 따라서:

* loop 진입 시 iteration 1, 2, 3을 순서대로 보여주지 않음
* fixpoint/invariant 상태를 보여줌
* 사용자가 이를 concrete first iteration value로 오해하지 않도록 명시 필요

## 6.5 External / Cross-contract Call

현재 분석으로 내부를 볼 수 없는 `@IReturn` 등의 external result는 opaque로 처리될 수 있다. Step Into가 불가능하면:

```text
opaque external call
```

처럼 명시적으로 보여주는 방식이 고려되어 있다.

---

# 7. Intent-Aware Debugging

IQDebug의 중요한 축이다. 사용자가 제공한 abstract input 아래에서 계산된 program behavior를 developer-written intent와 비교한다.

예:

```text
debug input
    ↓
abstract interpretation
    ↓
program-point states
    ↓
@During / @Post validation
    ↓
Satisfied / Warning / Violated
```

즉 intent validation은 독립적인 offline verifier라기보다 debugging workflow 안에 들어간다.

예상 UI:

* current line abstract state
* intent attached to the line/function
* verdict
* violation-related information
* relevant region/state

---

# 8. IQDebug의 Originality / Positioning

현재 반드시 “SolQDebug/IntentChecker와 완전히 독립적인 신규 알고리즘”을 하나 만들어야 한다고 보지는 않는다. 박사학위논문 자체가 기존 게재·심사 논문을 하나의 연구 흐름으로 통합하는 형태가 일반적인 경우가 있기 때문이다.

단, 실제 학과/학교 규정과 지도교수 판단이 최종 기준이다.

## 8.1 Smart-contract debugging research

Remix, Forge 등 실제 debugging tool은 이미 존재한다. 따라서:

```text
the first smart-contract debugging tool
```

처럼 주장하면 안 된다. 대신 기존 SolQDebug의 검증된 academic positioning을 계승한다. 예:

```text
the first edit-time debugging assistant for Solidity
```

정확한 claim은 기존 SolQDebug 논문 wording을 확인하여 사용한다.

## 8.2 Quick Abstract Debugging

concrete input 하나를 실행하는 것이 아니라 interval input으로 여러 가능 동작을 한 번에 분석한다.

```text
abstract input ranges
→ abstract execution
→ program-point ranges
→ interactive navigation
```

## 8.3 Intent-Aware Debugging

일반적인 pre/post validation뿐 아니라 IQDebug는 IntentChecker의 intent model을 사용한다.

* `@During`: program-point-level intent
* `@Post`: function-level entry/exit intent

특히 line/program-point 수준에서 before/after/assign과 같은 snapshot 관계를 검증할 수 있다.

단:

> “기존 다른 언어 연구들은 전부 Pre/Post만 지원하고 IQDebug만 During을 지원한다”

라는 claim은 아직 사용하지 않는다. 관련 연구 조사 후 검증이 필요하다. Assertions, invariants, program-point specification 등과의 비교가 필요하다.

---

# 9. Optional Extension: Plan B

시간이 허용되면 Plan B를 추가하고 싶다. 현재 tentative 방향은:

> **Intent-Guided Debug Input Generation**

목적은 전체 input domain을 완전히 partition하는 것보다, debugging 관점에서 **intent violation을 드러내는 abstract input range를 우선적으로 찾는 것**이다.

## 9.1 기본 아이디어

입력:

* Solidity code
* developer-written intent
* target function/program point
* code상의 branch/path conditions

목표:

```text
Violated verdict를 만들어내는 abstract input range
```

우선순위는 잠정적으로:

1. **Violated가 확정되는 input range**
2. 찾기 어렵다면 relevant `Warning` range
3. budget 초과 / 실패 시 사용자 수동 입력

## 9.2 왜 Violated 우선인가

IQDebug의 정체성이 debugger이기 때문이다. 사용자가 디버깅할 때 자연스러운 질문은:

> “내가 작성한 intent를 깨뜨리는 실행 조건이 있다면 그 조건에서 프로그램을 보여줘.”

Satisfied domain 전체를 characterizing하는 것은 verification에 더 가깝다. 반면:

```text
intent
→ violated input range
→ debugging session
```

은 debugging assistant의 흐름과 직접 연결된다.

---

# 10. Plan B의 개념적 입력 생성

현재 아이디어 단계다. 대략적으로:

```text
developer intent
+
program branch/reachability conditions
↓
candidate debugging input
↓
existing abstract interpreter
↓
IntentChecker verdict
```

핵심은 기존 IntentChecker engine을 계속 **final oracle**로 사용하는 것이다. 즉 별도의 symbolic engine이 Solidity 전체 semantics를 완전히 재구현하는 방식은 피하고 싶다.

---

# 11. 중요한 주의점: Intent는 단순 비교식이 아님

Plan B를 구현할 때 매우 중요하다. 실제 IntentChecker intent는 다음처럼 단순하지 않다.

```text
x > 10
```

수준에 한정되지 않는다. 예:

```text
balance(Exit) == balance(Entry) - amount
```

또는 `@During`에서:

```text
x(after)
x(before)
x(assign)
```

등이 expression 안에 등장한다. Arithmetic expression도 복잡하다.

따라서:

```text
NOT(intent) → solver
```

만으로 input generation 문제 전체를 해결한다고 가정하면 안 된다. 특히 다음이 고려되어야 한다.

* snapshot references
* arithmetic expressions
* division/modulo
* branches
* loops
* path merging
* cross-contract opaque values

따라서 Plan B는 처음부터 full symbolic inversion으로 설계하지 않는 것이 좋다. 기존 abstract interpreter를 forward oracle로 활용하는 search/refinement 방식이 현재로서는 더 자연스러운 후보이다.

---

# 12. Plan B와 Debugging 연결

Plan B가 구현된다면 가장 자연스러운 end-to-end workflow는 다음이다.

```text
Developer writes intent
        ↓
IQDebug searches for violating input range
        ↓
Violated range found
        ↓
That range is automatically populated into debug input
        ↓
Abstract analysis runs
        ↓
Developer enters Debug View
        ↓
step / backward / breakpoint / state inspection
        ↓
Developer investigates why intent is violated
```

이 연결은 중요하다. Plan B가 별도 분석 기능으로 끝나지 않고 Plan A의 actual debugger와 연결되어야 한다.

---

# 13. 현재는 제외하는 기능

## Intent Auto-generation

하지 않는다. Intent는 developer intent이고 인간이 작성한다.

## LLM

현재 core 방향에서는 사용하지 않는다. 이전 설계 문서에는 LLM-based range synthesis가 originality 후보로 있었지만 최신 방향에서는 내려놓았다.

## Intent Repair

현재 제외. Satisfied region으로부터 자동 `require`를 제안하거나 코드를 수정하는 기능 역시 현재 core scope에서 제외한다.

## Full Multi-transaction Fixpoint

현재 제외. 이유:

* 여러 함수에 대한 fixpoint 필요
* interactive responsiveness와 충돌
* `Quick` identity 약화

## Precompute & Inject

이전에는 다음 아이디어가 있었다.

```text
multi-tx / external state
→ offline heavy analysis
→ contract-level range precompute
→ quick debugger에 inject
```

하지만 현재 필수 기능이 아니다. 필요 시 future work로 둘 수 있다.

---

# 14. Unreachable

IQDebug에서는 intent point가 애초에 도달 불가능한 경우를 별도로 `Unreachable`로 다루는 아이디어가 있다.

개념적으로 Satisfied와 다르고, Violated와 다르고, Warning과도 다르다. 해당 observation point 자체에 도달할 수 없으므로 검증 대상이 실질적으로 발생하지 않는다.

현재 `@During` 기준 일부 구현은 존재하며 `@Post`는 추가 확인이 필요할 수 있다.

---

# 15. Satisfied Region → require 제안 아이디어

이전 논의에서:

```text
Satisfied region
→ safe input range
→ missing require 후보
```

라는 아이디어가 있었다. 현재는 사용하지 않는다. 이 기능은 debugging보다 precondition synthesis / repair에 가깝기 때문이다.

현재 IQDebug에서는:

```text
Satisfied = developer intent가 abstract state 전체에서 성립
```

정도로만 사용한다.

---

# 16. Plan A와 Plan B 우선순위

## Plan A — 반드시 완료

IQDebug 기본 시스템.

```text
SolQDebug abstract ranges
+
actual debugger navigation
+
IntentChecker intent validation
=
Intent-Aware Abstract Debugging Assistant
```

Plan A가 학위논문의 안정적인 core이다.

## Plan B — 시간이 허용될 경우

Intent-guided debug input generation.

```text
intent violation을 발생시키는 input range 자동 탐색
```

Plan B는 성공하면 연구적 색깔을 강화하지만, 실패하거나 시간이 부족해도 Plan A 기반 학위논문 전체가 흔들리지 않도록 설계한다.

---

# 17. 현재 논문의 잠정적인 핵심 문장

Plan A 기준:

> **IQDebug is an intent-aware abstract debugging assistant that enables developers to interactively navigate range-based program behaviors and validate developer-specified value-level intents during Solidity development.**

Plan B까지 구현될 경우:

> **IQDebug further uses developer intent and program conditions to derive abstract debugging input ranges that expose intent violations.**

두 문장은 의도적으로 분리한다. 첫 번째가 학위논문 core이며 두 번째는 optional extension이다.

**논문 제목 (2026-09-17 선정, 변경 가능)**:

> **An Intent-Aware Quick Debugging Assistant for Solidity**

`paper/Phd_thesis/main.tex` 의 4곳(표지·속표지·초록 헤딩·`pdftitle`)에 반영 완료.
국문 제목은 미정.

---

# 18. 구현 담당 LLM이 지켜야 할 원칙

1. **Plan A가 항상 우선이다.** Plan B 때문에 Plan A 일정이나 안정성을 깨면 안 된다.
2. **Intent는 자동생성하지 않는다.** Developer-written intent가 oracle이다.
3. **Final verdict는 기존 IntentChecker engine을 신뢰한다.** Plan B가 candidate input을 생성하더라도 최종 판정은 기존 engine의 `Satisfied / Warning / Violated`를 사용한다.
4. **Concrete debugger로 바꾸지 않는다.** IQDebug는 abstract/range debugging assistant이다.
5. **Path-sensitive execution을 새로 만드는 방향으로 함부로 가지 않는다.** 기존 SolQDebug 설계는 의도적으로 path-insensitive이다.
6. **Loop는 iteration unfolding보다 fixpoint abstraction을 유지한다.**
7. **Quick responsiveness를 훼손하는 기능은 interactive loop 밖으로 분리하거나 제외한다.**
8. **현재 scope는 multi-contract single-transaction 중심이다.** Full multi-transaction analysis는 현재 core scope가 아니다.
9. **기존 논문 claim과 충돌하는 설계 변경을 하지 않는다.** 특히 interval domain / responsiveness priority / path-insensitivity / developer-written intent / value-level intent scope.
10. **논문 문장을 자동 수정하지 말고 ChatGPT와 확정된 텍스트를 삽입하는 역할을 우선한다.** 논리나 claim 변경이 필요한 경우 먼저 사용자에게 알려야 한다.

---

# 19. 구현 담당이 집중할 순서

### 1단계 — Plan A의 안정화

* engine integration
* abstract state serialization
* Debug View
* step/back/breakpoint/continue
* loop fixpoint state presentation
* intent panel
* debug input panel
* verdict panel
* incremental update correctness

### 2단계 — Plan A evaluation 준비

* 기존 SolQDebug / IntentChecker benchmark 재사용 가능성 확인
* latency
* navigation behavior
* intent-aware debug workflow
* case studies

### 3단계 — 시간이 남으면 Plan B feasibility prototype

처음부터 full implementation 하지 말고 작은 subset으로 가능성부터 확인한다. 예:

* simple arithmetic
* branch condition
* one `@During` or `@Post`
* no loop
* no opaque external call

에서:

```text
intent + branch condition
→ candidate interval
→ engine verify
```

가 실제로 동작하는지 먼저 본다. 가능성이 확인된 후 grammar coverage를 늘린다.

---

# 20. 현재 가장 중요한 프로젝트 원칙

IQDebug를 과도하게 크게 만들 필요는 없다. 박사학위논문의 기본 목표는 다음 계보를 완성하는 것이다.

```text
SolQDebug
“How do values evolve?”

        ↓

IntentChecker
“Do these values conform to what the developer intended?”

        ↓

IQDebug
“Can the developer interactively investigate those abstract behaviors
and their intent violations as part of an actual debugging workflow?”
```

Plan B가 성공할 경우 마지막 질문을 다음까지 확장한다.

```text
“Can the debugger also derive an input context that exposes the violation?”
```

---
---

# A. 구현 현황 · 남은 작업 (구현 담당 기록 · 2026-09-18 갱신)

> §19 1단계 체크리스트를 리포지토리 실제 상태에 매핑한 것. 상세는 `PROGRESS.md` decision 번호 참조.
> **회귀 스위트: `temp/` 16종 188 checks** (`.venv\Scripts\python.exe temp\<name>.py`).

## A.1 완료

| §19 항목 | 상태 | 근거 |
|---|---|---|
| engine integration | ✅ | `EngineSession` 3계층(analyze/evaluate/verify) + `engine_server.py` |
| abstract state serialization | ✅ | `_serialize_cfg`/`_serialize_node_state`, `types/result.ts` 와 1:1 |
| Debug View | ✅ | 툴바 + 코드 좌 + 우측 3분할 |
| step forward/backward · breakpoint · continue | ✅ | `useNavigation.ts`, 엔진 호출 0회 (decision #3) |
| merge backward (non-⊥ predecessor 전부 highlight) | ✅ | decision #4 |
| intent panel | ✅ | `IntentPanel.tsx` (라인-클릭 부착은 A.2 ⑦) |
| debug input panel | ✅ | 슬롯-주도, 값만 입력, Apply 버튼 (#32) |
| verdict panel | ✅ | S/W/V + risk + region 점프 + `falseRegions` |
| incremental update correctness | ✅ | B1 diff + SESE 수술 + full-rebuild 폴백 |
| **Unreachable (§14) — @During·@Post 둘 다** | ✅ | **#42** |
| **BOTTOM 전파 (require/assert)** | ✅ | **#42** — 근본 버그 수정 |
| **back_edge 라벨링** | ✅ | **#43** — dominator 기반 |
| **함수 목록 API (mock 고정 제거)** | ✅ | **#44** — `outline()` + `/outline` + `refreshOutline()` |

**최근 코어 변경**
- **#41**(2026-09-16) Guardian 리비전 1회성 이식 — snapshot reference 가 `arithFactor` 1급 항,
  ⊤→Warning, @Post/explicit-return 로컬 미조회 버그 수정.
- **#42**(2026-09-18) `require`/`assert` 가 BOTTOM 을 전파하지 않던 버그. 이후 노드·EXIT 가 빈 `{}` 로
  남아 도달불가를 놓치고 @Post 가 `internal error` 로 둔갑했다. `if`/`else-if` 분기와 동일한
  3단 패턴(seed→BOTTOM→append)으로 정정 + `_exit_env` 의 `related_variables` 폴백을 fail-loud 로.
- **#43 / #44**(2026-09-18) 위 표 참조. 둘 다 비코어(`engine_api`/`engine_server`/프론트).

## A.2 남은 작업 (Plan A 기준 · 우선순위 순)

> Plan B(intent-guided input generation)는 §9·§16 대로 **제외**. 아래는 전부 Plan A 범위.

### ② Step Into / Step Out — 규모 **대**, Plan A 의 최대 미구현 덩어리
`useNavigation.ts:153-163` 이 stub 이다(주석에 `// mock`). `stepInto` = `forwardPick`(그냥 forward),
`stepOut` = `pred[0]`(backward 1칸). §6 기능 목록과 §3.4.3 의 핵심인데 동작하지 않는다.
세 가지가 함께 필요하다:
- **call 노드 표식이 없다** — `NodeFlag`(`result.ts:5-13`, `engine_api._node_flags`)에 `call`/`opaque`
  가 없어 프론트가 "여기가 호출 지점인지" 를 알 수 없다.
- **callee CFG 가 직렬화되지 않는다** — 엔진은 내부 호출을 실제로 하강해 해석하지만
  (`Engine.py:673-729`, caller env 의 state/global 공유; `ContractCFG.functions` 가 함수별 CFG 보유)
  **callee 상태는 계산 후 버려진다**(`Engine.py:769` 복원, freeze 는 타겟 fcfg 만).
  → callee 도 freeze·직렬화해야 한다.
- **§6.5 opaque 경계 표시**가 여기 딸린다. `@IReturn` 이면 "opaque, 못 들어감" 을 띄워야 하는데
  표식 자체가 없다. (`TopVar.provenance` 도 `null` 고정 — ⊤ 출처 태깅 미구현)

### ⑤ 루프 fixpoint fold — 규모 **중**, ④의 잔여와 직접 맞물림
§6.4 "step forward 가 루프 진입 → 루프 전체 fixpoint 로 접어 표시" 가 없다. `stepForward` 는 그냥
successor 로 들어간다. `loop_body` flag 는 오고 `StateLocals` 가 "루프 불변식" 라벨은 붙이지만
**navigation 차원의 fold 가 없다.**
★ **#43 의 남은 절반**: 프론트 `succ()`(= `stepForward`/`continueRun`)는 back_edge 를 **안 거른다**.
그래서 forward 는 여전히 back edge 를 타고 루프를 돈다(= decision #4 가 금지한 "iteration 별 stepping"
착각). 여기서 단순히 걸러버리면 루프 꼬리에서 커서가 **멈춰버리므로**, fold 설계와 함께 가야 한다.
라벨(#43)은 이미 있으니 바로 쓸 수 있다.

### ③ DependencyStore — 규모 **중~대**, 데모 서사에 필요
`engine_api.py:1315-1325` 3개 메서드 전부 `NotImplementedError`. `/deps` 엔드포인트 없음.
`DepsSidebar` 는 순수 stub(첨부해도 아무 일 없음). 리포에 미리 빌드된 `Dependencies/objectfile/*.pkl`
만 동작한다. **multi-contract 가 IntentChecker 의 scope 인데 임의 의존성을 붙일 수 없다.**
topo-sort 도 미구현(`_con_order` 하드코딩).
🤔 **판단 필요**: 평가를 pkl 이 이미 있는 컨트랙트로만 돌리면 미구현이어도 논문은 나온다. 하지만
"개발자가 자기 프로젝트에 붙여 쓴다" 서사를 쓸 거면 필요하다. (§7 열린 질문)

### navigation 정합성 N1~N7 (2026-09-30, 논문 §Debugging 절 ↔ 구현 대조에서 도출)

> 논문 §Source-Level Debugging over Abstract Program States 초안을 실제 구현
> (`frontend/src/debug/useNavigation.ts` 212줄 = navigation 전부, `types/result.ts` = 계약)과
> 대조해 도출. 상세 대조 결과 = `PROGRESS.md` decision #47.
> **N1·N5·N6·N7 은 프론트 전용, N3 는 직렬화, N2 는 설계 결정 포함, N4 는 코어.**

**N1. forward 분기 표시 (backward 와 대칭)** — ✅ **적용 (2026-10-01)**
현재 `forwardPick = live[0] ?? ss[0]` 로 **자동 첫째**이고 나머지 successor 를 보여주지
않는다. backward 는 이미 live predecessor 를 전부 하이라이트하므로 **비대칭**이다.
→ `highlightedPreds` 와 대칭인 `highlightedSuccs` 를 두고, 커서는 첫 feasible successor,
나머지는 하이라이트. `CFGEdge.kind`(`'true'|'false'`)로 어느 분기인지 표시 가능.
★ **사용자에게 경로를 고르게 하지 않는다**(결정) — 그건 concrete path 선택으로의 회귀다.
abstract state 가 여러 경로를 동시에 표현하므로 화면도 동시에 보여준다.
⚠ 부수 정정: `live[0] ?? ss[0]` 폴백 때문에 **전부 dead 여도 이동**한다 →
"이후 모든 경로가 도달 불가" 로 표시하고 이동하지 않게.

> **적용**: `NavState.highlightedSuccs: string[]` 신규 (+ state, `go(id, preds, succs)`
> 3번째 인자). `forwardLive(from)` = non-back-edge successor 중 `!engineDead`,
> `forwardPick` = 그 첫째. **`?? ss[0]` 폴백을 제거**해 전부 dead 면 `stepForward`
> 가 아무 것도 하지 않는다. `live.length > 1` 일 때만 하이라이트(단일 분기엔 노이즈 없음).
> 표시: `CodePane.tsx` `succLines` → `.succ-line`(청록 `rgba(78,201,176,.16)`, pred 노랑과 구분),
> `StateLocals.tsx` 에 `branch forward: … 전부 feasible → 모두 하이라이트` 힌트.

**N2. `succ` 에 back_edge 필터 + 루프 fold** — ✅ **적용 (2026-10-01)**
`pred` 는 `kind !== 'back_edge'` 로 거르는데 **`succ` 는 거르지 않아** `stepForward`/
`continueRun` 이 루프를 다시 돈다(값은 fixpoint 라 안 바뀌지만 커서가 iteration 을 도는
것처럼 보인다 — decision #4 가 금지한 착각). 같은 파일의 applyTick 경로는 거른다 —
**한 파일 안 불일치**. #43 의 남은 절반.
→ **착지점 결정(사용자): 루프 이후 첫 statement**. 닫는 `}`(= `loop_exit`)가 아닌 이유는
그 노드가 `FORBIDDEN_TARGET_FLAGS` 에 있고(forward-pred 2개 이상 → pre-state 가 merge
대상이라 모호) 예외를 만들면 그 설계 전제를 다시 봐야 하기 때문이다.
⚠ **필터만 켜면 루프 꼬리에서 커서가 멈춘다** — fold 규칙 동반이 필수.

> **적용**
> - `succ` 에 `kind !== 'back_edge'` 추가 → `pred`·applyTick 과 의미론 일치.
> - `foldLoop(boundary)`: join(`fixpoint_evaluation`) → head(`condition` +
>   `cond_type ∈ {while,for,do_while}`) → head 의 `false` 엣지 → `loop_exit` →
>   **그 첫 live 후속 = 루프 이후 첫 statement**. 없으면 `loop_exit` 자체(함수 끝).
>   구조는 **직렬화된 flags/edges 만으로** 복원한다(엔진 재질의 없음 = "quick" 정체성 유지).
> - `exitEnclosingLoop(id)`: 꼬리의 `back_edge` → 그 join → `foldLoop`.
>   back_edge 를 거른 대가인 **"커서 갇힘" 을 이것으로 해소**한다. 중첩 루프의 내부 꼬리면
>   내부 루프만 빠져나가고 바깥 루프에는 남는다.
> - `stepForward` 는 세 경우를 본다: ① 커서가 루프 헤더 → 그 루프를 접는다
>   ② live 후속 없음(꼬리) → `exitEnclosingLoop` ③ 단일 live 후속이 루프 경계 → 접는다.
> - `NavState.foldedLoopHead` 신규 → UI 가 "어느 루프를 접고 왔는지" 와 그 `loop_delta` 를 띄운다.
>   커서는 루프 **이후**에 있으므로 표시가 없으면 건너뛴 사실이 화면에서 사라진다.
>
> ★ **`continueRun`/`next bp` 는 접지 않고 본문을 통과한다** (설계 결정).
> `runAdvance = forwardPick(x) ?? exitEnclosingLoop(x).landing` 를 쓴다.
> 근거: concrete debugger 에서 **Step Over 는 호출을 건너뛰지만 Continue 는 그 안의
> breakpoint 에 멈춘다** — 그 관계를 그대로 옮긴 것이다. 루프 본문의 breakpoint 는
> "루프 불변식" 을 보는 정당한 지점이므로 놓치게 하면 안 된다. 상태가 fixpoint 하나뿐이라
> `visited` 가 본문을 **한 번만** 지나게 보장하므로 iteration 착시도 생기지 않는다.

**N2·N3 검증 (2026-10-01, `scratchpad/navsim2.py` — TS 규칙을 실엔진 CFG 위에서 재현)**

| 케이스 | step forward 궤적 | Continue (본문 bp) |
|---|---|---|
| `while` + 이후 문장 | `VarDecl_7 → VarDecl_8 → Assign_13 ⟲fold:while_cond_9 → Return_14` | `Assign_10` L10 ✅ |
| `for` + 이후 문장 | `VarDecl_7 → for_init_8 → Assign_11 ⟲fold:for_cond_8 → Return_12` | `Assign_9` L9 ✅ |
| 루프가 함수 마지막 | `VarDecl_7 → VarDecl_8 → Return_13 ⟲fold:while_cond_9` | `Assign_10` L10 ✅ |
| `if`-in-loop | `VarDecl_7 → for_init_8 → Assign_13 ⟲fold:for_cond_8 → Return_14` | `if_condition_9` L9 ✅ |

본문에 들어가지 않고, back edge 를 타지 않고, 루프 **이후 첫 statement** 에 착지한다.
`loop_delta` 도 전부 헤더 노드 하나에만 실린다(`{acc: ⊤, i: [0,10]}` 등).

✅ **⑰ 해소** (F48, decision #49): `for_init_8(L-1)` → `(L8)`. `for` 줄에서 한 번 멈춘 뒤
다음 step 이 루프를 접는다.
✅ **중첩 루프 해소** (F45·F46·F47, decision #49): 6형태(`for`/`while`/`if` 조합) 전부
dangling 0 · 우회 엣지 0 · `acc=⊤`(루프 효과가 뒷 문장에 도달).
⚠ **단, 중첩 시 바깥 루프 카운터는 ⊤ 로 남는다** — flat chaotic iteration 의 비용이며
**건전하다**(과대근사). 최외곽 `loop_delta` 가 `{acc: ⊤, i: ⊤}` 가 되어 정보량이 줄어든다.
hierarchical 은 정확하지만 14배 느리고 3중 루프에서 크래시해 기각했다(decision #49).

**N3. `loopDelta` 웹 배선** — ✅ **적용 (2026-10-01)**
★ **엔진에 이미 있다**: `Engine.fixpoint` 가
`VariableEnv.diff_changed(join_baseline_env, fixpoint_evaluation_node_vars)` 로
**루프 진입 전 ↔ 수렴 후 값이 바뀐 변수만** 추출해 루프 헤더 라인에
`{"kind":"loopDelta","vars":…}` 로 기록한다(루프 내부 새 변수는 제외).
그런데 `engine_api.py` 가 `RecordManager.ledger` 를 **전혀 참조하지 않아** 웹으로 오지 않는다.
→ `CFGNode` 에 `loop_delta?: Record<string,string>` 추가 + `_serialize_cfg` 에서 채운다.
⚠ `types/result.ts` ↔ engine_api dataclass 는 **1:1 계약** — 양쪽을 함께 바꿔야 한다.
표시 예:
```
for (uint i = 0; i < n; i++) {   ← loopDelta: acc: [1,1] → [1,⊤],  i: [0,0] → [0,⊤]
    acc = acc + i;               ← 루프 불변식(모든 iteration 성립)
}
r = acc;                          ← Step Forward 착지점 (N2)
```

> **적용**
> - 엔진: `loopDelta` 가 **애초에 생성되지 않고 있었다** — 루프 본문이 해석되지 않았기
>   때문(= F43, decision #48). N3 의 전제가 깨져 있었고 그것부터 고쳐야 했다.
> - `engine_api._loop_delta(n, recorder)` 신규 → `recorder.ledger.get(src_line)` 에서
>   `kind == "loopDelta"` 를 꺼낸다. ⚠ **루프 조건 노드에만** 붙인다 —
>   `for (i=0; i<n; i++)` 는 헤더 한 줄에 init/cond/update 노드가 있어 라인만으로
>   매칭하면 같은 delta 가 중복된다. `ledger` 는 `defaultdict(list)` 라 `.get` 으로 읽어
>   빈 키 생성을 막는다.
> - `CFGNode.loop_delta: Optional[dict[str,str]]` (engine_api) ↔
>   `loop_delta?: Record<string,string>` (`types/result.ts`) — **양쪽 동시 변경**(1:1 계약).
> - `with_states=False`(analyze 구조 단계)에는 **내보내지 않는다**. ledger 에 이전 evaluate 의
>   delta 가 남아 있어도 "값 없는 결과" 계약을 지킨다.
> - 표시: `StateLocals` 의 `.loop-fold` 블록(접은 루프 헤더 라인 + 바뀐 변수 목록,
>   delta 가 비면 "수렴 후 바뀐 변수 없음"), `CodePane` 의 `.loop-fold-line`
>   (점선 테두리 + hover 에 delta).
> - ✅ **`inf` 표기 혼재 해소** — F45(2026-10-01, decision #49)로 widening 이 타입 최댓값을
>   넣는다. 직렬화 출력에서 `inf` 완전 소거.
> - ✅ **최외곽 루프만 내보낸다** (사용자 결정, decision #49). N2 의 step forward 가 최외곽
>   루프를 통째로 접고 그 **뒤**로 착지하므로 안쪽 루프는 navigation 착지점이 되지 않는다.
>   `engine_api._nested_loop_heads` 가 **직렬화 시점에 매번** 중첩 여부를 판정한다 —
>   안쪽 delta 는 증분 빌드 도중 ledger 에 **낡은 스냅샷**으로 남으므로 "안 생긴다" 에
>   기댈 수 없고 **걸러야** 한다. 판정 규칙은 `Engine.traverse_loop_nodes`(F46)와 동일.

**N4. Step Into / Step Out + Call Stack** — ✅ **적용 완료 (2026-10-01)**
현재 전부 stub(`into`=forward 1칸, `out`=backward 1칸, 주석에 "mock"). 막힌 곳 셋:
1. **callee 상태가 계산 후 버려진다** — 엔진은 실제로 하강 해석하지만
   (`interpret_function_cfg`) 끝에서 `_saved_node_vars` 로 callee 노드 env 를 **원복**하고,
   freeze 는 타겟 fcfg 하나만 한다. → callee 도 freeze·직렬화.
2. **`NodeFlag` 에 `'call'`/`'opaque'` 가 없다** → 프론트가 호출 지점을 모른다.
   `engine_api._node_flags` 에서 세팅.
3. **`AnalysisResult.cfg` 가 단일 CFG** → `callees?: Record<string, CFG>` 또는 별도 엔드포인트.

지원 범위 (decision #50 에서 확정):
internal ✅ / 상속(`super`/`Parent.f()`/abstract) ✅ / library ✅ / `this.f()` ✅ —
넷 다 `interpret_function_cfg` 를 타므로 상태만 보존하면 된다.
**주소 간접 외부 호출은 전부 ❌ opaque** — 인터페이스든 구체 컨트랙트든 같다. 컨트랙트 타입
캐스트는 런타임 검사가 없어 **주소에 배포된 임의의 코드가 실행**되므로 callee 코드가 타입으로
정해지지 않는다. `@IReturn` 으로 반환값만 받는다(mutability 는 선언으로 정해지고 EVM 이
STATICCALL 로 강제하므로 "부작용 없음" 만은 보장된다).
⚠ 내 이전 서술 **"dependency pkl 있으면 조건부 하강 가능" 은 거짓이었다** — 하강 구현 자체가
없고, 애초에 타입이 final 해도 코드는 주소로 정해진다. 논문의 "dependency CFG 존재" 서술도 거짓.

> **S1~S3 적용 (2026-10-01, F50)**
> - **S1** 엔진: `interpret_function_cfg` 의 restore **직전**에 `{노드명: {변수: 값}}` 포착.
>   키 = **(호출 지점, 컨트랙트, 함수)** — 함수명만으로는 같은 callee 의 두 호출 지점이 섞인다
>   (실측: `Math.mulDiv` 가 `_pct` 안에서는 `a=[1,100]`, `withdraw` 에서는 `a=[0,5000]`).
>   `update_statement_with_variables` 에서 `_call_site_node` 세팅(두 해석 경로의 공통 지점),
>   `interpret_function_cfg` 는 진입 시 로컬로 받아 중첩 프레임을 보존.
> - **S2** 계약: `NodeFlag += call/opaque`, `CalleeRef`, `CFGNode.callees`,
>   `AnalysisResult.callees` (engine_api ↔ `types/result.ts` 동시).
> - **S3** 직렬화: enterable 은 **실제 하강분**에서, opaque 는 외부 호출 스캔에서.
>   판정은 `_external_call_roots` 공용 헬퍼로 `@IReturn` 슬롯과 **같은 규칙**.
>   callee CFG 에도 `node_callees` 를 넘겨 **중첩 Step Into** 가능.
> - ★ **⊤ 우려 기각**: callee 가 타겟보다 **더 정밀**했다(타겟 ⊤ 14.0% vs callee 0.0%).
>   인자가 정제된 값으로 바인딩되고 state 변수를 공유하기 때문. 그리고 Step Into 가 새 정보를
>   준다 — `_pct` 의 `whole == 0` 가드가 ⊥ = 이 입력에서 죽은 코드(타겟 화면에서는 안 보인다).
> - **S4 프론트 (적용)**: `cursor: string` → **`stack: Frame[]`**.
>   `Frame = {cfgKey, node, label, contract, name, startLine, endLine}`,
>   `cfgKey === null` 이 타겟 프레임. `activeCfg` = `cfgKey ? result.callees[cfgKey] : result.cfg`
>   이고 **`succ`/`pred`/`engineDead`/`falseSucc`/`nodeById` 전부 활성 프레임 기준**으로 바뀜.
>   `StateLocals`·`CodePane` 도 `nav.activeCfg` 를 보게 고쳤다 — 타겟 CFG 를 뒤지면 callee
>   프레임에서 노드를 못 찾아 pre-state/path 가 전부 비어버린다.
>   - `go()` 는 **최상단 프레임의 node 만** 갱신한다. 부모 프레임 node 가 호출 지점에 남아
>     있으므로 **Step Out 은 pop 만으로** 제자리다.
>   - `stepInto`: 커서 노드의 `callees` 중 enterable 첫째로 **push**. opaque 뿐이거나 호출이
>     없으면 **이동하지 않고**, 사유는 UI 가 `CalleeRef.reason` 으로 띄운다. 여럿이면 첫째로
>     내려가고 나머지는 목록으로 보여준다(N1 과 같은 원칙 — **고르게 하지 않는다**).
>   - `MAX_CALL_DEPTH = 16` 은 **안전 상한일 뿐**이다. 재귀 감지·표시는 **보류**(백로그 ⑨).
>     루프 중첩과 달리 호출은 재귀면 무한히 깊어질 수 있어 UI 보호가 필요하다.
>   - **breakpoint 를 프레임(cfgKey)별로 분리**했다(`bpByFrame`). 하나의 Set 으로 두면 callee 가
>     **다른 파일**일 때 라인 번호가 겹쳐 엉뚱한 곳에서 멈춘다. `nav.breakpoints` 는 활성
>     프레임의 Set 을 노출하므로 외부 계약(CodePane)은 그대로다.
>   - `applyTick`(Apply) 은 스택을 **타겟 프레임 하나로 리셋**한다 — callee 스냅샷이 새 debug
>     값으로 전부 갱신되므로 옛 프레임을 들고 있으면 안 된다.
> - **Call Stack 패널 (신규 `CallStack.tsx`)**: `nav.stack` 을 그대로 그린다. 별도 자료구조가
>   아니라 **navigation 상태 자체**라 Step Into/Out 과 항상 일관된다. 프레임을 눌러 그 깊이로
>   되돌아가기(`popToFrame`), 현재 노드에서 "Step Into 가능/불가(사유)" 미리보기 포함.
> - **callee 소스 조달** (`DebugView`): ① 타겟 → `fnMeta` ② 같은 파일 callee → `store.functions`
>   (`/outline` 이 컨트랙트×함수를 전부 열거한다) ③ 의존성 callee → `depContents[컨트랙트]` 를
>   `CalleeRef` 의 라인 범위로 절취(pkl 라인은 **그 dep 파일 기준**이라 업로드 원문과 맞는다)
>   ④ 둘 다 없으면 소스 없음 안내 — **상태 패널은 그대로 동작**한다.
>   `attachDep` 가 이미 `depContents[name]` 에 원문을 보관하므로 엔진 변경이 필요 없었다.

**N4 검증 (2026-10-01, `scratchpad/navsim4.py` — Frame 규칙을 실엔진 결과 위에서 재현)**

```
depth 1  Pool.withdraw@VarDecl_26 (L26)   bal=[1,1000] pct=[10,1000]
  into → Pool._pct
depth 2  Pool._pct@if_condition_17 (L17)  part=[1,100] whole=[1000,1000]
  forward → Return_20 (L20)
  into → Math.mulDiv
depth 3  Math.mulDiv@VarDecl_6 (L6)       a=[1,100] b=[10000,10000] d=[1000,1000] p=[10000,1000000]
  out  ← Math.mulDiv   → Pool._pct@Return_20      ← 호출 지점 그대로 ✅
  out  ← Pool._pct     → Pool.withdraw@VarDecl_26 ← 호출 지점 그대로 ✅
  out                  → 이동 없음 (타겟 프레임)   ✅
```

`XC.sol` 로 opaque 확인 — `User.own`·`Base.baseRate`·`MathLib.twice` 는 into 되고,
`v.rate()`·`Vault(a).rate()`·`IRate(a).rate()` 는 **이동 없음**(사유 표시).
`npx tsc --noEmit` 0 errors.

⚠ **브라우저 육안 확인 미완** — Call Stack 패널 레이아웃, callee 소스 전환, 프레임별 breakpoint.

⚠ **재귀**: 재귀 가드가 전무하므로(백로그 ⑨) UI 에서 무한 하강이 가능해진다. 최소한
**호출 스택 깊이 상한 + "재귀 — 더 들어갈 수 없음" 표시**가 필요하다.
근본 해법은 사용자 검토 중(보류)이며, **N4 는 그것과 무관하게 진행하기로 결정**.

**N5. breakpoint 도달 불가 표시** — ✅ **적용 (2026-10-01)**
판정 함수가 **이미 있다**(`isBottom`/`engineDead`; `engine_api._serialize_node_state` 가
`"[None,None]" → "⊥"` 로 변환해줌). `canBreakpointOnLine` 에 이 검사를 더해
"이 라인은 도달 불가" 로 표시.

> **적용**: `isLineUnreachable(result, absLine)` 신규 export — 그 라인의 노드가
> **전부** ⊥ 포함일 때 true, 노드 없는 라인은 false(`도달 불가` 가 아니라 `분석 대상 아님`).
> ★ **breakpoint 를 막지 않는다** — 걸 수는 있게 두고 글리프를 바꾼다
> (`.bp-glyph-unreachable` = 빈 원 + 회색 테두리) + hover 로 `Continue/next bp 가
> 멈추지 않습니다` 설명. 막아버리면 **왜** 안 되는지가 화면에서 사라진다.

**N6. `next/prev Breakpoint` 를 CFG order 로** — ✅ **적용 (2026-10-01)**
현재 `[...breakpoints].sort((a,b)=>a-b).find(l => l > cl)` — **소스 라인 번호 정렬**이고
CFG 간선을 전혀 안 본다. `Continue` 는 CFG traversal 인데 의미론이 갈라져 있다.
→ `continueRun` 과 같은 traversal 재사용. 그러면 논문의 "저장된 CFG 상태를 이용한
navigation" 서술이 정확해진다.

> **적용**: `walkToBreakpoint(dir: 'fwd'|'back')` 신규. `fwd` = `forwardPick`,
> `back` = `pred`(back_edge 제외) 중 비-⊥ 우선. `visited` 로 사이클 차단,
> `isForbiddenTarget` 재확인.
> ★ **Continue 와의 차이를 의도적으로 유지**: breakpoint 에 도달하지 못하면
> `undefined` → `go` 가 **이동하지 않는다**(exit 로 가지 않음).
> Continue = `다음 breakpoint 또는 끝까지`, next/prev bp = `breakpoint 사이 이동`.

**N7. `continueRun` 의 `isForbiddenTarget` 누락** — ✅ **적용 (2026-10-01)**
applyTick 경로는 검사하는데 `continueRun` 만 빠져 merge/loop_exit/φ/exit 에 멈출 수 있다.

> **적용**: 정지 조건에 `&& !isForbiddenTarget(n)` 추가. 겸사겸사 `visited` 가드도 넣었다
> — back_edge 를 거르므로 지금은 사이클이 없지만 N2 에서 `succ` 를 손대면 바로 필요해진다.

**권장 순서 / 진행 상태**
```
✅ 즉시(독립)  : N7 → N5 → N1 → N6     ← 2026-10-01 적용 완료
✅ 그 다음      : N3 → N2               ← 2026-10-01 적용 완료 (F43·F44 선행 필요했음)
✅ 별개 덩어리  : N4 (+ Call Stack)      ← 2026-10-01 적용 완료 (F49·F50 선행)
```

**→ navigation N1~N7 전부 완료.** 남은 것은 **브라우저 육안 확인**과
**평가 재측정**(F43·F45·F46·F47 이 루프 결과를 바꿨다). 재귀 감지·표시는 보류(백로그 ⑨).

**N1·N5·N6·N7 검증 (2026-10-01)**
- `npx tsc --noEmit` → **0 errors**.
- `scratchpad/navsim.py` — TS 규칙(`forwardLive`/`isBottom`/`isForbiddenTarget`/
  `walkToBreakpoint`)을 **실엔진 CFG 위에서** 재현하는 파이썬 시뮬레이터
  (`engine_api.analyze_once(..., debug_values=...)` 결과를 그대로 먹인다).
  브라우저 육안 확인 전에 **로직만** 떼어 검사하는 용도.
- `synth/NavDead.sol` (`require(a > 100);` 뒤 `if (a < 5)`), `a ∈ [0, 2^64-1]` 시드:

  | 지점 | successor | live | 판정 |
  |---|---|---|---|
  | `require_condition_7` | `ERROR`, `require_true_7` | `require_true_7` | revert 분기 제외 ✅ |
  | `if_condition_9` | `if_true_9`, `else_block_11` | `else_block_11` | **dead then-분기 제외** ✅ |

  `if_true_9` 의 env = `{a: ⊥, r: ⊥, total: ⊥}` → `isLineUnreachable` true.
  live 가 1개뿐이라 **하이라이트도 나오지 않는다**(N1 의 의도대로).
- N7: Continue → `require_condition_7`(flags=`['condition']`, 금지 플래그 아님)에 정지 ✅
- N6: entry→next bp = `Return_15` L15 ✅ / `Return_15`→prev bp(L8) = `Assign_8` ✅ /
  breakpoint 없음 → `None` = **이동 안 함** ✅

⚠ **함정 기록**: navsim 첫 실행에서 두 분기가 모두 feasible 로 나왔는데, 원인은 N1 결함이
아니라 **debug 값을 안 넣어서** 였다 — 시드가 없으면 노드 `state` 가 전부 비어 있어
⊥ 가 **생길 수 없다**. `isLineUnreachable`/`engineDead` 류 검사는 모두 "값이 들어온
뒤"에만 의미가 있다(`evaluate` 이후). 초기 로드 화면에서 dead 분기 표시를 기대하면 안 된다.

⚠ **남은 것**: 브라우저 육안 확인(`.succ-line` 색, 빈 원 글리프, hover 메시지).

**논문 서술 주의 (N4 미구현 상태로 제출할 경우)**
- §call navigation 전체를 **"설계"** 로 표기
- debugger state 의 "optionally call-context information" → **call stack 자체가 없음**
- ⊤ 출처 설명 금지 — `TopVar.provenance` 는 `"현재 엔진엔 없음 → null"`
- `FalseRegions` 는 **출력공간**이며 **Warning + 단일 During 절**일 때만 존재
  (입력 파라미터 구간으로 읽히면 안 됨 — 입력공간 역전파는 Plan B 몫)
- backward 는 "predecessor 선택" 이 아니라 **동시 하이라이트**이고 **navigation history 없음**

### ⑦ 폴리시 / 작은 것
- ~~`continueRun` 이 `isForbiddenTarget` 를 안 본다~~ → **N7 로 해소 (2026-10-01)**.
- `@During` 라인-클릭 부착 미구현 (현재 라인번호 수동 입력).
- try/catch pre-state 의미 미검증 (#33 잔여).
- 비연속 다중영역 동시편집 미검증.
- advanced value types(array/bytes/enum) 입력 UI 스텁.
- `_make_bottom` 이 symbolic bytes(`msg.data`/`msg.sig`)엔 BOTTOM 표현이 없어 `None` 으로 직렬화
  (표시만, 도달불가 env 안이라 무해). #42 잔여.
- 앱 **최초 마운트** 시점엔 아직 mock 시드 함수 목록을 쓴다(초기 파일이 mock 소스라 결과적으로 일치).
  파일 열기/전환/편집 중 하나만 일어나도 갱신. 필요하면 App 마운트 훅. #44 잔여.
- **브라우저 육안 확인 전반 미완** — 특히 루프 함수(mock 에 루프가 없어 실엔진 필요),
  `⊥` 표시(#42 로 새로 생김), opaque 라벨.

## A.3 논문 원고 상태 (`paper/Phd_thesis/main.tex`)

- KU B5 양식 이관 완료 + 원본 템플릿 결함 **7종 수정**(F1–F7, 파일 헤더에 기록).
  빌드 검증: 에러 0 · 경고 0.
- 제목 = **An Intent-Aware Quick Debugging Assistant for Solidity** (2026-09-17, 변경 가능).
  4곳(표지·속표지·초록 헤딩·`pdftitle`) 동기화. 국문 제목 미정.
- **목차 = 7 chapter + 3.x 까지 반영 완료**(2026-09-17). label 은
  `chap:` / `sec:<chap>:<slug>` / `subsec:<chap>:<slug>` 규칙 — ChatGPT 가 쓴 텍스트의
  `\Cref{...}` 가 그대로 맞물리도록 **이름을 함부로 바꾸지 않는다**.
  각 leaf 절에 `% plan:` 주석으로 다룰 내용(사용자 아웃라인의 bullet)을 남겨 뒀다.
- 참고문헌 = `Bibliography`(목차·PDF 북마크 등재), BibTeX + `../references.bib`.
- `Appendix A: Typesetting Reference` 는 **삭제용 스모크 테스트**(리스팅·알고리즘·정리·추론규칙·
  TikZ·표·인용·색인을 한 번씩 사용). 실제 부록을 쓸 때 제거.
- ⚠ 남은 TODO: 국문 제목, 영문/국문 초록, 헌사, Preface(공동연구·기출판 선언 — **필수**),
  Acknowledgment, 학위수여 연월·심사본 마감·심사일, 심사위원 5명.

---

# B. ⚠ 평가 자산 리스크 (구현 담당 기록)

§19 2단계("기존 benchmark 재사용 가능성 확인")에 대한 현재 답: **재사용이 그대로는 안 된다.**

1. **`evaluation/RQ1/run_all.py` 가 20/20 VIOLATED → 0/20 SATISFIED 로 회귀**했다.
   decision #37(문법에서 어노테이션의 `'//'` 제거, `LINE_COMMENT` 복원)의 의도된 대가이며, 패치하지 않기로 결정됐다
   ("RQ1 은 Guardian 복붙본이고 IntentKeeper 는 웹 기반이라 실험 방식을 다시 짠다").
2. 게다가 그 20건은 **IntentChecker 리비전의 74건 eligible 세트 이전 판**이다.
3. `temp/` 의 회귀 스크립트 13종(145 checks)은 **구조 회귀**다 — "CFG·states·문법이 안 깨졌나"를 보지,
   "실제 버그를 탐지하나"를 보지 않는다.
4. 따라서 **위반이 조용히 "만족"으로 뒤집히는 실패(#37 이 정확히 그랬다)를 잡아줄 그물이 지금 없다.**

→ **제안**: §19 의 1단계와 2단계를 완전히 순차로 두지 말고, `EngineSession` 에 구조화 intent/debug 값을 투입하는
experiment harness 를 **먼저** 깐다. Plan B feasibility 를 볼 때도 같은 하네스가 그대로 쓰인다(§19 3단계).
⚠ 단 Plan A 일정을 밀어내지 않는 선에서 (원칙 #1).

**Plan B 평가 설계 시 주의**: 자동 생성한 input range 를 *Violated 가 나오게* 튜닝하면 순환논증이 된다.
range 는 원하는 verdict 와 무관하게 생성하고, 못 찾은 경우(§9.1 우선순위 ②③으로 떨어진 비율)를 함께 보고해야 한다.

---

## B.1 도구 비교 평가 — 설계 확정 + 컴파일 게이트 (2026-10-05)

위 §B 는 "기존 benchmark 재사용이 그대로는 안 된다" 까지였다. 그에 대한 **구체적 답**이 이것이다.
전체 경위·근거는 `PROGRESS.md` decision **(51)**.

### 확정 (사용자 결정)

| | 도구 | 비고 |
|---|---|---|
| **정량** | **Hardhat 2.29.1 + Foundry 1.8.4** | 둘은 중복이 아니다 — hardhat 은 스텝 디버거가 **없는** "재실행+로그" 기준선이자 `setStorageAt`/`setNextBlockTimestamp` 로 **소스 수정 없이** 상태를 심는 유일한 경로, foundry 는 최속 + 테스트 하네스 중심 |
| **정성** | Remix · Solidity Debugger Pro | Remix 는 보류(시간 남으면 소스 수정 없이 되는 케이스만 정량). sdbg 는 CLI/headless/DAP 진입점 없음 + 라이선스 불명 |
| **데이터셋** | **IntentChecker expressible 48** | web3bugs 41 + numscout 7. `RQ3/rq3_comparison_table.csv` 48행 = `evaluation/RQ1/cases/` 의 어노테이션 보유 48개 |

**Remix 하강의 진짜 이유**는 UI 자동화 난이도가 아니라 **측정 전제**다. SolQDebug 의 Remix 하네스는
`set_<var>` setter 를 **대상 소스에 주입**해야 상태를 심을 수 있었고(= 피측정 코드 변형), Remix VM 에는
`setStorageAt` 도 타임스탬프 조작도 없다. 48케이스는 `@StateVar` 87개 / `@GlobalVar` 10개 / `@IReturn` 8개라
이 방식으로는 공정한 비교가 성립하지 않는다. 심사 질문에 쓸 한 문장은 decision (51) 에 적어 뒀다.

### 지표 — ⚠ **미확정 (다음 논의 주제)**

현재까지 합의된 것은 "**SolQDebug 때의 비대칭을 물려받지 않는다**" 뿐이다. 당시
우리 쪽은 edit trace 전체 wall clock, Remix 쪽은 `debug_open + jump_to_end` 만 total 이었다 — 서로 다른 작업 단위.

- **(a) E2E task latency** — 공정하지만 상대 수치 대부분이 compile+deploy 라 "당연한 결과" 로 읽힌다.
- **(b) 증분 재측정 latency** ← 구현 담당 권고. 한 줄 고친 뒤 값을 다시 볼 때까지. 우리 = `update`+`evaluate`
  1회 / 상대 = recompile→redeploy→state 재주입→re-tx→re-open. IQDebug 의 edit-time·증분 주장과 측정축이 일치.
- **(c) 순수 step latency** — 우리는 커서 이동에 엔진 호출이 0회(≈0ms)라 압도적이고, 그래서 신뢰를 잃는다. 언급만.
- **보조 ①「하네스 LOC」** = 동적 도구로 같은 값을 보려면 사람이 써야 하는 코드량(의존성 배포·상태 주입·
  internal 이면 래퍼·modifier 용 mock·호출·로그). 우리 쪽 대응물은 어노테이션 줄 수(이미 실측: 평균 4~5).
  ⚠ LOC 는 약한 프록시라 집계 규칙(공백·주석 제외, boilerplate 포함, 자동생성분 별도)을 미리 못박고,
  **「작성해야 하는 산출물 수」**(harness n개 / mock n개 / storage write n개 / 소스 수정 여부)를 함께 낸다.
- **보조 ②「구간 커버리지」** = `@StateVar` 는 **구간**이고 1회 분석이 그 전체를 건전하게 덮지만 동적
  디버거는 구체값 1개 = 점 1개. ⚠ **원래 형태로 쓰면 안 된다** — 구간 크기의 곱을 "필요 실행 횟수" 로
  내면 천문학적 허수가 되어 깎인다. 측정 가능한 형태: **구간에서 무작위 샘플링해 위반을 처음 관측하기까지
  필요한 실행 횟수(중앙값) + 예산 B회 안의 검출률**. 퍼징 대비 정적분석 비교의 표준 형태라 방어된다.
  (B 를 정하려면 48케이스의 구간 폭 분포를 먼저 떠야 한다 — 미실시.)

**시간 전제**: 우리 `[TIMING]`(`main.py:202`)은 `simulate_inputs` 만 감싸고 `load_dependencies()` 는
import 시점에 끝나므로 **dependency 분석 시간은 이미 측정 밖**이다(IntentChecker 전제와 일관).
비교 도구에도 "의존성은 컴파일·배포 완료" 를 대칭 적용하되, **타겟** 재컴파일·재배포는 측정에 **포함**한다
(그게 (b) 가 드러내려는 비용이다).

### 컴파일 게이트 — **48/48 통과** (프로젝트 33개)

`evaluation/Dataset/reassemble.py --build`. **소스 .sol 은 한 바이트도 바꾸지 않았다** — 디렉토리 배치·
remapping·solc 선택만으로 import 를 해결한다. 48케이스 → **서로 다른 프로젝트 33개**(w35 4건,
w5·w52·w62·w70 각 3건 공유)라 셋업 비용은 케이스당이 아니다.

그 과정에서 **평가 자산 결함 6종**이 드러났다. 전부 decision (51) 에 근거와 함께 기록했고, 논문에
반영해야 하는 것은 ★ 둘이다.

- ★ **numscout 7개의 "원본"이 원본이 아니었다** — `target_contracts_original/numscout_*` 은 IntentChecker 가
  축약·전개한 형태라 solc 가 못 읽는다(Nokon 62줄 vs Etherscan 271줄). Etherscan 검증 원문으로 교체(5개).
  **SwordCrowdsale 은 원문이 어디에도 없어** 35줄 단순화 재현본으로 대체 → **"simplified reproduction" 명시 필요**.
- ★ **`cases48.csv` 표기 오류 2건** — w77_H_01 의 타겟 함수는 `Exchange` 가 아니라 **`library MathLib`** 안에
  있고, w16_H_04 의 타겟 파일 실체는 `lib/LibBalances.sol`(`library Balances`)이다. 데이터셋 표 수정 필요.
- 복원 인터페이스 3개(`IWETH`·`IMarginTrading`·`IBentoBoxV1`) / 원 저장소에서 받은 contest 전용 4개 /
  solc 핀 1건(w42 SPDX) / 순환 import 2건(w36·w65). Guardian `Dependencies/*` 사본은 import 가 제거된
  pkl 분석용이라 **컴파일 소스로 0건** 사용.

### ⚠ 데이터셋 적합성 — 미해결 질문

48개는 IntentChecker 의 **intent 표현가능성**으로 고른 집합이고 **디버깅 요소로 고른 게 아니다**. 실측:

```
loop ≥1  12 (25%)   internal call ≥1  34   external call ≥1  41   branch ≥1  36
StateVar==0  8      pure/view  12          가시성: public 22 / external 9 / internal 12 / private 5
```

루프가 12건뿐이라 F43~F47 이 바꾼 루프·중첩루프와 N2/N3(loop fold) 를 **n=12** 로 말해야 한다.
구현 담당 제안 = **48 유지(비교·verdict) + 요소별 보강셋(정밀도·navigation)**. 보강셋은 intent 가
필요 없어(`@StateVar`/타겟 함수만 있으면 된다) 케이스당 비용이 절반 이하이고, 후보 풀도 충분하다
(`Dataset/Web3Bugs` contest 119개, `Numscout/Original` 34개, `LogicErrorContracts` 65개, `for`/`while`
포함 .sol 507개). 외부 호출 분류는 collect_metrics 의 `.method(` 방식이 아니라 **`engine_api._external_call_roots`
기준**(interface/contract-typed → opaque, library/internal → 하강)을 써야 F49 와 같은 잣대가 된다.
⚠ 보강 케이스는 엔진 미지원 형태(한 줄 블록, `else <stmt>;`)에 걸릴 수 있으므로 **엔진 통과 게이트**를
먼저 돌려야 하고, 거기서 떨어지는 비율 자체가 limitation 수치가 된다.

### 남은 작업

1. **hardhat 게이트** — 같은 `projects/` 를 hardhat 2.29.1 로도 컴파일(프로젝트 밖 소스 경로 허용 확인).
2. **Step 2 상태 주입** — `storageLayout` → 슬롯 계산 → `setStorageAt` / `@GlobalVar` 10건 →
   `setNextBlockTimestamp` / `@IReturn` 8건(4케이스) → mock 배포 / **internal 12건 → 상속 harness**(원본
   수정 없음) / **private 5건 → `internal` 패치 + 메타데이터 제거 바이트코드 diff 0 확인**.
   `public` 으로 바꾸면 디스패처 엔트리가 생겨 바이트코드가 달라지므로 **반드시 `internal`**.
   여기가 공수의 핵심이고, modifier 6건(`onlyOwner`/`onlyMember`/`onlyWhitelist`/`onlyAuction`/`nonReentrant`)
   은 권한 세팅·mock 이 더 붙는다.
3. **지표 확정** (위 ⚠) → 그 다음에 IQDebug 측 latency 하네스를 `engine_api` 연산별
   (`analyze`/`update` 1줄/`evaluate`/`verify`)로 작성. 현재 수치는 레거시 `main.py` 경로라
   **논문이 주장하는 경로와 다르다**.

---

# C. ⚠ #41 로 인한 RQ2 재산정 (구현 담당 기록)

`evaluation/RQ2/l4_l5_case_review.md` 는 34개 not-detectable 케이스를 분류하면서
**L4c·L4d 를 "산술 PostEntryExit 부재로 인한 grammar-limit"**, **G6 를 "다변수 불변식을 PostEntryExit 로 표현 불가"**
로 태깅했다. decision #41 ① 로 snapshot reference 가 arithmetic expression 의 first-class term 이 되면서
`balance(Exit) == balance(Entry) - amount` 류가 표현 가능해졌으므로, **이 태그가 붙은 케이스는 재판정이 필요하다.**

⚠ IntentChecker 가 심사중이라, 학위논문에서 분류를 갱신하면 제출 원고와 어긋난다.
**심사 결과를 기다릴지 / 학위논문에서만 갱신할지는 사용자·지도교수 결정 사항**이다(구현 담당이 정할 문제 아님).

---

# D. 문서 맵

| 문서 | 역할 | 상태 |
|---|---|---|
| `PROGRESS.md` | 엔진·구현 시간순 로그, decisions #1–#41 | 계속 append |
| **`PROGRESS2.md`** (이 문서) | 논문 방향 정본 handoff | 방향 바뀔 때 갱신 |
| `paper/Phd_thesis/main.tex` | 학위논문 LaTeX 골격 (KU B5 양식, 결함 7종 수정본). 확정 텍스트 삽입 대상 | 챕터 미정 |
| `temp/solqdebug-extension-direction.md` | 2026-06-12 방향 원문. **§7.4–7.7(LLM originality 헤드라인)은 §13 으로 폐기** | 참고용 동결 |
| `temp/direction-analysis.md` | **미채택** 두 방향(A/B) | 참고용 동결 |
| `evaluation/RQ2/l4_l5_case_review.md` | IntentChecker RQ2 케이스 리뷰 34건 | ⚠ §C 재산정 필요 |
| `Dataset/*.md` | 벤치마크 카탈로그(Web3Bugs·NumScout·LogicErrorContracts) | 참고용 |
| **`evaluation/Dataset/`** | 도구 비교용 평가 자산 정본 — `cases48.csv`(expressible 48), `target_original/`, `target_contraction/`, `Dependencies/{pool,contracts,interfaces,libraries,reconstructed,fetched}` | §B.1 (2026-10-05 신설) |
| `evaluation/Dataset/reassemble.py` | 48케이스 원본 → Foundry/Hardhat 프로젝트 33개 재조립 + `forge build` 게이트. **소스 내용 불변** | 48/48 통과 |
| `evaluation/Dataset/reassemble_report.json` | 프로젝트별 파일 출처·solc·`vpath_override`·build 결과 | 재생성물 |
| `evaluation/{forge,hardhat}/` | Foundry 1.8.4(`install.ps1` 로 재설치) / Hardhat 2.29.1 | bin·node_modules gitignored |
| `SolDebug/Proof_Read/main_proof.tex` | SolQDebug 최종 원고 (claim wording 확인용, §8.1) | 외부, 읽기전용 |
| `SolidityGuardian/paper/first_revision/main.tex` | IntentChecker 리비전 원고 | 외부, 읽기전용 |
