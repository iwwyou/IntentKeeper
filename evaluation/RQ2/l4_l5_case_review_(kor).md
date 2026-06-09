# L4/L5 Case-by-Case Deep Review

**대상**: 34개 not_detectable cases (L4a 10, L4b 8, L4c 1, L4d 1, L5a 7, L5b 7)
**목적**: 각 case의 audit report + source code를 바탕으로 분류 타당성·근본 원인 재검토, paper (Introduction / RQ2 / Discussion) 반영용 insight 도출.

---

# Paper-Ready Insights (누적)

아래는 case 분석에서 추출된 **교차 관찰** — 논문 본문(RQ1 / RQ2 / Discussion)에 바로 인용·편집 가능한 형태. Case별 상세는 하위 섹션 참조.

## I1. Annotation grammar ≠ Abstract interpretation 엔진

**관찰** (Case 1 유래): IntentChecker에는 두 개의 분리된 언어 계층이 있고 paper 본문에서 혼동될 위험이 있음:

- **분석 엔진 (abstract interpretation)**: `**`, 비트 연산, 루프, external view 호출 등 풍부한 Solidity 연산을 soundly 추상화 가능.
- **Intent annotation grammar**: 변수·정수 리터럴·interval `[a,b]`·`+ − × / %`·괄호만 허용 — 엔진이 다룰 수 있는 것의 **엄격한 하위집합**.
- **Debug annotations** (`@StateVar`, `@LocalVar`, `@IReturn` 등): **분석 엔진을 위한** 값 공급 장치. Intent annotation grammar를 확장하는 수단이 아님. 두 layer는 설계상 독립.

**Paper 반영**:
- Figure 6 (grammar BNF) 캡션에 한 문장 — annotation grammar의 단순성이 의도된 design choice이며 엔진 제약이 아님을 명시.
- RQ2 opening — 두 axis(engine expressiveness / annotation expressiveness) 분리 선언.
- L4a·L5 본문에서 "IntentChecker가 `**`를 지원 안 함" 같은 표현 금지 — "annotation grammar가 `**`를 포함하지 않음"으로 정확히 표기.

## I2. L4a / L5a 판정 기준 — "전지적 개발자 테스트" (I7과 함께 읽을 것)

**판정 기준** (Case 2 유래, Case 4에서 정제):
> 버그를 정확히 알고 있는 개발자가 grammar만 가지고 **정답 intent를 직접 표현하는** annotation을 작성할 수 있는가?
> - **가능** → **L5a/L5b** (*behavior deficit*): annotation 표현 가능, "어떤 annotation을 쓸지" 결정이 버그 인지 전제.
> - **불가능** → **L4a** (*expressibility deficit*): 전지적 개발자조차 intent를 직접 표현할 수 없음.

**중요 단서 (Case 4에서 교훈)**: "grammar-expressible distinguishing annotation의 존재"만으로 L5 결론 내리면 안 됨. Local proxy annotation이 우연히 distinguishing power를 갖는 경우까지 포함하면 분류가 무의미. **Intent-level expressibility** 요구 (→ I7).

**Paper 반영**:
- L4a·L5a 도입부에 정제된 기준을 공식 판정 룰로 선언.
- L5a 본문: "bug-awareness required"는 **증상**이고 원인은 "annotation 공간이 충분히 풍부해 선택이 의미를 갖는다".

## I3. L4a 내부 primary blocker — 세 갈래

**세 축** (Case 1·2·3·4 유래):

- **(α) 변수-관계에 함수 호출이 포함 (Case 1, Case 3 유형)**: scope에는 correct 관계식에 기여하는 변수들이 있으나, 관계 자체가 **함수 호출 결과**(external interface view 또는 internal view)를 피연산자로 요구. intentValue는 변수·상수만 허용하므로 함수가 관계 안에 들어갈 수 없음.
- **(β) 관계 맺을 변수 자체 부재 (Case 2 유형)**: correct RHS가 가리키는 도메인(예: underlying token decimals)에 대한 **proxy 변수가 scope·컨트랙트 어디에도 없음**. RHS가 scope 변수의 기여 없이 "literal + 외부 값"으로만 구성.
- **(γ) Multi-point accounting을 single-point annotation으로 표현 불가 (Case 4 유형)**: 버그가 단일 라인 수식 오류가 아니라 **여러 external call의 조합적 net effect**. 각 call의 local arg는 유효하지만 net이 의도와 다름. Intent는 multi-point balance 변화 — single-point annotation으로 포착 불가. External state(ERC20 balance 등) 의존 경우 많음.

**공통**: 세 축 모두 pure annotation-only workflow에서 intent 직접 표현 실패.

**Paper 반영**:
- L4a 본문(line 1307) 재서술에서 세 축을 구분 언급 혹은 대표 case 열거.
- Discussion에서 grammar 확장 효과는 축에 따라 다름 — (α)는 제한적 함수 reference 허용으로 해소 여지, (β)는 코드 수정 필요, (γ)는 multi-point accumulator 개념을 annotation language에 도입해야 함.

## I4. L4a / L5 경계의 투과성 — auxiliary local 주입

**관찰** (Case 2·3 유래): 개발자가 **side-effect-free auxiliary local**을 production code에 주입하면 (e.g., `uint256 D0 = _computeLiquidity(...)` 혹은 `uint8 uD = IERC20(...).decimals()`), scope landscape가 확장되어 annotation이 grammar-expressible해짐. 그러나 주입 결정 자체가 "이 값이 correctness에 중요하다"는 판단 → 버그 인지 전제 → **L5 영역으로 이동**.

**함의**: L4a / L5 경계는 **pure annotation-only workflow** 전제 하에서만 고정. "annotation-driven refactor" (annotation 작성 위해 auxiliary 변수 도입 허용) 환경에서는 L4a 다수가 L5로 재분류됨.

**Paper 반영**:
- Discussion/future work에서 "annotation-driven refactor" 워크플로우를 대안으로 제시 — grammar 확장보다 실용적일 수 있음.

## I5. "Silent sanction" 위험 — fail-by-confirmation mode (L4a 전반)

**관찰** (Case 3·4 유래): 개발자가 코드·natspec의 자연스러운 의도를 annotation으로 옮기면 **buggy 코드와 tautologically 일치**하는 경우가 발생. IntentChecker가 "올바르다"고 재확인하는 failure mode.

**두 failure mode**:
- **Mode-1 (fail-silent-by-omission)**: annotation 작성 시도 자체가 실패 → 아예 판정이 안 나옴.
- **Mode-2 (fail-by-confirmation, silent sanction)**: annotation이 grammar-expressible하고 buggy에서 Satisfied → 버그가 통과.

**Silent sanction 발생 양상** (case별):
- **Case 3 (29_H_05)**: Grammar의 rational-polynomial 표현 범위가 CP 공식 가족을 포함하고 이것이 buggy. "Grammar-algebraic coincidence".
- **Case 4 (39_H_02)**: L280 위 natspec "transfer premium minus fee from maker to sender"가 buggy 구현과 동기화되어 있어, natspec을 따라 쓴 annotation이 buggy를 validation. **Natspec-code consistency**.

**Paper 인용 가치**:
- 단순 grammar 확장이 Mode-2를 해소하지 못함.
- L4a를 "inexpressibility" 단일 메시지로 요약하면 Mode-2 위험을 숨김. Discussion에서 별도 언급 권장.
- Annotation-driven workflow는 **natspec review**와 함께 가야 함 — 자연스러운 intent가 buggy 구현을 따라가고 있지 않은지 점검하는 과정이 annotation 자체만큼 중요.

## I6. L4a 경계 관찰 — general form vs specific form

**관찰** (Case 2 유래): L4a case의 correctness 조건이 "parameter에 따라 달라지는 값"일 때, **특정 instance 고정** 시 상수 annotation은 grammar-expressible. 하지만:
- 모든 instance에 적용되는 단일 annotation → 외부 값 참조 필요 → **L4a**.
- Instance별 상수 박기 → 표현 가능하되 상수 = 정답 지식 → **L5a-flavored** (bug-awareness).

**함의**: "일반화된 intent annotation"의 표현력과 "특정 사례용 intent annotation"의 표현력이 구분되어야 하며, annotation 재사용성이 structural 한계의 다른 축을 드러냄.

## I7b. L4a/L5b 경계 재검토 — "Type A vs Type B" (미확정, 후속 정리 필요)

**발견 경로** (Case 5 분석 중 사용자 제안): L4a로 분류된 케이스를 "scope 내 proxy 변수 존재 여부"로 이분해 보면:

- **Type A (proxy in scope, correct 값에 가까운 변수가 있으나 현재 코드가 올바르게 활용 안 함)**: 이론적으로 `@Post return == correct_formula_using_proxy` 형태 annotation이 grammar-expressible 가능 → **사실상 L5b (wrong-code) 쪽이 맞을 수 있음**.
- **Type B (proxy 부재, correct 값과 연결될 scope·state 변수 자체 없음)**: grammar로 표현 경로 원천 봉쇄 → **L4a 정통**.

**현재까지 case 적용**:
- Case 1 (25_H_01): `source.decimals` struct field — **Type A 후보**. 기존 L4a 분류 재검토 필요.
- Case 2, 3, 4, 5: **Type B** 확인.

**미확정 사항**:
- Case 1이 Type A로 확정되면 L4a → L5b 재분류 필요.
- 나머지 L4a case(7개) 중 Type A가 더 있는지 전수조사 필요.
- "Proxy가 있으나 buggy 코드가 잘못된 변수를 사용" vs "proxy가 있으나 buggy 코드가 변수 자체는 맞게 썼으나 연산이 틀림"의 세분 기준 필요 가능성.

**함의 (paper 수준)**: 기존 I3 α/β/γ 삼분보다 이 **이분법이 더 cleanly cut**. "intent-level expressibility 가능 여부"를 scope 관찰만으로 기계적 판정 가능. 단 경계 모호한 case(struct 깊은 field, 상속 state 등)에서 운영 기준 필요.

**Paper 반영 (잠정)**:
- 전체 L4a 검토 완료 후 Type A/B 분포 통계 제시 — grammar 확장이 얼마나 해소할지의 상한.
- Discussion에서 "L4a 중 Type A는 grammar 확장보다 annotation_plans 작성 시 proxy 찾기 원칙 정립으로 해소 가능, Type B는 구조적 한계"로 분기 메시지.

## I8-pre. Classification priority: **L4 > L1-L3 > L5**

**원칙**: case가 여러 한계 축에 걸리면 **methodology 적용 가능성**이 가장 상위. 적용 불가 차원을 먼저 적용.

```
Pipeline 적용성 관점:
  (0) Intent annotation 표현 가능한가?  → 불가 시 L4 (파이프라인 진입 실패, tool silent)
  (1) 엔진이 abstract value 계산하는가? → widening/TOP 시 L1-L3 (Warning 발생, signal 있음)
  (2) 대조 verdict 산출하는가?         → 작성된 annotation이 bug 인지 전제면 L5
```

- **L4 primary**: annotation을 쓸 수 없음 → Satisfied/Warning/Violated 어느 verdict도 없음 → tool이 해당 함수에 침묵. **Methodology 자체의 적용 불가** — 가장 근본적 한계.
- **L1-L3 secondary**: annotation은 쓸 수 있음. Engine이 widening/TOP이라 Warning 발생. 최소한 "뭔가 이상" signal 제공.
- **L5 tertiary**: pipeline 작동. 단, 작성된 annotation의 *방향*이 정답에 맞아야 의미.

**실용적 함의**:
- Case가 L4 + L1-L3 둘 다 해당 시 **L4로 분류**, L1-L3는 secondary note.
- 즉 L4 확정 case에 대해 L1-L3 실험 불필요 (Case 6의 newBalances loop widening 실험 등).
- Paper narrative: L4가 main novel contribution (annotation language 표현력 한계 → future direction: grammar 확장). L1-L3는 공통 AI 도구 과제라 덜 distinctive.

---

## I9. `.arg[n]` 채널은 lint-level, L5b 판정 근거로 사용하지 않음

**발견 경로** (Case 4·8 연쇄 재검토): `.arg[n]` intent annotation이 grammar-expressible하여 buggy/correct arg 순서를 구분할 수 있음. 그러나:

- **성격**: `.arg[n]`은 **소스 코드의 argument identifier 선택**을 검사. 프로그램 **값**의 의미를 검사하는 semantic intent와 성격이 다름. 본질적으로 **lint-style pattern check**.
- **기존 도구와 overlap**: Slither 등 pattern-matching 정적분석이 이미 covers. IntentChecker의 고유 기여 영역 아님.

**Paper 분류 원칙**:
- `.arg[n]`으로 catch되더라도 **L5b 분류 근거로 쓰지 않음**.
- L4a/L5 경계는 **semantic intent 채널** (return value 의미, state change 의미)에서 판정.
- 즉 `@Post returnExpression == correct_expr`, `@Post changed(stateVar, true)` 등에서 correct_expr이 표현 가능한가로 L4a/L5 결정.

**적용 예시**:
- Case 4 (39_H_02): semantic intent(net flow) 표현 불가 → **L4a**. `.arg[n]` 있어도 무관.
- Case 8 (61_H_01): semantic intent(`_ratioOfPrices` 의미) 표현 불가 (@IReturn arg-indifference로 엔진이 buggy/correct 구분 못 함) → **L4a**.
- Case 7 (59_H_05): semantic intent(pre-penalty maltQuantity) 표현 불가 → **L4a**.

**대조 (기존 L5b 예시들)**:
- 52_H_15 (pool swap arg order): `.arg[n]`으로만 catch 가능. 이 원칙 적용 시 **L5b 지위도 재검토 필요** — 어쩌면 L4a로 재분류 대상.
- 113_H_05 (require 연산자): 단순 비교 연산자 오류. `.arg[n]` 아닌 semantic 비교로도 가능한지 검토 필요.
- 35_H_11 (struct field 오류): 비슷하게 재검토 필요.

**미해결 (후속 case에서)**: 기존 L5b 분류들도 이 원칙 하에서 L4a로 재분류될 가능성. L5b 섹션 검토 시 체계적으로 재평가.

**Paper 함의**:
- L5b를 "detectable with bug awareness"로 feature하려면 semantic-level annotation이 가능해야 함.
- `.arg[n]`만으로 catch되는 경우는 IntentChecker novelty에 포함시키지 말 것.

---

## I8. Value error vs Algorithm error × Type A/B (Paper narrative의 주 matrix)

**용어 선택 근거**: Paper Introduction·Background는 "numeric logic error"를 상위 umbrella로 사용. 이와 계층 충돌 없이 sub-class 구분하기 위해 **"algorithm error"** 사용 ("logic error"는 umbrella 전용 용어).

```
numeric logic error (umbrella)
├── value error      : 상수·피연산자·단일 값 오류 — 한 줄 수정
└── algorithm error  : 공식 선택·flow 구성·decomposition 누락 — 구조 수정
```

**목적**: "IntentChecker가 무엇을 풀고 무엇을 못 푸는가"의 대칭적 narrative 제공. I1–I7은 blocker-side 편향이었으므로 이를 **solvable ↔ unsolvable** 양방향 구조로 재편.

**두 축**:
- **Value error vs Algorithm error** (fix 크기·성격 축):
  - Value error: 특정 location의 상수·피연산자가 틀림. Fix = 한 줄·한 값 교정.
  - Algorithm error: 공식 선택·flow 구성·decomposition이 틀림. Fix = 알고리즘 재구조 혹은 multi-line 재작성.
  - 경계 case 존재 (한 줄 fix이나 의미는 flow 설계 교정 등).
- **Type A vs Type B** (scope 내 proxy 존재 축, I7b):
  - Type A: proxy 변수 존재 → 기존 scope에서 annotation 가능.
  - Type B: proxy 부재 → scope 밖 값 필요.

**2×2 matrix (잠정)**:

|  | Value error | Algorithm error |
|---|---|---|
| **Type A** | 기존 scope var로 `@Post == correct_value` 표현 가능 → 주로 **L5b (detectable)** | 기존 scope var로 post-condition 구성 가능 → **L5a (missing-code detectable)** |
| **Type B** | 필요 value가 scope 밖 → **L4a axis β** — future: proxy 발굴 원칙 | 알고리즘 decomposition 필요 → **L4a axis α/γ** — future: annotation-driven refactor / sequential grammar |

**지금까지 5 case 잠정 매핑**:
- Case 1 (25_H_01): Value error / Type A 후보 (Case 1 재검토 시 확정).
- Case 2 (25_H_05): **Value error / Type B**.
- Case 3 (29_H_05): **Algorithm error / Type B** — 단일 단계 (wrong formula choice).
- Case 4 (39_H_02): **Algorithm error / Type B** — cross-line fee flow composition.
- Case 5 (51_H_04): **Algorithm error / Type B** — multi-step decomposition missing.

**Paper narrative 전략**:
- **RQ1 (solvable)**: Type A 영역 대부분 + Type B 중 grammar-expressible 부분.
- **RQ2 (unsolvable)**: Type B cell별 분기 메시지:
  - Value/B: proxy 부재가 blocker → proxy 발굴 annotation 방법론 제안.
  - Algorithm/B: 재구조 필요 → grammar 확장 한계 + annotation-driven refactor 대안.
- **Discussion → Future direction**: cell별 해소 경로가 질적으로 다름을 축으로.

**주의**: matrix를 엄격한 partition으로 강제하지 않음. 경계 case는 **주 관점**만 기록, 34 case 전체 검토 완료 후 **summary 섹션에서 cell별 집계 + 대표 예시** 선정. 현재는 각 case §5에 `**[Category]**` 태그만 달아둠.

## I7. Formal expressibility ≠ Intent-level expressibility (L4a/L5 경계의 진짜 기준)

**발견 경로** (Case 4 재검토 중): I2 "전지적 개발자 테스트"를 순수 formal criterion ("grammar-expressible distinguishing annotation 존재?")으로 적용하면, **local proxy annotation**이 우연히 distinguishing power를 갖는 케이스까지 L5로 분류하게 됨 → 분류가 의미를 잃음.

**교정된 criterion**:
- **Formal expressibility**: grammar가 어떤 형태의 distinguishing annotation(proxy 포함)을 허용하는가? (약한 조건)
- **Intent-level expressibility**: grammar가 **정답 intent를 직접 표현하는** annotation을 허용하는가? (강한 조건, L4a/L5 경계의 진짜 기준)

**Case 4 적용**:
- Formal: `@During .arg[2] == premiumFilled` 존재 → 표현 가능.
- Intent-level: 진짜 intent는 "sender net flow = premiumFilled - fee" (외부 ERC20 balance) → 표현 불가 → **L4a**.
- Local `.arg[n]` proxy는 cross-line 역산 + 외부 표준 지식 + natspec override로 얻어지는 derived form이지 intent 자체가 아님.

**Paper 반영**:
- I2 판정 룰을 intent-level 기준으로 rewrite.
- RQ2 opening 혹은 L4a 도입부에 "formal proxy annotation이 우연히 distinguishing하는 경우도 있으나 분류는 intent-level에 의해 결정됨"을 명시. 리뷰어 challenge 방어.
- Discussion — intent-level expressibility 개념이 IntentChecker design philosophy의 핵심임을 강조 (annotation은 intent를 옮기는 언어이지 구현을 덮는 test가 아님).

---

Grammar 제약 빠른 참고 (**paper revision 기준, `**` 포함**):
- **intentValue**: 변수(member/index access 포함) · 정수 리터럴 · `[a,b]` · `+ - * / % **` · 괄호.
- **불가**: 함수 호출, 비트 연산(`<<`, `>>`, `&`, `|`, `^`), 사용자 정의 호출, scope 밖 변수.
- **Debug annotations**: `@IReturn`은 view/pure interface 호출에만. Intent grammar와 독립 (I1 참조).
- **변경 사항 (기록용)**: 초기 작성 시 `**` 미지원 가정이었으나 paper revision에서 추가 예정. 그 이전 case (1, 10)의 G2_annotation_only 태그는 **더 이상 blocker 아님**. 다만 G1 (함수 호출)·G3 (scope 부재) 축은 불변.

근본 원인 G-카테고리:
- **G1** grammar 내 함수 호출 부재
- **G2** grammar 내 비트·지수 연산 부재
- **G3** intermediate variable 코드에 없고 grammar로 도출 불가
- **G4** 상태 변경 자체 없음 (view/pure, library, 외부 위임)
- **G5** buggy/correct 질적 동일 · 양적 차이 (`changed`/entry-exit 구분 불가)
- **G6** 다중 변수 invariant (곱 보존 등) PostEntryExit 표현 불가
- **G7** 버그 인지 전제 (정답 annotation = fix 지식)
- **G8** 외부 contract state 의존 (`@IReturn` 허용 범위 밖)
- **G9** 기타

---

## L4a — Inexpressible Expected Value (10 cases)

---

### Case 1 — `web3bugs_25_H_01` (현재 분류: **L4a**)

#### 1. Audit report 인용

- **출처**: `reports/25.md` → `[H-01] CompositeMultiOracle returns wrong decimals for prices?`
- **Severity**: High. **Warden**: cmichel (C4 2021-08-yield micro)
- **핵심 주장 (원문 발췌)**:

  > The `CompositeMultiOracle.peek/get` functions seem to return wrong prices. A single price is computed as:
  > ```
  > (priceOut,_) = IOracle(source.source).peek(base, quote, 10 ** source.decimals);
  > priceOut = priceIn * priceOut / (10 ** source.decimals);
  > ```
  > Assume all oracles use 18 decimals and `source.decimals` refers to the token decimals of `source.source`. Going from USDC → DAI → USDT (`path = [DAI]`) starts with price `1e18`:
  > - `_peek(USDC, DAI, 1e18)`: `priceOut = 1e18 * 1e18 / 1e6 = 1e30`
  > - `_peek(DAI, USDT, 1e30)`: `priceOut = 1e30 * 1e18 / 1e18 = 1e30`
  >
  > Final `value = 1e30 * 1e6 / 1e18 = 1e18` = 10^12 USDT. Inflates USDT by 10^12.
  >
  > The issue is that `peek` assumes the final price is in 18 decimals (`value = price * amount / 1e18`) but `_peek`/`_get` don't enforce this.

- **권고된 수정안**:
  ```solidity
  priceOut = priceIn * priceOut / (10 ** IOracle(source.source).decimals());
  ```
  — 분모를 "오라클 자신이 말하는 출력 precision"으로. Sponsor(alcueca)는 이후 "모든 하위 oracle이 18 decimals를 갖도록 강제"하는 invariant로 patch.

#### 2. 코드 의미 이해

##### (2a) Contract 목적 & 시스템 위치

`CompositeMultiOracle` — Yield Protocol v2의 **가격 집계기(price aggregator)**. 직접 pair가 없는 A→B 가격을 구할 때 `paths[A][B] = [X₁, X₂, …]` 경유점으로 여러 하위 `IOracle`을 **곱셈 체이닝**하여 합성 환율을 얻음. Yield의 vault 담보 평가·liquidation·CR(collateralization ratio) 계산의 **가격 진실 공급원**.

##### (2b) 함수의 컨트랙트 내 역할

두 private helper:
- `_peek(base, quote, priceIn, updateTimeIn) → (priceOut, updateTimeOut)` (line 110–118, view)
- `_get(...)` (line 120–128, `_peek`의 mirror — `.peek` 대신 `.get`)

공개 `peek`/`get` (line 74–108)가 path를 순회하며 각 홉마다 이 helper를 호출. 즉 **체이닝의 단일 단계**를 curried multiplier로 수행.

**`base`/`quote` 용어가 두 층위에서 재사용됨에 주의** (이 case 이해의 핵심):
- **공개 `peek(base, quote, amount)` 관점**: `base` = 변환 출발 토큰(A), `quote` = 변환 도착 토큰(B). 사용자 관점의 최종 "A→B".
- **내부 `_peek(base, quote, …)` 관점**: 한 홉만 처리. `base`는 "이번 홉의 출발", `quote`는 "이번 홉의 도착". path 순회 중 **이전 홉의 도착이 다음 홉의 base로 바뀜** (line 84 `base_ = path[p]`). `base_`가 경로 위를 전진하는 포인터 역할.

##### (2c) 함수 의도 (수식 + 스케일 규약)

내부 환율 표현 규약: **`price`는 언제나 "rate × 10^18" 형태의 18-decimal fixed-point 누적 환율**.
- 시작값 `price = 1e18` (= rate 1.0, 아무 홉도 거치지 않음).
- 각 홉이 하는 일: "이번 홉의 raw 환율을 누적가에 곱하고 다시 18-dp로 정규화".

수식:
```
priceOut = priceIn    ×    raw_price_from_oracle    /   10^(output_scale)
           ^^^^^^^^        ^^^^^^^^^^^^^^^^^^^^^         ^^^^^^^^^^^^^^^^
           누적 환율(18dp)  이번 홉 환율(scale-dp)        정규화 divisor
```

**"priceIn을 곱한다" 직관**: rate composition. `USDC→USDT = USDC→DAI × DAI→USDT`. 각 홉은 자기 몫만 제공, 누적은 곱셈.

**"18 decimals로 정렬한다" 직관**: 오라클이 `10^scale`로 부풀린 숫자를 돌려주므로, 같은 크기로 나눠 다시 "순수 rate × 10^18"로 되돌림. 그래야 다음 홉 곱셈 때 스케일이 누적 오염되지 않음.

**Invariant (peek 계약)**: `peek(base, quote, amount) = value` ⇒ "`amount` 단위의 base 토큰은 현재 환율 기준 `value` 단위의 quote 토큰과 경제적으로 동등". `amount`·`value` 모두 각 토큰의 native integer representation (1 USDC = `1e6`, 1 DAI = `1e18`).

##### (2d) Line-by-line 분석 (`_peek` line 110–118)

```solidity
113  Source memory source = sources[base][quote];
114  require (source.source != address(0), "Source not found");
115  (priceOut, updateTimeOut) = IOracle(source.source).peek(base, quote, 10 ** source.decimals);
116  priceOut = priceIn * priceOut / (10 ** source.decimals);   // BUG
117  updateTimeOut = (updateTimeOut < updateTimeIn) ? updateTimeOut : updateTimeIn;
```

- **L113**: `sources[base][quote]` 조회 — `Source { address source; uint8 decimals; }`. `decimals`는 `_setSource`(line 131)에서 `IOracle(source).decimals()`를 snapshot — **의도상 하위 오라클의 출력 정밀도**.
- **L114**: source 미설정 시 revert.
- **L115**: 하위 오라클에게 "`10^source.decimals` 단위 base"의 quote 환산가를 요청 → `priceOut = raw_oracle_price`. 코멘트 "Get price for one unit"는 `source.decimals`를 **token decimals**로 전제한 표현 (cmichel 해석 지점).
- **L116 (BUG)**: `priceIn * priceOut / 10^source.decimals`. 분모의 의미론적 역할은 "오라클 출력 precision 제거"여야 하나, 변수 이름(`source.decimals`)이 모호. 실제 구현에서는 `_setSource`가 `IOracle.decimals()` 값을 넣어 수치적으로는 맞지만, **코드가 자기 의도를 표현하지 않아** 취약.
- **L117**: freshness 전파 (가장 오래된 updateTime 보존).

##### (2e) 버그의 근본 의미 (예시 포함)

**예시 A — 정상 동작** (`source.decimals == 18`, 모든 환율 1.0):

| hop | `priceIn` | sub raw | 계산 | `priceOut` |
|---|---|---|---|---|
| USDC→DAI | `1e18` | `1e18` | `1e18*1e18/1e18` | `1e18` ✅ |
| DAI→USDT | `1e18` | `1e18` | `1e18*1e18/1e18` | `1e18` ✅ |

