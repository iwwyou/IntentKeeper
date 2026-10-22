# IQDebug 리팩터링 계획 — CFG 구성 / 추상 해석 분리

> 확정일 2026-10-21. 사용자·Claude·다른 LLM 논의 결과. 진행 상황은 이 문서 §6 과 `PROGRESS.md` 에 기록.
> 엔진 수정 이력은 `(to_solidityguardian)_engine_fixes.md`(F55~)에 함께 남긴다.

## 0. 목표

SolQDebug 에서 물려받은 "편집 시점 즉시 평가" CFG 구성을
**증분 구조 구성(편집 시점) + 디버깅 시점 추상 해석**으로 분리한다.

- forward reference(뒤에 정의된 callee/modifier)로 인한 CFG 손상 제거
- pending reinterpretation 제거
- 재귀 호출 비용 제한
- 변수 스코프와 추상 상태 의미론 정리
- 디버깅 실행 간 상태 격리
- 기존 intent 검증 체계 유지 (intent 문법은 변경 금지)

복잡한 interprocedural summary 나 Solidity 전 기능 지원보다 **정확·빠름·유지보수성**을 우선한다.
지원 대상 Solidity = **0.5 이상** (0.5 와 의미가 같은 0.4.x 1건 허용, 0.4 고유 의미는 미지원).

## 1. 확정된 결정

### D1. CFG 구성과 추상 해석 분리
- 구성 단계(편집 시점): 증분 파싱, CFG 노드·엣지, Statement/Expression IR 저장,
  함수·변수 선언 정보, lexical scope, modifier 참조 등록, 디버깅 슬롯 도출, intent 등록.
- 구성 단계에서 **하지 않는 것**: 식 평가, 내부 호출 inline 해석, `reinterpret_from`, 루프 fixpoint, 노드별 값 전파.
- 추상 해석은 디버깅 입력이 주어졌을 때 타깃 함수 진입점부터 수행한다.
- CFG 제어 흐름 구조 결정을 위한 구문·구조 분석은 구성 단계에서 수행한다.

### D2. ⊥ 의미
- ⊥ = **도달 가능한 concrete 상태가 없음**(γ(⊥)=∅). 그 외 용도로 쓰지 않는다.
- ⊥ 가 아닌 것: 미평가, 미지정 입력, 정밀 계산 불가한 정상 값, 배열 미지정 원소, 미지원 식, 엔진 오류.
- 모르는 정상 값 = typed ⊤. Solidity 기본값이 정해진 경우 = 정확한 기본값(0, false 등).
- 엔진이 처리 못 했다는 이유로 ⊤ 를 반환하지 않는다(그건 버그 또는 지원 범위 문제).
- 별도 reachable boolean 은 두지 않는다. 도달 불가 = env 가 ⊥. 판정은 서버 한 곳(`_is_bottom_env`)으로 모은다.
- 루프는 fixpoint 로 한꺼번에 계산하고, 수렴 후 상태와 loopDelta 로만 노출한다.

**미평가 상태(`None`) 불변조건**
1. 실행 사본 생성 시 모든 노드 `variables = None`(미방문).
2. "미방문"과 "⊥" 판정 헬퍼를 각각 하나로 모으고, 흩어진 판정
   (`_is_bottom_env({})`=False / narrowing `if not in_vars[node]` / `_pred_src` 빈 env 제외 / `x.variables or {}`)을 교체.
   해석 중 `None` 은 join 에서 제외, ⊥ 로 취급하지 않는다.
3. 해석 종료 후: ENTRY 에서 그래프상 도달 가능한데 `None` 인 노드 → 내부 버그로 예외.
   그래프상 경로가 없는 노드(return 뒤 dead code 등) → 명시적 ⊥.
   → 직렬화·Guardian 은 `None` 을 보지 않는다.

### D3. 내부 호출: 디버깅 시점 on-demand 해석
- 구성 시점엔 호출 식 IR 만 보존. callee CFG 존재 불필요. caller↔callee 사전 연결·재해석 없음.
- 함수 선언·FunctionCFG 는 소스를 읽을 때 정상 등록한다.
- 정적 이름/타입 해석(오버로드, 정적 인자 타입, 상속/override, library·using-for, super, `X(a)` cast/호출 판정, modifier 이름)은
  선언이 모두 들어온 뒤(analyze 이후) 언제든 가능하며, 해석 중 호출을 만나면 그 결과로 callee 를 inline 해석한다.
