# 엔진 오류 케이스 상세 (2026-10-20)

대상: 새 RQ3 검증 48 재실행(`run_cases.py`, `results_before.json`/`results_after.json`)에서 **결과가 없거나 IntentChecker 와
다르게 나온 오류 케이스 5건**. 아직 **아무것도 고치지 않았다** — 아래 "수정안" 은 검토용이다.

- 줄 번호 = 케이스 레코드를 엔진의 삽입 규칙(`SolidityAnalyzer._insert_lines`: span 만큼 밀고 코드는 span 끝에 쓰기,
  closeBefore 는 앞 `}` 줄 재사용)대로 재생한 **최종 소스의 줄 번호**. 재생기 = `check_case_records.py --dump <case>`.
- "레코드 원래 줄" 은 JSON 의 `startLine`(삽입 시점 좌표)이라 최종 줄과 다를 수 있다.
- 근본 원인과 "패치 시 결과" 는 스크래치 monkeypatch 로 재현·해소까지 확인한 것(저장소 무수정, `scratchpad/agentErr/`).
  ⓥ = 내가 직접 다시 확인, ⓐ = 에이전트가 재현·검증.

---

## 0. 케이스 JSON 줄 번호 정합성 — 48 전수 검사

`.venv/Scripts/python.exe evaluation/intent_validation/check_case_records.py`

| 케이스 | 문제 | 판정 |
|---|---|---|
| **web3bugs_16_H_04** | rec#37 `} else if (trade.side == Perpetuals.Side.Short) {` 가 **옛 슬라이서 형식**(앞 `}` 를 떼고 closeBefore 를 붙이지 않음). 재생하면 최종 소스 끝에 `}` 가 하나 남는다(중괄호 깊이 −1, 67행) | **실제 결함** ⓥ |
| **web3bugs_36_H_02** | `@Post` 레코드가 `startLine 58` 로 들어가는데, 그 시점 함수/컨트랙트는 52–53행에서 끝나 있어 **53–57행 빈칸을 건너뛰고 컨트랙트 밖**에 놓인다. 디버그 배치(47행 삽입)가 뒤에 들어오면서 최종 69행, 컨트랙트 닫힘(64행) 뒤 | **실제 결함** ⓥ — @Post 의 줄 번호를 "최종 파일 좌표"로 적어 둔 것으로 보임 |
| **web3bugs_47_H_02** | 같은 유형: `@Post _allowances[sender][msg.sender] == 900` 가 최종 41행, 컨트랙트 닫힘(38행) 뒤. 또 디버그 배치가 최종 소스에서 `END`(30행) → `BEGIN`(31행) 순서로 뒤집혀 놓인다(같은 줄에 순차 삽입). 드라이버는 레코드 **순서**로 배치를 처리하므로 배치 동작은 정상 | **실제 결함** ⓥ (판정은 Violated 로 기대와 일치 — 엔진이 밖에 놓인 @Post 를 어떻게 함수에 붙이는지는 별도 확인 필요) |
| numscout_WANGMI | `else if` 가 `}` 줄을 덮어쓰지 않고 4줄 아래에 놓이는 레코드를 검사기가 이중 닫힘으로 셈 | **검사기 오탐**(엔진은 closeBefore 로 처리) |

나머지 44개는 줄 수·덮어쓰기·중괄호 균형·어노테이션 위치(타깃 함수 본문 안) 모두 정상.

---

## 1. web3bugs_78_H_02 — `AttributeError: 'NoneType' object has no attribute 'is_bottom'`

- **타깃**: `RebaseProxy.mint(address to, uint256 amount)` (최종 18–32행), intent `@Post _balances[to] <= amount` (31행)
- **입력**: `_totalSupply=1e21`, `_balances[to]=0`, `to=symbolicAddress 10`, `amount=5e20`, `@IReturn IERC20(baseToken).balanceOf()=1.5e21`
- **오류 위치** ⓥ: 26행 `uint256 _redeemRate = redeemRate();` → 내부 호출 `redeemRate()` 의 **11행**
  `return (balanceOfBase * ONE) / totalSupply();` 에서 나눗셈의 오른쪽 `totalSupply()` 가 `None`.
  `Interval.divide` → `_bottom_propagate`(Domain/Interval.py:30) 가 `None.is_bottom()` 호출.
