# IntentChecker 코드 수정 이슈 (나중에 일괄 수정)

## Issue 1: During standalone 라인 지원
- **현재**: During annotation은 반드시 코드 옆에 붙어야 함 (코드가 처리될 때 같이 평가)
- **필요**: During annotation 중 특정 statement에 바인딩되지 않는 유형은 standalone 라인(코드 없이 annotation만)으로 배치 가능해야 함
- **예시**: web3bugs_35_H_12.sol mint() 함수
  - line 229: `// @During Changed(secondsPerLiquidity)` (standalone annotation line)
  - line 230-242: `nearestTick = Ticks.insert(...)` (기존 코드가 한 줄 밀림)

### Standalone 가능/불가 분류
- **Standalone 불가**: `Before`, `After` — 해당 statement 실행 전/후 값 비교이므로 반드시 코드 라인에 바인딩 필요
- **Standalone 가능**: `Changed`/`Unchanged`, 값 비교(`x < 100`, `x == y + z`), `ASSIGN`/`CURRENT` — 특정 시점의 상태를 확인하므로 standalone 배치 가능

### 입력 분기 로직 (During만 해당)
- During annotation이 들어올 때, 해당 라인 번호에 **기존 코드가 있는지** 확인하여 분기:
  - **코드 있음** → inline annotation (코드 밀기 X, 해당 라인의 CFG 노드에 attach)
  - **코드 없음** → standalone annotation (코드 밀기 O, 이전 코드 라인의 CFG 노드에 attach)
- 다른 annotation(`@GlobalVar`, `@StateVar`, `@Post`, `@IReturn` 등)은 항상 standalone이므로 기존 add 로직 유지

### Standalone annotation의 CFG 노드 매핑
- standalone annotation은 "이 시점까지의 상태"를 검증하므로, **이전 코드 라인의 CFG 노드**에 연결
- 예: line 228 코드 실행 후 → line 229 standalone annotation 검증 → line 230 코드 실행
- `process_during`에서 `_cfg_node_at(line_no)` → None일 때, 위로 스캔하여 이전 CFG 노드 탐색

### 주요 수정 지점
1. **ContractAnalyzer.py (99-662)**: `update_code`/`_insert_lines`에서 During 입력 시 해당 라인 코드 유무 확인 → inline/standalone 분기
2. **ContractAnalyzer.py (1718-1752)**: `process_during`에서 CFG 노드 없을 때 이전 코드 라인의 노드 탐색 로직 추가
3. **Engine.py (_process_during_annotations)**: standalone annotation 라인의 검증 처리
4. **soltotestjson.py**: annotation-only 라인 처리

## Issue 2: Changed/Unchanged annotation 신규 구현
- **배경**: `Assign != Current`는 값 기반 비교 → 중간에 바뀌었다가 원래값 복귀 시 감지 불가 (false negative)
- **신규**: `Changed(var)` / `Unchanged(var)` — 이벤트 기반, write operation 발생 여부만 추적
- **Validation logic**:
  - `@Post Changed(var)`: Entry → Exit, CFG 전 경로에서 var에 write가 있었는지
  - `@During Changed(var)`: Entry → 해당 라인, CFG 전 경로에서 var에 write가 있었는지
  - `@Post Unchanged(var)`: 기존 구현이 Entry/Exit 값 비교라면 → 이벤트 기반으로 변경 필요
- **기존 `@Post Unchanged(var)` 수정**: 값 비교 → write event 추적으로 변경
- **예시**:
  - `// @During Changed(secondsPerLiquidity)` expected "violated" → write 없음 → missing-operation 탐지 (web3bugs_35_H_12)
  - `// @During Unchanged(balances[msg.sender])` expected "violated" → checkpoint 전에 balance 이미 변경됨 → ordering 버그 탐지 (web3bugs_112_H_01)
- **Motivation case (web3bugs_112_H_01)**:
  - StakerVault.transfer()에서 `balances` 업데이트 후 `userCheckpoint()` 호출 → 보상 계산이 변경된 balance로 수행됨
  - `@During Unchanged(balances[msg.sender])` at checkpoint line → balance 이미 변경 → violated → 탐지
  - 대조: 같은 컨트랙트의 `transferFrom()`은 올바르게 checkpoint → balance 순서
- **영향 범위**: Parser/Solidity.g4 (문법 추가), Analyzer (CFG write tracking), Interpreter (validation logic)

## Issue 3: Contract 밖 file-level struct 지원
- **현재**: struct 정의가 contract scope 안에 있어야만 파싱/처리 가능 (추정)
- **필요**: Solidity 0.6+ 에서 contract 밖 file-level에 정의된 struct 지원
- **예시**: web3bugs_3_H_04.sol
  ```solidity
  struct HourlyBond {
      uint256 amount;
      uint256 yieldQuotientFP;
      uint256 moduloHour;
  }

  abstract contract HourlyBondSubscriptionLending is BaseLending {
      // HourlyBond 사용
  }
  ```
- **Motivation case (web3bugs_3_H_04)**: `HourlyBond` struct가 contract 밖에 정의되어 있음
- **영향 범위**: Parser/Solidity.g4 (file-level struct 문법), Analyzer (struct resolution scope 확장)