- pending reinterpretation 메커니즘 제거. 미해결 호출 ⊤ 폴백 전부 제거.
- 호출 dispatcher·context 관리는 통합하되 호출 종류별 Solidity 의미는 구분한다.

### D4. 진단 최소화
- 사용자 진단은 두 경우만:
  (a) 컴파일러가 거부할 의미·타입 오류(해석 중 확인된 미해결 callee/modifier, 오버로드 모호, 미선언 식별자 등) → evaluate 오류.
  (b) IQDebug annotation 규칙 위반(예: 루프 본문 intent) → annotation 거부.
- 편집 중 callee 미정의는 오류가 아니다.
- infeasible 경로의 미해결 callee 는 분석하지 않으므로 보고하지 않는다(입력별 결정적, path-insensitive 의미와 일관).
- 미지원 기능·내부 버그는 ⊤ 로 숨기지 않고 예외로 드러낸다(수정 대상).
- 공식 보수적 근사(D7, 함수 포인터, 미지원 Yul)는 정상 정책 — 진단 없음(내부 provenance 기록은 가능).

### D5. 상태변수 초기 환경
- 미지정 mutable 상태변수 = typed ⊤ (배포 후 트랜잭션으로 바뀌었을 수 있음, multi-tx 는 범위 밖).
- constant = 정적 값 유지. immutable = 알려진 값이면 유지, 아니면 ⊤. 전역 = 디버깅 값 또는 정의된 sound 초기값
  (non-payable 함수의 msg.value = 0).
- 현황: elementary 상태변수는 2026-10-20 에 이미 ⊤ 로 변경됨(`ContractAnalyzer.process_state_variable`).
  남은 것: 배열 inline initializer 평가값 사용, 동적 배열 길이 0, `_sync_constructor_state` 의 생성자 효과 반영.
- **생성자 타깃 예외(배포 전 의미론: 기본값·initializer·base constructor·상속 초기화 순서)는 맨 마지막 단계.**

### D6. modifier, try/catch, do-while 지원
- modifier: 구성 시점엔 독립 ModifierCFG + FunctionCFG 의 modifier 참조(이름, 인자 식)만 등록. splice 하지 않는다.
  뒤에 정의된 modifier 도 구성은 정상 진행.
- 디버깅 시점에 **실행 사본 위에서 합성(splice)**한다(continuation 모델 대신 기존 단일 그래프 해석기 재사용):
  - modifier 인자 = 합성 진입부의 `param = arg` 대입 노드
  - 여러 modifier = 선언 순서대로 바깥→안쪽 중첩
  - 본문 `return` = placeholder 후속으로 연결(반환 변수 유지, modifier 나머지 실행)
  - `_` 없는 경로 = 본문 미도달(자연 처리)
  - `_` 여러 개 = 본문을 placeholder 마다 복제(같은 줄 다중 노드의 상태 표시 방식은 미결)
  - modifier 지역변수는 D8 스코프로 분리
- try/catch, do-while: visitor ↔ analyzer ↔ 해석기 연결.

### D7. 재귀: Conservative Recursive Call Approximation
- 일반 내부 호출 = inline 해석. 활성 호출 스택에 같은 함수 identity 재진입 시(자기·상호 재귀) 즉시 근사, 추가로 펼치지 않음.
- 반환값 typed ⊤ / mutable 상태 havoc / constant·immutable 유지 / callee 가 pure·view 면 storage 유지 /
  인자에서 닿는 memory 객체·storage 포인터 인자 havoc.
- 인자 식의 부수효과는 근사 전에 정상 평가한다. 검사 위치 = 통합 호출 진입점, 인자 바인딩·callee 상태 초기화보다 먼저.
- fixpoint 가 아니다. 정상 반환 후 상태의 과대근사이며 정상 종료 보장과는 구분한다.

### D8. 지역변수 스코프와 join
- 0.5 lexical block scope. 블록 exit(분기 join, 루프 exit, back-edge)에서 그 블록 선언을 env 에서 제거(정규화).
- union join 코드는 유지. 정규화 후 키 집합 일치는 assert 로 검증.
- shadowing: 선언 시 바깥 binding 을 저장, 블록 exit 에서 복원(bare block 에서의 unsound 덮어쓰기 방지).

