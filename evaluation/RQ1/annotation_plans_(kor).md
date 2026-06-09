# RQ2 Annotation Plans

컨트랙트별 contraction/annotation 계획을 추적하는 문서.
- case JSON 생성 전 단계에서 논의된 내용을 기록
- contraction 완료 후 case JSON으로 옮김

---

## web3bugs_35_H_12

- **Contract**: ConcentratedLiquidityPool
- **Function**: mint
- **Bug lines (original)**: 176; 184
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L5a: missing-state-update)`

### 버그 설명
`mint()`에서 `liquidity`를 변경(line 176)하지만 `secondsPerLiquidity`를 업데이트하지 않음. `swap()`에서는 `secondsPerLiquidity += uint160((diff << 128) / liquidity)`로 올바르게 갱신하지만, `mint()`에서 동일한 갱신이 누락됨.

### Not Detectable 사유
- `Changed(secondsPerLiquidity)` annotation으로 표현 가능하나, "liquidity가 변경될 때 secondsPerLiquidity도 갱신되어야 한다"는 것을 알아야 annotation 작성 가능 → 버그 인지 전제 (L5a: missing-state-update)
- `swap()`과의 일관성을 놓친 것이 버그 원인 — annotation 시점에서 그 일관성을 챙길 수 있었다면 코드에서도 챙겼을 것
- 부가적으로, `abi.decode`로 파라미터가 전달되어 debugging annotation으로 concrete 값 설정 불가

---

## web3bugs_43_H_02

- **Contract**: DelegatedStaking
- **Function**: unstake
- **Bug lines (original)**: 223; 224; 226
- **Pattern**: erroneous_accounting
- **Status**: excluded_fixed_code

### Notes
- 현재 코드가 이미 수정된 버전 (exchange rate 업데이트가 shares 계산 전에 호출됨)
- 탐지할 버그가 없으므로 데이터셋에서 제외

---

## web3bugs_45_H_01

- **Contract**: UToken
- **Function**: borrow
- **Bug lines (original)**: 403; 409; 413
- **Bug lines (contraction)**: 203; 205; 207; 213
- **Pattern**: erroneous_accounting
- **Status**: `annotated`

### Dependencies
**Contracts**:
- Controller, ReentrancyGuardUpgradeable, SafeERC20Upgradeable

**Interfaces**:
- IInterestRateModel, IUErc20, IUserManager, IAssetManager

**Libraries**:
- interestRateModel, assetManagerContract

**구현 필요**:
- `using SafeERC20Upgradeable for IUErc20;`

### Intent Annotations
| Type | Line (contraction) | Expression | Expected | Comment |
|------|-------------------|------------|----------|---------|
| During | 203, 205, 207, 213 | borrowIndex(Before < After) | violated | accrueInterest() 호출 전이므로 borrowIndex 미갱신 → Before == After → 위반 |

※ Z3 solver로 방향 확정: Before < After ✓ (z3_solvers/web3bugs_45_H_01_solver.py)

### Debug Annotations (Z3 생성값)
**LocalVar:**
| # | Variable | Value (interval) | Comment |
|---|----------|-------------------|---------|
| 1 | amount | [1000000000000000001, 1000000000000000001] | ~1e18 (1 token in wei) |
| 2 | account | symbolicAddress 101 | msg.sender와 일치 |

**StateVar:**
| # | Variable | Value (interval) | Comment |
|---|----------|-------------------|---------|
| 1 | minBorrow | [2, 2] | require 통과용 |
| 2 | debtCeiling | [1000000000000000002, 1000000000000000002] | getRemainingLoanSize용 |
| 3 | totalBorrows | [0, 0] | getRemainingLoanSize용 |
| 4 | originationFee | [1000000000000001, 1000000000000001] | ~0.1%, fee 계산용 |
| 5 | WAD | [1000000000000000000, 1000000000000000000] | 1e18 |
| 6 | accountBorrows[101].principal | [1000000000000000001, 1000000000000000001] | ~1e18 |
| 7 | accrualBlockNumber | [1, 1] | blockDelta 계산용 |
| 8 | borrowIndex | [1000000000000000001, 1000000000000000001] | ~1e18, intent 대상 |
| 9 | accountBorrows[101].interest | [1, 1] | calculatingInterest용 |
| 10 | accountBorrows[101].interestIndex | [1000000000000000001, 1000000000000000001] | ~1e18 |
| 11 | accountBorrows[101].lastRepay | [1, 1] | checkIsOverdue 통과용 |
| 12 | maxBorrow | [2001005000000000005, 2001005000000000005] | require 통과용 |
| 13 | overdueBlocks | [2, 2] | checkIsOverdue 통과용 |

**GlobalVar:**
| # | Variable | Value (interval) | Comment |
|---|----------|-------------------|---------|
| 1 | block.number | [2, 2] | blockDelta = 1 |

**중간 계산값 (검증용):**
- fee = 1000000000000001 (~1e15)
- blockDelta = 1
- borrowIndexNew = 1000005000000000001
- calculatingInterest = 5000000000001
- borrowBalanceView = 1000005000000000002

### 값 생성 조건 (Z3 constraint)
```
C1: debtCeiling > totalBorrows
    근거: if (debtCeiling >= totalBorrows) {return debtCeiling - totalBorrows;} (getRemainingLoanSize)

C2: amount >= minBorrow
    근거: require(amount >= minBorrow) (borrow)

C3: amount <= debtCeiling - totalBorrows
    근거: require(amount <= getRemainingLoanSize()) (borrow)

C4: accountBorrows[101].principal >= 1
    근거: if (loan.principal == 0) {return 0;} (calculatingInterest)

C5: block.number > accrualBlockNumber
    근거: uint256 blockDelta = currentBlockNumber - accrualBlockNumber; (calculatingInterest)

C6: overdueBlocks >= block.number - accountBorrows[101].lastRepay
    근거: require(!checkIsOverdue(msg.sender)) (borrow) — principal > 0이므로 else 분기, 연체 아닌 조건

C7: (((accountBorrows[101].principal + accountBorrows[101].interest)
      * ((0.0005e16 * (block.number - accrualBlockNumber) * borrowIndex) / WAD + borrowIndex))
      / accountBorrows[101].interestIndex)
    - accountBorrows[101].principal >= 1
    근거: calculatingInterest 반환값이 의미 있어야 함

C8: accountBorrows[101].principal
    + C7의 calculatingInterest 결과
    + amount + (originationFee * amount) / WAD
    <= maxBorrow
    근거: require(borrowBalanceView(msg.sender) + amount + fee <= maxBorrow) (borrow)
```

### Notes
- 버그: accrueInterest()가 borrowBalanceView()/getCreditLimit() 체크 뒤에 호출됨
- borrowBalanceView() → calculatingInterest() → borrowIndex(상태변수) 읽음
- accrueInterest() 미호출 시 borrowIndex 변화 없음 → stale 값으로 대출 한도 검사
- Changed(borrowIndex)로도 탐지 가능하나, Before < After가 더 정밀 (증가 방향 명시)
- checkIsOverdue 통과: principal > 0일 때 else 분기로 가서 overdueBlocks >= diff 이면 false 반환

---

## web3bugs_45_H_02

- **Contract**: CreditLimitByMedian
- **Function**: getLockedAmount
- **Bug lines (original)**: 66
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L1b: loop-body-granularity)

### Bug Description
`getLockedAmount()`의 for loop 내에서 `newLockedAmount = array[i].lockedAmount - 1`로 되어 있으나, 올바른 구현은 `array[i].lockedAmount - amount`여야 함. `1`이 하드코딩되어 있어서 lockedAmount가 제대로 unlock되지 않음.

### 탐지 불가 사유
IntentChecker는 loop를 statement 단위로 분석하지 않고 **fixed-point iteration**으로 loop 전체의 수렴값을 계산함. 따라서:
- Loop body 내부의 개별 statement에 intent annotation을 배치할 수 없음
- `newLockedAmount = array[i].lockedAmount - 1` vs `- amount` 같은 loop 내부 wrong-value 버그는 intent로 표현 불가
- Loop 밖에서 최종 반환값에 대한 annotation은 가능하나, fixed-point 결과가 이미 imprecise하므로 의미 있는 탐지가 어려움

### 버그 코드
```solidity
for (uint256 i = 0; i < array.length; i++) {
    if (array[i].lockedAmount > amount) {
        newLockedAmount = array[i].lockedAmount - 1;  // BUG: should be `- amount`
    } else {
        newLockedAmount = 0;
    }
    if (account == array[i].staker) {
        return newLockedAmount;
    }
}
```

---

## web3bugs_83_H_01

- **Contract**: MasterChef
- **Function**: add
- **Bug lines (original)**: 89 (totalAllocPoint 변경 전 massUpdatePools() 호출 누락)
- **Pattern**: inconsistent_state_updates
- **Status**: not_detectable (L5a: missing-call-no-effect)

### Bug Description
`add()` 함수에서 `totalAllocPoint`을 증가시키기 전에 `massUpdatePools()`를 호출하지 않음. 기존 풀들의 `accConcurPerShare`가 이전의 `totalAllocPoint`로 갱신되지 않은 채 새로운 (더 큰) `totalAllocPoint`가 적용되어, 기존 staker들의 reward가 소급적으로 희석됨.

### 탐지 불가 사유
`add()` 함수 내 실제 사용 변수(`totalAllocPoint`, `poolInfo`, `pid[_token]`)는 모두 자기 역할을 올바르게 수행하며 값 수준의 이상이 없음. 버그의 효과(기존 풀의 `accConcurPerShare` 미갱신)는 `add()` scope 밖의 변수에만 나타남.

- `poolInfo[1].accConcurPerShare(Entry != Exit)` 같은 post condition으로 표현은 가능하나, 개발자가 "기존 풀을 업데이트해야 한다"를 이미 인지해야 작성 가능 → 인지했으면 `massUpdatePools()` 호출을 추가하면 되므로 현실적 검출 시나리오가 아님
- 함수 내 변수만으로는 누락된 side effect를 감지할 수 없음

---

## web3bugs_83_H_02

- **Contract**: MasterChef
- **Function**: deposit
- **Bug lines (original)**: 170; 171; 172
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L4b: no-target-storage)

### Bug Description
`deposit()`에서 `depositFeeBP > 0`일 때 fee를 계산하여 `user.amount`에서 차감하지만, 그 fee를 받을 수신자(feeRecipient)의 `amount`를 증가시키는 코드가 없음. 결과적으로 deposit fee 만큼의 토큰이 컨트랙트에 영구 lock됨.

### 탐지 불가 사유
IntentChecker의 intent annotation은 **변수의 값에 대한 명제**(proposition)를 검증하는 방식이다. 명제를 세우려면 대상 변수가 코드에 존재해야 하는데, 이 버그는 fee를 credit할 대상 변수(`feeRecipient.amount`)가 코드에 없어 annotation을 구성할 수 없다.

- 기존 변수들은 모두 자기 역할을 올바르게 수행하여 값 수준의 이상이 없음:
  - `user.amount`: `_amount - depositFee`로 정확히 계산됨
  - `depositFee`: 올바르게 계산됨
  - `user.rewardDebt`: 새 amount 기반으로 정확히 재계산됨
- `Before/After`, `Assign/Current`, `Entry/Exit`, CommonClause 어떤 패턴으로도 기존 변수에서 이상을 탐지할 수 없음

### 버그 코드
```solidity
if (_amount > 0) {
    if (pool.depositFeeBP > 0) {
        uint depositFee = _amount.mul(pool.depositFeeBP).div(_perMille);
        user.amount = SafeCast.toUint128(user.amount + _amount - depositFee);
        // BUG: depositFee가 feeRecipient에게 credit되지 않음
    } else {
        user.amount = SafeCast.toUint128(user.amount + _amount);
    }
}
```

---

## web3bugs_3_H_04

- **Contract**: HourlyBondSubscriptionLending
- **Function**: viewHourlyBondAmount
- **Bug lines (original)**: 96; 97
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L1a: loop-widening-precision-loss)

### Bug Description
`viewHourlyBondAmount()`에서 `applyInterest()`의 리턴값 해석이 잘못됨.

**같은 컨트랙트 내 두 가지 사용 패턴:**
```solidity
// (1) updateHourlyBondAmount(): applyInterest = 원금+이자 (full balance) 로 취급
bond.amount = applyInterest(bond.amount, yA.accumulatorFP, yieldQuotientFP);
uint256 deltaAmount = bond.amount - oldAmount;  // delta를 따로 계산

// (2) viewHourlyBondAmount(): applyInterest = 이자만 (delta) 로 취급 → BUG
return bond.amount + applyInterest(bond.amount, cumulativeYield, yieldQuotientFP);
```

`updateHourlyBondAmount()`에서 `deltaAmount = bond.amount - oldAmount`으로 delta를 별도 계산하는 것을 보면, `applyInterest`는 **원금+이자(full balance)를 리턴**하는 함수. 따라서 `viewHourlyBondAmount()`의 `bond.amount + applyInterest(...)`는 원금을 **이중 계산(double-count)**하여 실제보다 약 2배 큰 값을 리턴.

### 탐지 가능성 분석

**후보 Annotation**: `@During returnExpression == <expected_value>` (debug annotation으로 구체적 값 제공)

**문제**: `returnExpression`에 대한 intent를 세우려면 `applyInterest`의 리턴값을 알아야 하는데, 그 값은 `cumulativeYield`에 의존하고, `cumulativeYield`는 `viewCumulativeYieldFP()` → `calcCumulativeYieldFP()`를 통해 계산됨.

### 탐지 불가 사유: calcCumulativeYieldFP의 반복문과 Widening

`calcCumulativeYieldFP()`에는 아래 반복문이 존재:

```solidity
function calcCumulativeYieldFP(
    YieldAccumulator storage yieldAccumulator,
    uint256 timeDelta
) internal view returns (uint256 accumulatorFP) {
    // Step 1: 시간 단위 미만 선형 보간
    uint256 secondsDelta = timeDelta % (1 hours);
    accumulatorFP =
        (yieldAccumulator.accumulatorFP *
            yieldAccumulator.hourlyYieldFP *
            secondsDelta) /
        (FP32 * 1 hours);     // 분모 = 2^32 × 3600 ≈ 1.5×10^13

    // Step 2: 시간 단위 복리 계산 (문제의 반복문)
    uint256 hoursDelta = timeDelta / (1 hours);
    if (hoursDelta > 0) {
        for (uint256 i = 0; i < hoursDelta; i++) {
            accumulatorFP =
                (accumulatorFP * yieldAccumulator.hourlyYieldFP) /
                FP32;
        }
    }
}
```

여기서 FP32 = 2^32 (고정소수점 32비트). 모든 `_FP` 접미사 변수는 실수값 × 2^32 형태.

**반복문의 수학적 의미 (개발자 의도):**
- `hourlyYieldFP`는 시간당 이자율 (예: 1.0001 → FP32로 ≈ 4,295,396,762)
- 매 iteration: `acc = acc × hourlyYield_real` (실수로 풀면 단순 곱셈)
- N시간 후: `acc = acc_initial × hourlyYield^N` (복리 계산)
- 실제 Solidity 실행 시에는 정상 동작

**IntentChecker의 Fixpoint 분석에서 발생하는 문제:**

IntentChecker는 반복문을 **fixpoint iteration + widening**으로 분석:

1. debug annotation으로 `hoursDelta = 2` 지정 시, 2회 반복까지 구체적으로 실행
2. 2회 후에도 fixpoint(수렴)가 안 되면 **widening operator** 적용

반복문 본체 `accumulatorFP = (accumulatorFP * hourlyYieldFP) / FP32`에서:
- `hourlyYieldFP > FP32` (이자율 > 1.0, 정상 케이스): 매 iteration마다 **증가** → fixpoint 불가 → widening → **∞ (inf)**
- `hourlyYieldFP < FP32` (이자율 < 1.0, 비정상): 매 iteration마다 **감소** → fixpoint 불가 → widening → **0**
- `hourlyYieldFP == FP32` (이자율 = 1.0, 비현실적): fixpoint 도달하나 이자 0%로 무의미

**결과적으로 `cumulativeYield`가 0 또는 ∞:**

```solidity
// applyInterest:
return (balance * accumulatorFP) / yieldQuotientFP;
```

- `cumulativeYield = 0` → `applyInterest` = 0 → buggy return = `bond.amount + 0` = `bond.amount`
  - 정상 return도 = `applyInterest(amount, 0, yieldQuotient)` = 0 → 구분 불가
- `cumulativeYield = ∞` → `applyInterest` = ∞ → buggy/correct 모두 ∞ → 구분 불가

두 경우 모두 buggy code와 correct code의 리턴값이 동일하게 되어 **annotation이 위반되지 않으므로 탐지 불가**.

### Step 1 (선형 보간)만으로 우회 가능한가?

`hoursDelta = 0` (timeDelta < 3600)으로 설정하면 반복문을 건너뛸 수 있으나:
```solidity
accumulatorFP = (acc * hourlyYield * secondsDelta) / (FP32 * 3600);
```
분모가 `2^32 × 3600 ≈ 1.5×10^13`이므로:
- 작은 debug 값 (acc=100, hourlyYield=100, secondsDelta=30): 분자 = 300,000 → 정수 나눗셈 → **0**
- FP32 스케일 값 (acc=2^32, hourlyYield=2^32): 의미 있는 결과가 나오지만, 이 경우 `secondsDelta`가 0이면 여전히 0이고, `secondsDelta > 0`이면 결과가 나와도 `applyInterest`까지 정확히 기대값을 계산해야 함 → diagnostic annotation 성격

### 요약

| 구분 | 내용 |
|------|------|
| **Limitation 유형** | loop-widening-precision-loss |
| **근본 원인** | `calcCumulativeYieldFP`의 반복문이 고정소수점 복리 계산 → 매 iteration 값 변화 → fixpoint 미수렴 → widening으로 0 또는 ∞ |
| **영향** | `cumulativeYield` (핵심 중간값)이 imprecise → `returnExpression` annotation의 expected value 계산 불가 |
| **우회 불가 사유** | 반복문 없이(hoursDelta=0) 실행해도 선형 보간 분모가 2^32×3600으로 커서 작은 값은 0 되고, FP32 스케일 값을 써도 applyInterest 결과를 미리 계산해야 하는 diagnostic 문제 존재 |
| **대조 (updateHourlyBondAmount)** | 같은 문제 — `getUpdatedHourlyYield` 내부에서도 `calcCumulativeYieldFP` 호출하므로 동일한 widening 문제 발생 |

---

## web3bugs_25_H_01

- **Contract**: CompositeMultiOracle
- **Function**: _peek; _get
- **Bug lines (original)**: 116; 126
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L4a: inexpressible-expected-value)`

### Bug Description
`_peek()`/`_get()`에서 `priceOut`을 계산할 때 `10 ** source.decimals` (토큰 decimals)로 나누지만, 올바른 구현은 `10 ** IOracle(source.source).decimals()` (오라클 출력 decimals, 항상 18)로 나눠야 함. 체인된 oracle path에서 가격 스케일이 누적적으로 잘못되어 inflated된 값을 반환. (예: USDC→DAI→USDT 경로에서 `1e30`으로 inflate)

### Not Detectable 사유
- Interface call은 이제 지원되어 `IOracle(source.source).peek()` 반환값은 TOP이 아님
- 그러나 올바른 denominator는 `10 ** IOracle(source.source).decimals()` (오라클 출력 precision)
- `IOracle(source.source).decimals()`는 buggy 코드에서 **호출되지 않는 함수** → 값을 담는 변수가 scope에 없음
- annotation grammar에서 함수 호출 불가 (intentValue = 변수/상수/산술 조합만)
- 따라서 올바른 expected value를 annotation으로 표현할 수 없음 (L4a)

---

## web3bugs_34_H_01

- **Contract**: DrawCalculator
- **Function**: _numberOfPrizesForIndex
- **Bug lines (original)**: 422; 423; 424
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L1a: loop-widening)

### Bug Description
`_numberOfPrizesForIndex()`에서 특정 tier의 상금 개수를 계산할 때, while loop으로 모든 lower power를 빼서 올바른 값보다 작은 값을 반환.

**Buggy formula**: `b^d - b^(d-1) - b^(d-2) - ... - b^0` (while loop으로 과도하게 뺌)
**Correct formula**: `b^d - b^(d-1)` (한 번만 뺄셈, loop 불필요)

예시 (b=16, d=3): buggy = 4096 - 256 - 16 - 1 = 3823, correct = 4096 - 256 = 3840

### 탐지 불가 사유
함수 자체는 `internal pure`이고 모든 입력이 parameter에서 오므로 interface-call-return-top 문제 없음. Debugging annotation으로 parameter에 concrete value 부여 가능.

그러나 while loop의 fixpoint iteration + widening으로 인해 over-approximation 발생:
- `numberOfPrizesForIndex -= bitRangeDecimal**(_prizeTierIndex - 1)` 에서 `-=` operator
- 매 iteration마다 다른 exponential 값을 빼므로 fixpoint 미수렴 → widening 적용
- widening은 **sound over-approximation**: 실제값(3823)과 correct value(3840)를 모두 포함하는 범위 생성
- interval domain이면 [0, 4096], flat domain이면 Top → 3840 ∈ 범위 내 → violation 미검출

**핵심**: widening으로 나오는 0은 실제 프로그램 동작이 아닌 over-approximation의 하한. 실제 buggy output은 3823이고 correct output은 3840. 둘 다 widened range 안에 포함되므로 구분 불가.

### 버그 코드
```solidity
function _numberOfPrizesForIndex(uint8 _bitRangeSize, uint256 _prizeTierIndex)
    internal pure returns (uint256)
{
    uint256 bitRangeDecimal = 2**uint256(_bitRangeSize);
    uint256 numberOfPrizesForIndex = bitRangeDecimal**_prizeTierIndex;

    while (_prizeTierIndex > 0) {
        numberOfPrizesForIndex -= bitRangeDecimal**(_prizeTierIndex - 1);  // BUG: 과도한 뺄셈
        _prizeTierIndex--;
    }

    return numberOfPrizesForIndex;
}
```