최종: `value = 1e18 * 1e6 / 1e18 = 1e6` → 1 USDT. 정확.

**예시 B — cmichel 해석 (버그 시나리오)**: USDC source의 `source.decimals = 6` (토큰 decimals). 오라클 실제 출력은 여전히 18-dp.

| hop | `priceIn` | sub call | raw | 잘못된 나눗셈 | `priceOut` |
|---|---|---|---|---|---|
| USDC→DAI | `1e18` | peek(...,10^6) | `1e18` | `1e18*1e18/1e6` | **`1e30`** ❌ |
| DAI→USDT | `1e30` | peek(...,10^18) | `1e18` | `1e30*1e18/1e18` | `1e30` |

최종: `value = 1e30 * 1e6 / 1e18 = 1e18` → USDT 관점 `1e18/1e6 = 10^12` USDT. 1 USDC가 1조 USDT로 평가됨.

오류 지점: **첫 홉의 `/1e6`**. 오라클이 18-dp로 돌려준 숫자를 6-dp로 나눠 `10^12` 배율이 누적가에 주입, 마지막까지 남음.

**Protocol-level 결과**: Yield vault가 담보 평가 시 `value`를 담보 수량으로 사용 → 평가액이 `10^k` 배 부풀거나 축소 → 무담보 대출 혹은 정상 포지션의 즉시 liquidation → 양방향 자산 손실.

##### (2f) 올바른 fix

```solidity
priceOut = priceIn * priceOut / (10 ** IOracle(source.source).decimals());
```
분모를 "저장된 숫자 `source.decimals`"가 아니라 "지금 이 순간 하위 오라클이 말하는 자기 decimals"로. 변수명의 모호성과 무관하게 수학적으로 정확.

#### 3. IntentChecker annotation 시도

**(a) state variable 변화?** 없음. `_peek`는 view, `_get`도 storage write 없음. Post `changed`/entry-exit 대상 부재.

**(b) 올바른 반환값을 arithExpr로?**
```
@Post returnExpression == priceIn * priceOut_raw / (10 ^ IOracle(source.source).decimals())
```
- `10 ** x` / `10 ^ x` → **G2** (지수 부재).
- `IOracle(source.source).decimals()` → **G1** (함수 호출 부재). `@IReturn`으로 view call 공급을 시도해도 결과를 `**`와 함께 쓸 방법이 없음.
- 하위 raw `priceOut`은 `@IReturn`으로 공급 가능하지만 `10^decimals` 나눗셈 표현 자체가 막힘.
- 우회로 `1e18` 하드코딩 → 코드에 없는 invariant를 annotation이 선행 주장하는 꼴, 의미 왜곡.

**(c) 버그 인지 전제?** 표현 불가 단계에서 막힘 → L5 후보 아님.

**예측**: 어떤 형식이어도 파싱/표현 불가 → buggy/correct 양쪽 판정 없음.

#### 4. 분류 타당성

- 현재: **L4a**. ✅ 유지.
- blocker 본질: 올바른 분모가 `10^IOracle(...).decimals()` — **지수 + 함수 호출** 조합에 의존. 새 중간값이 target 함수 scope 밖 (`_setSource`에만 있음).
- `annotation_plans.md` line 360의 "Interface call은 이제 지원되어 ... TOP이 아님" 설명은 맞지만 **진짜 blocker인 G1/G2/G3**를 가리는 면이 있음 → 보강 필요.

#### 5. 근본 원인

**본질 (impedance mismatch)**: IntentChecker의 intent annotation은 **함수 trace 상에 실제로 존재하는 값들 사이의 1차 관계**를 표현하는 변수-관계 언어. 즉 허용되는 피연산자는 (i) 함수 local/parameter/storage 변수, (ii) 정수 리터럴, (iii) `@IReturn`으로 label된 **코드에 이미 있는 호출**의 반환. 반면 이 버그의 correctness 조건은 `IOracle(source.source).decimals()` — **함수가 호출하지 않는 함수**의 반환값 — 에 대한 관계. 즉 "annotation이 말할 수 있는 세계"와 "correctness가 요구하는 세계"가 단절. 아래 G-카테고리는 모두 이 한 mismatch의 표면 증상.

- **G1 (문법적 표면)** — annotation 문법에 함수 호출 자리가 없음. `IOracle(...).decimals()`를 intentValue에 쓸 수 없다는 직접적 제약.
- **G3 (의미론적 표면)** — 설령 grammar가 허용해도 `.decimals()` 호출 사이트가 `_peek`/`_get` 본문에 없어 `@IReturn`으로의 우회 불가. `_setSource`에만 존재하므로 target 함수 trace 바깥.
- **G2 (보조, annotation-only)** — annotation 문법이 `**`를 포함하지 않아 `10 ** x` 형태 표현 불가. ※ **단, 이 한계는 annotation 언어에 국한됨** — abstract interpretation 엔진은 `**`를 지원하므로 **buggy 런타임의 `10 ** source.decimals` 계산은 정밀하게 추상화됨** (TOP 아님). 따라서 G2는 "분석 불가"의 표면이 아니라 "정답 표현 불가"의 표면. (별도 paper correction 필요 — `paper_corrections.md` 참조.)
- **G4 (augmenting)** — view/effectively-view 함수라 post-state 채널도 닫힘 → G1/G3가 유일 채널이면서 막힘.

**[Category (I8)]**: **Value error / Type A 후보** — `source.decimals` 가 snapshot proxy. 재검토 필요 (audit 해석 분기 존재).

#### 6. paper 문장 개선 제안

현재 (main.tex line 1307):
> **L4a (Inexpressible expected value, 10).** The correct expected value depends on a new intermediate computation, an external contract's state, or a function call that does not appear in the program; no intentValue expression can be constructed.

개선안 (impedance mismatch로 상위 명제화):
> **L4a (Inexpressible expected value, 10).** The corrective specification references values that the target function's trace does not produce — most commonly, the return of a function the target does not call. Since `intentValue` is a first-order language over variables and call returns already bound in the function (`@IReturn` applies only to call sites already present in the code), no expression matches the correctness condition.

(Annotation 문법이 `**`를 포함하지 않는 별개의 한계는 본문 표현력 논의에서 분리해 기술 — 아래 Case 1 에서 제안.)

---

### Case 2 — `web3bugs_25_H_05` (현재 분류: **L4a**)

#### 1. Audit report 인용

- **출처**: `reports/25.md` → `[H-05] Exchange rates from Compound are assumed with 18 decimals`
- **Severity**: High. **Warden**: shw.
- **핵심 주장 (원문 발췌)**:
  > `CTokenMultiOracle` assumes the exchange rates of Compound always have 18 decimals. According to the Compound documentation, the exchange rate returned from `exchangeRateCurrent`/`exchangeRateStored` is scaled by `1 * 10^(18 - 8 + Underlying Token Decimals)`. Using a wrong decimal number on the exchange rate could cause incorrect pricing on tokens. See `CTokenMultiOracle.sol#L110`.
- **권고된 수정안**: "get the decimals of the underlying tokens to set the correct decimal of a Source."
- **Sponsor**: confirmed and patched (`e9c1ee5532...`).

#### 2. 코드 의미 이해

##### (2a) Contract 목적 & 시스템 위치

`CTokenMultiOracle` — Compound cToken과 그 underlying ERC20 간 환율을 Yield 시스템 내부 표현(18-dp)으로 노출하는 **어댑터 oracle**. e.g. cDAI ↔ DAI, cUSDC ↔ USDC. `CompositeMultiOracle`(case 1)이 path 구성 시 하위 `IOracle` 중 하나로 이 어댑터를 지목할 수 있으므로, **cToken 기반 Yield vault의 담보 평가 전 구간**에 영향.

Compound의 `exchangeRate`는 "1 cToken이 얼마만큼의 underlying을 대표하는가"를 나타내는 raw 숫자로, Compound는 이를 **`10^(18 - 8 + uD)` 스케일** (여기서 `uD` = underlying 토큰 decimals)로 리턴. cToken 자체 decimals는 8 고정. 예: cDAI (uD=18) → 스케일 `10^28`, cUSDC (uD=6) → 스케일 `10^16`.

Yield 내부 규약: 모든 오라클의 출력은 18-dp (`decimals = 18` public constant, line 14).

##### (2b) 함수의 컨트랙트 내 역할

- `_setSource(cTokenId, underlying, source)` (line 109–124, internal): `sources[cTokenId][underlying]`와 `sources[underlying][cTokenId]` 양방향 엔트리 설정. 후자는 `inverse = true`.
- 이 함수가 저장하는 `decimals` 값이 이후 모든 `_peek`/`_get` 호출의 **가격 스케일 정규화 파라미터**가 됨.

L110 `uint8 decimals_ = 18;` — 이 한 줄이 버그.

##### (2c) 함수 의도 (수식)

`_peek`/`_get` 내부 정규화 (line 82–86):
```solidity
if (source.inverse)  price = 10 ** (source.decimals + 18) / rawPrice;   // underlying → cToken
else                 price = rawPrice * 10 ** (18 - source.decimals);   // cToken → underlying
```
여기서 `source.decimals`의 의미론적 역할 = **"rawPrice가 들고 있는 scale"** = `10 + uD` (= 18 - 8 + uD).

그러므로 `_setSource` 의도:
```
decimals_ = 10 + IERC20(CTokenInterface(source).underlying()).decimals()
```
예: cDAI → `decimals_ = 28`, cUSDC → `decimals_ = 16`.

##### (2d) Line-by-line 분석 (`_setSource` line 109–124)

```solidity
109  function _setSource(bytes6 cTokenId, bytes6 underlying, address source) internal {
110      uint8 decimals_ = 18; // Does the borrowing rate have 18 decimals?   // BUG
111      require (decimals_ <= 18, "Unsupported decimals");
112      sources[cTokenId][underlying] = Source({
113          source: source,
114          decimals: decimals_,
115          inverse: false
116      });
117      sources[underlying][cTokenId] = Source({
118          source: source,
119          decimals: decimals_,
120          inverse: true
121      });
122      emit SourceSet(cTokenId, underlying, source);
123      emit SourceSet(underlying, cTokenId, source);
124      // }
```

- **L110 (BUG)**: `decimals_`를 하드코딩 `18`. 주석 `// Does the borrowing rate have 18 decimals?`는 개발자도 확신이 없었음을 드러냄 — 결국 틀린 가정을 코드로 박음.
- **L111**: tautology (`18 <= 18`). 실제 underlying decimals를 조회했다면 이 guard가 의미를 가졌을 것.
- **L112–116**: 정방향 엔트리 저장. `decimals = 18`이 `_peek` 분기의 `18 - 18 = 0` 지수로 흘러감 → `price = rawPrice * 10^0 = rawPrice`. Underlying이 DAI면 `rawPrice`는 `10^28` 스케일인데 18-dp 규약을 주장하는 price로 그대로 노출 → **10^10 배 부풀림**.
- **L117–121**: 역방향 엔트리 (inverse). 동일 `decimals = 18`로 저장 → `_peek`의 inverse 분기 `10^(18+18) / rawPrice = 10^36 / rawPrice`. Underlying이 DAI면 `10^36 / 10^28 = 10^8`대 값이 나오는데, 18-dp price 규약 위배.
- **L122–123**: 양방향 이벤트.

##### (2e) 버그의 근본 의미

`_setSource`에 "underlying의 decimals를 조회하라"는 명령이 없어, 저장된 `source.decimals = 18`이 이후 모든 환율 계산에서 **잘못된 정규화 지수**로 사용. `_peek`/`_get`의 수식은 대수적으로 맞지만, 입력 파라미터 `source.decimals`가 틀려 체계적 스케일 오차.

Protocol-level: case 1과 같은 경로 — Yield vault가 이 오라클 결과를 담보 평가에 사용 → cUSDC 담보가 10^2배 축소 평가되어 즉시 liquidation, 또는 cDAI 담보가 10^10배 부풀어 무담보 대출. **체계적 편향** (버그 방향이 underlying 토큰마다 다름)이라 공격자가 유리한 방향을 선택 가능.

##### (2f) 올바른 fix

Audit 권고를 구현 수준으로:
```solidity
uint8 uD = IERC20(CTokenInterface(source).underlying()).decimals();
uint8 decimals_ = uint8(10 + uD);
require(decimals_ <= 36, "Unsupported decimals");   // _peek inverse branch overflow 방지
```
Sponsor는 이 방향으로 commit `e9c1ee5532...`에 patch.

#### 3. IntentChecker annotation 시도

**(a) state variable 변화?** — `sources[...][...]`에 write 있음 (L112, L117). `changed(sources[cTokenId][underlying], true)`는 buggy/correct 모두 satisfied (둘 다 쓴다, 값만 다름). → 질적 구분 불가.

**(b) 올바른 값의 산술 표현?** — 이상적 annotation:
```
@Post sources[cTokenId][underlying].decimals == 10 + IERC20(CTokenInterface(source).underlying()).decimals()
```
- `IERC20(...).decimals()`, `CTokenInterface(source).underlying()` → **G1** (함수 호출). 둘 다 view라 `@IReturn` 이론적 허용 대상이지만:
  - `_setSource` 본문에 해당 호출 사이트 **없음** (underlying이나 decimals를 가져오지 않음).
  - `@IReturn`은 코드에 존재하는 call expression에만 값 공급. 존재하지 않는 호출을 annotation으로 "가상 주입" 불가.
- 숫자만 두고 본다면 `10 + <token decimals>`는 단순 `+`이므로 grammar 허용. 그러나 `<token decimals>`에 해당하는 변수가 함수 scope·상속 scope 어디에도 없음 → **G3**.
- 우회: `@LocalVar`로 `decimals_` 값 자체를 넣어도 이는 **입력을 buggy 값 `18`로 정답 선언**하는 꼴. Value condition 불가.

**(c) 버그 인지 전제?** 여기 도달하지 못함.

**예측**: annotation 작성 단계에서 표현 실패 → 양쪽 판정 없음.

#### 4. 분류 타당성

- 현재: **L4a**. ✅ 유지.
- blocker: 올바른 값이 "코드에 존재하지 않는 두 view 호출의 반환에 의존". 심지어 hop별 계산 결과가 아닌 **저장되는 파라미터 자체의 값**이 틀려 모든 downstream 계산에 파급.
- `annotation_plans.md` line 2006–2012 설명은 정확. 다만 "새로운 중간 계산 필요"가 G1+G3 조합임을 명시하면 더 날카로움.

#### 5. 근본 원인

**본질 (한 줄)**: L110의 `decimals_ = 18`이 틀렸음을 IntentChecker가 알아채려면, buggy/correct를 구분하는 grammar-expressible annotation을 **기존 `CTokenMultiOracle` 변수 landscape 만으로** 구성할 수 있어야 함. 그런데 **전지적 개발자조차 그런 annotation을 작성할 수 없음** — 관계식의 피연산자가 컨트랙트 어디에도 없기 때문. (이 점이 L5a "missing-code"와의 결정적 차이: L5a는 landscape는 충분하되 "어떤 annotation을 쓸지" 결정이 버그 인지 전제 — 이 case는 landscape 자체가 부족.)

**변수 현황 검증** — L110 시점에 참조 가능한 식별자와 `decimals_`와의 관계 가능성:

| 식별자 | 타입 | `decimals_`와의 관계 |
|---|---|---|
| `decimals` (contract constant) | `uint8` = 18 | `decimals_ == decimals` → 동어반복 (18 == 18). buggy/correct 구분 불가 |
| `cTokenId`, `underlying` | `bytes6` | 타입 mismatch — 수치 산술 불가 |
| `source` | `address` | 타입 mismatch |
| `sources[...][...]` | struct mapping | L110 시점엔 미기입, 이후 `decimals_` 자체로 채워짐 |

→ 올바른 값 `10 + uD`의 피연산자 `uD` (underlying decimals)에 **상응하는 변수가 컨트랙트 어디에도 없음**. 값을 얻으려면 `CTokenInterface(source).underlying()` 후 `IERC20(...).decimals()` 두 번의 외부 호출이 필요하고, 두 호출 모두 이 함수(`_setSource`)에 쓰이지 않음.

G-표면:
- **G1** — `CTokenInterface(...).underlying()`·`IERC20(...).decimals()`를 intentValue에 쓸 수 없음.
- **G3** — 위 호출들의 반환을 담는 변수 부재 + **호출 사이트 자체 부재** → `@IReturn` 우회도 불가.
- **G2 해당 없음** — 필요한 산술은 `10 + x`. grammar 허용 연산만. 문제는 오로지 `x`를 얻을 수 없다는 것.

**Case 1 대비 부수 관찰**: Case 1의 `_peek`은 `10 ** source.decimals`로 decimals 수치 도메인을 한 번은 통과. Case 2의 `_setSource`는 decimals 도메인에 전혀 진입하지 않음 — `18` 은 흔적이 아니라 fabrication. 런타임 trace의 깊이는 다르나, **annotation 차단 측면에서는 둘 다 "관계 피연산자가 컨트랙트에 없다"로 수렴**.

**L4a ↔ L5 경계 관찰** — 특정 cToken-underlying pair를 고정하면 상수 annotation (`sources[cDAI][DAI].decimals == 28`)은 grammar-expressible. 하지만:
- 모든 pair에 단일 annotation을 달려면 uD 참조 필요 → uD는 컨트랙트 밖 → **L4a**.
- Pair별 상수 박기는 표현 가능하나 상수 = 정답 지식 → **L5a-flavored** (bug-awareness).

이 "general form ↔ specific form" 분리는 L4a와 L5의 경계 현상으로 paper에 인용 가치.

**[Category (I8)]**: **Value error / Type B** — 하드코딩 `18` 자리에 correct 값 `10 + uD`의 `uD` proxy가 scope·contract 어디에도 없음. L4a 정통.

---

### Case 3 — `web3bugs_29_H_05` (현재 분류: **L4a**)

#### 1. Audit report 인용

- **출처**: `reports/29.md` → `[H-05] hybrid pool uses wrong non_optimal_mint_fee`
- **Severity**: High. **Warden**: broccoli (C4 2021-09-sushitrident).
- **핵심 주장 (원문 발췌)**:
  > When an LP provider deposits an imbalanced amount of tokens, a swap fee is applied. `HybridPool` uses the same `_nonOptimalMintFee` as `constantProductPool`; however, since the two pools use different AMM curves, the ideal balance is not the same.
  >
  > Stable swap pools are designed for 1B+ TVL. Any issue related to pricing/fee is serious. I consider this is a high-risk issue.
- **권고된 수정안**: Curve의 `StableSwap3Pool.vy#L322-L337` 방식으로 재작성 — 입금 전후 invariant `D` 차이 기반으로 ideal balance 계산.
- **Sponsor**: confirmed.

#### 2. 코드 의미 이해

##### (2a) Contract 목적 & 시스템 위치

`HybridPool` — Sushi **Trident**의 stableswap pool template. 1:1에 가까운 자산 쌍(예: USDC-USDT, DAI-USDC)에 대해 Curve-style amplified invariant `D`를 사용해 슬리피지를 최소화. Trident router·aggregator가 이 pool과 상호작용하며, pool 내 모든 가격·유동성·수수료 계산은 stableswap invariant에 종속.

##### (2b) 함수의 컨트랙트 내 역할

`_nonOptimalMintFee(_amount0, _amount1, _reserve0, _reserve1) → (token0Fee, token1Fee)` (line 426–441, internal view). 
- 호출자: `mint(bytes data)` (line 99).
- 역할: LP provider가 **불균형 입금** 시 암묵적 swap이 일어난 것으로 간주하고 그만큼 swap fee를 부과. 입금 후 보상 LP 토큰 수를 계산하기 전에 fee를 차감.
- 잘못된 fee는 protocol revenue의 과소/과다 징수, LP 간 가치 이전 왜곡으로 이어짐.

##### (2c) 함수 의도 (수식)

Stableswap 이론 기반 올바른 의도:
- D₀ = current invariant (입금 전): `D₀ = computeLiquidity(_reserve0, _reserve1)`
- D₁ = post-deposit invariant: `D₁ = computeLiquidity(_reserve0 + _amount0, _reserve1 + _amount1)`
- 각 토큰 i의 **ideal balance** (balanced growth 하에서): `idealᵢ = D₁ × _reserveᵢ / D₀`
- **Imbalance** (실제 post-balance – idealᵢ): `|(_reserveᵢ + _amountᵢ) − idealᵢ|`
- Fee per token: `swapFee × imbalanceᵢ / (2 × MAX_FEE)`

즉, "ideal balance"의 정의가 curve에 따라 달라짐:
- **Constant product** (xy=k): `idealᵢ = _amountⱼ × _reserveᵢ / _reserveⱼ` — reserve 비율.
- **Stableswap** (D-invariant): 위 수식. D를 Newton iteration으로 계산해야 함.

##### (2d) Line-by-line 분석 (line 426–441)

```solidity
431  ) internal view returns (uint256 token0Fee, uint256 token1Fee) {
432      if (_reserve0 == 0 || _reserve1 == 0) return (0, 0);
433      uint256 amount1Optimal = (_amount0 * _reserve1) / _reserve0;   // BUG — CP 공식
434
435      if (amount1Optimal <= _amount1) {
436          token1Fee = (swapFee * (_amount1 - amount1Optimal)) / (2 * MAX_FEE);
437      } else {
438          uint256 amount0Optimal = (_amount1 * _reserve0) / _reserve1;   // BUG — CP 공식
439          token0Fee = (swapFee * (_amount0 - amount0Optimal)) / (2 * MAX_FEE);
440      }
441  }
```

- **L432**: 빈 pool 처리 — 둘 중 하나 0이면 fee 없음. (virgin mint 시 적용.)
- **L433 (BUG)**: `amount1Optimal = _amount0 × _reserve1 / _reserve0`. 이는 **constant-product** pool의 balanced deposit 공식. StableSwap에서는 reserve 비율이 ideal deposit 비율이 아님 (amplification A가 curve를 flatten).
- **L435**: 입금한 `_amount1`이 CP 기준 optimal 이하면 → token1 부족 → token1 측에 fee 부과.
- **L436**: `token1Fee = swapFee × (_amount1 - amount1Optimal) / (2 × MAX_FEE)`. 수식 구조는 맞지만 `amount1Optimal`이 틀림.
- **L437–440**: 반대 분기, 동일하게 CP 공식으로 `amount0Optimal` 계산 후 fee. 동일 버그.
- **L441**: 종료.

##### (2e) 버그의 근본 의미

HybridPool은 amplification `A`를 가진 stableswap curve로 운영되어, **가격 곡선이 구간별로 flat**. A가 클수록 소액 임밸런스가 유발하는 가격 이탈이 작음. 따라서 "LP가 얼마나 imbalanced 했는가"의 측정 기준이 **reserve ratio**가 아니라 **invariant D 기반 ideal balance**.

CP 공식을 그대로 쓰면:
- 정상 stableswap 환경(작은 price impact)에서 **imbalance가 과대 평가** → 실제 유발된 swap보다 큰 fee 부과. LP가 억울하게 손해.
- 극단적 불균형(near-depeg)에서는 반대로 **과소 평가** 가능성도 존재.
- 공격 관점: LP가 이 공식을 역산해 보상을 얻을 수 있는 deposit 패턴을 설계 가능 (MEV).

Protocol-level: stableswap의 1B+ TVL 설계 전제 하에서 소규모 fee 왜곡도 누적 금액으로는 크며, pool의 유인 구조 (LP가 imbalance 기여한 만큼 부담) 자체가 파손.

##### (2f) 올바른 fix

```solidity
function _nonOptimalMintFee(...) internal view returns (uint256 token0Fee, uint256 token1Fee) {
    if (_reserve0 == 0 || _reserve1 == 0) return (0, 0);
    uint256 D0 = _computeLiquidity(_reserve0, _reserve1);
    uint256 D1 = _computeLiquidity(_reserve0 + _amount0, _reserve1 + _amount1);
    uint256 ideal0 = D1 * _reserve0 / D0;
    uint256 ideal1 = D1 * _reserve1 / D0;
    uint256 new0 = _reserve0 + _amount0;
    uint256 new1 = _reserve1 + _amount1;
    uint256 diff0 = new0 > ideal0 ? new0 - ideal0 : ideal0 - new0;
    uint256 diff1 = new1 > ideal1 ? new1 - ideal1 : ideal1 - new1;
    token0Fee = swapFee * diff0 / (2 * MAX_FEE);
    token1Fee = swapFee * diff1 / (2 * MAX_FEE);
}
```
Curve StableSwap3Pool.vy L322–337의 전형적 구조. `_computeLiquidity` (line 341)는 HybridPool이 이미 정의한 internal view function — Newton iteration 내장.

#### 3. IntentChecker annotation 시도 (개발 시점 관점 포함)

**개발 시점 가정**: HybridPool 저자는 stableswap 구조를 이해하고 있음 (`_computeLiquidity`, `_getY`, `_getYD` 작성). 버그 인지 없이 `_nonOptimalMintFee`에 annotation을 달려 하면?

**(a) state variable 변화?** — `_nonOptimalMintFee`는 `internal view`, storage write 없음. `changed`/entry-exit 채널 부재.

**(b) 기존 landscape의 grammar-expressible annotation으로 buggy/correct 구분?**

함수 scope 변수: `_amount0`, `_amount1`, `_reserve0`, `_reserve1`, `swapFee`, `MAX_FEE`, `amount1Optimal`(or `amount0Optimal`), `token0Fee`, `token1Fee`. 모두 uint256. Grammar-expressible annotation은 이들의 **다항 산술 결합**뿐.

발달 시점 개발자가 자연스럽게 시도할 만한 annotation들:

1. **상·하한 bound**: `@Post token1Fee <= swapFee * _amount1 / MAX_FEE`. Grammar OK. 그러나 buggy·correct 모두 satisfied → 구분 불가.
2. **비율 기반 intent**: `@Post token1Fee == swapFee * (_amount1 - _amount0 * _reserve1 / _reserve0) / (2 * MAX_FEE)` (개발자가 "imbalance = _amount1 − CP-optimal"로 정의한 경우). Grammar OK. **하지만 이것이 정확히 buggy 코드의 수식** → buggy는 tautologically satisfied, correct는 violated. 결과: **IntentChecker가 correct를 violation으로 오판**.
3. **올바른 stableswap 공식**: `@Post token1Fee == swapFee * (_new1 - D1 * _reserve1 / D0) / (2 * MAX_FEE)` 형식. `D0`·`D1`이 함수 scope에 없음 → **표현 실패**.

→ **핵심 관찰 (수학적 엄밀)**: Grammar의 expressive range = scope 변수에 대한 **rational-polynomial 함수**. 반면 correct ideal balance는 stableswap invariant D에 의존하며, D는 3차 방정식 `D³ − 16A·xy·D + 16A·xy·(x+y) − 4xy·D = 0`의 해로 **rational-polynomial이 아님** (Cardano 공식 적용 시 세제곱근 등장). 따라서 `A`, `_reserve0`, `_reserve1`가 모두 scope 안에 있음에도 **이들의 어떤 rational-polynomial 조합도 D와 같아지지 않음**. 재료 부족이 아니라 **허용된 연산의 닫힘 범위** 밖 (자·컴퍼스로 각의 삼등분 불가와 같은 구조적 제약).

이 맥락에서 개발자가 자연스럽게 시도하는 "경제학적으로 가장 그럴듯한" rational-polynomial specification(`_amount_j × _reserveᵢ / _reserveⱼ`)이 하필 **buggy 공식 그 자체**. Grammar가 허용하는 다른 표현도 많지만 그 어느 것도 correct가 아니며, 가장 단순·직관적 후보가 buggy와 일치해 **IntentChecker가 오히려 버그를 sanction하는 위험**을 낳음.