### D9. 함수 포인터·Yul
- 함수 타입 변수 호출 = D7 과 같은 보수적 근사. 함수 타입의 mutability 가 view/pure 면 storage 유지.
- Yul: 기존 지원 연산(산술·비교 `gt`/`lt` 등)은 정밀 유지. 그 외 연산만 보수적 근사:
  값만 내는 연산 = 결과 typed ⊤ / `sstore` = storage 전체 havoc / `mstore` 등 = memory 지역 객체 havoc.
  지원 목록·근사 목록을 코드에 명시한다.

### D10. 루프 본문 intent
- 루프 본문 `@During` 금지(연구 범위상 의도된 제한). annotation 단계에서 거부(D4-b).
  inline 해석과 standalone verify 에 동일하게 적용.

### D11. 판정
- 판정 = `Satisfied / Warning / Violated / Unreachable` (`engine_api.py:68`).
  Warning = 만족 증명 불가·위반 배제 불가(potential violation). ⊤ 는 Warning. 재귀 근사로 인한 Warning 은 정밀도 손실이지 unsound 가 아니다.

## 2. 의존성 빌드 (`evaluation/Dataset/build_project_deps.py`)
- D3·D6 으로 callee/modifier 선언 순서가 무관해지므로 `reorder_members` 는 **struct/enum 순서로 축소**
  (callable 재배치·오버로드 arity 처리 제거).
- 위상정렬 순환(F-E, interface↔구현) 문제는 별도로 남는다.

## 3. 범위 밖 / limitation
- 정밀 재귀 분석(summary fixpoint 등), 함수 포인터 정밀 dispatch, Yul 저수준 의미 전체, 정밀 alias 분석,
  multi-transaction, 루프 본문 intent, internal callee 안의 interface 호출에 대한 @IReturn 슬롯(슬롯은 타깃 함수 본문 한정).
- 논문 기술 시 구분: 보수적 근사로 지원 / 정밀 분석만 미지원 / 입력이 지원 범위 밖 / intent 언어에서 의도적 금지.

## 4. 구현 순서

| Phase | 내용 | 불변조건 |
|---|---|---|
| 0 | 기준선: 48 케이스 노드 상태·판정·디버깅 슬롯 JSON 덤프, 구문별 마이크로 케이스, 48 케이스 시간 프로파일 | — (알려진 버그도 기록만, 정답 취급 안 함) |
| 1 | 실행 격리: 1a = 타깃 실행용 fcfg 사본, 누수 제거(ireturn_registry, return_vals, before_envs, snapshot 의미, _states_cache 스코프), try/finally / 1b = library·this 호출의 오류 삼키기 제거 | 1a: 기준선과 동일(누수 차이 제외), A→B→A 동일 / 1b: 드러난 오류 보고 |
| 2 | IR 보존·기본 의미: `--`, 튜플 initializer, emit, unchecked, ⊥ 오용 정리(D2) | 항목별 차이 개별 확인 |
| 3 | 구성 단계 평가 제거: 스코프 트리(Scope(parent, decls), 노드 = (scope, 선언 수)), `process_*`·삭제 경로의 평가·`reinterpret_from` 제거, pending 제거, D8, `None`(미방문) 불변조건(D2) | CFG 구조 동일, 결과 = Phase 2 (스코프 밖 변수 제거만 허용), 슬롯 동일, 편집 순서 무관 동일 CFG |
| 4 | on-demand 호출 해석(D3): ⊤ 폴백 제거, cast/호출 정적 판정, 호출 진입점 통합 / modifier 실행 시 합성(D6) | |
| 5 | 재귀 근사(D7), 함수 포인터·Yul 근사(D9), 루프 본문 intent 거부(D10) | |
| 6 | try/catch, do-while 연결, 나머지 회귀 | |
| 7 | 생성자 pre-state(D5 예외) | |

## 5. 필수 테스트
- 구성 동등성: 같은 최종 소스에 대해 편집 순서(순서대로 추가 / caller 먼저 / callee 삭제 후 재추가 / 중간 삽입 후 삭제 /
  `} else {` 수정)가 달라도 구조·해석 결과 동일.
- 실행 격리: 입력 A → B → A 에서 첫 A = 마지막 A.
- 스코프: 한쪽 분기 선언, 블록 exit 소멸, shadowing(bare block 포함), 루프 지역변수, catch 파라미터, named return.
- 내부 호출: forward reference, 중첩 호출 식, overload, library, 상속, 자기·상호 재귀, 상태 변경, tuple 반환, memory/storage 참조.
- modifier: 함수 앞/뒤 정의, 다중 modifier, 다중 `_`, 인자, 본문 return, `_` 없음, 조건부 `_`.
- soundness: 작은 concrete 입력에 대해 실제 실행 결과가 추상 결과에 포함되는지(feasible/infeasible/정상 반환/revert/재귀 근사).