## Issue 4: `using` 키워드 커스텀 라이브러리 지원
- **현재**: `using SafeMath for uint256`만 지원 (SafeMath 내장 처리)
- **필요**: 임의의 library에 대한 `using LibName for Type` 지원. `using`으로 바인딩된 메서드 호출을 해당 library의 internal 함수 호출로 resolve하여 분석
- **구현 방향**: library를 dependency로 사전 정의 → `using` 선언 파싱 → `value.method(args)` 호출을 `LibName.method(value, args)`로 변환하여 library 함수 body 진입
- **참고**: 일부 library는 function overloading 사용 (e.g., FixedPointMath의 `add(FixedDecimal, FixedDecimal)` vs `add(FixedDecimal, uint256)`). overload resolution도 필요할 수 있음
- **해당 annotated 케이스**:
  - web3bugs_35_H_12: `using Ticks for mapping(int24 => Ticks.Tick)`
  - web3bugs_45_H_01: `using SafeERC20Upgradeable for IUErc20`
  - web3bugs_112_H_01: `using AddressProviderHelpers for IAddressProvider`, `using SafeERC20 for IERC20`, `using ScaledMath for uint256`
  - web3bugs_70_H_10: `using FixedPoint for FixedPoint.uq112x112`, `using FixedPoint for FixedPoint.uq144x112`
  - web3bugs_56_H_02: `using FixedPointMath for FixedPointMath.FixedDecimal`, `using SafeMath for uint256`, `using SafeERC20 for IDetailedERC20`
  - web3bugs_60_H_01: `using UFixed18Lib for UFixed18`, `using Fixed18Lib for Fixed18`
- **영향 범위**: Parser (using 선언 파싱, method call resolution), Analyzer (library function body 진입), dependency pre-analysis (library 사전분석)

## Issue 5: User-Defined Value Type 지원
- **현재**: `type Fixed18 is int256;` 같은 user-defined value type 미지원 (추정)
- **필요**: Solidity 0.8.8+에서 도입된 `type X is Y;` 구문 지원. 사용자 정의 타입을 underlying primitive type으로 resolve하여 분석
- **구문**: `type Fixed18 is int256;`, `type UFixed18 is uint256;`
- **동작**: `Fixed18.wrap(value)` → int256로, `Fixed18.unwrap(a)` → int256 추출, 타입 자체는 underlying type과 동일하게 취급
- **해당 케이스**:
  - web3bugs_60_H_01: `type Fixed18 is int256;`, `type UFixed18 is uint256;` (OptimisticLedgerLib에서 사용)
- **영향 범위**: Parser (type 선언 파싱), Analyzer (타입 resolution — user-defined type을 underlying type으로 매핑), Interpreter (wrap/unwrap 처리)

## Issue 6: `@During require passable` annotation
- **현재**: require/assert 조건이 항상 false일 때, 함수가 revert되어 @Post에 도달 불가 → post-condition이 vacuously true → 버그 미탐지
- **필요**: require/assert의 통과 가능성을 검증하는 annotation 지원
- **Syntax**: `// @During require passable` (require/assert 라인 직전에 배치)
- **Validation logic**:
  - require 조건식의 abstract value 기준:
  - `[1, 1]` (항상 true) → **satisfied**
  - `[0, 1]` (true 가능) → **satisfied**
  - `[0, 0]` (항상 false, 절대 통과 불가) → **violated**
- **Bug-awareness 불필요**: "이 함수가 정상 동작하면 이 require는 통과해야 한다"는 자연스러운 기대
- **Motivation case (web3bugs_51_H_02)**:
  - `rampTargetPrice`에서 `MAX_RELATIVE_PRICE_CHANGE` (10^16)를 배수가 아닌 delta로 써야 하는데 배수로 사용
  - `future * 0.01 >= initial` (decrease 시) → future < initial이므로 항상 false → 항상 revert
  - `@Post self.futureTargetPrice Changed`로는 탐지 불가 (revert → vacuously true)
  - `@During require passable`로 require 조건이 항상 false임을 탐지
- **영향 범위**: Parser (require passable 구문 파싱), Interpreter (require 조건식 평가 후 passable validation)

## Issue 7: `address(this).balance` GlobalVar 지원
- **현재**: `@GlobalVar`는 `identifier ('.' identifier)?` 형식만 지원 (e.g., `block.timestamp`, `msg.value`). `address(this).balance`는 이 패턴에 맞지 않아 debug annotation으로 설정 불가 (추정)
- **필요**: 컨트랙트의 ETH 잔액 `address(this).balance`를 debug annotation으로 설정할 수 있도록 지원
- **구현 방향**: `address(this).balance`를 특수 GlobalVar로 인식하거나, 별도 syntax 추가 (e.g., `@GlobalVar selfBalance = [100, 100]`)
- **해당 케이스**:
  - numscout_HippoHotel: `withdraw()` 함수에서 `address(this).balance` 읽어서 분배
  - numscout_EthereumGod: `swapAndLiquify()` 함수에서 `address(this).balance` 사용 (단, 이 케이스는 interface call이 주 blocker)
- **영향 범위**: Parser (GlobalVar 문법 확장), Interpreter (address(this).balance 값 주입)

## Issue 8: 피상속 컨트랙트의 private state variable 접근 지원
- **현재**: target contract 자체의 state variable만 @StateVar / @Post로 접근 가능 (추정)
- **필요**: 상속받은 부모 컨트랙트(e.g., OpenZeppelin ERC20)의 private state variable (`_balances`, `_totalSupply`)에 대해 @StateVar 설정 및 @Post 검증 가능하도록 지원
- **구현 방향**: 상속 체인을 따라 부모 컨트랙트의 state variable을 target contract의 scope에 포함. `_mint()`, `_burn()` 등 부모 함수 호출 시 부모의 state variable 변화 추적
- **해당 annotated 케이스**:
  - web3bugs_78_H_02: `RebaseProxy is ERC20` — `_mint(to, proxy)` 후 `_balances[to]` 검증 필요. `@Post _balances[to] <= amount`로 과다 mint 탐지
- **영향 범위**: Analyzer (상속 체인 state variable resolution), Interpreter (부모 state variable 값 설정/검증)