**(c) 보조 local 주입 우회?**: 개발자가 `uint256 D0 = _computeLiquidity(_reserve0, _reserve1);`를 함수 상단에 추가해 landscape 확장 가능. 그러면 `@Post amount1Optimal == D1 * _reserve1 / D0`가 grammar-expressible. 그러나:
- 이 주입은 **production code 변경**이며, 개발자가 "D가 fee 계산에 관여한다"는 것을 알고 있어야 수행 → **버그 인지 전제**.
- 주입 이후에는 "buggy amount1Optimal = CP 기반 ≠ D 기반 ideal"이므로 annotation이 fire — 즉 **L4a가 auxiliary injection을 통해 L5 영역으로 이동**.

**"Pure annotation-only" paradigm에서는 표현 불가** → L4a 확정.

#### 4. 분류 타당성

- 현재: **L4a**. ✅ 유지.
- blocker 본질: 함수의 기존 variable landscape에서 grammar-expressible annotation 중 어떤 것도 buggy/correct를 구분하지 못함. Grammar의 algebraic 범위가 CP 공식 가족을 정확히 덮음 — 즉 **grammar로 쓸 수 있는 정답 후보들이 모두 실은 오답(buggy 코드 자체)** 이라는 특이한 배치.
- `annotation_plans.md` line 1419–1424 설명은 정확. 다만 "D가 Newton iteration으로 계산됨"이라는 표현이 한계의 원인을 독자에게 정확히 전달하는지 — **분석 엔진은 `_computeLiquidity`를 호출·추상화할 수 있으나 annotation grammar가 함수 호출을 허용하지 않는다**는 점을 명시하면 더 분명.

#### 5. 근본 원인

**본질 (I3 axis α — 변수-관계에 함수 호출이 포함)**: `_nonOptimalMintFee` scope에는 correct 관계에 기여하는 변수들(`_reserve0`, `_reserve1`, `_amount0`, `_amount1`, `swapFee`, `MAX_FEE`, `A`, `N_A`, `A_PRECISION`)이 **존재함**. 문제는 correct 관계식이 이들 사이의 rational-polynomial 조합만으로는 표현되지 않고 **`_computeLiquidity(_reserve0, _reserve1)`, `_computeLiquidity(_reserve0 + _amount0, _reserve1 + _amount1)` 두 internal 함수 호출 결과**를 피연산자로 요구한다는 점. intentValue grammar는 변수·상수만 허용하므로 함수 호출이 관계 안에 들어갈 수 없음.

Case 2와의 구분: Case 2는 scope에 correct 관계를 맺을 변수 자체가 부재 (axis β). 본 case는 Case 1과 같은 축 (axis α) — 재료가 없는 것이 아니라, **재료를 올바르게 조합하려면 함수 경계를 넘는 호출이 필요**.

Sub-variation (I3 axis α 내부):
- **Case 1**: external interface view call (`IOracle(source.source).decimals()`) — grammar 확장 시 `@IReturn`-style 바인딩으로 접근 가능할 수 있는 대상.
- **Case 3 (본 case)**: **internal view function** (`_computeLiquidity`) — 현재 `@IReturn`은 interface 전용이라 grammar 확장에도 별도 채널 설계 필요.

G-표면:
- **G1** — `_computeLiquidity(...)`를 intentValue에 쓸 수 없음 (internal function call).
- **G3** — D₀, D₁ 값을 담는 local이 `_nonOptimalMintFee` scope에 부재. (주입 경로는 I4 참조 — L5 영역으로 이동.)
- **G2 해당 없음** — 사용자 관찰대로 D를 얻은 뒤에는 `D*D*D` 같은 반복 곱셈이면 충분. `**` 부재는 이 case의 primary blocker 아님.

**부차 관찰 — "silent sanction" 위험 (I5 유래)**: Grammar가 허용하는 rational-polynomial specification 중 "가장 경제적으로 그럴듯한" 선택(`_amount_j × _reserveᵢ / _reserveⱼ`)이 하필 buggy 공식 자체. 개발자가 선의로 작성한 annotation이 buggy 코드를 tautologically validation할 수 있음 → **L4a 내에서도 fail-by-confirmation mode가 가능한 위험 사례**. I3 axis α의 일반 패턴에 얹힌 부가 위험이며, α 분류 자체와는 독립.

**[Category (I8)]**: **Algorithm error / Type B** — 잘못된 공식 가족(CP)이 선택됨. 올바른 stableswap 공식은 `D` 값을 요구하는데 `D`·`D₀`·`D₁` 어느 것도 `_nonOptimalMintFee` scope에 없음. 단일 단계 algorithm error.

#### 6. paper 문장 개선 제안

현재 L4a 문장 (line 1307) 유지 가능하되, 이 case의 insight는 **별도 insight 문단**으로 Discussion에 배치 가치 (C5 항목 참조):
> *When the annotation grammar's algebraic range coincides with the buggy code's formula, even a well-intentioned developer producing the most specific annotation confirms the buggy behavior. This is a failure mode of simple grammars that goes beyond "inexpressibility" — the specification language silently sanctions the wrong answer.*

---

### Case 4 — `web3bugs_39_H_02` (현재 분류: **L4a** → 재분류 제안: **L5b**)

#### 1. Audit report 인용

- **출처**: `reports/39.md` → `[H-02] Swivel: Taker is charged fees twice in exitVaultFillingVaultInitiate`
- **Severity**: High (judge upgrade). **Warden**: itsmeSTYJ, also gpersoon (C4 2021-09-swivel).
- **핵심 주장 (원문 발췌)**:
  > Taker is charged fees twice in `exitVaultFillingVaultInitiate()`. Maker is transferring less than premiumFilled to taker and then taker is expected to pay fees i.e. taker's net balance is `premiumFilled - 2*fee`.
- **Judge 승격 이유**: "fees are being incorrectly taken from the taker and not the maker, the maker ends up with a higher balance than expected and the taker has no way to recoup these fees (assets are now lost)".
- **권고 fix** (audit 제공 코드):
  ```solidity
  uToken.transferFrom(o.maker, msg.sender, premiumFilled);        // full premium
  uToken.transferFrom(msg.sender, address(this), fee);             // fee 한 번
  ```
  즉 L280의 `premiumFilled - fee`를 `premiumFilled`로 변경.
- **Sponsor**: confirmed.

#### 2. 코드 의미 이해

##### (2a) Contract 목적 & 시스템 위치

`Swivel` — fixed/floating yield splitting 프로토콜의 on-chain order matching engine. 오프체인 서명된 주문(`Hash.Order`)을 taker가 체결. 주문 유형: zcToken(고정 수익) / Vault(변동 수익) × initiate / exit의 4조합. Swivel은 각 매칭 시 fee를 `fenominator` 배열(`[200, 600, 400, 200]`)의 역수 비율로 수취. Swivel 자체는 ERC20 escrow와 MarketPlace 계약 호출 코디네이터 역할.

##### (2b) 함수의 컨트랙트 내 역할

`exitVaultFillingVaultInitiate(o, a, c)` (L268–289, internal):
- Caller: public `exit(...)` (L209–234)이 `o[i].exit == true`이고 `o[i].vault == true`일 때 dispatch.
- 시나리오: maker가 오프체인으로 "vault(nToken) initiate" 주문을 올려둔 상황에서, msg.sender가 자기 nToken을 **매각(exit)**. Sender = vault holder 매도자, maker = vault 매수자. Maker가 premium 지불, sender가 nToken transfer.
- 잘못된 금액 계산 시 sender가 premium을 못 받거나 중복 지불 → 직접적 자산 손실.

##### (2c) 함수 의도 (수식)

Intended token flows:
- `premiumFilled = a * o.premium / o.principal` — maker가 sender에게 지불할 premium (principal 매각 비율만큼).
- `fee = premiumFilled / fenominator[3]` — 프로토콜 수수료 (vaultExit fee 비율).
- **Maker → Sender**: `premiumFilled` (full premium).
- **Sender → Swivel**: `fee`.
- **Sender → Maker**: `a` nToken (notional, `p2pVaultExchange`).

Sender net cash flow: `+premiumFilled - fee`.

##### (2d) Line-by-line 분석 (L268–289)

```solidity
269  bytes32 hash = validOrderHash(o, c);
271  require(a <= (o.principal - filled[hash]), ...);
273  filled[hash] += a;
275  uint256 premiumFilled = (((a * 1e18) / o.principal) * o.premium) / 1e18;
276  uint256 fee = ((premiumFilled * 1e18) / fenominator[3]) / 1e18;
278  Erc20 uToken = Erc20(o.underlying);
280  uToken.transferFrom(o.maker, msg.sender, premiumFilled - fee);   // BUG
283  uToken.transferFrom(msg.sender, address(this), fee);
286  require(MarketPlace(marketPlace).p2pVaultExchange(..., msg.sender, o.maker, a), ...);
288  emit Exit(...);
```

- **L269–273**: 서명·취소·만료 검증 후 `filled[hash] += a` — order 누적 체결량 갱신 (state write).
- **L275**: `premiumFilled` 계산 (overflow-safe 1e18 scaling 순서).
- **L276**: `fee` 계산 (`fenominator[3] = 200` 기본값 → premium의 0.5%).
- **L278**: ERC20 핸들.
- **L280 (BUG)**: "maker가 sender에게 premium에서 fee를 **미리 뺀 금액** 송금". 개발자의 잘못된 가정: "sender가 어차피 fee 부담할 거니 maker 쪽에서 미리 빼면 한 번의 transfer로 처리 가능" — L283을 간과.
- **L283**: sender가 swivel에 fee 지불. L280에서 이미 fee만큼 덜 받은 sender가 여기서 또 fee를 뱉음 → **이중 부담**.
- **L286**: MarketPlace에 nToken 이전 위임 (sender → maker).

##### (2e) 버그의 근본 의미

**두 transfer의 조합적 오류**. 각 transfer의 금액 계산은 개별적으로 문법·산술상 문제 없음 (`premiumFilled - fee`, `fee` 모두 유효한 uint256). 그러나 **두 transfer의 net effect가 의도를 벗어남**:
- 의도: sender 순수익 = `+premiumFilled - fee`
- 실제: sender 순수익 = `+(premiumFilled - fee) - fee = +premiumFilled - 2·fee`

Protocol-level: sender는 주문마다 **명시된 fee의 2배**를 잃음. Maker는 반대로 fee만큼 덜 지불하여 이익. Judge 지적대로 taker는 자산 회수 수단 없음.

이 case의 특징: 버그가 **단일 라인의 수식 오류가 아니라 두 external call 간의 "의도 분할" 실패**. "Maker가 깎고 보낸다" + "Sender가 또 fee 낸다" 중 정확히 하나는 없어야 함.

##### (2f) 올바른 fix

Audit 제안 그대로. L280의 `premiumFilled - fee` → `premiumFilled`. L283은 유지. 한 줄 수정.

#### 3. IntentChecker annotation 시도 (개발 시점 관점)

**(a) state variable 변화?** `filled[hash] += a`는 state write이나 buggy·correct 모두 동일 → `changed`로 구분 불가.

**(b) "net flow"를 `@Post`로?** Sender 순수익 = external ERC20 `uToken.balanceOf(msg.sender)`의 entry-exit 차이. 그러나:
- Swivel contract의 state variable이 아님 → Swivel scope에서 reference 불가.
- `@IReturn`은 debug annotation(분석 엔진용)이지 intent 입력 아님 (I1).
- 따라서 `@Post` 경로는 봉쇄.

**(c) `@During` + `.arg[n]` 경로** (annotation_plans가 누락한 채널):

Grammar의 duringClause에 `identifier.arg[n] relOp intentValue` 형태 존재 (limitation_types.md L5b 예: `pool0.swap.arg[0] == 0`). L280 call 위에:

```solidity
// @During uToken.transferFrom.arg[2] == premiumFilled
uToken.transferFrom(o.maker, msg.sender, premiumFilled - fee);   // buggy
```

- Buggy: arg[2] = `premiumFilled - fee` ≠ `premiumFilled` → **VIOLATED**.
- Correct (fix 후): arg[2] = `premiumFilled` → **SATISFIED**.
- 피연산자 `premiumFilled`은 L275에서 선언된 local, scope 안. Grammar 전부 허용.

→ **grammar-expressible distinguishing annotation 존재**.

**개발 시점 관점의 함정 (silent sanction 재등장)**: 개발자가 L280 buggy 코드를 그대로 반영하여 "maker가 premium-fee 송금"이라는 자연스러운 intent를 쓰면:
```
// @During uToken.transferFrom.arg[2] == premiumFilled - fee
```
→ buggy tautologically satisfied, correct violated (false positive). **I5 silent sanction** 패턴이 L4a 뿐 아니라 L5b 범주에서도 나타남.

올바른 annotation `arg[2] == premiumFilled`를 쓰려면 "maker는 full premium을 송금해야 한다, fee는 별도 징수"라는 기제 이해 = fix 지식 = **버그 인지 전제**.

#### 4. 분류 타당성 — **L4a 유지 (L5b 재분류 시도 후 철회)**

**검토 과정**: 초기 분석에서 `@During uToken.transferFrom.arg[2] == premiumFilled` at L280이 grammar-expressible하고 buggy/correct를 구분한다는 이유로 L5b 재분류를 제안. 그러나 아래 사유로 **철회하고 L4a 유지**:

**(1) 진짜 intent는 외부 ERC20 state 의존** — L4a 정의 정확 부합:
- 버그의 본질은 "sender의 **순수익(net token flow)**이 의도 대비 fee만큼 부족"이라는 외부 ERC20 balance 변화.
- `limitation_types.md` L4a 정의: "올바른 값이 외부 contract state, 함수 호출, 또는 새로운 중간 계산에 의존" — **정확히 이 case**.
- Sender 순수익 = `uToken.balanceOf(msg.sender)` entry-exit 차이 → Swivel scope 밖 → `@Post` 경로 봉쇄.

**(2) `.arg[2] == premiumFilled`는 intent가 아니라 proxy**:
- L280 위 natspec은 `// transfer premium minus fee from maker to sender` — **buggy 의도를 그대로 서술**. 개발자가 natspec 따라 annotation을 쓰면 `arg[2] == premiumFilled - fee` (buggy와 일치).
- Correct `arg[2] == premiumFilled` 도출 경로:
  1. ERC20 `transferFrom` semantics (외부 표준 지식).
  2. L280 + L283 **cross-line accounting**: sender 순수익 = `+arg[2]_L280 - arg[2]_L283`.
  3. 의도된 net flow = `premiumFilled - fee` (프로토콜 설계 지식).
  4. 연립 → arg[2]_L280 = `premiumFilled`.
- 즉 local proxy를 도출하려면 **cross-line 역산 + natspec override + 외부 표준 지식**. 전형적 L5b ("단일 location의 wrong arg/operator/field를 알아차림" — e.g., 52_H_15, 113_H_05)의 bug-awareness 수준을 질적으로 벗어남.

**(3) I2 "전지적 개발자 테스트"의 정제 필요 (→ I7)**:
- 공식적 criterion: "grammar-expressible annotation이 buggy/correct 구분하는가".
- 그러나 **local proxy annotation**이 우연히 distinguishing power를 갖는 경우까지 포함하면 L4a/L5 구분이 무의미해짐.
- 정제된 criterion: "**정답 intent를 직접 표현**하는 grammar-expressible annotation이 존재하는가". Case 4의 intent(net flow)는 외부 state 의존으로 직접 표현 불가 → **L4a**.

**결론**: **L4a 유지**. `.arg[n]` proxy는 formal 표현 가능성을 가지나 intent-level expressibility 기준에서 L4a에 해당.

#### 5. 근본 원인

**본질**: Bug의 correctness 조건은 **external ERC20 contract state (sender balance)** 의존. Swivel scope 밖의 상태를 annotation grammar로 직접 참조할 채널이 없음 (`@Post` external state 표현 불가, `@IReturn`은 debug용으로 intent 진입 불가 — I1).

**L4a 내 새로운 하위 패턴 — "cross-line accounting" 버그**:
- 버그가 단일 라인의 수식 오류가 아니라 **여러 external call의 조합**에서 발생.
- 각 call의 local arg는 문법상 유효하지만 net effect가 의도와 다름.
- 이런 버그의 intent는 본질적으로 **multi-point accumulation (balance 변화)** — single-point annotation으로 표현 불가.
- Case 1의 "함수 호출 결과 필요" (axis α), Case 2의 "관계 맺을 변수 부재" (axis β)와 구분되는 **axis γ — multi-point accounting을 single-point annotation으로 표현 불가** 패턴.

G-표면:
- **G1 (간접)** — sender balance를 reference하려면 `uToken.balanceOf(msg.sender)` 호출 필요. intentValue는 함수 호출 허용 안 함.
- **G3 (primary)** — net flow 값을 담는 scope 변수 부재. External balance 변화는 Swivel scope 밖.
- **G8 (해당)** — external contract state (ERC20 balance) 의존.

**Natural annotation의 silent sanction**: 개발자가 L280의 natspec("premium minus fee from maker")을 그대로 따라 쓰면 buggy intent를 annotation화 → buggy tautologically satisfied, correct violated. **I5 silent sanction**이 여기서는 natspec이 buggy 구현과 동기화되어 있기 때문에 발생. 이는 L4a의 전형적 failure mode이자, "annotation이 코드/문서의 자연스러운 의도를 따르면 자동으로 buggy를 재확인하는" 가장 위험한 변형.

**[Category (I8)]**: **Algorithm error / Type B** — 두 transfer의 fee 분배 composition이 잘못됨. Correct intent (sender 순수익)는 외부 ERC20 balance 변화로, Swivel scope 밖. Cross-line accounting algorithm error.

#### 6. paper 문장 개선 제안

- **L4a 본문 (line 1307)**: 현재 문장의 "external contract's state, function call that does not appear" 나열 유지하되, **"multi-point accounting을 single-point annotation으로 포착 불가"** 하위 패턴 1줄 추가 가치. Case 4가 이 패턴의 대표.
- **Discussion — intent-level expressibility (I7)**: formal expressibility vs intent-level expressibility를 별개 축으로 구분. L4a/L5 경계의 real criterion은 후자임을 명시.
- **Silent sanction 확장 (I5)**: natspec-code consistency가 silent sanction을 유발할 수 있음. Annotation-driven 개발 workflow가 natspec review와 함께 되어야 함을 Discussion에 제안.

---

### Case 5 — `web3bugs_51_H_04` (현재 분류: **L4a**)

#### 1. Audit report 인용

- **출처**: `reports/51.md` → `[H-04] Swaps are not split when trade crosses target price`
- **Severity**: High. **Warden**: cmichel, gzeon (C4 2021-11-bootfinance).
- **핵심 주장 (원문 발췌)**:
  > The protocol uses two amplifier values A1 and A2 for the swap, depending on the target price. The swap curve is therefore **a join of two different curves at the target price**. When doing a trade that crosses the target price, it should first perform the trade partially with A1 up to the target price, and then the rest of the trade with A2.
  >
  > However, `SwapUtils.swap / _calculateSwap` does not do this, it only uses the "new A", see `getYC` step 5:
  > ```solidity
  > if (aNew == a) { return y; }
  > else { return getY(self, ..., x, xp, aNew, d); }   // BUG
  > ```
- **Impact**: "Worse (better) average execution price. In the worst case, it could even be possible to make the entire trade with one amplifier and then sell the swap result again using the other amplifier making a profit" — **자유 arbitrage 공격 경로**.
- **권고**: trade를 두 구간으로 split하여 각각 A1, A2 적용.
- **Sponsor**: confirmed.

#### 2. 코드 의미 이해

##### (2a) Contract 목적 & 시스템 위치

`SwapUtils` — Boot Finance의 dual-amplifier StableSwap library. Curve-style invariant를 기본 사용하되, **가격 영역에 따라 amplifier를 전환**하는 piecewise curve 구조:
- `xp[0] < xp[1]` → amplifier **A1** 사용
- `xp[0] >= xp[1]` → amplifier **A2** 사용
- 경계 (`xp[0] == xp[1]`)가 "target price". 이 지점에서 curve가 꺾임.

이 구조는 Boot Finance가 개별 asset-pair에 맞춘 custom pricing behavior를 구현하려는 design. Swap이 **경계를 가로지를 때** 단일 A로 전체를 계산하면 가격 왜곡 발생 → LP 가치 훼손 + taker arbitrage.

##### (2b) 함수의 컨트랙트 내 역할

`getYC(self, tokenIndexFrom, tokenIndexTo, x, xp) → uint256 y` (L735–771, internal view):
- Caller: `_calculateSwap` (L914–933) → 최종적으로 external `swap()` (L1098–1152)이 호출.
- 역할: "FROM 토큰을 `x` (new total amount)까지 늘릴 때, TO 토큰이 pool에 얼마나 남아야 invariant가 유지되는가".
- 반환 `y` → `dy = xp[tokenIndexTo] - y - 1`로 swap 결과 계산. 이 `dy`가 msg.sender에게 transfer, state `balances[tokenIndexTo]`가 감소.

##### (2c) 함수 의도 (수식)

단일-A 가정 하 정상 의도 (StableSwap 표준):
```
given A, d, x → solve for y such that invariant(xp with tokenFrom=x, tokenTo=y, A) = d
```
`getY`가 Newton iteration으로 해결.

**dual-A 경우 correct intent** (audit 제안):
1. Swap이 경계를 가로지르는가? (`aNew != a`일 때).
2. 경계점 (`xp[0] == xp[1]`)까지의 amount `dx₁` 계산.
3. Partial swap 1: (x 중 `dx₁`만큼, A, d) → intermediate `y₁`, 중간 state.
4. 중간 state에서 새 invariant `d₂ = getD(중간 xp, aNew)`.
5. Partial swap 2: (나머지 `x - dx₁`, aNew, d₂) → 최종 `y₂`.
6. 반환 `y₂`.

##### (2d) Line-by-line 분석 (L735–771)

```solidity
742  uint256 numTokens = self.pooledTokens.length;
753  uint256 a = determineA(self, xp);        // (1) 현재 상태의 A
756  uint256 d = getD(xp, a);                 // (2) 현재 A 기준 invariant
759  uint256 y = getY(self, ..., x, xp, a, d);// (3) 단일-A로 계산한 새 y
762  uint256 aNew = _xpCalc(self, ..., x, y); // (4) 계산된 y 기준으로 새 영역의 A
765  if (aNew == a) {
766      return y;                            // 경계 안 넘음 → 정상
767  } else {
768      return getY(self, ..., x, xp, aNew, d);  // BUG: aNew + old d로 전체 재계산
769  }
```

- **L753**: `determineA` — `xp[0]` vs `xp[1]` 비교로 현재 A 결정.
- **L756**: 현재 xp와 A로 invariant `d` 계산 (Newton loop).
- **L759**: `getY`로 x에 대한 y 계산 (Newton loop). **A가 바뀌지 않는다고 가정** — 단일-A swap.
- **L762**: 계산된 y로 post-state의 A가 무엇일지 확인 (`_xpCalc`).
- **L765–766**: A가 그대로 → 단일-A 가정이 유효했음 → return y.
- **L767–768 (BUG)**: A가 바뀜 → 단일-A 가정 무효. 하지만 코드는 **새 A(aNew)와 옛 d로 전체 swap을 재계산**. 이는:
  - `d`는 구 영역의 curve invariant 값. 새 영역 curve(A=aNew)에서 이 invariant는 의미가 없음.
  - 전체 swap을 새 A만 적용 → 경계 이전 구간의 가격 왜곡.
  - Audit 지적대로 arbitrage 가능: 한 A로 사서 다른 A로 파는 사이클에서 prof.

##### (2e) 버그의 근본 의미

Pool의 가격 곡선은 target price에서 **꺾인 piecewise curve**. Curve1과 curve2가 그 지점에서 연속적으로 이어지나 기울기가 다름. Correct swap은 **각 구간에서 해당 A로 이동량을 계산하고 합산**해야 함.

Buggy는 "A가 바뀌면 전체를 aNew로 재계산" — 마치 curve가 전체 구간에서 A=aNew인 것처럼 가정. 경계를 가로지르는 trade에서:
- Trade 초기(구 영역)의 가격 impact이 aNew curve로 계산되어 실제 curve1보다 **과대/과소 평가**.
- 누적 결과 `y`가 실제 curve-following 결과와 다름.
- Arbitrage 경로: 경계 바로 앞까지 curve1로 사고, 경계 직후에 curve2로 팔면 차익. Pool이 체계적으로 손실.

Protocol-level: LP 자금 서서히 유실, MEV bot이 자동 수확 대상.

##### (2f) 올바른 fix

Audit 권고 그대로 split. Pseudocode:
```solidity
if (aNew != a) {
    uint256 dx1 = computeBoundaryX(self, tokenIndexFrom, xp, a, d);  // 경계 도달 amount
    uint256 y1 = getY(self, tokenIndexFrom, tokenIndexTo, dx1, xp, a, d);
    // 중간 state로 xp' 구성
    uint256[] memory xpMid = ...;
    uint256 d2 = getD(xpMid, aNew);
    return getY(self, tokenIndexFrom, tokenIndexTo, x, xpMid, aNew, d2);  // remaining
}
```
핵심 미발현 요소: `computeBoundaryX` (경계점 찾기 — 비선형 방정식), `xpMid` (중간 state), `d2` (새 invariant).

#### 3. IntentChecker annotation 시도 (개발 시점 관점)

**함수 scope 변수**: parameters(`tokenIndexFrom`, `tokenIndexTo`, `x`, `xp[]`), locals(`numTokens`, `a`, `d`, `y`, `aNew`), contract state(`initialA`, `futureA`, `initialA2`, `futureA2`, …).

**(a) state variable 변화?** `getYC`는 internal view, storage write 없음. `changed`/entry-exit 채널 없음. (Caller `swap`에는 있으나 buggy/correct 모두 `balances` 감소 동일 방향 — I3 β style로도 구분 불가.)

**(b) `@Post return == expr` 경로**:

Correct return value:
```
return == getY(...rest..., aNew, getD(xpMid, aNew))   // 두 번째 partial swap 결과
```
- `getY(...)`, `getD(...)` 모두 **internal function call** → intentValue 허용 안 함 (G1).
- `xpMid`, `d2`, `y1`, `dx1` — scope 부재 (G3).
- `dx1`은 방정식 `xp[0] + dx1 == xp[1] - getY(...)`의 해 → 자체가 비선형 방정식의 해, rational-polynomial 밖.

**(c) 다른 형태의 annotation**:

| 시도 | Grammar | Buggy 판정 | Correct 판정 | 평가 |
|---|---|---|---|---|
| `@Post return == y` (L759 결과) | OK | VIOLATED (다른 값 반환) | VIOLATED (split 결과 ≠ y) | 둘 다 violated, 구분 불가 |
| `@Post getY.arg[5] == a` (즉 둘째 호출의 `a` 인자가 원래 `a`여야 함) | OK (.arg[n]) | VIOLATED (`aNew` 전달) | — (correct는 split 방식이라 이 제약 자체 무의미) | 의미 있는 correctness 표현 아님 |
| `@Post return >= xp[tokenIndexTo] - x` 같은 bound | OK | 둘 다 satisfied | 둘 다 satisfied | 구분 불가 |

**전지적 개발자가 intent를 직접 표현하려면 두 `getY` 호출과 한 `getD` 호출의 연쇄를 annotation에 담아야 함** — grammar 범위 밖.