## 6. 진행 기록
- 2026-10-21: 계획 확정. Phase 0 착수.
  - 하네스: `evaluation/refactor/baseline_cases.py`(48 케이스, flush 마다 freeze fcfg → 노드 상태·슬롯·callee·시간),
    `evaluation/refactor/micro_cases.py`(구문별 36 케이스 + 실행 격리 A→B→A). 결과 `evaluation/refactor/baseline/`.
  - ⚠ `evaluation/intent_validation/run_cases.py:163` 이 커밋 상태에서 SyntaxError(정규식 `\n` 이 실제 개행으로 들어감).
    수정 = `r"//[^\n]*"` 한 줄. 하네스는 헬퍼를 복사해 의존하지 않음. (보고, 미수정)
  - 마이크로 기준선(micro_p0)에서 확인된 현 동작:
    - 틀린 값: `x--` 가 +1(incdec b=[14,24], 기대 [10,20]) / 튜플 선언 ⊤ / emit 인자 호출 효과 누락(counter [1,1], 기대 [2,2]) /
      modifier 미실행(counter [5,5], 기대 [6,6], a 미refine) / shadowing bare block unsound(x=[2,2], 기대 [1,1]) /
      break·continue 루프 s=[0,1] (기대 ⊇ [0,3], unsound 의심) / unchecked 언더플로 래핑 누락(b=[0,4]) /
      블록 밖 변수 잔류(x, for 의 i).
    - 예외: assert(`process_assert_statement` 인자 누락 TypeError) / do-while / try-catch / 뒤에 정의된 modifier /
      forward internal call(`logical_not` on UnsignedIntegerInterval = ⊤ 폴백) / struct 생성자 `P(a)` /
      자기 재귀(RecursionError) / 상호 재귀 / 함수 뒤 선언 상태변수.
    - 실행 격리 A→B→A 는 이 케이스에선 동일.
  - 코드 읽기 중 발견: library 호출(`Evaluation.py:2971`)·this 호출(`:3132`) 의 `except Exception` 이 **모든 내부 오류를
    심볼 문자열로 삼키고 컨텍스트 복원 없이 진행** — D4 위반, Phase 1b 에서 제거(결과 변화는 보고).
  - Phase 1 세부: 1a = 동작 보존 격리(타깃 실행용 fcfg 사본, snapshot 의미 수정, try/finally, ireturn_registry 소비 후 비움,
    `_states_cache` 키 스코프), 1b = 오류 삼키기 제거. `None`(미방문) 불변조건은 구성 단계가 값을 안 채우게 되는 Phase 3 로 이동
    (지금 넣으면 모든 `.variables` 읽기 지점을 먼저 정리해야 해서 동작 보존이 안 됨).
  - Phase 1a 완료(F55): legacy 46/48 동일. 3_H_04 Warning→Violated = 구성 시점 RETURN.return_vals(⊤ 입력)로 @Post 반환값을
    검증하던 버그 해소(입력 기준 3000≠2000). @IReturn 다음 회차 누수 해소. 시간 565s→432s.
  - Phase 1b 완료(F56): legacy 48/48 동일, rebuilt 42_H_01 실제 오류 노출 — `'denominator' not in struct
    'IDiscountProfile.discount_ret'` (보고, 미수정).
  - Phase 2 완료(F57): 48 legacy 판정 변화 0, 상태 변화는 전부 원인 확인(의도). rebuilt numscout_HIT 결과 생김(Violated, 일치).
    드러난 결함: BoostToken `_rOwned[_excluded[i]]` → AddressSet (길이 모르는 동적 배열 원소 접근, D5 동적 배열 과제와 연결).
    deps(프로젝트별) pkl 11개가 옛 unary 토큰 → Phase 3 후 deps 전체 재빌드 때 해소.
  - Phase 3a 완료(F58): 구성 단계 평가·재해석·pending 제거. 시간 451s→130s. 드러난 결함 다수(F58 ⚠, 아래 '보고 목록').
  - Phase 3b 완료(F59): D8 블록 스코프·shadowing, 지역변수 기본값, 튜플/다중반환/삼항식 침묵 처리 제거, env 복사 성능.
    48 판정 = 3a 와 동일.
  - **보고 목록(미수정, 사용자 결정 대기)**: (1) `} else {` 중괄호 소실(rebuilt 58_H_02) (2) for 루프 `continue` 후 흐름 unsound
    (3) callee 의 memory struct 참조 수정이 caller 에 미반영(memory_alias) (4) 한 줄 블록 `{ stmt; }` slicer 미지원
    (5) `process_payable_function_call`/`process_function_call_options` 가 `pass`(옵션 호출 문장 소실) (6) `address.transfer/send`
    미해결 멤버 (7) BoostToken `_rOwned[_excluded[i]]` → AddressSet (8) 42_H_01 `'denominator' not in struct 'cf'`
    (9) rebuilt 42_H_01 이전 오류 `IDiscountProfile.discount_ret`.
  - Phase 3c 완료: 미방문 노드 = 도달 불가면 명시적 ⊥, 도달 가능한데 미방문이면 예외. 루프 노드는 들어오는 흐름이 전부
    infeasible/⊥ 일 때만 ⊥.
  - Phase 4a 완료(F61): 호출 진입점 통합(`invoke_callee`, memory 참조 write-back), 미해결 호출 → 예외, modifier 디버깅 시점 합성.
    legacy 33/48 동일(판정 변화 = HIT 컴파일 불가 contraction, SwordCrowdsale 중복 `Ownable`). 시간 legacy 113s / rebuilt 35s.