### Correct code (fix)
```solidity
if (_prizeTierIndex > 0) {
    return (1 << _bitRangeSize * _prizeTierIndex) - (1 << _bitRangeSize * (_prizeTierIndex - 1));
} else {
    return 1;
}
```

---

## web3bugs_52_H_34

- **Contract**: TwapOracle
- **Function**: consult
- **Bug lines (original)**: 129; 152
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L1a: loop-widening)

### Bug Description
`consult()`에서 for loop 내부에서 `sumNative`와 `sumUSD`를 독립적으로 누적하여 최종적으로 `(sumUSD * decimals) / sumNative`로 나누는데, 각 pair의 native amount와 USD price가 올바르게 가중 결합되지 않아 잘못된 consultation 결과를 반환.

### 탐지 불가 사유

**문제 1: Loop body 내부 intent annotation 불가**
- 버그가 line 129 (`sumNative += ...`)와 line 152 (`sumUSD += ...`)에 있으며 둘 다 loop body 내부
- 올바른 수정은 accumulation 방식 자체의 변경 (예: weighted average) → 단일 라인의 값에 대한 intent로 표현 불가
- `result` (line 156)에 intent를 달더라도 `sumUSD`와 `sumNative`가 이미 Top이면 의미 없음

**문제 2: `+=` 에 의한 widening**
- `sumNative += pairData.price1Average.mul(1).decode144()` → `+=` operator → widening 방향은 ∞ → **Top**
- `sumUSD += uint256(price) * (10**10)` → `+=` operator → widening 방향은 ∞ → **Top**
- 결과: `result = (Top * Top) / Top` → **Top**
- buggy와 correct 모두 Top이므로 구분 불가

**참고**: `price`는 `AggregatorV3Interface(...).latestRoundData()` interface 호출이라 Top이지만, 이는 debugging annotation으로 해결 가능한 부차적 문제. 근본 blocker는 loop 내 `+=` widening.

### 버그 코드
```solidity
function consult(address token) public view returns (uint256 result) {
    uint256 pairCount = _pairs.length;
    uint256 sumNative = 0;
    uint256 sumUSD = 0;

    for (uint256 i = 0; i < pairCount; i++) {
        PairData memory pairData = _pairs[i];

        if (token == pairData.token0) {
            sumNative += pairData.price1Average.mul(1).decode144();  // line 129: += widening → Top
            ...
            sumUSD += uint256(price) * (10**10);                     // line 152: += widening → Top
        }
    }
    require(sumNative != 0, "TwapOracle::consult: Sum of native is zero");
    result = ((sumUSD * IERC20Metadata(token).decimals()) / sumNative);  // Top / Top = Top
}
```

---

## web3bugs_52_H_04

- **Contract**: TwapOracle
- **Function**: consult
- **Bug line (original)**: 156
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L1a: loop-widening)

### Bug Description
`consult()`의 최종 계산에서 `IERC20Metadata(token).decimals()` (= 18)를 사용하지만, 올바른 구현은 `10 ** IERC20Metadata(token).decimals()` (= 1e18)를 사용해야 함. scaling factor가 1e18이 아닌 18이 적용되어 결과가 크게 왜곡됨.

### 탐지 불가 사유
`sumNative`와 `sumUSD`가 모두 루프 내 `+=` 누적 → widening → Top. 최종 `result = (sumUSD * decimals) / sumNative` = Top / Top = Top으로, scaling 차이를 감지할 수 없음. web3bugs_52_H_34와 동일한 루프 구조.

### 버그 코드
```solidity
result = ((sumUSD * IERC20Metadata(token).decimals()) / sumNative);
// BUG: decimals() returns 18, should be 10**decimals() = 1e18
// Fix: uint256 scalingFactor = 10 ** IERC20Metadata(token).decimals();
//      result = (sumUSD * scalingFactor) / sumNative;
```

---

## web3bugs_52_H_28

- **Contract**: TwapOracle
- **Function**: consult
- **Bug line (original)**: 156
- **Pattern**: erroneous_accounting
- **Status**: excluded (duplicate_of_52_H_04)

### Notes
web3bugs_52_H_04와 동일한 컨트랙트, 동일한 함수, 동일한 버그 라인(156)을 다른 감사자가 중복 보고한 케이스. 52_H_04에서 분석.

---

## web3bugs_59_H_04

- **Contract**: AuctionBurnReserveSkew
- **Function**: getPegDeltaFrequency
- **Bug line (original)**: 131
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L1a: loop-widening)

### Bug Description
`getPegDeltaFrequency()`에서 `count < auctionAverageLookback`일 때 분모를 `auctionAverageLookback` 대신 `count`로 나눠야 함. 현재 구현은 실제 관측 수보다 큰 분모를 사용하여 과소평가된 값을 반환.

### 탐지 불가 사유
`total`이 루프 내에서 `total = total + pegObservations[index]`로 `+=` 누적 → widening → Top. 최종 `total * 10000 / auctionAverageLookback`든 `total * 10000 / count`든 결과가 Top → 구분 불가.

### 버그 코드
```solidity
function getPegDeltaFrequency() public view returns (uint256) {
    uint256 initialIndex = 0;
    if (count > auctionAverageLookback) {
        initialIndex = count - auctionAverageLookback;
    }
    uint256 total = 0;
    for (uint256 i = initialIndex; i < count; ++i) {
        index = _getIndexOfObservation(i);
        total = total + pegObservations[index];  // += widening → Top
    }
    return total * 10000 / auctionAverageLookback;  // BUG: should be / count when count < auctionAverageLookback
}
```

---

## web3bugs_70_H_03

- **Contract**: LiquidityBasedTWAP
- **Function**: _calculateUSDVPrice (동일 구조: _calculateVaderPrice)
- **Bug lines (original)**: 399; 403
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L1a: loop-widening)

### Bug Description
`_calculateUSDVPrice()`에서 pair가 2개 이상일 때 USDV 가격을 잘못 계산. "비율들의 가중평균"이 아니라 "가중평균들의 비율"을 계산함.

**수학적 문제**: `E[X/Y] ≠ E[X]/E[Y]`
- **Correct**: `Σ(weight_i/totalWeight × foreignPrice_i / nativePrice_i)` — 각 pair별 USD 가격을 먼저 구한 후 가중평균
- **Buggy**: `Σ(weight_i/totalWeight × foreignPrice_i) / Σ(weight_i/totalWeight × nativePrice_i)` — foreign price 평균과 native price 평균을 각각 구한 후 나누기

Pair가 1개면 두 식은 동일하지만, 2개 이상이면 결과가 달라짐. `_calculateVaderPrice()`도 동일한 구조적 문제 보유.

### 탐지 불가 사유

**문제 1: `+=` 에 의한 widening**
- `totalUSD += (foreignPrice * liquidityWeights[i]) / totalUSDVLiquidityWeight` → `+=` → widening → **Top**
- `totalUSDV += (nativeAvgPrice * liquidityWeights[i]) / totalUSDVLiquidityWeight` → `+=` → widening → **Top**
- 결과: `(Top * 1 ether) / Top` → **Top**
- buggy와 correct 모두 Top이므로 구분 불가

**문제 2: Loop body 내 intent annotation 불가**
- 버그가 accumulation 방식 자체의 문제 (비율의 평균 vs 평균의 비율)
- 수정하려면 loop body 구조 자체를 변경해야 함 → 단일 라인의 값에 대한 intent로 표현 불가

**참고**: `getChainlinkPrice()` → `oracle.latestRoundData()` interface 호출로 `foreignPrice`도 Top이지만, debugging annotation으로 해결 가능한 부차적 문제. 근본 blocker는 loop 내 `+=` widening.

### 버그 코드
```solidity
function _calculateUSDVPrice(
    uint256[] memory liquidityWeights,
    uint256 totalUSDVLiquidityWeight
) internal view returns (uint256) {
    uint256 totalUSD;
    uint256 totalUSDV;
    uint256 totalPairs = usdvPairs.length;

    for (uint256 i; i < totalPairs; ++i) {
        ...
        uint256 foreignPrice = getChainlinkPrice(address(foreignAsset));

        totalUSD +=                                          // line 399: += widening → Top
            (foreignPrice * liquidityWeights[i]) /
            totalUSDVLiquidityWeight;

        totalUSDV +=                                         // line 403: += widening → Top
            (pairData.nativeTokenPriceAverage
                .mul(pairData.foreignUnit)
                .decode144() * liquidityWeights[i]) /
            totalUSDVLiquidityWeight;
    }

    return (totalUSD * 1 ether) / totalUSDV;                 // Top / Top = Top
}
```

---

## web3bugs_70_H_04

- **Contract**: LiquidityBasedTWAP
- **Function**: syncVaderPrice
- **Bug lines (original)**: 131; 140; 144; 147
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L1a: loop-widening)

### Bug Description
`syncVaderPrice()`의 for loop에서 `timeElapsed < pairData.updatePeriod`인 pair를 `continue`로 건너뛰는데, 이때 해당 pair의 기여분이 완전히 누락됨.

**구체적 문제**:
1. `pastLiquidityWeights[i]`가 0으로 남음 (line 140 미실행) → `_calculateVaderPrice` 분자에서 누락
2. `_totalLiquidityWeight`에 해당 pair 미포함 (line 144 미실행)
3. `pastTotalLiquidityWeight`는 이전 저장된 **전체** 합 (line 124) → 분모는 모든 pair 포함
4. Line 147에서 불완전한 `_totalLiquidityWeight`를 state에 저장 → 다음 호출의 `pastTotalLiquidityWeight`도 오염

**결과**: 분자는 일부 pair만, 분모는 전체 pair → 가격 과소평가.

**올바른 수정**: `continue` 전에 `pastLiquidityWeights[i] = pairData.pastLiquidityEvaluation`과 `_totalLiquidityWeight += pairData.pastLiquidityEvaluation` 추가.

### 탐지 불가 사유

**문제 1: `+=` widening**
- `_totalLiquidityWeight += currentLiquidityEvaluation` → loop 내 `+=` → widening → **Top**
- 결과적으로 `totalLiquidityWeight` state 변수도 Top

**문제 2: Interface calls**
- `_updateVaderPrice` 내부에서 `pair.token0()`, `pair.getReserves()`, `UniswapV2OracleLibrary.currentCumulativePrices()` 등 interface 호출 → Top

**문제 3: Control flow 버그**
- `continue`로 인한 선택적 누락은 값(value) annotation으로 표현하기 어려움
- "skipped pair도 weight에 포함되어야 한다"는 제어 흐름 속성이지 값 속성이 아님

### 버그 코드
```solidity
function syncVaderPrice() public override returns (...) {
    uint256 _totalLiquidityWeight;
    ...
    pastTotalLiquidityWeight = totalLiquidityWeight[uint256(Paths.VADER)];  // 전체 합

    for (uint256 i; i < totalPairs; ++i) {
        ...
        if (timeElapsed < pairData.updatePeriod) continue;  // line 131: skip → 아래 전부 미실행

        pastLiquidityWeights[i] = pastLiquidityEvaluation;   // line 140: skip시 0으로 남음
        ...
        _totalLiquidityWeight += currentLiquidityEvaluation; // line 144: skip시 미포함
    }

    totalLiquidityWeight[uint256(Paths.VADER)] = _totalLiquidityWeight;  // line 147: 불완전한 합 저장
}
```

---

## web3bugs_70_H_05

- **Contract**: LiquidityBasedTWAP
- **Function**: _calculateUSDVPrice
- **Bug line (original)**: 412
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L1a: loop-widening)

### Bug Description
`_calculateUSDVPrice()`에서 Chainlink의 `foreignPrice`가 8 decimals (1e8 = $1)로 반환되는데, 프로토콜은 18 decimals (1e18 = $1)을 기대함. `foreignPrice`를 스케일링 없이 그대로 `totalUSD`에 누적하여, 최종 결과가 1e18이어야 할 것이 1e8로 반환됨.

### 탐지 불가 사유
`totalUSD`와 `totalUSDV` 모두 루프 내 `+=` 누적 → widening → Top. 최종 `(totalUSD * 1 ether) / totalUSDV` = Top / Top = Top. 스케일링 오류(1e8 vs 1e18)를 감지할 수 없음. web3bugs_70_H_03, web3bugs_70_H_04와 동일한 TWAP oracle 루프 구조.

### 버그 코드
```solidity
// foreignPrice = getChainlinkPrice(address(foreignAsset));  // 1e8 (8 decimals)
totalUSD += (foreignPrice * liquidityWeights[i]) / totalUSDVLiquidityWeight;  // += widening → Top
totalUSDV += ...;  // += widening → Top

return (totalUSD * 1 ether) / totalUSDV;  // Top / Top = Top
// BUG: foreignPrice is 1e8 scale, should be scaled to 1e18
```

---

## web3bugs_71_H_11

- **Contract**: PoolTemplate
- **Function**: resume
- **Bug lines (original)**: 709; 710; 711
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L1b: loop-body-granularity)`

### Bug Description
`resume()`에서 각 index pool의 상환액(`_redeemAmount`)을 계산할 때 나눗셈(`_divCeil`)을 사용하지만, 올바른 계산은 곱셈이어야 함.

**수학적 문제**:
- `_deductionFromIndex` = 전체 index에서 차감할 총액 (× 1e6 scaled)
- `_shareOfIndex` = 해당 index의 비율 (× 1e6, 예: 30% → 300000)
- **Buggy**: `_divCeil(총액, 비율)` = 총액 ÷ 0.3 → 총액의 3.3배 (과다 상환)
- **Correct**: `총액 × 비율 / 1e6` → 총액의 30% (정상 비례 배분)

Index가 1개면 shareOfIndex = 1e6이라 나눠도 동일. 2개 이상이면 각 index가 과다 상환.

### 탐지 불가 사유 (L1b: loop-body-granularity)

**Interface call은 이제 지원됨**: `vault.debts()`, `totalLiquidity()` → @IReturn으로 concrete 가능. L2a blocker 해소.

**새로운 blocker: L1b** (paper Fig 8 의 L1b: loop-body-granularity 에 대응)

```solidity
uint256 _debt = vault.debts(address(this));  // vault = IVault → interface call → Top
...
uint256 _deductionFromIndex = (_debt * _totalCredit * MAGIC_SCALE_1E6) /
    totalLiquidity();                         // totalLiquidity() → vault.underlyingValue() → Top
```

- `_debt` = Top (interface call) → `_deductionFromIndex` = Top
- `_redeemAmount = _divCeil(Top, _shareOfIndex)` = **Top**
- buggy(나눗셈)든 correct(곱셈)든 Top → 구분 불가

**Loop body 변수의 수렴 여부**:
- `_index`, `_credit`, `_shareOfIndex`, `_redeemAmount` — 매 iteration 새로 선언 (declaration, not accumulation)
- Fixpoint iteration에서 join으로 수렴 가능 → loop-widening은 이들에 적용 안됨
- 유일한 accumulator `_actualDeduction += ...`만 widening 대상

**그러나 loop-widening은 부차적 문제**:
- `IIndexTemplate(_index).compensate(_redeemAmount)` → loop 내 interface call → 리턴값 Top
- `_actualDeduction += Top` → widening 없어도 이미 Top
- 근본 blocker는 interface call이지 loop widening이 아님

**Debugging annotation으로 해결 가능한가?**:
- `vault.debts()`, `totalLiquidity()` (loop 전 호출) → debugging annotation으로 concrete 가능
- 하지만 loop 내 `IIndexTemplate(_index).compensate()` → 매 iteration 다른 `_index`로 호출 → per-iteration 리턴값 지정 어려움
- 또한 bug line (709-711)이 loop body 내부 → intent annotation 배치 불가 (loop-body-granularity)

### 버그 코드
```solidity
function resume() external {
    ...
    uint256 _debt = vault.debts(address(this));           // interface call → Top
    uint256 _totalCredit = totalCredit;
    uint256 _deductionFromIndex = (_debt * _totalCredit * MAGIC_SCALE_1E6) /
        totalLiquidity();                                  // Top
    uint256 _actualDeduction;
    for (uint256 i = 0; i < indexList.length; i++) {
        address _index = indexList[i];
        uint256 _credit = indicies[_index].credit;
        if (_credit > 0) {
            uint256 _shareOfIndex = (_credit * MAGIC_SCALE_1E6) /
                _totalCredit;
            uint256 _redeemAmount = _divCeil(              // line 709: BUG — 나눗셈이 아니라 곱셈이어야 함
                _deductionFromIndex,                       // line 710: Top (from interface)
                _shareOfIndex                              // line 711
            );
            _actualDeduction += IIndexTemplate(_index).compensate(  // interface call → Top
                _redeemAmount
            );
        }
    }
    ...
}
```

---

## web3bugs_3_H_05

- **Contract**: CrossMarginAccounts
- **Function**: belowMaintenanceThreshold
- **Bug line (original)**: 203
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L2b: external-call-state-unknown)

### Bug Description
`belowMaintenanceThreshold()`에서 비교 방향이 반대. 함수 이름은 "maintenance threshold 이하인지"를 반환해야 하지만, 실제 구현은 건강한(healthy) 상태일 때 `true`를 반환:

```solidity
return 100 * holdings >= liquidationThresholdPercent * loan;  // BUG: >= should be < or <=
```

- `holdings >= loan * 1.1` → account가 건강 → `true` 반환
- 이름(`belowMaintenanceThreshold`)과 실제 반환값의 의미가 반대

### 탐지 불가 사유

**본질: external-call-state-unknown (L2b)**

`belowMaintenanceThreshold` → `loanInPeg` / `holdingsInPeg` → `sumTokensInPegWithYield` (loop) → `yieldTokenInPeg` → 외부 컨트랙트 호출:

```solidity
// yieldTokenInPeg (line 280):
uint256 yieldFP = Lending(lending()).viewBorrowingYieldFP(token);  // 외부 컨트랙트 호출 → Top

// yieldTokenInPeg (line 287):
return PriceAware.getCurrentPriceInPeg(...);                       // 외부 컨트랙트 호출 → Top
```

- `Lending`은 `import "./Lending.sol"`로 concrete type이 존재하나, 별도 deployment된 외부 컨트랙트
- `lending()`은 `RoleAware.mainCharacterCache[LENDING]`에서 address 반환 (type casting, not constructor)
- `Lending` 컨트랙트의 state variable에 debugging annotation 불가 → 내부 연산이 Top으로 흘러감
- `PriceAware.getCurrentPriceInPeg()`도 동일한 문제

**Call chain**:
```
belowMaintenanceThreshold
  → loanInPeg(account, true)
    → sumTokensInPegWithYield(account.borrowAmounts, account.borrowTokens, true)
      → for loop (index-bound)
        → yieldTokenInPeg(token, amount, true)
          → Lending(lending()).viewBorrowingYieldFP(token)  // Top
          → PriceAware.getCurrentPriceInPeg(...)            // Top
  → holdingsInPeg(account, true)
    → (동일 구조, 외부 호출로 Top)
```

**결과**:
- `loan` = Top (외부 호출 결과 누적)
- `holdings` = Top (동일)
- `100 * Top >= liquidationThresholdPercent * Top` → Top >= Top → **Top**
- buggy(`>=`)든 correct(`<`)든 결과가 모두 Top → 구분 불가

### 버그 코드
```solidity
function belowMaintenanceThreshold(CrossMarginAccount storage account)
    internal returns (bool)
{
    uint256 loan = loanInPeg(account, true);
    uint256 holdings = holdingsInPeg(account, true);
    // The following should hold:
    // holdings / loan >= 1.1
    // => holdings >= loan * 1.1
    return 100 * holdings >= liquidationThresholdPercent * loan;  // BUG: >= should be < or <=
}
```

---

## web3bugs_51_H_04

- **Contract**: SwapUtils (library)
- **Function**: getYC
- **Bug lines (original)**: 765; 767; 768
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L4a: inexpressible-expected-value)

### Bug Description
StableSwap AMM에서 amplifier를 2개(A1, A2) 사용하며, pool balance 비율(`xp[0]` vs `xp[1]`)에 따라 어떤 A를 쓸지 `determineA()`가 결정한다. Swap이 target price를 넘어 A가 전환될 때, 올바른 구현은 swap을 target price 기준으로 **2단계로 분할**하여 각각 A1, A2를 적용해야 한다.

그러나 `getYC()`는 A가 바뀌면 **새 A로 전체 swap을 재계산**한다:

```solidity
// 5. Check if we switched A's during the swap
if (aNew == a){     // We have used the correct A
    return y;
} else {    // We have switched A's, do it again with the new A
    return getY(self, tokenIndexFrom, tokenIndexTo, x, xp, aNew, d);  // BUG
}
```

`d`는 old `a`로 계산된 invariant인데, `aNew`와 함께 사용됨. 결과적으로 A2 커브를 전체 거래에 적용하여 실행 가격이 왜곡된다.

### 탐지 불가 사유

**본질: inexpressible-expected-value (L4a)**

**1. 질적 차이 없음**

`getYC`의 반환값은 `_calculateSwap` → `swap`을 거쳐 `self.balances[tokenIndexTo]`를 갱신한다:
- buggy: `balances[tokenIndexTo]` 감소 (잘못된 dy만큼)
- correct: `balances[tokenIndexTo]` 감소 (올바른 dy만큼)

둘 다 **같은 방향으로 변화**하므로 `Changed`, `Before > After` 등 질적 annotation으로 구분 불가.

**2. 올바른 값을 산술식으로 표현 불가**

올바른 결과를 구하려면:
1. **split point `dx₁`** 계산 — `xp[0] + dx₁ == xp[1] - getY(dx₁)`를 만족하는 dx₁ (방정식의 해, 단순 산술식 아님)
2. `getY(..., a, d)`로 부분 swap 1 수행
3. 중간 상태로 새 `d₂ = getD(중간상태, aNew)` 계산
4. `getY(..., aNew, d₂)`로 부분 swap 2 수행

이 중 `dx₁` (split point)가 코드에 존재하지 않는 값이며, 기존 변수의 `+`, `-`, `*`, `/` 조합으로 표현 불가 (자체가 비선형 방정식의 해). 따라서 `@Post return == expr` 형태의 annotation을 구성할 수 없다.

**3. 시도한 annotation 접근과 실패 사유**

| 접근 | 실패 사유 |
|------|----------|
| `return == concrete_value` | 올바른 값을 미리 계산해야 함 → 탐지가 아닌 답 제공 |
| `return == y` (old A로 계산한 값) | correct code도 `y`를 리턴하지 않음 (split 결과 ≠ y) → 양쪽 모두 violation |
| `getY.arg == a` (파라미터 제약) | "old A 유지"는 올바른 수정이 아님 (split이 정답) |
| `Changed`/`Before > After` on balances | buggy/correct 모두 동일하게 만족 |
| `getD([x, return], aNew) == getD(xp, aNew)` | annotation 내 함수 호출 불가 |

### Loop 수렴 여부 (참고)

`getY` 내부에 Newton's method loop (MAX_LOOP_LIMIT=256)이 있으나, debugging annotation으로 concrete value를 제공하면 ~4회 이내 수렴. **loop-widening은 blocker가 아님**. 핵심 blocker는 올바른 값의 표현 불가능성.

`getD` 내부의 Newton's method loop도 마찬가지로 concrete input에서 수렴.

첫 번째 loop (`for i < numTokens`)은 2-3회만 반복하는 index-bound loop으로 사실상 unroll.

---

## web3bugs_51_H_06

- **Contract**: SwapUtils (library)
- **Function**: addLiquidity
- **Bug line (original)**: 1231
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L4a: inexpressible-expected-value)

### Bug Description

StableSwap의 `addLiquidity`에서 imbalanced liquidity 추가 시 fee를 계산하기 위해 "ideal balance"를 구한다. 이 값은 `d1/d0 * old_balance`로 계산되며, d0과 d1이 같은 커브(같은 A 값) 위에 있어야 비율이 의미를 가진다.

그러나 이 컨트랙트는 dual-A 시스템(A1, A2)을 사용하며, `determineA()`가 토큰 비율(`xp[0]` vs `xp[1]`)에 따라 A를 선택한다:

```solidity
v.d0 = getD(self);
// → 내부: determineA(self, _xp(self)) → old balances 기준 A (예: A1)

