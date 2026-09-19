# IntentKeeper → SolidityGuardian 역포팅 대상 엔진 수정

> **방향**: 이 문서는 IntentKeeper 에서 고친 것 중 **SolidityGuardian 에도 적용할 것**을 모은다.
> (반대 방향 = `(solidityguardian)_engine_code_changes.md`)
>
> ⚠ **SolidityGuardian 디렉토리는 읽기 전용이다.** 여기 적힌 것을 Guardian 에 옮길지, 언제 옮길지는
> 사용자가 결정한다. 이 문서는 "무엇을 어떻게 옮기면 되는지"의 명세일 뿐이다.
>
> **적용 여부 확인 방법**: 각 항목의 `Guardian 상태` 는 Guardian 파일을 **읽어서** 확인한 것이다
> (2026-09-19 기준). 포팅 전 재확인 권장.
>
> 관련 로그: `PROGRESS.md` (decision 번호), `Dependencies/ISSUES.md` (의존성 분석 이슈)

---

## 배경 — 왜 이 수정들이 필요했나

IntentKeeper 에서 `Dependencies/objectfile/*.pkl` 을 **전량 재생성**하면서 드러났다.
재생성 전에는 `analyze_file` 이 visitor 예외를 `[ERR]` 로 출력만 하고 넘어갔고, 그 결과
**함수 CFG 에 statement 가 하나도 안 들어간 채 pkl 로 저장**돼 있었다. 그런 함수를 호출하면
크래시도 경고도 없이 **선언된 리턴변수의 기본값(예: uint160 이면 0)을 조용히 반환**한다.
(Guardian 의 `Dependencies/main.py:343` 주석이 지적한 바로 그 현상 —
"web3bugs_35_H_10 케이스 빌드 중 TickMath.getSqrtRatioAtTick / DyDxMath.getDx/getDy 에서 발견,
아직 아무 pkl 도 이걸로 재생성하지 않았음")

**전체 효과 (IntentKeeper 기준, 135개 의존성 소스 재생성)**

| | 수정 전 | 수정 후 |
|---|---:|---:|
| visitor 오류 `[ERR]` | 552 | **212** (−62%) |
| 파싱 오류 `[ANTLR]` | 212 | **192** |
| 본문 있는 함수 | 380 | **384** |
| 본문이 빈 채 저장된 함수 | 39 | **30** |

**복구된 대표 함수** (전부 stmts=0 → 채워짐)

| 함수 | 전 | 후 |
|---|---|---|
| `UnsafeMath.divRoundingUp` | nodes=4, stmts=**0** | nodes=5, stmts=**1** |
| `DyDxMath.getDx` | nodes=9, stmts=**0** | nodes=11, stmts=**2** |
| `DyDxMath.getDy` | nodes=9, stmts=**0** | nodes=11, stmts=**2** |
| `DyDxMath.getLiquidityForAmounts` | nodes=12, stmts=**0** | nodes=17, stmts=**5** |
| `FullMath.mulDiv` | — | nodes=38, stmts=**25** |
| `TickMath.getSqrtRatioAtTick` | stmts=**0** | nodes=110, stmts=**23** |
| `TickMath.getTickAtSqrtRatio` | stmts=**0** | nodes=80, stmts=**69** |

이 함수들에 의존하는 평가 케이스: **web3bugs_35_H_08 / 35_H_10 / 35_H_12**

---

## F1. `require`/`assert` 가 BOTTOM 을 전파하지 않음 ★코어

**파일**: `Interpreter/Engine.py` — `_run_worklist` 의 `condition_node_type in ["require","assert"]` 분기
**Guardian 상태**: 미확인(포팅 전 확인 필요). IntentKeeper 에선 `PROGRESS.md` decision #42.

**증상**: debug 입력이 함수 가드와 모순이면(`a=[200,300]` vs `require(a<=100)`)
`@Post` 가 `Warning` + `internal error: This 'balance' is may be elementary variable but may not be declared`
(risk 0.0)로 나온다. 같은 상황에서 `@During` 은 `Unreachable` 을 낸다 — **두 경로 비일관**.

**근본 원인**: `can_true` 가 False 일 때
```python
else:
    self._set_bottom_env(t.variables)   # t.variables 가 아직 {} → 빈 dict 순회 = no-op
    # work.append(t) 없음 → BOTTOM 이 downstream 으로 전혀 안 퍼짐
```
**바로 위 `if`/`else-if` 분기는 같은 상황을 올바르게 처리**한다(seed → BOTTOM → append).
즉 메커니즘은 이미 있는데 require/assert 분기만 두 줄을 빠뜨렸다.

연쇄: 이후 노드가 전부 `{}` → `_force_join_before_exit` 가 `{}` 들을 join → `EXIT.variables={}`
→ `_is_bottom_env({})` 가 **False** → 도달불가 인식 실패.

**실측 근거**: 정상/모순 모두 `EXIT.preds=1` 로 **그래프는 안 끊긴다**. 차이는 predecessor 의
`variables` 개수뿐(17 → 0). → predecessor 검사로는 못 잡고 env 를 봐야 한다.
그리고 BOTTOM 이 아니라 *빈 dict* 였다 → `_is_bottom_env` 단독으론 못 잡는다.

**수정**
```python
else:
    t.variables = VariableEnv.copy_variables(cur_vars)   # ① seed
    self._set_bottom_env(t.variables)                     # ② BOTTOM
    work.append(t)                                        # ③ 전파
```

**부수 효과(의도됨)**: 직렬화가 `state={}` → `state={a:'⊥', …}` 로 바뀐다. 프론트가 `⊥` 포함
여부로 dead 를 판정한다면 그동안 dead 노드를 못 잡고 있었던 것이 자동 해결된다.

---

## F2. `@Post` 도달불가 판정 + `_exit_env` 폴백 제거 ★코어

**파일**: `Interpreter/Engine.py` `_process_exit_node_intents`,
`Analyzer/GuardianVerificationEngine.py` `_exit_env`
**Guardian 상태**: 미확인. IntentKeeper `PROGRESS.md` decision #42 와 한 묶음.

**수정 A** — `_process_exit_node_intents` 진입부(**try 블록보다 앞**)에 도달불가 판정 추가.
try 안에 두면 그 `except` 가 예외를 삼켜 다시 internal-error 로 둔갑한다.
```python
preds = guardian._preds(fcfg, normal_only=True)
if not preds: unreachable
else:
    env = guardian._exit_env(fcfg, normal_only=True)
    unreachable = (not env) or self._is_bottom_env(env)
```
`_preds` 를 먼저 보는 이유: (a) 정상 경로로 exit 에 닿는 길이 없으면 그 자체로 도달불가,
(b) 아래 수정 B 로 `_exit_env` 가 raise 하므로 여기서 먼저 걸러야 한다.

**수정 B** — `_exit_env` 의 `related_variables` 폴백을 **fail-loud** 로.
```python
preds = self._preds(...)
if not preds:
    raise RuntimeError("_exit_env: no normal predecessor for exit of ...")
```
그 폴백은 `_get_post_exit_node` 가 없던 시절 "explicit return 함수의 EXIT 는 predecessor 0개" 를
덮던 응급처치(**Guardian Initial commit 유래**)이고, 근본 원인은 `_get_post_exit_node` 가
RETURN 을 고르면서 이미 해결됐다. 남겨두면 *도달 불가한* exit 를 "선언 초기값 env" 로 덮어써
**vacuous verdict** 를 만든다. 9가지 함수 형태로 폴백 발동을 시도했으나 **0회** — 사실상 사문화.

⚠ `VerdictStatus` 에 `Unreachable` 이 없다면 함께 추가해야 한다.

---

## F3. `assembly` 분기에서 `find_function_context` 튜플 언패킹 누락 ★최대 효과

**파일**: `Analyzer/SolidityAnalyzer.py` (Guardian: **L291-296**)
**Guardian 상태**: ❗**동일 버그 존재 확인** (L295 `ca.current_target_function = ca.find_function_context(start_line)`)

**증상**: `[ERR] ctx=assembly: unhashable type: 'list'` — **131건**, 10개 파일.
assembly 를 가진 모든 소스가 **첫 Yul 문장부터** 실패해 함수 본문이 빈 채 저장된다.

**traceback**
```
EnhancedYulVisitor.visitYulAssignment
 → ContractAnalyzer.process_yul_assignment
 → ContractCFG.get_function_cfg
 → self.functions.get(function_name)      TypeError: unhashable type: 'list'
```

**근본 원인**: `find_function_context` 는 docstring 대로 **`(함수이름, 파라미터타입리스트)` 튜플**을
반환하는데, assembly 분기만 그걸 통째로 `current_target_function` 에 넣는다.
**전수 확인: 6개 호출부 중 나머지 5개는 전부 정상 언패킹.** 고립된 버그다.

**수정**
```python
if parent == "assembly":
    ca.current_context_type = "assembly"
    ca.current_target_contract = ca.find_contract_context(start_line)
    ca.current_target_function, ca.current_target_function_param_types = \
        ca.find_function_context(start_line)
    return
```

---

## F4. Solidity 16진 리터럴을 signed 로 판정 ★두번째 효과

**파일**: `Analyzer/EnhancedSolidityVisitor.py` `visitLiteralExp` (Guardian: **L2380**)
**Guardian 상태**: ❗**동일 버그 존재 확인**

**증상**: `Bitwise/Shift operands must both be int/uint intervals` — **156건**
(TickMath, PRBMathCommon, PRBMathSD59x18, FixedPoint, BitMath 등)

**근본 원인**
```python
result_expr.expr_type = 'uint' if literal_value.isdigit() else 'int'
#                                                             ^^^^^  16진 → signed
```
Solidity 숫자 리터럴은 10진·16진 **모두 부호 없는 값**이다. 음수는 단항 `-` 이지 리터럴 자체가
음수가 되지 않는다. 10진과 16진을 다르게 취급할 이유가 없다.

**연쇄 (TickMath 실증)**
```solidity
uint256 ratio = absTick & 0x1 != 0 ? 0xfffcb933... : 0x1000...;
```
```
0x1        → 'int' → IntegerInterval
absTick    → uint256 → UnsignedIntegerInterval
absTick & 0x1                       → 타입 불일치 ✗
0xfffcb933... → IntegerInterval → ratio(uint256 선언)가 signed 로 오염
ratio >> 128 (128 은 10진 → Unsigned) → 타입 불일치 ✗
```

**수정**
```python
if literal_value.isdigit() or literal_value.startswith(('0x', '0X')):
    result_expr.expr_type = 'uint'
    result_expr.type_length = 256
```

⚠ **주소 리터럴을 여기서 분리하지 않는다**(검토 후 기각):
- Solidity 주소는 `address(0x..)` **타입 변환**으로 들어오고 별도 경로다
  (`expr_type='address'` 를 세팅하는 유일한 곳은 intent 문법의 `visitAddrLiteralExpr`)
- `Evaluation._literal_is_address` 는 길이 검사가 없어 `0x1` 도 "주소" 로 통과한다
- 이 리포의 맨몸 40-hex 4건은 **전부 비트마스크**였다(`SafeTransferLib` 의 `0xff..ff`).
  길이로 판정하면 그걸 주소로 오분류한다.

**효과**: Bitwise 89 → **0**, Shift 67 → **3**, 미선언 오류 96 → 69.

---

## F5. Yul 리터럴이 `expr_type` 없음 + `literal` 이 int

**파일**: `Analyzer/EnhancedYulVisitor.py` `_build_literal` (Guardian: **L178-194**)
**Guardian 상태**: ❗**동일 버그 존재 확인**

**증상**: `[ERR] ctx=assembly: Unsupported literal expr_type 'None'` — **51건**
(TickMath 36, PRBMathCommon 7, PRBMathSD59x18 5, FullMath 2, UnsafeMath 1)

**근본 원인 (둘)**
1. **`expr_type` 미설정** — 5개 반환 경로 전부. `evaluate_literal_context` 가 `ety` 로 분기하는데
   `None` 이면 모든 분기를 빠져나가 마지막 `raise` 에 걸린다.
2. **`literal` 이 str 이 아니라 int** — `int(getText())` 로 변환해 넣는다. 그런데
   `evaluate_literal_context` 는 `int(txt, 0)` 로 파싱하므로 int 를 주면
   `TypeError: int() can't convert non-string with explicit base` 가 나고,
   그 함수의 `except ValueError` 로는 **안 잡힌다**.
   → ①만 고치면 51건이 `TypeError` 로 바뀔 뿐이다. **둘을 같이 고쳐야 한다.**

**타입 판정 = `'uint'` / 256**: Yul 은 타입 없는 256-bit word 언어다.
이 리포 소스에서 `slt`/`sdiv`/`smod`/`sar`/`signextend` 는 **0건**, `sgt` 만 7건.

**수정**
```python
if ctx.DECIMAL_NUMBER():
    return Expression(literal=ctx.DECIMAL_NUMBER().getText(),
                      expr_type='uint', type_length=256, context="LiteralExpContext")
if ctx.HEX_NUMBER():
    return Expression(literal=ctx.HEX_NUMBER().getText(),   # '0x..' 원문 그대로
                      expr_type='uint', type_length=256, context="LiteralExpContext")
if ctx.STRING_LITERAL():
    return Expression(literal=ctx.STRING_LITERAL().getText(),
                      expr_type='string', context="LiteralExpContext")
text = ctx.getText()
if text in ('true', 'false'):        # Yul 에 bool 없음 → 1/0 word
    return Expression(literal='1' if text == 'true' else '0',
                      expr_type='uint', type_length=256, context="LiteralExpContext")
raise ValueError(f"Unknown yulLiteral: {text!r}")   # 무조건 0 반환 폴백 제거
```

**효과**: `UnsafeMath` 오류 1→0, `FullMath` 2→0. `DyDxMath` 본문 복구.

---

## F6. 비트 연산 `& | ^` 이 `Evaluation` 디스패치에 없음

**파일**: `Interpreter/Semantics/Evaluation.py` `evaluate_binary_operator`
**Guardian 상태**: ❗**동일 누락 확인** — 디스패치 0건, 그러나 `Domain/Interval.py` 에
`bitwise`/`bitwise_not` 은 **이미 5개 존재**한다. 즉 **도메인은 있는데 배선만 없다.**

**증상**: `Unsupported operator '&' in expression: absTick & 0x2` 등 **약 105건**
(전부 Solidity 식. `ctx=if` 92, `simpleStatement` 10)

**중요**: 식 평가가 실패하면 대입문이 통째로 실패해 **LHS 가 이전 값을 유지**한다 —
⊤ 로 떨어지는 게 아니라 **조용한 오분석**이다.

**수정** (시프트 분기 바로 뒤, 시프트와 **동일한 규약**: 타입 일치 요구, 불일치 시 예외)
```python
elif operator in ('&', '|', '^'):
    if (isinstance(leftInterval, IntegerInterval) and
            isinstance(rightInterval, IntegerInterval)):
        result = leftInterval.bitwise(operator, rightInterval)
    elif (isinstance(leftInterval, UnsignedIntegerInterval) and
          isinstance(rightInterval, UnsignedIntegerInterval)):
        result = leftInterval.bitwise(operator, rightInterval)
    else:
        raise ValueError(f"Bitwise operands must both be int/uint intervals, got "
                         f"{type(leftInterval).__name__} and {type(rightInterval).__name__}")
```
단항 `~` 는 `evaluate_unary_operator` 에 **이미 배선돼 있다**(`bitwise_not()`).

⚠ **F4 와 함께 적용해야 한다.** F6 만 넣으면 105건이 "Unsupported operator" 에서
"타입 불일치" 로 바뀔 뿐이다(실측: 89건이 그렇게 됐다).

⚠ **논문 claim 확인 필요**: IntentChecker 원고 Limitations 가 Yul 지원에
"bitwise operations, shifts" 를 포함한다고 적었는데, Yul `_BINARY_OPS` 는 `and/or/xor` 를
`&/|/^` 로 매핑하므로 **이 디스패치가 없으면 Yul 비트 연산도 동작하지 않았다.**

---

## F10. Yul 비교 연산이 `BoolInterval` 을 냄 (Yul 엔 bool 이 없다)

**파일**: `Analyzer/EnhancedYulVisitor.py` — `_BINARY_OPS` 매핑 / `_build_function_call`
**Guardian 상태**: ❗**동일 구조** (`'gt': '>'` 등으로만 매핑, word 변환 없음)

**증상**: `Shift operands must both be int/uint intervals, got UnsignedIntegerInterval and BoolInterval`
— TickMath 41건 중 **40건이 이 하나에서 연쇄**.

**실패 패턴** (3줄 묶음이 8회 반복)
```yul
let f := shl(7, gt(r, 0xFFFF...))   ← Shift: Unsigned << BoolInterval  ✗
msb := or(msb, f)                    ← 'f' 미선언 (앞줄이 실패해 선언 안 됨)
r   := shr(f, r)                     ← 'f' 미선언
```

**근본 원인**: **Yul 에는 bool 타입이 없다.** `lt`/`gt`/`slt`/`sgt`/`eq`/`iszero` 는
**1 또는 0 인 256-bit word** 를 반환하고 그대로 산술·시프트에 쓰인다.
`shl(7, gt(r, C))` = "조건이 참이면 128, 거짓이면 0" 은 흔한 Yul 관용구다.
그런데 `_BINARY_OPS` 가 `'gt' → '>'` 로만 매핑해 Solidity 비교로 평가되고 `BoolInterval` 이 나온다.

**수정**: 비교 계열 결과를 `cond ? 1 : 0` 삼항으로 감싸 uint word 로 만든다.
```python
_CMP_OPS = {'lt', 'gt', 'slt', 'sgt', 'eq'}      # and/or/xor 는 비트연산이므로 제외

@staticmethod
def _word(literal: str) -> Expression:
    return Expression(literal=literal, expr_type='uint', type_length=256,
                      context="LiteralExpContext")

def _as_word(self, cond: Expression) -> Expression:
    return Expression(condition=cond, true_expr=self._word('1'), false_expr=self._word('0'),
                      operator='?:', context="ConditionalExpContext")
```
호출부: 2인자 binary op 가 `_CMP_OPS` 면 `_as_word(...)` 로 감싸고,
`iszero` 도 `_as_word(...)` 로 감싼다(우변 리터럴도 `_word('0')` — F5 의 문자열 규약).

**정밀도 손실 없음**: `evaluate_conditional_expression_context` 가 `BoolInterval [1,1]`/`[0,0]`
이면 해당 분기로 **정확히 접고**, `[0,1]` 이면 두 분기를 join 해 `[0,1]` 을 준다. ⊤ 로 안 뭉갠다.

⚠ **Yul 경로에만 적용한다.** Solidity 에선 bool 이 산술에 쓰일 수 없으므로 `Evaluation` 쪽에서
`BoolInterval` 을 승격하면 진짜 타입 오류를 덮게 된다.

**효과**: TickMath 41 → 19. **`TickMath.getSqrtRatioAtTick`(nodes=110, stmts 0→23)과
`getTickAtSqrtRatio`(nodes=80, stmts 0→69) 본문 복구** — Guardian 주석이 명시했던 함수들이다.

---

## F11. 시프트 추상 의미론이 불건전 ★코어 · 전수 검증

**파일**: `Domain/Interval.py` — `IntegerInterval.shift`, `UnsignedIntegerInterval.shift`
(+ `Interpreter/Semantics/Evaluation.py` 시프트 디스패치)
**Guardian 상태**: 미확인(같은 코드로 보임 — 포팅 전 확인).

**증상 ①(불건전)**: 음수 구간에서 **참값을 놓치거나 역전된 구간**을 만든다.
```
[-4,-1] << [0,2] : 참값 (-16,-1) → 구현 (-4,-4)     ← 불건전
[-8,-8] << [0,3] : 참값 (-64,-8) → 구현 (-8,-64)    ← lo>hi 역전
[-8,-8] >> [0,3] : 참값  (-8,-1) → 구현 (-1,-8)     ← 역전
```
전수 검증(w=4/5, wrap 의미론 기준): **signed 49~53%, unsigned 41~44% 조합이 불건전**.

**증상 ②(디스패치)**: `Evaluation` 이 산술처럼 "좌우 타입 일치"를 요구해
`int256 log_2 = (int256(msb) - 128) << 64;`(유효한 Solidity)가 거부됐다.
그 한 줄이 실패하면 `log_2` 선언이 안 돼 뒤따르는 assembly 18줄이 연쇄 실패(TickMath).

**근본 원인**
1. `x << s ≡ x·2^s` 는 **부호에 따라 단조성이 뒤집힌다**. 그런데 구현은
   `lo = x.min << s.min`, `hi = x.max << s.max` 로 **코너를 고정**했다(양수만 가정).
2. unsigned 는 오버플로를 **포화(clamp)** 했다. Solidity 시프트는 revert 없이 **wrap** 하므로
   `(2^255) << 1 = 0` 이다 — 포화는 그 작은 값을 놓친다.
3. 시프트는 산술이 아니다. **좌변=피시프트값 / 우변=시프트양** 으로 역할이 다르고,
   Solidity 에서 시프트 양은 unsigned, 좌변은 signed 여도 된다.

**수정** — 두 클래스의 `shift` 를 동일 로직으로 재정의:
- **4코너 min/max** (고정 코너 폐기)
- 오버플로 → **TOP** (포화 아님)
- **거대 정수를 만들지 않는다**: `'<<'` 는 `s.max ≥ w` 면 계산 없이 TOP,
  `'>>'` 는 `s` 를 `w` 로 캡(그 이상은 결과가 동일 — 0 또는 -1)
- `shift_iv` 는 min/max 만 읽으므로 **타입이 달라도 된다** →
  `Evaluation` 의 타입 일치 요구를 제거(`leftInterval.shift(rightInterval, op)` 로 단순화)

**검증**: 실제 클래스로 w=4/5 전수 — signed/unsigned 각 5,712·29,568 조합 **불건전 0건**
(시프트 양을 uint256 으로 전달해 타입 불일치 상황도 포함).
`uint256 TOP << TOP`, `int256 TOP >> TOP` 모두 **0.0ms** 즉시 반환.

---

## F12. 산술 결과가 타입 범위를 벗어나 **비트수가 폭주** ★코어

**파일**: `Domain/Interval.py` — signed `add`/`subtract`/`multiply`/`exponentiate`,
unsigned `add`/`multiply`/`exponentiate`
**Guardian 상태**: 미확인(같은 코드로 보임 — 포팅 전 확인).

**증상**: `PRBMathSD59x18.sol` 분석이 **끝나지 않는다**(전체 재생성이 멈춤).
스택: `Interval._mul` ← `multiply` ← `evaluate_binary_operator` ← `fixpoint` ← `reinterpret_from`.

**근본 원인 — 연산자가 아니라 도메인 불변식 부재**:
`multiply` 자체는 4코너 min/max 로 **정확하고 O(1)** 이다. 문제는
`IntegerInterval(lo, hi, w)` 가 `w` 를 **받기만 하고 경계를 강제하지 않는** 것이다.
그래서 결과가 타입 범위를 벗어난 채 다음 연산의 피연산자가 되고,
fixpoint 루프의 `x = x*x` 에서 **비트수가 매 반복 2배**로 자란다.

실측(int256 TOP 에서 시작):
```
시작 255비트 → 1회 511 → 2회 1021 → 3회 2041 → … → 8회 65,281비트
```
각 연산은 O(1)인데 **피연산자가 도메인을 탈출**해 멈춘 것이다.

부수 확인:
- signed `add`/`subtract`/`multiply` 는 **경계 강제가 전혀 없었다**.
- unsigned `multiply` 는 `max` 만 `type_max` 로 포화시키고 **`min` 은 그대로** 뒀다
  → `[거대값, type_max]` 역전 구간이 나온다.
- `exponentiate` 는 `pow(base, exp)` 를 **실제로 계산**한다 → `pow(2, 2**255)` 에서 멈춘다.

**수정**
```python
def _fit_signed(lo, hi, w):      # 벗어나면 TOP (포화 아님 — unchecked 는 wrap)
def _fit_unsigned(lo, hi, w):
def _pow_fits(base, exp, w):     # 비트수로 미리 판정 — 거듭제곱을 수행하지 않는다
                                 #   결과 비트수 ≈ exp · bitlen(base)
```
위 7개 연산의 결과에 적용하고, `exponentiate` 는 `_pow_fits` 가 거짓이면 **계산 없이 TOP**.

⚠ **unsigned `subtract` 는 그대로 둔다** — 이미 유계이고(`[0, a.max]`),
"항상 음수면 bottom"(= underflow revert → 도달불가) 로직이 **checked 의미론으로 load-bearing** 이다
(`require(a <= bal); balance = bal - a` 같은 패턴이 여기 의존한다).

**검증**: `x = x*x` 30회 반복 후 비트수가 255/256 유지, **0.0ms**.
`uint256 2 ** [0, 2^255]` 도 즉시 TOP 반환.

**효과**: 정지 해소 → 전체 재생성 정상 완료(pkl 134, regen1 과 차집합 0).
`[ERR]` 246 → **212**. PRBMathSD59x18 30→23, TickMath 19→14. **증가한 파일 0개.**

⚠ **정밀도 영향**: 오버플로 지점이 포화값 대신 TOP 이 된다. 곱셈은 자주 쓰이므로 영향이 넓다.
다만 기존 포화값은 **틀린 값**이었고, TOP 은 Warning 으로 흐르지 잘못된 Satisfied 를 만들지 않는다.
더 정밀하게 하려면 `unchecked_block` 플래그로 checked 문맥에선 '범위 교집합' 을 쓰면 된다(별건).

---

## F13. Yul 비트 연산의 타입 불일치 — 2의 보수 word 재해석 ★코어

**파일**: `Analyzer/EnhancedYulVisitor.py` (컨텍스트 표식 7곳),
`Interpreter/Semantics/Evaluation.py` (`_is_yul_ctx`, `_reinterpret_as`, 비트 분기)
**Guardian 상태**: ❗**동일** — Guardian 의 `EnhancedYulVisitor` 도
`context="BinaryOperationContext"` 를 쓰고, F6 자체가 미적용이라 비트 분기가 없다.
F6 을 먼저 포팅한 뒤 이 항목을 얹어야 한다.

**증상**: `Bitwise operands must both be int/uint intervals, got IntegerInterval and
UnsignedIntegerInterval` — **15건** (TickMath 14, PRBMathSD59x18 1).
```yul
// TickMath.getTickAtSqrtRatio, L136 부터 6줄 간격으로 14회
log_2 := or(log_2, shl(63, f))
```
좌변 `log_2` 는 Solidity 쪽에서 `int256 log_2` 로 선언됐고(IntegerInterval),
`shl(63, f)` 는 Yul 리터럴이라 unsigned(UnsignedIntegerInterval) 다.

**근본 원인**: **Yul 에는 타입이 없다.** 모든 값이 raw 256-bit word 이고
`or`/`and`/`xor` 는 비트 패턴에만 작용한다. 즉 위 코드는 Yul 로서 **완전히 합법**이다.
엔진은 Solidity 선언의 타입(`int256`)을 Yul 블록 안까지 그대로 들고 들어가고,
F6 에서 넣은 "양쪽 타입 일치" 검사가 그것을 거부했다.
그 검사는 **Solidity 경로에서는 유지돼야 한다**(Solidity 에선 `int & uint` 가 실제 타입 에러).
따라서 "검사를 없앤다"가 아니라 **Yul 경로를 구분**하는 것이 옳은 수정이다.

**수정 (2단계)**

1. Yul 이 만든 표현식에 출처 표식을 남긴다 — `EnhancedYulVisitor` 의
   `context="BinaryOperationContext"` 6곳 → `"YulBinaryOperationContext"`,
   `"UnaryOperationContext"` 1곳 → `"YulUnaryOperationContext"`.
   (Evaluation 은 `context` 를 **분기 조건으로만** 쓰고 문자열 값 자체를 소비하지 않으므로
   접두어 추가는 기존 Solidity 경로에 영향이 없다 — 전 호출부 확인 완료.)

2. 비트 분기에서 Yul 표식이 있을 때만 피연산자를 2의 보수 word 로 재해석한다.
```python
def _is_yul_ctx(expr) -> bool:
    c = getattr(expr, "context", None)
    return isinstance(c, str) and c.startswith("Yul")

def _reinterpret_as(iv, target_cls):
    if iv.is_bottom():
        return target_cls(None, None, iv.type_length)
    w, lo, hi = iv.type_length, iv.min_value, iv.max_value
    if target_cls is UnsignedIntegerInterval:
        return UnsignedIntegerInterval(lo, hi, w) if lo >= 0 \
               else UnsignedIntegerInterval.top(w)      # 부호 비트가 갈림 → TOP
    return IntegerInterval(lo, hi, w) if hi <= (1 << (w - 1)) - 1 \
           else IntegerInterval.top(w)
```
**건전성**: 부호 비트가 구간 안에서 변하지 않으면(`min ≥ 0` 이거나 `max ≤ 2^(w-1)-1`)
비트 패턴이 그대로라 **값 범위가 동일** — 손실이 없다. 변하면 비트 패턴이 갈라지므로
TOP 을 준다. 결과 타입은 **좌변을 따른다**(시프트와 동일 규약).

**효과**: `[ERR]` 212 → **198**. `TickMath.sol` **14 → 0**.
pkl 134 동일, `[ANTLR]` 192 동일, **증가한 파일 0개**, 본문 있는 함수 384 유지.

⚠ **작업 중 자초한 사고 기록**: 이 헬퍼들을 처음에 `class Evaluation` **본문 안에**
컬럼 0 `def` 로 넣었다. 컬럼 0 이 클래스 본문을 끝내버려 아래 55개 메서드가 전부
모듈 레벨 함수가 됐고 `[ERR]` 이 212→**1303** 으로 폭발했다(970건이
`'Evaluation' object has no attribute 'evaluate_binary_operator'`).
모듈 레벨 헬퍼는 반드시 `class` 선언 **앞**에 둘 것. 포팅 시 `ast` 로
`Evaluation` 메서드 수(55)를 확인하면 즉시 잡힌다.

---

## F14. Solidity 숫자 리터럴의 문맥 타이핑 ★코어

**파일**: `Interpreter/Semantics/Evaluation.py` — `_is_numeric_literal`, `_literal_retype`, 비트 분기
**Guardian 상태**: ❗**동일** — F4/F6 과 한 묶음. F4 를 포팅하면 이 문제가 같이 따라온다.

**증상**: F13 적용 후에도 남은 마지막 1건.
```solidity
// PRBMathSD59x18.sol:27  (int256 x, int256 y)
result = (x >> 1) + (y >> 1) + (x & y & 1);
```
`(x & y)` = IntegerInterval, 리터럴 `1` = UnsignedIntegerInterval → 타입 검사 거부.
**Yul 이 아니라 Solidity 경로**라 F13 의 재해석이 적용되지 않는다(적용되면 안 된다).

**근본 원인 — F4 의 필연적 귀결**:
Solidity 에서 숫자 리터럴은 **타입이 없는 유리수**이고, 타입은 **문맥**(상대 피연산자)이 정한다.
`int256 & 1` 에서 `1` 은 `int256(1)` 로 변환되는 것이 언어 규칙이다.
F4 는 `visitLiteralExp` 에서 모든 숫자 리터럴을 uint256 으로 **못박았다**.
그 자체는 옳다 — 음수 리터럴은 존재하지 않고 단항 `-` 로 표현되므로.
빠진 것은 **사용 시점의 문맥 타입 부여**다.

**수정**: 비트 분기에서 타입이 엇갈릴 때, 한쪽이 숫자 리터럴이면 상대 타입으로 재해석.
```python
def _literal_retype(sub_expr, iv, target_cls):
    if type(iv) is target_cls or not _is_numeric_literal(sub_expr):
        return None
    ...
    if lo < b_lo or hi > b_hi:
        return None            # 대상 타입 범위 밖 → 호출부에서 예외 (실제 Solidity 도 컴파일 에러)
    return target_cls(lo, hi, w)
```
호출부는 `expr.right` 를 먼저, 안 되면 `expr.left` 를 시도하고, 둘 다 실패하면
F13 의 Yul 재해석으로 넘어간다. 그것도 아니면 예외 — **⊤ 로 덮지 않는다.**

**F13 과의 차이(혼동 주의)**
| | F13 `_reinterpret_as` | F14 `_literal_retype` |
|---|---|---|
| 대상 | Yul 문맥의 **모든** 피연산자 | Solidity 숫자 **리터럴**만 |
| 근거 | Yul 엔 타입이 없다 (raw word) | 리터럴엔 타입이 없다 (유리수) |
| 손실 | 부호 비트 갈리면 **TOP** | **없음** (단일 상수, 범위 밖이면 예외) |

**적용 범위**: 비트 분기(`& | ^`)에만 넣었다. 산술(`+ - * / % **`)은 도메인 메서드를
직접 호출할 뿐 **타입 일치 검사가 없어** 현재 실패 사례가 없다. 실패하지 않는 경로를
건드리면 값이 조용히 바뀌므로 손대지 않았다(포팅 시에도 동일하게 할 것).

**효과**: `[ERR]` 198 → **197**, 비트 타입 불일치 **15 → 0**(전부 해소).
`PRBMathSD59x18.sol` 23 → 22, `PRBMathSD59x18.avg` 가 본문을 갖게 됨
(본문 있는 함수 384 → **385**, 빈 함수 30 → **29**). **증가한 파일 0개**, pkl 134 동일.

---

## F15. 인터페이스 body 의 event 선언이 null 컨텍스트로 새어나감 ★진단

**파일**: `Analyzer/ContractAnalyzer.py` — `analyze_context`, 인터페이스 분기
**Guardian 상태**: 미확인(같은 코드로 보임 — 포팅 전 확인).

**증상**: `[ERR] L4 ctx=None: None` — **59건**(인터페이스 15개).
메시지가 `None` 이라 오래 "원인 불명"으로 남아 있었다.

**근본 원인**: 인터페이스 body 분기가 `function ` 이 아니면 `return` 으로 "스킵" 했는데,
그 **스킵이 호출자에게 전달되지 않는다**. `analyze_context` 는 앞에서 이미
`current_context_type`/`current_target_contract` 를 None 으로 초기화한 뒤 그냥 돌아올 뿐이다.
드라이버(`Dependencies/main.py`, `main.simulate_inputs`, `EngineSession._apply_code_record`)는
`ctx is None` 을 확인하지 않으므로 그대로 파싱·visit 을 계속하고,
`event` 선언은 문법적으로 멀쩡하니 파싱에 성공해 visitor 가 돈다:

```
visitEventDefinition → process_event_definition
    ccf = self.contract_cfgs[self.current_target_contract]   # ← None
    → KeyError: None      # str(KeyError(None)) == 'None'  ← 메시지가 'None' 인 이유
```

**수정**: contract/library 분기엔 이미 있는 `event` 처리를 인터페이스에도 맞춘다.

```python
if stripped_code.startswith('function '):
    self.current_context_type = "functionDefinition"
elif stripped_code.startswith('event '):
    self.current_context_type = "event"
else:
    return
self.current_target_contract = self.find_contract_context(start_line)
```

`else: return` 은 유지 — 전수 조사 결과 이 코퍼스에서 **도달 0건**이고(슬라이서가 여러 줄
함수 시그니처를 한 레코드로 합치므로 연속 줄은 오지 않는다), 유효한 Solidity 중 유일하게
올 수 있는 것은 custom error 다(아래 "아직 안 고친 것" 참조).

**효과**: `[ERR]` 197 → **138**. `None` 메시지 **59 → 0**. 증가한 파일 0개.

⚠ **정직하게**: 분석 결과는 달라지지 않는다. `ccf.events` 는 **아무도 읽지 않고**
(`process_emit_statement` 는 `pass`, emit 은 상태를 안 바꾼다), 본문 있는 함수 385 / 빈 함수 29 로
전후 동일하다. 이건 **59건의 가짜 경보를 없애 진짜 문제가 보이게 하는** 정리다.
다만 "스킵 의도가 호출자에게 전달되지 않는" 구조 자체가 결함이므로 고쳐두는 게 맞다.

---

## F16. `bytesN` constant 가 전부 거부 + 문자열 리터럴 정확 인코딩 ★코어

**파일**: `Analyzer/ContractAnalyzer.py` — `process_constant_variable`,
`Interpreter/Semantics/Evaluation.py` — `evaluate_literal_context` bytesN 분기
**Guardian 상태**: 미확인(같은 코드로 보임 — 포팅 전 확인).

**증상**: `Type 'bytes32' cannot be declared as constant: 'GOVERNANCE'` — **24건**
(Roles 9 · AddressProviderKeys 9 · ERC1155Upgradeable 2 · Controller 2 · ERC165Upgradeable 1 · LockeERC20 1).

**근본 원인 (1) — 허용 목록 누락**: 게이트가
`et in ["string","bytes"] or et.startswith(("int","uint","bool")) or et == "address"` 인데
`"bytes"` 는 **동적** bytes 만 매치한다. `bytes1..bytes32` 는 Solidity 의 value type 이고
`Domain/BytesSet.py` 와 `evaluate_literal_context` 의 bytesN 분기가 **이미 있었다** — 게이트만 막고 있었다.
선언이 거부되면 `register_var` 까지 못 가므로 이 상수를 읽는 코드가 연쇄 실패한다.

**근본 원인 (2) — 리터럴에 선언 타입이 전달되지 않음**: 초기화식 실측 분포

| 형태 | 건수 | `context` | `expr_type` |
|---|---:|---|---|
| 문자열 `"governance"` | 19 | `LiteralExpContext` | `'string'` |
| 16진 `0x01ffc9a7` | 3 | `LiteralExpContext` | `'uint'` |
| `keccak256(...)` | 2 | `FunctionCallContext` | `None` |

`visitLiteralExp` 는 자기가 본 형태로만 찍는다. 그대로 두면 bytesN 분기를 못 타고
**원문 str** 이 상수에 박힌다(`'"governance"'`). F14 와 같은 원리 — 리터럴엔 타입이 없고
문맥(선언)이 타입을 준다.

⚠ **bytesN 에만** 덮어쓸 것. `uint256` 으로 덮으면 `evaluate_literal_context` 가 `'uint256'` 을
모른다(`Unsupported literal expr_type 'uint256'`). 실측 확인.
`keccak256` 은 손대지 않는다 — 이미 `BytesSet.top(32)` 로 올바르게 평가된다(Evaluation.py:1485).

**근본 원인 (3) — 문자열 리터럴 → bytesN 인코딩 부재**: bytesN 분기가 숫자/16진만 처리하고
따옴표 리터럴은 `BytesSet.top()` 으로 떨어뜨렸다.

**수정**

```python
# (1)(2) process_constant_variable
_is_fixed_bytes = et.startswith("bytes") and len(et) > 5 and et[5:].isdigit()
if _is_fixed_bytes and getattr(init_expr, "context", None) == "LiteralExpContext":
    init_expr.expr_type = et

# (3) evaluate_literal_context, bytesN 분기
if len(lit) >= 2 and lit[0] in ("'", '"') and lit[-1] == lit[0]:
    body = lit[1:-1]
    if "\\" in body:                                # 이스케이프 → 틀린 싱글턴이 된다
        raise ValueError(...)
    raw = body.encode("utf-8")
    if len(raw) > byte_size:                        # 실제 solc 도 거부
        raise ValueError(...)
    return BytesSet(values={int.from_bytes(raw + bytes(byte_size - len(raw)), "big")},
                    byte_size=byte_size)
raise ValueError(...)   # hex".." / unicode".." 는 미구현 — ⊤ 로 덮지 않는다
```

**★ 건전성 검증 (이게 이 수정의 핵심)**

상수의 구체 값 집합은 **싱글턴**이므로 값이 정확하면 `BytesSet({v})` 가 가장 좁은 건전한
추상화다. 틀리면 **불건전**(잘못된 definite 판정)이므로 인코딩을 실증했다.

- 규칙: UTF-8 바이트를 **상위 바이트부터** 배치, 하위를 0 으로 채움(left-aligned = 오른쪽 0 패딩).
- 근거: `Dataset/Web3Bugs/S3_2/contest_145_H_02/registry_ReverseRegistrar.sol:12` (실제 ENS 코드)
  ```solidity
  bytes32 constant lookup = 0x3031323334353637383961626364656600000000000000000000000000000000;
  mstore8(i, byte(and(addr, 0xf), lookup))
  ```
  Yul `byte(n,x)` 는 MSB 부터 n 번째를 뽑으므로 이 인덱싱(0→'0', 15→'f')이 성립하려면
  ASCII 가 상위 바이트에 있어야 한다. 리포 내 32바이트 hex 상수 65개 전수 스캔으로 확보.
- **대조 결과**: 엔진이 계산한 `bytes32("0123456789abcdef")` 가 ENS 상수와 **비트 단위 일치**.
- 대상 19개 문자열 전수 검사: 이스케이프 0 · non-ASCII 0 · 길이 초과 0 (전부 pragma 0.8.9).
- 미모델링 형태(이스케이프 / `hex""` / `unicode""` / 길이 초과)는 **raise**. ⊤ 로 덮으면
  "정밀도만 잃는" 게 아니라 잘못된 경로를 믿게 된다. 현재 그 케이스들은 이미 오류라 현상 유지다.

**왜 ⊤ 로 두면 안 되나**: `BytesSet.equals` 는 `is_top` 이면 **무조건** `BoolInterval(0,1)`
(Unknown → Warning)을 낸다. 이 상수들의 실제 쓰임이
`require(hasRole(ROLE_ADMIN, msg.sender))` · `onlyRoles2(Roles.GOVERNANCE, ...)` ·
`currentUInts256[_KEEPER_REQUIRED_STAKED_BKD]`(**mapping key**) 이므로,
⊤ 이면 verdict 가 전부 Warning 이 되고 mapping 슬롯도 특정할 수 없다.
즉 이건 오류 건수가 아니라 **verdict 품질** 문제다.

**효과**: `[ERR]` 138 → **112**. `cannot be declared as constant` **24 → 0**.
AddressProviderKeys 9→0 · Roles 9→0 · ERC165Upgradeable 1→0 · LockeERC20 1→0 ·
ERC1155Upgradeable 6→3 · Controller 31→28. **증가한 파일 0개**, pkl 134, `[ANTLR]` 192 동일,
빈 함수 29 → 28. `temp/` 회귀 7/10/7 통과.

⚠ **범위**: `constant` 에 한정. 일반 state variable(`bytes32 nonconst = "plain"`)은 여전히
원문 str 을 갖는다 — **별건의 잠재 문제**로 남겨둔다(현재 오류 없이 동작 중이라
건드리면 값이 조용히 바뀐다).

⚠ **작업 중 사고 2건**
- 패치 문자열의 `\x00` escape 가 전송 중 뭉개져 소스에 **실제 NUL 바이트**가 들어갔다
  (`ast.parse` → `source code string cannot contain null bytes`). 생성 코드에는 백슬래시
  escape 를 쓰지 말 것 — `raw.ljust(n, b"\x00")` 대신 `raw + bytes(n - len(raw))` 처럼
  escape 없는 표현을 쓴다.
- 1차 시도를 되돌릴 때 `s.index("            et = ...")`(12칸)가 `process_state_variable` 안의
  **16칸 들여쓰기 줄의 부분문자열**에 먼저 매치돼 **84줄이 통째로 삭제**됐다
  (`process_constant_variable` 정의 자체가 소실). 앵커는 반드시 **줄 시작 포함 + 유일성 검증**으로
  잡을 것. 복구는 `git diff HEAD` 로 손상 훅(`@@ -814,90 +834,6 @@`)을 특정하고
  HEAD 해당 구간을 재삽입해서 했다.

---

## F17. 상속 체인을 1단계만 탐색 + intent 문법이 `ceil`/`floor` 를 예약어로 만듦 ★

**파일**: `Analyzer/ContractAnalyzer.py`(`_find_in_ancestors` 신규, `process_modifier_invocation`),
`Dependencies/main.py`(`_load_parent_pkls`),
소스 `Dependencies/libraries/PRBMath{SD59x18,UD60x18}.sol`
**Guardian 상태**: 미확인(같은 코드로 보임 — 포팅 전 확인).

**증상**: `No active function CFG` 계열 **40건**(Controller 20 · PRBMathSD59x18 18 · 기타 2).
원인이 **두 갈래**였다.

⚠ 먼저 확인한 것: **레코드 슬라이싱은 전부 의도대로였다.** 여러 줄 함수 시그니처
(Controller L18~23), 여러 줄 modifier 시그니처(AuthorizationBase L19~23), 여러 줄
`require(...)`(L24~27) 모두 한 레코드로 정확히 병합된다. 변환 단계 문제가 아니다.

---

### (A) 상속 체인 전이적 탐색 — Controller 20건

체인: `contract Controller is IController, Authorization, Preparable`
→ `contract Authorization is AuthorizationBase` → `modifier onlyGovernance` 는
**AuthorizationBase** 에 정의돼 있다.

두 군데가 얕았다:
- `ContractAnalyzer.process_modifier_invocation` 이 `parent_contracts` 를 **1단계만** 순회.
  `ContractCFG.get_function_cfg` 도 `self.functions` 만 보고 부모 체인을 타지 않는다.
- `Dependencies/main._load_parent_pkls` 는 docstring 에 **"(재귀)"** 라 써 있지만
  실제로는 소스의 `X is A, B, C` 를 한 번 파싱해 직계 부모만 로드했다.
  실측: Controller 분석 시 `contract_cfgs=['Authorization','IController','Preparable']`
  — **AuthorizationBase 없음**.

modifier 해석 실패는 **함수 정의 자체를 예외로 중단**시키므로, 그 함수 본문 전체가
"No active FunctionCFG" 로 연쇄 실패한다. `Controller` 의 등록 함수는 **0개**였다.

**수정**
```python
def _find_in_ancestors(self, ccf, name):
    """상속 체인 BFS. 조상 CFG 는 ccf.parent_cfgs(pkl 에 객체째 직렬화됨) +
       self.contract_cfgs 두 곳에서 얻는다."""
```
`con_Authorization.pkl` 이 `parent_cfgs['AuthorizationBase']` 를 **객체로 품고 있어서**
조회만 고쳐도 도달한다. `_load_parent_pkls` 재귀화는 `contract_cfgs` 를 직접 보는
다른 경로(타입 해석 등)를 위한 **독립적** 보완이다.

⚠ 탐색 순서는 **선언 순서**다. Solidity 의 C3 선형화는 뒤쪽 부모가 더 파생이라
(`is A, B` → B 우선) 엄밀히는 역순이어야 한다. 이 코퍼스엔 조상 간 이름 충돌이 없어
영향이 없지만, 다이아몬드 상속에선 잘못된 정의를 고를 수 있다 — **별건**.

**부수 확정**: `onlyGovernance` 의 CFG 는 **정상**이다 — nodes=7 +
`cond_expr: _roleManager().hasRole(Roles.GOVERNANCE, msg.sender)`.
`require` 가 조건 노드로 모델링되므로 `statements=0` 이 맞다.
→ **`check_pkl.py` 가 modifier 를 손상으로 오분류**하는 것이 확정됐다(판정 기준 교정 필요).

---

### (B) intent 문법이 `ceil`/`floor` 를 예약어로 만듦 — PRBMath 19건

```
[ANTLR] 1:9 no viable alternative at input 'functionceil'
L31  function ceil(int256 x) internal pure returns (int256 result) {
```

`Parser/Solidity.g4:323-324`
```antlr
| intentValue relOp 'ceil'  '(' intentValue ',' numberLiteral ')'   # Ceil
| intentValue relOp 'floor' '(' intentValue ',' numberLiteral ')'   # Floor
```

ANTLR 은 파서 규칙 안의 인라인 문자열 리터럴에 **암묵 토큰**을 만들고, 그 토큰은
`Identifier` 보다 **우선**한다. 결과적으로 `ceil`/`floor` 는 **모든 Solidity 소스에서
식별자로 쓸 수 없게** 됐다. IntentChecker 의 술어 문법이 일반 Solidity 파싱을 깨뜨린 것이다.

충돌 규모(리포 전체 `.sol` **3,984개** 스캔):

| 예약어 | 충돌 | 내역 |
|---|---:|---|
| `floor` | 24 | 멤버접근 11, 호출 6, function 이름 5, 변수 선언 2 |
| `ceil` | 9 | function 이름 4, 호출 4, 변수 선언 1 |
| `array` | 1 | 변수 선언 1 |
| 나머지 17개(`PercentOf` `changed` `returnExpression` `arg` `Before` `After` `Entry` `Exit` `Current` `Assign` `Unchanged` …) | **0** | — |

**채택한 해법 — 소스 rename (사용자 결정)**
`ceil` → `_ceil`, `floor` → `_floor`. **정의 4줄, 2파일**뿐이다:
`PRBMathSD59x18.sol:31,107` · `PRBMathUD60x18.sol:20,58`.
내부/외부 호출자 0곳, RQ1 케이스 JSON 영향 0건(`web3bugs_79_H_02.json` 132 레코드 중 사용 0).
`evaluation/RQ1/.../dependencies/` 사본은 **건드리지 않았다** — `Dependencies/main.py` 는
`Dependencies/{libraries,interfaces,contracts}/*.sol` 만 스캔하고, 루트 `main.load_dependencies()`
는 그 디렉토리를 `interface\s+(\w+)` **정규식 이름 수집에만** 쓴다(파싱하지 않음).

⚠ **문법은 고치지 않기로 했다(사용자 결정)** — intent 문법은 IntentChecker 논문에 실린
것이므로 변경하지 않는다. 즉 **도구 자체의 한계로 남는다**: 사용자가 에디터에
`function floor(...)` 를 입력하면 파싱이 깨진다. `from`(F9) 과는 성격이 다르다 —
`from` 은 Solidity 자체 예약어라 원본이 잘못이었지만, `ceil`/`floor` 는 **유효한 Solidity** 이고
우리 문법이 잘못이다. 소스 rename 은 증상 대응이지 근본 수정이 아니다.
(soft keyword 화 — `CEIL : 'ceil'; identifier : Identifier | CEIL | ...` — 는 언제든 가능하지만
**파서 재생성**이 필요하고 intent 문법 변경을 수반한다.)

---

**효과**: `[ERR]` 112 → **76**. `No active function CFG` 계열 **40 → 1**.
`[ANTLR]` 192 → **188**. **증가한 파일 0개**, pkl 134.
Controller 28→11 · PRBMathSD59x18 22→4 · PRBMathUD60x18 5→4.
본문 있는 함수 385 → **391**.

함수 등록 복구:
```
con_112_Controller.pkl   : 0개 → 8개 함수 (본문 있음 6)
lib_PRBMathSD59x18.pkl   : _ceil/_floor 포함 22개 (본문 있음 21)
lib_PRBMathUD60x18.pkl   : _ceil/_floor 포함 21개 (본문 있음 20)
```
`temp/` 회귀 7/10/7 통과.

⚠ **빈 함수 28 → 30 (+2)**: 회귀가 아니라 **함수가 6개 더 생겨서**다(385→391).
새로 등록된 Controller modifier 들이 `check_pkl.py` 의 (잘못된) 판정에 걸린 것이다.

⚠ **메시지 종류가 바뀐 것**: Controller 의 `may not be declared` 가 3→6 등으로 늘었는데,
전엔 함수 본문이 **아예 분석되지 않았기 때문**에 안 보이던 진짜 선언 문제가 이제 드러난 것이다.
파일 총계는 28→11 로 줄었고 증가한 파일은 0개다.

---

## F18. Phase 1(interfaces) 위상정렬 누락 + file-level enum 미수집 ★

**파일**: `Dependencies/main.py`(Phase 1, `scan_file_level_enums` 신규, Phase 0/주입),
`Analyzer/EnhancedSolidityVisitor.py`(타입 해석 체인)
**Guardian 상태**: 미확인(같은 코드로 보임 — 포팅 전 확인).

**증상**: `Type 'X' is not defined as struct, enum, or type alias` **17건**.
분해해보니 **네 갈래**였고, 그중 둘이 엔진 결함이다.

| 갈래 | 건수 | 성격 |
|---|---:|---|
| (A) 의존성 자산 누락 | 9 | `.sol` 이 `Dependencies/` 에 없음 — **엔진 무관** |
| (B) Phase 1 위상정렬 누락 | 2 | **F7 미완성** |
| (C) file-level enum 미수집 | 5 | 수집·주입·해석 3단 모두 없음 |
| (D) `Roles` 동명이인 | 1 | 레지스트리 키 충돌 — **별건** |

---

### (B) Phase 1 에만 위상정렬이 빠져 있었다 — 2건

```python
# 수정 전: Dependencies/main.py
ifc_files = sorted(IFC_DIR.rglob("*.sol"))       # ← 알파벳순
# Phase 2(libraries)/Phase 3(contracts) 는 _topo_order(...)   ← F7 이 여기만 고침
```

`IPooledCreditLine is IPooledCreditLineDeclarations is IPooledCreditLineEnums` 이고
`enum PooledCreditLineStatus` 는 맨 위 조상에 있다. 알파벳순은
`IPooledCreditLine` < `…Declarations` < `…Enums` — **의존 방향의 정확히 반대**다.

조상이 나중에 분석되면 부모 분석 시점에 조상 pkl 이 없어 `parent_cfgs` 가 **빈 채로**
저장된다. 실측(수정 전):
```
ifc_IPooledCreditLineEnums.pkl        enumDefs=['CancellationStatus','PooledCreditLineStatus']
ifc_IPooledCreditLineDeclarations.pkl parent_contracts=['IPooledCreditLineEnums'] parent_cfgs=[]
ifc_IPooledCreditLine.pkl             parent_contracts=['IPooledCreditLineDeclarations'] parent_cfgs=[]
```
`EnhancedSolidityVisitor._find_in_chain` 은 `parent_cfgs` 를 재귀로 도는 **올바른 코드가
이미 있었다** — 돌 것이 비어서 무용지물이었을 뿐이다.

**수정**: Phase 1 도 `_topo_order(ifc_files, "interfaces")`.
IFC_DIR 73개 전수 확인 결과 주 선언이 **모두 interface** 라 모드 불일치 위험이 없다.
정렬 결과: `IPooledCreditLineEnums`(40) → `Declarations`(69) → `IPooledCreditLine`(72).

**효과**: 부모가 있는 interface pkl **14개 중 0개 → 12개**의 `parent_cfgs` 가 채워졌다
(나머지 2개는 부모 `.sol` 자체가 없는 (A) 케이스).

---

### (C) file-level enum — 5건

`enum AssetClass {...}`(IMochiProfile.sol), `enum Status {...}`(IMochiVault.sol) 은
**파일 최상위 enum**(Solidity 0.8+ 허용)이다. 실측 `ifc_IMochiProfile.pkl`·
`ifc_IMochiVault.pkl` 의 `enumDefs=[]`.

`SolidityAnalyzer.file_level_enums` **필드도 있고 소비처도 있는데**
(`Evaluation.py:1090`, `Refine.py:190`) 세 단계가 모두 비어 있었다:

1. **수집 없음** — `Dependencies/main.py` Phase 0 은 `scan_type_aliases` /
   `scan_interface_names` / `scan_file_level_structs` 만 한다.
   루트 `main.py:98-102` 와 `engine_api.py:793` 은 regex 로 수집한다 — **pkl 생성 경로만 누락**.
2. **주입 없음** — `analyze_file` 의 주입부에도 빠져 있었다.
3. **타입 해석 분기 없음** — `EnhancedSolidityVisitor` 의 체인에 `file_level_structs` 분기는
   있는데(L699) `file_level_enums` 분기가 없다. `Evaluation.py:1090` 은 *식별자 평가*
   (`AssetClass.Stable`)에만 쓰고 *타입 선언*(`returns (AssetClass)`)엔 쓰지 않는다.

**수정**: `scan_file_level_enums`(brace-depth 0 스캔, 여러 줄 본문 지원) + 주입 + 해석 분기.

⚠ **typeCategory 만 세우면 안 된다** — 하류가 `ccf.enumDefs.get(enumTypeName)` 를 하고
없으면 `undefined enum` 으로 터진다(ContractAnalyzer:1277/1324/1427/1520).
그래서 해석 분기에서 `EnumDefinition` 을 만들어 `contract_cfg.enumDefs` 에 등록한다.
(검증: regen20 에서 `undefined enum` **0건** — 에러를 옮기기만 한 게 아니다.)

⚠ 기존 `scan_*` 3종은 `d.glob("*.sol")`(**비재귀**)라 `contracts/112/` 같은 하위 디렉토리를
놓친다. 새 함수는 `rglob` 을 쓴다 — 기존 3종의 비재귀는 **별건**으로 남긴다.

---

**효과**: `[ERR]` 76 → **69**. `not defined as struct/enum/alias` **17 → 10**
(해소 7 = B 2 + C 5, 남은 10 = A 9 + D 1 — 예상과 정확히 일치).
`undefined enum` 0건. **증가한 파일 0개**, pkl 134, `[ANTLR]` 188 동일, 본문 있는 함수 391 동일.
IMochiProfile 4→2 · IMochiVault 5→2 · IPooledCreditLine 1→0 · IPooledCreditLineDeclarations 1→0.
`temp/` 회귀 7/10/7 통과.

---

## F19. 타입 참조 pkl 로드 + 위상정렬에 타입 참조 반영 (도구)

**파일**: `Dependencies/main.py` — `_type_refs_in`·`_load_pkl_for`·`_load_type_ref_pkls` 신규,
`_topo_order` 의존 집합
**Guardian 상태**: 미확인.

**증상**: `contract RoleAware { Roles public immutable roles; ... }` 처럼 **상속하지 않고
타입으로만 쓰는** 컨트랙트가 해석되지 않음 → `Type 'Roles' is not defined...` 1건 +
`roles` 를 쓰는 4줄 연쇄 = 5건, `con_RoleAware.pkl` 의 함수 4개가 빈 채 저장.

**원인 두 겹**
- `_refs_in` 은 상속·라이브러리호출·using 만 본다 → 타입 참조가 의존으로 안 잡혀
  `RoleAware.sol`(13) 이 `contracts/Roles.sol`(14) 보다 **먼저** 분석된다.
- 분석된 contract CFG 는 다음 파일 분석에 주입되지 않는다(`_global_library_cfgs` 는
  library 만, `_load_parent_pkls` 는 `is` 절만). 인터페이스엔 `ca.interface_names`
  (전역 regex 수집)가 있지만 **contract 엔 그런 레지스트리가 없다.**

**수정**
```python
_typedecl_re / _typeret_re → _type_refs_in(src)   # 타입 위치의 대문자 이름만
_load_pkl_for(pname, ca)    # 후보가 **정확히 1개일 때만** 로드
_load_type_ref_pkls(source, ca)   # analyze_file 에서 _load_parent_pkls 뒤에 호출
refs[f] = _refs_in(src) | _type_refs_in(src)      # _topo_order 안에서만 합집합
```
- 후보 1개 제한: `Controller` 처럼 `con_112_Controller.pkl`/`con_45_Controller.pkl` 이
  공존하는 이름은 어느 프로젝트 것인지 알 수 없으므로 **조용히 아무거나 집지 않는다**.
- `_refs_in` 자체는 건드리지 않는다. 순환 위험을 3개 Phase 전수 검증함
  (interfaces 73 / libraries 32 / contracts 30 — 순환 없음, RoleAware 13→23).

⚠ **가드 함정**: `analyze_file` 이 `ca.contract_cfgs.update(_global_library_cfgs)` 로
라이브러리를 contract_cfgs 에도 넣는다(호환성). 그래서 `if pname in ca.contract_cfgs: continue`
로 막으면 **동명 라이브러리가 진짜 contract pkl 의 로드를 가로막는다.**
"이미 있는 것이 진짜 ContractCFG 일 때만" 건너뛰도록 해야 한다.

**효과**: 단독으로는 **0건**. 진짜 원인은 아래 F20 이었고, F20 을 고친 뒤에 이 배관이
비로소 동작한다. (F19 만으로 regen 이 변하지 않은 것이 F20 을 찾게 된 단서였다.)

---

## F20. `make_contract_cfg` 가 동명의 LibraryCFG 를 contract CFG 로 재사용 ★

**파일**: `Analyzer/StaticCFGFactory.py` — `make_contract_cfg`
**Guardian 상태**: 미확인(같은 코드로 보임 — 포팅 전 확인).

**증상**: `RoleAware.sol` 5건. F19 의 배관을 다 깔아도 변화가 없었다.

**근본 원인**
```python
def make_contract_cfg(an, contract_name) -> ContractCFG:
    if contract_name in an.contract_cfgs:
        return an.contract_cfgs[contract_name]      # ← 종류를 안 따지고 재사용
```
`analyze_file` 의 호환성 주입(`contract_cfgs.update(_global_library_cfgs)`)이
**다른 프로젝트의 동명 라이브러리**를 먼저 넣어두면, contract 의 CFG 를 만들 때
그 **LibraryCFG 를 그대로 돌려준다.** 그 뒤 contract 의 함수들이 LibraryCFG 안에 쌓이고
pkl 로 저장된다. 실측:
```
contracts/112/Roles.sol  = library Roles  (bytes32 상수, Backd)      순번 0
contracts/Roles.sol      = contract Roles (giveRole/getRole, MarginSwap) 순번 13
→ con_Roles.pkl : 타입 LibraryCFG / 내용은 contract 함수 4개
```
`ContractCFG` 와 `LibraryCFG` 는 **상속 관계 없는 형제 클래스**라, 이 잘못된 객체는
`isinstance(x, ContractCFG)` 검사를 모두 통과하지 못한다. 타입 해석 분기
`type_name in contract_cfgs and type_name not in library_cfgs` 가 계속 실패한 진짜 이유다.

**수정**
```python
_existing = an.contract_cfgs.get(contract_name)
if isinstance(_existing, ContractCFG):
    return _existing
cfg = ContractCFG(contract_name)   # LibraryCFG 등 다른 종류면 새로 만든다
```

**효과**: `[ERR]` 54 → **49**. `RoleAware.sol` **5 → 0**.
`con_Roles.pkl` 타입 LibraryCFG → **ContractCFG**.
본문 있는 함수 392 → **396**, 빈 함수 29 → **25**. 증가한 파일 0개.

⚠ **rename 은 불필요하다.** 처음엔 `Roles` 동명이인을 소스 rename 으로 풀려 했으나,
실측 결과 이름 충돌이 아니라 **객체 종류 검사 누락**이 원인이었다. 평가 자산을
건드리지 않고 해결된다.

---

## F21. 배열 원소 생성에서 중첩배열/mapping/enum 누락 + 리터럴 인덱스 우회 ★코어

**파일**: `Interpreter/Semantics/Evaluation.py` — 배열 인덱싱 3곳
**Guardian 상태**: 미확인(같은 코드로 보임 — 포팅 전 확인).

**증상**: `CommonLibrary.splitAmounts` **14건**이 한 줄에서 연쇄.
```solidity
function splitAmounts(uint256[] memory amounts, uint256[][] memory weights) ... {
    require(weights[i].length == n, "NV");   ← member 'length' is not a recognised global-member
```

**근본 원인**: 배열 원소를 만드는 **두 분기가 base 타입을 손으로 나열**하는데
`uint/int/bool/address/struct` 만 있고 **중첩배열·mapping·enum 이 빠져 있다.**
`uint256[][]` 의 `arrayBaseType.typeCategory == "array"` 라 마지막 `else` 로 떨어져
**문자열** `"symbolic_w[<unk>]"` 를 돌려주고, 거기에 `.length` 를 걸면 터진다.

세 번째 지점은 별개의 우회다 — **리터럴 인덱스 경로가 `get_or_create_element` 를 안 쓴다.**
길이 미상 파라미터(`uint256[][] memory w`)의 `w[0]` 이 auto-push 없이
`IndexError: Index 0 out of range` 로 터졌다.

**이미 올바른 구현이 있었다**: `Domain/Variable.py` 의
`_create_new_array_element` (중첩 ArrayVariable / MappingVariable / EnumVariable 생성) 와
그 래퍼 `_create_element_virtual`, 그리고 `get_or_create_element`(동적이면 auto-push).
`DebugInitializer` 는 이미 `isDynamicArray` 분기 + `get_or_create_element` 패턴을 쓰고,
`Evaluation.py:510` 도 `_create_element_virtual` 을 쓴다. **세 지점만 누락**돼 있었다.

접근 경로 일관성 (수정 전):
| 파일 | `get_or_create_element` | `.elements[idx]` 직접 |
|---|---:|---:|
| `DebugInitializer.py` | 3 | 3 — 항상 `isDynamicArray` 분기와 짝 ✅ |
| `Evaluation.py` | 1 | 6 |
| `Update.py` | 4 | 3 |

**수정**
```python
# (a) 확정 인덱스·요소 없음 / (b) 불확정 인덱스·빈 배열
elif base_t.typeCategory in ("array", "mapping", "enum"):
    return callerObject._create_element_virtual(idx)

# (c) 리터럴 인덱스
if callerObject.typeInfo.isDynamicArray:
    return callerObject.get_or_create_element(idx)   # 동적 → 확장
...범위 검사...                                       # 정적 → 그대로
```

**건전성**: 생성되는 원소 값은 `_create_default_value` 의 **⊤**
(address→`AddressSet.top()`, bool→`[0,1]`, int/uint→전범위). 길이 미상 배열의 원소를
⊤ 로 보는 것은 over-approximation 이라 건전하고, **문자열을 돌려주던 기존 동작보다
엄격하게 정확하다**(문자열은 추상값이 아니라 이후 연산이 전부 깨진다).
정적 배열의 범위 검사는 유지한다(실제 Solidity 도 컴파일 에러).
이미 요소가 있는 정상 경로(`elements[idx]` 반환)는 건드리지 않는다.

**효과**: `[ERR]` 49 → **35**. `CommonLibrary.sol` **14 → 0**. 증가한 파일 0개.
`temp/` 회귀 7/10/7 통과.

---

## 부수: 평가 자산 보강 (도구 아님)

**누락 인터페이스 9종 복사** — `Web3Bugs/contracts/` 에서 `Dependencies/interfaces/` 로.
`IVMochi` `IUSDM` `IFeePool` `ILiquidator`(42 mochi-core) · `IInflationManager`(112 backd) ·
`IVaultRegistry` `IVaultFactory`(58 mellow-vaults) · `IERC721` `IERC165`(OZ).
`IERC721` 은 `from` 파라미터 4곳을 `_from` 으로(F9 규칙).
→ `Type 'X' is not defined as struct/enum/alias` **17 → 1**, pkl 134 → 143.

⚠ **블록 주석이 슬라이서를 깨뜨린다**: OZ 파일의 NatSpec(`/** ... */`)이
`slice_solidity` 에서 **뒤따르는 선언과 한 레코드로 합쳐져**
`analyze_context` 의 `startswith('interface'/'event'/...)` 분류가 전부 빗나간다
(IERC721 = `[ERR]` 12 + `[ANTLR]` 25). 문법엔 `COMMENT : '/*' .*? '*/' -> channel(HIDDEN)`
이 있으므로 **파서가 아니라 슬라이서/분류기의 문제**다.
기존 Dependencies 144개 중 블록 주석이 있던 파일은 **복사한 3개뿐**이라 여태 안 드러났다.
지금은 그 3개에서 제거해 해결했으나, **사용자가 에디터에 NatSpec 을 치면 같은 문제가 난다.**

**전처리 툴킷 확보**: `SolidityGuardian/temp/` 에서 `IntentKeeper/tools/` 로 9개
(`preprocess_contraction.py` 8단계 파이프라인, `rename_reserved_identifiers.py`,
`generate_case_jsons.py`, `PROCESS_GUIDE{,_v2}.md` 등).
드라이런 결과 **기존 코퍼스는 이미 전처리를 거친 상태**였고(예약어 0 · bare scope 0),
잔여 2단계(enum 멤버 합치기 4파일 · single-line if 확장 1파일)를 적용했으나 오류 변화는 없었다.
`PROCESS_GUIDE_v2.md` 에 **"Dependencies/main.py pkl 생성 시 분석 순서"** 이슈가 이미
문서화돼 있었다 — F7/F18/F19 가 바로 그 항목이다.

---

## F22. 지역 struct/enum 선언이 정의를 붙이지 않음 (regen 기여 0, 그러나 실재하는 결함)

**파일**: `Analyzer/ContractAnalyzer.py` — `_create_variable_object` 2-B/2-C (+ 2-D 중복 제거)
**Guardian 상태**: 미확인.

**원인**: 같은 함수 안에서 2-A(배열)·2-D(매핑)는 `get_full_struct_enum_defs()` 로
정의를 넘겨 `_make_value` 가 초기화하는데, **2-B(struct)·2-C(enum) 만 아무것도 안 했다.**
```python
elif type_obj.typeCategory == "struct":
    v = StructVariable(identifier=var_name,
                       struct_type=type_obj.structTypeName, scope="local")   # 끝. 멤버 없음
```

**수정**: 2-B/2-C 도 `get_full_struct_enum_defs()` 로 정의를 얻어
`initialize_struct` / enum 멤버 테이블을 채운다. qualified(`Ticks.Tick`) 로 못 찾으면
bare(`Tick`) 로 한 번 더 조회한다(실측: `structDefs` 에 두 이름이 **둘 다** 있는 경우가 있다).
2-D 의 인라인 중복(정의 수집 로직)도 헬퍼로 교체.

⚠ **regen 기여 0건** (35 → 35, 증가·감소 모두 없음).
목표였던 `Ticks.sol` 은 `process_variable_declaration:1341` 이
```python
if isinstance(resolved, (StructVariable, ArrayVariable, MappingVariable)):
    v = VariableEnv.deep_clone_variable(resolved, var_name)   # 방금 만든 v 를 버림
```
로 **초기화식이 준 객체를 쓰기 때문**이었다(진짜 원인은 F23).
그래도 **초기화식이 없는** 지역 struct 선언(`Tick memory t;`)에는 이 수정이 필요하므로 남긴다.
"효과 0" 이라는 사실 자체가 F23 을 찾게 한 단서였다.

---

## F23. index-access 의 **멤버 접근 키**가 매핑 조회를 건너뜀 ★코어

**파일**: `Interpreter/Semantics/Evaluation.py` — `evaluate_member_access_context` 반환부 3곳
**Guardian 상태**: 미확인(같은 코드로 보임 — 포팅 전 확인).

**증상**: `Member 'X' not in struct 'X'` **6건** (Ticks 4 + AddressProviderMeta 2).
```solidity
Ticks.Tick storage current  = ticks[lower];                 // OK
Ticks.Tick storage previous = ticks[current.previousTick];  // ← 여기서 깨짐
previous.nextTick = current.nextTick;   // Member 'nextTick' not in struct 'previous'
```

**근본 원인**: `evaluate_index_access_context` 는 인덱스 접근을 **인덱스 식 평가에 위임**한다.
```python
base_val = self.evaluate_expression(expr.base, variables, None, "IndexAccessContext")  # 매핑
return self.evaluate_expression(expr.index, variables, base_val, "IndexAccessContext")
```
`callerObject=매핑` 을 넘겨 **인덱스 식 핸들러가 매핑 조회까지 마치도록** 설계돼 있다.
- 리터럴 키 → `evaluate_literal_context` 의 `isinstance(callerObject, MappingVariable)` 분기 ✅
- 식별자 키 → `evaluate_identifier_context` 의 매핑 분기 ✅
- **멤버 접근 키 → `evaluate_member_access_context` … 처리 없음** ❌

실행 추적으로 확인: `ticks[current.previousTick]` 평가 중 `get_or_create` 도
`_create_value_virtual` 도 **한 번도 호출되지 않고**, `evaluate_member_access_context` 가
`nested.value`(int24 구간)만 돌려주고 끝난다. 매핑은 버려진다.
그 값이 `resolved` 가 되어 `process_variable_declaration` 의
`isinstance(resolved, StructVariable)` 분기를 못 타므로 빈 struct 가 그대로 남는다.

**수정**: 이미 20곳 이상에서 쓰이는 헬퍼를 반환부 3곳에 붙인다.
```python
if isinstance(nested, EnumVariable):
    return self._mapping_lookup_if_needed(nested.value, callerObject)
if (isinstance(nested, Variables) and not isinstance(nested, (ArrayVariable, StructVariable, MappingVariable))):
    return self._mapping_lookup_if_needed(nested.value, callerObject)
return self._mapping_lookup_if_needed(nested, callerObject)
```
`_mapping_lookup_if_needed` 는
- `callerObject` 가 MappingVariable 이 **아니면 그대로 통과** → 기존 경로 무영향
- 맞으면 `struct_defs`/`enum_defs` 를 `get_full_struct_enum_defs()` 로 보충하고
  키(싱글턴이면 값, 아니면 심볼릭)로 `get_or_create` → `_make_value` 가 **정의가 붙은 struct** 생성

**효과**: `[ERR]` 35 → **31**. `Member not in struct` **6 → 2**.
`Ticks.sol` 7→3. ⚠ `AddressProviderMeta` 2건은 **그대로 남았다**
(첫 보고에서 상위 N개만 출력하는 집계에 가려 `0` 으로 잘못 적었던 것을 정정). 증가한 파일 0개, `[ANTLR]` 187 동일,
본문 있는 함수 396 동일. `temp/` 회귀 7/10/7 통과.
검증: `previous` 가 `structTypeName='Tick'`, `members=['previousTick','nextTick','liquidity']` 로 정상화.

★ **F16·F21·F22 와 같은 패턴이 네 번째다** — 올바른 구현이 이미 도메인/헬퍼에 있는데
특정 경로에서만 그것을 쓰지 않는다. 남은 오류를 볼 때 **"이 경로가 기존 헬퍼를 쓰고 있나"**
를 먼저 확인하는 것이 빠르다.

⚠ 비싱글턴 키는 `_mapping_lookup_if_needed` 의 기존 규약대로 `func_result_{id(result)}`
심볼릭 키를 쓴다(id 기반이라 재현성이 없다). 기존 20여 곳과 동일한 동작이므로 그대로 뒀으나,
**키 명명 규약은 별도로 볼 가치가 있다**.

---

## F24. 존재하지 않는 컨텍스트 문자열 `IndexAccessExpContext` ★코어 · 조용한 오분석

**파일**: `Interpreter/Semantics/Update.py`(1곳), `Interpreter/Semantics/Refine.py`(2곳)
**Guardian 상태**: 미확인(같은 코드로 보임 — 포팅 전 확인).

**증상**: `Cannot resolve mapping key from expression` 3건(Ticks).
같은 모양인데 어떤 줄은 되고 어떤 줄은 안 됐다 —
`ticks[lower].liquidity = ...`(L66) OK / `ticks[upper].liquidity = ...`(L85) 실패.

**근본 원인**: 문법 라벨은 `# IndexAccess`(Solidity.g4:596) 이므로 생성 클래스는
**`IndexAccessContext` 하나뿐**이다. `IndexAccessExpContext` 는 어디에도 없다.
(비슷한 라벨이 더 있어 혼동하기 쉽다: `# IntentIndexAccess`(L385, intent 절),
 `# IReturnIndexAccess`(L296, @IReturn). visitor 도 셋을 구분해 문자열을 만든다.)

따라서 `Update.py:327` 의 키 추출 블록이 **한 번도 실행된 적이 없다**:
```python
if getattr(base_exp, "context", "") == "IndexAccessExpContext":   # 항상 False
    ...  # 식별자/리터럴/멤버접근 키 추출 — 전부 죽은 코드
```
매핑 쓰기는 오직 그 아래 폴백으로만 동작하고 있었다:
```python
# ② 매핑에 엔트리 하나뿐이면 그걸 그대로 사용
if key is None and len(base_obj.mapping) == 1:
    key, _ = next(iter(base_obj.mapping.items()))
```
L66 은 그 시점에 엔트리가 1개라 **우연히** 맞았고, L85 는 엔트리가 늘어 실패한 것이다.

⚠ **오류 3건보다 이쪽이 훨씬 위험하다**: 폴백이 성공할 때도 **키를 검증하지 않고
있는 유일한 엔트리를 집는다.** `ticks[A]` 에 쓰는 코드가 실제로는 `ticks[B]` 를
**조용히** 수정할 수 있었다.

`Refine.py` 의 두 곳도 같은 오타이고, 그건 "심볼릭 인덱스면 refine 을 건너뛴다" 는
**건전성 가드**였다(코드 주석은 `IndexAccessContext` 라고 올바르게 적혀 있다).

**수정**: 세 곳의 `"IndexAccessExpContext"` → `"IndexAccessContext"`.

**효과**: `[ERR]` 31 → **28**. `Cannot resolve mapping key` **3 → 0**, `Ticks.sol` **3 → 0**
(이 파일은 이제 오류 0). 증가한 파일 0개, `[ANTLR]` 187 동일, 회귀 7/10/7 통과.

⚠ **남은 과제**: 폴백 ②(`엔트리 하나면 그걸 사용`)는 오타를 고친 지금도 남아 있다.
CLAUDE.md 의 fail-loud 방침에 어긋나므로 **도달 빈도를 측정한 뒤 제거를 검토**해야 한다.
또 intent 쪽 인덱스 접근(`IntentIndexAccess`)은 `Update`/`Refine` 의 이 블록에 여전히
걸리지 않는다 — `DebugInitializer` 는 둘을 함께 처리하므로, 의도된 분리인지 확인이 필요하다.

---

## F25. 전처리에 '빈 블록 `{ }` 확장' 단계가 없었다 (도구, 부분 해소)

**파일**: `tools/preprocess_contraction.py`(`_expand_empty_block` 신규) + 소스 8곳
**Guardian 상태**: ❗원본(`SolidityGuardian/temp/preprocess_contraction.py`)에도 없다.

**증상**: `Unsupported expression context in interactiveExpressionStatement` 중 3건 —
OZ upgradeable 관용구인 storage gap 이 **함수 바로 뒤**에 올 때.
```solidity
function _beforeTokenTransfer(...) internal virtual { }   // ← 한 줄 빈 본문
...
uint256[44] private __gap;                                 // ctx=simpleStatement 로 오분류
```

**근본 원인**: `find_function_context` 는 위로 거슬러 올라가며
"닫힌 만큼 상쇄하고 남은 첫 `{`" 를 찾는데, **한 줄에 `{` 와 `}` 가 같이 있으면**
`open > 0` 인 순간 곧바로 `break` 하고 같은 줄의 `close` 를 무시한다.
→ **이미 닫힌 함수**를 "열려 있다" 고 착각하고, 뒤따르는 상태변수를 함수 내부 문장으로 분류한다.
(실측: 7개 대상 중 틀리는 3건이 정확히 오류 3건과 일치. 나머지 4건은 `{`/`}` 가 다른 줄이라 정상.)

**수정(우회)**: 전처리의 `expand_single_line_blocks` 에 빈 블록 확장 분기 추가.
```python
RE_SINGLE_EMPTY = re.compile(r'^(\s*)(?!\s*\})(?P<head>[^{}]*\{)\s*\}\s*$')
RE_TYPE_DECL    = re.compile(r'^\s*(?:abstract\s+)?(?:interface|contract|library)')
```
★ **`} else {` / `} else if (...) {` / `} catch ... {` 는 절대 제외**한다 — 저건 `}` 가 먼저 와서
**이전 블록을 닫는** 것이고 슬라이서의 `closeBefore` 메커니즘이 전담한다(앞의 `}` 를 떼어
`closeBefore=True` 로 표시). 건드리면 블록 join 이 깨진다. `(?!\s*\})` 로 명시 배제.
★ `interface X is Y {}` / `contract X {}` 도 제외 — 슬라이서가 `{` 로 끝나는 헤더에 **가짜 `}`** 를
붙여 2줄 블록으로 만들기 때문에 실제 `}` 와 충돌할 수 있고, 현재 `_empty_blk` 분기로 정상 처리된다.
드라이런으로 확장 대상 10건 / 제외 101건(`}` 선행)을 전수 확인한 뒤 적용했다.

**효과**: `[ERR]` 28 → **26**, `[ANTLR]` 187 → **183**.
`45/Controller` 4→3, `ERC20Upgradeable` 1→0. 증가한 파일 0개, 회귀 7/10/7 통과.

⚠ **부분 해소(3건 중 2건)**. 남은 1건 `ERC1155Upgradeable.sol:156` 은 직전 함수가
**여러 줄 시그니처 + `{` 단독 줄**(`safeBatchTransferFrom`) 이라 형태가 다르다.

⚠ **엔진 결함은 그대로다**. 사용자가 에디터에 `function f() {}` 를 입력하면 여전히 깨진다.
근본 수정은 `find_function_context` 의 괄호 상쇄를 **순증감**으로 바꾸는 것:
```python
net = open_braces - close_braces
if net > 0: open_brace_line = line; break
close_brace_count += (-net)
```
`{ }` 한 줄은 `net == 0` 이라 지나가고, `} else {` 도 `net == 0` 이라 올바르다.
단 **라인 좌표계 핵심부**이고 `find_function_context` 호출부가 6곳이라 신중히 가야 한다.
선행 확인 필요: `line_info` 의 `open`/`close` 가 **문자열 리터럴·주석 안의 중괄호**를 세는지.

⚠ **작업 중 범위 초과**: `expand_single_line_blocks()` 를 통째로 호출해 기존
`if`/`unchecked` 확장 단계까지 같이 돌았고, 승인 범위 밖인 RQ1 자산 **12개 파일**
(Babylonian/BitMath/Fixed18/FixedPoint/UFixed18/solmate_ERC20 + `original/` 사본,
90 insertions)이 변형됐다 → `git checkout` 으로 원복. 전처리는 **필요한 단계만 직접 호출**할 것.

---

## F7. 의존성 분석 순서 하드코딩 → 위상정렬 (도구)

**파일**: `Dependencies/main.py`
**Guardian 상태**: ❗**동일** — Phase 2 `_late = {Fixed18, FixedPoint, LibPerpetuals}`,
Phase 3 `_con_order` 수동 목록

**증상**: `[ERR] ctx=simpleStatement: This 'UnsafeMath' is may be array or struct but may not be declared`
— `DyDxMath` 9건. 알파벳순이라 `DyDxMath`(D) 가 `FullMath`(F)/`UnsafeMath`(U) **보다 먼저** 분석돼
라이브러리 CFG 가 아직 주입되지 않은 상태에서 호출을 해소하려다 실패한다.

**근본 문제**: `_con_order` 하드코딩은 "저자가 손으로 정렬한 컨트랙트에서만 동작" 을 뜻한다.
데이터셋이 늘 때마다 손으로 유지할 수 없다.

**수정**: 소스에서 상속(`X is A, B`)·라이브러리 호출(`A.f()`)·`using A for` 를 추출해 DAG 구성 →
위상정렬. 같은 층위는 경로순으로 고정(재현성). **순환 시 폴백 없이 예외.**
헬퍼: `_decl_re`, `_libcall_re`, `_using_re`, `_strip_comments`, `_declared_in`, `_refs_in`,
`_topo_order`, `_primary_decl`.

**효과**: `DyDxMath` 9 → 0.

---

## F8. pkl 이름/모드를 "새로 생긴 CFG 중 첫 번째" 로 정함 (도구)

**파일**: `Dependencies/main.py` `analyze_file` 의 3개 저장 블록
**Guardian 상태**: ❗**동일** — `new_libs[0]` / `new_ifcs[0]` / `new_cons[0]`

**증상**: F7 로 순서를 바로잡자 `SafeTransferLib.sol` 이
`con_ERC20.pkl (0 functions)` 로 저장되는 **회귀**가 드러났다.
`new_libs[0]` 방식이 **분석 순서에 따라 결과가 바뀌는** 잠재 버그였고 순서 변경이 그걸 노출했다.

**수정 = 주 선언(primary declaration) 기준.** 135개 파일 전수 조사 결과에 근거한 규칙:
1. 최상위 선언이 **하나면** 그것이 주 선언
   (파일명과 달라도 됨: `Fixed18.sol`→`Fixed18Lib`, `LibPerpetuals.sol`→`Perpetuals`,
   `UFixed18.sol`→`UFixed18Lib`, `78_OZ_ERC20.sol`→`ERC20`, `solmate_ERC20.sol`→`ERC20` — 5건)
2. 여러 개면 **파일명(stem)과 일치하는 것**
   (해당 사례는 `SafeTransferLib.sol` = `[contract ERC20, library SafeTransferLib]` **단 1건**)
3. 그래도 못 정하면 **예외** — 폴백해서 엉뚱한 선언을 고르지 않는다

같은 원리로 `_topo_order` 의 모드 판정과 `by_name` 인덱스도 주 선언 기준으로 한다
(보조 선언 = `SafeTransferLib.sol` 안의 `contract ERC20` 스텁은 실제 정의처가 아니다).

---

## F9. 소스 수정: `from` 은 Solidity 예약어

**파일**: 의존성 `.sol` 소스
**Guardian 상태**: ❗**동일 파일들에 존재**(IntentKeeper 가 Guardian 에서 복사해온 것)

`from` 이 파라미터/이벤트 인자 이름으로 쓰이면 파싱이 깨진다(`[ANTLR] mismatched input 'from'`).
이 리포의 관례대로 `_from` 으로 바꾼다.

| 파일 | 라인 |
|---|---|
| `Dependencies/libraries/SafeTransferLib.sol` | 25, 34 |
| `Dependencies/interfaces/5/iERC20.sol` | 17 |
| `Dependencies/interfaces/IBentoBoxMinimal.sol` | 14, 22 |
| `Dependencies/interfaces/IBentoBoxV1.sol` | 8 |
| `Dependencies/interfaces/IERC20.sol` | 4, 12 |

⚠ **문자열 리터럴 안의 `from` 은 건드리면 안 된다**
(`78_OZ_ERC20.sol` L44/50/69, `ERC1155Upgradeable.sol` L89 — `"ERC20: transfer from the zero address"`).

**효과**: `[ANTLR]` 212 → 192.

---

## 부수 도구

### `Dependencies/check_pkl.py` (신규)

pkl 건강검진. 모든 pkl 을 로드해 **본문이 빈 채 저장된 함수**를 보고한다.
재생성 로그의 `[ERR]` 는 *파싱/평가* 실패만 잡으므로, 결과물 쪽에서 한 번 더 확인한다.

⚠ 현재 판정 기준이 거칠다 — OpenZeppelin 훅(`_beforeTokenTransfer` 등 소스에서도 `{}`)과
modifier 를 "손상" 으로 오분류한다. **소스 본문과 대조하도록 개선 필요**(미적용).

---

## 아직 안 고친 것 (IntentKeeper 기준 잔여 26건 — regen30)

| 메시지 | 건수 | 주요 파일 |
|---|---:|---|
| `Unable to find contract CFG for None` | 4 | IMochiProfile 2, IMochiVault 2 |
| `Unsupported expression context in interactiveExpre` | 4 | Float 3, ERC1155Upgradeable 1 |
| `'X' object has no attribute 'X'` | 3 | PRBMathSD59x18 1, PRBMathUD60x18 1, Controller 1 |
| `Qualified type 'X': 'X' not found in library 'X'.` | 2 | ILiquidityBasedTWAP 1, IAddressProvider 1 |
| `This 'X' is may be elementary variable but may not` | 2 | Float 1, ERC1155Upgradeable 1 |
| `No CFG node found after line 251 (searched up to l` | 2 | PRBMathSD59x18 2 |
| `No CFG node found after line 194 (searched up to l` | 2 | PRBMathUD60x18 2 |
| `Member 'X' not in struct 'X'` | 2 | AddressProviderMeta 2 |
| `No CFG node found after line 250 (searched up to l` | 1 | PRBMathSD59x18 1 |
| `No CFG node found after line 193 (searched up to l` | 1 | PRBMathUD60x18 1 |
| `Unsupported compound-assignment operator: None` | 1 | Controller 1 |
| `Argument count mismatch in function call to 'X': e` | 1 | Controller 1 |
| `No active function CFG.` | 1 | ERC1155Upgradeable 1 |

**파일별**: Float 4 · PRBMathSD59x18 4 · PRBMathUD60x18 4 · Controller 3 · ERC1155Upgradeable 3 · IMochiProfile 2 · IMochiVault 2 · AddressProviderMeta 2 · ILiquidityBasedTWAP 1 · IAddressProvider 1

**해소 이력**: 552 → 246(F3~F6) → 224(F10) → 212(F11,F12) → 198(F13) → 197(F14)
→ 138(F15) → 112(F16) → 76(F17) → 69(F18) → 54(자산 보강) → 49(F20) → 35(F21)
→ 35(F22, 기여 0) → 31(F23) → 28(F24) → **26**(F25).  **−95%**

### 알려진 별건 (백로그)

**① custom error 미구현** (문법 `*` 누락 + visitor 스텁 + ctx 분류 누락)
- `Parser/Solidity.g4:131` 의 `(errorParameter (',' errorParameter))?` 에 반복 `*` 누락 →
  **파라미터 0개 또는 정확히 2개만** 파싱. `eventDefinition`(L173)은 정상.
  같은 누락이 `assemblyFlagString`(L500)에도 있다. **파서 재생성 필요**.
- `visitErrorDefinition` 이 빈 스텁 → `visitBasicType(ctx, type_obj)` 에서 `TypeError`.
- `analyze_context` 의 contract/library 분기에 `error` 없음 → `stateVariableDeclaration` 오분류.
- 등록 자체는 불필요(`revert Foo(a,b)` 는 이미 동작).
- 규모: 선언 106건 중 19건 파싱 실패. **`Dependencies/` 안은 0건**.

**② 블록 주석이 슬라이서/분류기를 깨뜨린다 ★신규**
`/** ... */` NatSpec 이 뒤따르는 선언과 한 레코드로 합쳐져
`analyze_context` 의 `startswith(...)` 분류가 전부 빗나간다(IERC721 실측: `[ERR]` 12 + `[ANTLR]` 25).
문법엔 `COMMENT : '/*' .*? '*/' -> channel(HIDDEN)` 이 있으므로 **파서가 아니라 슬라이서 문제**다.
`Dependencies/` 에서는 해당 3파일의 주석을 지워 우회했지만,
**사용자가 에디터에 NatSpec 을 입력하면 같은 문제가 난다** — 도구 결함으로 남아 있다.
수정 후보: (a) `analyze_context`/`determine_top_level_context` 가 **주석을 제거한 사본**으로
분류하고 파싱은 원문으로(ANTLR 이 HIDDEN 처리) — 최소 변경 · (b) 슬라이서에서 제거.

**③ intent 문법의 `ceil`/`floor`/`array` 예약** — F17(B). 소스 rename 으로 우회.
**문법은 불변**(사용자 결정: IntentChecker 논문 제출본).

**④ C3 선형화 미준수** — 조상 탐색이 선언 순서. Solidity 는 `is A, B` 에서 B 가 더 파생.

**⑤ `check_pkl.py` 판정 기준 오류 (확정)** — `require` 만 있는 modifier 는 조건 노드로
모델링되어 `statements=0` 이 **정상**인데 손상으로 오분류한다(실측: `onlyGovernance` 는
nodes=7 + `cond_expr` 정상). 판정을 "소스에 본문이 있는데 statements=0" 으로 바꿔야 한다.

**⑥ Yul 커버리지** — `switch`/`case`, `returndatacopy`, `revert`, `success :=` 에서 `[ANTLR]`.
PRBMath* 두 파일이 `[ANTLR]` 157건(전체 187 중)을 차지한다.
`_BINARY_OPS` 가 `sgt`→`>`, `sdiv`→`/`, `sar`→`>>` 로 **signed 를 뭉갠다**.

**⑦ `scan_*` 3종이 비재귀** — `scan_type_aliases`/`scan_interface_names`/
`scan_file_level_structs` 가 `d.glob("*.sol")` 라 `contracts/112/`·`interfaces/5/` 를 놓친다.
`scan_file_level_enums`(신규)만 `rglob`.

**⑧ 기타**
- `Evaluation._literal_is_address` 에 길이 검사 없음.
- 일반 state variable 의 `bytes32 x = "plain"` 은 여전히 **원문 str**(F16 은 `constant` 한정).
- `_load_parent_pkls` 의 pkl 로드가 `except Exception: pass` — 실패가 조용히 묻힌다.
- 배열 읽기 경로에 `.elements[idx]` 직접 접근이 아직 `Evaluation` 4곳 / `Update` 3곳 남아 있다
  (F21 에서 3곳만 정리). `DebugInitializer` 의 `isDynamicArray` 분기 패턴으로 통일 검토.