**I4 auxiliary local 주입 경로**: `uint256 dx1 = ...; uint256 y1 = getY(...); uint256 d2 = getD(...); uint256 y2 = getY(...);`를 함수 상단에 삽입 후 `@Post return == y2`. 그러나:
- 삽입 자체가 fix 구조(split)를 구현하는 것과 같음 — **버그 인지 전제**.
- 경계점 `dx1` 계산이 비선형 방정식 해이므로, 주입 가능한 closed-form이 없음. Binary search 같은 iteration 루틴을 만들어야 함 — production 수정의 깊이가 큼.

#### 4. 분류 타당성

- 현재: **L4a**. ✅ 유지.
- I2 전지적 개발자 테스트: grammar로 correct intent(piecewise split) 직접 표현 불가 → L4a 확정.
- I7 intent-level expressibility: 형식적으로도 proxy annotation이 buggy/correct 구분에 실패 → formal 수준에서도 표현 불가.
- `annotation_plans.md` L862–893의 분석은 정확. 특히 "시도한 annotation 접근과 실패 사유" 표가 이 case의 철저성을 잘 보여줌.

#### 5. 근본 원인

**본질 (Type B — scope에 proxy 부재)**:

`getYC` scope에 존재하는 local은 `a`, `d`, `y`, `aNew`. 이들은 모두 **single-A 가정 하에 계산된 값들** — 즉 "curve 1 전체에서 x만큼 swap했다고 가정한 결과". Correct 의도는 piecewise split 결과인 `y₂`인데, 이는:
- **경계점 `M`** (`getD([M,M], a) == d`를 만족하는 값)
- **중간 state `xpMid`** (`[M, M]`)
- **새 invariant `d₂ = getD([M,M], aNew)`**
- **partial 1 결과 `y₁`**, **partial 2 결과 `y₂`**

이 값들 중 어느 하나도 `getYC` scope 혹은 `Swap` struct state 어디에도 **존재하지 않음**. State variables(`initialA, futureA, balances, tokenPrecisionMultipliers, …`)도 현재 pool 상태일 뿐 "가상의 경계점"이나 "중간 state"를 담지 않음.

기존 `d`, `y`는 scope에 있으나 correct 관계식과 무관. 즉 **proxy 자체가 없음** (Type B — 사용자 제안 framing).

G-표면:
- **G3 (primary)** — 필요 intermediate(M, xpMid, d₂, y₁, y₂) 전부 scope·state 부재.
- **비선형성** (보조) — `M`은 `getD([M,M], a) == d` 비선형 방정식의 해. 설령 grammar가 rational-polynomial 확장을 받아도 closed-form 구성 불가 (Case 3의 D와 같은 transcendental 장벽).
- **Multi-step sequential dependency** (구조) — M → y₁ → xpMid → d₂ → y₂ 연쇄. 각 단계가 이전 단계 결과에 의존. Grammar가 "단일 relation"을 기술하는 언어이므로 연쇄 자체의 표현 구조 없음.

**Case 1·2·3과의 관계 (Type A/B 기준)**:
- Case 2, 3, 5: Type B (proxy 없음) — scope에 correct 값과 연결될 변수 자체 부재.
- Case 1: Type A 가능성 (struct field `source.decimals`가 snapshot proxy) — 별도 L4a/L5b 경계 재검토 필요 (향후).
- 따라서 Case 5는 표면적 복잡성(multi-step, 비선형)에도 불구하고 **본질적 blocker는 Case 2·3과 동일한 "proxy 부재"**. 복잡성은 이 부재가 해소되기 어려운 정도를 설명할 뿐.

**[Category (I8)]**: **Algorithm error / Type B** — missing split decomposition. Correct 는 경계점(M), 중간 state, d₂, y₁, y₂ 모두 요구. 이 중 어느 하나도 scope·state에 없음. Multi-step sequential algorithm error — I8 matrix Type B 중 가장 복잡한 축.

#### 6. paper 문장 개선 제안

- **L4a 본문 (line 1307)**: Case 5는 "multi-step algorithmic intent" 하위 패턴의 극단적 예. `paper_corrections.md` I3 axis γ 설명에 "경계점 + partial swap 연쇄" 예시로 인용.
- **Discussion future work**: Annotation grammar에 "sequential computation"을 도입하는 제안의 한계 — Case 5처럼 step 수가 input-dependent인 경우 효과적이려면 grammar가 사실상 imperative 언어에 가까워져야 함. 단순성 tradeoff.
- **Arbitrage 경로 설명**: 이 case는 audit report가 명시적으로 "one amplifier로 사서 other amplifier로 파는" 공격 경로를 제시 — L4a case 중 **economically exploitable severity**가 가장 명확한 예. Introduction motivation에서 "미탐지 버그가 경제적 손실로 직결"되는 실증으로 인용 가치.

---

### Case 6 — `web3bugs_51_H_06` (현재 분류: **L4a**)

#### 1. Audit report 인용

- **출처**: `reports/51.md` → `[H-06] Ideal balance is not calculated correctly when providing imbalanced liquidity`
- **Severity**: High. **Warden**: jonah1005 (C4 2021-11-bootfinance).
- **핵심 주장 (원문 발췌)**:
  > In Saddle Finance, the optimal balance should be the same ratio as in the Pool. For example, if there's 10000 USD and 10000 DAI, the user should get the optimal LP if they provide liquidity with ratio = 1.
  >
  > However, if the `customSwap` pool is created with a target price = 2, **the user would get 2 times more LP if they deposit DAI**. The current implementation does not calculate ideal balance correctly. If the target price is set to be 10, the ideal balance deviates by 10. The fee deviates a lot.
- **POC (audit 제공)**: `target_price = 4`인 DAI/LINK pool에서 imbalanced deposit 시 LP 토큰이 **약 4배 과다 발행**. 즉 동일 deposit에 4배 수익 — 펌프 공격 경로.
- **권고 fix (audit)**: `self.balances` 사용 로직 재검토; `d0`·`d1`을 일관된 A로 계산.
- **Sponsor**: confirmed.

#### 2. 코드 의미 이해

##### (2a) Contract 목적 & 시스템 위치

동일 `SwapUtils` (Case 5와 같은 contract). Dual-A custom StableSwap. `addLiquidity`는 LP provider가 token deposit 시 호출하는 공개 경로. 부정확한 fee 계산은 **LP 토큰 발행량 왜곡 → LP 가치 이전 공격**으로 직결.

##### (2b) 함수의 컨트랙트 내 역할

`addLiquidity(self, amounts[], minToMint) → toMint` (L1163–1270, external):
- LP가 pool에 token 입금 → LP 토큰 발행.
- Imbalanced deposit (pool 비율과 다르게 입금)은 **암묵적 swap**을 포함 → swap fee를 imbalance 비례로 부과 후 순 입금분에 해당하는 LP 토큰 발행.
- Fee의 정확성이 **모든 LP 간 가치 공정성**의 기반.

##### (2c) 함수 의도 (수식)

표준 StableSwap addLiquidity 수식:
1. `d0 = getD(oldBalances, A)` — 입금 전 invariant.
2. `newBalances[i] = oldBalances[i] + amounts[i]`.
3. `d1 = getD(newBalances, A)` — 입금 후 invariant.
4. For each i:
   - `idealBalance[i] = d1 × oldBalances[i] / d0` — "공정하게 균형 유지됐을 때 newBalance여야 할 값".
   - `fee[i] = feePerToken × |idealBalance[i] − newBalances[i]|` — imbalance에 비례한 fee.
5. Fee 반영한 `d2 = getD(feeAdjustedBalances, A)`.
6. `toMint = (d2 − d0) × totalSupply / d0`.

**핵심 가정**: `d0`, `d1`, `d2` 모두 **같은 curve (같은 A)** 에서 계산되어야 ratio가 의미 있음. 다른 curve의 D는 scale·단위가 다름.

##### (2d) Line-by-line 분석 (addLiquidity 일부, L1178–1241)

```solidity
1178  if (self.lpToken.totalSupply() != 0) {
1179      v.d0 = getD(self);                                    // (1) 현재 balances 기반, 내부 determineA가 A 선택
1180  }
1188  uint256[] memory newBalances = self.balances;
1190  for (...) { newBalances[i] = self.balances[i].add(amounts[i]); }    // (2) new balances
1216  v.preciseA = determineA(self, _xp(self, newBalances));    // (3) new balances 기반 A (A 전환 가능)
1222  v.d1 = getD(_xp(self, newBalances), v.preciseA);          // (4) NEW A로 d1 계산
1223  require(v.d1 > v.d0, "D should increase");
1227  if (self.lpToken.totalSupply() != 0) {
1230      for (uint256 i = 0; i < self.pooledTokens.length; i++) {
1231          uint256 idealBalance = v.d1.mul(self.balances[i]).div(v.d0);  // BUG
1232          fees[i] = feePerToken
1233              .mul(idealBalance.difference(newBalances[i]))
1234              .div(FEE_DENOMINATOR);
1235          self.balances[i] = newBalances[i].sub(
1236              fees[i].mul(self.adminFee).div(FEE_DENOMINATOR)
1237          );
1238          newBalances[i] = newBalances[i].sub(fees[i]);
1239      }
1240      v.d2 = getD(_xp(self, newBalances), determineA(self, _xp(self, newBalances)));
1241  }
```

- **L1178–1179**: 초기 LP가 아닌 경우 d0 계산. `getD(self)` 내부는 `determineA(self, _xp(self))` → **old balances로 A 결정** (A_old라 부름). 그리고 `getD(xp_old, A_old)` 호출.
- **L1188–1190**: newBalances 구성.
- **L1216 (Important)**: `v.preciseA = determineA(self, _xp(self, newBalances))` — **new balances로 A 결정** (A_new라 부름). Deposit이 pool 비율을 역전시킬 정도면 `A_old ≠ A_new`.
- **L1222**: `v.d1 = getD(xp_new, A_new)` — **A_new curve로 d1 계산**.
- **L1231 (BUG)**: `idealBalance = d1 × balances[i] / d0`. 여기서 `d0`은 A_old curve, `d1`은 A_new curve. 두 curve의 D는 단위·scale 다름 → **비율이 의미 없음**. 결과 `idealBalance` 왜곡.
- **L1232–1234**: 왜곡된 `idealBalance` 기반 fee 계산 → fee 왜곡.
- **L1235–1238**: 왜곡된 fee로 `self.balances[i]` 갱신 → state 왜곡.
- **L1240**: `d2`는 또 새로운 `determineA` 호출 — 혼재 가능.
- 결국 `toMint = (d2 - d0) × totalSupply / d0` (L1251)도 세 개 다른 A의 D 혼용 → LP 발행량 왜곡.

##### (2e) 버그의 근본 의미

Dual-A 설계에서 invariant `D`의 **scale·값이 A에 따라 다름**. `idealBalance` 공식의 "balance_i × d1 / d0" 비율은 **같은 curve 위의 두 상태** 간 비례 스케일링을 의미 — 서로 다른 curve에서는 "kg/lb 비율을 계산하는" 것과 같이 물리적 의미 없음.

Audit이 보여준 POC: target_price=4에서 imbalanced deposit은 A 전환을 유발 → 공식 계산 왜곡 → LP 토큰 **4배 과다 발행**. 공격자는:
1. Target price 근처로 pool을 push.
2. A 전환 유발하는 imbalanced deposit.
3. 과다 발행된 LP 토큰을 획득.
4. Pool 정상화 후 withdraw — LP 가치 전이 획득.

**Protocol-level**: 기존 LP holders의 지분 희석 (value drain). Target price가 높을수록(공격자 악성 pool 배포 시) 피해 비례 증대.

##### (2f) 올바른 fix

Audit 권고를 따라: `d0`·`d1`을 **consistent A**로 계산. 예:
```solidity
v.preciseA = determineA(self, _xp(self, newBalances));    // A_new 선택
v.d0 = getD(_xp(self), v.preciseA);                        // A_new로 d0 재계산 (consistent)
v.d1 = getD(_xp(self, newBalances), v.preciseA);
```
혹은 둘 다 A_old 사용. 핵심은 **동일 A로 통일**.

#### 3. IntentChecker annotation 시도 (개발 시점 관점)

**함수 scope 변수** (addLiquidity 시점):
- `amounts[]`, `fees[]`, `newBalances[]` (local arrays).
- `v.d0`, `v.d1`, `v.d2`, `v.preciseA` (AddLiquidityInfo struct locals).
- `feePerToken`, `idealBalance`, `toMint` (locals, 부분 scope).
- State via `self`: `balances[]`, `pooledTokens[]`, `lpToken`, `initialA`, `futureA`, `initialA2`, `futureA2`, ... .

**(a) state variable 변화?** `self.balances[]` 변화 있음. 그러나 buggy·correct 모두 증가 방향 동일 → `changed`/entry-exit 구분 불가 (I3 γ 성격: 방향은 같고 magnitude만 다름 — L4c 직전이나 더 깊음).

**(b) 기존 scope로 `@Post ... == correct_expr` 시도**:

Correct `idealBalance`는:
```
idealBalance_correct = d1_consistent × balances[i] / d0_consistent
```
where `d0_consistent = getD(oldBalances, A_consistent)`. 

여기서:
- `v.d0` (L1179)은 `A_old`로 계산됨 → inconsistent.
- `v.d1` (L1222)은 `v.preciseA` (`A_new`)로 계산됨.
- **A_new로 재계산한 d0** (=correct d0) 은 scope에 없음.
- **A_old로 재계산한 d1** (대안 fix) 도 scope에 없음.

결국 correct idealBalance 표현에 `getD(...)` 호출 결과가 새 인자로 필요 → Case 5와 동일 구조. 추가로 이 호출 결과를 담는 변수가 scope 부재.

**(c) `.arg[n]` 채널 시도**: L1222의 `getD` 호출에 `@During getD.arg[1] == some_A` 형태? `v.preciseA`가 인자로 쓰이는데, "correct A"가 무엇인지 표현하려 해도 그 자체가 이미 `v.preciseA` (new A). Correct fix는 `v.d0` 재계산을 요구하는 것이지 `v.d1`의 인자 교정이 아님. 따라서 `.arg[n]`로 해결 안 됨.

**(d) 상태변수 간접 제약**:
- `@Post v.d0 computed_with_A == v.preciseA` 같은 meta-제약은 grammar에 없음.
- `@Post self.balances[i] (entry relOp exit)` 방향만 체크 — 앞서 본 대로 구분 불가.

모든 경로 grammar 내 표현 실패. **Type B 확정**.

#### 4. 분류 타당성

- 현재: **L4a**. ✅ 유지.
- I2 전지적 개발자 테스트: correct idealBalance 식이 `getD(...)` 재호출 결과에 의존. grammar 불허.
- I7 intent-level: formal proxy annotation도 buggy/correct 구분 실패 — `.arg[n]`로도 우회 못 함.
- `annotation_plans.md` L904–962 기존 설명은 정확. "annotation 내 함수 호출 불가 + Newton loop 반복 함수" 설명이 핵심 포착.

#### 5. 근본 원인

**본질 (Type B — scope에 consistent-A D 부재)**:

`addLiquidity` scope에는 D 관련 값들이 있으나 모두 **혼재된 A 기준**:
- `v.d0` — old balances + A_old (buggy)
- `v.d1` — new balances + A_new
- `v.d2` — fee-adjusted balances + 또 다른 A (determineA 재호출)

Correct idealBalance가 요구하는 **consistent-A 기준 d0** (즉 `getD(oldBalances, A_new)` 혹은 그 대칭)는 scope 어디에도 없음. State variables (initialA, futureA, …)은 raw A 파라미터일 뿐 D 값을 담지 않음.

Case 5와 쌍둥이 구조:
- Case 5 (`getYC`): split 결과 `y₂`가 scope에 없음.
- Case 6 (`addLiquidity`): consistent-A `d0_correct`가 scope에 없음.
- 둘 다 **같은 dual-A library**의 다른 함수에서 같은 원인(A 일관성 유지 실패)으로 발생한 쌍둥이 버그.

G-표면:
- **G3 (primary)** — consistent-A D 값이 scope·state 부재.
- **G1 (secondary)** — 설령 D 값 proxy가 있어도 `getD(...)`를 intentValue에서 호출할 수 없어 대안 경로 봉쇄.
- **Multi-A dependency** — dual-A 시스템 특유의 "같은 A로 D를 두 번 계산" 요구는 grammar로 기술하기 어려운 constraint (meta-level: "계산 동질성" 같은 개념이 grammar에 없음).

**Case 5와의 미세한 차이**:
- Case 5: 결과 값 자체 (`y₂`)가 multi-step 연쇄의 최종 산물.
- Case 6: 연쇄는 단일 단계이나 **동일 call의 인자 일관성**이 문제. "A_consistent로 d0을 다시 호출" — 단 한 번의 추가 호출이면 fix 되나, 그 호출의 결과가 scope에 없음.
- 따라서 Case 6이 **algorithm error 중 상대적으로 경미**. Grammar가 "기존 호출을 새 인자로 재호출한 결과" reference를 허용하면 해소 가능 — Case 5보다 grammar 확장 효과 크게 받을 case.

**Silent sanction 관찰**:
- 개발자가 L1231 공식을 그대로 annotation으로 옮기면: `@Post idealBalance == v.d1 * self.balances[i] / v.d0` — buggy tautologically satisfied, correct는 다른 d0 쓰므로 violated. 전형적 **fail-by-confirmation** (I5 Mode-2). Case 3과 같은 패턴 재등장.

**[Category (I8)]**: **Algorithm error / Type B** — consistent-A 기준 `d0` 재계산 필요. Single-step algorithm error (Case 5처럼 multi-step은 아님). Grammar에 "호출의 인자 일관성" 제약 도입하거나 re-invocation 결과 reference 허용 시 해소 여지.

---

### Case 7 — `web3bugs_59_H_05` (현재 분류 불일치: limitation_types.md = **L4a**, annotation_plans.md = L5b → 객관 판정: **L4a**)

#### 1. Audit report 인용

- **출처**: `reports/59.md` → `[H-05] AuctionEschapeHatch.sol#exitEarly updates state of the auction wrongly`
- **Severity**: High. **Warden**: 0x0x0x (C4 2021-11-malt).
- **핵심 주장 (원문 발췌)**:
  > When the user exits an auction with profit, to apply the profit penalty **less maltQuantity is liquidated** compared to how much malt token the liquidated amount corresponds to. The problem is `auction.amendAccountParticipation()` simply subtracts the malt quantity **with penalty** and full `amount` from users auction stats. This causes a major problem:
  >
  > `uint256 maltQuantity = userMaltPurchased.mul(amount).div(userCommitment);`
  >
  > The ratio of `userMaltPurchased / userCommitment` gets higher after each profit taking (since penalty is applied to subtracted maltQuantity from userMaltPurchased), by doing so **a user can earn more than it should**.
- **Judge**: "warden has identified an exploit that allows early withdrawers to gain more rewards than expected... flow in the accounting logic". High severity confirmed.
- **Sponsor**: 0xScotch confirmed.
- **권고 fix**: 미구체. "Make sure which values are used for what and update values which doesn't create problems like this."

#### 2. 코드 의미 이해

##### (2a) Contract 목적 & 시스템 위치

`AuctionEscapeHatch` — Malt (algorithmic stablecoin)의 auction-based stabilization 메커니즘에서, **이미 참여한 auction position을 조기 청산**할 수 있게 하는 escape hatch. 청산 시 **profit penalty**를 적용하여 완전 이익 실현을 억제 (sticky 참여 유도).

##### (2b) 함수의 컨트랙트 내 역할

`exitEarly(auctionId, amount, minOut)` (L65–92, external):
- User가 `amount` 만큼의 auction commitment를 조기 청산.
- Internal: penalty-adjusted maltQuantity 계산 → mint → DEX에서 collateral로 매각 → user에게 전송.
- **핵심 의존**: auction contract의 `amendAccountParticipation` 호출로 **auction의 user 참여 state를 차감** (subtract amount from userCommitment, maltQuantity from userMaltPurchased 추정).
- 반복 호출 가능 — state가 정확히 proportional하게 줄어야 누적 arbitrage 없음.

##### (2c) 함수 의도 (수식)

의도된 invariant:
- Pre-exit: `userMaltPurchased / userCommitment = ratio_initial`.
- Exit `amount`: proportional하게 malt/commitment 모두 차감 → **비율 불변**.
- Pro-rata pre-penalty `maltQuantity`: `userMaltPurchased × amount / userCommitment`.
- Liquidated (post-penalty): `desiredReturn × pegPrice / currentPrice` — 이익 실현 일부만.
- **State 차감에는 pre-penalty 값 써야**. Liquidation(mint)에는 post-penalty 값 써야.

##### (2d) Line-by-line 분석 (exitEarly L65–92)

```solidity
66   uint256 maltQuantity = _calculateMaltRequiredForExit(_auctionId, amount);
     // → post-penalty 값 반환 (내부 L209에서 overwrite)
69   malt.mint(address(dexHandler), maltQuantity);     // (A) mint용 — post-penalty 맞음
70   uint256 amountOut = dexHandler.sellMalt();
72   require(amountOut > minOut, "EarlyExit: Insufficient output");
74   AuctionExits storage auctionExits = auctionEarlyExits[_auctionId];
76   auctionExits.exitedEarly = auctionExits.exitedEarly + amount;
77   auctionExits.earlyExitReturn = auctionExits.earlyExitReturn + amountOut;
78   auctionExits.maltUsed = auctionExits.maltUsed + maltQuantity;   // 자체 accounting
...
83   auction.amendAccountParticipation(                // (B) state 차감용 — BUG
84     msg.sender,
85     _auctionId,
86     amount,            // commitment 차감량
87     maltQuantity       // BUG: post-penalty 값이 들어감. pre-penalty여야 함.
88   );
90   collateralToken.safeTransfer(msg.sender, amountOut);
91   emit EarlyExit(msg.sender, amount, amountOut);
```

- **L66**: `_calculateMaltRequiredForExit` 호출. 내부에서 pre-penalty (L195) 계산 후 profit 있으면 post-penalty로 overwrite (L209). 최종 반환은 post-penalty.
- **L69 (OK)**: liquidation — post-penalty 양만큼 malt를 mint. 정확한 사용.
- **L83–88 (BUG)**: 같은 `maltQuantity` (post-penalty)가 auction state 차감에도 전달됨. 그 결과 amendAccountParticipation 내부에서 `userMaltPurchased -= post-penalty_maltQuantity` (펜티만큼 덜 차감) + `userCommitment -= amount` (그대로).
- **결과**: user 남은 비율 `userMaltPurchased/userCommitment` 증가. 다음 exitEarly에서 더 많은 malt/commitment 비율로 계산 → 과다 지급. 반복 가능 → 공격 경로.

##### (2e) 버그의 근본 의미

`_calculateMaltRequiredForExit`의 반환값이 **이중 용도**로 사용되지만 두 용도가 요구하는 값이 서로 다름:
- **Mint (liquidation)**: penalty로 실제 mint량을 줄여야 함 → post-penalty.
- **State accounting**: user의 남은 참여 비율을 보존해야 함 → pre-penalty.

이 분리를 코드가 하지 않음 (단일 변수로 collapse). State는 pre-penalty로 차감되어야 비율 invariant가 유지되는데, post-penalty로 차감하여 매번 비율이 불어남.

Protocol-level: 반복 exitEarly 호출로 점점 많은 malt per commitment 추출 → 완전히 소진하기 전에 **과다 이익 실현** + 잔여 commitment로 `claimArbitrage` 추가 이익. 시스템 자금 유출.

##### (2f) 올바른 fix

가능한 두 가지:
1. `_calculateMaltRequiredForExit`가 **두 값 모두 반환**:
   ```solidity
   (uint256 postPenalty, uint256 prePenalty) = _calculateMaltRequiredForExit(...);
   malt.mint(address(dexHandler), postPenalty);
   ...
   auction.amendAccountParticipation(msg.sender, _auctionId, amount, prePenalty);
   ```
2. `exitEarly`에서 pre-penalty 직접 계산 (중복이나 명확):
   ```solidity
   // user state를 별도로 query해서 pre-penalty 계산
   (,, uint256 userMaltPurchased) = auction.getAuctionParticipationForAccount(msg.sender, _auctionId);
   (uint256 userCommitment,,) = auction.getAuctionParticipationForAccount(msg.sender, _auctionId);
   uint256 prePenalty = userMaltPurchased * amount / userCommitment;
   ```

둘 다 **새 local 변수 도입 + 기존 반환값 구조 변경** 수반.

#### 3. IntentChecker annotation 시도 (개발 시점 관점)

**함수 scope 변수** (exitEarly):
- Params: `_auctionId`, `amount`, `minOut`.
- Locals: `maltQuantity` (post-penalty), `amountOut`, `auctionExits` pointer.
- State: `auction`, `dexHandler`, `malt`, `maxEarlyExitBps`, `cooloffPeriod`, `auctionEarlyExits` (자체 tracking).

**(a) state variable 변화?** `auctionExits.*` 업데이트 있음 — 그러나 이는 AuctionEscapeHatch 자체의 tracking이지 bug의 대상(auction state)이 아님. bug는 external auction의 state에서 발생 (cross-contract). `changed` 채널 buggy/correct 둘 다 동일.

**(b) `@During amendAccountParticipation.arg[3] == 기대값` 시도**:
- Correct 기대값 = pre-penalty maltQuantity = `userMaltPurchased × amount / userCommitment`.
- `userMaltPurchased`, `userCommitment`는 **auction contract의 external state** — exitEarly scope에 없음.
- 이들을 얻으려면 `auction.getAuctionParticipationForAccount(...)` 호출 결과 필요. 이 호출은 `_calculateMaltRequiredForExit` 안에서만 일어남 — exitEarly 본문에는 없음.
- intentValue에 함수 호출 불가 (G1). @IReturn도 호출 사이트가 `_calculateMaltRequiredForExit` 내부라 exitEarly annotation에 binding 어려움.
- **표현 실패**.

**(c) `@During amendAccountParticipation.arg[3] == maltQuantity` (naive)**:
- Scope의 `maltQuantity` local 사용 → buggy에서 tautologically satisfied. Correct에서는 다른 값이라 violated.
- **Silent sanction** (I5 Mode-2) — 개발자가 "그냥 maltQuantity 넘기면 됨"이라 쓰면 buggy 재확인.

**(d) Auxiliary injection 경로 (I4)**:
- exitEarly 상단에 `(uint256 _userCommitment, , uint256 _userMaltPurchased) = auction.getAuctionParticipationForAccount(msg.sender, _auctionId);` 삽입.
- 그러면 `@During ... arg[3] == _userMaltPurchased * amount / _userCommitment` 작성 가능.
- 버그 인지 전제 — "pre-penalty / post-penalty 분리 필요" 판단이 fix 자체 수준.

#### 4. 분류 타당성 — **L4a 확정**

**문서 간 불일치 해결**: `limitation_types.md` (L4a) 가 맞고 `annotation_plans.md` (L5b) 가 틀림. 근거:

- I2 전지적 개발자 테스트: exitEarly scope 내 기존 변수만으로 grammar-expressible distinguishing annotation **존재하지 않음**.
- `userMaltPurchased`·`userCommitment`는 외부 auction contract state이자 exitEarly 함수 내부에 전혀 binding 없음.
- `annotation_plans.md`의 L5b 근거 ("wrong argument 전달 → bug awareness 필요")는 *arg가 틀렸음을 아는 것*에만 해당하고, *올바른 값을 grammar로 표현할 수 있는가*는 별개 — 표현 불가이므로 L4a.