v.preciseA = determineA(self, _xp(self, newBalances));
// → new balances 기준 A (예: A2, A가 전환될 수 있음)

v.d1 = getD(_xp(self, newBalances), v.preciseA);
// → A2로 계산된 D

idealBalance = v.d1.mul(self.balances[i]).div(v.d0);  // BUG (line 1231)
// d0은 A1 커브, d1은 A2 커브 → 서로 다른 커브의 D 비율은 무의미
```

imbalanced liquidity 추가로 토큰 비율이 역전되면 (`xp[0] < xp[1]` → `xp[0] > xp[1]`), d0과 d1이 서로 다른 A 값으로 계산되어 idealBalance가 틀림 → fee 계산 오류 → 최종 `self.balances[i]`와 `toMint` 모두 부정확.

### 탐지 불가 사유

**본질: inexpressible-expected-value (L4a)**

**1. 질적 차이 없음**

`addLiquidity` 후 `self.balances[i]`는 buggy/correct 모두 증가한다 (liquidity 추가 후 fee 차감). `Changed`, `Before < After` 등 질적 annotation으로 구분 불가.

**2. 올바른 값을 산술식으로 표현 불가**

올바른 `idealBalance`를 구하려면 d0과 d1을 **같은 A**로 계산한 `getD()` 결과가 필요:
- correct_d0 = getD(oldBalances, A_consistent)
- correct_d1 = getD(newBalances, A_consistent)
- correct_idealBalance = correct_d1 * old_balance / correct_d0

`getD()`는 Newton's method 반복(iterative) 함수이므로, annotation expression (`+`, `-`, `*`, `/` 조합)으로 표현 불가. annotation 내 함수 호출도 불가.

**3. 시도한 annotation 접근과 실패 사유**

| 접근 | 실패 사유 |
|------|----------|
| `Changed` / `Before < After` on self.balances | buggy/correct 모두 동일하게 만족 (둘 다 증가) |
| `self.balances[i] == expr` | 올바른 값이 getD() 호출 결과에 의존 → 산술식 표현 불가 |
| `getD(newBal, A_old) * bal / getD(oldBal, A_old)` | annotation 내 함수 호출 불가 |
| concrete value annotation | 올바른 값 자체를 수동 계산해야 함 → 탐지가 아닌 답 제공 |

### 참고: Newton loop 수렴 여부

51_H_04와 동일하게, `getD` 내부의 Newton's method loop는 concrete debugging annotation 하에서 ~4회 이내 수렴 가능. 따라서 loop-widening(L1)은 blocker가 아님. 핵심 blocker는 올바른 값의 표현 불가능성.

---

## web3bugs_70_H_10

- **Contract**: LiquidityBasedTWAP
- **Function**: syncVaderPrice
- **Bug line (original)**: 187
- **Pattern**: inconsistent_state_updates
- **Status**: `annotated`

### Bug Description

`syncVaderPrice()` → `_updateVaderPrice()` 호출 시 `previousPrices[uint256(Paths.VADER)]`가 갱신되지 않음. `setupVader()`에서 초기값 설정 후 한 번도 업데이트 안 됨. 시간이 지나면서 실제 VADER 가격과 괴리 → `currentLiquidityEvaluation` 왜곡 → TWAP 가격 부정확.

### 외부 타입 의존성

`ExchangePair` struct와 `Paths` enum은 `ILiquidityBasedTWAP` 인터페이스에 정의됨. `LiquidityBasedTWAP is ILiquidityBasedTWAP`로 상속.

- 이것은 L2(cross-deployment-call-top)와 **다름** — 외부 함수 호출이 아니라 **타입 상속**
- `twapData`는 target contract 자체의 storage → annotation scope 안
- 사전분석(dependency pre-analysis)에서 인터페이스의 struct/enum 정의를 resolve하면 됨

```
ILiquidityBasedTWAP (interface)
├── struct ExchangePair { lastMeasurement, updatePeriod, pastLiquidityEvaluation, ... }
├── enum Paths { VADER, USDV }
└── LiquidityBasedTWAP가 상속 → struct/enum 타입 사용 가능
```

### 루프 분석

`syncVaderPrice`의 루프 (line 90-111)에 `_totalLiquidityWeight += currentLiquidityEvaluation` (accumulation) 있음. 이건 70_H_03/04/05에서 loop-widening의 원인이었던 동일 루프.

그러나 이 버그의 annotation target은 `previousPrices[0]`이며, 루프 내에서 `previousPrices`에 대한 write는 (buggy code에서) **전혀 없음**. 따라서 `_totalLiquidityWeight`의 widening은 `previousPrices`의 Changed/Unchanged 판정에 영향 없음.

### Annotation 삽입 순서 및 라인 배치

**Step 1: Intent annotation 삽입** — contraction line 114 (`}` 직전)

```
113: totalLiquidityWeight[uint256(Paths.VADER)] = _totalLiquidityWeight;
114: // @Post Changed(previousPrices[0])      ← 삽입
115: }                                         ← 원래 114
```

**Step 2: Debug annotations 삽입** — line 85부터 (함수 body 시작 전, 8줄)

```
85: // @GlobalVar block.timestamp = [10000, 10000]
86: // @StateVar previousPrices[0] = [1000000000000000, 1000000000000000]
87: // @StateVar vaderPairs.length = [1, 1]
88: // @StateVar totalLiquidityWeight[0] = [1, 1]
89: // @StateVar twapData[1].lastMeasurement = [1000, 1000]
90: // @StateVar twapData[1].updatePeriod = [60, 60]
91: // @StateVar twapData[1].pastLiquidityEvaluation = [1, 1]
92: // @StateVar twapData[1].nativeTokenPriceCumulative = [0, 0]
93: uint256 _totalLiquidityWeight;            ← 원래 85
```

값은 Z3 constraint solving으로 결정 (`z3_solvers/web3bugs_70_H_10_solver.py`).
- `timeElapsed = 10000 - 1000 = 9000 >= updatePeriod(60)` → loop body 진입 보장
- `previousPrices[0] = 1e15` → 1e18 스케일 기준 0.001 VADER 가격

interpret 시 debug annotation으로 concrete 값 주입 → 분석 실행 → intent annotation 결과 출력.

### Z3 Constraints

debug annotation 값 결정 시 다음 제약 조건을 Z3로 풀어야 함:

1. **underflow 방지** (Solidity 0.8.9 checked arithmetic → revert 방지)
   - `block.timestamp >= twapData[1].lastMeasurement` (line 93: `block.timestamp - pairData.lastMeasurement`)
2. **loop body 진입 보장**
   - `block.timestamp - twapData[1].lastMeasurement >= twapData[1].updatePeriod` (line 95: `timeElapsed < updatePeriod`이면 continue)
3. **_updateVaderPrice 내부 overflow 방지**
   - `reserveNative * previousPrices[0]` overflow 없도록 (line 72-73)
   - `reserveForeign * chainlinkPrice` overflow 없도록 (line 74)
   - 단, `reserveNative`, `reserveForeign`은 외부 interface call → Top. constraint는 annotation 가능한 변수 범위 내에서 설정
4. **unchecked 블록 내 의미 있는 값**
   - `nativeTokenPriceCumulative(현재) >= twapData[1].nativeTokenPriceCumulative` (line 62-63, unchecked이라 revert는 안 하지만 의미 있는 분석을 위해)

### Debug Annotation 참고

- `block.timestamp` → GlobalVar로 설정 필요 (누락 시 분석 불가)
- `vaderPairs.length = [1, 1]` → 동적 배열 크기 설정 (DebugInitializer에서 `.length` 특별 처리 지원)
- `twapData[1]` → mapping의 리터럴 키 (address-keyed mapping에서 자동 AddressSet 변환)
- `twapData[1].lastMeasurement` 등 → mapping value의 struct 멤버 접근 (사전분석으로 ExchangePair struct 정의 필요)

### Intent Annotation 결과 예측

```
// @Post Changed(previousPrices[0])
```

- **Buggy**: `previousPrices[0]`에 write 없음 → Unchanged → `Changed` 위반 → **alarm**
- **Correct**: `previousPrices[0]`에 새 가격 기록 → Changed → **pass**

※ `Changed` 키워드는 Issue 2 (code_modification_issues.md) 구현 후 사용 가능. 현재 문법으로는 `previousPrices[0](Entry != Exit)`로 대체 가능 (buggy code에서 write 자체가 없으므로 Entry == Exit → 동일 효과).

---

## web3bugs_58_H_02

- **Contract**: LpIssuer
- **Function**: _chargeFees
- **Bug line (original)**: 270
- **Bug line (contraction)**: 85
- **Pattern**: erroneous_accounting
- **Status**: `annotated` (was: `not_detectable,interface-call-return-top`)

### Bug Description
Performance fee 계산 공식이 잘못됨. `toMint = (baseSupply * minLpPriceFactor) / DENOMINATOR`에서:
1. `minLpPriceFactor = lpPrice * DENOMINATOR / hwm` → lpPrice > hwm이면 항상 > DENOMINATOR
2. 따라서 `toMint > baseSupply` — 매번 전체 supply보다 많은 LP를 mint
3. `performanceFee` 비율이 계산에 아예 사용되지 않음 (> 0 체크만 하고 끝)
- Correct: `toMint = baseSupply * (minLpPriceFactor - DENOMINATOR) * performanceFee / (DENOMINATOR²)`
- Report: sponsor(MihanixA) confirmed

### Dependencies
**Libraries (사전 분석 필요):**
- `CommonLibrary.sol`: `DENOMINATOR = 10^9`, `PRICE_DENOMINATOR = 10^18`, `YEAR = 31536000` — constant, 인라인됨

**Interfaces:**
- `ILpIssuerGovernance`: `delayedProtocolParams()`, `delayedStrategyParams()`, `delayedProtocolPerVaultParams()`, `internalParams()`
- ERC20 상속: `_mint()` — totalSupply/balanceOf 변경

### 루프 분석
min-finding 패턴. accumulation(`+=`)이 아니고 monotonically non-increasing → widening 대상 아님. 배열 길이 concrete(=2) → 정확히 2회 unroll. **루프는 blocker가 아님.**

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| StateVar | lastFeeCharge | [0, 0] | 23 | elapsed 충분히 크도록 |
| StateVar | _lpPriceHighWaterMarks[0] | [1900000000000000000, 1900000000000000000] | 23 | 1.9e18, lpPrice(2e18)보다 작음 |
| StateVar | _lpPriceHighWaterMarks[1] | [2900000000000000000, 2900000000000000000] | 23 | 2.9e18, lpPrice(3e18)보다 작음 |
| LocalVar | thisNft | [1, 1] | 23 | NFT id |
| LocalVar | tvls[0] | [2000000000000000000000, 2000000000000000000000] | 23 | 2000e18 |
| LocalVar | tvls[1] | [3000000000000000000000, 3000000000000000000000] | 23 | 3000e18 |
| LocalVar | supply | [1000000000000000000000, 1000000000000000000000] | 23 | 1000e18 |
| LocalVar | deltaTvls[0] | [100000000000000000000, 100000000000000000000] | 23 | 100e18 (isWithdraw=false, 미사용) |
| LocalVar | deltaTvls[1] | [150000000000000000000, 150000000000000000000] | 23 | 150e18 |
| LocalVar | deltaSupply | [100000000000000000000, 100000000000000000000] | 23 | 100e18 |
| LocalVar | isWithdraw | false | 23 | baseSupply = supply |
| IReturn | vg.delayedProtocolParams().managementFeeChargeDelay | [0, 0] | 23 | delay=0, early return 방지 |
| IReturn | vg.delayedStrategyParams().managementFee | [0, 0] | 23 | skip management fee |
| IReturn | vg.delayedStrategyParams().performanceFee | [100000000, 100000000] | 23 | 10^8 = 10% (> 0) |
| IReturn | vg.delayedStrategyParams().strategyPerformanceTreasury | symbolicAddress 1 | 23 | mint 대상 |
| IReturn | vg.delayedProtocolPerVaultParams().protocolFee | [0, 0] | 23 | skip protocol fee |

- isWithdraw=false → baseSupply = supply = 1000e18
- baseTvls[0] = 2000e18, baseTvls[1] = 3000e18
- lpPrice[0] = 2e18 > hwm(1.9e18) ✓, lpPrice[1] = 3e18 > hwm(2.9e18) ✓
- delta[0] ≈ 1052631578, delta[1] ≈ 1034482758 (둘 다 > DENOMINATOR)
- minLpPriceFactor = 1034482758
- Buggy: toMint = 1000e18 * 1034482758 / 10^9 ≈ 1034.48e18 > baseSupply(1000e18)
- Correct: toMint ≈ 3.45e18 << baseSupply

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| During | 85 | toMint < baseSupply | violated | Performance fee는 이익의 일부 → totalSupply 초과 mint 불가. Buggy: 1034e18 > 1000e18 → violated |

---

## web3bugs_29_H_14

- **Contract**: IndexPool
- **Function**: _computeSingleOutGivenPoolIn
- **Bug line (original)**: 279
- **Pattern**: erroneous_accounting
- **Status**: excluded (overflow-revert)

### Bug Description
`_computeSingleOutGivenPoolIn`이 `_pow(poolRatio, _div(BASE, normalizedWeight))`를 호출하는데, `_div(BASE, normalizedWeight)`는 WAD 단위(18 decimals) 값을 반환함. 그러나 `_pow(a, n)`은 `n`을 plain integer로 취급하므로, 예를 들어 weight가 25%면 exponent가 `4 * 10^18`이 되어 `a^(4*10^18)`을 계산 시도 → integer overflow → revert.

올바른 호출은 `_compute(poolRatio, _div(BASE, normalizedWeight))`이며, `_compute`는 WAD 단위 exponent를 whole/fractional로 분리하여 처리함.

### Excluded 사유
- Solidity >=0.8.0에서 overflow는 자동 revert됨 (checked arithmetic)
- 조용히 잘못된 값을 반환하는 것이 아니라 실행 자체가 중단됨
- **Numeric logical error 정의에 해당하지 않음**: compile 단계 통과 후 실행 시 잘못된 값을 "반환"하는 것이 아니라, overflow로 인해 revert되는 문제

---

## web3bugs_29_H_15

- **Contract**: IndexPool
- **Function**: _computeSingleOutGivenPoolIn
- **Bug line (original)**: 282
- **Pattern**: erroneous_accounting
- **Status**: excluded (overflow-revert)

### Bug Description
Line 282에서 `(BASE - normalizedWeight) * _swapFee`로 raw `*`를 사용하나, fixed-point 곱셈 `_mul`을 써야 함. raw `*` 결과가 BASE^2 스케일이 되어, 이후 `BASE - zaz`에서 integer underflow → Solidity 0.8.x revert.

### Excluded 사유
- 29_H_14와 동일한 함수, 동일한 exclusion 사유
- Underflow로 인해 revert되는 문제로, 잘못된 값을 반환하는 numeric logical error가 아님

---

## web3bugs_112_H_01

- **Contract**: StakerVault
- **Function**: transfer
- **Bug lines (original)**: 112; 113; 117; 118
- **Bug lines (contraction)**: 31; 32; 36; 37 (annotation 삽입 후: 31; 32; 37; 39)
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L5b: wrong-code)`

### Bug Description
`transfer()`에서 `balances` 업데이트(contraction line 31-32)가 `userCheckpoint()` 호출(contraction line 37, 39) **전에** 실행됨. `userCheckpoint()`는 내부적으로 `stakedAndActionLockedBalanceOf(user)` → `balances[user]`를 읽어 보상을 계산하므로, 이미 변경된 balance로 보상이 계산됨. 수신자가 반복적으로 자기 계정 간 transfer하면서 보상을 과다 청구 가능.

대조: 같은 컨트랙트의 `transferFrom()`(original line 155-158)은 올바르게 **checkpoint → balance 변경** 순서.

### Not Detectable 사유 (L5b: wrong-code — operation ordering)

**유일하게 가능한 intent**: `@During changed(balances[msg.sender], false)` (standalone, checkpoint 호출 직전)

**Bug awareness가 필요한 이유**:
1. `balances[msg.sender] -= amount` (line 31)에서 이미 변경된 것이 같은 함수 내에서 **5줄 위에 보임**
2. 그 아래에서 "unchanged여야 한다"고 쓰는 것은, "이 변경이 checkpoint 뒤에 와야 한다"는 ordering 지식을 전제
3. 개발자가 코드를 읽으면서 "여기서 balance가 바뀌었으니 unchanged annotation을 달아야지"라고 자연스럽게 쓸 수 없음 — 이미 바뀐 변수에 "unchanged"를 쓰는 건 모순
4. 올바른 순서(checkpoint → balance 변경)를 이미 알아야 annotation 작성 가능 → 그 지식이 있었으면 코드 순서를 직접 고쳤을 것

**Report 원문**: "In every actionable function except `transfer()`, a call to `userCheckpoint()` is correctly made BEFORE the action effects." — 감사자도 다른 함수와의 일관성 비교로 버그 발견. 이 비교 자체가 bug awareness.

### Dependencies
**Interfaces** (6):
- IStakerVault, IController, IAddressProvider, IERC20, ILiquidityPool, ILpGauge

**Libraries** (3):
- AddressProviderHelpers, SafeERC20, ScaledMath

**Contracts** (4):
- Authorization, Pausable, Initializable, Preparable

**기타**:
- Error (require 메시지용 라이브러리/contract)
- Transfer event (IStakerVault에 정의 추정)

### Intent Annotations (standalone)
| Type | Line (contraction, annotation 삽입 후) | Expression | Expected | Comment |
|------|---------------------------------------|------------|----------|---------|
| During | 36 (standalone, 대상: line 37) | Unchanged(balances[msg.sender]) | violated | checkpoint 시점에 balances[msg.sender]가 이미 변경됨 (line 31) → Entry ≠ Current → violated |
| During | 38 (standalone, 대상: line 39) | Unchanged(balances[account]) | violated | checkpoint 시점에 balances[account]가 이미 변경됨 (line 32) → Entry ≠ Current → violated |

### Debug Annotations
**LocalVar:**
| # | Variable | Value (interval) | Comment |
|---|----------|-------------------|---------|
| 1 | account | symbolicAddress 1 | 수신자 |
| 2 | amount | [100, 100] | 전송량 |

**StateVar:**
| # | Variable | Value (interval) | Comment |
|---|----------|-------------------|---------|
| 1 | balances[101] | [200, 200] | balances[msg.sender], require 통과용 |
| 2 | balances[1] | [0, 0] | balances[account] |
| 3 | currentAddresses[_LP_GAUGE] | symbolicAddress 2 | if 분기 진입용 (≠ address(0)), 피상속 상태변수 (Preparable) |

**입력 조건:**
- balances[101] >= amount (require 통과)
- currentAddresses[_LP_GAUGE] != address(0) (if 분기 진입)

**실행 후 검증:**
- balances[101] = 200 - 100 = 100 ≠ Entry(200) → Unchanged **violated** ✓
- balances[1] = 0 + 100 = 100 ≠ Entry(0) → Unchanged **violated** ✓

