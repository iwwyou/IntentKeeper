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

### ⑦ 폴리시 / 작은 것
- `continueRun` 이 `isForbiddenTarget` 를 안 본다(`useNavigation.ts:165-176`). applyTick effect 는
  보는데(`:124`) 여기만 빠져 merge/loop_exit 에 멈출 수 있다. 한 줄.
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
| `SolDebug/Proof_Read/main_proof.tex` | SolQDebug 최종 원고 (claim wording 확인용, §8.1) | 외부, 읽기전용 |
| `SolidityGuardian/paper/first_revision/main.tex` | IntentChecker 리비전 원고 | 외부, 읽기전용 |