**문서 업데이트 필요**: `annotation_plans.md` L2398–2402를 L4a 설명으로 수정. (확정 후 반영.)

#### 5. 근본 원인

**본질 (Type B — scope에 pre-penalty maltQuantity 부재)**:

exitEarly 함수는 `_calculateMaltRequiredForExit`의 반환 `maltQuantity` (post-penalty)와 `amount` (param), 자체 state만 가짐. 버그 수정에 필요한 pre-penalty maltQuantity, 그 구성 재료인 `userMaltPurchased`·`userCommitment`는 **다른 contract의 state**이며 exitEarly 본문에 어떤 형태로도 binding되지 않음. 기존 scope 변수의 산술 조합으로 correct 값 표현 불가.

더불어 버그의 원인적 구조는 **반환값의 이중 용도 collapse** — `_calculateMaltRequiredForExit`이 하나의 `maltQuantity`를 돌려주되 이것이 mint 용도(post-penalty)와 state 차감 용도(pre-penalty) 양쪽에 쓰임. 이 두 용도가 penalty 유무에서 갈리는데, **함수는 penalty 적용 후 버전만 반환**. Pre-penalty가 중간 단계(L195)에서 존재했다가 L209 overwrite로 사라짐 — local scope의 transient 값.

**Case 4 (39_H_02)와의 유사성**:
- 둘 다 external state-modifying call에 **잘못된 인자 전달**.
- 둘 다 correct 값이 external contract state(ERC20 balance / auction participation)에 의존.
- 둘 다 "한 변수를 이중 용도로 쓴 결과"라는 조합적 오류 (Case 4: sender 순수익 collapse, Case 7: maltQuantity collapse).
- **쌍둥이 패턴** — "dual-use value without decomposition".

G-표면:
- **G3 (primary)** — pre-penalty maltQuantity 값이 exitEarly scope 부재.
- **G1** — 필요 값 얻으려면 `auction.getAuctionParticipationForAccount(...)` 호출이 exitEarly에 없음 + intent grammar에 함수 호출 불허.
- **G8** — external contract state 의존.

**Silent sanction (I5)**:
- 개발자가 L83–88의 코드를 그대로 annotation으로 옮기면 (`@During ... arg[3] == maltQuantity`) buggy tautologically 통과.
- Case 3·4·6과 동일 pattern: 자연스러운 local reference 기반 annotation이 buggy를 재확인.

**Aux injection 가능성 (I4)**:
- 가능하나 pre-penalty 분리 판단 자체가 fix의 핵심 — 버그 인지 전제.

**[Category (I8)]**: **Algorithm error / Type B** — 단일 값의 dual-use collapse가 algorithmic 오류. Fix는 값 분리 (decomposition) 요구. Case 4와 쌍둥이 구조. L4a 정통, axis α (external view call 결과 필요 + scope 밖 변수 참조).

---

### Case 8 — `web3bugs_61_H_01` (현재 분류: **L4a** → 재분류 제안: **L5b**)

#### 1. Audit report 인용

- **출처**: `reports/61.md` → `[H-01] In CreditLine#_borrowTokensToLiquidate, oracle is used wrong way`
- **Severity**: High. **Warden**: 0x0x0x (C4 2021-12-sublime).
- **핵심 주장 (원문 발췌)**:
  > Current implementation:
  > `(uint256 _ratioOfPrices, uint256 _decimals) = IPriceOracle(priceOracle).getLatestPrice(_borrowAsset, _collateralAsset);`
  >
  > But it should not consult `borrowToken / collateralToken`, rather it should consult the **inverse**. As a consequence, in `liquidate` the liquidator/lender can lose/gain funds as a result of this miscalculation.
- **권고 fix**: `getLatestPrice(_collateralAsset, _borrowAsset)` — 두 인자 위치 swap.
- **Sponsor**: ritik99 confirmed.

#### 2. 코드 의미 이해

##### (2a) Contract 목적 & 시스템 위치

`CreditLine` — Sublime의 **P2P 대출 프로토콜** 핵심 컨트랙트. Lender가 대출 한도를 제공하고 borrower가 담보를 예치하여 차용. Liquidation 시 담보를 borrow token으로 환산해 청산 처리.

##### (2b) 함수의 컨트랙트 내 역할

`_borrowTokensToLiquidate(_borrowAsset, _collateralAsset, _totalCollateralTokens) → uint256` (L1045–1056, internal view):
- Caller: `liquidate` (L996, autoLiquidation 분기), public `borrowTokensToLiquidate` (view wrapper).
- 역할: "이만큼의 collateral을 청산하려면 liquidator가 몇 개의 borrow token을 필요하는가" 계산. Reward fraction 차감 후 oracle 비율로 환산.

##### (2c) 함수 의도 (수식)

Intended:
```
_borrowTokens = _totalCollateralTokens
              × (1 - liquidatorRewardFraction)
              × (collateral/borrow price ratio)
```
즉 "n개 collateral × (collateral 단가 / borrow 단가) = n개 collateral의 borrow-equivalent 수량". Oracle의 `getLatestPrice(A, B)` 규약 = `A_price / B_price` (대개).

##### (2d) Line-by-line 분석 (L1045–1056)

```solidity
1045  function _borrowTokensToLiquidate(
1046      address _borrowAsset,
1047      address _collateralAsset,
1048      uint256 _totalCollateralTokens
1049  ) internal view returns (uint256) {
1050      (uint256 _ratioOfPrices, uint256 _decimals) = IPriceOracle(priceOracle).getLatestPrice(
1051          _borrowAsset, _collateralAsset);          // BUG — arg order swapped
1052      uint256 _borrowTokens = (
1053          _totalCollateralTokens
1054              .mul(uint256(10**30).sub(liquidatorRewardFraction))
1055              .div(10**30)
1056              .mul(_ratioOfPrices)
1057              .div(10**_decimals)
1058      );
1059      return _borrowTokens;
1060  }
```

- **L1050–1051 (BUG)**: `getLatestPrice(_borrowAsset, _collateralAsset)` — borrow/collateral 비율을 받음. Correct는 collateral/borrow 필요.
- **L1052–1058**: `_borrowTokens = collateral_amount × (1 - reward) × _ratioOfPrices / 10^decimals`. 수식 구조는 OK, 단 `_ratioOfPrices`가 뒤집힘.

**결과**:
- 가령 collateral 가격 $100, borrow 가격 $1 → correct ratio = 100, buggy ratio = 0.01.
- collateral 10개의 correct borrow-eq = 10 × 100 = 1000.
- Buggy = 10 × 0.01 = 0.1.
- 10^4 배 차이. Liquidator는 거의 무료로 담보 탈취 가능 (borrow token만 0.1개로 1000개 가치 collateral 획득).

##### (2e) 버그의 근본 의미

Oracle 호출 convention 위반. 같은 contract의 다른 호출 사이트들과의 **pattern inconsistency**:
- L442 (`calculateBorrowableAmount`): `getLatestPrice(_collateralAsset, _borrowAsset)` — **correct order** 사용.
- L869 (`calculateCurrentCollateralRatio`): `getLatestPrice(_collateralAsset, _borrowAsset)` — **correct**.
- L931 (`withdrawableCollateral`): `getLatestPrice(_collateralAsset, _borrowAsset)` — **correct**.
- L1050 (`_borrowTokensToLiquidate`): **BUGGY 혼자 swap**.

즉 **같은 컨트랙트 4개 호출 사이트 중 하나만 틀림**. 단순 오타/copy-paste 오류 수준. Protocol 설계 지식보다는 **call convention 일관성** 검사로 잡히는 버그.

##### (2f) 올바른 fix

한 줄 수정: `_borrowAsset, _collateralAsset` → `_collateralAsset, _borrowAsset` swap.

#### 3. IntentChecker annotation 시도 (개발 시점 관점)

**함수 scope 변수**: `_borrowAsset`, `_collateralAsset` (params), `_ratioOfPrices`, `_decimals`, `_borrowTokens` (locals), contract state (`priceOracle`, `liquidatorRewardFraction`).

**(a) state 변화?** `_borrowTokensToLiquidate`는 internal view — storage write 없음.

**(b) `@Post returnExpression == correct_formula` 시도**:
- Correct formula requires `_ratioOfPrices_correct = getLatestPrice(_collateralAsset, _borrowAsset).ratio`.
- `_ratioOfPrices` local은 **buggy 값** — correct 값은 scope에 없음.
- `@Post return == ... * correct_ratio / ...` 표현에 correct_ratio 표현 불가 (G1: 함수 호출 불허, Type B for ratio).
- 이 경로만으로는 L4a처럼 보임.

**(c) `@During .arg[n]` 채널** (결정적 관찰):

`getLatestPrice.arg[0] == _collateralAsset` 형태 annotation 시도:

```solidity
// @During IPriceOracle(priceOracle).getLatestPrice.arg[0] == _collateralAsset
(uint256 _ratioOfPrices, uint256 _decimals) = IPriceOracle(priceOracle).getLatestPrice(
    _borrowAsset, _collateralAsset);   // buggy
```

- **Buggy**: arg[0] = `_borrowAsset` ≠ `_collateralAsset` → **VIOLATED**.
- **Correct (fix 후)**: arg[0] = `_collateralAsset` → **SATISFIED**.
- `_collateralAsset`은 함수 parameter로 scope 안. Grammar 전부 허용.

→ **distinguishing annotation이 grammar-expressible로 존재**. `limitation_types.md` L5b 예 `pool0.swap.arg[0] == 0` (52_H_15)과 **정확히 같은 패턴**: 인자 순서 오류를 `.arg[n]`으로 포착.

**개발자의 annotation 작성 노동**:
- 같은 contract 다른 3곳(L442, L869, L931)에서 `_collateralAsset` 먼저 쓰는 패턴 관찰 → convention 추론.
- L1050에도 동일 convention을 annotation으로 assert.
- 이 annotation 작성은 **deep domain knowledge 불필요**, 단지 contract 내 pattern 일관성만 보면 됨.
- 그러나 "assert해야 한다"는 결정 자체는 버그 인지 전제 — convention이 자동 강제되지 않으므로.

#### 4. 분류 타당성 — **L4a 유지** (L5b 제안 철회)

**L5b 제안 검토 및 철회**:

초기 분석에서 `@During IPriceOracle.getLatestPrice.arg[0] == _collateralAsset` annotation이 grammar-expressible하고 buggy/correct를 구분하므로 L5b로 제안. 그러나 **I9 원칙 (L5b 판정은 semantic intent 채널 기준)** 적용 시 철회:

- `.arg[n]` 채널은 **lint-style pattern check** (argument identifier 선택을 source code 수준에서 검사). IntentChecker 고유 기여 영역이 아니며 paper의 L5b 근거로 쓰기 약함.
- Semantic intent 채널 = `_ratioOfPrices` 반환값의 의미 (`collateral_price / borrow_price` 비율) 검증. 여기서는:
  - `@IReturn`이 `IPriceOracle.getLatestPrice`에 **arg-indifferent concrete 반환값 하나만 공급**.
  - Buggy 코드 `getLatestPrice(_borrow, _collateral)` 와 correct 코드 `getLatestPrice(_collateral, _borrow)` 모두 엔진 관점에서 **같은 `_ratioOfPrices` 값 수신**.
  - 하류 `_borrowTokens` 계산도 동일 → `@Post returnExpression == ...` 어떤 expression도 buggy/correct 구분 불가.
- → **Semantic intent 채널에서 표현 불가** → **L4a 확정**.

**L4a (`inexpressible-expected-value`) 근거**:
- Correct `_ratioOfPrices` 값 = `collateral_price / borrow_price` (oracle 의미).
- 이 값은 oracle 반환의 수치 의미이며 scope 내 변수의 산술 조합으로 표현 불가.
- `@IReturn` 공급값은 구성적으로 buggy 코드가 받는 값과 구분되지 않음 (arg-indifference).
- 따라서 intent annotation이 어떤 proxy를 쓰든 진짜 correct 의미를 표현할 수 없음.

**L4a vs L4b 선택**:
- L4b는 "no-target-storage — attach point 부재"의 구조적 한계 (view 함수 전형).
- 본 case는 return-based `@Post returnExpression == expr` 채널 자체는 열려 있음. 문제는 `expr` 자리에 correct 값을 쓸 수 없음 — **표현 불가** 문제.
- → L4a가 맞음. View 함수 성격은 부차적.

#### 5. 근본 원인

**본질 (Type B — `_ratioOfPrices` semantic 의미 표현 불가)**:

`_borrowTokensToLiquidate` scope에는 `_ratioOfPrices` (oracle 반환 local)가 있으나 이는 **@IReturn으로 공급된 concrete 값**. 그 **수치 의미 (collateral/borrow vs borrow/collateral)** 는 scope 어디에도 저장되지 않음. Correct 의미를 assert하려면 "oracle이 돌려준 값의 convention이 올바른가"를 검사해야 하는데, 이 convention은 **external oracle API 명세**로 scope 밖.

분석 엔진 관점에서 buggy와 correct는 **구분 불능**:
- @IReturn이 arg-indifferent로 동일 값 공급 → 엔진 계산 동일.
- Semantic intent annotation으로 어떤 expression을 써도 buggy/correct 모두 같은 판정.

G-표면:
- **G1** — `IPriceOracle.getLatestPrice(...)`의 **의미적 반환값**을 intent에서 참조할 방법 없음.
- **G3** — `collateral_price`, `borrow_price` 같은 소스 값이 scope에 없음 (`@IReturn`은 비율만 반환).
- **G8** — external oracle state 의존.
- **@IReturn arg-indifference** (분석 엔진 특유 한계): 같은 함수의 서로 다른 arg 순서 호출을 구분하지 않음. I1의 "debug annotation vs intent annotation 분리" 원칙의 구체 발현.

**Case 2·7과의 유사성 (Value/Type B 축)**:
- Case 2 (25_H_05): hardcoded `18` 대신 필요한 `10 + uD` — external underlying decimals 의존.
- Case 7 (59_H_05): post-penalty `maltQuantity` 대신 필요한 pre-penalty — external auction state + scope 내 transient 값 소실.
- **Case 8 (본 case)**: `_ratioOfPrices`의 buggy 의미 대신 필요한 correct 의미 — external oracle API convention 의존.

세 case 모두 **"value error / Type B"** 공통 cell. 모두 외부 state/convention 의존.

**`.arg[n]`으로 잡히긴 하나 lint-level (I9)**:
- `.arg[n]` 채널은 syntactic lint tool (Slither 등)도 pattern-matching으로 포착 가능한 영역.
- IntentChecker novelty 주장에 포함하지 않음.
- 단순 arg 순서 오류는 현대 정적분석 도구가 covers하는 영역으로 인정.

**[Category (I8)]**: **Value error / Type B** — correct oracle ratio의 semantic 의미가 scope 변수·상수의 산술 조합으로 표현 불가. `@IReturn` arg-indifference가 debug annotation 채널로의 우회도 봉쇄. Case 2·7과 같은 cell.

#### 6. paper 문장 개선 제안

- **`.arg[n]` 채널 언급 자제**: Paper에서 Case 8을 L5b로 프레이밍하면 L5b-syntactic으로 하락 — 기존 lint 도구 영역. L4a (semantic intent 표현 불가) 프레이밍이 paper 기여도 강화.
- **@IReturn arg-indifference 관찰**: Debug annotation의 구조적 한계 — 같은 함수의 argument 변이를 구분하지 않음. 이는 I1 (annotation vs engine 분리)의 구체 발현이자 **별도 제한 축**으로 언급 가치.
- **기존 L5b 분류 재검토 암시**: I9 원칙으로 52_H_15, 113_H_05, 35_H_11도 semantic 채널에서 catch 가능한지 검토 필요. L5b 섹션 진입 시 체계적 재평가.
- **`annotation_plans.md` 수정 필요**: L1830–1836의 L4a 근거는 기본적으로 맞으나 `@IReturn` arg-indifference를 primary로 강조. `.arg[n]` 우회는 lint로 간주해 배제.

---

### Case 9 — `web3bugs_61_H_02` (분류 불일치: limitation_types.md = **L4a**, annotation_plans.md = L5a → 객관 판정: **L4a**)

#### 1. Audit report 인용

- **출처**: `reports/61.md` → `[H-02] Wrong returns of SavingsAccountUtil.depositFromSavingsAccount() can cause fund loss`
- **Severity**: High. **Warden**: WatchPug (C4 2021-12-sublime).
- **핵심 주장 (원문 발췌)**:
  > `savingsAccountTransfer()` does not return the result of `_savingsAccount.transfer()`, but returned `_amount` instead, which means that `SavingsAccountUtil.depositFromSavingsAccount()` may not return the actual shares (when pps is not 1).
- **POC**:
  > Given the price per share of yearn USDC vault is `1.2`:
  > 1. Alice deposited 12,000 USDC to yearn strategy, received 10,000 share tokens.
  > 2. Alice created a pool, added all 12,000 USDC from savings account as collateral. The recorded `CollateralAdded` got the wrong number: **12000** (should be **10000**).
  > 3. `cancelPool()` fails (recorded shares > actual). **Alice loses all 12,000 USDC**. Liquidation also fails → lender fund loss.
- **권고 fix**:
  ```solidity
  function savingsAccountTransfer(...) internal returns (uint256) {
      if (_from == address(this)) return _savingsAccount.transfer(...);
      else return _savingsAccount.transferFrom(...);
  }
  ```
  즉 L79의 `return _amount;` 제거하고 interface call 결과를 직접 return.

#### 2. 코드 의미 이해

##### (2a) Contract 목적 & 시스템 위치

`SavingsAccountUtil` — Sublime의 **savings account (yield-bearing 지급 계좌)**와 pool/credit line 사이의 wrapper library. Token transfer에 해당하는 **shares** 단위 처리를 매개.

Savings account: Yearn 같은 yield strategy에 예치되어 price-per-share (pps)가 1이 아닐 수 있음. 사용자가 12,000 USDC를 예치해도 shares 단위로는 10,000 (pps=1.2일 때). 하류 회계는 **shares 기준**으로 해야 정확.

##### (2b) 함수의 컨트랙트 내 역할

`savingsAccountTransfer(_savingsAccount, _from, _to, _amount, _token, _strategy) → uint256` (L66–80, internal library):
- Caller: `depositFromSavingsAccount` (L11–26) → Pool·CreditLine의 deposit/withdraw 흐름.
- 역할: savings account 간 shares 이동 실행 + **이동된 실제 shares 반환**.
- 반환값은 upstream의 `_sharesReceived`로 저장되어 `poolVariables.baseLiquidityShares` 등 critical accounting에 사용.

##### (2c) 함수 의도 (수식)

Intended:
- Call `_savingsAccount.transfer(...)` which moves shares and returns actual share count.
- Return that share count to caller.
- Caller records shares for future withdraw/liquidation.

Intent 핵심: "**shares 단위 정확성 유지**". Token amount ≠ shares when pps ≠ 1.

##### (2d) Line-by-line 분석 (L66–80)

```solidity
66  function savingsAccountTransfer(
67      ISavingsAccount _savingsAccount,
68      address _from,
69      address _to,
70      uint256 _amount,
71      address _token,
72      address _strategy
73  ) internal returns (uint256) {
74      if (_from == address(this)) {
75          _savingsAccount.transfer(_amount, _token, _strategy, _to);   // BUG — return 무시
76      } else {
77          _savingsAccount.transferFrom(_amount, _token, _strategy, _from, _to);   // BUG — return 무시
78      }
79      return _amount;   // BUG — shares 대신 token amount 반환
80  }
```

- **L74–75**: `_from == address(this)`일 때 `_savingsAccount.transfer(...)` 호출. 이 함수는 **state-modifying** (balances 변경) 이며 shares를 반환. 그러나 여기서는 **반환값 무시**.
- **L76–77**: 다른 분기, `transferFrom` 호출. 역시 반환값 무시.
- **L79 (BUG)**: `_amount` 그대로 반환. `_amount`는 token 단위 (USDC 등). pps ≠ 1이면 실제 shares와 mismatch.

결과: caller가 `_sharesReceived = 12,000` (실제 shares는 10,000)으로 기록. 이후 `cancelPool()`/`liquidate()` 시 12,000 shares 인출 시도 → 실제로는 10,000 shares만 있으므로 실패 → 자금 영구 락.

##### (2e) 버그의 근본 의미

**Return value scope mismatch**. Interface call (`transfer`/`transferFrom`)이 state-modifying이면서 유용한 return value (shares)를 제공. 그러나 buggy 코드는 이 반환을 **capture하지 않고** (local에 저장 안 함) 대신 무관한 parameter (`_amount`)를 반환.

본질적으로 "**반환값 연결 실패**" — external call의 결과가 caller에게 전달되어야 하는데 중간 wrapper에서 소실. 한 단계 indirection이 accounting unit (token amount vs shares) 변환 기회를 놓침.

Protocol-level: token amount와 shares를 혼동한 회계 → pool liquidity tracking 파손. Alice POC처럼 full 자금 락 가능. lender 자금 손실.

##### (2f) 올바른 fix

Audit 권고 그대로. `return _savingsAccount.transfer(...)` — interface call의 return을 **직접 return으로 연결**. 혹은:
```solidity
uint256 _sharesReceived = _savingsAccount.transfer(_amount, _token, _strategy, _to);
return _sharesReceived;
```
두 경우 모두 **새 local 도입 혹은 return 식에 interface call 직접 사용**.

#### 3. IntentChecker annotation 시도 (개발 시점 관점)

**함수 scope 변수**: parameters만 (`_savingsAccount`, `_from`, `_to`, `_amount`, `_token`, `_strategy`). **Local 변수 없음**. Library 함수라 state 없음.

**(a) state 변화?** Library 본문 state write 없음. Storage 채널 닫힘.

**(b) `@Post returnExpression == correct_shares` 시도**:
- Correct value = `_savingsAccount.transfer(...)`의 반환. 
- 이 값이 scope에 없음 (local에 저장 안 함 — 바로 그게 버그).
- `@IReturn`으로 공급 가능? → **`transfer`는 state-modifying interface call**. `@IReturn`은 **view/pure 전용** → 적용 불가.
- Grammar에 함수 호출 불허. `@Post returnExpression == _savingsAccount.transfer(...)` 표현 불가 (G1).
- 결과: correct 값을 reference할 어떤 경로도 없음.

**(c) `@Post returnExpression == _amount` (naive)**:
- Grammar OK. Buggy: `_amount == _amount` tautology. Satisfied.
- Correct: shares 반환 → `shares == _amount` → pps ≠ 1이면 VIOLATED.
- 이는 **false positive on correct**. 즉 개발자가 자연스럽게 "return == _amount"라고 annotation 쓰면 buggy 보증, correct 위반. **I5 silent sanction 재등장**.

**(d) `.arg[n]` 채널**: transfer/transferFrom의 arg 검사로 bug 포착 불가 — arg는 buggy/correct 동일.

**(e) Auxiliary local 주입 (I4)**:
- `uint256 _sharesReceived = _savingsAccount.transfer(...);` 삽입.
- 그러면 `@Post returnExpression == _sharesReceived` 작성 가능.
- 그러나 **이 주입 자체가 fix**. Audit 권고 fix 구조와 동일 → 버그 인지 전제.

#### 4. 분류 타당성 — **L4a 확정** (annotation_plans.md의 L5a 철회)

**annotation_plans.md L5a 주장의 자기모순**:
- "올바른 fix: return capture assignment 누락 (L5a)"
- "annotation grammar에서 함수 호출 불가 → `returnExpression == _savingsAccount.transfer(...)` 표현 불가"

두 문장이 양립 불가. L5a는 "post-condition **표현 가능**, 버그 인지만 부족"이어야 하는데, 위 두 번째 문장은 표현 불가를 인정. → **L5a 조건 불충족**.

**L4a (inexpressible-expected-value) 확정 근거**:
- Correct shares 값이 scope에 부재 (local 미저장 = 버그 자체).
- `@IReturn` 경로 봉쇄 (state-modifying interface).
- Grammar 함수 호출 불허.
- 결론: **전지적 개발자조차 기존 scope로 correct annotation 작성 불가** → L4a 확정.

**L4a vs L4b**:
- Library 함수 (no storage) → L4b 후보.
- 그러나 return-based `@Post`는 원칙적으로 열려 있음. 문제는 **correct 표현 불가** (value).
- **L4a primary** (표현 불가), L4b는 부차 (구조적 no-state는 sub-factor).

**limitation_types.md (L4a) 확정**, annotation_plans.md 수정 필요.

#### 5. 근본 원인

**본질 (Type B — state-modifying interface call의 semantic 반환값이 scope에 미저장)**:

`savingsAccountTransfer` scope는 parameters만. Interface call (`transfer`/`transferFrom`)의 **shares 반환이 scope에 binding 없음** — 버그가 곧 이 binding 누락. 이 값의 의미(shares)는 oracle/external spec에 정의되며 scope 내 어떤 산술 조합으로도 구할 수 없음.

Debug annotation 경로도 봉쇄:
- **`@IReturn`이 view/pure 전용**이라 state-modifying `transfer()`에 적용 불가.
- 이는 I1 (annotation layer vs engine layer 분리)의 **구체적 제약 발현**: debug annotation이 engine에게 공급할 수 있는 값의 범위가 state-modifying interface에서 끊김.

G-표면:
- **G1** — `transfer(...)`를 intent에서 참조 불가 (함수 호출 grammar 부재).
- **G3** — shares 값이 local로 저장 안 되어 scope 부재.
- **G8** — external contract state 의존 (pps, shares balance).
- **@IReturn 제한** (보조) — state-modifying interface에 debug 값 공급 불가.

**Case 7 (59_H_05)과의 쌍둥이 성격**:
- Case 7: dual-use value collapse — `_calculateMaltRequiredForExit` 반환이 두 용도에 쓰이는데 둘 중 하나만 맞음.
- Case 9 (본 case): interface call 반환을 무시하고 parameter를 대신 return — **반환값 교체 오류**.
- 둘 다 **"반환값 연결" 관련 버그**. Case 7은 collapse, Case 9는 drop.
- 둘 다 "wrapper/helper function"이 하류로 잘못된 value를 전달하는 구조.

**Silent sanction (I5) 강함**: 자연스러운 annotation `returnExpression == _amount`가 buggy tautologically 통과, correct에서 violated. **fail-by-confirmation** — 개발자가 코드 텍스트 그대로 intent를 옮기면 bug 인증.

**Aux injection (I4)**: 주입 = fix 자체. Case 5처럼 "injection이 곧 수정".

**[Category (I8)]**: **Value error / Type B** — 반환 값이 wrong (parameter 대신 interface call 결과). Fix는 한 줄 (`return _savingsAccount.transfer(...)`). Correct 값이 scope 부재 + `@IReturn` 봉쇄. Cases 2, 7, 8과 같은 cell.

#### 6. paper 문장 개선 제안

- **`@IReturn`의 view/pure 제한이 별도 G-category 필요**: Debug annotation system의 구조적 제약으로, state-modifying interface call의 return을 공급할 수 없다는 점이 L4a 발생의 **독립 원인**. Case 9, 그리고 앞으로의 case에서 반복될 가능성.
- **`annotation_plans.md` L2336–2341 수정 필요**: L5a→L4a로 정정. L5a의 전제인 "post-condition 표현 가능"이 거짓이라 L5a는 논리적으로 성립 안 됨.
- **Silent sanction 강조**: 자연스러운 `return == _amount` annotation이 buggy 인증하는 fail-by-confirmation — paper에서 **"developer writes intent matching code text, not protocol spec"**의 대표 예시로 인용 가치.
- **Case 7 + Case 9 쌍둥이**: wrapper function의 반환값 처리 오류 (collapse vs drop) — L4a 내 **"wrapper layer return misrouting" sub-pattern** 으로 묶을 수 있음. 34 case 완주 후 sub-pattern 통계 제시.