### Notes
- `@During Unchanged(var)` = "이 program point에서 var의 Current 값이 Entry 값과 같아야 한다"
- 버기 코드: balance 변경 → checkpoint → Unchanged violated → 탐지
- 정상 코드: checkpoint → balance 변경 → checkpoint 시점에 Unchanged satisfied
- `@During Unchanged` 구현 필요 (code_modification_issues.md Issue 2)
- standalone annotation 지원 필요 (code_modification_issues.md Issue 1)
- `userCheckpoint()`는 ILpGauge interface 호출 → 외부 컨트랙트 효과이나, annotation 대상은 StakerVault 내부의 `balances` 상태변수
- `currentAddresses`는 Preparable에서 상속된 상태변수 → 피상속 상태변수에 대한 debug annotation 가능 여부 확인 필요

### 버그 코드 (contraction, annotation 삽입 후)
```solidity
function transfer(address account, uint256 amount) external override notPaused returns (bool) {
    require(msg.sender != account, Error.SELF_TRANSFER_NOT_ALLOWED);
    require(balances[msg.sender] >= amount, Error.INSUFFICIENT_BALANCE);

    ILiquidityPool pool = controller.addressProvider().getPoolForToken(token);
    pool.handleLpTokenTransfer(msg.sender, account, amount);

    balances[msg.sender] -= amount;       // line 31: balance 먼저 변경
    balances[account] += amount;           // line 32: balance 먼저 변경

    address lpGauge = currentAddresses[_LP_GAUGE];
    if (lpGauge != address(0)) {
        // @During Unchanged(balances[msg.sender])          // line 36: standalone annotation
        ILpGauge(lpGauge).userCheckpoint(msg.sender);       // line 37: checkpoint 나중 → BUG
        // @During Unchanged(balances[account])              // line 38: standalone annotation
        ILpGauge(lpGauge).userCheckpoint(account);          // line 39: checkpoint 나중 → BUG
    }

    emit Transfer(msg.sender, account, amount);
    return true;
}
```

---

## web3bugs_24_H_03

- **Contract**: SwappableYieldSource
- **Function**: setYieldSource
- **Bug lines (original)**: 258; 268; 269
- **Pattern**: inconsistent_state_updates
- **Status**: excluded (multi-transaction)

### Notes
- 버그는 `setYieldSource()` 호출 후 `transferFunds()` 호출 전 사이에 `supplyTokenTo()`가 호출되면 exchange rate가 왜곡되는 문제
- yieldSource는 변경되었지만 자금은 아직 이전되지 않아 `balanceOfToken()`이 0에 가까운 값을 반환 → 비정상적으로 많은 shares 발행
- 이는 두 개의 독립 트랜잭션 간의 상태 불일치 문제 (multi-transaction)이므로 single-transaction 분석 범위 밖 → excluded

---

## web3bugs_39_H_02

- **Contract**: Swivel
- **Function**: exitVaultFillingVaultInitiate
- **Bug lines (original)**: 280
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L4a: inexpressible-expected-value)

### Bug Description
`exitVaultFillingVaultInitiate`에서 taker(msg.sender)에게 수수료가 2번 부과됨:
1. Line 280: `transferFrom(o.maker, msg.sender, premiumFilled - fee)` — 받는 금액에서 fee 차감
2. Line 283: `transferFrom(msg.sender, address(this), fee)` — fee를 별도로 또 지불

결과적으로 sender의 순수익은 `premiumFilled - 2*fee`이며, 의도된 값은 `premiumFilled - fee`.

### Not Detectable 사유
- 각 `transferFrom` 호출의 인자 값은 개별적으로 모두 정확함 (`premiumFilled - fee`, `fee` 각각 올바른 계산 결과)
- 버그는 두 external call의 **조합**에서 발생: fee 부담 주체가 잘못 설정되어 sender가 이중 부담
- sender의 순수익(net token flow)을 표현하려면 외부 ERC20 contract의 balance 변화를 추적해야 하나, 이는 분석 대상 contract의 state variable이 아님
- 단일 program point에서 어떤 변수나 산술 조합으로도 "sender가 fee를 이중으로 지불하고 있다"는 사실을 표현할 수 없음 → inexpressible-expected-value

---

## web3bugs_52_H_09

- **Contract**: VaderReserve
- **Function**: reimburseImpermanentLoss
- **Bug lines (original)**: 85
- **Pattern**: erroneous_accounting
- **Status**: excluded (bug-not-in-target-contract)

### Notes
- 버그 제목은 "VaderPoolV2 incorrectly calculates the amount of IL protection to send to LPs"
- 실제 IL protection 금액 계산은 호출자인 VaderPoolV2에서 수행되며, VaderReserve의 `reimburseImpermanentLoss`는 전달받은 amount를 reserve 잔액과 비교 후 전송하는 단순 로직
- 권장 수정: VADER/USDV 간 conversion rate를 oracle(TwapOracle)로 처리 → VaderPoolV2 측 설계 변경 필요
- 타겟 contract(VaderReserve)에 계산 오류가 없으므로 excluded

---

## web3bugs_52_H_23

- **Contract**: VaderPoolV2
- **Function**: mintSynth
- **Bug lines (original)**: 161
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L5a: missing-code)

### Bug Description
`mintSynth`에서 synth 발행 후 `_update` 호출 시 `reserveForeign`을 차감하지 않아 synth가 과다 발행됨:
- Buggy (line 158-164): `_update(foreignAsset, reserveNative + nativeDeposit, reserveForeign, ...)`
- Correct: `_update(foreignAsset, reserveNative + nativeDeposit, reserveForeign - amountSynth, ...)`

### Dependency 현황
BasePoolV2.sol, VaderMath.sol 등 모든 dependency 확보 완료 (Web3Bugs 원본에서 복사). VaderMath.calculateSwap은 pure 함수, inline assembly 없음 → 분석 가능.

### Not Detectable 사유 (L5a: missing-code)
`_update` 호출 시 `reserveForeign`에서 `amountSynth`를 빼는 코드가 **누락**됨. `@Intent`로 "synth 발행 후 foreign reserve가 줄어야 한다"고 표현은 가능하나, 이 intent를 작성하려면 `- amountSynth` 누락을 이미 인지하고 있어야 함 → bug awareness 전제.

annotated 케이스(5_H_07: 주석이 spec, 5_H_12: 변수 의미론에서 자연스러운 intent 도출)와 달리, 이 케이스는 synth 발행의 회계 규칙에 대한 도메인 지식 + 버그 인지가 있어야 intent 작성 가능.

---

## web3bugs_5_H_07

- **Contract**: Utils
- **Function**: calcAsymmetricShare
- **Bug line (original)**: 273
- **Bug line (contraction)**: 22
- **Pattern**: erroneous_accounting
- **Status**: annotated

### Bug Description
`calcAsymmetricShare` 함수의 수식 구현에서 괄호 누락 버그. 주석에 의도된 수식은 `(part1 * (part2 - part3 + part4)) / part5` = `u*A*(2*U*U - 2*U*u + u*u) / (U*U*U)` 이나, 실제 코드(line 22)는 `((part1 * part2) - part3) + part4`로 구현되어 part3과 part4가 part1에 곱해지지 않음.

### Dependencies
없음

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| LocalVar | u | [100, 100] | 18 | 함수 파라미터, u < U 조건 충족 |
| LocalVar | U | [1000, 1000] | 19 | 함수 파라미터, total units |
| LocalVar | A | [5000, 5000] | 20 | 함수 파라미터, total amount |

- overflow/underflow 검증: part1*part2 = 100*5000*2*10^6 = 10^12 (uint256 안전), part2-part3 = 2*10^6 - 2*10^5 = 1.8*10^6 > 0 (underflow 없음)

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| During | 24 | returnExpression == u*A*(2*U*U - 2*U*u + u*u) / (U*U*U) | violated | 5.md H-07: 주석에 명시된 의도 수식과 실제 구현 불일치. 올바른 결과 905 vs 버그 결과 ~999 |

---

## web3bugs_5_H_08

- **Contract**: Utils
- **Function**: calcLiquidityUnits
- **Bug line (original)**: 239
- **Bug line (contraction)**: 40
- **Pattern**: erroneous_accounting
- **Status**: annotated

### Bug Description
`calcLiquidityUnits` 함수의 수식 구현에서 괄호 누락 버그. 주석에 의도된 수식은 `P * (t*B + T*b) / (2*T*B) * slipAdjustment`이나, 실제 코드(line 40)는 `(P * part1 + part2) / part3`으로 구현되어 `P`가 `part1`(`t*B`)에만 곱해지고 `part2`(`T*b`)에는 곱해지지 않음. 5_H_07과 동일한 괄호 누락 패턴.

### Dependencies
없음 (getSlipAdustment는 같은 컨트랙트 내 함수)

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| LocalVar | b | [100, 100] | 33 | 함수 파라미터, base deposited |
| LocalVar | B | [1000, 1000] | 34 | 함수 파라미터, base balance |
| LocalVar | t | [100, 100] | 35 | 함수 파라미터, token deposited |
| LocalVar | T | [1000, 1000] | 36 | 함수 파라미터, token balance |
| LocalVar | P | [500, 500] | 37 | 함수 파라미터, total pool units, P > 0으로 else 분기 진입 |

- state variable `one = 10**18`은 컨트랙트에 이미 초기화됨
- overflow/underflow 검증: 대칭 입금(b/B == t/T)으로 slipAdjustment = one. 올바른 _units=50, 버그 _units=25

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| During | 40 | _units == P * (t * B + T * b) / ((T * B) * 2) | violated | 5.md H-08: 주석에 명시된 의도 수식 `P*(tB+Tb)/(2TB)`와 실제 구현 불일치. 올바른 결과 50 vs 버그 결과 25 |

---

## web3bugs_29_H_05

- **Contract**: HybridPool
- **Function**: _nonOptimalMintFee
- **Bug line (original)**: 433
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L4a: inexpressible-expected-value)

### Bug Description
`_nonOptimalMintFee`에서 optimal deposit ratio를 `(_amount0 * _reserve1) / _reserve0`으로 계산하는데, 이는 constant-product AMM 공식. HybridPool은 stableswap 방식이므로 optimal ratio가 reserve 비율과 다름 (amplification parameter A에 의해 커브가 flat). 결과적으로 fee가 과대/과소 계산됨.

### Not Detectable 사유 (L4a)
- 올바른 optimal ratio는 stableswap invariant D에 의존하며, D는 Newton's method 반복(loop)으로 계산됨
- 올바른 fee 값을 프로그램 내 기존 변수의 산술 조합으로 표현할 수 없음
- fee의 크기 자체는 정상 범위(0 ~ swapFee) 내에 있어 단순 bound annotation으로 구분 불가

---

## web3bugs_52_H_25

- **Contract**: VaderMath (library)
- **Function**: calculateSwap
- **Bug line (original)**: 105
- **Pattern**: erroneous_accounting
- **Status**: excluded (not-a-bug)

### Notes
- 수식 `x * X * Y / (x + X)^2`는 Thorchain CLP 모델의 의도된 설계
- Sponsor가 명시적으로 dispute: "This is the intended design of the Thorchain CLP model"
- Judge도 sponsor 입장을 사실상 수용
- 코드 구현이 주석과 일치하며, 수식 자체에 computation error 없음
- `amountIn > reserveIn`일 때 output이 감소하는 현상은 CLP 모델의 고유 특성

---

## web3bugs_56_H_02

- **Contract**: CDP (library)
- **Function**: update
- **Bug line (original)**: 39
- **Bug line (contraction)**: 41
- **Pattern**: erroneous_accounting
- **Status**: annotated

### Bug Description
`update()` 함수에서 `_earnedYield > totalDebt`일 때 `totalCredit`을 누적(+=)하지 않고 덮어쓰기(=)함. 기존 credit이 소실됨.
- Buggy (line 41): `_self.totalCredit = _earnedYield.sub(_currentTotalDebt);`
- Correct: `_self.totalCredit = _self.totalCredit.add(_earnedYield.sub(_currentTotalDebt));`
- `getUpdatedTotalCredit` (view 함수)에서는 올바르게 `_self.totalCredit + (yield - debt)`로 누적 — 의도 확인 가능
- Report: sponsor 최종 confirmed

### Dependencies
- FixedPointMath library (FixedDecimal struct, sub/mul/cmp/decode 등)
- SafeMath library (using SafeMath for uint256)
- Issue 4 (code_modification_issues.md): `using` 키워드 커스텀 라이브러리 지원 필요

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| StateVar | _self.totalCredit | [1000, 1000] | 37 | 기존 credit 양수 — overwrite 버그 시현 |
| StateVar | _self.totalDebt | [0, 0] | 37 | debt 상환 완료 상태, earnedYield > 0이면 if 분기 진입 |
| StateVar | _self.totalDeposited | [1000, 1000] | 37 | getEarnedYield 계산에 필요 |
| StateVar | _self.lastAccumulatedYieldWeight.x | [1000000000000000000, 1000000000000000000] | 37 | 1e18 (fixed-point 1.0) |
| StateVar | _ctx.accumulatedYieldWeight.x | [1200000000000000000, 1200000000000000000] | 37 | 1.2e18 (fixed-point 1.2) |

- earnedYield = (1.2e18 - 1e18) * 1000 / 1e18 = 200
- totalDebt = 0이므로 earnedYield(200) > totalDebt(0) → if 분기 진입
- Buggy: totalCredit = 200 - 0 = 200 (1000에서 200으로 덮어씀)
- Correct: totalCredit = 1000 + (200 - 0) = 1200

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| Post | 46 | totalCredit(entry <= exit) | violated | 56.md H-02: update 호출 시 credit은 감소하지 않아야 함. Buggy code에서 entry(1000) > exit(200) → violated |

---

## web3bugs_60_H_01

- **Contract**: OptimisticLedgerLib
- **Function**: settleAccount
- **Bug lines (original)**: 68; 73
- **Pattern**: erroneous_accounting
- **Status**: annotated

### Bug Description
`settleAccount()`에서 shortfall이 이중 계산됨. `shortfall` (local) = `self.shortfall + |newBalance|`로 기존 shortfall을 포함시킨 뒤, `self.shortfall = self.shortfall + shortfall`로 또 기존 shortfall을 더함.
- Buggy: `self.shortfall = 2 * old_shortfall + |newBalance|`
- Correct: `self.shortfall = old_shortfall + |newBalance|`
- Report: sponsor(kbrizzle) confirmed, judge 동의

### Dependencies
- Fixed18.sol (Fixed18Lib, `type Fixed18 is int256;`)
- UFixed18.sol (UFixed18Lib, `type UFixed18 is uint256;`)
- Issue 4 (code_modification_issues.md): `using` 키워드 커스텀 라이브러리 지원 필요
- Issue 5 (code_modification_issues.md): user-defined value type 지원 필요

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| StateVar | self.shortfall | [100, 100] | 15 | 비제로 필수 — shortfall 이중 계산 버그 시현 |
| StateVar | self.balances[account] | [50, 50] | 15 | account balance |
| LocalVar | amount | [-100, -100] | 15 | Fixed18 음수값 — newBalance를 음수로 만듦 |

- newBalance = 50 + (-100) = -50 → 음수, if 분기 진입
- |newBalance| = 50
- Buggy: shortfall(local) = 100 + 50 = 150, self.shortfall = 100 + 150 = 250
- Correct: self.shortfall = 100 + 50 = 150

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| During | 23 | self.shortfall == 150 | violated | 60.md H-01: shortfall 이중 계산. 정상이면 150이어야 하나 buggy code에서 250 → violated |

---

## web3bugs_77_H_01

- **Contract**: MathLib
- **Function**: calculateLiquidityTokenQtyForSingleAssetEntry
- **Bug lines (original)**: 174-185
- **Pattern**: erroneous_accounting
- **Status**: annotated

### Bug Description
Single asset entry 시 LP 토큰 수량(ΔRo) 계산을 위한 gamma(γ) 공식이 잘못됨. 과소 계산으로 새 LP가 기여 대비 적은 지분을 받아 자금 손실 발생.
- Buggy gamma: `γ = ΔY / Y' / 2 * (ΔX / α^)` — 과소 계산
- Report 예시: LP가 4 quoteToken 기여 → 2.67 quoteToken 가치만 수령 (1.33 손실)
- 정확한 올바른 공식은 report 본문에 불완전하게 제시됨 (issue page 참조), sponsor도 제안 수정이 "partially correct"이라고 언급
- **탐지 전략**: 정확한 공식 대신 경제적 공정 지분 하한값(proportional fairness bound) 사용
- Report: sponsor(0xean) confirmed & resolved, judge High severity 동의

### Dependencies
- 없음 (wDiv, wMul이 같은 library 내 정의, pure function)

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| LocalVar | _totalSupplyOfLiquidityTokens | [1000, 1000] | 35 | Ro = sqrt(X*Y), X=1000, Y=1000 |
| LocalVar | _tokenQtyAToAdd | [4000, 4000] | 36 | ΔY (quoteToken added by LP) |
| LocalVar | _internalTokenAReserveQty | [5000, 5000] | 37 | Y' = Y + ΔY = 1000 + 4000 |
| LocalVar | _tokenBDecayChange | [4000, 4000] | 38 | ΔX = ΔY * Omega (Omega=1) |
| LocalVar | _tokenBDecay | [9000, 9000] | 39 | Alpha - X = 10000 - 1000 |

- Report rebase-up 예시 기반: Alpha=10000, X=1000, Y=1000, Omega=1, LP adds 4000 quoteToken
- wGamma = 16/90 * WAD ≈ 1.777e17
- Buggy ΔRo ≈ 216
- Fair ΔRo = Ro * 4/11 ≈ 363 (LP 기여 4000 / pool total 15000 = 4/15 지분)

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| Post | 38 | returnExpression >= 363 | violated | 77.md H-01: gamma 과소 계산. Fair ΔRo ≥ 363이어야 하나 buggy code에서 ≈216 → violated |

---

## web3bugs_31_H_01

- **Contract**: MyStrategy
- **Function**: manualRebalance
- **Bug lines (original)**: 469; 471; 477
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L5b: wrong-code)`

### Bug Description
`manualRebalance()`에서 두 변수의 단위가 다른데 비교함:
- Line 469: `currentLockRatio = balanceInLock * 1e18 / totalCVXBalance` → **비율** (percentage, max 1e18)
- Line 471: `newLockRatio = totalCVXBalance * toLock / MAX_BPS` → **절대 CVX 수량** (token amount)
- Line 477: `if (newLockRatio <= currentLockRatio)` → 비율과 수량을 비교 → 잘못된 분기
- Report의 권장 수정: `currentLockRatio`를 `balanceInLock` (amount)으로 변경. `cvxToLock = newLockRatio.sub(currentLockRatio)`의 사용처에서 역추론.
- Report: sponsor(GalloDaSballo) confirmed, mitigated by rewriting

### Not Detectable 사유 (L5b: wrong-code)
- Interface call은 이제 지원되어 `balanceOf()`, `getPricePerFullShare()` 등 반환값은 TOP이 아님
- 그러나 버그는 `currentLockRatio` 계산식의 dimensional mismatch: percentage(1e18 precision)로 계산했으나 실제로는 amount여야 함
- 올바른 식(`currentLockRatio = balanceInLock`)을 알려면 하류 코드(line 488: `cvxToLock = newLockRatio.sub(currentLockRatio)` → CVX 수량으로 사용)의 차원 분석이 필요
- 감사자(cmichel)도 "Judging from the `cvxToLock = ...`"로 하류 사용처에서 올바른 의미를 역추론
- 어떤 annotation이든 두 변수의 단위가 같아야 한다는 전제 필요 → dimensional mismatch 인지 = bug awareness

---

## web3bugs_16_H_04

- **Contract**: Balances
- **Function**: applyTrade
- **Bug lines (original)**: 187
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L3: unsupported-construct-top)

### Bug Description
`applyTrade()`에서 Long 포지션의 fee 부호가 반대:
- Line 187: `newQuote = position.quote - quoteChange + fee` (buggy: fee를 더함)
- Correct: `newQuote = position.quote - quoteChange - fee` (fee를 빼야 함)
- Short 포지션(line 190)은 올바르게 `- fee` 처리
- Report: sponsor(raymogg) confirmed

### Not Detectable 사유
PRBMath dependency 확보 완료 (npm에서 설치 후 복사). 그러나 PRBMath 라이브러리 내부 핵심 함수(`mulDivFixedPoint`, `mulDiv`)가 inline assembly를 사용하여 분석 불가:
- `quoteChange = PRBMathSD59x18.mul(signedAmount, signedPrice)` → assembly 내부 → TOP
- `fee = getFee(...)` → `PRBMathUD60x18.mul` → assembly 내부 → TOP
- `newQuote = position.quote - TOP + TOP` → TOP → buggy/correct 구분 불가

---

## web3bugs_62_H_01

- **Contract**: Stream
- **Function**: recoverTokens
- **Bug lines (original)**: 654
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L4b: wrong-code — wrapper no state, balanceOf inline chain)`

### Bug Description
`recoverTokens()`에서 excess depositToken 계산 시 `depositTokenFlashloanFeeAmount`을 빼지 않음. stream creator가 flashloan fee를 회수할 수 있어 governance의 fee 청구 또는 사용자 출금이 실패할 수 있음.
- Buggy (line 654): `excess = balanceOf(this) - (depositTokenAmount - redeemedDepositTokens)`
- Correct: `excess = balanceOf(this) - (depositTokenAmount - redeemedDepositTokens) - depositTokenFlashloanFeeAmount`
- Report: sponsor(brockelmore) confirmed

### Not Detectable 사유 (L4b: wrong-code)
- **L4b 재분류 근거** (l4_l5_classification.csv reclass_reason: `annotation_plans_L5a_but_wrapper_no_state_balanceOf_inline_chain_I9_principle`)
- 이전 L2a (interface-call-return-top) 분류는 잘못됨 — interface 는 이제 지원되므로 L2a 아님
- `recoverTokens()` 는 wrapper 함수로 state 변경 없음 (safeTransfer 만). `balanceOf()` 결과가 named variable 로 저장되지 않고 inline chain 으로만 사용됨 → annotation grammar 의 Post/During 대상 state/local var 부재
- I9 principle (grammar expressibility 우선) 에 따라 "missing term (depositTokenFlashloanFeeAmount 차감) bug awareness" 층보다 "wrapper no state + balanceOf inline" 의 구조적 한계가 상위 → L4b
- Case9 wrapper family archetype