- 2026-10-22: 결정 (사용자)
  - 보고 목록 (1)(2)(5)(6) 수정 승인, (7) 길이 모르는 동적 배열은 후속 과제로 미룸, (8) 원인 조사, `_` 다중 modifier 는 Phase 6 이후.
  - **평가 기준 = rebuilt(프로젝트별 deps) 모드로 일원화**, legacy 는 회귀 참고용. pkl 은 전부 재빌드(IR 영향 수정 확정 후 1회).
  - 원칙: 의미론적으로 올바른 설계가 기본, 임시방편은 선택지로만 제시.
  - 입력 전제: **입력 1개 = statement 1개**. `if (x) { return; }` 는 `if (x) {`⏎`}` 와 `return;` 두 입력이어야 한다.
  - using-for: 타깃과 같은 파일에서 라이브러리가 **뒤에 선언**된 경우는 오류로 취급(pkl 빌드는 위상정렬이라 무관).
  - 재진입: 외부 컨트랙트 → 타깃 호출은 고려 안 함. a → (외부) b → a 재진입은 **미정 — 후속 결정 목록에 모음**.
- Phase 4b (진행 중): (1) `} else {` — 저장소에 원문 보관(`SolidityAnalyzer._stored_text`), 문맥 판정은 앞 `}` 무시,
  `_function_span` 보정 제거. (2) for `continue` → 증감 노드, 증감 없는 for 의 body→join. (5) 옵션 호출 문장은 원래 정상
  (진단 오류) — 호출 없는 옵션식만 컴파일 오류 예외. (6) 원인 = `address payable` 타입명 불일치 → 방문자에서 `address` 로
  정규화; `.call/.delegatecall/.staticcall` = (bool ⊤, bytes) 튜플; 옵션 호출은 옵션을 벗긴 호출로 평가.
  (8) 원인 = interface 반환 조회가 `Dependencies/objectfile` 경로 하드코딩 → 프로젝트 deps 와 다른 판(`FloatStruct`) 혼입.
  하드코딩 pkl 폴백 4곳 제거(로드된 의존성만 조회).
  - 드러난 것: w36·w58·w65 deps 빌드가 `_topo_order` 예외로 pkl 0개였음(폴백이 공용 트리 SafeERC20 로 가림),
    Nokon 은 `using SafeMath` 뒤 선언, 70_H_04/10 `Cannot join intervals of different type lengths`(미조사),
    31_H_01 `.mul` 미해결.
  - 새로 발견: 중첩 루프 뒤 `continue`/`break` 가 안쪽 루프로 연결(감싸는 루프를 역방향 DFS 로 찾음) — 수정 방식 결정 대기.