---

### Case 10 — `web3bugs_61_H_04` (현재 분류: **L4a**)

#### 1. Audit report 인용

- **출처**: `reports/61.md` → `[H-04] Yearn token <> shares conversion decimal issue`
- **Severity**: High. **Warden**: cmichel (C4 2021-12-sublime).
- **핵심 주장 (원문 발췌)**:
  > The yearn strategy `YearnYield` converts shares to tokens by `pricePerFullShare * shares / 1e18`. But Yearn's `getPricePerFullShare` seems to be in `vault.decimals()` precision, i.e., it should convert as `pricePerFullShare * shares / (10 ** vault.decimals())`. The vault decimals are the same as the underlying token decimals.
- **Impact**: "The token and shares conversions do not work correctly for underlying tokens that do not have 18 decimals. Too much or too little might be paid out leading to a loss for either the protocol or user."
- **권고 fix**: "Divide by `10**vault.decimals()` instead of `1e18`."
- **Sponsor**: ritik99 confirmed.

#### 2. 코드 의미 이해

##### (2a) Contract 목적 & 시스템 위치

`YearnYield` — Sublime의 Yearn V2 vault 어댑터 strategy. `SavingsAccount`가 예치된 자산을 Yearn vault에 locking. `lockTokens` / `unlockTokens` / `getTokensForShares` / `getSharesForTokens` API 제공.

Yearn vault의 `getPricePerFullShare()` = "1 share가 몇 units의 underlying token에 해당하는가"를 **vault의 decimals precision**으로 반환. Yearn spec: `vault.decimals == underlying_token.decimals` (USDC vault → 6, DAI vault → 18).

##### (2b) 함수의 컨트랙트 내 역할

`getTokensForShares(shares, asset) → amount` (L178–181, public view):
- Caller: SavingsAccount, CreditLine 등 여러 곳에서 shares ↔ token amount 변환에 사용.
- 역할: "이만큼의 shares는 몇 units의 underlying token과 같은가" 계산.
- 잘못된 변환은 withdraw/liquidation 등 자산 이동 정확성 훼손.

##### (2c) 함수 의도 (수식)

```
amount = pricePerFullShare × shares / 10^(vault.decimals)
```
여기서 `pricePerFullShare`는 vault의 decimals 배율로 표현된 pps.

USDC vault (decimals=6) 예시:
- pps = `1.05 * 1e6` = `1050000` (1 share = 1.05 USDC).
- shares = `1000`.
- correct amount = `1050000 * 1000 / 1e6 = 1050`. (1000 shares = 1050 USDC units = 0.00105 USDC in human, but uint representation is 1050 * 1e6-scaled... wait I need to recheck scales).

Actually Yearn's convention: shares are in vault's own decimals (same as underlying). So:
- 1000 shares (uint) = 1000 * 10^(-6) = 0.001 vault share tokens in human.
- pps = 1.05 (in decimals, represented as `1050000` = 1.05 * 1e6).
- correct amount = `1050000 * 1000 / 1e6 = 1050` → 0.00105 USDC (uint 1050).

Buggy divides by 1e18: `1050000 * 1000 / 1e18 ≈ 0` (underflow). 거의 0 반환 → 시스템 중대 오류.

18-dec 토큰 (DAI)에서는 우연히 맞음 (buggy·correct 동일 결과). 6-dec·8-dec 토큰에서 심각 오류.

##### (2d) Line-by-line 분석 (L178–181)

```solidity
178  function getTokensForShares(uint256 shares, address asset) public view override returns (uint256 amount) {
179      if (shares == 0) return 0;
180      amount = IyVault(liquidityToken[asset]).getPricePerFullShare().mul(shares).div(1e18);   // BUG
181  }
```

- **L179**: 빠른 반환.
- **L180 (BUG)**: 
  - `IyVault(liquidityToken[asset])`: vault 주소 획득.
  - `.getPricePerFullShare()`: vault의 pps, **vault.decimals precision**.
  - `.mul(shares).div(1e18)`: 1e18로 나눔 (잘못됨).
  - Correct는 `.div(10 ** vaultDecimals)` — vault decimals로 나눠야 pps의 scaling 제거 → rate가 "1.0 기반 실수"로 복원.

**Systematic scaling error**: 모든 non-18-dec underlying 자산에 대해 `10^(18-vaultDecimals)` 배 오차. USDC (6-dec) = 10^12 배 왜곡. WBTC (8-dec) = 10^10 배.

##### (2e) 버그의 근본 의미

Cross-protocol convention 가정 오류. Yearn V1은 18-dec precision을 썼으나 V2는 **vault.decimals precision**으로 변경. 개발자가 V1 convention (`1e18` 분모) 가정으로 코드 작성. non-18-dec 토큰에서 shares↔token 변환이 protocol 전반에 걸쳐 체계적으로 왜곡.

Protocol-level: 
- Withdraw 시 실제 상환 금액이 0에 가깝거나 무한대 → user/lender 자금 영구 손실.
- Liquidation 시 담보 평가 왜곡 → 부당 liquidation 혹은 방어 불가.

##### (2f) 올바른 fix

Audit 권고:
```solidity
amount = IyVault(liquidityToken[asset]).getPricePerFullShare()
    .mul(shares)
    .div(10 ** IyVault(liquidityToken[asset]).decimals());   // vault.decimals()
```
혹은 동등하게 underlying token의 decimals 사용.

#### 3. IntentChecker annotation 시도 (개발 시점 관점)

**함수 scope 변수**: `shares`, `asset` (params). `amount` (return). State: `liquidityToken` mapping.

**(a) `@Post amount == pps_value * shares / (10 ** vaultDecimals)` 시도**:

Correct annotation의 구성 요소:
- `pps_value`: `IyVault(liquidityToken[asset]).getPricePerFullShare()` 반환. Scope에 local 없음.
- `vaultDecimals`: `IyVault(liquidityToken[asset]).decimals()` 반환. **Buggy 코드에 해당 호출 자체가 없음**.
- `10 ** vaultDecimals`: `**` 연산자 **annotation grammar 부재** (G2 annotation-only — 엔진은 지원).

세 가지 blocker 겹침:
- `pps_value` 접근: `@IReturn`으로 getPricePerFullShare 반환 공급 가능 (view). 그러나 intent expression에 함수 호출 불허이므로 `@Post amount == <IyVault(..).getPricePerFullShare()> * shares / ...` 자체가 표현 불가. `@IReturn`은 debug 공급이지 intent 표현 수단 아님 (I1).
- `vaultDecimals` 접근: 해당 호출이 buggy 코드에 부재 → `@IReturn` 붙일 call site 없음. 호출을 intent에 직접 쓸 수도 없음.
- `10 ** x`: grammar에 `**` 부재.

**(b) 자연 annotation `@Post amount == pps * shares / 1e18` 시도**:

Grammar 허용하나 buggy 코드 공식 그대로 → **tautologically satisfied** in buggy, violated in correct (non-18-dec 토큰). **I5 silent sanction 전형**. Developer가 `1e18`을 자연스럽게 쓰면 buggy 인증.

**(c) Aux injection (I4) — `**` grammar 포함 시**:
- 개발자가 두 local 주입:
  ```solidity
  uint256 pps = IyVault(liquidityToken[asset]).getPricePerFullShare();
  uint8 vaultDecimals = IyVault(liquidityToken[asset]).decimals();
  amount = pps.mul(shares).div(10 ** vaultDecimals);   // fix
  ```
- Annotation: `@Post amount == pps * shares / (10 ** vaultDecimals)` — grammar OK (`**` 지원 가정).
- **Detectable**. 단 주입 결정 = fix 자체 = 버그 인지 전제 → **L5 영역으로 transit (I4)**.

**즉 현재 grammar(`**` 포함) 하에서 L4a → L5 transit path는 viable**. Pure annotation-only workflow에서는 여전히 L4a (함수 호출 intent 불허 + 반환값 local 미저장).

**(d) Concrete value 접근**:
- 특정 vault instance로 고정: USDC vault → vaultDecimals = 6 → divisor = `1000000` literal.
- Annotation: `@Post amount == pps * shares / 1000000` — USDC scenario에만 유효.
- 모든 vault에 일반화 불가 → I6 general vs specific 경계.

#### 4. 분류 타당성 — **L4a 확정** (Case 1과 쌍둥이)

- I2 전지적 개발자 테스트: general form correct annotation 표현 불가 (G1+G2+G3 3중 봉쇄).
- `annotation_plans.md` L2026–2032의 분석 정확. "25_H_01과 동일 패턴"이라 명시된 대로.

#### 5. 근본 원인

**본질 (Value / Type B — Case 1과 구조적 쌍둥이)**:

Correct 나눗셈 분모 `10 ** vault.decimals()`가:
- **Scope 부재**: `vaultDecimals` 값을 담는 변수 없음 (`.decimals()` 호출 자체가 buggy 코드에 없음).
- **Call site 부재**: `@IReturn` 붙일 위치도 없음 → G3의 가장 엄격한 형태 (Case 25_H_05와 유사).
- **Grammar 봉쇄**: 설령 vaultDecimals 값을 주입해도 `10 ** x` 표현 불가 (G2 annotation-only).

**Case 1 (25_H_01)과의 미묘한 차이**:
- Case 1: `source.decimals` struct field가 snapshot proxy로 존재 (Type A_candidate).
- Case 10: vault.decimals 해당 proxy 전혀 없음 (**Type B 순수형**).
- Case 10이 Case 1의 **Type A 가능성을 완전히 제거한 청정 버전**.

**Case 2 (25_H_05)와의 유사성**:
- Case 2: `uD` (underlying decimals) 부재, `CTokenInterface(source).underlying()` + `IERC20(...).decimals()` chain 필요.
- Case 10: `vaultDecimals` 부재, `IyVault(liquidityToken[asset]).decimals()` 단일 호출 필요.
- 둘 다 **external view call 결과를 `10 + x` 혹은 `10 ** x` 연산에 넣어야 함**.
- 차이: Case 2는 `+`만 필요 (grammar OK), Case 10은 `**` 필요 (grammar 봉쇄).

G-표면 (grammar에 `**` 포함 가정):
- **G1** — `IyVault(...).decimals()`, `getPricePerFullShare()` intent 내 참조 불가.
- **G3** — `vaultDecimals` 값이 scope 부재 + `.decimals()` call site 부재. `getPricePerFullShare()`도 반환이 local에 저장 안 됨.

**Silent sanction (I5) 강함**: `amount == pps * shares / 1e18` 자연스런 annotation이 buggy 전형. Developer가 code text 그대로 intent로 옮기는 workflow에서 fail-by-confirmation.

**Aux injection 경유 L5 transit viable (I4)**: `**` grammar 지원 가정 하에서 `pps`, `vaultDecimals` 주입 후 annotation 가능. Pure annotation-only에서는 L4a 유지.

**I6 general vs specific**: USDC 같은 특정 vault instance로 고정 시 상수 `1000000` annotation은 grammar-expressible하나 모든 vault에 일반화 불가 → L5b-flavored. General annotation은 L4a.

**[Category (I8)]**: **Value error / Type B** — scaling divisor가 Case 2·61_H_01·61_H_02와 같은 cell. 특히 Case 2, 25_H_01과 **decimals-based scaling** sub-family.

#### 6. paper 문장 개선 제안

- **"Decimals-based scaling L4a family"**: Case 1 (25_H_01), Case 2 (25_H_05), Case 10 (61_H_04) 공통 — **`10^x` 형태의 scaling 오류가 L4a에서 반복**. Paper에서 sub-pattern으로 제시 가능. 해결하려면 grammar에 `**` 혹은 `pow(10, x)`를 허용하거나, convention-based scaling을 annotation으로 표현하는 별도 문법 도입.
- **`@IReturn` 활용 불가 명시**: L4a 다수가 `@IReturn`의 설계 경계(view/pure 전용 + arg-indifferent + intent 내 미사용) 때문에 우회 불가. 이는 **debug annotation system의 설계 trade-off**로 Discussion에 명시 가치.
- **Cases 1, 2, 10 "scaling trio"**: paper의 L4a 대표 예시로 이 3개를 묶어 제시 — decimals 처리의 정적 분석 한계를 구체화.

---

### L4a Subsection Summary (10 cases reviewed)

34 case 중 **10개 L4a case 전체 리뷰 완료**. 통계는 `l4_l5_classification.csv` 및 `l4_l5_classification.py stats()` 참조. Cross-cutting observations는 상단 I1–I9 insights 및 `paper_corrections.md` C1–C6에 누적. 다음 단계: **L4b section (8 cases)** 진입.

---

## L4b — No Target Storage (8 cases)

L4b 정의: 버기 함수가 target contract의 storage variable을 변경하지 않아 state-based intent annotation 부착 대상 부재. 주 유형: view/pure 함수, state-modifying이 없는 wrapper, library helper.

---

### Case 11 — `web3bugs_17_H_02` (분류 불일치: limitation_types.md = **L4b**, annotation_plans.md = L5a → 객관 판정: **L4b**)

#### 1. Audit report 인용

- **출처**: `reports/17.md` → `[H-02] Buoy3Pool.safetyCheck is not precise and has some assumptions`
- **Severity**: High (judge upgrade). **Wardens**: cmichel, shw (C4 2021-06-gro).
- **핵심 주장 (원문 발췌)**:
  > 1. Only checks if the `a/b` and `a/c` ratios are within `BASIS_POINTS`. By transitivity, `b/c` is only within `2 * BASIS_POINTS` if `a/b` and `a/c` are in range. For a more precise check whether both USDC and USDT are within range, `b/c` must be checked as well.
  > 2. If `a/b` is within range, this does not imply that `b/a` is within range.
  > 3. The NatSpec for the function states that it checks Curve and an external oracle, but no external oracle calls are checked.
- **Judge 승격 이유**: "A possibility of stopping deposits or withdrawals deserves high risk."
- **Sponsor**: kristian-gro confirmed, release version에 b/c check 추가.
- **권고 fix**: `b/c` ratio 체크 추가.

#### 2. 코드 의미 이해

##### (2a) Contract 목적 & 시스템 위치

`Buoy3Pool` — Gro protocol의 **price sanity checker**. Curve 3Pool (DAI, USDC, USDT) 위에서 pricing 관련 연산 제공. 핵심 역할: Curve pool에 flash loan 공격 등으로 가격이 depeg 됐는지 감지 → 감지 시 deposit/withdraw 차단.

`safetyCheck`는 **모든 상호작용 함수의 첫 gate** — 통과 못 하면 transaction revert.

##### (2b) 함수의 컨트랙트 내 역할

`safetyCheck() external view returns (bool)` (L87–96):
- Caller: Gro의 vault·controller가 deposit·withdraw·rebalance 전에 호출.
- 역할: Curve pool의 내부 (a, b, c) 가격 비율이 **직전에 캐시된 lastRatio와 BASIS_POINTS(20bp) 이내로 편차가 있는지** 검사. 통과시 true, 초과시 false.
- 잘못된 통과 → stablecoin depeg 상태에서 deposit/withdraw 허용 → 사용자 자금 탈취 가능.

##### (2c) 함수 의도 (NatSpec 기준)

NatSpec 발췌:
> "establishes a set of ratios (a/a, a/b, a/c), (b/b, b/a, b/c), (c/c, c/a, c/b). The following set should provide the necessary coverage checks: (a/b, a/c)"

NatSpec은 "(a/b, a/c)만 체크하면 충분"이라고 argue하지만, 이것이 본 버그의 근본 원인 — **transitivity 논리가 틀림**. `|a/b - last_a/b| ≤ ε` ∧ `|a/c - last_a/c| ≤ ε` 이어도 `|b/c - last_b/c| ≤ 2ε`까지만 보장. 따라서 `ε`(BASIS_POINTS) 내 b/c 변동은 감지 못함.

또한 NatSpec은 "Curve + external oracle 비교"를 언급하나 **이 함수는 oracle call 없음** (`_updateRatios`에만 있음).

##### (2d) Line-by-line 분석 (L87–96)

```solidity
87  function safetyCheck() external view override returns (bool) {
88      for (uint256 i = 1; i < N_COINS; i++) {       // i = 1, 2만 iterate (N_COINS=3)
89          uint256 _ratio = curvePool.get_dy(int128(0), int128(i), getDecimal(0));
90          _ratio = abs(int256(_ratio - lastRatio[i]));
91          if (_ratio.mul(PERCENTAGE_DECIMAL_FACTOR).div(CURVE_RATIO_DECIMALS_FACTOR) > BASIS_POINTS) {
92              return false;
93          }
94      }
95      return true;
96  }
```

- **L88**: `i = 1..2` — token 0(DAI)에서 token 1(USDC), token 2(USDT)로의 비율만 체크. **token 1 ↔ token 2 (b/c) 는 loop에 없음**.
- **L89**: Curve `get_dy(from=0, to=i, amount_in=1 unit of 0)` → 1 unit DAI 스왑 시 얼마나 USDC/USDT 나오는지. 즉 a/b, a/c.
- **L90**: `lastRatio[i]`와 절대값 차이. `lastRatio`는 `_updateRatios`에서 oracle-sanitized된 Curve 값.
- **L91**: 차이가 BASIS_POINTS(20bp) 초과면 **false** 반환.
- **L95**: 둘 다 통과하면 true.

**누락**:
- 핵심 누락: **i 조합에서 `(from=1, to=2)` 즉 b/c** 체크.
- External oracle 비교 없음 (NatSpec은 언급).

##### (2e) 버그의 근본 의미

**Transitivity 오추론**. 개발자가 "a/b OK && a/c OK → b/c도 OK"라고 가정했으나, 수학적으로 2-BP 범위까지만 보장:
- `|a/b - last_a/b| ≤ 20bp`
- `|a/c - last_a/c| ≤ 20bp`
- ⇒ `|b/c - last_b/c| ≤ 40bp` (최악). 즉 실제로는 BASIS_POINTS의 2배까지 b/c가 depeg 가능.

Attack 시나리오:
- Flash loan으로 Curve 3Pool의 USDC/USDT 비율만 30bp 왜곡 (a/b, a/c는 각 15bp씩 변동 → 둘 다 20bp 이하 통과).
- safetyCheck true 반환 → 공격자 deposit/withdraw 실행.
- Curve가 왜곡된 가격으로 LP 토큰 산정 → 공격자 이익, 나머지 LP 손실.

##### (2f) 올바른 fix

```solidity
function safetyCheck() external view override returns (bool) {
    // a/b, a/c (기존)
    for (uint256 i = 1; i < N_COINS; i++) {
        uint256 _ratio = curvePool.get_dy(int128(0), int128(i), getDecimal(0));
        _ratio = abs(int256(_ratio - lastRatio[i]));
        if (_ratio.mul(PERCENTAGE_DECIMAL_FACTOR).div(CURVE_RATIO_DECIMALS_FACTOR) > BASIS_POINTS) {
            return false;
        }
    }
    // b/c 추가
    uint256 bc_ratio = curvePool.get_dy(int128(1), int128(2), getDecimal(1));
    uint256 bc_diff = abs(int256(bc_ratio - lastRatio_bc));   // lastRatio_bc 도 cache 필요
    if (bc_diff.mul(PERCENTAGE_DECIMAL_FACTOR).div(CURVE_RATIO_DECIMALS_FACTOR) > BASIS_POINTS) {
        return false;
    }
    return true;
}
```

#### 3. IntentChecker annotation 시도 (개발 시점 관점)

**함수 scope 변수**: parameter 없음. State: `lastRatio[1]`, `lastRatio[2]`, `BASIS_POINTS`.

**(a) 상태 변화?** `view` 함수 → state write 없음 → post-state 채널 봉쇄.

**(b) Return-based @Post**:
- `@Post returnExpression == false` when "b/c out of range"?
- "b/c out of range"를 표현하려면 `curvePool.get_dy(1, 2, ...)` 호출 결과 + `lastRatio_bc` (state에 없음) 필요.
- 두 값 모두 scope·state 부재. G3.
- `curvePool.get_dy()` 자체를 intent에 쓸 수도 없음 (G1, 함수 호출 불허).

**(c) Natural annotation (silent sanction)**:
- 개발자가 코드 로직 그대로 옮기면: `@Post returnExpression == !(any i=1,2 has _ratio[i] > BASIS_POINTS)`.
- Buggy에서 tautology, correct (b/c 포함)에서는 다른 조건 → 개발자 natural intent가 buggy 그대로. **I5 silent sanction 전형**.
- 추가: **NatSpec이 잘못된 transitivity 설명을 제공** → annotation 작성자를 추가로 오도 (natspec-driven silent sanction 이중).

**(d) Aux injection (I4)**:
- `uint256 bc_ratio = curvePool.get_dy(int128(1), int128(2), getDecimal(1));` 삽입 가능.
- 그러나 `lastRatio[b/c]` 같은 캐시가 **state에 없음**. `mapping(uint256 => uint256) lastRatio`는 index 1, 2만 저장 — b/c 비교용 state 자체가 data model에 부재.
- 이 부재는 contract state 확장 필요 (add `uint256 lastRatioBc` state var). Production code 대규모 수정 + 초기화 로직 + `_updateRatios` 수정 동시 필요.
- **Injection이 data model 확장까지 요구** → L5 transit도 어려움 (**Y_hard**).

#### 4. 분류 타당성 — **L4b 확정**

**기존 분류 검토**:
- `limitation_types.md` (L4b): view 함수라 state attach 불가.
- `annotation_plans.md` (L5a): missing-code.

**객관 판정**:
- L4b 기준: view 함수로 state modifier 없음 → state-based @Post 부착 대상 부재. 맞음.
- L5a 기준: post-condition 표현 가능해야 하는데, return-based 표현도 scope 부재로 불가. **L5a 조건 미충족**.
- → **L4b 확정**, annotation_plans.md의 L5a는 틀림.

**L4a vs L4b overlap 해소**:
- L4b (no-target-storage)와 L4a (inexpressible-expected-value) 둘 다 적용 가능한 case.
- 본 case는 **function type이 view → state 채널 부재** (L4b) + **return-based 표현도 scope 부재로 불가** (L4a).
- 기존 taxonomy convention: view 함수면 L4b 우선 (`limitation_types.md` L161 명시적). 유지.

#### 5. 근본 원인

**본질 (L4b — view 함수 + return 표현 불가)**:

`safetyCheck`는 state를 수정하지 않는 view. Intent annotation의 두 주요 채널:
- State-based `@Post changed(...)`: view라 대상 없음.
- Return-based `@Post returnExpression == ...`: correct expression에 scope 밖 값 (b/c ratio from Curve + lastRatio_bc from state-that-doesn't-exist) 필요.

두 채널 모두 막힘. **"annotation을 attach할 곳 자체가 없거나, attach해도 값을 못 씀"** — L4b 정의의 spiritual 의미.

**I8 축 재분류 (새 축)**:
- **Bug category**: **Algorithm error** — missing check (b/c ratio 검증 알고리즘 누락). 단일 값 오류 아닌 **검증 로직 구조 누락**.
- **Proxy type**: **Type B** — b/c ratio와 그 cached value 둘 다 scope·state 부재.
- **Annotation channel**: state 채널 닫힘 (view) + return 채널 봉쇄 (scope 부재).

G-표면:
- **G1** — `curvePool.get_dy(1, 2, ...)` intent 내 참조 불가.
- **G3** — `lastRatio_bc` 같은 state 자체가 data model 부재 (해당 cache 슬롯 설계 시 누락).
- **G4** — view 함수라 state write 채널 닫힘.

**Silent sanction 이중**: (a) developer natural annotation이 buggy 로직 그대로 → fail-by-confirmation, (b) **NatSpec이 "(a/b, a/c)만 체크하면 충분"** 이라는 잘못된 설명을 제공해 annotation 작성자를 오도. **Natspec-driven silent sanction** 이 I5의 강력한 예.

**Aux injection (I4) 어려움 (Y_hard)**: b/c 값 주입은 가능하나 lastRatio_bc state 추가 + 초기화 + _updateRatios 수정까지 동시 필요. 단순 local injection 수준 넘어 **data model 확장** 수준 → L5 transit도 대공사.

**Case 10·Case 5과의 비교**:
- Case 10: `**` grammar만 추가하면 injection 가능.
- Case 5: multi-step algorithmic injection 필요하나 data model 변경 없음.
- Case 11 (본): **data model 자체 확장 필요** — 가장 깊은 수준 fix.

**[Category (I8)]**: **Algorithm error / Type B** — missing verification logic + 관련 state data model 부재. View 함수라 state-based 우회도 불가. Cases 3·5와 함께 Algorithm/B cell.

#### 6. paper 문장 개선 제안

- **L4b 본문 (line 1315)**: 현재 "view 함수 → @Post attach 대상 부재" 중심. Case 11은 **view + return expression 둘 다 막힘 패턴**. L4b 정의에 "return-based expression도 inexpressible인 view 함수" 포함 명시.
- **Silent sanction + NatSpec**: 이미 Case 4에서 제기한 natspec-driven silent sanction 패턴이 Case 11에서도 재등장. NatSpec이 잘못된 설명을 포함하면 annotation 작성자를 오도. Discussion에서 **"NatSpec audit이 annotation workflow의 필수 전제"** 로 강조.
- **Data model 확장 요구 case**: Case 11의 I4 difficulty ("Y_hard")는 aux injection의 한계를 보이는 예 — 단순 변수 주입 넘어 storage 슬롯 추가 필요. Paper future work에서 "annotation-driven contract refactoring의 범위"를 논할 때 인용.

---

### Case 12 — `web3bugs_52_H_15` (현재 분류: **L4b**, 단 limitation_types.md 내 self-inconsistent)

#### 1. Audit report 인용

- **출처**: `reports/52.md` → `[H-15] VaderRouter._swap performs wrong swap`
- **Severity**: High. **Warden**: cmichel (C4 2021-11-vader).
- **핵심 주장 (원문 발췌)**:
  > The 3-path hop in `VaderRouter._swap` is supposed to first swap **foreign** assets to native assets, and then the received native assets to different foreign assets again. `pool.swap(nativeAmountIn, foreignAmountIn)` accepts the foreign amount as the **second** argument. The code however mixes these positional arguments up:
  > ```solidity
  > return pool1.swap(0, pool0.swap(amountIn, 0, address(pool1)), to);   // BUG
  > // should be:
  > return pool1.swap(pool0.swap(0, amountIn, address(pool1)), 0, to);
  > ```
- **Impact**: "All 3-path swaps through the VaderRouter fail in the pool check when `require(nativeAmountIn = amountIn <= nativeBalance - nativeReserve = 0)` is checked."
- **권고 fix**: `pool1.swap(pool0.swap(0, amountIn, address(pool1)), 0, to);` 인자 순서 swap.
- **Sponsor**: SamSteinGG confirmed.

#### 2. 코드 의미 이해

##### (2a) Contract 목적 & 시스템 위치

`VaderRouter` — Vader Protocol의 DEX 라우터. Uniswap V2 API와 호환되게 설계된 router로, Vader pool들(native ↔ foreign asset 교환)에 대한 swap/liquidity 관리 래퍼. `factory`, `reserve` 주소만 state로 보유, 자체 회계 state 없음 (순수 router).

##### (2b) 함수의 컨트랙트 내 역할

`_swap(amountIn, path, to) → amountOut` (L302-351, private):
- Caller: `swapExactTokensForTokens`, `swapTokensForExactTokens` (public entry).
- 역할: path 길이 2 (single-hop) or 3 (multi-hop)에 따라 pool.swap을 호출.
- 3-path의 경우 **foreign A → native → foreign B** — pool0에서 foreign→native, 받은 native로 pool1에서 native→foreign.
- VaderRouter 자체의 state write 없음 — 모든 자산 이동은 pool 및 ERC20 external call로 위임.

##### (2c) 함수 의도 (수식)

3-path swap logic:
- pool0: `foreign A` in → `native` out. `pool0.swap(nativeAmountIn=0, foreignAmountIn=amountIn, to=pool1)` → returns nativeAmountOut.
- pool1: `native` in → `foreign B` out. `pool1.swap(nativeAmountIn=nativeAmountOut, foreignAmountIn=0, to=recipient)` → returns foreignAmountOut.
- 핵심 convention: `pool.swap(nativeAmountIn, foreignAmountIn, to)` — **첫째 인자 native, 둘째 인자 foreign**.

##### (2d) Line-by-line 분석 (L302-351, 3-path 분기)

```solidity
309      if (path.length == 3) {
310-315      require(
                 path[0] != path[1] &&
                     path[1] == factory.nativeAsset() &&
                     path[2] != path[1],
                 "VaderRouter::_swap: Incorrect Path"
             );
317          IVaderPool pool0 = factory.getPool(path[0], path[1]);   // foreign A ↔ native
318          IVaderPool pool1 = factory.getPool(path[1], path[2]);   // native ↔ foreign B
320-324      IERC20(path[0]).safeTransferFrom(msg.sender, address(pool0), amountIn);
326          return pool1.swap(0, pool0.swap(amountIn, 0, address(pool1)), to);   // BUG
```

- **L317-318**: 두 pool 획득. pool0 = (foreign A, native), pool1 = (native, foreign B).
- **L320-324**: sender → pool0으로 foreign A amountIn 전송 (swap을 위한 사전 입금).
- **L326 (BUG)**:
  - **내측 `pool0.swap(amountIn, 0, address(pool1))`**: arg[0] = amountIn (native 자리), arg[1] = 0 (foreign 자리). 즉 **native→foreign swap** 시도 — 반대 방향.
  - pool0은 foreign A만 입금받았으므로 native reserve 증가 없음. `require(nativeAmountIn = amountIn <= nativeBalance - nativeReserve = 0)` 체크에서 revert.
  - **올바른**: `pool0.swap(0, amountIn, address(pool1))` — foreign A를 native로 swap.
  - 외측 `pool1.swap(0, ..., to)`: arg[0] = 0, arg[1] = 중첩 호출 결과 (만약 안 revert됐으면 native값인데 foreign 자리). 역시 방향 오류.
  - **올바른**: `pool1.swap(pool0_native_out, 0, to)` — pool0에서 받은 native를 pool1에서 foreign B로 swap.

**실행 결과**: 모든 3-path swap이 **pool0에서 revert**. 해당 기능 완전히 사용 불가.

##### (2e) 버그의 근본 의미

**Uniswap V2 API convention과 Vader pool API convention 혼동**. Uniswap V2의 `swap(amount0Out, amount1Out, to, data)`는 **output** amount를 인자로 받음. Vader `pool.swap(nativeAmountIn, foreignAmountIn, to)`는 **input** amount를 받으며, 각 자산별로 별도 위치.

개발자가 Uniswap V2 스타일로 생각하면서 "input 방향을 0으로 설정" 착각했을 가능성 (실제로는 pool.swap이 input을 받는데 output처럼 처리).

Protocol-level: 3-path swap 기능 완전 불능 → DEX의 cross-pool swap 경로 봉쇄. 직접적 자금 손실은 revert로 방지되나 **기능 마비 + UX 파손**. (실제 severity는 "functional loss"로 High로 처리됨.)

##### (2f) 올바른 fix

Audit 권고 그대로 L326 한 줄 swap:
```solidity
return pool1.swap(pool0.swap(0, amountIn, address(pool1)), 0, to);
```

#### 3. IntentChecker annotation 시도 (개발 시점 관점)

**함수 scope 변수**: `amountIn`, `path` (params), `pool0`, `pool1` (local). `to` (param). State: `factory` (immutable), `reserve`.

**(a) 상태 변화?** VaderRouter._swap는 state write 없음 (전부 external call). `_swap`의 직접적 state 채널 **봉쇄**.

**(b) Return-based @Post**:
- `@Post returnExpression == correct_amountOut_formula`: amountOut은 pool의 swap formula (constant product 기반) 결과. 외부 pool의 state(reserves)에 의존. 표현 불가.

**(c) `.arg[n]` 채널 (lint-level, I9 원칙상 배제)**:
- `@During pool0.swap.arg[0] == 0` — arg[0]이 nativeAmountIn이어야 함을 assert. Buggy: `amountIn ≠ 0` → VIOLATED. Correct: `0 == 0` → SATISFIED.
- `.arg[1] == amountIn` 도 추가 가능.
- 기존 `limitation_types.md`가 L5b 예시로 든 annotation.
- **I9 원칙**: 이건 lint-style. L5b 판정 근거로 사용 안 함.

**(d) Semantic intent via require feasibility**:
- Grammar의 `require feasible` / `assert feasible` 절 활용.
- `@During pool0.swap의 내부 require` — 그러나 pool0은 external contract. 내부 require에 접근 불가.
- Only VaderRouter._swap 내부 require (L310-315)만 annotate 가능하나 이건 path 형식 체크지 swap 방향 체크 아님.

**(e) Revert detection**:
- Buggy는 항상 revert → 이게 bug sign. Correct는 return.
- `@Post returnExpression` 자체가 (buggy에서) 도달 불가능한 state. 엔진이 "이 path는 infeasible"로 표현할 수 있음.
- 그러나 이건 IntentChecker의 intent annotation 기능이 아닌 분석 엔진의 부수 효과. **Intent annotation 관점에서 명시적 표현 수단 없음**.

**(f) Aux injection (I4)**:
- 새 state 추가나 외부 값 injection은 이 case에 별 의미 없음 — 버그가 arg 순서지 값 자체가 아님.
- N/A.

#### 4. 분류 타당성 — **L4b 확정** (Case 8·Case 4와 구분)

**기존 분류 검토 (limitation_types.md 내 self-inconsistency)**:
- L4b list (L33): 52_H_15 포함.
- L5b examples section (L229-237): 52_H_15을 대표 L5b 예시로 제시.
- → 문서 내 모순.

**객관 판정**:
- VaderRouter._swap은 **router/wrapper 함수, state write 없음**.
- Semantic intent (correct amountOut) 표현 불가 (external pool state 의존).
- `.arg[n]` 채널은 I9에 의해 L5b 판정에서 배제.
- → **L4b** (no-target-storage: router/wrapper 분류).

**Case 8·Case 4와의 비교**:
| | Case 4 (39_H_02) | Case 8 (61_H_01) | Case 12 (본 case) |
|---|---|---|---|
| Function type | non-view (state write 있음) | internal view | private wrapper (state write 없음) |
| Bug 형태 | arg[2] 값 오류 (cross-line fee flow) | arg order swap (oracle) | arg order swap (pool) |
| 실제 `.arg[n]` 표현 가능? | 예 (proxy) | 예 (intent 자체) | 예 (arg 순서) |
| I9 하에서 L5b 인정? | 아니오 (proxy) | 아니오 (lint) | 아니오 (lint) |
| Semantic 채널 가능? | 아니오 (외부 ERC20 balance) | 아니오 (@IReturn arg-indifference) | 아니오 (외부 pool state) |
| 분류 | L4a (cross-line intent) | L4a (inexpressible) | **L4b (wrapper, no state)** |

세 case 모두 "arg 관련 버그지만 semantic intent 표현 불가"의 공통 패턴. 분류가 L4a/L4b로 갈리는 기준은 **함수 타입** (state write 여부).

#### 5. 근본 원인

**본질 (L4b — router/wrapper 함수 + arg 방향 오류)**:

VaderRouter._swap는 순수 router — 자체 state 없음. Correct intent는 **외부 pool의 state 변화 방향**에 대한 것: pool0의 foreign reserve 증가·native reserve 감소, pool1의 native reserve 증가·foreign reserve 감소. 이 방향성은 외부 pool contract의 state → VaderRouter scope 밖.

Intent annotation의 두 채널:
- State-based @Post: VaderRouter 자체 state 없음. 채널 봉쇄.
- Return-based @Post: amountOut의 correct 값 계산에 외부 pool의 reserves + swap formula 필요. 표현 불가.
- Arg-based @During: `.arg[n]`으로 인자 순서 제약 가능. 그러나 I9 원칙상 lint-level이라 L5b 판정 배제.

**I8 축 재분류 (새 축)**:
- **Bug category**: **Value error** — 인자 identifier 선택 오류 (order swap). 한 줄 fix.
- **Proxy type**: **Type B** — correct amountOut이나 pool state 변화가 scope 부재.
- **Annotation channel**: state 채널 봉쇄 (router 특성) + return 채널 봉쇄 (외부 state 의존) + arg 채널 (lint).

G-표면:
- **G1** — `pool0.swap(...)`, `pool1.swap(...)` 반환값 intent 내 참조 불가.
- **G3** — correct amountOut이나 pool reserves가 VaderRouter scope 부재.
- **G4** — router/wrapper라 state write 채널 닫힘.
- **G8** — external pool state 의존.

**Silent sanction (I5)**: Code 그대로 annotation으로 옮기면 (`arg[0] == amountIn, arg[1] == 0`) buggy tautology → fail-by-confirmation. `.arg[n]` 형식으로도, 일반 natural intent로도 둘 다 silent sanction 위험.

**Aux injection (I4) N/A**: 값 문제가 아닌 인자 순서 문제라 injection으로 해소되는 성격이 아님.

**[Category (I8)]**: **Value error / Type B** — router/wrapper 함수에서 인자 순서 오류. Case 8과 같은 cell (value/B)이나 **함수 타입 차이로 L4b**. Cross-cutting pattern: "arg-level value error with semantic intent 외부 state 의존".

#### 6. paper 문장 개선 제안

- **L4b list 정정**: `limitation_types.md` 내 52_H_15이 L4b list와 L5b examples 모두에 등장하는 self-inconsistency 해결 — **L4b로 통일**하고 L5b examples section에서 52_H_15 제거 (혹은 "originally listed as L5b, reclassified to L4b under I9 principle"로 명시).
- **L4a vs L4b 기준 명시**: Case 4·8·12 비교표를 paper에 포함. "semantic intent 표현 불가 공통, 구분은 함수 타입 (state write 여부)".
- **Router/wrapper L4b의 전형**: 자체 state 없는 함수는 모든 semantic intent가 외부 state에 의존 → L4b가 기본값. Vader 관련 여러 case(52_H_15, 52_H_16, 70_H_08)가 이 cell.

---

## L4c — Magnitude-only Difference (1 case)

L4c 정의: State variable이 buggy/correct 모두에서 동일 방향으로 변경되며, 차이는 변경 크기(magnitude)뿐. `changed()` / `Entry op Exit` annotation은 buggy/correct 모두에서 동일하게 satisfied. PostEntryExit에서 산술 표현(`Entry - Exit == expected_magnitude`) 미지원이 primary blocker.

---

### Case 13 — `web3bugs_35_H_10` (현재 분류: **L4c**, 유일 case)

#### 1. Audit report 인용

- **출처**: `reports/35.md` → `[H-10] ConcentratedLiquidityPool.burn() Wrong implementation`
- **Severity**: High. **Warden**: WatchPug (C4 2021-09-sushitrident-2).
- **핵심 주장 (원문 발췌)**:
  > The reserves should be updated once LP tokens are burned to match the actual total bento shares hold by the pool. However, the current implementation only updated reserves with the fees subtracted. Makes the `reserve0` and `reserve1` smaller than the current `balance0` and `balance1`.
- **Impact**: "many essential features of the contract will malfunction, includes `swap()` and `mint()`" (reserve > balance 조건으로 후속 require 실패).
- **권고 fix**:
  ```solidity
  // L263-266 변경
  unchecked {
      reserve0 -= uint128(amount0);   // was amount0fees
      reserve1 -= uint128(amount1);   // was amount1fees
  }
  ```
- **Sponsor**: sarangparikh22 confirmed.

#### 2. 코드 의미 이해

##### (2a) Contract 목적

`ConcentratedLiquidityPool` — Sushi Trident의 **Uniswap V3-style 집중 유동성 pool**. Tick 기반 범위 유동성 + fee accounting. `reserve0`/`reserve1`은 pool이 보유한 bento shares의 내부 추적값.

##### (2b) 함수의 역할

`burn(bytes data)` (L231–272, public):
- LP provider가 position을 burn하여 유동성 회수.
- 회수 금액 = **principal (liquidity 비례) + fee** 두 부분.
- Reserve 감소는 **두 부분 모두 반영**해야 balance와 동기화.

##### (2d) Line-by-line 핵심 (L245–266)

```solidity
245  (uint256 amount0, uint256 amount1) = _getAmountsForLiquidity(...);   // principal 부분
252  (uint256 amount0fees, uint256 amount1fees) = _updatePosition(...);    // fee 부분
254  unchecked {
255      amount0 += amount0fees;                                            // 총 회수 = principal + fees
256      amount1 += amount1fees;
257  }
...
263  unchecked {
264      reserve0 -= uint128(amount0fees);    // BUG: principal 부분 누락
265      reserve1 -= uint128(amount1fees);    // BUG
266  }
268  _transferBothTokens(recipient, amount0, amount1, unwrapBento);       // 실제 송금은 amount0 (total)
```

- L255–256: `amount0`가 **principal + fees 합**으로 업데이트.
- L268: **`amount0` 전체 송금**.
- L264 (BUG): `reserve0`는 **`amount0fees`만큼만** 감소.
- 결과: `balance0`는 `amount0` 만큼 줄었는데 `reserve0`는 `amount0fees`만 줄어 → **reserve0 > balance0** 상태 지속.
- 후속 `mint()`의 `require(reserve0 <= balance0)` 체크에서 transaction revert → pool 기능 마비.

##### (2e) 버그 근본 의미

Reserve tracking의 내부 invariant (`reserve ≤ balance`) 유지가 목표. `burn`이 tokens를 sender에게 transfer 했으면 reserve도 같은 양으로 감소해야 함. Fee-only 차감은 **principal 이동을 무시**하는 accounting 오류.

#### 3. IntentChecker annotation 시도

**함수 scope**: `amount0`, `amount1`, `amount0fees`, `amount1fees` — **모두 local variable로 존재**.

**(a) `@Post reserve0 (entry relOp exit)` 채널**:
- `entry > exit` (감소 방향): buggy·correct 모두 satisfied — 둘 다 reserve0 감소.
- `entry == exit`: 둘 다 violated.
- 방향성만으로는 **구분 불가**. Grammar의 entry/exit 비교는 **qualitative (relOp: =, ≠, <, >)만 허용**, **magnitude 비교 불가**.

**(b) `@Post changed(reserve0, true)` 채널**:
- Buggy·correct 모두 satisfied — 둘 다 변경.

**(c) Magnitude 표현 시도**:
- `@Post reserve0_entry - reserve0_exit == amount0` 형태 필요.
- `reserve0_entry`를 arithExpr 안에 쓸 문법 없음. `reserve0 (entry relOp exit)`는 특수 form.
- `commonClause`의 `intentValue relOp intentValue`에서 `reserve0`는 exit 값만 참조.
- Entry 값 참조할 경로 없음 → **표현 불가**.

**(d) Aux injection (I4)**:
- 함수 상단에 `uint128 reserve0_before = reserve0;` 삽입.
- Annotation: `@Post reserve0_before == reserve0 + amount0` — grammar OK.
- Buggy: `reserve0_before == reserve0 + amount0fees ≠ reserve0 + amount0` → VIOLATED.
- Correct: `reserve0_before == reserve0 + amount0` → SATISFIED.
- **Injection 하면 detectable**. 단 snapshot 주입 결정 자체가 "reserve 차감량이 amount0이어야 한다"는 버그 인지 → L5 transit.

#### 4. 분류 타당성 — **L4c 확정**

**L4c 본질**: Grammar의 postClause `intentValue (entry relOp exit)`가 **qualitative 비교만 허용** (direction/equality). Magnitude (exact 차이)를 표현할 문법 수단 없음. Case 13의 buggy/correct가 같은 방향·같은 state var 변경, magnitude만 다른 전형.

`limitation_types.md` L4c 설명 정확. **유일 L4c case라 일반화 판단 아직 불가**.

#### 5. 근본 원인

**본질 (L4c — postClause 문법의 qualitative 제약)**:

PostEntryExit 형식 `intentValue (entry relOp exit)`이 arithmetic을 포함하지 않음. 즉 "reserve0가 amount0만큼 감소했다" (`before - after == amount0`) 표현 불가. **Grammar-level 한계**.

**I8 새 축 재분류**:
- **Bug category**: **Value error** — 잘못된 identifier 선택 (`amount0fees` 대신 `amount0`이어야). 한 줄 fix.
- **Proxy type**: **Type A** — 올바른 identifier `amount0`이 **scope에 존재함**.
- 즉 Case 13은 **Value / Type A**. Case 1(A_candidate)에 이어 **두 번째 Type A 확정 사례**.

**Case 8 (61_H_01)과의 유사성**: 둘 다 identifier 선택 오류 (wrong identifier in scope).
- Case 8: `.arg[n]` 채널 가능, semantic 채널 막힘 (@IReturn arg-indifference) → **L4a**.
- Case 13: `.arg[n]` 채널 없음 (state 차감은 `x -= y` 형식이지 call 아님), `changed`/`entry-exit` 채널은 qualitative만 → **L4c**.
- 둘 다 I9 원칙상 lint-level L5b 배제 → L4로 고정.

**중요 관찰 — L4c의 성격**:
- L4c는 **scope는 Type A (proxy 존재)인데 grammar postClause가 magnitude 표현 못해서 L4로 떨어지는 cell**.
- L4a (Type B: proxy 부재) 와 **성격이 완전히 다름**.
- 새 I8 axis matrix에서 L4c는 **Value / Type A / grammar-limit** 으로 단일 cell 차지. L4a의 Value/B cell과 구분.

**Aux injection (I4) 경로**: 단순 snapshot local `reserve0_before` 주입. 가장 쉬운 I4 injection (state 단일 복사). Y (easy).

**[Category (I8)]**: **Value error / Type A (grammar-limit)** — L4c의 유일 case. PostClause 문법의 qualitative 제약이 primary blocker. Proxy (`amount0`)는 scope 안에 있으나 grammar가 state transition magnitude를 표현 못 함.

#### 6. paper 문장 개선 제안

- **L4c 본문 (line 1319)** 유지 가능. 단 **L4c의 본질이 "grammar-level 제약"이지 scope 부재 아님**을 명시. Aux injection 경유 L5 transit 가능성 언급.
- **Grammar 확장 후보**: `intentValue (entry - exit == expr)` 같은 arithmetic 허용 시 L4c가 해소됨 (snapshot injection 없이도). **간단한 grammar 확장으로 해소 가능한 유일한 L4 category**라는 paper insight.
- **I8 matrix 배치**: 34 case 완주 후 matrix에서 L4c는 **Value/A / grammar-limit** 셀로 분리. L4a(Value/B)와 구조 다름을 강조.

---

## L4d — Invariant Masked (1 case)

L4d 정의: 동일 함수 내 다른 코드가 이미 target 변수를 변경하여 `changed()`/PostEntryExit가 buggy/correct 모두에서 satisfied. Product invariant 등 **multi-variable arithmetic 관계**가 필요하나 PostEntryExit에서 산술 표현 미지원.

---

### Case 14 — `web3bugs_36_H_02` (현재 분류: **L4d**, 유일 case)

#### 1. Audit report 인용

- **출처**: `reports/36.md` → `[H-02] Basket.sol#auctionBurn() A failed auction will freeze part of the funds`
- **Severity**: High (judge confirmed). **Warden**: WatchPug (C4 2021-09-defiprotocol).
- **핵심 주장 (원문 발췌)**:
  > Given the `auctionBurn()` function will `_burn()` the auction bond without updating the `ibRatio`. Once the bond of a failed auction is burned, the proportional underlying tokens won't be able to be withdrawn, in other words, being frozen in the contract.
- **POC**: ibRatio=1e18, totalSupply=400, burn 1 token → buggy ibRatio remains 1e18, totalSupply=399. 사용자가 1 token burn 시 1 BTC + 1 ETH 회수 가능하나 원래 자산 대비 **1 BTC + 1 ETH 영구 락**.
- **권고 fix**:
  ```solidity
  function auctionBurn(uint256 amount) onlyAuction external override {
      handleFees();
      uint256 startSupply = totalSupply();
      _burn(msg.sender, amount);
      uint256 newIbRatio = ibRatio * startSupply / (startSupply - amount);
      ibRatio = newIbRatio;
      emit NewIBRatio(newIbRatio);
      emit Burned(msg.sender, amount);
  }
  ```
- **Judge**: "funds can be irrevocably lost, this is a high severity finding".

#### 2. 코드 의미 이해

##### (2a) Contract 목적

`Basket` — DefiProtocol의 **index basket token** (ETF-style). 사용자가 basket 토큰을 mint/burn하면 underlying tokens(BTC, ETH 등)를 proportional하게 입출금. `ibRatio`는 basket token ↔ underlying 비율을 유지하는 **accounting multiplier**. Invariant: `ibRatio × totalSupply`가 pool의 underlying total value에 비례.

##### (2b) 함수의 역할

`auctionBurn(amount) onlyAuction external` (L102–108):
- Auction 컨트랙트가 **실패한 auction bond**를 burn 처리할 때 호출.
- `_burn`으로 totalSupply 감소.
- 남은 사용자들이 동일한 underlying 비례 회수를 받으려면 **ibRatio가 totalSupply 감소에 반비례하여 증가**해야 함 (invariant 유지).
- Audit fix: `newIbRatio = ibRatio * startSupply / (startSupply - amount)` — 정확한 invariant 유지 공식.

##### (2d) Line-by-line (L102–108)

```solidity
102  function auctionBurn(uint256 amount) onlyAuction external override {
103      handleFees();         // (A) 특정 분기에서 ibRatio 업데이트
105      _burn(msg.sender, amount);   // totalSupply 감소
107      emit Burned(msg.sender, amount);
108  }
```

- **L103 (`handleFees`)**: `lastFee != 0 && time passed`일 때만 ibRatio 업데이트 (`ibRatio = ibRatio * startSupply / totalSupply()`). Fee 징수 목적. `lastFee == 0`이면 no-op (setter만).
- **L105 (`_burn`)**: totalSupply 감소.
- **BUG 누락**: totalSupply 감소 후 **invariant 유지용 ibRatio 업데이트** 없음.

##### (2e) 버그 근본 의미

**Multi-variable product invariant violation**. `auctionBurn` 전: `ibRatio_entry × totalSupply_entry = K`. `auctionBurn` 후 (fix 하에): `ibRatio_exit × totalSupply_exit = K` 유지. Buggy에서 totalSupply만 감소하고 ibRatio 불변 → 곱 감소 → underlying token 중 비례분이 "회수 불가" (freeze).

POC의 경우: 1 BTC + 1 ETH가 영구 락. 자금의 proportional freeze는 High severity.

#### 3. IntentChecker annotation 시도

**함수 scope**:
- Param: `amount`.
- State: `ibRatio`, `totalSupply` (ERC20 inherited), `lastFee`, etc.

**(a) `@Post changed(ibRatio, true)` 채널** — L4d의 핵심 이슈:
- `handleFees`가 **특정 분기에서 이미 ibRatio 업데이트**. 따라서:
  - Scenario-A (`lastFee != 0` + time passed): handleFees가 ibRatio 변경 → buggy·correct 모두 `changed` satisfied. **구분 불가**.
  - Scenario-B (`lastFee == 0`): handleFees가 ibRatio 변경 안 함 → buggy unchanged, correct changed. 구분 가능.
- 즉 **debug annotation 시나리오 따라 detectability 갈림** (I6 general vs specific 경계).

**(b) `@Post ibRatio (entry == exit)` (불변성 주장)**:
- Buggy Scenario-A: ibRatio가 handleFees로 이미 바뀜 → VIOLATED.
- Buggy Scenario-B: ibRatio 불변 → SATISFIED.
- Correct: 항상 변경 (manual update) → VIOLATED.
- Scenario-B에서 역방향 구분. Scenario-A에선 둘 다 VIOLATED → 구분 불가.

**(c) Product invariant (진짜 intent)**:
- Correct: `@Post ibRatio * totalSupply (entry == exit)` — **곱 보존**.
- Grammar의 `intentValue (entry relOp exit)`는 **qualitative only**. 산술 표현 (곱) 허용 안 함.
- `commonClause`의 `intentValue relOp intentValue`로 `ibRatio * totalSupply == <entry value>` 시도: entry value 표현 경로 없음 (Case 13과 동일).
- **표현 불가** (L4d primary 본질).

**(d) Aux injection (I4)**:
- `uint256 K_before = ibRatio * totalSupply();` 주입 → product invariant 체크 가능. 단 `totalSupply()` 함수 호출 문제 (ERC20 inherited `_totalSupply` state 접근 가능하면 해결 — Issue 8 영역).
- **Y_medium** 수준.

#### 4. 분류 타당성 — **L4d 확정**

`limitation_types.md` L4d 설명 정확. Handle Fees가 이미 ibRatio를 변경할 수 있어 `changed` 마스킹, 진짜 invariant (곱 보존)는 PostEntryExit 산술 부재로 표현 불가.

#### 5. 근본 원인

**본질 (L4d — multi-variable arithmetic invariant 표현 불가)**:

Correct intent = `ibRatio × totalSupply == ibRatio_entry × totalSupply_entry` (product preservation). PostClause grammar에 이 형식 없음.

**Case 13 (L4c)과 비교**:
- L4c: single var magnitude (`reserve0 entry - exit == amount0`).
- L4d: multi-var product (`ibRatio × totalSupply` invariant).
- 둘 다 **PostEntryExit grammar 산술 표현력 한계**로 귀결.

즉 **L4c와 L4d는 사실상 동일 grammar-limit의 서로 다른 발현**:
- L4c: `diff == const`.
- L4d: `product == const`.
- 본질적 blocker 동일 (arithmetic PostEntryExit 부재).

**I8 새 축 재분류**:
- **Bug category**: **Algorithm error** — invariant 유지 로직(= missing state update) 누락. Fix는 여러 줄 (startSupply + newIbRatio 계산 + ibRatio 업데이트 + emit).
- **Proxy type**: **Type A** — 모든 관련 변수(`ibRatio`, `totalSupply`, `amount`)가 scope·state에 존재.
- **Algorithm / Type A (grammar-limit)** — Case 13 (Value/A)과 **같은 "Type A / grammar-limit" 축**, bug category 다름.

G-표면:
- **G6 (L4d 전용)** — multi-variable PostEntryExit 산술 표현 불가.
- **Type A 측면**: G1/G3 없음 (변수 모두 scope에 있음).

**Silent sanction (I5)**:
- `@Post changed(ibRatio, true)` Scenario-A에서 buggy satisfied → silent sanction.
- Scenario-B에서만 구분 → 운 좋은 시나리오 (I6 specific form).

**Case 13 + 14 공통 — "L4c/L4d merger 제안"**:
둘 다 PostEntryExit grammar-limit이 primary. Bug category만 다름:
- L4c (Case 13): Value / Type A / magnitude-grammar-limit.
- L4d (Case 14): Algorithm / Type A / product-grammar-limit.
- 새 axis matrix에서 이 두 case는 **동일 grammar-limit cell의 두 sub-pattern**. Paper에서 L4c와 L4d를 **"PostEntryExit arithmetic gap"**으로 merger 제안.

**[Category (I8)]**: **Algorithm error / Type A (grammar-limit)** — multi-variable invariant preservation. L4c와 구조 공유.

#### 6. paper 문장 개선 제안

- **L4c + L4d merger**: 새 axis 기준 두 case가 **같은 grammar-limit cell**. Paper에서 "PostEntryExit arithmetic absence" 단일 항목으로 통합 서술 검토.
- **Grammar 확장 후보**: Case 13·14 둘 다 `intentValue (entry arithOp exit)` 허용으로 해소. 구체적 제안: `reserve0 (entry - exit == amount0)` (L4c), `ibRatio * totalSupply (entry == exit)` (L4d).
- **Invariant DSL future direction**: Multi-variable protocol invariant는 DeFi cornerstone이나 현재 grammar 미지원. Paper future work에서 **invariant annotation DSL** 제안 근거.

---

## L4b 배치 (Cases 15–20) — 6 cases compact batch

**배치 방식**: Case별 핵심 정보 + 새 4축 태깅. 공통 패턴은 L4b subsection summary에 통합. 파일 부피 제어.

---

### Case 15 — `web3bugs_52_H_16` (L4b, Case 12 쌍둥이)

- **Audit**: `[H-16] VaderRouter.calculateOutGivenIn calculates wrong swap` (cmichel, confirmed).
- **버그** (L488–495): 3-path swap에서 pool 순서 뒤바뀜. Inner `calculateSwap`이 `pool1` reserves, outer가 `pool0` reserves를 사용 — 올바른 순서는 **inner=pool0 (foreign→native), outer=pool1 (native→foreign)**.
- **Fix**: reserve 인자를 pool0/pool1 위치 swap.
- **함수 타입**: `calculateOutGivenIn` external view — no state write.
- **Annotation 시도**: (a) `@Post returnExpression == correct_amountOut` 필요 — VaderMath.calculateSwap chain + pool0·pool1 reserves의 결합. Grammar에서 함수 호출 불허 → 표현 불가. (b) `.arg[n]` 순서 체크 가능하나 **I9에 의해 lint-level, L5b 배제**.
- **분류**: annotation_plans.md = L5b → I9 원칙 적용 후 **L4b** (view + external reserves/formula 의존).
- **[Category (I8)]**: **Value error / Type B** — Case 12 (52_H_15)의 view version 쌍둥이. Pool routing semantic이 VaderRouter scope 밖.

---

### Case 16 — `web3bugs_58_H_04` (L4b)

- **Audit**: `[H-04] AaveVault stale tvl` (Aave의 rebasing aToken). annotation_plans.md L5a.
- **버그** (L47, _push/_pull 관련): `tvl()`이 cached `_tvls` 반환. `_push()`에서 `updateTvls()`가 **deposit 이후** 호출 → LPIssuer가 **old tvl 기준으로 shares 계산** → Aave 이자가 반영되기 전 과다 shares 발행.
- **Fix**: `_push()` 시작에 `updateTvls()` 추가 (operation ordering 교정).
- **함수 타입**: `tvl` view, `_push`/`_pull` state-modifying wrapper.
- **Annotation 시도**:
  - `@Post` on `_tvls` 변화: buggy·correct 모두 satisfied (둘 다 updateTvls는 부름).
  - "deposit 전에 tvl 갱신" ordering invariant: grammar 지원 없음.
  - `@During bal_before == bal_after_before_deposit` 같은 snapshot — aux injection 필요.
- **분류**: L4b (view tvl; _push wrapper → state attach 있지만 ordering 문제라 구분 불가).
- **[Category (I8)]**: **Algorithm error / Type B** — ordering 문제가 단일 annotation 범위 넘음. Case 11 (17_H_02)와 유사 (view + missing check/call).

---

### Case 17 — `web3bugs_62_H_01` (L4b)

- **Audit**: `[H-01] Stream.recoverTokens leaks flashloan fee`. Sponsor (brockelmore) confirmed.
- **버그** (L654): `excess = balanceOf(this) - (depositTokenAmount - redeemedDepositTokens)` — `depositTokenFlashloanFeeAmount` 누락.
- **Fix**: `excess = balanceOf(this) - (depositTokenAmount - redeemedDepositTokens) - depositTokenFlashloanFeeAmount` (한 term 추가).
- **함수 타입**: external, safeTransfer만 — Stream contract 자체 state write 없음 (wrapper에 가까움).
- **Annotation 시도**:
  - Correct formula의 피연산자 `depositTokenFlashloanFeeAmount`는 **state var in scope**.
  - `balanceOf(this)`는 external interface view — call site 존재하나 **local 미저장** (inline chain).
  - `@During excess (assign == balanceOf_result - (...) - depositTokenFlashloanFeeAmount)` — `balanceOf_result`가 local 없음.
  - Aux injection: `uint256 bal = balanceOf(...);` 삽입 후 annotation 가능.
- **annotation_plans.md L5a** → I9 원칙 + wrapper 성격으로 **L4b** 재분류 제안 (no state write + balanceOf inline chain).
- **[Category (I8)]**: **Algorithm error / Type B** — missing formula term + balanceOf 결과 local 미저장. Case 9 (61_H_02)와 유사 (wrapper return handling).

---

### Case 18 — `web3bugs_70_H_08` (L4b)

- **Audit**: `[H-08] USDV/VADER rate conversion missing 1e18 scaling`. Judge resolved.
- **버그** (L98, L102):
  - Line 98: `amount = amount / usdvPrice` — usdvPrice 1e18 스케일, 결과 1e18배 과소.
  - Line 102: `amount = amount * vaderPrice` — 1e18배 과대.
  - Correct: `amount * 1e18 / usdvPrice`, `amount * vaderPrice / 1e18`.
- **함수 타입**: external, vader.safeTransfer 후 emit. VaderReserve state 불변 (transfer만). Wrapper.
- **Annotation 시도**:
  - `usdvPrice`, `vaderPrice` — interface view call 반환, **local로 저장됨** (L96, L100).
  - Correct annotation: `@During amount (assign == original_amount * 1e18 / usdvPrice)` in branch 1.
  - 문제: `amount`가 **parameter 자체 overwrite** → original 값 소실.
  - Aux injection: `uint256 original = amount;` 상단에 삽입 필요.
- **annotation_plans.md L5a** → wrapper + parameter overwrite로 **L4b** 재분류 제안.
- **[Category (I8)]**: **Value error / Type B** — scaling factor missing, parameter overwrite로 original 값 scope 부재. Case 1·2·10 "scaling trio"의 wrapper 버전.

---

### Case 19 — `web3bugs_83_H_02` (L4b)

- **Audit**: `[H-02] MasterChef deposit fee permanently locked`. 
- **버그** (L170–172, deposit 내 분기): `depositFee` 계산되어 user.amount에서 차감되나 **feeRecipient.amount 증가 코드 없음** → fee만큼 tokens 영구 lock.
- **Fix**: feeRecipient 대응 state update 추가.
- **함수 타입**: external, user state 변경 있음 (user.amount, user.rewardDebt).
- **Annotation 시도**:
  - User 측 state (user.amount)는 buggy/correct 모두 `_amount - depositFee`로 정확 → `changed(user.amount, true)` 양쪽 다 satisfied.
  - Fee recipient 측 state가 **코드에 아예 없음** — data model에 fee recipient account 슬롯 없음.
  - Case 11 (Buoy3Pool.safetyCheck)의 "missing state variable" 패턴.
- **annotation_plans.md L4b 기존** — 변경 없음. "target storage variable"의 "target"이 fee recipient이고 그게 scope에 없음.
- **[Category (I8)]**: **Algorithm error / Type B** — missing state update + target state variable 자체 부재. Case 11과 유사 (data model 부재).

---

### Case 20 — `web3bugs_110_H_01` (L4b, 쌍둥이 패턴 반복)

- **Audit**: `[H-01] StakedCitadel.balance missing strategy portion`. Sponsor confirmed.
- **버그** (L293–294): `balance()`가 `token.balanceOf(address(this))`만 반환, `IStrategy(strategy).balanceOf()` 누락. 주석에 "vault + strategy balance"라 명시됨에도 구현은 vault만.
- **Fix**: `return token.balanceOf(address(this)) + IStrategy(strategy).balanceOf();`
- **함수 타입**: public view.
- **Annotation 시도**:
  - Correct return에 `IStrategy(strategy).balanceOf()` 호출 필요.
  - `strategy`는 state var (in scope), 그러나 `.balanceOf()` 호출 자체가 **코드에 없음** → `@IReturn` 부착점 부재 (Case 2 25_H_05와 동일 구조).
  - `@Post returnExpression == token.balanceOf(this) + strategy.balanceOf()` — 두 호출 모두 intent에서 표현 불가 (G1).
- **분류**: annotation_plans.md L5a → I9 + view + function call absent로 **L4b** 재분류 제안.
- **[Category (I8)]**: **Algorithm error / Type B** — missing interface call + 호출 사이트 부재. Case 11·16과 동일 family (view + missing call).

---

### L4b Subsection Summary (Cases 11-12, 15-20 — 총 8 cases)

**공통 패턴**:
1. **함수 타입**: view (11, 15, 16 tvl, 20) / wrapper without state (12, 17, 18) / state-modifying but target-state-absent (19).
2. **Intent channel 봉쇄**:
   - State-based @Post 불가 (view) 또는 구분력 없음 (wrapper/missing-target).
   - Return-based @Post도 semantic expression 불가 (G1, G3).
3. **Proxy type**: 모두 **Type B**. L4b 정의 ("no-target-storage")가 사실상 Type B의 함수-type 기반 특수 케이스.
4. **Bug category**: Value 2건 (15, 18), Algorithm 6건 (11, 12, 16, 17, 19, 20). 다수 Algorithm — missing call/update/term 패턴 많음.
5. **Silent sanction 빈도**: 대부분 해당 — 코드 그대로 annotation 옮기면 buggy 그대로.
6. **Aux injection**: 가능한 경우 (17, 18) vs 불가능한 경우 (data model 확장 필요: 11, 19). **난이도 스펙트럼**.

**Twin 관찰**:
- (11, 16, 20): view function + missing call/update/check.
- (12, 15): VaderRouter _swap vs calculateOutGivenIn — 같은 contract 쌍둥이 (state-modifying vs view).
- (17, 18, 1, 2, 10): scaling/formula-term missing 계열.

**분류 재검토 결과**:
- annotation_plans.md가 많은 L4b case를 L5a/L5b로 잘못 라벨. I9 원칙 + function type 고려 시 **L4b가 옳음**.
- 재분류: 15 (L5b→L4b), 17 (L5a→L4b 제안), 18 (L5a→L4b 제안), 20 (L5a→L4b 제안).

**I8 matrix 분포 (L4b 8 cases)**:
- Algorithm/B: 6 (11, 12, 16, 17, 19, 20).
- Value/B: 2 (15, 18).
- Type A·A_candidate·non-B: 0.

→ **L4b는 Type B 전용 cell**임이 confirmed.

---

## L5a — Missing Code (7 cases, compact batch: Cases 21–27)

**L5a 정의**: 있어야 할 코드(state update, function call 등) 누락. 기존 state 변수로 post-condition 표현 가능 (Type A 기본). 버그 인지 전제.

**L5 전용 축 제안**: **Bug awareness source**:
- **(consistency)**: sibling function/branch와의 비교로 도출 가능 (pattern-level).
- **(domain)**: 프로토콜 도메인 지식 필요 (semantic-level).

---

### Case 21 — `web3bugs_35_H_12` (L5a)

- **Contract/Function**: ConcentratedLiquidityPool / mint (L176, L184 original).
- **버그**: `liquidity` 변경 후 `secondsPerLiquidity` 갱신 누락. `swap()`은 동일 변경에서 `secondsPerLiquidity += uint160((diff << 128) / liquidity)` 수행 — 일관성 놓침.
- **Annotation**: `@Post changed(secondsPerLiquidity, true)` — buggy 미변경, correct 변경 → 구분.
- **Bug awareness**: **consistency** (swap과의 sibling 비교로 도출 가능).
- **부가 blocker**: `abi.decode`로 파라미터 전달 (L3 unsupported-construct) — debug annotation 공급 제한.
- **[Category]**: **Value / Type A / consistency** (L5a).

---

### Case 22 — `web3bugs_52_H_23` (L5a)

- **Contract/Function**: VaderPoolV2 / mintSynth (L161).
- **버그**: `_update(foreignAsset, reserveNative + nativeDeposit, reserveForeign, ...)` — `reserveForeign`에서 `amountSynth` 차감 누락. 과다 synth 발행.
- **Annotation**: `@Post changed(reserveForeign, true)` — buggy 변경 없음 (arg = current value), correct 변경 → 구분. 또는 `@Post reserveForeign (entry > exit)`.
- **Bug awareness**: **domain** (synth 발행 시 foreign reserve 반영 회계 규칙 필요).
- **[Category]**: **Value / Type A / domain** (L5a).

---

### Case 23 — `web3bugs_62_H_03` (L5a, symptom in recoverTokens, root in claimReward)

- **Contract/Function**: Stream / claimReward (L575 transfer).
- **버그**: reward token 전송 시 `rewardTokenAmount -= rewardAmt` 누락. `recoverTokens`에서 stale 값 참조로 excess 계산 오류.
- **Annotation (root cause 지점)**: `@Post changed(rewardTokenAmount, true)` 혹은 `@Post rewardTokenAmount (entry > exit)` on `claimReward`.
- **Bug awareness**: **consistency** (token transfer ↔ tracking variable 갱신이라는 일반 회계 패턴).
- **부가 blocker (symptom 지점)**: `balanceOf()` external — L2a 보조.
- **[Category]**: **Value / Type A / consistency** (L5a).

---

### Case 24 — `web3bugs_62_H_10` (L5a, symptom in recoverTokens, root in creatorClaimSoldTokens)

- **Contract/Function**: Stream / creatorClaimSoldTokens (L597 transfer).
- **버그**: deposit token 전송 시 `redeemedDepositTokens` 갱신 (혹은 `depositTokenAmount = 0`) 누락. 62_H_03 쌍둥이 패턴.
- **Annotation**: `@Post changed(redeemedDepositTokens, true)` on `creatorClaimSoldTokens`.
- **Bug awareness**: **consistency** (동일 token-transfer-tracking 패턴).
- **[Category]**: **Value / Type A / consistency** (L5a). Case 23과 쌍둥이.

---

### Case 25 — `web3bugs_65_H_01` (L5a)

- **Contract/Function**: Basket / handleFees (L136–137).
- **버그**: `startSupply == 0` 분기에서 `lastFee = block.timestamp` 갱신 누락. 다른 두 분기(`lastFee == 0`, 정상 `else`)는 갱신. Supply가 0이었던 기간에도 fee 부과되는 결과.
- **Annotation**: `@Post changed(lastFee, true)` — 모든 분기에서 반드시 변경되어야 함.
- **Bug awareness**: **consistency** (branch 간 일관성 — 다른 branch가 하는 것 누락 확인).
- **[Category]**: **Value / Type A / consistency** (L5a).

---

### Case 26 — `web3bugs_83_H_01` (L5a)

- **Contract/Function**: MasterChef / add (L89).
- **버그**: `totalAllocPoint` 증가 전 `massUpdatePools()` 호출 누락. 기존 pool의 `accConcurPerShare`가 새 `totalAllocPoint`로 소급 반영되어 기존 staker reward 희석.
- **Annotation**: `@Post poolInfo[1].accConcurPerShare (entry != exit)` — 기존 pool에 대해 accConcurPerShare가 반드시 갱신되어야.
- **Bug awareness**: **consistency** (`set`/`update` 함수 다른 곳에서 massUpdatePools 먼저 호출 — 비교로 도출 가능) + **도메인** (reward accrual 이해).
- **[Category]**: **Algorithm / Type A / consistency+domain** (L5a).

---

### Case 27 — `web3bugs_192_H_01` (L5a)

- **Contract/Function**: Lock / extendLock (L90, L91).
- **버그**: `transferFrom`으로 토큰 받으면서 `totalLocked[_asset] += _amount` 누락. 후속 `release()`의 `totalLocked[asset] -= lockAmount`에서 underflow → 자금 영구 락.
- **Annotation**: `@Post totalLocked[_asset] (entry < exit)` 또는 `@Post changed(totalLocked[_asset], true)`.
- **Bug awareness**: **consistency** (`lock()` 함수는 `totalLocked += _amount` 올바르게 수행 — `extendLock`이 놓침. sibling 비교).
- **[Category]**: **Value / Type A / consistency** (L5a).

---

### L5a Subsection Summary (7 cases)

**공통 패턴**:
1. **모두 Type A** (L5 정의상 당연) — 관련 state var가 scope에 있음.
2. **Annotation 형식**: 거의 모두 `changed(x, true)` 혹은 `x (entry relOp exit)` — state 변경 방향/여부 체크로 충분.
3. **Bug awareness source 분포**:
   - **consistency 6건** (35_H_12, 62_H_03, 62_H_10, 65_H_01, 83_H_01, 192_H_01).
   - **domain 1건** (52_H_23).
   - → L5a는 **pattern-check로 대부분 도출 가능**.
4. **Bug category 분포**:
   - **Value (missing state update) 6건**: 35_H_12, 52_H_23, 62_H_03, 62_H_10, 65_H_01, 192_H_01.
   - **Algorithm (missing function call) 1건**: 83_H_01.

**Twin 관찰**:
- (62_H_03, 62_H_10): Stream의 token-transfer-vs-tracking 쌍둥이.
- (35_H_12, 83_H_01, 192_H_01): sibling function 일관성 누락 family.
- (65_H_01): branch 일관성 (단일 함수 내).

**Paper insight**:
- L5a "detectability"는 **annotation 표현이 아닌 "consistency pattern을 개발자가 눈치채는가"**에 달림. 
- 이는 **IntentChecker의 annotation-writing workflow가 sibling/branch consistency 리뷰 원칙과 결합될 때 강력**함을 시사. Paper Discussion에서 "consistency-driven annotation writing" 워크플로우 제안 근거.
- **Domain case (52_H_23)는 별도** — 도메인 전문가 리뷰 필수. Annotation만으로 해소 어려움.

**I8 + L5축 분포 (7 cases)**:
- Value/A/consistency: 5 (35_H_12, 62_H_03, 62_H_10, 65_H_01, 192_H_01).
- Value/A/domain: 1 (52_H_23).
- Algorithm/A/consistency+domain: 1 (83_H_01).

→ **L5a는 Value/A/consistency cell에 집중** — paper에 "가장 쉬운 detection 영역" 으로 제시 가능.

---

## L5b — Wrong Code (7 cases, compact batch: Cases 28–34)

**L5b 정의**: 코드가 존재하나 잘못된 식별자·연산자·struct field·순서 등 사용. Annotation 표현은 가능 (Type A), 정확한 intent 작성에 버그 인지 전제.

---

### Case 28 — `web3bugs_31_H_01` (L5b)

- **Contract/Function**: MyStrategy / manualRebalance (L469, 471, 477).
- **버그**: Dimensional mismatch. `currentLockRatio = balanceInLock * 1e18 / totalCVXBalance` (비율) vs `newLockRatio = totalCVXBalance * toLock / MAX_BPS` (절대 수량) → 비율과 수량을 `<=`로 비교.
- **Fix (audit)**: `currentLockRatio = balanceInLock` (amount로 통일).
- **Annotation**: `@During currentLockRatio (assign == balanceInLock)` — grammar OK, `balanceInLock` in scope.
- **Bug awareness**: **domain** (하류 `cvxToLock = newLockRatio.sub(currentLockRatio)` 분석으로 역추론).
- **[Category]**: **Value / Type A / domain** (L5b).

---

### Case 29 — `web3bugs_35_H_11` (L5b)

- **Contract/Function**: Ticks / cross (L40, L49).
- **버그**: `zeroForOne` 분기에서 잘못된 struct field 갱신 — `ticks[next].feeGrowthOutside0` 업데이트해야 하는데 1번 사용 (반대 분기도 같은 반대).
- **Annotation**: `@Post changed(ticks[nextTickToCross].feeGrowthOutside1, true)` (zeroForOne 시) — 올바른 field만 변경 assert.
- **Bug awareness**: **domain** (`zeroForOne → token1 수수료 → feeGrowthOutside1` 매핑 semantic).
- **[Category]**: **Value / Type A / domain** (L5b).

---

### Case 30 — `web3bugs_70_H_09` (L5b)

- **Contract/Function**: USDV / mint, burn (L76 mint, L109 burn).
- **버그**: `uAmount = vPrice * vAmount / 1e18` (mint), `vAmount = uPrice * uAmount / 1e18` (burn) — oracle 반환 의미(USD/Vader vs Vader/USD)에 따라 공식 방향 틀림.
- **Fix**: `uAmount = vAmount * 1e18 / vPrice` (혹은 `vPrice * vAmount / 1e18` — oracle spec에 따라).
- **Annotation**: `@Post uAmount == vAmount * 1e18 / vPrice` — grammar OK.
- **Bug awareness**: **domain** (oracle API spec 이해 필요).
- **[Category]**: **Value / Type A / domain** (L5b).

---

### Case 31 — `web3bugs_79_H_02` (L5b)

- **Contract/Function**: LaunchEvent / createPair (L398).
- **버그**: `tokenAllocated = (wavaxReserve * 10**token.decimals()) / floorPrice` — `floorPrice`는 1e18 스케일이므로 올바른 계산은 `wavaxReserve * 1e18 / floorPrice`. 18 decimals 아닌 토큰(WBTC=8)에서 심각 오류.
- **Annotation**: `@Post tokenAllocated == wavaxReserve * 1e18 / floorPrice`.
- **Bug awareness**: **domain** (natspec "scaled to 1e18"가 partial 힌트 제공 — 완전 domain은 아니나 scaling semantic 이해 필요).
- **[Category]**: **Value / Type A / domain** (L5b).

---

### Case 32 — `web3bugs_101_H_02` (L5b)

- **Contract/Function**: LenderPool / terminate (L389, L400).
- **버그**: `_actualNotBorrowedInShares`를 token/share 혼합 계산으로 구해 `withdrawShares`에 전달. Terminate = 전체 shares 출금이므로 `_sharesHeld` 직접 사용이 올바름.
- **Fix**: `_sharesHeld`로 단순화.
- **Annotation**: `@Post withdrawShares == _sharesHeld` — `_sharesHeld` in scope.
- **Bug awareness**: **domain** (terminate semantic = "전체 shares 출금" 이해).
- **[Category]**: **Value / Type A / domain** (L5b).

---

### Case 33 — `web3bugs_112_H_01` (L5b, **operation ordering**)

- **Contract/Function**: StakerVault / transfer (L112, 113, 117, 118).
- **버그**: `balances[sender] -= amount` / `balances[receiver] += amount` (L31–32) 이 `userCheckpoint()` (L37, L39) **전에** 실행. Checkpoint가 이미 변경된 balance로 보상 계산 → 과다 reward 청구 경로.
- **Fix**: checkpoint → balance 순서로 교체 (`transferFrom` 함수는 올바른 순서).
- **Annotation**: `@During changed(balances[msg.sender], false)` at checkpoint call 직전 — buggy에서 balance 이미 변경 → VIOLATED. Correct에서 unchanged → SATISFIED.
- **Bug awareness**: **consistency** (`transferFrom`이 올바른 순서 — sibling 비교).
- **[Category]**: **Algorithm / Type A / consistency** (L5b — ordering은 algorithm 성격).

---

### Case 34 — `web3bugs_113_H_05` (L5b)

- **Contract/Function**: NFTPairWithOracle / _lend (L316).
- **버그**: `require(params.ltvBPS >= accepted.ltvBPS, ...)` — lender 입장에서 낮은 LTV 선호이므로 `<=`가 올바름.
- **Annotation**: `@During params.ltvBPS <= accepted.ltvBPS` — require와 complementary.
- **Bug awareness**: **domain** (lender가 어떤 방향이 유리한가 이해).
- **부가 blocker**: `ltvBPS`가 후속 금액 계산에 미사용 (require check만) → state 채널 영향 없음 (L2a 부가적).
- **[Category]**: **Value / Type A / domain** (L5b).

---

### L5b Subsection Summary (7 cases)

**공통 패턴**:
1. **모두 Type A** (L5 정의상).
2. **Annotation 형식 다양**: `@During x (assign == y)` (value 교정), `@Post changed(struct.field, true)` (field 교정), `@Post expr == formula` (공식 교정), `@During changed(x, false)` (ordering 교정).
3. **Bug awareness source 분포**:
   - **domain 6건** (31, 35_H_11, 70_H_09, 79_H_02, 101_H_02, 113_H_05).
   - **consistency 1건** (112_H_01).
   - → L5b는 **domain-knowledge dominant**. L5a와 대비 (consistency-dominant).
4. **Bug category 분포**:
   - **Value 6건**: 31, 35_H_11, 70_H_09, 79_H_02, 101_H_02, 113_H_05.
   - **Algorithm 1건**: 112_H_01 (ordering).

**L5a vs L5b 대조** (Paper insight candidate):
| | L5a (missing-code) | L5b (wrong-code) |
|---|---|---|
| Bug awareness | **consistency dominant** (6/7) | **domain dominant** (6/7) |
| Detection 난이도 | sibling/branch 비교 리뷰로 가능 | 프로토콜 semantic 지식 필요 |
| IntentChecker 기여 | **높음** (pattern discovery 보조) | **제한적** (domain 전문가 몫) |

**I8 + L5축 분포 (L5b 7 cases)**:
- Value/A/domain: 5 (31, 35_H_11, 70_H_09, 79_H_02, 113_H_05).
- Value/A/domain (101_H_02와 같이 파라미터 단순화 case): 1.
- Algorithm/A/consistency: 1 (112_H_01 ordering).

→ **L5b는 Value/A/domain cell에 집중** — "annotation-writing 경험 있는 도메인 전문가" 필요 영역.

---

### 🎉 L5 완료 — Cross-L5 Synthesis (14 cases)

**L5a + L5b 대조 insight**:

```
L5a (missing-code)  → consistency-dominant → IntentChecker의 강점 영역
  (sibling/branch 비교로 annotation writer가 "뭔가 없다"를 catch)

L5b (wrong-code)    → domain-dominant     → IntentChecker의 제한 영역
  (잘못된 identifier/operator/ordering을 semantic 지식 없이 catch 불가)
```

**I8 matrix 전체 (L4+L5 14 cases, L5 7+7=14 합류):**
- Value/A/consistency: 5 (all L5a).
- Value/A/domain: 6 (1 L5a + 5 L5b).
- Value/A/mixed: 0.
- Value/A/grammar-limit: 1 (Case 13, L4c).
- Value/A_candidate: 1 (Case 1, L4a 재검토 대기).
- Value/B: 7 (all L4).
- Algorithm/A/consistency: 2 (112_H_01 L5b, 83_H_01 L5a-mixed).
- Algorithm/A/domain: 0.
- Algorithm/A/grammar-limit: 1 (Case 14, L4d).
- Algorithm/B: 10 (all L4).

**Paper-ready dichotomy**:
- Type A / Value / consistency → **easiest detection**, pattern-check workflow 유효.
- Type A / Value / domain → **domain expert 필요**, annotation이 보조 도구.
- Type A / grammar-limit (L4c, L4d) → **grammar 확장으로 해소 가능** (arithmetic PostEntryExit).
- Type B → **현재 grammar + workflow로는 근본적 한계**. Grammar 확장 + auxiliary injection workflow 필요.

---