---

## web3bugs_44_H_02
- **Status**: `not_detectable (L3: unsupported-construct-top)`
- **Contract**: Swap
- **Function**: fillZrxQuote()
- **Bug lines**: 210 (originalETHBalance), 215 (ethDelta)

### Bug 설명
`fillZrxQuote()`에서 balance snapshot을 잘못된 시점에 캡처:
1. ETH: `originalETHBalance = address(this).balance` — 이미 `msg.value`가 포함된 상태. ETH refund가 있어도 `subOrZero(newBalance, originalETHBalance)` = 0
2. ERC20: 같은 토큰 arb 시 `originalERC20Balance = balanceOf(this)` — 입력량이 이미 포함. delta가 실제보다 과소 계산
- Buggy: `ethDelta = address(this).balance.subOrZero(originalETHBalance)` (originalETHBalance에 msg.value 포함)
- Correct: `originalETHBalance = address(this).balance - msg.value`로 보정 필요
- Report: sponsor(Shadowfiend) confirmed

### Not Detectable 사유 (L3: unsupported-construct-top)
- ~~`address(this).balance` → TOP~~ → Issue 7 구현으로 GlobalVar 제공 가능 ✅
- **`zrxTo.call{value: ethAmount}(zrxData)`** → low-level `.call()`, 구현 코드 없음 → side effect 불명 (primary blocker)
- `.call()` 후 `address(this).balance` 재읽기 → balance가 `.call()`에 의해 변했을 수 있으나 추적 불가
- `zrxBuyTokenAddress.balanceOf()` → interface call이나 low-level call 이후 state 변화 추적 불가
- low-level `.call()`의 side effect가 unsupported construct → L3 유지

---

## web3bugs_66_H_02
- **Status**: excluded_fixed_code
- **Contract**: sYETIToken
- **Function**: rebase()
- **Bug line**: 297

### 사유
Web3Bugs repo의 코드가 이미 수정된 버전. buggy 코드에서는 `yetiTokenBalance` (whole balance)와 비교했으나, 현재 코드는 `adjustedYetiTokenBalance = yetiTokenBalance.sub(effectiveYetiTokenBalance)` (extra balance)와 비교. `_getValueOfContract` 수식도 변경됨.

---

## web3bugs_70_H_08
- **Status**: `not_detectable (L4b: wrong-code — wrapper no state, parameter overwrite)`
- **Contract**: VaderReserve
- **Function**: reimburseImpermanentLoss()
- **Bug lines**: 98, 102

### Bug 설명
IL(Impermanent Loss) 보상금 계산 시 fixed-point 스케일링 누락:
- Buggy (line 98): `amount = amount / usdvPrice` — usdvPrice가 1e18 스케일 → 결과 1e18배 과소
- Buggy (line 102): `amount = amount * vaderPrice` — vaderPrice가 1e18 스케일 → 결과 1e18배 과대
- Correct: `amount * 1e18 / usdvPrice`, `amount * vaderPrice / 1e18`
- Report: sponsor 미확인 (judge resolved)

### Not Detectable 사유 (L4b: wrong-code)
- **L4b 재분류 근거** (l4_l5_classification.csv reclass_reason: `annotation_plans_L5a_but_wrapper_no_state_parameter_overwrite_original_lost`)
- wrapper 함수, self-state 없음 — 어떤 @Post state invariant 도 대상 없음
- `amount` 파라미터가 line 98/102 에서 overwrite 되어 원본 값이 program 내 named var 로 보존되지 않음 → annotation grammar 로 correct scaling (`amount * 1e18 / usdvPrice`) 표현 불가 (원본 amount 가 scope 에서 사라짐)
- I9 principle 에 따라 "스케일 팩터 인지 부족 (L5a 후보)" 보다 구조적 expressibility (wrapper + parameter overwrite) 가 선행 → L4b
- Case1/Case10 wrapper version archetype (scaling factor missing 1e18)

---

## web3bugs_42_H_01
- **Contract**: MochiVault
- **Function**: borrow()
- **Bug line (original)**: 248
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L2a: interface-call-return-top)`

> Note: 이전에 "annotated (was: not_detectable,interface-call-return-top)" 로 승격을 시도했으나, paper Table 6 (20 mitigated cases) 및 dataset.csv 기준으로 `not_detectable` 유지가 ground truth. 아래 Intent Annotations 섹션은 시도한 annotation 기록용으로 보존.

### Bug Description
`borrow()`에서 0.5% fee를 포함한 `increasingDebt = (_amount * 1005) / 1000`으로 개별 debt(`details[_id].debt`)를 증가시키지만, global `debts`는 fee 미포함 `_amount`로만 증가 → 개별 debt 합계와 global debts 불일치. `repay()`/`liquidate()`에서는 fee 포함 값으로 debts를 차감하므로 결국 debts가 underflow.
- Buggy (line 248): `debts += _amount`
- Correct: `debts += increasingDebt`
- Report: sponsor(jonah1005) confirmed

### Dependencies
**Libraries (사전 분석 필요):**
- `Float.sol` (`42_Float.sol`): `using Float for uint256`, `float` struct, `.multiply()`, `.divide()` — pure, assembly 없음 → 분석 가능
- `CheapERC20.sol` (`42_CheapERC20.sol`): `using CheapERC20 for IERC20` — borrow() 직접 경로 미사용, contraction에서 제거 시 불필요

**Interfaces:**
- `IMochiVault.sol`: `Detail` struct, `Status` enum (file-level 정의)
- `IMochiEngine.sol`: `engine.cssr()`, `engine.mochiProfile()`, `engine.nft()`, `engine.minter()`, `engine.discountProfile()`
- `IMochiProfile.sol`: `calculateFeeIndex()`, `maxCollateralFactor()`, `creditCap()`, `minimumDebt()`, `liquidationFactor()`
- `IDiscountProfile.sol`: `discount()`
- `IMochiNFT.sol`: `ownerOf()`, `asset()`
- `IMinter.sol`: `mint()`
- `ICSSRRouter.sol` (`42_ICSSRRouter.sol`): `update()`, `getPrice()`
- `IReferralFeePool.sol`: `addReward()`
- `IERC3156FlashLender.sol`, `IERC3156FlashBorrower.sol`: 상속

### 추가 구현 사항
- Issue 3: file-level struct 지원 (`struct Detail`, `enum Status` — contract 밖 interface 파일에 정의)
- Issue 4: `using Float for uint256` 커스텀 라이브러리 지원

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| StateVar | debts | [800, 800] | 29 | 초기 global debt = 500+300+0, invariant 유지 |
| StateVar | debtIndex | [1000000000000000000, 1000000000000000000] | 29 | 1e18, 이자 없는 초기 상태 |
| StateVar | lastAccrued | [현재timestamp, 현재timestamp] | 29 | accrueDebt에서 이자 0 |
| StateVar | details[0].debt | [500, 500] | 29 | 기존 position 0 |
| StateVar | details[0].debtIndex | [1000000000000000000, 1000000000000000000] | 29 | 1e18 |
| StateVar | details[0].status | Status.Active | 29 | active |
| StateVar | details[1].debt | [300, 300] | 29 | 기존 position 1 |
| StateVar | details[1].debtIndex | [1000000000000000000, 1000000000000000000] | 29 | 1e18 |
| StateVar | details[1].status | Status.Active | 29 | active |
| StateVar | details[2].debt | [0, 0] | 29 | borrow 대상, 초기 debt 0 |
| StateVar | details[2].debtIndex | [1000000000000000000, 1000000000000000000] | 29 | 1e18 |
| StateVar | details[2].collateral | [10000000, 10000000] | 29 | 충분한 담보 |
| StateVar | details[2].status | Status.Collaterized | 29 | 담보만 있는 상태 |
| IReturn | engine.mochiProfile().calculateFeeIndex() | [1000000000000000000, 1000000000000000000] | 29 | debtIndex 그대로 반환 (이자 0) |
| IReturn | engine.cssr().update() | float{1e18, 1e18} | 29 | price = 1.0 |
| IReturn | engine.mochiProfile().maxCollateralFactor() | float{8e17, 1e18} | 29 | cf = 0.8 |
| IReturn | engine.mochiProfile().creditCap() | [100000000, 100000000] | 29 | 충분히 큰 cap |
| IReturn | engine.mochiProfile().minimumDebt() | [0, 0] | 29 | 최소 debt 없음 |
| LocalVar | _amount | [1000, 1000] | 29 | borrow 금액 |

- 초기 invariant: debts(800) == details[0].debt(500) + details[1].debt(300) + details[2].debt(0) ✓
- accrueDebt: currentIndex == debtIndex → increased = 0, 변화 없음
- increasingDebt = 1000 * 1005 / 1000 = 1005
- details[2].debt = 0 + 1005 = 1005
- Buggy: debts = 800 + 1000 = 1800
- Correct: debts = 800 + 1005 = 1805

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| Post | 52 | debts == details[0].debt + details[1].debt + details[2].debt | violated | Accounting invariant: global debts = Σ individual debts. debts=800+1000=1800 ≠ 500+300+1005=1805 → violated |

---

## web3bugs_42_H_05
- **Status**: excluded (duplicate_of_42_H_01)
- **Contract**: MochiVault
- **Function**: borrow()
- 42_H_01과 동일한 버그 (debts calculation 부정확)

---

## web3bugs_52_H_16
- **Status**: `not_detectable (L4b: wrong-code — view function no state)`
- **Contract**: VaderRouter
- **Function**: calculateOutGivenIn()
- **Bug lines**: 488-491

### Bug Description
3-path swap에서 pool0과 pool1의 reserve 파라미터 순서가 뒤바뀜. inner calculateSwap이 pool1 reserve를 사용하고 outer가 pool0 reserve를 사용하지만, 올바르게는 inner=pool0(foreign→native), outer=pool1(native→foreign)이어야 함.
- Buggy: `calculateSwap(calculateSwap(amountIn, nativeReserve1, foreignReserve1), foreignReserve0, nativeReserve0)`
- Correct: `calculateSwap(calculateSwap(amountIn, foreignReserve0, nativeReserve0), nativeReserve1, foreignReserve1)`
- Report: sponsor(SamSteinGG) confirmed. 52_H_15와 동일한 wrong-arg-order 패턴.

### Not Detectable 사유 (L4b: wrong-code)
- **L4b 재분류 근거** (l4_l5_classification.csv reclass_reason: `annotation_plans_L5b_but_view_function_no_state_I9_principle_L4b`) — view function 이 state 를 쓰지 않아 L5b 의 "bug awareness" 조건 대신 I9 principle (grammar expressibility) 적용, L4b
- Interface call은 지원되지만 `VaderMath.calculateSwap()` library pure 함수는 annotation grammar 에서 직접 호출 불가
- view function 이므로 @Post changed/Entry/Exit 대상 state variable 부재 → grammar 로 표현 가능한 invariant 가 원천적으로 없음 → L4b (grammar expressibility)
- 52_H_15 twin case 와 동일한 router wrapper L4b archetype

---

## web3bugs_5_H_15

- **Contract**: Router
- **Function**: swapWithSynthsWithLimit
- **Bug line**: 170 (original 기준)
- **Status**: `not_detectable (L2a: interface-call-return-top)`
- **Bug**: Token→Token 스왑 시 두 번째 slippage check에서 첫 스왑의 base output 대신 원래 `inputAmount`를 사용
- Buggy (line 170): `iUTILS(UTILS()).calcSwapSlip(inputAmount, iPOOLS(POOLS).getBaseAmount(outputToken))`
- Correct: `iUTILS(UTILS()).calcSwapSlip(firstSwapOutput, iPOOLS(POOLS).getBaseAmount(outputToken))`
- 첫 번째 스왑(line 166)의 return value가 미사용됨
- Report: sponsor(strictly-scarce) confirmed

### @IReturn 재검토
- `iUTILS.calcSwapSlip()` → **pure** → @IReturn 가능
- `iPOOLS.getBaseAmount()` → **view** → @IReturn 가능
- `iPOOLS.getTokenAmount()` → **view** → @IReturn 가능
- `iPOOLS.isAnchor()` → **view** → @IReturn 가능
- `iPOOLS.swap()` → **state-modifying (mutability 없음)** → @IReturn **불가**

### Not Detectable 사유
- 버그 탐지에 필요한 핵심 값: 첫 스왑 output (`iPOOLS(POOLS).swap()` 반환값)
- `swap()`은 state-modifying 함수이므로 @IReturn 적용 불가
- 첫 스왑 output을 concrete하게 만들 수 없으므로, `inputAmount`와 `firstSwapOutput`의 차이를 검증할 방법 없음
- view/pure 함수들(@IReturn 가능)만으로는 버그의 핵심인 "잘못된 변수 사용"을 탐지할 수 없음

---

## web3bugs_61_H_01

- **Contract**: CreditLine
- **Function**: _borrowTokensToLiquidate
- **Bug line**: 1050 (original 기준)
- **Status**: `not_detectable (L4a: inexpressible-expected-value)`
- **Bug**: `IPriceOracle(priceOracle).getLatestPrice(_borrowAsset, _collateralAsset)` — 인자 순서가 반대
- Buggy: `getLatestPrice(_borrowAsset, _collateralAsset)` → borrow/collateral 비율
- Correct: `getLatestPrice(_collateralAsset, _borrowAsset)` → collateral/borrow 비율
- collateral를 borrow token으로 환산하려면 collateral/borrow 비율이 필요
- Report: sponsor(ritik99) confirmed

### Not Detectable 사유 (L4a: inexpressible-expected-value)
- Interface call은 이제 지원되어 `getLatestPrice()` 반환값은 TOP이 아님
- 그러나 구조적으로 올바른 expected value를 표현 불가:
  1. @IReturn이 인자를 구분하지 않음: `getLatestPrice(A, B)`든 `getLatestPrice(B, A)`든 동일 concrete 반환 → buggy/correct 동일 결과
  2. annotation grammar에서 함수 호출 불가 → `_ratioOfPrices == getLatestPrice(_collateralAsset, _borrowAsset)` 표현 불가
  3. 올바른 `_ratioOfPrices`는 oracle 반환값이므로 프로그램 내 기존 변수의 산술 조합으로도 표현 불가
- 버그를 인지하더라도 올바른 값을 annotation으로 구분할 수 없음 → L4a

---

## web3bugs_14_H_01

- **Contract**: IdleYieldSource
- **Function**: redeemToken
- **Bug line**: 131 (original 기준)
- **Status**: `excluded,missing-dependency`
- **Bug**: `redeemIdleToken(redeemedShare)` — `redeemedShare` 대신 `redeemAmount`를 전달해야 함

### Excluded 사유
- `IIdleToken` interface 정의 파일이 repository에 존재하지 않음
- dependency가 없으면 IntentChecker가 interface를 인식할 수 없어 분석 자체 불가

---

## web3bugs_29_H_11

- **Contract**: ConstantProductPool
- **Function**: burnSingle
- **Bug line**: 175; 183 (original 기준)
- **Status**: `not_detectable (L3: unsupported-construct-top)`
- **Bug**: swap 계산 시 `_reserve`를 사용했지만 `balance`를 사용해야 함
- Buggy (175): `_getAmountOut(amount0, _reserve0 - amount0, _reserve1 - amount1)`
- Correct: `_getAmountOut(amount0, balance0 - amount0, balance1 - amount1)`
- `burn` 후에는 reserve가 balance로 업데이트되므로 balance 기준이 맞음
- Report: sponsor(maxsam4) confirmed, severity bumped to High

### Not Detectable 사유 (L3: unsupported-construct-top)
- Interface call이 아닌 low-level `staticcall` + `abi.decode` 패턴 (29_H_08과 동일):
  - `_balance()`: `bento.staticcall(abi.encodeWithSelector(0xf7888aec, ...))` → `abi.decode`
- `staticcall`은 low-level external call로 추적 불가, `abi.decode`는 L3 unsupported construct → 반환값 TOP
- `balance0`, `balance1` → TOP → `amount0 = (liquidity * TOP) / _totalSupply` → TOP
- `_getAmountOut(TOP, _reserve0 - TOP, _reserve1 - TOP)` → TOP
- Interface 지원과 무관하게 `staticcall` + `abi.decode`가 blocker (L3)

---

## web3bugs_16_H_02

- **Contract**: Pricing
- **Function**: updateFundingRate (internal, called from recordTrade)
- **Bug Lines**: 155, 159
- **Status**: `excluded,multi-transaction`

### 버그 설명
`updateFundingRate()`에서 cumulative funding rate를 계산할 때 `fundingRates[currentFundingIndex]`를 읽어 이전 cumulative 값을 가져옴. 그러나 이전 호출에서 `setFundingRate`가 같은 인덱스에 쓴 후 `currentFundingIndex += 1`로 증가시켰으므로, 현재 호출에서 새 인덱스(미초기화 슬롯)를 읽게 됨 → cumulative 값이 항상 0 + 신규 rate = 신규 rate만 남음.

```solidity
// line 155: fundingRates[currentFundingIndex] → 미초기화 슬롯 읽기 (0)
int256 currentFundingRateValue = fundingRates[currentFundingIndex].cumulativeFundingRate;
int256 cumulativeFundingRate = currentFundingRateValue + newFundingRate; // 0 + new = new (이전 cumulative 손실)

// line 159: 동일 문제
int256 currentInsuranceFundingRateValue = insuranceFundingRates[currentFundingIndex].cumulativeFundingRate;

// line 163-165: 같은 인덱스에 쓰기
setFundingRate(newFundingRate, cumulativeFundingRate);
setInsuranceFundingRate(iPoolFundingRate, iPoolFundingRateValue);