- **케이스 JSON**: 정상 ⓥ (줄 수·위치 문제 없음). 단, 디버그 입력이 OZ ERC20 의 `_totalSupply`/`_balances` 를 전제한다.
- **로직** ⓐ:
  1. `RebaseProxy is ERC20, TokenProxyLike`. 실제 contest 코드의 ERC20 은 **OpenZeppelin**(forge 프로젝트 w78 도 OZ 로 컴파일됨).
  2. 그런데 엔진이 로드한 `ERC20` CFG 는 **solmate** 판이다(`uint256 public totalSupply` 상태변수, `totalSupply()` 함수 없음).
  3. `Dependencies/contracts/78_OZ_ERC20.sol` 와 `solmate_ERC20.sol` 이 둘 다 `contract ERC20` 이라 **같은 `con_ERC20.pkl` 로 저장되고
     나중 것이 경고 없이 덮어쓴다**(Dependencies/main.py:814). `main.load_dependencies`(main.py:66-78)는 숫자 접두어까지 떼므로
     `con_51_ERC20` 도 같은 키에 가려진다.
  4. 그래서 `find_function_in_hierarchy`(Evaluation.py:662)가 `totalSupply` 를 ERC20 에서 못 찾고 `TokenProxyLike → IERC20` 의
     **본문 없는 interface 선언**을 찾는다 → 그래프가 ENTRY/EXIT 뿐 → `_run_worklist` 결과 없음 → `Engine._extract_return_value`
     (Engine.py:1186) 가 `None` 반환.
  5. 부가: 엔진은 `public` 상태변수의 자동 getter 를 지원하지 않으므로 solmate 판이 맞았더라도 `totalSupply()` 는 못 풀린다.
- **패치 시 결과** ⓐ: OZ ERC20 CFG 로 바꿔 넣으면 `@Post` **Violated** (IntentChecker 와 일치).
- **수정안**:
  - (a) pkl 저장 시 같은 이름이 이번 실행에서 이미 쓰였으면 **예외**(무경고 덮어쓰기 금지).
  - (b) 의존성 pkl 을 **프로젝트(contest) 단위 이름공간**으로 만들고 케이스는 자기 프로젝트 pkl 만 로드 — 의존성 19건(A 부류) 해결안과 같은 작업.
  - (c) 부수: 본문 없는 선언으로 해석되는 내부 호출은 `None` 대신 예외.
- **영향**: ERC20 처럼 이름이 겹치는 모든 케이스의 해석 대상 CFG 가 바뀐다 → 전체 재실행 필요.

---

## 2. web3bugs_52_H_23 — `AttributeError: 'str' object has no attribute 'multiply'` (⊤ 변경 후에만)

- **타깃**: `VaderPoolV2.mintSynth(IERC20 foreignAsset, uint256 nativeDeposit, address _from, address to)` (최종 95–134행),
  intent `@During _update.arg[2] == reserveForeign - amountSynth` (124행)
- **입력**: `foreignAsset=sym1`, `nativeDeposit=100000`, `_from=sym2`, `to=sym3`, `supported[foreignAsset]=true`,
  `pairInfo[foreignAsset].reserveNative=100000`, `pairInfo[foreignAsset].reserveForeign=1`, `nativeAsset=sym4`
  (**`block.timestamp`, `pair.blockTimestampLast` 는 미지정**)
- **오류 위치** ⓥ: `mintSynth` → 내부 호출 `_update(...)`(57–79행)의 **72행**
  `pair.priceCumulative.nativeLast += uint256( UQ112x112.encode(reserveForeign).uqdiv(reserveNative) ) * timeElapsed;`
- **케이스 JSON**: 줄 번호는 정상 ⓥ. 그러나 **내용 결함**: 원본 부모 `BasePoolV2.sol:54` 의 `using UQ112x112 for uint224;` 가
  케이스(평탄화된 contraction)에 **없다** ⓥ — 즉 케이스 코드는 그대로는 컴파일되지 않는다.
- **로직** ⓐ:
  1. `UQ112x112.encode(reserveForeign)` → uint224 interval.
  2. 그 값의 멤버 `.uqdiv(...)` 를 찾는데 `using UQ112x112 for uint224` 가 없어 라이브러리 바인딩 실패 →
     Evaluation.py:1915 가 **`"symbolic(<값>.uqdiv)"` 문자열**을 돌려준다(조용한 실패).
  3. `uint256(문자열)` 도 문자열 그대로 → `문자열 * timeElapsed` 에서 Evaluation.py:2303 `leftInterval.multiply` 크래시.