- **후속 결정 목록(모아서 논의)**: a → b → a 재진입 모델, 길이 모르는 동적 배열, `_` 다중 modifier(Phase 6 이후).
- 2026-10-22 (2): 결정 (사용자) — **아직 미적용, 재개 시 이 순서로**
  1. 중첩 루프 `continue`/`break` 대상 = **문법적으로 감싸는 가장 안쪽 루프**(중괄호 체인 `_enclosing_open_brace_line` 을
     올라가 처음 나오는 for/while/do 줄의 조건 노드). forward/역방향 그래프 탐색 방식 폐기. 마이크로 `continue_nested` 로 검증.
  2. 입력 전제(1 입력 = 1 statement): **의존성 소스는 정규화 가능**(빌드 시 한 줄 블록·본문 없는 for/while 을 펴기 —
     대상: deps 의 `HIT.sol:140`, `LiquidityBasedTWAP.sol:25` 등). **타깃 컨트랙트·함수는 입력 쪽 책임** — 엔진은 위반 입력에
     명시적 오류(조용한 오분석 금지).
  3. using-for 뒤 선언: 오류 취급 유지(현 코드). 표현은 "증분 입력 순서 전제상 선언 전 참조 미지원". numscout_Nokon 은
     **contraction 에서 `library SafeMath` 를 컨트랙트 앞으로 이동**(데이터 수정).
  4. 미결: numscout_HIT 컴파일 불가 contraction 처리, 70_H_04/10 `Cannot join intervals of different type lengths` 원인 조사 허가.
  5. 그 뒤: w36·w58·w65 `_topo_order` 실패 조사 → deps/objectfile pkl 전체 재빌드(`reorder_members` struct/enum 축소 포함) →
     Phase 5.
  - 현재 작업 트리 상태: Phase 4b 수정(위 항목) 적용됨, temp 회귀 16/16 통과, 덤프 `baseline/p4b_{legacy,rebuilt}.json`,
    `micro_p4b.json`. 2026-10-22 프론트 기능(논문 main.tex 2957-3098) 검토로 잠시 전환.
- 2026-10-22 (3): 위 1~3 적용.
  1. `DynamicCFGBuilder._enclosing_loop`(중괄호 체인의 최내곽 for/while; do-while 안은 Phase 6 까지 명시적 오류, 루프 밖이면
     컴파일 오류) — continue/break 공용. `find_loop_condition` 삭제. 마이크로 `continue_nested`·`break_nested`·
     `continue_then_inner`·`while_continue` 모두 바깥/올바른 루프로 연결 확인.
  2. `Dependencies.main._one_statement_violation` — 슬라이서가 한 줄 블록·다중 문장·중괄호 없는 제어문을 명시적 오류로 거부
     (예전엔 다음 줄과 조용히 합쳐짐). 의존성 정규화 = `preprocess_contraction.normalize_one_statement_per_line`
     (`expand_single_line_blocks` 끝에서 호출 → `build_project_deps.prep` 경유). 전수 점검: 현재 평가 소스 중 위반은
     deps 3줄(HIT.sol:140, w5 Utils.sol:120, LiquidityBasedTWAP.sol:25) — 재빌드 시 정규화됨. target_contraction_auto 0건.
  3. `contraction_target.order_declarations` — 최상위 선언 안정 위상정렬(순환은 예외). 74 케이스 중 변화는 Nokon(SafeMath) 뿐.
     Nokon contraction·case 재생성 → rebuilt Warning 복귀.
  - **보고(결정 대기)**: (A) 정수 폭 암묵 변환 부재 — 70_H_04/10 원인. 선언 타입 폭으로 변환하지 않고 산술은 왼쪽 피연산자 폭을
    씀 → uint112 반환값을 uint256 변수에 담은 뒤 곱셈이 112비트에서 overflow → 112비트 ⊤ (**unsound**).
    (B) deps 빌드 순환(w34·w36·w58·w65) — 원인은 interface 끼리의 **타입 전용 참조** 간선(합법적 상호 참조).
- 2026-10-22 (4): (A) 정수 암묵 변환·공통 타입 승인·적용(F63). (B) deps 빌드 순서는 사용자가 다른 LLM 과 논의 중.
  - 결정 대기: ① 초기화식 있는 mutable 상태변수 = 초기값 유지 vs D5 대로 ⊤ ② 범위 인덱스 쓰기 unsound·다중 반환 join 폴백 수정 시점
    ③ `_pow_fits` 정밀도. 재빌드 대기: legacy 3_H_05(옛 pkl 초기값 폭).
  - 덤프: `baseline/p4c_{legacy,rebuilt}.json`, `micro_p4c.json`. legacy 41/48·rebuilt 44/48 동일(p4b 대비).