// line 168: 인덱스 증가 → 다음 호출에서 미초기화 슬롯 읽기 유발
currentFundingIndex = currentFundingIndex + 1;
```

### Excluded 사유: multi-transaction
- `updateFundingRate`는 `internal`이고, `recordTrade` (external)에서만 호출됨
- 각 `recordTrade` 호출은 별도 트랜잭션
- 버그 발현 조건: 이전 트랜잭션에서 `currentFundingIndex`가 증가된 상태에서 현재 트랜잭션이 미초기화 슬롯을 읽음
- 첫 번째 호출(index=0)은 정상 (초기값 0이 올바름), 두 번째+ 호출부터 cumulative 손실 발생
- IntentChecker는 single-transaction 분석 → 트랜잭션 간 상태 변화 추적 불가

---

## web3bugs_51_H_03

- **Contract**: SwapUtils (library)
- **Function**: _xp (두 오버로드)
- **Bug Lines**: 666, 676
- **Status**: `excluded,multi-transaction`

### 버그 설명
`_xp()` 함수들이 `self.tokenPrecisionMultipliers` (저장된 값)를 직접 사용하지만, 올바른 동작은 `_getTargetPricePrecise()`로 현재 `block.timestamp` 기반 보간된 target price를 실시간 계산하여 multiplier를 구해야 함. 저장된 multiplier는 `rampTargetPrice()` / `stopRampTargetPrice()` 호출 시점에만 갱신되므로, ramp 기간 중에는 stale한 값 사용.

### Excluded 사유: multi-transaction
- `rampTargetPrice()` 호출 (tx1)에서 multiplier 설정
- 이후 swap/addLiquidity 등 (tx2~N)에서 `_xp()`가 stale multiplier 사용
- multiplier의 "staleness"는 트랜잭션 간 시간 경과(`block.timestamp` 변화)에 의해 발생
- 단일 트랜잭션 내에서 `tokenPrecisionMultipliers`는 단순히 이전 tx에서 설정된 상태값일 뿐, "stale 여부"를 판단할 수 없음

---

## web3bugs_5_H_12

- **Contract**: Pools
- **Function**: getAddedAmount (internal)
- **Bug line (original)**: 201
- **Pattern**: erroneous_accounting
- **Status**: `annotated` (was: `not_detectable,interface-call-return-top`)

### Bug Description
`getAddedAmount(address _token, address _pool)`의 else branch에서 `addedAmount = _balance - mapToken_tokenAmount[_pool]` 수행. `_token`의 추가량을 구해야 하므로 올바른 key는 `_token`이나 잘못된 key `_pool`을 사용. `_token != _pool`일 때 잘못된 결과 반환. `sync(token1, token2)` 등으로 악용하여 accounting 파괴 가능.

### Dependencies
- iERC20 interface (balanceOf)

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| SymAddress | address(this) | addr0 | 24 | 컨트랙트 자신 |
| SymAddress | _token | addr1 | 24 | 함수 파라미터 |
| SymAddress | _pool | addr2 | 24 | 함수 파라미터, ≠ _token |
| SymAddress | VADER | addr3 | 24 | state variable, ≠ _token (if 분기 스킵) |
| SymAddress | USDV | addr4 | 24 | state variable, ≠ _token (else if 분기 스킵) |
| IReturn | iERC20(_token).balanceOf(address(this)) | [200, 200] | 24 | 현재 잔액 |
| StateVar | mapToken_tokenAmount[_token] | [100, 100] | 24 | _token의 저장량 |
| StateVar | mapToken_tokenAmount[_pool] | [50, 50] | 24 | _pool의 저장량, ≠ _token's |

- else 분기 진입 조건: _token ≠ VADER, _token ≠ USDV (SymAddress로 모두 distinct)
- underflow 검증: _balance(200) >= mapToken_tokenAmount[_pool](50) ✓, _balance(200) >= mapToken_tokenAmount[_token](100) ✓

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| Post | 34 | returnExpression == _balance - mapToken_tokenAmount[_token] | violated | 5.md H-12: 함수 이름(getAddedAmount) + mapping 이름(mapToken_tokenAmount) + 파라미터(_token) semantics에서 자연스럽게 도출 가능한 함수 계약. 올바른 결과 100(200-100) vs 버그 결과 150(200-50) → violated |

---

## web3bugs_16_H_06

- **Contract**: GasOracle
- **Function**: latestAnswer
- **Bug Line**: 32, 33, 35
- **Status**: `not_detectable (L3: unsupported-construct-top)`

### 버그 설명
`latestAnswer()`에서 `gasOracle.latestAnswer()`(line 32)와 `priceOracle.latestAnswer()`(line 33)의 raw 값을 `toWad()`으로 18 decimals 변환 없이 바로 `PRBMathUD60x18.mul()`(line 35)에 전달. Chainlink oracle의 decimals가 18이 아닐 경우 결과값 스케일이 잘못됨. `toWad()` 함수가 존재하지만 호출되지 않음.

### Not Detectable 사유
- Interface call은 이제 지원되어 `gasOracle.latestAnswer()`, `priceOracle.latestAnswer()` 반환값은 TOP이 아님
- 그러나 `PRBMathUD60x18.mul(gasPrice, ethPrice)` (line 35) → PRBMath 라이브러리 내부에 inline assembly 사용 → result가 TOP (L3)
- result가 TOP이므로 annotation으로 스케일 오류 여부를 검증 불가
- 부차적으로 버그 자체도 `toWad()` 미호출 (missing-code 패턴)이나, L3이 주된 blocker

---

## web3bugs_14_H_03

- **Contract**: BadgerYieldSource
- **Function**: balanceOfToken
- **Bug Line**: 36
- **Status**: `excluded,missing-dependency`

### 버그 설명
`balanceOfToken()`에서 `badger.balanceOf(address(badgerSett))`(line 36)는 Sett 컨트랙트에 물리적으로 보유된 badger만 반환하여 strategy에 deploy된 자금을 미포함. 올바른 구현은 `badgerSett.balance()`로 전체 잔액(Sett + Controller + Strategy)을 사용해야 함.

### Excluded 사유
- `IBadgerSett`, `IBadger` interface 정의 파일이 repository에 존재하지 않음
- dependency가 없으면 IntentChecker가 interface를 인식할 수 없어 분석 자체 불가

---

## web3bugs_25_H_05

- **Contract**: CTokenMultiOracle
- **Function**: _setSource
- **Bug Line**: 110
- **Status**: `not_detectable (L4a: inexpressible-expected-value)`

### 버그 설명
`_setSource()`(line 110)에서 `decimals_`를 18로 하드코딩. 그러나 Compound의 exchange rate는 `1 * 10^(18 - 8 + underlyingTokenDecimals)`로 스케일되므로, 올바른 decimals는 `10 + underlyingTokenDecimals`(예: USDC=16, DAI=28). 잘못된 decimals가 `_peek()`/`_get()`의 가격 스케일링 계산에 사용되어 가격 오류 발생.

### Not Detectable 사유
- 버기 값: `decimals_ = 18` (하드코딩된 상수)
- 올바른 값: `18 - 8 + underlyingTokenDecimals` — `underlyingTokenDecimals`는 코드 내에 존재하지 않는 변수
- 올바른 값을 구하려면 `CToken.underlying()` → `IERC20.decimals()` 같은 현재 코드에 없는 새로운 중간 계산이 필요
- 프로그램 내 기존 변수들의 산술 조합으로 올바른 decimals를 표현할 수 없음 (L4a)

---

## web3bugs_61_H_04

- **Contract**: YearnYield
- **Function**: getTokensForShares
- **Bug Line**: 180
- **Status**: `not_detectable (L4a: interface-call-return-top)`

### 버그 설명
`getTokensForShares()`(line 180)에서 `IyVault.getPricePerFullShare()`의 결과를 `1e18`로 나누지만, Yearn의 `getPricePerFullShare()`는 `vault.decimals()` precision(= underlying token decimals)으로 반환. 올바른 구현은 `div(10 ** vault.decimals())`. 18 decimals가 아닌 토큰(e.g. USDC=6)에서 변환 오류 발생.

### Not Detectable 사유 (L4a: inexpressible-expected-value)
- Interface call은 이제 지원되어 `getPricePerFullShare()` 반환값은 TOP이 아님
- 그러나 올바른 divisor `10 ** vault.decimals()`:
  1. `vault.decimals()`가 buggy 코드에서 호출되지 않음 → 값을 담는 변수가 scope에 없음
  2. annotation grammar에서 함수 호출 불가 → `10 ** IyVault(...).decimals()` 표현 불가
  3. 올바른 divisor를 기존 변수의 산술 조합으로 표현 불가
- 25_H_01과 동일 패턴: 올바른 denominator가 코드에 없는 함수 호출 반환값에 의존 → L4a

---

## web3bugs_79_H_02

- **Contract**: LaunchEvent
- **Function**: createPair
- **Bug Line**: 398
- **Status**: `not_detectable (L5b: wrong-code)`

### 버그 설명
`createPair()`(line 398)에서 floor price 미달 시 `tokenAllocated = (wavaxReserve * 10**token.decimals()) / floorPrice`로 계산. `floorPrice`는 1e18 스케일이므로 올바른 계산은 `wavaxReserve * 1e18 / floorPrice`. 18 decimals 아닌 토큰(e.g. WBTC=8)에서 심각한 오류 발생.

### Not Detectable 사유 (L5b: wrong-code)
- Interface call은 이제 지원되어 `token.decimals()` 반환값은 TOP이 아님
- 그러나 annotation `tokenAllocated == wavaxReserve * 1e18 / floorPrice`는 fix code 그 자체
- natspec "scaled to 1e18"이 scaling factor를 제공하지만, 이를 formula에 적용하는 것 = 버그를 고치는 것
- 5_H_07(주석에 완전한 수식 제공)과 달리 natspec은 scaling factor만 제공 → formula 구성에 bug awareness 필요 → L5b

---

## web3bugs_29_H_08

- **Contract**: HybridPool
- **Function**: _getReserves
- **Bug Line**: 255, 256
- **Status**: `not_detectable (L3: unsupported-construct-top)`

### 버그 설명
`_updateReserves()`에서 `_balance()`가 이미 BentoBox shares→amounts 변환한 값을 `reserve0`/`reserve1`에 저장. 그런데 `_getReserves()`(lines 255-256)에서 이미 amounts인 reserves를 `_toAmount()`으로 다시 변환 (double conversion). 모든 swap/mint/burn에서 잘못된 reserve 사용.

### Not Detectable 사유
- Interface call이 아닌 low-level `staticcall` + `abi.decode` 패턴:
  - `__balance()`: `bento.staticcall(abi.encodeWithSelector(...))` → `abi.decode(___balance, (uint256))`
  - `_toAmount()`: `bento.staticcall(abi.encodeWithSelector(...))` → `abi.decode(_output, (uint256))`
- `staticcall`은 low-level external call로 추적 불가, `abi.decode`는 L3 unsupported construct → 반환값 TOP
- `_balance()` → TOP, `_updateReserves()`: `reserve0 = uint128(TOP)` → storage에 TOP
- `_getReserves()`: `_toAmount(token0, TOP)` → TOP
- Interface 지원과 무관하게 `staticcall` + `abi.decode`가 blocker (L3)

---

## web3bugs_78_H_02

- **Contract**: RebaseProxy
- **Function**: mint
- **Bug line (original)**: 36
- **Pattern**: erroneous_accounting
- **Status**: `annotated` (was: `not_detectable,interface-call-return-top`)

### Bug Description
`mint()`(line 36)에서 `proxy = (baseBalance * ONE) / _redeemRate`로 계산하지만, `baseBalance`는 transfer 후의 전체 잔액(기존 잔액 포함). 올바른 구현은 `(amount * ONE) / _redeemRate` (입금한 금액 기준). 기존 잔액이 있으면 과다 mint 발생.
- Report: sponsor(gititGoro) confirmed

### Dependencies
- `TokenProxyLike.sol` (dependencies/에 존재): `ONE = 1 ether` (constant, 인라인됨), `baseToken` (internal state variable)
- ERC20 (OpenZeppelin 상속): `_mint()`, `_balances`, `_totalSupply` — **Issue 8 (피상속 private state variable 접근) 필요**

### 추가 구현 사항
- **Issue 8**: 피상속 ERC20의 `_balances[to]`, `_totalSupply` private state variable 접근 필요

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| StateVar | _totalSupply | [1000000000000000000000, 1000000000000000000000] | 19 | 1000e18, ERC20 상속 (Issue 8) |
| StateVar | _balances[to] | [0, 0] | 19 | 수신자 초기 잔액 0, ERC20 상속 (Issue 8) |
| IReturn | IERC20(baseToken).balanceOf(address(this)) | [1500000000000000000000, 1500000000000000000000] | 19 | 1500e18 |
| IReturn | IERC20(baseToken).transferFrom() | true | 19 | require 통과 |
| LocalVar | amount | [500000000000000000000, 500000000000000000000] | 19 | 500e18 입금액 |

- ONE = 1e18 (TokenProxyLike constant, 사전 분석 시 인라인)
- @IReturn은 pre/post transfer 구분 못함 → 둘 다 1500e18 반환
- redeemRate = 1500e18 * 1e18 / 1000e18 = 1.5e18
- Buggy: proxy = 1500e18 * 1e18 / 1.5e18 = 1000e18 → _balances[to] = 1000e18 > 500e18
- Correct: proxy = 500e18 * 1e18 / 1.5e18 ≈ 333e18 → _balances[to] = 333e18 < 500e18

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| Post | 24 | _balances[to] <= amount | violated | Vault share ≤ deposit amount (redeemRate ≥ ONE). Buggy: 1000e18 > 500e18 → violated |

---

## web3bugs_101_H_01

- **Contract**: LenderPool
- **Function**: _calculatePrincipalWithdrawable
- **Bug line (original)**: 678, 679, 680
- **Bug line (contraction)**: 43, 44, 45
- **Pattern**: erroneous_accounting
- **Status**: `annotated` (was: `not_detectable,interface-call-return-top`)

### Bug Description
`_calculatePrincipalWithdrawable()`에서 `borrowLimit`(line 43)를 denominator로 사용하지만, start fee 적용 시 `borrowLimit < totalSupply[_id]`. 함수 주석: "total lent amount - principal borrowed) * lenders lp balance / total lent amount" — denominator는 `totalSupply`여야 함. `balanceOf > borrowLimit`이면 가용량 초과 인출 → revert.
- Report: sponsor 확인 (judge resolved)

### Dependencies
**상속:**
- `ERC1155Upgradeable`: `balanceOf()` 제공 (Issue 8: 피상속 private state variable)
- `ReentrancyGuardUpgradeable`
- `IPooledCreditLineEnums`: enum 정의
- `ILenderPool`: interface

**using:**
- `SafeMath` for uint256
- `SafeERC20` for IERC20

**state variable 타입 (interface):**
- `ISavingsAccount` (`101_ISavingsAccount.sol` 존재)
- `IPooledCreditLine`: `getPrincipal()` 호출
- `IVerification`
- `IERC20`

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| StateVar | pooledCLConstants[_id].borrowLimit | [99000, 99000] | 43 | fee 차감된 borrowLimit |
| IReturn | POOLED_CREDIT_LINE.getPrincipal(_id) | [0, 0] | 43 | 미차입 |
| IReturn | balanceOf(_lender, _id) | [100000, 100000] | 43 | sole lender = totalSupply |
| LocalVar | _id | [1, 1] | 43 | pool id |

- _borrowedTokens = 99000
- _totalLiquidityWithdrawable = 99000 - 0 = 99000
- _principalWithdrawable = 99000 * 100000 / 99000 = 100000
- Buggy: 100000 > 99000 (가용량 초과)
- Correct (totalSupply 사용 시): 99000 * 100000 / 100000 = 99000

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| During | 45 | _principalWithdrawable <= _totalLiquidityWithdrawable | violated | 개별 인출액 ≤ 총 가용액. 기본 accounting invariant. Buggy: 100000 > 99000 → violated |

---

## web3bugs_101_H_02

- **Contract**: LenderPool
- **Function**: terminate
- **Bug Line**: 389, 400
- **Status**: `not_detectable (L5b: wrong-code)`

### 버그 설명
`terminate()`에서 `_actualNotBorrowedInShares`(line 389)를 token/share 혼합 계산으로 구하고, `_totalInterestInShares`와 합쳐 `withdrawShares`(line 400)에 전달. token amount와 share를 혼합하여 잘못된 값 산출. 올바른 구현은 단순히 `_sharesHeld`를 직접 사용하여 전체 shares를 출금하는 것.

### Not Detectable 사유 (L5b: wrong-code)
- Interface call은 이제 지원되어 `getPrincipal()`, `getSharesForTokens()` 반환값은 TOP이 아님
- 그러나 올바른 값은 단순히 `_sharesHeld` (terminate = 전체 shares 출금)
- buggy 코드는 복잡한 token/share 혼합 계산으로 `_totalBorrowAsset`을 구하지만, 올바른 구현은 `_sharesHeld` 직접 사용
- `_sharesHeld`가 정답이라는 것을 알면 복잡한 계산이 불필요하다는 것을 아는 것 = bug awareness → L5b

---

## web3bugs_192_H_01

- **Contract**: Lock
- **Function**: extendLock
- **Bug Line**: 90, 91 (original)
- **Status**: `not_detectable (L5a: missing-state-update)`

### 버그 설명
`extendLock()`에서 토큰을 전송받지만(`transferFrom`, line 90) `totalLocked[_asset] += _amount` 업데이트가 누락됨. 이후 `release()` 호출 시 `totalLocked[asset] -= lockAmount`에서 underflow 발생하여 자금이 영구 잠김.

### Not Detectable 사유
- `extendLock()` 내에 잘못된 numeric 연산이 아니라, 있어야 할 `totalLocked[_asset] += _amount` 코드가 누락됨
- `totalLocked[_asset] Changed` 또는 `Before < After` post-condition으로 표현 가능하나, 이 annotation을 쓰려면 "totalLocked가 업데이트되어야 한다"는 사실을 이미 인지해야 함
- `lock()`에서는 올바르게 `totalLocked += _amount`를 수행하지만, 개발자가 `extendLock()`에서 동일 업데이트가 필요하다는 일관성을 놓친 것이 버그의 원인 → 버그 인지 전제 (L5a: missing-state-update)

---

## web3bugs_36_H_02

- **Contract**: Basket
- **Function**: auctionBurn
- **Bug Line**: 105 (original)
- **Status**: `not_detectable (L4d: missing-state-update)`

### 버그 설명
`auctionBurn()`에서 `_burn()` 후 `ibRatio` 업데이트가 누락됨. `handleFees()`에서 fee에 의한 `ibRatio` 업데이트는 수행하지만, burn에 의한 supply 감소에 대한 `ibRatio = ibRatio * startSupply / (startSupply - amount)` 업데이트가 없음. 이후 다른 사용자의 `burn()` 호출 시 `pushUnderlying()`에서 낮은 ibRatio로 인해 받는 underlying token이 줄어듦.

### Not Detectable 사유
- `auctionBurn()` 내 `_burn()` 연산 자체는 올바름. 누락된 것은 burn 후 `ibRatio` 업데이트 코드
- `handleFees()`가 이미 `ibRatio`를 변경하므로 단순 `Changed` annotation은 만족됨. burn에 의한 추가 업데이트가 필요하다는 것을 알아야 더 정밀한 annotation 작성 가능
- `burn()`에서는 `handleFees()` → `pushUnderlying()` → `_burn()` 순서로 ibRatio 반영이 자연스럽지만, `auctionBurn()`에서는 별도 업데이트가 필요하다는 일관성을 놓친 것 → grammar 상 multi-var product invariant(`ibRatio × totalSupply` 보존) 가 annotation grammar 의 Post/During 표현 범위 밖 → L4d (Algorithm/Usable, only L4d case)

---

## web3bugs_65_H_01

- **Contract**: Basket
- **Function**: handleFees
- **Bug Line**: 136, 137 (original)
- **Status**: `not_detectable (L5a: missing-state-update)`

### 버그 설명
`handleFees()`에서 `startSupply == 0`일 때 `return;`으로 즉시 반환하면서 `lastFee = block.timestamp` 업데이트 누락. 이후 다시 mint/burn 시 stale `lastFee`로 fee를 계산하여, supply가 0이었던 기간에 대해서도 fee 부과.

### Not Detectable 사유
- `handleFees()`의 3개 분기 중 2개(`lastFee == 0`, 정상 `else`)는 `lastFee = block.timestamp`를 수행하지만, `startSupply == 0` 분기에서만 누락
- `lastFee Changed` post-condition으로 표현 가능하나, "supply가 0이어도 lastFee는 항상 갱신되어야 한다"는 것을 알아야 annotation 작성 가능 → 버그 인지 전제 (L5a: missing-state-update)

---

## web3bugs_62_H_03

- **Contract**: Stream
- **Function**: recoverTokens (bug line 672), root cause: claimReward
- **Bug Line**: 672 (original, 증상 발현 지점)
- **Status**: `not_detectable (L5a: missing-state-update)`

### 버그 설명
`claimReward()`에서 reward token을 전송(line 575)하면서 `rewardTokenAmount`를 감소시키지 않음. `rewardTokenAmount`는 `fundStream()`에서만 증가. 이후 `recoverTokens()`에서 `excess = balanceOf(this) - (rewardTokenAmount + rewardTokenFeeAmount)` 계산 시, stale한 `rewardTokenAmount`로 인해 excess가 underflow 또는 0이 되어 토큰 회수 불가.

### Not Detectable 사유
- Root cause는 `claimReward()`에서 `rewardTokenAmount -= rewardAmt` 누락 (missing state update)
- `rewardTokenAmount Changed` 또는 `Before > After` post-condition으로 표현 가능하나, "reward 전송 시 rewardTokenAmount를 감소시켜야 한다"는 것을 알아야 annotation 작성 가능 → 버그 인지 전제 (L5a: missing-state-update)
- Bug line 672 자체도 `balanceOf()` 외부 호출 → TOP (L2a) 부가적 blocker 존재

---

## web3bugs_62_H_10

- **Contract**: Stream
- **Function**: recoverTokens (bug line 654), root cause: creatorClaimSoldTokens
- **Bug Line**: 654 (original, 증상 발현 지점)
- **Status**: `not_detectable (L5a: missing-state-update)`

### 버그 설명
`creatorClaimSoldTokens()`에서 deposit token을 전송(line 597)하면서 `depositTokenAmount`이나 `redeemedDepositTokens`를 업데이트하지 않음. 이후 `recoverTokens()`에서 `excess = balanceOf(this) - (depositTokenAmount - redeemedDepositTokens)` 계산 시, stale한 값으로 인해 underflow 또는 잘못된 excess 산출.

### Not Detectable 사유
- Root cause는 `creatorClaimSoldTokens()`에서 `redeemedDepositTokens = depositTokenAmount` 또는 `depositTokenAmount = 0` 누락 (missing state update)
- 62_H_03과 동일 패턴: 토큰 전송 함수에서 tracking variable 미업데이트
- Annotation 표현 가능하나 버그 인지 전제 (L5a: missing-state-update)
- Bug line 654 자체도 `balanceOf()` 외부 호출 → TOP (L2a) 부가적 blocker 존재

---

## web3bugs_35_H_10

- **Contract**: ConcentratedLiquidityPool
- **Function**: burn
- **Bug Line**: 217 (original)
- **Status**: `not_detectable (L4c: missing-state-update)`

### 버그 설명
`burn()`에서 position을 제거할 때 `reserve0 -= amount0fees` / `reserve1 -= amount1fees`로 fee 금액만 차감하고 실제 liquidity 제거 금액(`amount0`, `amount1`)을 차감하지 않음. 이후 `reserve` 기반 계산이 부풀려진 reserve 값을 사용하여 가격/유동성 왜곡 발생.

### Not Detectable 사유
- `reserve0 -= amount0` 코드가 누락된 missing state update (L4c: Value/Usable, grammar limit — Entry/Exit 방향은 표현 가능하나 magnitude-only difference 가 필요한데 arithmetic postEntryExit 지원 부재)
- `@Post reserve0 == Before(reserve0) - amount0` annotation으로 표현 가능하나, "burn 시 amount0만큼 reserve를 차감해야 한다"는 것을 알아야 작성 가능 → 버그 인지 전제
- 부가적으로, `abi.decode`로 파라미터(`lower`, `upper`, `amount`, `recipient`, `unwrapBento`)가 전달되어 debugging annotation으로 concrete 값 설정 불가 → 모든 decoded 변수가 TOP

---

## web3bugs_35_H_08

- **Contract**: ConcentratedLiquidityPool
- **Function**: mint, burn
- **Bug Lines (original)**: 176 (mint), 242 (burn)
- **Status**: `not_detectable (L3: unsupported-construct-top)`

### 버그 설명
`mint()`과 `burn()`에서 liquidity 업데이트 조건이 `priceLower < currentPrice && currentPrice < priceUpper`로 strict inequality를 사용. `priceLower == currentPrice` (현재 가격이 position 하한과 정확히 일치)일 때 liquidity가 업데이트되지 않아 swap 금액 왜곡. 올바른 조건은 `priceLower <= currentPrice`.

### Not Detectable 사유
- **Primary blocker: abi.decode → TOP (L3)**
  - `mint()` line 142: `abi.decode(data, (MintParams))` → 모든 mint 파라미터 TOP
  - `burn()` line 232-235: `abi.decode(data, ...)` → 모든 burn 파라미터 TOP
  - `priceLower = TickMath.getSqrtRatioAtTick(TOP)` → TOP
  - 조건 `TOP < concrete` → 양쪽 분기 모두 탐색 → 경계값 edge case 구분 불가
- **Even without abi.decode**: `priceLower == currentPrice`라는 정확한 경계값을 debug annotation으로 설정해야 하며, 일반적 범위 설정으로는 잡히지 않는 edge case
- 같은 컨트랙트의 35_H_10, 35_H_12도 abi.decode secondary blocker 보유

---

## web3bugs_113_H_05

- **Contract**: NFTPairWithOracle
- **Function**: _lend
- **Bug Line (original)**: 316
- **Status**: `not_detectable (L5b: wrong-validation-operator)`

### 버그 설명
`_lend()`의 require 조건에서 `params.ltvBPS >= accepted.ltvBPS`로 검사하지만, lender 입장에서 낮은 LTV가 유리하므로 `params.ltvBPS <= accepted.ltvBPS`가 올바름. 예: borrower가 86% LTV를 요청하고 lender가 80%까지만 수용했는데, buggy 코드는 86%로 대출 실행 → lender에게 불리.

### Not Detectable 사유
- **Require 조건의 wrong operator (L5d)**: `>=` 대신 `<=`여야 하지만, require 자체가 직관적 검증문이라 annotation 대상이 아님. 올바른 조건을 During annotation으로 별도 표현 가능하나, 이미 작성된 require를 redundant하게 재검증하는 것은 해당 require가 틀렸음을 인지해야 함 → 버그 인지 전제
- **Buggy 파라미터가 후속 computation에 미반영**: `ltvBPS`는 require 체크에서만 사용되고 이후 금액 계산(`totalShare`, `openFeeShare`, `protocolFeeShare`)은 모두 `params.valuation` 기반 → ltvBPS 불일치가 state variable에 반영되지 않음
- **부가 blocker (L2a)**: `feesEarnedShare += protocolFeeShare`에서 `bentoBox.toShare()` interface call → TOP
- ltvBPS의 실질적 효과는 별도 함수 `removeCollateral()`의 청산 threshold에서 나타남 (별도 트랜잭션)

---

## web3bugs_61_H_02

- **Contract**: SavingsAccountUtil (library)
- **Function**: savingsAccountTransfer
- **Bug Lines (original)**: 75, 77, 79
- **Status**: `not_detectable (L4a: wrapper-return-indifference)`

### 버그 설명
`savingsAccountTransfer()`이 `_savingsAccount.transfer()`/`transferFrom()`의 실제 반환값(shares)을 무시하고 입력 파라미터 `_amount`를 그대로 반환. price per share ≠ 1일 때 실제 shares와 _amount가 다르므로, 호출측에서 잘못된 shares 수량이 기록되어 자금 손실 발생 (cancelPool 실패, 청산 실패 등).

### Not Detectable 사유 (L4a: wrapper-return-indifference)
- **L4a 재분류 근거** (l4_l5_classification.csv reclass_reason: `annotation_plans_md_said_L5a_but_self_contradictory_limitation_types_md_says_L4a_confirmed`)
- wrapper library 함수로 자체 state 없음. 반환값 capture assignment 가 코드에 아예 없어 annotation scope 의 named variable 로 bind 되지 않음 → grammar expressibility limit
- IReturn 이 state-modifying interface transfer call 에 대해 arg-indifferent 하게 모델링되므로 buggy (_amount 반환) 와 correct (transfer() 반환) 가 semantic channel 로 구분되지 않음 → L4a (pure Type B wrapper)
- Case7 twin (wrapper return misrouting drop pattern, pps/shares mismatch)

---

## web3bugs_110_H_01

- **Contract**: StakedCitadel
- **Function**: balance
- **Bug Lines (original)**: 293, 294
- **Status**: `not_detectable (L4b: missing-code — view function, missing call site)`

### 버그 설명
`balance()`가 `token.balanceOf(address(this))`(vault 잔액)만 반환하고 `IStrategy(strategy).balanceOf()`(strategy 잔액)을 누락. 올바른 구현은 vault + strategy 합산. 이 값이 `_depositFor`, `_withdraw`, `_handleFees` 등 전체 accounting에 사용되어 shares mint/burn 계산이 심각하게 왜곡됨.

### Not Detectable 사유 (L4b: missing-code)
- **L4b 재분류 근거** (l4_l5_classification.csv reclass_reason: `annotation_plans_L5a_but_view_function_missing_call_site_G3_I9_L4b`)
- `balance()` 는 view 함수 — state 변경 없음, @Post Entry/Exit/changed 대상 state var 없음
- 누락된 `IStrategy(strategy).balanceOf()` 호출 자체가 코드에 존재하지 않으므로 annotation 이 참조할 call site (G3) 가 부재 → grammar 로 `returnExpression == balanceOf(this) + strategy.balanceOf()` 표현 불가
- I9 principle: grammar expressibility (call site 부재) 가 bug awareness 층 보다 선행 → L4b (not L5a)
- Case11/Case16/Case20 family (vault/strategy split pattern)

---

## web3bugs_17_H_02

- **Contract**: Buoy3Pool
- **Function**: safetyCheck
- **Bug line (original)**: 88
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L4b: inexpressible-intent — missing scope vars)`