- **왜 ⊤ 변경 후에만** ⓐ: 예전엔 `block.timestamp=[0,0]` 이라 `timeElapsed = 0 - blockTimestampLast(0) = 0` →
  67행 `if (timeElapsed > 0 && …)` 가 불가능 → 72행이 실제로 평가되지 않았다. ⊤ 가 되면서 분기가 열려 결함이 드러났다.
  (`block.timestamp` 만 [0,0] 으로 되돌리면 예전 Warning 이 그대로 나옴을 확인.)
- **패치 시 결과** ⓐ: `using UQ112x112 for uint224` 를 등록하면 **Warning** (IntentChecker 와 일치).
- **수정안**:
  - (a) **케이스 데이터**: 누락된 `using` 줄 추가 — 케이스 파일 수정이라 승인 필요. (또는 자동 contraction + 프로젝트 pkl 경로로
    전환하면 부모의 `using` 이 그대로 들어온다.)
  - (b) **엔진**: Evaluation.py:1915 의 문자열 반환을 예외로("unresolved member … missing using-for?") — 폴백 제거.
  - (c) **잠복 버그**: Evaluation.py:1459 `getattr(baseVal, 'bits', 256)` → interval 은 `type_length` 를 쓰므로 항상 256 이 된다.
- **영향**: (b) 는 다른 곳에서 조용히 문자열로 새던 경우를 예외로 드러낸다(의도된 것).

---

## 3. web3bugs_16_H_04 — 결과 없음 (ANTLR 파싱 오류 1)

- **타깃**: `applyTrade(Position memory position, Trade memory trade, uint256 feeRate)` (library, 최종 37–65행),
  intent `@During` (56행, `newQuote = position.quote - quoteChange + fee;` 에 인라인)
- **입력**: `feeRate=1e16`, `trade.side=0`, `trade.amount=1e19`, `trade.price=2e18`, `position.quote=1e21`, `position.base=0`
- **오류 ①(파싱)** ⓥⓐ: rec#37 `"} else if (trade.side == Perpetuals.Side.Short) {\n}"` — 옛 형식(앞 `}` 포함, closeBefore 없음).
  현재 슬라이서(Dependencies/main.py:193-202)는 `}` 를 떼고 `closeBefore=True` 를 붙인다. 옛 형식이면
  `get_current_context_type` 가 None → 파서가 1:0 의 `}` 에서 실패. **48 중 이 파일 하나뿐.**
- **오류 ②(해석, 엔진 버그 A)** ⓐ: 레코드를 고쳐도 결과가 없다. 48행
  `int256 quoteChange = PRBMathSD59x18.mul(signedAmount, signedPrice);` 이후 환경이 **⊥** 가 되어 56행 `@During` 노드가
  평가되지 않는다. 원인은 아래 **§A**.
- **케이스 JSON**: **결함** (rec#37 옛 형식) ⓥ
- **패치 시 결과** ⓐ: §A 패치만으로(원래 레코드든 고친 레코드든) **Warning** (IntentChecker 와 일치).
- **수정안**: (a) 현재 슬라이서로 케이스 재생성(승인 필요), (b) §A, (c) `@During` 이 붙은 노드가 ⊥ 이면 아무것도 안 내는 대신
  **Unreachable** 로 보고.

---

## 4. web3bugs_16_H_06 — Unreachable (IntentChecker: Warning)

- **타깃**: `GasOracle.latestAnswer()` (최종 7–18행), intent `@Post result == (gasPrice * (10 ** 9) * ethPrice * (10 ** 12)) / (10 ** 18)` (17행)
- **입력**: `@IReturn gasOracle.latestAnswer()=5e9`, `@IReturn priceOracle.latestAnswer()=3e9`
- **오류 위치** ⓥ: 15행 `uint256 result = PRBMathUD60x18.mul(gasPrice, ethPrice);` — 라이브러리 내부에서 ⊥ 가 되어 돌아온다.
- **케이스 JSON**: 정상 ⓥ
- **로직 = 엔진 버그 A** (아래).
- **패치 시 결과** ⓐ: §A 패치 후 **Violated** (IntentChecker 는 Warning — **판정이 달라짐**. 이 차이는 따로 해석 필요).

## §A. 공통 엔진 버그 — 조기 `return` 만 있는 함수의 EXIT 가 ⊥ (16_H_04·16_H_06)

- `PRBMath.mulDivFixedPoint` 에 조기 `if (prod1 == 0) { …; return result; }` 가 있다. 이 경로는 `Return_322 → RETURN` 노드로 가고
  **EXIT 로 가는 간선이 없다**. 나머지 경로(`prod1 != 0`)는 주어진 입력에서 불가능 → ⊥.
- `Engine._force_join_before_exit`(Engine.py:1416-1421)는 **EXIT 의 선행 노드만** join 하므로 RETURN 쪽 상태가 빠져 EXIT = ⊥.
- `interpret_function_cfg` 가 그 ⊥ 상태변수·전역을 호출자에 되돌려 쓰고(Engine.py:784, 806-829), `_is_bottom_env`(변수 하나라도 ⊥ 이면
  환경 전체 ⊥)가 호출자 경로를 죽인다 → `mul` 을 거쳐 타깃 함수까지 전이.
- **수정안(코어)**:
  ```diff
   def _force_join_before_exit(self, fcfg):
       g = fcfg.graph; exit_node = fcfg.get_exit_node()
  +    preds = list(g.predecessors(exit_node))
  +    rn = fcfg.get_return_exit_node()
  +    if rn is not None and rn in g: preds += list(g.predecessors(rn))
       joined_env = {}
  -    for p in list(g.predecessors(exit_node)):
  +    for p in preds:
  ```
  (⊥ 는 `join_variables_simple` 의 항등원이라 안전 ⓐ)
- **영향**: EXIT 환경은 `@Post` 와 `_sync_named_return_vars` 에도 쓰인다 → **조기 return 이 있는 모든 함수의 @Post 결과가 바뀔 수 있다**.
  더 정확해지는 방향이지만 전 케이스 재실행 필요.

---

## 5. web3bugs_36_H_02 — Unreachable (IntentChecker: 결과 없음)

- **타깃**: `Basket.auctionBurn(uint256 amount) onlyAuction` (최종 46–63행),
  intent `@Post ibRatio(Entry) * _totalSupply(Entry) == ibRatio * _totalSupply` (**최종 69행 — 컨트랙트 밖, §0 참조**)
- **입력**: `auction=sym1`, `msg.sender=sym1`, `ibRatio=1e18`, `_totalSupply=400`, `lastFee=1e6`, `block.timestamp=1e6`,
  `publisher=sym2`, `factory=sym3`, `amount=200`
- **오류 위치** ⓥ: 58행 `handleFees();` → `handleFees`(25–44행)의 **36행**
  `_mint(Ownable(address(factory)).owner(), fee * factory.ownerSplit() / BASE);`
- **케이스 JSON**: **결함** — @Post 줄 번호가 컨트랙트 밖(§0) ⓥ
- **로직** ⓐ:
  1. `Ownable(address(factory)).owner()` — `Ownable` 은 interface 가 아니라 **contract**(`con_51_Ownable`).
  2. `_lookup_interface_return`(Evaluation.py:290-325)는 `Dependencies/objectfile/ifc_<이름>.pkl` 만 열어서 반환형을 찾으므로 실패(None).
  3. Evaluation.py:2629-2630 의 **"fallback: uint256 top"** 이 `owner()` 결과로 **uint interval** 을 낸다 → `address` 자리에 숫자.
  4. `_mint` 의 `require(account != address(0))` 가 (주소가 아닌 값과 비교되며) 성립 불가로 판정 → `_mint` EXIT ⊥ →
     `handleFees` → `auctionBurn` 으로 ⊥ 전이 → `@Post` **Unreachable**.
- **패치 시 결과** ⓐ: 반환형을 이미 로드된 `contract_cfgs[name]` 에서(`find_function_in_hierarchy` + `return_types[0]` + `top_from_soltype`)
  찾게 하고 uint256-top 폴백을 예외로 바꾸면 **Violated**.
- **수정안**: 위 그대로 (반환형 조회 경로 수정 + 폴백 제거). 케이스의 @Post 줄 번호도 함수 본문 안으로 정정(승인 필요).
- **영향**: 지금 조용히 uint ⊤ 를 받던 다른 contract 타입 호출이 예외 또는 타입 변경으로 바뀐다.

---

## 부수 발견 (미조사)

- `TokenProxyLike.parent_cfgs['IERC20']` 가 `iERC20` CFG 를 가리킨다 — §1 과 같은 이름 충돌 의심.
- 엔진 판정 용어가 `satisfied` / `success` 로 섞여 있다(Engine._combine_logic_results).
- 36_H_02·47_H_02 처럼 컨트랙트 **밖**에 놓인 `@Post` 를 엔진이 오류 없이 어떤 함수에 붙이고 있다 — 붙이는 규칙 확인 필요.