### Bug Description
`safetyCheck()`에서 stablecoin 가격 비율 체크가 불완전:
1. `a/b`, `a/c` ratio만 체크, `b/c` 미체크 → transitivity로 `b/c`는 `2 * BASIS_POINTS` 범위만 보장
2. `a/b` in range ≠ `b/a` in range (비대칭)
3. NatSpec에 "Curve + external oracle" 체크라고 명시했으나 oracle 호출 없음
- Report: sponsor(kristian-gro) confirmed, b/c check 추가

### Not Detectable 사유 (L4b: inexpressible-intent)
- **L4b 재분류 근거** (l4_l5_classification.csv reclass_reason: `annotation_plans_md_said_L5a_but_post_condition_not_expressible_due_to_missing_scope_vars_limitation_types_L4b_confirmed`)
- 이전 L5a(missing-code) 해석은 "b/c 체크 코드 추가" 방향이었으나, 실제 annotation 작성 시 필요한 scope variable(`b/c` ratio, external oracle 결과)이 view function `safetyCheck()` 의 local/state scope에 존재하지 않음 → grammar 자체로 표현 불가 → L4b
- Interface call은 이제 지원되어 `curvePool.get_dy()` 반환값은 TOP이 아니지만, transitivity 보완식(`b/c`)을 위한 named variable이 함수 scope 밖 → L4b (grammar expressibility limit)

---

## web3bugs_59_H_05

- **Contract**: AuctionEscapeHatch
- **Function**: exitEarly
- **Bug lines (original)**: 83, 87
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L4a: wrong-code)`

### Bug Description
`exitEarly()`에서 `auction.amendAccountParticipation(msg.sender, _auctionId, amount, maltQuantity)` 호출 시, `maltQuantity`는 profit penalty가 적용된 값(실제보다 적음). `amount`(전체 commitment)는 그대로 차감되지만 `maltQuantity`(penalty 적용)만 차감되므로 `userMaltPurchased / userCommitment` 비율이 점점 높아짐. 반복 호출로 과다 수익 가능.
- Report: sponsor(0xScotch) confirmed

### Not Detectable 사유 (L4a: wrong-code)
- **L4a 재분류 근거** (l4_l5_classification.csv reclass_reason: `annotation_plans_md_says_L5b_but_limitation_types_md_says_L4a_objective_judgment_L4a`)
- `amendAccountParticipation` 은 state-modifying external call — 외부 컨트랙트 state 변화 검증이 annotation scope 밖 (→ L4a inexpressible-expected-value 과 동일 계열: arg[N] 정답값이 원본 pre-penalty quantity 인데 이 값이 program 내 named variable 로 존재하지 않음)
- IReturn arg indifference: annotation grammar 에서 `func.arg[N]` 체크 시 pre-penalty 원본값과 비교할 대상이 scope 에 없음 → 구조적 expressibility 한계 → L4a
- I9 principle 에 의거, wrong-code 이지만 scope vars 부재가 더 근본이므로 L4a 로 통일 (Case4 twin, pre-vs-post penalty value collapse)

---

## web3bugs_70_H_09

- **Contract**: USDV
- **Function**: mint, burn
- **Bug lines (original)**: 76 (mint), 109 (burn)
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L5b: wrong-code)`

### Bug Description
`mint()`: `uAmount = (vPrice * vAmount) / 1e18` — `vPrice`가 USD/Vader 단위면 결과는 USD 금액이지 USDV 금액이 아님.
`burn()`: `vAmount = (uPrice * uAmount) / 1e18` — 동일 패턴. oracle 가격의 의미에 따라 공식이 달라져야 함.
- Report: sponsor 미확인 (judge resolved)

### Not Detectable 사유 (L5b: wrong-code)
- Interface call은 이제 지원되어 `lbt.getVaderPrice()`, `lbt.getUSDVPrice()` 반환값은 TOP이 아님
- 그러나 올바른 price conversion formula는 oracle이 반환하는 가격의 단위/의미에 의존
- `vPrice * vAmount / 1e18`이 맞는지 `vAmount * 1e18 / vPrice`가 맞는지는 oracle 스펙 이해 필요
- domain knowledge / bug awareness → L5b

---

## numscout_EthereumGod

- **Contract**: EthereumGod
- **Function**: swapAndLiquify
- **Bug lines (original)**: 937, 941, 942, 956
- **Pattern**: precision_loss_trend
- **Status**: `not_detectable (L2a: interface-call-return-top)`

### Bug Description
`swapAndLiquify()`에서 fee splitting의 chained div/mul 연산으로 precision loss 누적. marketing fee와 liquidity fee 분배 시 여러 단계의 나눗셈/곱셈이 중간 값을 truncate하여 최종 분배 금액에 오차 발생.

### Not Detectable 사유 (L2a: interface-call-return-top)
- ~~`address(this).balance` → L3 unsupported construct~~ → Issue 7 구현으로 GlobalVar 제공 가능
- 그러나 `address(this).balance`가 **두 번** 읽힘:
  1. `initialBalance = address(this).balance` (line 948, swap 전)
  2. `address(this).balance.sub(initialBalance)` (line 955, swap 후)
- 두 읽기 사이에 `swapTokensForEth(toSwapForEth)` (line 952)가 실행됨
  - 내부적으로 `uniswapV2Router.swapExactTokensForETHSupportingFeeOnTransferTokens()` 호출
  - **state-modifying interface call** → @IReturn 적용 불가
  - swap이 ETH를 컨트랙트로 전송 → balance 변화
- Static GlobalVar는 하나의 값만 제공 → swap 전후 balance 차이를 표현 불가
- `fromSwap = (swap후 balance) - initialBalance` → 두 시점 balance가 같으면 0이 되어 무의미
- Primary blocker: state-modifying interface call로 인한 balance 변화 추적 불가 (5_H_15와 동일 패턴)

---

## numscout_HippoHotel

- **Contract**: HippoHotel
- **Function**: withdraw
- **Bug line (original)**: 1937
- **Pattern**: precision_loss_trend
- **Status**: `excluded (E7: inherent-truncation)`

### Numscout 감지 내용
Numscout가 `balance.mul(25).div(100)` (line 1937)에서 `precision_loss_trend` 패턴을 감지. `mul().div()` 체인에서 truncation이 발생할 수 있다는 heuristic 매칭.

### 원본 코드 (line 1935-1940)
```solidity
function withdraw() external onlyOwner {
    uint256 balance = address(this).balance;         // L1936
    uint256 balance2 = balance.mul(25).div(100);     // L1937 ← Numscout 감지 지점
    payable(wallet2).transfer(balance2);              // L1938
    payable(wallet1).transfer(balance.sub(balance2)); // L1939
}
```

### Excluded 사유 (E7: inherent-truncation)

**1. 코드가 이미 최적 연산 순서(mul-first)를 사용**
- `balance.mul(25).div(100)` = `balance * 25 / 100` (mul-first)
- div-first인 `balance.div(100).mul(25)`보다 같거나 나은 결과

**2. 대안 구현도 동일 결과 — "correct code"가 존재하지 않음**
- `floor(balance * 25 / 100)` = `floor(balance / 4)` (수학적 항등)
- 검증: balance=1003 → `1003*25/100 = 250`, `1003/4 = 250` → 동일
- 어떤 정수 연산 구현이든 `floor(balance * 0.25)`와 같은 결과

**3. 자금 유실 없음**
- wallet2: `balance2 = 250`
- wallet1: `balance - balance2 = 1003 - 250 = 753`
- 총합: `250 + 753 = 1003 = balance` (완전 분배, remainder는 wallet1에 할당)

**4. Intent annotation으로 buggy/correct 구분 불가**
- `balance2 == balance * 25 / 100` → 코드가 하는 것 그대로라 항상 satisfied
- `balance2 * 100 == balance * 25` (무손실 검증) → 어떤 구현이든 balance % 4 ≠ 0이면 violated
- `balance2 == balance / 4` → 항상 satisfied (수학적 항등)
- 모든 intent가 buggy와 correct에서 동일하게 평가됨

**5. Numscout false positive 분석**
- Numscout의 `precision_loss_trend` 패턴은 `mul().div()` 체인의 truncation 가능성을 heuristic하게 감지
- 이 케이스에서는 truncation이 실제로 발생하지만 (balance=1003일 때 75 wei 손실), 이는 정수 연산의 수학적 속성이지 코드 실수가 아님
- 대안 코드가 다른 결과를 산출하지 않으므로 "수정 가능한 버그"에 해당하지 않음

---

## web3bugs_58_H_04

- **Contract**: AaveVault
- **Function**: tvl (line 47), _push, _pull
- **Bug Line (original)**: 47
- **Status**: `not_detectable (L4b: ordering-problem)`

### 버그 설명
`tvl()`이 cached `_tvls` 배열을 반환. `_push()`에서 `updateTvls()`가 Aave lending pool deposit **후에** 호출되어, 호출측(LPIssuer)이 old tvl 기준으로 shares를 계산. Aave의 rebasing aToken 이자가 반영되기 전의 tvl로 과다한 shares 발행 → attacker가 이자 탈취 가능.

### Not Detectable 사유 (L4b: ordering-problem)
- **L4b 재분류 근거** (l4_l5_classification.csv reclass_reason: `annotation_plans_L5a_but_ordering_problem_not_expressible_L4b_per_function_type`)
- 버그 본질은 `_push()` 내부의 **operation ordering**: `updateTvls()`가 deposit 전이 아니라 후에 호출됨
- 각 함수 개별적으로는 정상 (`tvl()` view, `_push()` deposit+updateTvls 순, `updateTvls()` balanceOf 반영). ordering bug 은 단일 함수 scope 안 관계가 아니라 "stale cache 가 호출자에게 노출됨" 이라는 호출-흐름 속성
- ordering 을 표현할 annotation grammar 원소(예: `@During before(updateTvls) before(deposit)`)가 없음 → grammar expressibility limit → L4b (not L5a)

---

## web3bugs_47_H_02

- **Contract**: WrappedIbbtcEth
- **Function**: transferFrom
- **Bug Line (original)**: 111
- **Pattern**: erroneous_accounting
- **Status**: `annotated`

### 버그 설명
`transferFrom()`에서 `amount`를 `amountInShares`로 변환 후 `_transfer`에 전달하는 것은 정상이나, `_approve` 호출 시 allowance 차감도 `amountInShares`로 수행. allowance는 balance 단위(rebalanced amount)인데 shares 단위로 차감하므로, `pricePerShare > 1e18`일 때 차감량이 적어져 spender가 승인량 이상을 전송 가능.

### Annotation 계획

**Contraction**: `target_contracts_contraction/web3bugs_47_H_02.sol` (29 lines)
- `balanceToShares()` + `transferFrom()` 포함

**Dependencies**:
- `47_ERC20Upgradeable.sol`: `_transfer`, `_approve`, `_allowances`, `_balances`
- `47_SafeMathUpgradeable.sol`: `.mul()`, `.div()`, `.sub()`, `.add()`
- `47_ContextUpgradeable.sol`: `_msgSender()` → `msg.sender`
- `47_Initializable.sol`, `47_IERC20Upgradeable.sol`, `47_AddressUpgradeable.sol`, `ICore.sol`

**Debug annotations (line 22, transferFrom 시작)**:
- `// @LocalVar sender = symbolicAddress 1`
- `// @LocalVar recipient = symbolicAddress 2`
- `// @LocalVar amount = [100, 100]`
- `// @StateVar _allowances[1][101] = [1000, 1000]`
- `// @StateVar pricePerShare = [2000000000000000000, 2000000000000000000]`
- `// @StateVar _balances[1] = [500, 500]`

**Intent annotation**:
- `@Post _allowances[1][101] == 900` (또는 line 26 이후 `@During`)
- 버그 코드: 1000 - 50(amountInShares) = 950 → **violated**
- 정상 코드: 1000 - 100(amount) = 900 → **satisfied**

**Rationale**: 47.md H-02 — approve가 override 안 되어 allowance는 balance 단위인데 transferFrom에서 shares 단위로 차감. ERC20 표준상 allowance 차감은 사용자가 지정한 amount 단위여야 함.

---

## web3bugs_62_H_08

- **Contract**: Stream
- **Function**: updateStreamInternal
- **Bug Lines (original)**: 226;229;230
- **Pattern**: inconsistent_state_updates
- **Status**: `annotated`

### 버그 설명
`updateStreamInternal()`에서 `ts.lastUpdate`가 `if (acctTimeDelta > 0 && ts.tokens > 0)` 블록 안에서만 갱신됨. 사용자가 전액 withdraw 후(`ts.tokens == 0`) 다시 stake하면, updateStream 호출 시 `ts.tokens == 0`이므로 if 블록이 skip되어 `ts.lastUpdate`가 갱신되지 않음. 이후 withdraw 시 stale `ts.lastUpdate`로 `ts.tokens` decay가 잘못 계산되어 실제보다 많은 토큰을 인출 가능.

### Annotation 계획

**Contraction**: `target_contracts_contraction/web3bugs_62_H_08.sol` (183 lines)
- `lastApplicableTime()`, `rewardPerToken()`, `earned()`, `updateStreamInternal()` 포함

**Dependencies**: 없음 (모든 호출 함수가 같은 contract 내부)

**Debug annotations (line 146, updateStreamInternal 시작)**:

Global:
- `// @GlobalVar block.timestamp = [1000, 1000]`

Immutable state variables:
- `// @StateVar endStream = [2000, 2000]`
- `// @StateVar startTime = [500, 500]`
- `// @StateVar streamDuration = [1500, 1500]`
- `// @StateVar depositDecimalsOne = [1000000000000000000, 1000000000000000000]`

Mutable state variables:
- `// @StateVar lastUpdate = [1000, 1000]`
- `// @StateVar cumulativeRewardPerToken = [100, 100]`
- `// @StateVar totalVirtualBalance = [0, 0]`
- `// @StateVar unstreamed = [0, 0]`

Mapping struct fields (msg.sender = 101):
- `// @StateVar tokensNotYetStreamed[101].tokens = [0, 0]`
- `// @StateVar tokensNotYetStreamed[101].lastUpdate = [800, 800]`
- `// @StateVar tokensNotYetStreamed[101].rewards = [0, 0]`
- `// @StateVar tokensNotYetStreamed[101].lastCumulativeRewardPerToken = [100, 100]`
- `// @StateVar tokensNotYetStreamed[101].virtualBalance = [0, 0]`

**Intent annotation (line 182, updateStreamInternal 종료 직전)**:
- `// @Post tokensNotYetStreamed[101].lastUpdate == [1000, 1000]`

**검증 시나리오** (ts.tokens == 0, block.timestamp >= startTime):
1. `rewardPerToken()`: totalVirtualBalance==0 → return 100 (unchanged)
2. `earned()`: 0 * (100-100) / 1e18 + 0 = 0
3. `acctTimeDelta = 1000 - 800 = 200`
4. `200 > 0 && 0 > 0` → FALSE → ts.lastUpdate 갱신 skip
5. Buggy: `tokensNotYetStreamed[101].lastUpdate == 800` ≠ 1000 → **VIOLATION**
6. Correct (ts.lastUpdate를 if 블록 밖에서 갱신): `tokensNotYetStreamed[101].lastUpdate == 1000` → **SATISFIED**

**Rationale**: `updateStreamInternal`은 stream 상태 갱신 함수로, 호출 시 `ts.lastUpdate`가 현재 timestamp로 갱신되는 것은 자연스러운 invariant. bug-awareness 없이도 "update 함수 호출 후 lastUpdate == block.timestamp" 라는 intent를 작성할 수 있음.

---

## web3bugs_51_H_02

- **Contract**: SwapUtils (library)
- **Function**: rampTargetPrice
- **Bug Lines (original)**: 1573;1578
- **Pattern**: erroneous_accounting
- **Status**: `annotated`

### 버그 설명
`rampTargetPrice()`의 sanity check에서 `MAX_RELATIVE_PRICE_CHANGE` (10^16, 1% delta)를 배수로 사용하여 require 조건이 항상 false.
- decrease: `future * 10^16 / 10^18 = future * 0.01 >= initial` → future < initial이므로 항상 false
- increase: `future <= initial * 10^16 / 10^18 = initial * 0.01` → future >= initial이므로 항상 false

올바른 공식: `MAX_RELATIVE_PRICE_CHANGE + WEI_UNIT` (= 1.01 배수)를 사용해야 함. 결과적으로 target price를 절대 업데이트할 수 없음.

### Annotation 계획

**Contraction**: `target_contracts_contraction/web3bugs_51_H_02.sol` (125 lines)
- `_getTargetPricePrecise()` (L80-98), `rampTargetPrice()` (L100-124)

**Dependencies**: `_getTargetPricePrecise` — 같은 library 내부 함수, 외부 호출 없음

**Debug annotations (line 105, rampTargetPrice 시작, 8개)**:

Global:
- `// @GlobalVar block.timestamp = [2000000, 2000000]`

TargetPrice storage self 필드 (state variables, 5개):
- `// @StateVar self.initialTargetPriceTime = [1000000, 1000000]`
- `// @StateVar self.futureTargetPriceTime = [1500000, 1500000]`
- `// @StateVar self.futureTargetPrice = [1000000000000000000, 1000000000000000000]`
- `// @StateVar self.initialTargetPrice = [1000000000000000000, 1000000000000000000]`
- `// @StateVar self.originalPrecisionMultipliers[0] = [1000000000000000000, 1000000000000000000]`

함수 파라미터 (local variables, 2개):
- `// @LocalVar futureTargetPrice_ = [990000000000000000, 990000000000000000]`
- `// @LocalVar futureTime_ = [3209600, 3209600]`

**Intent annotation (line 113, buggy require)**:
- `// @During require passable`

**검증 시나리오** (target price 1% 감소 시도):
1. L105: `2000000 >= 1000000 + 86400` → ✓ (1 day 경과)
2. L106: `3209600 >= 2000000 + 1209600` → ✓ (MIN_RAMP_TIME 충족)
3. L107: `990000000000000000 >= 0` → ✓
4. L109: `_getTargetPricePrecise(self)` → `block.timestamp(2M) >= futureTargetPriceTime(1.5M)` → else → returns `10^18`
5. L110: `futureTargetPricePrecise = 990000000000000000 * 1 = 990000000000000000`
6. L112: `990000000000000000 < 10^18` → true (decrease 브랜치)
7. L113: `990000000000000000 * 10^16 / 10^18 = 9900000000000000` → `9900000000000000 >= 10^18` → **FALSE → REVERT**
8. `@During require passable` → **VIOLATED** ✓

**Correct code 검증** (`MAX_RELATIVE_PRICE_CHANGE + WEI_UNIT` 사용 시):
- `990000000000000000 * (10^16 + 10^18) / 10^18 = 990000000000000000 * 1.01 = 999900000000000000`
- `999900000000000000 >= 10^18` → FALSE (0.1% 차이) — 하지만 이건 1% 감소가 1% 한도 내이므로 통과해야 함
- 실제로는 `futureTargetPricePrecise.mul(MAX_RELATIVE_PRICE_CHANGE.add(WEI_UNIT)).div(WEI_UNIT) >= initialTargetPricePrecise`
- `990000000000000000 * 1010000000000000000 / 1000000000000000000 = 999900000000000000`
- `999900000000000000 >= 1000000000000000000` → FALSE → 1% 정확히가 아니라 약간 부족
- 0.99% 감소로 재시도: `futureTargetPrice_ = 991000000000000000` → `991 * 1.01 = 1000.91 * 10^15 = 1000910000000000000 >= 10^18` → TRUE ✓
- 정상적인 범위 내 가격 변경이 가능해짐 → `@During require passable` → **SATISFIED**

**Rationale**: `rampTargetPrice`는 target price 업데이트 함수로, 합리적인 입력(1% 이내 가격 변경)으로 호출 시 require를 통과해야 한다는 것은 자연스러운 기대. `@During require passable`은 bug-awareness 없이 "이 함수가 정상 동작해야 한다"는 intent를 표현.

**참고**: `@During require passable` annotation은 Issue 6 (code_modification_issues.md) 구현 필요.

---

## numscout_BoostToken_indivisible

- **Contract**: BoostToken
- **Function**: sendETHToTeam
- **Bug Lines (original)**: 933;934;935;936
- **Pattern**: indivisible_amount
- **Status**: `annotated`

### 버그 설명
`sendETHToTeam(amount)`에서 4개 지갑으로 ETH를 분배할 때 `amount.div(4)`, `amount.div(12)`, `amount.div(9)` 등 정수 나눗셈을 사용. `amount`가 LCM(4,12,9)=36 미만인 소액일 때 모든 나눗셈 결과가 0이 되어, 어떤 지갑도 ETH를 받지 못하고 컨트랙트에 잔류.

### Annotation 계획

**Contraction**: `Dataset/Numscout/contraction/indivisible_amount/BoostToken_contraction.sol`
- `sendETHToTeam(uint256 amount)` (L135-140)

**Dependencies**: 없음 (transfer는 native ETH 전송)

**Debug annotations (line 135, sendETHToTeam 시작, 1개)**:

- `// @LocalVar amount = [3, 3]`
  - amount=3: div(4)=0, div(12)=0, div(9)=0 → 모든 transfer 금액 0

**Intent annotations (L136-L139, 각 transfer 라인, 4개)**:

- L136: `// @During transfer.arg[0] > 0`
  - amount.div(4) = 0 → 0 > 0 → **VIOLATED** ✓
- L137: `// @During transfer.arg[0] > 0`
  - amount.div(12).mul(5) = 0*5 = 0 → 0 > 0 → **VIOLATED** ✓
- L138: `// @During transfer.arg[0] > 0`
  - amount.div(9).mul(2) = 0*2 = 0 → 0 > 0 → **VIOLATED** ✓
- L139: `// @During transfer.arg[0] > 0`
  - amount.div(9) = 0 → 0 > 0 → **VIOLATED** ✓

**검증 시나리오** (amount=3 wei):
1. L136: `3.div(4) = 0` → `_devWalletAddress.transfer(0)` → transfer.arg[0] = 0 → `0 > 0` → **VIOLATED**
2. L137: `3.div(12) = 0`, `0.mul(5) = 0` → transfer.arg[0] = 0 → **VIOLATED**
3. L138: `3.div(9) = 0`, `0.mul(2) = 0` → transfer.arg[0] = 0 → **VIOLATED**
4. L139: `3.div(9) = 0` → transfer.arg[0] = 0 → **VIOLATED**

**Correct code 검증** (최소 금액 검증 추가: `require(amount >= 36)`):
- amount=3 → require 실패 → revert → intent 미도달 → vacuously satisfied
- amount=36 → div(4)=9, div(12).mul(5)=15, div(9).mul(2)=8, div(9)=4 → 모두 > 0 → **SATISFIED**

**Rationale**: "각 지정 수령자에게 양수 금액이 전송되어야 한다"는 자금 분배 함수의 자연스러운 기대. bug-awareness 불필요.

---

## numscout_HIT

- **Contract**: HIT
- **Function**: getTokens
- **Bug Lines (original)**: 126;144
- **Pattern**: profit_opportunity
- **Status**: `annotated`

### 버그 설명
`getTokens()` 함수에서 `toGive = value + msg.value * 10000000` (L63)으로 배포량 계산. `msg.value = 0`(ETH 미지불)이어도 `toGive = value`(5000e18, 5000 토큰)이 무료로 배포됨. `payable` 함수이나 `require(msg.value > 0)` 검증 없음 → 무제한 무료 토큰 취득 가능.

### Annotation 계획

**Contraction**: `Dataset/Numscout/contraction/profit_opportunity/HIT_contraction.sol`
- `getTokens()` (L54-80), `distr()` (L41-52)

**Dependencies**: `distr()` — 같은 컨트랙트 내부 함수

**Debug annotations (line 54, getTokens 시작, 7개)**:

Global:
- `// @GlobalVar msg.value = [0, 0]`
  - msg.sender는 101로 사전 지정 (설정 불필요)

State:
- `// @StateVar value = [5000000000000000000000, 5000000000000000000000]`
  - 5000e18 (초기값)
- `// @StateVar totalRemaining = [800000000000000000000000000, 800000000000000000000000000]`
  - 800Me18
- `// @StateVar totalDistributed = [200000000000000000000000000, 200000000000000000000000000]`
  - 200Me18
- `// @StateVar totalSupply = [1000000000000000000000000000, 1000000000000000000000000000]`
  - 1Be18
- `// @StateVar distributionFinished = false`
  - canDistr modifier 통과용
- `// @StateVar blacklist[msg.sender] = false`
  - onlyWhitelist modifier 통과용

**Intent annotation (line 69, distr 호출, 1개)**:

- `// @During toGive => msg.value`
  - Implication: "토큰이 배포되려면(toGive > 0), 대가 지불이 있어야 함(msg.value > 0)"
  - antecedent: toGive = [5000e18, 5000e18] → non-zero → satisfied (true)
  - consequent: msg.value = [0, 0] → zero → violated (false)
  - true ⇒ false → **VIOLATED** ✓

**검증 시나리오** (msg.value=0, ETH 미지불):
1. canDistr: `!false` → pass
2. onlyWhitelist: `blacklist[101] == false` → pass
3. L55: `5000e18 > 800Me18` → false, skip
4. L59: `require(5000e18 <= 800Me18)` → pass
5. L63: `toGive = 5000e18 + 0 * 10000000 = 5000e18`
6. L65: `800Me18 <= 200Me18` → false, skip
7. L69: `distr(101, 5000e18)` → 5000 토큰 무료 배포
8. `@During toGive => msg.value` → [5000e18] ⇒ [0] → **VIOLATED** ✓

**Correct code 검증** (`require(msg.value > 0)` 추가 시):
- msg.value=0 → require 실패 → revert → intent 미도달 → vacuously satisfied

**대안 correct code** (`toGive = msg.value * 10000000`, free value 제거):
- toGive = 0 * 10000000 = 0
- `@During toGive => msg.value`: antecedent `0 != 0` → violated (false) → vacuously true → **SATISFIED** ✓

**Rationale**: "토큰 배포(toGive > 0)는 대가 지불(msg.value > 0)을 전제해야 한다"는 exchange 함수의 자연스러운 invariant. bug-awareness 불필요.

---

## numscout_WANGMI

- **Contract**: WANGMI
- **Function**: _transfer
- **Bug line (original)**: 428
- **Pattern**: div_in_path
- **Status**: `annotated`

### 버그 설명
`_transfer()`에서 sell fee 처리 시 line 428: `tokensForLiquidity = tokensForLiquidity.add(fees.mul(sellLiquidityFee).div(sellTotalFees))` — `fees.mul(3).div(12)`가 `fees < 4`일 때 `0`으로 truncate. 이로 인해 sell이 발생해도 `tokensForLiquidity`가 증가하지 않는 편향(accumulation 누락) 발생. Div In Path의 전형적 패턴.

### Annotation 계획

**Contraction/input**: `evaluation/RQ1/cases/div_in_path/WANGMI_input.json` (contract 이름 WANGMI, _transfer override)

**Dependencies**: IUniswapV2Router02, ERC20, Ownable, Context (OpenZeppelin 스타일)

**Debug annotations (line 384, _transfer 시작)**:
- `// @LocalVar _from = symbolicAddress 1`
- `// @LocalVar to = symbolicAddress 2`
- `// @LocalVar amount = [33, 33]` — 작은 수량으로 sellTotalFees=12 기준 truncation 시현
- `// @StateVar uniswapV2Pair = symbolicAddress 2` — to == pair이므로 sell 분기 진입
- `// @StateVar sellLiquidityFee = [3, 3]`, `sellTxFee = [9, 9]` → sellTotalFees = 12
- `// @StateVar tokensForLiquidity = [100, 100]` (초기값)
- (그 외 isLaunched=true, maxTx/Wallet 통과, isExcludedFromFees=false 등 env 설정)

중간 계산: `fees = 33 * 12 / 100 = 3`, `fees.mul(3).div(12) = 3*3/12 = 0` → tokensForLiquidity += 0 → 증가 없음.

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| During | 428 | tokensForLiquidity(Before < After) | violated | sell이 발생하면 fee가 누적되어야 하나 truncation으로 Before == After → violated |

**Rationale**: paper §6.2 Guideline 3 (multi-step arithmetic) 7 case 중 하나. `fees * sellLiquidityFee / sellTotalFees` 는 truncation으로 sell fee 누적이 항상 0이 되는 경계를 가짐. Before/After 방향성으로 직접 포착.

---

## numscout_Nokon

- **Contract**: Nokon
- **Function**: buy
- **Bug line (original)**: 51
- **Pattern**: exchange_problem
- **Status**: `annotated`

### 버그 설명
`buy()` line 51: `uint256 amountToBuy = msg.value / ethRateFix * calculateRate()` — division-first 후 multiplication이어서 `msg.value < ethRateFix` 범위에서 `msg.value / ethRateFix = 0`로 truncate, 결과 `amountToBuy = 0`. 사용자가 ETH 지불해도 토큰을 못 받는 exchange_problem 패턴.

### Annotation 계획

**Contraction/input**: `evaluation/RQ1/cases/exchange_problem/Nokon_input.json`

**Dependencies**: 없음 (SafeMath using 만 있음, calculateRate는 내부 함수)

**Debug annotations (line 49, buy 시작)**:
- `// @GlobalVar msg.value = [50000000000500000, 50000000000500000]` — 0.05 ETH + 약간 (ethRateFix = 10000000000 보다 큰 값)
- `// @StateVar presell = true`
- `// @StateVar balances[address(this)] = [2000000000000, 2000000000000]` — dex 보유량 충분

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| During | 51 | amountToBuy * ethRateFix >= msg.value * 250000 | violated | 이상적 공식(mul-first): `msg.value * rate / ethRateFix` 를 rearrange한 부등식. calculateRate 최솟값 250000 기준 하한 보장. buggy는 division-first로 truncation 발생 → 위반 |

**Rationale**: paper §6.2 Guideline 3 (multi-step arithmetic). Division-first가 의도한 `msg.value × rate / ethRateFix`와 다른 결과를 주는 전형적 패턴. Multiplication-first 이상 공식과 비교하여 precision gap 노출.

---

## flyinointment_SwordCrowdsale

- **Source**: Fly-in-the-Ointment (Greedy Contract dataset, paper §4.2 Dataset Collection, Table 1)
- **Contract**: SwordCrowdsale
- **Function**: refundMoney
- **Bug line (original)**: 77-79 (dataset.csv의 `bug_line=33`은 contraction 기준)
- **Pattern**: greedy_contract
- **Status**: `annotated`

### 버그 설명
`refundMoney()`가 기여자에게 ETH 환불을 수행하면서 `weiRaised`를 감소시키지 않음. `contributorList[_address].contributionAmount = 0`와 `.tokensIssued = 0`만 갱신하고, `weiRaised -= amount` 가 누락됨. `forwardAllRaisedFunds()` 호출 시 `wallet.transfer(weiRaised)` 라인에서 실제 잔액보다 더 많은 ETH 송금 시도 → 상시 revert, 자금이 컨트랙트에 영구 잠김 (Greedy Contract).

### Annotation 계획

**Contraction/input**: `evaluation/RQ1/cases/greedy_contract/SwordCrowdsale_input.json`

**Dependencies**: Ownable, Context (onlyOwner modifier 사용)

**Debug annotations (line 76, refundMoney 시작)**:
- `// @StateVar contributorList[_address].contributionAmount = [100, 100]` — 환불 대상 금액
- `// @StateVar weiRaised = [1000, 1000]` — 초기 누적 모금액
- owner/msg.sender 설정은 onlyOwner modifier 통과용

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| Post | 81 (refundMoney 종료 직후) | weiRaised(Entry > Exit) | violated | 환불 성공 시 누적 모금액은 감소해야 함. Buggy: Entry=1000, Exit=1000 → `Entry > Exit` false → violated |

**Rationale**: paper Tab 1 NumScout(7) + Flyinointment(1) + Web3Bugs(81) = 89 dataset composition 중 유일한 Flyinointment-origin case. paper §6.2 Guideline 1 (directional annotation via Entry/Exit)의 대표적 적용 — `weiRaised` 가 refund 후 감소해야 한다는 자연스러운 directional intent.

---

## numscout_BoostToken_operator

- **Contract**: BoostToken
- **Function**: sendETHToTeam
- **Bug lines (original)**: 141; 142
- **Pattern**: operator_order_issue
- **Status**: `annotated`

### 버그 설명
`sendETHToTeam(uint256 amount)` 내부의 두 라인:
- Line 141: `_marketingWalletAddress.transfer(amount.div(12).mul(5))` — `amount / 12 * 5`, division-first. 의도는 amount의 5/12.
- Line 142: `_dipWalletAddress.transfer(amount.div(9).mul(2))` — `amount / 9 * 2`, division-first. 의도는 amount의 2/9.

두 경우 모두 `amount < 12` (혹은 `< 9`)에서 `amount.div(k) = 0` → truncation → transfer 금액 0. Operator order issue: `amount * 5 / 12` (mul-first) 가 올바른 순서.

### Annotation 계획

**Contraction/input**: `evaluation/RQ1/cases/operator_order_issue/BoostToken_input.json`

**Dependencies**: Ownable, Context, SafeMath, Address (OpenZeppelin)

**Debug annotations (line 140, sendETHToTeam 시작)**:
- `// @LocalVar amount = [68, 68]` — 68 < 12 * 9 = 108 범위에서 `68/12*5 = 5*5 = 25`가 `68*5/12 = 28`보다 작음을 시현

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| During | 141 | transfer.arg[0] >= amount * 5 / 12 | violated | marketing wallet 송금량은 mul-first 하한값 이상이어야 함. buggy: 5*5=25 < 68*5/12=28 → violated |
| During | 142 | transfer.arg[0] >= amount * 2 / 9 | violated | dip wallet 송금량은 mul-first 하한값 이상이어야 함. buggy: 7*2=14 < 68*2/9=15 → violated |

**Rationale**: paper §6.2 Guideline 3 (multi-step arithmetic, 7 of 20) 대표 case. Function-arg 형태(`func.arg[N] relOp expr`)의 specialized @During 사용.

---

## web3bugs_8_H_03

- **Contract**: NFTXVaultUpgradeable
- **Function**: getRandomTokenIdFromFund
- **Bug line (original)**: 414
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L3: unsupported-construct-top)`

### Bug Description
`getRandomTokenIdFromFund()` 가 random pick 시 ERC1155 의 `quantity1155` 을 고려하지 않음. 즉 quantity > 1 인 ERC1155 슬롯도 단일 확률로 sampled 되어 weight 가 잘못됨 (reports/8.md H-03).
- Report: submission `code-423n4/2021-05-nftx-findings/issues/56`

### Not Detectable 사유 (L3: unsupported-construct-top)
- Random 값은 `keccak256(abi.encodePacked(block.timestamp, block.difficulty, ...)) % holdings.length` 로 계산됨
- abstract interpreter 는 `keccak256` 을 opaque builtin 으로 취급 → 결과 TOP 으로 propagate
- bug check 가 의존하는 "확률 분포의 편향" 은 값 수준 invariant 가 아님 — TOP 상태에서는 buggy/correct 동일 결과 (둘 다 TOP)
- ERC1155 probability weight 는 counting argument 으로만 증명 가능 → intent annotation 의 interval domain 으로 구분 불가 → L3

---

## web3bugs_35_H_11

- **Contract**: Ticks (library)
- **Function**: cross
- **Bug lines (original)**: 40, 49
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L5b: wrong-code)`

### Bug Description
`Ticks.cross()` 에서 swap 방향과 업데이트 대상 field 의 mapping 이 반대 (reports/35.md H-11):
- `zeroForOne == true` (token0 → token1 swap, pool tick 감소): token1 fees outside 가 갱신되어야 하나 buggy 코드는 `feeGrowthOutside0` 갱신
- `zeroForOne == false`: 대칭적으로 `feeGrowthOutside1` 대신 `feeGrowthOutside0` 갱신해야 함
- 즉 `0` 과 `1` 이 swap 되어야 함

### Not Detectable 사유 (L5b: wrong-code)
- Struct field access, state array write 모두 지원되므로 L1/L2/L3 아님
- 올바른 annotation 은 `@Post changed(ticks[nextTickToCross].feeGrowthOutside1, true)` (zeroForOne branch 기준, l4_l5 csv annotation_text 참조)
- 이 annotation 은 **field 방향 지식**("zeroForOne → outside1 갱신") 을 전제 — 개발자가 이미 정확한 방향을 알고 있어야 작성 가능 → bug awareness → L5b
- annotation_tier: weak (directional, paper §6.2 Guideline 1 "7 of 14 L5 expressible" 에 포함)

### Intent Annotation (from l4_l5 csv)
| Type | Expression | Expected | Rationale |
|------|------------|----------|-----------|
| Post | changed(ticks[nextTickToCross].feeGrowthOutside1, true) | violated | zeroForOne branch 에서 outside1 이 갱신되어야 하나 buggy 는 outside0 만 갱신 → unchanged → violated |

---

## web3bugs_52_H_15

- **Contract**: VaderRouter
- **Function**: _swap
- **Bug line (original)**: 326
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L4b: wrong-code — router wrapper)`

### Bug Description
`VaderRouter._swap()` 3-path hop 에서 pool 간 reserve 인자 순서가 뒤바뀜 (reports/52.md H-15):
- 의도: foreign → native (pool0) → different foreign (pool1)
- buggy: 첫 hop 에서 native amount 조건 체크가 foreign 기준으로 작동 → `require(nativeAmountIn == amountIn <= nativeBalance - nativeReserve == 0)` revert
- Report: `code-423n4/2021-11-vader-findings/issues/161` (sponsor confirmed)

### Not Detectable 사유 (L4b: wrong-code)
- **L4b 분류 근거** (l4_l5_classification.csv: `original_class=L4b, final_class=L4b, reclass_reason=limitation_types_md_self_inconsistent_L4b_list_and_L5b_examples_both_contain_this_case_I9_principle_picks_L4b`)
- VaderRouter 는 router wrapper — state 변경 없음, `BasePool.swap()` 을 외부 호출만 수행
- `VaderMath.calculateSwap()` 은 pure library 이지만 annotation grammar 에서 직접 함수 호출 불가 → 올바른 expected swap result 표현 불가
- 3-path 모두 revert 되므로 intent 가 도달하는 check point 자체가 없음 (silent sanction via require)
- I9 principle: arg[N] lint-level (router wrapper no state) → L4b archetype (52_H_16 twin)

### Intent Annotation (시도)
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| (시도 불가) | 326 | (`VaderMath.calculateSwap(...)` 함수 호출 annotation grammar 밖) | — | router wrapper + 외부 pool call + grammar 제한으로 작성 불가 |
