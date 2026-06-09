# RQ2 Annotation Plans

A document tracking per-contract contraction/annotation plans.
- Records discussions held prior to case JSON generation
- After contraction is complete, content is migrated into the case JSON

---

## web3bugs_35_H_12

- **Contract**: ConcentratedLiquidityPool
- **Function**: mint
- **Bug lines (original)**: 176; 184
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L5a: missing-state-update)`

### Bug Description
`mint()` modifies `liquidity` (line 176) but does not update `secondsPerLiquidity`. `swap()` correctly updates it via `secondsPerLiquidity += uint160((diff << 128) / liquidity)`, but the same update is missing in `mint()`.

### Reason Not Detectable
- This could be expressed via a `Changed(secondsPerLiquidity)` annotation, but writing such an annotation requires knowing that "when liquidity changes, secondsPerLiquidity must also be updated" — i.e., it presupposes awareness of the bug (L5a: missing-state-update).
- The root cause of the bug is missing the consistency with `swap()` — if the developer had caught that consistency at annotation time, they would have caught it in the code as well.
- Additionally, parameters are passed via `abi.decode`, so concrete values cannot be set through debugging annotations.

---

## web3bugs_43_H_02

- **Contract**: DelegatedStaking
- **Function**: unstake
- **Bug lines (original)**: 223; 224; 226
- **Pattern**: erroneous_accounting
- **Status**: excluded_fixed_code

### Notes
- The current code is already the fixed version (the exchange rate update is invoked before the shares computation).
- Excluded from the dataset since there is no bug to detect.

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

**Required Implementation**:
- `using SafeERC20Upgradeable for IUErc20;`

### Intent Annotations
| Type | Line (contraction) | Expression | Expected | Comment |
|------|-------------------|------------|----------|---------|
| During | 203, 205, 207, 213 | borrowIndex(Before < After) | violated | Because this is before the accrueInterest() call, borrowIndex is not updated → Before == After → violated |

Note: direction confirmed via Z3 solver: Before < After (z3_solvers/web3bugs_45_H_01_solver.py)

### Debug Annotations (Z3-generated values)
**LocalVar:**
| # | Variable | Value (interval) | Comment |
|---|----------|-------------------|---------|
| 1 | amount | [1000000000000000001, 1000000000000000001] | ~1e18 (1 token in wei) |
| 2 | account | symbolicAddress 101 | matches msg.sender |

**StateVar:**
| # | Variable | Value (interval) | Comment |
|---|----------|-------------------|---------|
| 1 | minBorrow | [2, 2] | to satisfy require |
| 2 | debtCeiling | [1000000000000000002, 1000000000000000002] | for getRemainingLoanSize |
| 3 | totalBorrows | [0, 0] | for getRemainingLoanSize |
| 4 | originationFee | [1000000000000001, 1000000000000001] | ~0.1%, for fee computation |
| 5 | WAD | [1000000000000000000, 1000000000000000000] | 1e18 |
| 6 | accountBorrows[101].principal | [1000000000000000001, 1000000000000000001] | ~1e18 |
| 7 | accrualBlockNumber | [1, 1] | for blockDelta computation |
| 8 | borrowIndex | [1000000000000000001, 1000000000000000001] | ~1e18, intent target |
| 9 | accountBorrows[101].interest | [1, 1] | for calculatingInterest |
| 10 | accountBorrows[101].interestIndex | [1000000000000000001, 1000000000000000001] | ~1e18 |
| 11 | accountBorrows[101].lastRepay | [1, 1] | to satisfy checkIsOverdue |
| 12 | maxBorrow | [2001005000000000005, 2001005000000000005] | to satisfy require |
| 13 | overdueBlocks | [2, 2] | to satisfy checkIsOverdue |

**GlobalVar:**
| # | Variable | Value (interval) | Comment |
|---|----------|-------------------|---------|
| 1 | block.number | [2, 2] | blockDelta = 1 |

**Intermediate Values (for verification):**
- fee = 1000000000000001 (~1e15)
- blockDelta = 1
- borrowIndexNew = 1000005000000000001
- calculatingInterest = 5000000000001
- borrowBalanceView = 1000005000000000002

### Value Generation Conditions (Z3 constraints)
```
C1: debtCeiling > totalBorrows
    Rationale: if (debtCeiling >= totalBorrows) {return debtCeiling - totalBorrows;} (getRemainingLoanSize)

C2: amount >= minBorrow
    Rationale: require(amount >= minBorrow) (borrow)

C3: amount <= debtCeiling - totalBorrows
    Rationale: require(amount <= getRemainingLoanSize()) (borrow)

C4: accountBorrows[101].principal >= 1
    Rationale: if (loan.principal == 0) {return 0;} (calculatingInterest)

C5: block.number > accrualBlockNumber
    Rationale: uint256 blockDelta = currentBlockNumber - accrualBlockNumber; (calculatingInterest)

C6: overdueBlocks >= block.number - accountBorrows[101].lastRepay
    Rationale: require(!checkIsOverdue(msg.sender)) (borrow) — since principal > 0 takes the else branch, this is the not-overdue condition

C7: (((accountBorrows[101].principal + accountBorrows[101].interest)
      * ((0.0005e16 * (block.number - accrualBlockNumber) * borrowIndex) / WAD + borrowIndex))
      / accountBorrows[101].interestIndex)
    - accountBorrows[101].principal >= 1
    Rationale: the calculatingInterest return value must be meaningful

C8: accountBorrows[101].principal
    + the calculatingInterest result from C7
    + amount + (originationFee * amount) / WAD
    <= maxBorrow
    Rationale: require(borrowBalanceView(msg.sender) + amount + fee <= maxBorrow) (borrow)
```

### Notes
- Bug: accrueInterest() is called after the borrowBalanceView()/getCreditLimit() check
- borrowBalanceView() → calculatingInterest() → reads borrowIndex (state variable)
- Without an accrueInterest() call, borrowIndex does not change → loan limit is checked against a stale value
- Detection is also possible with Changed(borrowIndex), but Before < After is more precise (it specifies the direction of increase)
- checkIsOverdue passes: when principal > 0, control takes the else branch and returns false if overdueBlocks >= diff

---

## web3bugs_45_H_02

- **Contract**: CreditLimitByMedian
- **Function**: getLockedAmount
- **Bug lines (original)**: 66
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L1b: loop-body-granularity)

### Bug Description
Inside the for loop of `getLockedAmount()`, the code reads `newLockedAmount = array[i].lockedAmount - 1`, but the correct implementation should be `array[i].lockedAmount - amount`. Because `1` is hard-coded, lockedAmount is not properly unlocked.

### Reason Not Detectable
IntentChecker does not analyze loops on a per-statement basis; instead, it computes the converged value of the entire loop via **fixed-point iteration**. As a result:
- Intent annotations cannot be placed on individual statements inside a loop body.
- Wrong-value bugs inside a loop body, such as `newLockedAmount = array[i].lockedAmount - 1` vs. `- amount`, cannot be expressed as intents.
- Annotations on the final return value outside the loop are possible, but since the fixed-point result is already imprecise, meaningful detection is difficult.

### Buggy Code
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
- **Bug lines (original)**: 89 (missing massUpdatePools() call before changing totalAllocPoint)
- **Pattern**: inconsistent_state_updates
- **Status**: not_detectable (L5a: missing-call-no-effect)

### Bug Description
The `add()` function does not call `massUpdatePools()` before incrementing `totalAllocPoint`. Existing pools' `accConcurPerShare` values are not refreshed using the previous `totalAllocPoint`, and the new (larger) `totalAllocPoint` is then applied, retroactively diluting existing stakers' rewards.

### Reason Not Detectable
The variables actually used in `add()` (`totalAllocPoint`, `poolInfo`, `pid[_token]`) all perform their roles correctly with no value-level anomalies. The bug's effect (the missing update of existing pools' `accConcurPerShare`) only manifests in variables outside the `add()` scope.

- It can be expressed as a post-condition such as `poolInfo[1].accConcurPerShare(Entry != Exit)`, but the developer must already be aware that "existing pools must be updated" to write it. If they were aware, they would simply add a `massUpdatePools()` call, so this is not a realistic detection scenario.
- The missing side effect cannot be detected from the function-local variables alone.

---

## web3bugs_83_H_02

- **Contract**: MasterChef
- **Function**: deposit
- **Bug lines (original)**: 170; 171; 172
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L4b: no-target-storage)

### Bug Description
In `deposit()`, when `depositFeeBP > 0`, a fee is computed and subtracted from `user.amount`, but there is no code that increments the recipient's (`feeRecipient`) `amount`. As a result, tokens equal to the deposit fee are permanently locked in the contract.

### Reason Not Detectable
IntentChecker's intent annotations validate **propositions over variable values**. To form a proposition, the target variable must exist in the code, but in this bug the variable that should be credited the fee (`feeRecipient.amount`) does not exist in the code, so the annotation cannot be constructed.

- The existing variables all perform their roles correctly with no value-level anomalies:
  - `user.amount`: computed precisely as `_amount - depositFee`
  - `depositFee`: computed correctly
  - `user.rewardDebt`: recomputed precisely based on the new amount
- None of the patterns — `Before/After`, `Assign/Current`, `Entry/Exit`, CommonClause — can detect any anomaly in the existing variables.

### Buggy Code
```solidity
if (_amount > 0) {
    if (pool.depositFeeBP > 0) {
        uint depositFee = _amount.mul(pool.depositFeeBP).div(_perMille);
        user.amount = SafeCast.toUint128(user.amount + _amount - depositFee);
        // BUG: depositFee is not credited to feeRecipient
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
In `viewHourlyBondAmount()`, the return value of `applyInterest()` is interpreted incorrectly.

**Two usage patterns within the same contract:**
```solidity
// (1) updateHourlyBondAmount(): treats applyInterest = principal+interest (full balance)
bond.amount = applyInterest(bond.amount, yA.accumulatorFP, yieldQuotientFP);
uint256 deltaAmount = bond.amount - oldAmount;  // computes delta separately

// (2) viewHourlyBondAmount(): treats applyInterest = interest only (delta) → BUG
return bond.amount + applyInterest(bond.amount, cumulativeYield, yieldQuotientFP);
```

The fact that `updateHourlyBondAmount()` separately computes `deltaAmount = bond.amount - oldAmount` shows that `applyInterest` is a function that **returns principal+interest (the full balance)**. Therefore `viewHourlyBondAmount()`'s `bond.amount + applyInterest(...)` **double-counts** the principal and returns a value roughly twice the actual balance.

### Detectability Analysis

**Candidate annotation**: `@During returnExpression == <expected_value>` (with debug annotations supplying concrete values)

**Problem**: To form an intent over `returnExpression`, we must know `applyInterest`'s return value, which depends on `cumulativeYield`, which is computed via `viewCumulativeYieldFP()` → `calcCumulativeYieldFP()`.

### Reason Not Detectable: the Loop and Widening in calcCumulativeYieldFP

`calcCumulativeYieldFP()` contains the following loop:

```solidity
function calcCumulativeYieldFP(
    YieldAccumulator storage yieldAccumulator,
    uint256 timeDelta
) internal view returns (uint256 accumulatorFP) {
    // Step 1: linear interpolation for sub-hour units
    uint256 secondsDelta = timeDelta % (1 hours);
    accumulatorFP =
        (yieldAccumulator.accumulatorFP *
            yieldAccumulator.hourlyYieldFP *
            secondsDelta) /
        (FP32 * 1 hours);     // denominator = 2^32 × 3600 ≈ 1.5×10^13

    // Step 2: hourly compound computation (the problematic loop)
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

Here FP32 = 2^32 (32-bit fixed-point). All variables with the `_FP` suffix are of the form (real value) × 2^32.

**Mathematical meaning of the loop (developer intent):**
- `hourlyYieldFP` is the per-hour interest rate (e.g., 1.0001 → in FP32 ≈ 4,295,396,762)
- Each iteration: `acc = acc × hourlyYield_real` (in real numbers, simple multiplication)
- After N hours: `acc = acc_initial × hourlyYield^N` (compound interest)
- Behaves correctly when actually executed in Solidity

**Problems that arise in IntentChecker's fixpoint analysis:**

IntentChecker analyzes loops via **fixpoint iteration + widening**:

1. When debug annotations specify `hoursDelta = 2`, the loop is executed concretely up to 2 iterations.
2. If the fixpoint (convergence) is not reached after 2 iterations, the **widening operator** is applied.

In the loop body `accumulatorFP = (accumulatorFP * hourlyYieldFP) / FP32`:
- `hourlyYieldFP > FP32` (interest rate > 1.0, the normal case): **increases** every iteration → no fixpoint → widening → **∞ (inf)**
- `hourlyYieldFP < FP32` (interest rate < 1.0, abnormal): **decreases** every iteration → no fixpoint → widening → **0**
- `hourlyYieldFP == FP32` (interest rate = 1.0, unrealistic): fixpoint is reached, but interest is 0% so it is meaningless

**As a result, `cumulativeYield` becomes 0 or ∞:**

```solidity
// applyInterest:
return (balance * accumulatorFP) / yieldQuotientFP;
```

- `cumulativeYield = 0` → `applyInterest` = 0 → buggy return = `bond.amount + 0` = `bond.amount`
  - The correct return is also = `applyInterest(amount, 0, yieldQuotient)` = 0 → indistinguishable
- `cumulativeYield = ∞` → `applyInterest` = ∞ → both buggy and correct = ∞ → indistinguishable

In both cases the buggy and correct return values are identical, so **the annotation is not violated and detection is impossible**.

### Can it be circumvented using only Step 1 (linear interpolation)?

Setting `hoursDelta = 0` (timeDelta < 3600) bypasses the loop, but:
```solidity
accumulatorFP = (acc * hourlyYield * secondsDelta) / (FP32 * 3600);
```
Since the denominator is `2^32 × 3600 ≈ 1.5×10^13`:
- For small debug values (acc=100, hourlyYield=100, secondsDelta=30): numerator = 300,000 → integer division → **0**
- For FP32-scale values (acc=2^32, hourlyYield=2^32): meaningful results emerge, but in this case if `secondsDelta` is 0 the result is still 0; even when `secondsDelta > 0`, the expected value of `applyInterest` itself must be precisely computed → this becomes a diagnostic-annotation issue

### Summary

| Item | Content |
|------|---------|
| **Limitation type** | loop-widening-precision-loss |
| **Root cause** | The loop in `calcCumulativeYieldFP` performs fixed-point compound interest computation → values change every iteration → fixpoint not reached → widening yields 0 or ∞ |
| **Impact** | `cumulativeYield` (a key intermediate value) is imprecise → the expected value of the `returnExpression` annotation cannot be computed |
| **Why circumvention fails** | Even running without the loop (hoursDelta=0), the linear-interpolation denominator is so large (2^32×3600) that small values become 0; even using FP32-scale values requires pre-computing the applyInterest result, which is itself a diagnostic problem |
| **Comparison (updateHourlyBondAmount)** | Same problem — `getUpdatedHourlyYield` internally also calls `calcCumulativeYieldFP`, so the same widening problem occurs |

---

## web3bugs_25_H_01

- **Contract**: CompositeMultiOracle
- **Function**: _peek; _get
- **Bug lines (original)**: 116; 126
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L4a: inexpressible-expected-value)`

### Bug Description
In `_peek()`/`_get()`, when computing `priceOut`, the code divides by `10 ** source.decimals` (token decimals), but the correct implementation should divide by `10 ** IOracle(source.source).decimals()` (oracle output decimals, always 18). On a chained oracle path, the price scale becomes cumulatively wrong and the returned value is inflated. (e.g., on the USDC→DAI→USDT path, inflated by `1e30`.)

### Reason Not Detectable
- Interface calls are now supported, so the return value of `IOracle(source.source).peek()` is not TOP.
- However, the correct denominator is `10 ** IOracle(source.source).decimals()` (the oracle output precision).
- `IOracle(source.source).decimals()` is **a function not called** in the buggy code → no variable in scope holds the value.
- The annotation grammar does not allow function calls (intentValue is restricted to combinations of variables, constants, and arithmetic).
- Therefore, the correct expected value cannot be expressed as an annotation (L4a).

---

## web3bugs_34_H_01

- **Contract**: DrawCalculator
- **Function**: _numberOfPrizesForIndex
- **Bug lines (original)**: 422; 423; 424
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L1a: loop-widening)

### Bug Description
In `_numberOfPrizesForIndex()`, when computing the prize count for a given tier, a while loop subtracts every lower power, returning a value smaller than the correct one.

**Buggy formula**: `b^d - b^(d-1) - b^(d-2) - ... - b^0` (over-subtracted by the while loop)
**Correct formula**: `b^d - b^(d-1)` (a single subtraction, no loop needed)

Example (b=16, d=3): buggy = 4096 - 256 - 16 - 1 = 3823, correct = 4096 - 256 = 3840

### Reason Not Detectable
The function itself is `internal pure` and all inputs come from parameters, so there is no interface-call-return-top issue. Concrete values can be assigned to parameters via debugging annotations.

However, the fixpoint iteration + widening over the while loop causes over-approximation:
- In `numberOfPrizesForIndex -= bitRangeDecimal**(_prizeTierIndex - 1)`, the `-=` operator is used.
- Different exponential values are subtracted on each iteration, so no fixpoint is reached → widening is applied.
- Widening is a **sound over-approximation**: it produces a range that contains both the actual value (3823) and the correct value (3840).
- In the interval domain it would be [0, 4096]; in the flat domain it would be Top → 3840 ∈ range → violation not detected.

**Key point**: the 0 produced by widening is the lower bound of the over-approximation, not actual program behavior. The actual buggy output is 3823 and the correct output is 3840. Both are contained in the widened range, so they are indistinguishable.

### Buggy Code
```solidity
function _numberOfPrizesForIndex(uint8 _bitRangeSize, uint256 _prizeTierIndex)
    internal pure returns (uint256)
{
    uint256 bitRangeDecimal = 2**uint256(_bitRangeSize);
    uint256 numberOfPrizesForIndex = bitRangeDecimal**_prizeTierIndex;

    while (_prizeTierIndex > 0) {
        numberOfPrizesForIndex -= bitRangeDecimal**(_prizeTierIndex - 1);  // BUG: over-subtraction
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
In `consult()`, `sumNative` and `sumUSD` are accumulated independently inside a for loop and finally divided as `(sumUSD * decimals) / sumNative`. The native amount and USD price of each pair are not properly weight-combined, so the consultation result is incorrect.

### Reason Not Detectable

**Problem 1: Intent annotations cannot be placed inside the loop body**
- The bugs are at line 129 (`sumNative += ...`) and line 152 (`sumUSD += ...`), both inside the loop body.
- The correct fix is a change to the accumulation scheme itself (e.g., a weighted average) → cannot be expressed as an intent on a single line's value.
- Even attaching an intent to `result` (line 156) is meaningless if `sumUSD` and `sumNative` are already Top.

**Problem 2: Widening due to `+=`**
- `sumNative += pairData.price1Average.mul(1).decode144()` → `+=` operator → widening direction is ∞ → **Top**
- `sumUSD += uint256(price) * (10**10)` → `+=` operator → widening direction is ∞ → **Top**
- Result: `result = (Top * Top) / Top` → **Top**
- Both buggy and correct are Top, so they are indistinguishable.

**Note**: `price` is Top because it comes from the `AggregatorV3Interface(...).latestRoundData()` interface call, but this is a secondary problem solvable by debugging annotations. The fundamental blocker is the `+=` widening inside the loop.

### Buggy Code
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
In the final computation of `consult()`, the code uses `IERC20Metadata(token).decimals()` (= 18), but the correct implementation should use `10 ** IERC20Metadata(token).decimals()` (= 1e18). The scaling factor of 18 instead of 1e18 grossly distorts the result.

### Reason Not Detectable
Both `sumNative` and `sumUSD` are accumulated in the loop with `+=` → widening → Top. The final `result = (sumUSD * decimals) / sumNative` = Top / Top = Top, so the scaling difference cannot be detected. Same loop structure as web3bugs_52_H_34.

### Buggy Code
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
The same contract, same function, and same bug line (156) as web3bugs_52_H_04, redundantly reported by a different auditor. Analyzed under 52_H_04.

---

## web3bugs_59_H_04

- **Contract**: AuctionBurnReserveSkew
- **Function**: getPegDeltaFrequency
- **Bug line (original)**: 131
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L1a: loop-widening)

### Bug Description
In `getPegDeltaFrequency()`, when `count < auctionAverageLookback`, the denominator should be `count` instead of `auctionAverageLookback`. The current implementation uses a denominator larger than the actual number of observations and returns an underestimated value.

### Reason Not Detectable
`total` is accumulated inside the loop as `total = total + pegObservations[index]` (a `+=`-style accumulation) → widening → Top. The final result, whether `total * 10000 / auctionAverageLookback` or `total * 10000 / count`, is Top → indistinguishable.

### Buggy Code
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
- **Function**: _calculateUSDVPrice (same structure: _calculateVaderPrice)
- **Bug lines (original)**: 399; 403
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L1a: loop-widening)

### Bug Description
In `_calculateUSDVPrice()`, when there are two or more pairs, the USDV price is computed incorrectly. It computes the "ratio of weighted averages" rather than the "weighted average of ratios".

**Mathematical issue**: `E[X/Y] ≠ E[X]/E[Y]`
- **Correct**: `Σ(weight_i/totalWeight × foreignPrice_i / nativePrice_i)` — first compute the USD price per pair, then take a weighted average
- **Buggy**: `Σ(weight_i/totalWeight × foreignPrice_i) / Σ(weight_i/totalWeight × nativePrice_i)` — separately average the foreign prices and the native prices, then divide

The two expressions are equivalent for a single pair, but differ when there are two or more. `_calculateVaderPrice()` has the same structural problem.

### Reason Not Detectable

**Problem 1: Widening due to `+=`**
- `totalUSD += (foreignPrice * liquidityWeights[i]) / totalUSDVLiquidityWeight` → `+=` → widening → **Top**
- `totalUSDV += (nativeAvgPrice * liquidityWeights[i]) / totalUSDVLiquidityWeight` → `+=` → widening → **Top**
- Result: `(Top * 1 ether) / Top` → **Top**
- Both buggy and correct are Top, so they are indistinguishable.

**Problem 2: Intent annotations cannot be placed inside the loop body**
- The bug lies in the accumulation scheme itself (average of ratios vs. ratio of averages).
- Fixing it requires changing the structure of the loop body itself → cannot be expressed as an intent on a single line's value.

**Note**: `getChainlinkPrice()` → `oracle.latestRoundData()` is an interface call so `foreignPrice` is also Top, but this is a secondary problem solvable by debugging annotations. The fundamental blocker is the `+=` widening inside the loop.

### Buggy Code
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
In the for loop of `syncVaderPrice()`, pairs with `timeElapsed < pairData.updatePeriod` are skipped via `continue`, and that pair's contribution is omitted entirely.

**Concrete issues**:
1. `pastLiquidityWeights[i]` remains 0 (line 140 not executed) → omitted from the numerator of `_calculateVaderPrice`
2. The pair is not included in `_totalLiquidityWeight` (line 144 not executed)
3. `pastTotalLiquidityWeight` is the previously stored **total** sum (line 124) → the denominator includes all pairs
4. Line 147 stores the incomplete `_totalLiquidityWeight` to state → the next call's `pastTotalLiquidityWeight` is also polluted

**Result**: numerator covers only some pairs while denominator covers all → price is underestimated.

**Correct fix**: before `continue`, add `pastLiquidityWeights[i] = pairData.pastLiquidityEvaluation` and `_totalLiquidityWeight += pairData.pastLiquidityEvaluation`.

### Reason Not Detectable

**Problem 1: `+=` widening**
- `_totalLiquidityWeight += currentLiquidityEvaluation` → `+=` inside loop → widening → **Top**
- Consequently the `totalLiquidityWeight` state variable is also Top

**Problem 2: Interface calls**
- Inside `_updateVaderPrice`, interface calls such as `pair.token0()`, `pair.getReserves()`, and `UniswapV2OracleLibrary.currentCumulativePrices()` → Top

**Problem 3: Control-flow bug**
- Selective omission caused by `continue` is hard to express as a value annotation.
- "Skipped pairs must also be included in the weight" is a control-flow property, not a value property.

### Buggy Code
```solidity
function syncVaderPrice() public override returns (...) {
    uint256 _totalLiquidityWeight;
    ...
    pastTotalLiquidityWeight = totalLiquidityWeight[uint256(Paths.VADER)];  // total sum

    for (uint256 i; i < totalPairs; ++i) {
        ...
        if (timeElapsed < pairData.updatePeriod) continue;  // line 131: skip → none of the below executes

        pastLiquidityWeights[i] = pastLiquidityEvaluation;   // line 140: remains 0 when skipped
        ...
        _totalLiquidityWeight += currentLiquidityEvaluation; // line 144: not included when skipped
    }

    totalLiquidityWeight[uint256(Paths.VADER)] = _totalLiquidityWeight;  // line 147: stores incomplete sum
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
In `_calculateUSDVPrice()`, Chainlink's `foreignPrice` is returned with 8 decimals (1e8 = $1), but the protocol expects 18 decimals (1e18 = $1). `foreignPrice` is accumulated into `totalUSD` without any scaling, so the final result is returned at the 1e8 scale when it should be at 1e18.

### Reason Not Detectable
Both `totalUSD` and `totalUSDV` are accumulated via `+=` inside the loop -> widening -> Top. The final `(totalUSD * 1 ether) / totalUSDV` = Top / Top = Top. The scaling error (1e8 vs 1e18) cannot be detected. Same TWAP oracle loop structure as web3bugs_70_H_03 and web3bugs_70_H_04.

### Bug Code
```solidity
// foreignPrice = getChainlinkPrice(address(foreignAsset));  // 1e8 (8 decimals)
totalUSD += (foreignPrice * liquidityWeights[i]) / totalUSDVLiquidityWeight;  // += widening -> Top
totalUSDV += ...;  // += widening -> Top

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
In `resume()`, the redemption amount (`_redeemAmount`) for each index pool is computed using division (`_divCeil`), but the correct computation should be multiplication.

**Mathematical issue**:
- `_deductionFromIndex` = total amount to be deducted from all indices (x 1e6 scaled)
- `_shareOfIndex` = the index's share ratio (x 1e6, e.g. 30% -> 300000)
- **Buggy**: `_divCeil(total, ratio)` = total / 0.3 -> 3.3x the total (over-redemption)
- **Correct**: `total * ratio / 1e6` -> 30% of the total (correct proportional allocation)

If there is only one index, `shareOfIndex = 1e6` so dividing yields the same value. With two or more indices, each index is over-redeemed.

### Reason Not Detectable (L1b: loop-body-granularity)

**Interface calls are now supported**: `vault.debts()`, `totalLiquidity()` -> can be made concrete via @IReturn. The L2a blocker is resolved.

**New blocker: L1b** (corresponds to L1b: loop-body-granularity in paper Fig 8)

```solidity
uint256 _debt = vault.debts(address(this));  // vault = IVault -> interface call -> Top
...
uint256 _deductionFromIndex = (_debt * _totalCredit * MAGIC_SCALE_1E6) /
    totalLiquidity();                         // totalLiquidity() -> vault.underlyingValue() -> Top
```

- `_debt` = Top (interface call) -> `_deductionFromIndex` = Top
- `_redeemAmount = _divCeil(Top, _shareOfIndex)` = **Top**
- Whether buggy (division) or correct (multiplication), the result is Top -> indistinguishable

**Convergence of loop body variables**:
- `_index`, `_credit`, `_shareOfIndex`, `_redeemAmount` -- newly declared each iteration (declaration, not accumulation)
- Can converge via join in fixpoint iteration -> loop-widening does not apply to these
- Only the accumulator `_actualDeduction += ...` is subject to widening

**However, loop-widening is a secondary concern**:
- `IIndexTemplate(_index).compensate(_redeemAmount)` -> interface call inside the loop -> return value Top
- `_actualDeduction += Top` -> already Top even without widening
- The fundamental blocker is the interface call, not loop widening

**Can it be resolved with debugging annotations?**:
- `vault.debts()`, `totalLiquidity()` (called before the loop) -> can be made concrete via debugging annotations
- However, `IIndexTemplate(_index).compensate()` inside the loop -> called with a different `_index` per iteration -> per-iteration return values are hard to specify
- Additionally, the bug lines (709-711) lie inside the loop body -> intent annotations cannot be placed there (loop-body-granularity)

### Bug Code
```solidity
function resume() external {
    ...
    uint256 _debt = vault.debts(address(this));           // interface call -> Top
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
            uint256 _redeemAmount = _divCeil(              // line 709: BUG -- should be multiplication, not division
                _deductionFromIndex,                       // line 710: Top (from interface)
                _shareOfIndex                              // line 711
            );
            _actualDeduction += IIndexTemplate(_index).compensate(  // interface call -> Top
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
In `belowMaintenanceThreshold()`, the comparison direction is reversed. The function name suggests it should return whether the account is "below the maintenance threshold," but the actual implementation returns `true` when the account is in a healthy state:

```solidity
return 100 * holdings >= liquidationThresholdPercent * loan;  // BUG: >= should be < or <=
```

- `holdings >= loan * 1.1` -> account is healthy -> returns `true`
- The semantics of the return value are the opposite of what the name (`belowMaintenanceThreshold`) implies

### Reason Not Detectable

**Root cause: external-call-state-unknown (L2b)**

`belowMaintenanceThreshold` -> `loanInPeg` / `holdingsInPeg` -> `sumTokensInPegWithYield` (loop) -> `yieldTokenInPeg` -> external contract calls:

```solidity
// yieldTokenInPeg (line 280):
uint256 yieldFP = Lending(lending()).viewBorrowingYieldFP(token);  // external contract call -> Top

// yieldTokenInPeg (line 287):
return PriceAware.getCurrentPriceInPeg(...);                       // external contract call -> Top
```

- A concrete type for `Lending` exists via `import "./Lending.sol"`, but it is a separately deployed external contract
- `lending()` returns an address from `RoleAware.mainCharacterCache[LENDING]` (type casting, not a constructor)
- Debugging annotations cannot be applied to state variables of the `Lending` contract -> internal computation flows to Top
- `PriceAware.getCurrentPriceInPeg()` has the same issue

**Call chain**:
```
belowMaintenanceThreshold
  -> loanInPeg(account, true)
    -> sumTokensInPegWithYield(account.borrowAmounts, account.borrowTokens, true)
      -> for loop (index-bound)
        -> yieldTokenInPeg(token, amount, true)
          -> Lending(lending()).viewBorrowingYieldFP(token)  // Top
          -> PriceAware.getCurrentPriceInPeg(...)            // Top
  -> holdingsInPeg(account, true)
    -> (same structure, Top from external call)
```

**Result**:
- `loan` = Top (accumulation of external call results)
- `holdings` = Top (same)
- `100 * Top >= liquidationThresholdPercent * Top` -> Top >= Top -> **Top**
- Whether buggy (`>=`) or correct (`<`), the result is Top -> indistinguishable

### Bug Code
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
The StableSwap AMM uses two amplifiers (A1, A2), and `determineA()` selects which A to use based on the pool balance ratio (`xp[0]` vs `xp[1]`). When a swap crosses the target price and A switches, the correct implementation should **split the swap into two stages** at the target price, applying A1 and A2 respectively.

However, `getYC()` **recomputes the entire swap with the new A** when A changes:

```solidity
// 5. Check if we switched A's during the swap
if (aNew == a){     // We have used the correct A
    return y;
} else {    // We have switched A's, do it again with the new A
    return getY(self, tokenIndexFrom, tokenIndexTo, x, xp, aNew, d);  // BUG
}
```

`d` is the invariant computed with the old `a`, but it is used together with `aNew`. As a result, the A2 curve is applied to the entire trade, distorting the execution price.

### Reason Not Detectable

**Root cause: inexpressible-expected-value (L4a)**

**1. No qualitative difference**

The return value of `getYC` flows through `_calculateSwap` -> `swap` and updates `self.balances[tokenIndexTo]`:
- buggy: `balances[tokenIndexTo]` decreases (by an incorrect dy)
- correct: `balances[tokenIndexTo]` decreases (by the correct dy)

Both **change in the same direction**, so qualitative annotations such as `Changed` or `Before > After` cannot distinguish them.

**2. The correct value cannot be expressed as an arithmetic formula**

To obtain the correct result:
1. Compute the **split point `dx_1`** -- the dx_1 satisfying `xp[0] + dx_1 == xp[1] - getY(dx_1)` (a solution of an equation, not a simple arithmetic expression)
2. Perform partial swap 1 via `getY(..., a, d)`
3. Compute a new `d_2 = getD(intermediate state, aNew)` from the intermediate state
4. Perform partial swap 2 via `getY(..., aNew, d_2)`

Among these, `dx_1` (the split point) is a value that does not exist in the code and cannot be expressed as a combination of `+`, `-`, `*`, `/` over existing variables (it is itself the solution of a nonlinear equation). Therefore an annotation of the form `@Post return == expr` cannot be constructed.

**3. Attempted annotation approaches and reasons for failure**

| Approach | Reason for failure |
|----------|-------------------|
| `return == concrete_value` | Requires precomputing the correct value -> providing the answer rather than detecting the bug |
| `return == y` (value computed with old A) | The correct code also does not return `y` (split result != y) -> both sides violate |
| `getY.arg == a` (parameter constraint) | "Keeping old A" is not the correct fix (the fix is to split) |
| `Changed`/`Before > After` on balances | Both buggy and correct satisfy it equally |
| `getD([x, return], aNew) == getD(xp, aNew)` | Function calls inside annotations are not allowed |

### Loop convergence (for reference)

`getY` contains a Newton's method loop (MAX_LOOP_LIMIT=256), but with concrete values supplied via debugging annotations, it converges within ~4 iterations. **Loop-widening is not the blocker**. The fundamental blocker is the inexpressibility of the correct value.

The Newton's method loop inside `getD` similarly converges with concrete inputs.

The first loop (`for i < numTokens`) is an index-bound loop iterating only 2-3 times, effectively unrolled.

---

## web3bugs_51_H_06

- **Contract**: SwapUtils (library)
- **Function**: addLiquidity
- **Bug line (original)**: 1231
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L4a: inexpressible-expected-value)

### Bug Description

In StableSwap's `addLiquidity`, when imbalanced liquidity is added, an "ideal balance" is computed to determine fees. This value is computed as `d1/d0 * old_balance`, and the ratio is meaningful only if d0 and d1 lie on the same curve (same A value).

However, this contract uses a dual-A system (A1, A2), and `determineA()` selects A based on the token ratio (`xp[0]` vs `xp[1]`):

```solidity
v.d0 = getD(self);
// -> internally: determineA(self, _xp(self)) -> A based on old balances (e.g., A1)

v.preciseA = determineA(self, _xp(self, newBalances));
// -> A based on new balances (e.g., A2; A may have switched)

v.d1 = getD(_xp(self, newBalances), v.preciseA);
// -> D computed with A2

idealBalance = v.d1.mul(self.balances[i]).div(v.d0);  // BUG (line 1231)
// d0 is on the A1 curve, d1 is on the A2 curve -> the D ratio across different curves is meaningless
```

If the imbalanced liquidity addition flips the token ratio (`xp[0] < xp[1]` -> `xp[0] > xp[1]`), d0 and d1 are computed with different A values, making `idealBalance` incorrect -> fee miscalculation -> both the final `self.balances[i]` and `toMint` are inaccurate.

### Reason Not Detectable

**Root cause: inexpressible-expected-value (L4a)**

**1. No qualitative difference**

After `addLiquidity`, `self.balances[i]` increases in both buggy and correct cases (liquidity is added, fee is deducted). Qualitative annotations such as `Changed` or `Before < After` cannot distinguish them.

**2. The correct value cannot be expressed as an arithmetic formula**

To obtain the correct `idealBalance`, we need `getD()` results computed with d0 and d1 using **the same A**:
- correct_d0 = getD(oldBalances, A_consistent)
- correct_d1 = getD(newBalances, A_consistent)
- correct_idealBalance = correct_d1 * old_balance / correct_d0

`getD()` is an iterative Newton's method function, so it cannot be expressed by an annotation expression (a combination of `+`, `-`, `*`, `/`). Function calls inside annotations are also not allowed.

**3. Attempted annotation approaches and reasons for failure**

| Approach | Reason for failure |
|----------|-------------------|
| `Changed` / `Before < After` on self.balances | Both buggy and correct satisfy it equally (both increase) |
| `self.balances[i] == expr` | The correct value depends on the result of a `getD()` call -> not expressible as an arithmetic formula |
| `getD(newBal, A_old) * bal / getD(oldBal, A_old)` | Function calls inside annotations are not allowed |
| concrete value annotation | Requires manually computing the correct value -> providing the answer rather than detecting the bug |

### Reference: Newton loop convergence

As in 51_H_04, the Newton's method loop inside `getD` converges within ~4 iterations under concrete debugging annotations. Therefore loop-widening (L1) is not the blocker. The fundamental blocker is the inexpressibility of the correct value.

---

## web3bugs_70_H_10

- **Contract**: LiquidityBasedTWAP
- **Function**: syncVaderPrice
- **Bug line (original)**: 187
- **Pattern**: inconsistent_state_updates
- **Status**: `annotated`

### Bug Description

When `syncVaderPrice()` calls `_updateVaderPrice()`, `previousPrices[uint256(Paths.VADER)]` is not updated. After being initialized in `setupVader()`, it is never updated again. As time passes, it diverges from the actual VADER price -> distorts `currentLiquidityEvaluation` -> inaccurate TWAP price.

### External Type Dependencies

The `ExchangePair` struct and `Paths` enum are defined in the `ILiquidityBasedTWAP` interface, which is inherited via `LiquidityBasedTWAP is ILiquidityBasedTWAP`.

- This is **different from** L2 (cross-deployment-call-top) -- it is **type inheritance**, not an external function call
- `twapData` is the target contract's own storage -> within annotation scope
- It suffices to resolve the interface's struct/enum definitions during dependency pre-analysis

```
ILiquidityBasedTWAP (interface)
|-- struct ExchangePair { lastMeasurement, updatePeriod, pastLiquidityEvaluation, ... }
|-- enum Paths { VADER, USDV }
+-- LiquidityBasedTWAP inherits -> can use the struct/enum types
```

### Loop Analysis

The loop in `syncVaderPrice` (lines 90-111) contains `_totalLiquidityWeight += currentLiquidityEvaluation` (accumulation). This is the same loop that caused loop-widening in 70_H_03/04/05.

However, the annotation target for this bug is `previousPrices[0]`, and there is **no write** to `previousPrices` inside the loop (in the buggy code). Thus the widening of `_totalLiquidityWeight` does not affect the Changed/Unchanged judgment for `previousPrices`.

### Annotation Insertion Order and Line Placement

**Step 1: Insert intent annotation** -- contraction line 114 (just before `}`)

```
113: totalLiquidityWeight[uint256(Paths.VADER)] = _totalLiquidityWeight;
114: // @Post Changed(previousPrices[0])      <- inserted
115: }                                         <- originally line 114
```

**Step 2: Insert debug annotations** -- starting at line 85 (just before the function body, 8 lines)

```
85: // @GlobalVar block.timestamp = [10000, 10000]
86: // @StateVar previousPrices[0] = [1000000000000000, 1000000000000000]
87: // @StateVar vaderPairs.length = [1, 1]
88: // @StateVar totalLiquidityWeight[0] = [1, 1]
89: // @StateVar twapData[1].lastMeasurement = [1000, 1000]
90: // @StateVar twapData[1].updatePeriod = [60, 60]
91: // @StateVar twapData[1].pastLiquidityEvaluation = [1, 1]
92: // @StateVar twapData[1].nativeTokenPriceCumulative = [0, 0]
93: uint256 _totalLiquidityWeight;            <- originally line 85
```

The values are determined via Z3 constraint solving (`z3_solvers/web3bugs_70_H_10_solver.py`).
- `timeElapsed = 10000 - 1000 = 9000 >= updatePeriod(60)` -> guaranteed to enter the loop body
- `previousPrices[0] = 1e15` -> a VADER price of 0.001 at the 1e18 scale

At interpret time, the debug annotations inject concrete values -> analysis runs -> the intent annotation result is reported.

### Z3 Constraints

The following constraints must be solved with Z3 when determining debug annotation values:

1. **Underflow prevention** (Solidity 0.8.9 checked arithmetic -> avoid revert)
   - `block.timestamp >= twapData[1].lastMeasurement` (line 93: `block.timestamp - pairData.lastMeasurement`)
2. **Loop body entry guarantee**
   - `block.timestamp - twapData[1].lastMeasurement >= twapData[1].updatePeriod` (line 95: `continue` if `timeElapsed < updatePeriod`)
3. **Overflow prevention inside _updateVaderPrice**
   - Avoid overflow in `reserveNative * previousPrices[0]` (lines 72-73)
   - Avoid overflow in `reserveForeign * chainlinkPrice` (line 74)
   - However, `reserveNative` and `reserveForeign` come from external interface calls -> Top. Constraints are set within the range of variables that can be annotated.
4. **Meaningful values inside unchecked block**
   - `nativeTokenPriceCumulative(current) >= twapData[1].nativeTokenPriceCumulative` (lines 62-63; unchecked so no revert, but meaningful for analysis)

### Debug Annotation Notes

- `block.timestamp` -> must be set as GlobalVar (analysis fails if missing)
- `vaderPairs.length = [1, 1]` -> setting dynamic array length (DebugInitializer supports special handling of `.length`)
- `twapData[1]` -> literal key for a mapping (automatic AddressSet conversion for address-keyed mappings)
- `twapData[1].lastMeasurement`, etc. -> struct member access on a mapping value (requires the ExchangePair struct definition via pre-analysis)

### Predicted Intent Annotation Result

```
// @Post Changed(previousPrices[0])
```

- **Buggy**: no write to `previousPrices[0]` -> Unchanged -> violates `Changed` -> **alarm**
- **Correct**: new price is recorded in `previousPrices[0]` -> Changed -> **pass**

Note: the `Changed` keyword becomes available after Issue 2 (code_modification_issues.md) is implemented. With current syntax it can be substituted with `previousPrices[0](Entry != Exit)` (since the buggy code performs no write at all, Entry == Exit -> equivalent effect).

---

## web3bugs_58_H_02

- **Contract**: LpIssuer
- **Function**: _chargeFees
- **Bug line (original)**: 270
- **Bug line (contraction)**: 85
- **Pattern**: erroneous_accounting
- **Status**: `annotated` (was: `not_detectable,interface-call-return-top`)

### Bug Description
The performance fee formula is incorrect. In `toMint = (baseSupply * minLpPriceFactor) / DENOMINATOR`:
1. `minLpPriceFactor = lpPrice * DENOMINATOR / hwm` -> always > DENOMINATOR if lpPrice > hwm
2. Therefore `toMint > baseSupply` -- each call mints more LP than the entire supply
3. The `performanceFee` ratio is never used in the calculation (it is only checked > 0)
- Correct: `toMint = baseSupply * (minLpPriceFactor - DENOMINATOR) * performanceFee / (DENOMINATOR^2)`
- Report: confirmed by sponsor (MihanixA)

### Dependencies
**Libraries (require pre-analysis):**
- `CommonLibrary.sol`: `DENOMINATOR = 10^9`, `PRICE_DENOMINATOR = 10^18`, `YEAR = 31536000` -- constants, inlined

**Interfaces:**
- `ILpIssuerGovernance`: `delayedProtocolParams()`, `delayedStrategyParams()`, `delayedProtocolPerVaultParams()`, `internalParams()`
- ERC20 inheritance: `_mint()` -- modifies totalSupply/balanceOf

### Loop Analysis
Min-finding pattern. Not accumulation (`+=`); monotonically non-increasing -> not subject to widening. Array length is concrete (=2) -> exactly 2 unrolled iterations. **The loop is not a blocker.**

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| StateVar | lastFeeCharge | [0, 0] | 23 | so that elapsed is sufficiently large |
| StateVar | _lpPriceHighWaterMarks[0] | [1900000000000000000, 1900000000000000000] | 23 | 1.9e18, smaller than lpPrice(2e18) |
| StateVar | _lpPriceHighWaterMarks[1] | [2900000000000000000, 2900000000000000000] | 23 | 2.9e18, smaller than lpPrice(3e18) |
| LocalVar | thisNft | [1, 1] | 23 | NFT id |
| LocalVar | tvls[0] | [2000000000000000000000, 2000000000000000000000] | 23 | 2000e18 |
| LocalVar | tvls[1] | [3000000000000000000000, 3000000000000000000000] | 23 | 3000e18 |
| LocalVar | supply | [1000000000000000000000, 1000000000000000000000] | 23 | 1000e18 |
| LocalVar | deltaTvls[0] | [100000000000000000000, 100000000000000000000] | 23 | 100e18 (isWithdraw=false, unused) |
| LocalVar | deltaTvls[1] | [150000000000000000000, 150000000000000000000] | 23 | 150e18 |
| LocalVar | deltaSupply | [100000000000000000000, 100000000000000000000] | 23 | 100e18 |
| LocalVar | isWithdraw | false | 23 | baseSupply = supply |
| IReturn | vg.delayedProtocolParams().managementFeeChargeDelay | [0, 0] | 23 | delay=0, prevent early return |
| IReturn | vg.delayedStrategyParams().managementFee | [0, 0] | 23 | skip management fee |
| IReturn | vg.delayedStrategyParams().performanceFee | [100000000, 100000000] | 23 | 10^8 = 10% (> 0) |
| IReturn | vg.delayedStrategyParams().strategyPerformanceTreasury | symbolicAddress 1 | 23 | mint target |
| IReturn | vg.delayedProtocolPerVaultParams().protocolFee | [0, 0] | 23 | skip protocol fee |

- isWithdraw=false -> baseSupply = supply = 1000e18
- baseTvls[0] = 2000e18, baseTvls[1] = 3000e18
- lpPrice[0] = 2e18 > hwm(1.9e18) ok, lpPrice[1] = 3e18 > hwm(2.9e18) ok
- delta[0] ~ 1052631578, delta[1] ~ 1034482758 (both > DENOMINATOR)
- minLpPriceFactor = 1034482758
- Buggy: toMint = 1000e18 * 1034482758 / 10^9 ~ 1034.48e18 > baseSupply(1000e18)
- Correct: toMint ~ 3.45e18 << baseSupply

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| During | 85 | toMint < baseSupply | violated | Performance fee is a portion of profit -> cannot mint more than totalSupply. Buggy: 1034e18 > 1000e18 -> violated |

---

## web3bugs_29_H_14

- **Contract**: IndexPool
- **Function**: _computeSingleOutGivenPoolIn
- **Bug line (original)**: 279
- **Pattern**: erroneous_accounting
- **Status**: excluded (overflow-revert)

### Bug Description
`_computeSingleOutGivenPoolIn` calls `_pow(poolRatio, _div(BASE, normalizedWeight))`, where `_div(BASE, normalizedWeight)` returns a WAD-scale (18 decimals) value. However, `_pow(a, n)` treats `n` as a plain integer, so for example with a 25% weight the exponent becomes `4 * 10^18` and `a^(4*10^18)` is attempted -> integer overflow -> revert.

The correct call is `_compute(poolRatio, _div(BASE, normalizedWeight))`, where `_compute` separates the WAD-scale exponent into whole and fractional parts.

### Reason for Exclusion
- In Solidity >=0.8.0, overflow auto-reverts (checked arithmetic)
- Execution itself halts rather than silently returning an incorrect value
- **Does not match the definition of a numeric logical error**: not a case of "returning" an incorrect value at runtime after passing compilation, but rather reverting due to overflow

---

## web3bugs_29_H_15

- **Contract**: IndexPool
- **Function**: _computeSingleOutGivenPoolIn
- **Bug line (original)**: 282
- **Pattern**: erroneous_accounting
- **Status**: excluded (overflow-revert)

### Bug Description
Line 282 uses raw `*` in `(BASE - normalizedWeight) * _swapFee`, but should use the fixed-point multiplication `_mul`. The raw `*` result becomes BASE^2 scale, and the subsequent `BASE - zaz` then triggers integer underflow -> Solidity 0.8.x revert.

### Reason for Exclusion
- Same function as 29_H_14, same exclusion rationale
- A revert due to underflow, not a numeric logical error returning an incorrect value

---

## web3bugs_112_H_01

- **Contract**: StakerVault
- **Function**: transfer
- **Bug lines (original)**: 112; 113; 117; 118
- **Bug lines (contraction)**: 31; 32; 36; 37 (after annotation insertion: 31; 32; 37; 39)
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L5b: wrong-code)`

### Bug Description
In `transfer()`, the `balances` updates (contraction lines 31-32) are executed **before** the `userCheckpoint()` calls (contraction lines 37, 39). `userCheckpoint()` internally reads `stakedAndActionLockedBalanceOf(user)` -> `balances[user]` to compute rewards, so rewards are computed using the already-modified balance. By repeatedly transferring between their own accounts, a recipient can over-claim rewards.

For comparison: `transferFrom()` in the same contract (original lines 155-158) correctly uses the **checkpoint -> balance update** order.

### Reason Not Detectable (L5b: wrong-code -- operation ordering)

**The only possible intent**: `@During changed(balances[msg.sender], false)` (standalone, immediately before the checkpoint call)

**Why bug awareness is required**:
1. `balances[msg.sender] -= amount` (line 31) was already modified, and that modification is visible **5 lines above** within the same function
2. Writing "must be unchanged" below it presupposes the ordering knowledge that "this modification should come after checkpoint"
3. While reading the code, a developer cannot naturally write "this balance was just changed, so I'll add an unchanged annotation here" -- it is contradictory to write "unchanged" on a variable that has just changed
4. Writing the annotation requires already knowing the correct ordering (checkpoint -> balance update); had the developer known this, they would have fixed the code order directly

**Original report wording**: "In every actionable function except `transfer()`, a call to `userCheckpoint()` is correctly made BEFORE the action effects." -- the auditor also discovered the bug by comparing consistency with other functions. That very comparison is bug awareness.

### Dependencies
**Interfaces** (6):
- IStakerVault, IController, IAddressProvider, IERC20, ILiquidityPool, ILpGauge

**Libraries** (3):
- AddressProviderHelpers, SafeERC20, ScaledMath

**Contracts** (4):
- Authorization, Pausable, Initializable, Preparable

**Other**:
- Error (library/contract for require messages)
- Transfer event (presumed defined in IStakerVault)

### Intent Annotations (standalone)
| Type | Line (contraction, after annotation insertion) | Expression | Expected | Comment |
|------|-----------------------------------------------|------------|----------|---------|
| During | 36 (standalone, target: line 37) | Unchanged(balances[msg.sender]) | violated | At checkpoint time, balances[msg.sender] is already modified (line 31) -> Entry != Current -> violated |
| During | 38 (standalone, target: line 39) | Unchanged(balances[account]) | violated | At checkpoint time, balances[account] is already modified (line 32) -> Entry != Current -> violated |

### Debug Annotations
**LocalVar:**
| # | Variable | Value (interval) | Comment |
|---|----------|-------------------|---------|
| 1 | account | symbolicAddress 1 | recipient |
| 2 | amount | [100, 100] | transfer amount |

**StateVar:**
| # | Variable | Value (interval) | Comment |
|---|----------|-------------------|---------|
| 1 | balances[101] | [200, 200] | balances[msg.sender], to satisfy require |
| 2 | balances[1] | [0, 0] | balances[account] |
| 3 | currentAddresses[_LP_GAUGE] | symbolicAddress 2 | for entering the if branch (!= address(0)); inherited state variable (Preparable) |

**Input conditions:**
- balances[101] >= amount (passes require)
- currentAddresses[_LP_GAUGE] != address(0) (enters if branch)

**Post-execution verification:**
- balances[101] = 200 - 100 = 100 != Entry(200) -> Unchanged **violated** ok
- balances[1] = 0 + 100 = 100 != Entry(0) -> Unchanged **violated** ok

### Notes
- `@During Unchanged(var)` = "at this program point, the Current value of var must equal the Entry value"
- Buggy code: balance modified -> checkpoint -> Unchanged violated -> detected
- Correct code: checkpoint -> balance modified -> Unchanged satisfied at checkpoint time
- Required Implementation: `@During Unchanged` (code_modification_issues.md Issue 2)
- Required Implementation: standalone annotation support (code_modification_issues.md Issue 1)
- `userCheckpoint()` is an ILpGauge interface call -> external contract effect, but the annotation target is the `balances` state variable inside StakerVault
- `currentAddresses` is a state variable inherited from Preparable -> need to verify whether debug annotations on inherited state variables are supported

### Bug Code (contraction, after annotation insertion)
```solidity
function transfer(address account, uint256 amount) external override notPaused returns (bool) {
    require(msg.sender != account, Error.SELF_TRANSFER_NOT_ALLOWED);
    require(balances[msg.sender] >= amount, Error.INSUFFICIENT_BALANCE);

    ILiquidityPool pool = controller.addressProvider().getPoolForToken(token);
    pool.handleLpTokenTransfer(msg.sender, account, amount);

    balances[msg.sender] -= amount;       // line 31: balance modified first
    balances[account] += amount;           // line 32: balance modified first

    address lpGauge = currentAddresses[_LP_GAUGE];
    if (lpGauge != address(0)) {
        // @During Unchanged(balances[msg.sender])          // line 36: standalone annotation
        ILpGauge(lpGauge).userCheckpoint(msg.sender);       // line 37: checkpoint comes later -> BUG
        // @During Unchanged(balances[account])              // line 38: standalone annotation
        ILpGauge(lpGauge).userCheckpoint(account);          // line 39: checkpoint comes later -> BUG
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
- The bug is that if `supplyTokenTo()` is called between a call to `setYieldSource()` and the subsequent call to `transferFunds()`, the exchange rate is distorted
- yieldSource has been changed but funds have not yet been transferred, so `balanceOfToken()` returns a value close to 0 -> abnormally many shares are issued
- This is a state inconsistency between two independent transactions (multi-transaction), outside the scope of single-transaction analysis -> excluded

---

## web3bugs_39_H_02

- **Contract**: Swivel
- **Function**: exitVaultFillingVaultInitiate
- **Bug lines (original)**: 280
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L4a: inexpressible-expected-value)

### Bug Description
In `exitVaultFillingVaultInitiate`, the fee is charged twice to the taker (msg.sender):
1. Line 280: `transferFrom(o.maker, msg.sender, premiumFilled - fee)` -- fee deducted from the amount received
2. Line 283: `transferFrom(msg.sender, address(this), fee)` -- fee paid separately again

As a result, the sender's net gain is `premiumFilled - 2*fee`, while the intended value is `premiumFilled - fee`.

### Reason Not Detectable
- The argument values to each `transferFrom` call are individually correct (`premiumFilled - fee` and `fee` are each correct computational results)
- The bug arises from the **combination** of two external calls: the party bearing the fee is set incorrectly, causing the sender to be double-charged
- To express the sender's net token flow, balance changes of an external ERC20 contract must be tracked, but these are not state variables of the contract under analysis
- At a single program point, no variable or arithmetic combination can express the fact that "the sender is paying the fee twice" -> inexpressible-expected-value

---

## web3bugs_52_H_09

- **Contract**: VaderReserve
- **Function**: reimburseImpermanentLoss
- **Bug lines (original)**: 85
- **Pattern**: erroneous_accounting
- **Status**: excluded (bug-not-in-target-contract)

### Notes
- The bug title is "VaderPoolV2 incorrectly calculates the amount of IL protection to send to LPs"
- The actual IL protection amount calculation is performed in the caller VaderPoolV2; VaderReserve's `reimburseImpermanentLoss` is simple logic that compares the received amount with the reserve balance and transfers
- Recommended fix: handle the VADER/USDV conversion rate via an oracle (TwapOracle) -> requires design changes on the VaderPoolV2 side
- Since the target contract (VaderReserve) has no calculation error, excluded

---

## web3bugs_52_H_23

- **Contract**: VaderPoolV2
- **Function**: mintSynth
- **Bug lines (original)**: 161
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L5a: missing-code)

### Bug Description
In `mintSynth`, after issuing synth, the call to `_update` does not subtract `reserveForeign`, causing over-issuance of synth:
- Buggy (line 158-164): `_update(foreignAsset, reserveNative + nativeDeposit, reserveForeign, ...)`
- Correct: `_update(foreignAsset, reserveNative + nativeDeposit, reserveForeign - amountSynth, ...)`

### Dependency Status
All dependencies including BasePoolV2.sol and VaderMath.sol are secured (copied from the Web3Bugs original). VaderMath.calculateSwap is a pure function with no inline assembly -> analyzable.

### Reason Not Detectable (L5a: missing-code)
The code that subtracts `amountSynth` from `reserveForeign` in the `_update` call is **missing**. While `@Intent` could express "after synth issuance, foreign reserve must decrease", writing this intent requires already being aware of the missing `- amountSynth` -> bug awareness is a prerequisite.

Unlike the annotated cases (5_H_07: comments serve as spec; 5_H_12: intent naturally derived from variable semantics), this case requires both domain knowledge of the accounting rules for synth issuance and bug awareness to write the intent.

---

## web3bugs_5_H_07

- **Contract**: Utils
- **Function**: calcAsymmetricShare
- **Bug line (original)**: 273
- **Bug line (contraction)**: 22
- **Pattern**: erroneous_accounting
- **Status**: annotated

### Bug Description
A missing-parentheses bug in the formula implementation of the `calcAsymmetricShare` function. The intended formula in the comment is `(part1 * (part2 - part3 + part4)) / part5` = `u*A*(2*U*U - 2*U*u + u*u) / (U*U*U)`, but the actual code (line 22) is implemented as `((part1 * part2) - part3) + part4`, so part3 and part4 are not multiplied by part1.

### Dependencies
None

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| LocalVar | u | [100, 100] | 18 | Function parameter; satisfies u < U |
| LocalVar | U | [1000, 1000] | 19 | Function parameter; total units |
| LocalVar | A | [5000, 5000] | 20 | Function parameter; total amount |

- Overflow/underflow check: part1*part2 = 100*5000*2*10^6 = 10^12 (safe in uint256), part2-part3 = 2*10^6 - 2*10^5 = 1.8*10^6 > 0 (no underflow)

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| During | 24 | returnExpression == u*A*(2*U*U - 2*U*u + u*u) / (U*U*U) | violated | 5.md H-07: the intended formula in the comment differs from the actual implementation. Correct result 905 vs buggy result ~999 |

---

## web3bugs_5_H_08

- **Contract**: Utils
- **Function**: calcLiquidityUnits
- **Bug line (original)**: 239
- **Bug line (contraction)**: 40
- **Pattern**: erroneous_accounting
- **Status**: annotated

### Bug Description
A missing-parentheses bug in the formula implementation of the `calcLiquidityUnits` function. The intended formula in the comment is `P * (t*B + T*b) / (2*T*B) * slipAdjustment`, but the actual code (line 40) is implemented as `(P * part1 + part2) / part3`, so `P` is multiplied only by `part1` (`t*B`) and not by `part2` (`T*b`). Same missing-parentheses pattern as 5_H_07.

### Dependencies
None (getSlipAdustment is a function within the same contract)

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| LocalVar | b | [100, 100] | 33 | Function parameter; base deposited |
| LocalVar | B | [1000, 1000] | 34 | Function parameter; base balance |
| LocalVar | t | [100, 100] | 35 | Function parameter; token deposited |
| LocalVar | T | [1000, 1000] | 36 | Function parameter; token balance |
| LocalVar | P | [500, 500] | 37 | Function parameter; total pool units; P > 0 enters else branch |

- The state variable `one = 10**18` is already initialized in the contract
- Overflow/underflow check: with symmetric deposit (b/B == t/T), slipAdjustment = one. Correct _units = 50, buggy _units = 25

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| During | 40 | _units == P * (t * B + T * b) / ((T * B) * 2) | violated | 5.md H-08: the intended formula `P*(tB+Tb)/(2TB)` in the comment differs from the actual implementation. Correct result 50 vs buggy result 25 |

---

## web3bugs_29_H_05

- **Contract**: HybridPool
- **Function**: _nonOptimalMintFee
- **Bug line (original)**: 433
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L4a: inexpressible-expected-value)

### Bug Description
In `_nonOptimalMintFee`, the optimal deposit ratio is computed as `(_amount0 * _reserve1) / _reserve0`, which is the constant-product AMM formula. HybridPool uses a stableswap scheme, so the optimal ratio differs from the reserve ratio (the curve is flattened by the amplification parameter A). As a result the fee is over-/under-computed.

### Reason Not Detectable (L4a)
- The correct optimal ratio depends on the stableswap invariant D, and D is computed via Newton's method iteration (a loop)
- The correct fee value cannot be expressed as an arithmetic combination of existing variables in the program
- The magnitude of the fee itself stays within the normal range (0 ~ swapFee), so a simple bound annotation cannot distinguish it

---

## web3bugs_52_H_25

- **Contract**: VaderMath (library)
- **Function**: calculateSwap
- **Bug line (original)**: 105
- **Pattern**: erroneous_accounting
- **Status**: excluded (not-a-bug)

### Notes
- The formula `x * X * Y / (x + X)^2` is the intended design of the Thorchain CLP model
- The sponsor explicitly disputed: "This is the intended design of the Thorchain CLP model"
- The judge effectively accepted the sponsor's position
- The code implementation matches the comment, and there is no computation error in the formula itself
- The phenomenon where output decreases when `amountIn > reserveIn` is an inherent property of the CLP model

---

## web3bugs_56_H_02

- **Contract**: CDP (library)
- **Function**: update
- **Bug line (original)**: 39
- **Bug line (contraction)**: 41
- **Pattern**: erroneous_accounting
- **Status**: annotated

### Bug Description
In the `update()` function, when `_earnedYield > totalDebt`, `totalCredit` is overwritten (=) instead of accumulated (+=). The existing credit is lost.
- Buggy (line 41): `_self.totalCredit = _earnedYield.sub(_currentTotalDebt);`
- Correct: `_self.totalCredit = _self.totalCredit.add(_earnedYield.sub(_currentTotalDebt));`
- `getUpdatedTotalCredit` (view function) correctly accumulates as `_self.totalCredit + (yield - debt)` -- the intent can be confirmed
- Report: sponsor finally confirmed

### Dependencies
- FixedPointMath library (FixedDecimal struct, sub/mul/cmp/decode, etc.)
- SafeMath library (using SafeMath for uint256)
- Issue 4 (code_modification_issues.md): support for the `using` keyword with custom libraries required

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| StateVar | _self.totalCredit | [1000, 1000] | 37 | Existing credit positive -- demonstrates overwrite bug |
| StateVar | _self.totalDebt | [0, 0] | 37 | Debt fully repaid; if earnedYield > 0 the if branch is taken |
| StateVar | _self.totalDeposited | [1000, 1000] | 37 | Required for getEarnedYield computation |
| StateVar | _self.lastAccumulatedYieldWeight.x | [1000000000000000000, 1000000000000000000] | 37 | 1e18 (fixed-point 1.0) |
| StateVar | _ctx.accumulatedYieldWeight.x | [1200000000000000000, 1200000000000000000] | 37 | 1.2e18 (fixed-point 1.2) |

- earnedYield = (1.2e18 - 1e18) * 1000 / 1e18 = 200
- totalDebt = 0, so earnedYield(200) > totalDebt(0) -> if branch taken
- Buggy: totalCredit = 200 - 0 = 200 (overwritten from 1000 to 200)
- Correct: totalCredit = 1000 + (200 - 0) = 1200

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| Post | 46 | totalCredit(entry <= exit) | violated | 56.md H-02: on calling update, credit must not decrease. In buggy code entry(1000) > exit(200) -> violated |

---

## web3bugs_60_H_01

- **Contract**: OptimisticLedgerLib
- **Function**: settleAccount
- **Bug lines (original)**: 68; 73
- **Pattern**: erroneous_accounting
- **Status**: annotated

### Bug Description
In `settleAccount()`, shortfall is double-counted. The local `shortfall` is set to `self.shortfall + |newBalance|`, including the existing shortfall, and then `self.shortfall = self.shortfall + shortfall` adds the existing shortfall again.
- Buggy: `self.shortfall = 2 * old_shortfall + |newBalance|`
- Correct: `self.shortfall = old_shortfall + |newBalance|`
- Report: sponsor (kbrizzle) confirmed; judge agreed

### Dependencies
- Fixed18.sol (Fixed18Lib, `type Fixed18 is int256;`)
- UFixed18.sol (UFixed18Lib, `type UFixed18 is uint256;`)
- Issue 4 (code_modification_issues.md): support for the `using` keyword with custom libraries required
- Issue 5 (code_modification_issues.md): support for user-defined value types required

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| StateVar | self.shortfall | [100, 100] | 15 | Must be non-zero -- demonstrates the double-count bug |
| StateVar | self.balances[account] | [50, 50] | 15 | Account balance |
| LocalVar | amount | [-100, -100] | 15 | Negative Fixed18 value -- forces newBalance negative |

- newBalance = 50 + (-100) = -50 -> negative; if branch taken
- |newBalance| = 50
- Buggy: shortfall(local) = 100 + 50 = 150, self.shortfall = 100 + 150 = 250
- Correct: self.shortfall = 100 + 50 = 150

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| During | 23 | self.shortfall == 150 | violated | 60.md H-01: shortfall double-counted. Should be 150 in the correct case but 250 in buggy code -> violated |

---

## web3bugs_77_H_01

- **Contract**: MathLib
- **Function**: calculateLiquidityTokenQtyForSingleAssetEntry
- **Bug lines (original)**: 174-185
- **Pattern**: erroneous_accounting
- **Status**: annotated

### Bug Description
In a single asset entry, the gamma (γ) formula used to compute the LP token quantity (ΔRo) is wrong. The under-computation causes new LPs to receive shares smaller than their contribution, resulting in fund loss.
- Buggy gamma: `γ = ΔY / Y' / 2 * (ΔX / α^)` -- under-computed
- Report example: an LP contributes 4 quoteToken -> receives only 2.67 quoteToken worth (1.33 loss)
- The exact correct formula is presented incompletely in the report body (see issue page); the sponsor also notes the proposed fix is "partially correct"
- **Detection strategy**: instead of the exact formula, use a proportional fairness lower bound on the economically fair share
- Report: sponsor (0xean) confirmed & resolved; judge agreed High severity

### Dependencies
- None (wDiv, wMul are defined in the same library; pure functions)

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| LocalVar | _totalSupplyOfLiquidityTokens | [1000, 1000] | 35 | Ro = sqrt(X*Y), X=1000, Y=1000 |
| LocalVar | _tokenQtyAToAdd | [4000, 4000] | 36 | ΔY (quoteToken added by LP) |
| LocalVar | _internalTokenAReserveQty | [5000, 5000] | 37 | Y' = Y + ΔY = 1000 + 4000 |
| LocalVar | _tokenBDecayChange | [4000, 4000] | 38 | ΔX = ΔY * Omega (Omega=1) |
| LocalVar | _tokenBDecay | [9000, 9000] | 39 | Alpha - X = 10000 - 1000 |

- Based on the report rebase-up example: Alpha=10000, X=1000, Y=1000, Omega=1, LP adds 4000 quoteToken
- wGamma = 16/90 * WAD ≈ 1.777e17
- Buggy ΔRo ≈ 216
- Fair ΔRo = Ro * 4/11 ≈ 363 (LP contribution 4000 / pool total 15000 = 4/15 share)

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| Post | 38 | returnExpression >= 363 | violated | 77.md H-01: gamma under-computed. Fair ΔRo should be ≥ 363 but in buggy code ≈ 216 -> violated |

---

## web3bugs_31_H_01

- **Contract**: MyStrategy
- **Function**: manualRebalance
- **Bug lines (original)**: 469; 471; 477
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L5b: wrong-code)`

### Bug Description
In `manualRebalance()`, two variables with different units are compared:
- Line 469: `currentLockRatio = balanceInLock * 1e18 / totalCVXBalance` -> a **ratio** (percentage, max 1e18)
- Line 471: `newLockRatio = totalCVXBalance * toLock / MAX_BPS` -> an **absolute CVX amount** (token amount)
- Line 477: `if (newLockRatio <= currentLockRatio)` -> compares ratio against amount -> wrong branch
- Recommended fix in the report: change `currentLockRatio` to `balanceInLock` (amount). Reverse-inferred from the use site of `cvxToLock = newLockRatio.sub(currentLockRatio)`.
- Report: sponsor (GalloDaSballo) confirmed; mitigated by rewriting

### Reason Not Detectable (L5b: wrong-code)
- Interface calls are now supported, so return values such as `balanceOf()` and `getPricePerFullShare()` are not TOP
- However, the bug is a dimensional mismatch in the `currentLockRatio` formula: computed as a percentage (1e18 precision) when it should be an amount
- To know the correct expression (`currentLockRatio = balanceInLock`) requires a dimensional analysis of the downstream code (line 488: `cvxToLock = newLockRatio.sub(currentLockRatio)` -> used as a CVX amount)
- The auditor (cmichel) likewise reverse-infers the correct meaning from the downstream use site, "Judging from the `cvxToLock = ...`"
- Any annotation requires the assumption that the two variables share the same unit -> awareness of the dimensional mismatch = bug awareness

---

## web3bugs_16_H_04

- **Contract**: Balances
- **Function**: applyTrade
- **Bug lines (original)**: 187
- **Pattern**: erroneous_accounting
- **Status**: not_detectable (L3: unsupported-construct-top)

### Bug Description
In `applyTrade()`, the fee sign for a Long position is reversed:
- Line 187: `newQuote = position.quote - quoteChange + fee` (buggy: adds fee)
- Correct: `newQuote = position.quote - quoteChange - fee` (fee should be subtracted)
- Short positions (line 190) correctly use `- fee`
- Report: sponsor (raymogg) confirmed

### Reason Not Detectable
PRBMath dependency is secured (installed via npm, then copied). However, core internal functions of the PRBMath library (`mulDivFixedPoint`, `mulDiv`) use inline assembly and cannot be analyzed:
- `quoteChange = PRBMathSD59x18.mul(signedAmount, signedPrice)` -> inside assembly -> TOP
- `fee = getFee(...)` -> `PRBMathUD60x18.mul` -> inside assembly -> TOP
- `newQuote = position.quote - TOP + TOP` -> TOP -> cannot distinguish buggy from correct

---

## web3bugs_62_H_01

- **Contract**: Stream
- **Function**: recoverTokens
- **Bug lines (original)**: 654
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L4b: wrong-code -- wrapper no state, balanceOf inline chain)`

### Bug Description
In `recoverTokens()`, `depositTokenFlashloanFeeAmount` is not subtracted when computing excess depositToken. The stream creator can claw back the flashloan fee, causing governance fee claims or user withdrawals to fail.
- Buggy (line 654): `excess = balanceOf(this) - (depositTokenAmount - redeemedDepositTokens)`
- Correct: `excess = balanceOf(this) - (depositTokenAmount - redeemedDepositTokens) - depositTokenFlashloanFeeAmount`
- Report: sponsor (brockelmore) confirmed

### Reason Not Detectable (L4b: wrong-code)
- **L4b reclassification rationale** (l4_l5_classification.csv reclass_reason: `annotation_plans_L5a_but_wrapper_no_state_balanceOf_inline_chain_I9_principle`)
- Previous L2a (interface-call-return-top) classification was incorrect -- interfaces are now supported, so not L2a
- `recoverTokens()` is a wrapper function with no state changes (only safeTransfer). The `balanceOf()` result is not stored in a named variable but used only in an inline chain -> no state/local var available as a target for Post/During in the annotation grammar
- By the I9 principle (grammar expressibility takes priority), the structural limitation "wrapper no state + balanceOf inline" supersedes "missing term (failure to subtract depositTokenFlashloanFeeAmount) bug awareness" -> L4b
- Case9 wrapper family archetype

---

## web3bugs_44_H_02
- **Status**: `not_detectable (L3: unsupported-construct-top)`
- **Contract**: Swap
- **Function**: fillZrxQuote()
- **Bug lines**: 210 (originalETHBalance), 215 (ethDelta)

### Bug Description
In `fillZrxQuote()`, balance snapshots are captured at the wrong moment:
1. ETH: `originalETHBalance = address(this).balance` -- already includes `msg.value`. Even if there is an ETH refund, `subOrZero(newBalance, originalETHBalance)` = 0
2. ERC20: in same-token arb, `originalERC20Balance = balanceOf(this)` -- already includes the input amount. The delta is under-computed relative to the true value
- Buggy: `ethDelta = address(this).balance.subOrZero(originalETHBalance)` (originalETHBalance includes msg.value)
- Correct: must adjust as `originalETHBalance = address(this).balance - msg.value`
- Report: sponsor (Shadowfiend) confirmed

### Reason Not Detectable (L3: unsupported-construct-top)
- ~~`address(this).balance` -> TOP~~ -> can be provided as GlobalVar via the Issue 7 implementation ✅
- **`zrxTo.call{value: ethAmount}(zrxData)`** -> low-level `.call()`, no implementation code -> side effect unknown (primary blocker)
- Re-reading `address(this).balance` after `.call()` -> balance may have changed due to `.call()` but cannot be tracked
- `zrxBuyTokenAddress.balanceOf()` -> interface call, but state changes after a low-level call cannot be tracked
- The side effect of low-level `.call()` is an unsupported construct -> L3 retained

---

## web3bugs_66_H_02
- **Status**: excluded_fixed_code
- **Contract**: sYETIToken
- **Function**: rebase()
- **Bug line**: 297

### Reason
The code in the Web3Bugs repo is already a fixed version. The buggy code compared against `yetiTokenBalance` (whole balance), but the current code compares against `adjustedYetiTokenBalance = yetiTokenBalance.sub(effectiveYetiTokenBalance)` (extra balance). The `_getValueOfContract` formula has also been changed.

---

## web3bugs_70_H_08
- **Status**: `not_detectable (L4b: wrong-code -- wrapper no state, parameter overwrite)`
- **Contract**: VaderReserve
- **Function**: reimburseImpermanentLoss()
- **Bug lines**: 98, 102

### Bug Description
Fixed-point scaling is missing in the IL (Impermanent Loss) reimbursement calculation:
- Buggy (line 98): `amount = amount / usdvPrice` -- usdvPrice is at 1e18 scale -> result under by 1e18x
- Buggy (line 102): `amount = amount * vaderPrice` -- vaderPrice is at 1e18 scale -> result over by 1e18x
- Correct: `amount * 1e18 / usdvPrice`, `amount * vaderPrice / 1e18`
- Report: sponsor not confirmed (judge resolved)

### Reason Not Detectable (L4b: wrong-code)
- **L4b reclassification rationale** (l4_l5_classification.csv reclass_reason: `annotation_plans_L5a_but_wrapper_no_state_parameter_overwrite_original_lost`)
- Wrapper function with no self-state -- no @Post state invariant has any target
- The `amount` parameter is overwritten at lines 98/102, so the original value is not preserved as a named var in the program -> the correct scaling (`amount * 1e18 / usdvPrice`) cannot be expressed in the annotation grammar (the original amount disappears from scope)
- By the I9 principle, structural expressibility (wrapper + parameter overwrite) precedes "lack of awareness of the scaling factor (L5a candidate)" -> L4b
- Case1/Case10 wrapper version archetype (scaling factor missing 1e18)

---

## web3bugs_42_H_01
- **Contract**: MochiVault
- **Function**: borrow()
- **Bug line (original)**: 248
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L2a: interface-call-return-top)`

> Note: previously an attempt was made to promote this to "annotated (was: not_detectable, interface-call-return-top)", but the ground truth based on paper Table 6 (20 mitigated cases) and dataset.csv keeps it as `not_detectable`. The Intent Annotations section below is preserved as a record of the attempted annotation.

### Bug Description
In `borrow()`, the individual debt (`details[_id].debt`) is increased by `increasingDebt = (_amount * 1005) / 1000` including a 0.5% fee, but the global `debts` is increased only by `_amount` without the fee -> the sum of individual debts and global debts mismatch. In `repay()`/`liquidate()`, debts are decremented using fee-included values, so eventually `debts` underflows.
- Buggy (line 248): `debts += _amount`
- Correct: `debts += increasingDebt`
- Report: sponsor (jonah1005) confirmed

### Dependencies
**Libraries (require prior analysis):**
- `Float.sol` (`42_Float.sol`): `using Float for uint256`, `float` struct, `.multiply()`, `.divide()` -- pure, no assembly -> analyzable
- `CheapERC20.sol` (`42_CheapERC20.sol`): `using CheapERC20 for IERC20` -- not used on the direct path of borrow(); unnecessary if removed in contraction

**Interfaces:**
- `IMochiVault.sol`: `Detail` struct, `Status` enum (file-level definitions)
- `IMochiEngine.sol`: `engine.cssr()`, `engine.mochiProfile()`, `engine.nft()`, `engine.minter()`, `engine.discountProfile()`
- `IMochiProfile.sol`: `calculateFeeIndex()`, `maxCollateralFactor()`, `creditCap()`, `minimumDebt()`, `liquidationFactor()`
- `IDiscountProfile.sol`: `discount()`
- `IMochiNFT.sol`: `ownerOf()`, `asset()`
- `IMinter.sol`: `mint()`
- `ICSSRRouter.sol` (`42_ICSSRRouter.sol`): `update()`, `getPrice()`
- `IReferralFeePool.sol`: `addReward()`
- `IERC3156FlashLender.sol`, `IERC3156FlashBorrower.sol`: inheritance

### Required Implementation
- Issue 3: file-level struct support (`struct Detail`, `enum Status` -- defined in interface files outside the contract)
- Issue 4: support for `using Float for uint256` custom library

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| StateVar | debts | [800, 800] | 29 | Initial global debt = 500+300+0; invariant holds |
| StateVar | debtIndex | [1000000000000000000, 1000000000000000000] | 29 | 1e18; initial state with no interest |
| StateVar | lastAccrued | [current timestamp, current timestamp] | 29 | Interest is 0 in accrueDebt |
| StateVar | details[0].debt | [500, 500] | 29 | Existing position 0 |
| StateVar | details[0].debtIndex | [1000000000000000000, 1000000000000000000] | 29 | 1e18 |
| StateVar | details[0].status | Status.Active | 29 | active |
| StateVar | details[1].debt | [300, 300] | 29 | Existing position 1 |
| StateVar | details[1].debtIndex | [1000000000000000000, 1000000000000000000] | 29 | 1e18 |
| StateVar | details[1].status | Status.Active | 29 | active |
| StateVar | details[2].debt | [0, 0] | 29 | Borrow target; initial debt 0 |
| StateVar | details[2].debtIndex | [1000000000000000000, 1000000000000000000] | 29 | 1e18 |
| StateVar | details[2].collateral | [10000000, 10000000] | 29 | Sufficient collateral |
| StateVar | details[2].status | Status.Collaterized | 29 | Collateral-only state |
| IReturn | engine.mochiProfile().calculateFeeIndex() | [1000000000000000000, 1000000000000000000] | 29 | Returns debtIndex unchanged (interest 0) |
| IReturn | engine.cssr().update() | float{1e18, 1e18} | 29 | price = 1.0 |
| IReturn | engine.mochiProfile().maxCollateralFactor() | float{8e17, 1e18} | 29 | cf = 0.8 |
| IReturn | engine.mochiProfile().creditCap() | [100000000, 100000000] | 29 | Sufficiently large cap |
| IReturn | engine.mochiProfile().minimumDebt() | [0, 0] | 29 | No minimum debt |
| LocalVar | _amount | [1000, 1000] | 29 | Borrow amount |

- Initial invariant: debts(800) == details[0].debt(500) + details[1].debt(300) + details[2].debt(0) ✓
- accrueDebt: currentIndex == debtIndex -> increased = 0; no change
- increasingDebt = 1000 * 1005 / 1000 = 1005
- details[2].debt = 0 + 1005 = 1005
- Buggy: debts = 800 + 1000 = 1800
- Correct: debts = 800 + 1005 = 1805

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| Post | 52 | debts == details[0].debt + details[1].debt + details[2].debt | violated | Accounting invariant: global debts = Σ individual debts. debts=800+1000=1800 ≠ 500+300+1005=1805 -> violated |

---

## web3bugs_42_H_05
- **Status**: excluded (duplicate_of_42_H_01)
- **Contract**: MochiVault
- **Function**: borrow()
- Same bug as 42_H_01 (incorrect debts calculation)

---

## web3bugs_52_H_16
- **Status**: `not_detectable (L4b: wrong-code -- view function no state)`
- **Contract**: VaderRouter
- **Function**: calculateOutGivenIn()
- **Bug lines**: 488-491

### Bug Description
In a 3-path swap, the order of the reserve parameters for pool0 and pool1 is swapped. The inner calculateSwap uses the pool1 reserves and the outer uses the pool0 reserves, but the correct order is inner=pool0 (foreign->native), outer=pool1 (native->foreign).
- Buggy: `calculateSwap(calculateSwap(amountIn, nativeReserve1, foreignReserve1), foreignReserve0, nativeReserve0)`
- Correct: `calculateSwap(calculateSwap(amountIn, foreignReserve0, nativeReserve0), nativeReserve1, foreignReserve1)`
- Report: sponsor (SamSteinGG) confirmed. Same wrong-arg-order pattern as 52_H_15.

### Reason Not Detectable (L4b: wrong-code)
- **L4b reclassification rationale** (l4_l5_classification.csv reclass_reason: `annotation_plans_L5b_but_view_function_no_state_I9_principle_L4b`) -- since the view function does not write state, the I9 principle (grammar expressibility) applies instead of the L5b "bug awareness" condition; L4b
- Interface calls are supported, but the `VaderMath.calculateSwap()` library pure function cannot be invoked directly from the annotation grammar
- Being a view function, there are no state variables targetable by @Post changed/Entry/Exit -> no invariant expressible in the grammar in principle -> L4b (grammar expressibility)
- Same router wrapper L4b archetype as the 52_H_15 twin case

---

## web3bugs_5_H_15

- **Contract**: Router
- **Function**: swapWithSynthsWithLimit
- **Bug line**: 170 (original basis)
- **Status**: `not_detectable (L2a: interface-call-return-top)`
- **Bug**: in a Token->Token swap, the second slippage check uses the original `inputAmount` instead of the base output of the first swap
- Buggy (line 170): `iUTILS(UTILS()).calcSwapSlip(inputAmount, iPOOLS(POOLS).getBaseAmount(outputToken))`
- Correct: `iUTILS(UTILS()).calcSwapSlip(firstSwapOutput, iPOOLS(POOLS).getBaseAmount(outputToken))`
- The return value of the first swap (line 166) is unused
- Report: sponsor (strictly-scarce) confirmed

### @IReturn Reassessment
- `iUTILS.calcSwapSlip()` -> **pure** -> @IReturn possible
- `iPOOLS.getBaseAmount()` -> **view** -> @IReturn possible
- `iPOOLS.getTokenAmount()` -> **view** -> @IReturn possible
- `iPOOLS.isAnchor()` -> **view** -> @IReturn possible
- `iPOOLS.swap()` -> **state-modifying (no mutability)** -> @IReturn **not possible**

### Reason Not Detectable
- The key value needed for bug detection: the first swap's output (return value of `iPOOLS(POOLS).swap()`)
- `swap()` is a state-modifying function, so @IReturn cannot be applied
- The first swap output cannot be made concrete, so there is no way to verify the discrepancy between `inputAmount` and `firstSwapOutput`
- view/pure functions alone (where @IReturn is possible) cannot detect the core issue of "wrong variable usage"

---

## web3bugs_61_H_01

- **Contract**: CreditLine
- **Function**: _borrowTokensToLiquidate
- **Bug line**: 1050 (original basis)
- **Status**: `not_detectable (L4a: inexpressible-expected-value)`
- **Bug**: `IPriceOracle(priceOracle).getLatestPrice(_borrowAsset, _collateralAsset)` -- argument order reversed
- Buggy: `getLatestPrice(_borrowAsset, _collateralAsset)` -> borrow/collateral ratio
- Correct: `getLatestPrice(_collateralAsset, _borrowAsset)` -> collateral/borrow ratio
- To convert collateral to borrow token, the collateral/borrow ratio is needed
- Report: sponsor (ritik99) confirmed

### Reason Not Detectable (L4a: inexpressible-expected-value)
- Interface calls are now supported, so the return value of `getLatestPrice()` is not TOP
- However, structurally the correct expected value cannot be expressed:
  1. @IReturn does not distinguish arguments: both `getLatestPrice(A, B)` and `getLatestPrice(B, A)` yield the same concrete return -> buggy and correct produce the same result
  2. Function calls are not allowed in the annotation grammar -> `_ratioOfPrices == getLatestPrice(_collateralAsset, _borrowAsset)` cannot be expressed
  3. The correct `_ratioOfPrices` is an oracle return value, so it cannot be expressed as an arithmetic combination of existing program variables either
- Even with bug awareness, the correct value cannot be distinguished by an annotation -> L4a

---

## web3bugs_14_H_01

- **Contract**: IdleYieldSource
- **Function**: redeemToken
- **Bug line**: 131 (original basis)
- **Status**: `excluded, missing-dependency`
- **Bug**: `redeemIdleToken(redeemedShare)` -- should pass `redeemAmount` instead of `redeemedShare`

### Reason Excluded
- The `IIdleToken` interface definition file does not exist in the repository
- Without the dependency, IntentChecker cannot recognize the interface, so analysis itself is impossible

---

## web3bugs_29_H_11

- **Contract**: ConstantProductPool
- **Function**: burnSingle
- **Bug line**: 175; 183 (original basis)
- **Status**: `not_detectable (L3: unsupported-construct-top)`
- **Bug**: the swap calculation uses `_reserve` but should use `balance`
- Buggy (175): `_getAmountOut(amount0, _reserve0 - amount0, _reserve1 - amount1)`
- Correct: `_getAmountOut(amount0, balance0 - amount0, balance1 - amount1)`
- After `burn`, reserves are updated to balances, so balance-based is the right choice
- Report: sponsor (maxsam4) confirmed; severity bumped to High

### Reason Not Detectable (L3: unsupported-construct-top)
- Not an interface call but a low-level `staticcall` + `abi.decode` pattern (same as 29_H_08):
  - `_balance()`: `bento.staticcall(abi.encodeWithSelector(0xf7888aec, ...))` -> `abi.decode`
- `staticcall` is a low-level external call that cannot be tracked, and `abi.decode` is an L3 unsupported construct -> return value TOP
- `balance0`, `balance1` -> TOP -> `amount0 = (liquidity * TOP) / _totalSupply` -> TOP
- `_getAmountOut(TOP, _reserve0 - TOP, _reserve1 - TOP)` -> TOP
- Independent of interface support, `staticcall` + `abi.decode` is the blocker (L3)

---

## web3bugs_16_H_02

- **Contract**: Pricing
- **Function**: updateFundingRate (internal, called from recordTrade)
- **Bug Lines**: 155, 159
- **Status**: `excluded, multi-transaction`

### Bug Description
In `updateFundingRate()`, when computing the cumulative funding rate, `fundingRates[currentFundingIndex]` is read to fetch the previous cumulative value. However, in the previous call `setFundingRate` wrote to the same index and then incremented `currentFundingIndex += 1`, so the current call reads a new (uninitialized) index slot -> the cumulative value is always 0 + new rate = only the new rate remains.

```solidity
// line 155: fundingRates[currentFundingIndex] -> reads uninitialized slot (0)
int256 currentFundingRateValue = fundingRates[currentFundingIndex].cumulativeFundingRate;
int256 cumulativeFundingRate = currentFundingRateValue + newFundingRate; // 0 + new = new (previous cumulative lost)

// line 159: same issue
int256 currentInsuranceFundingRateValue = insuranceFundingRates[currentFundingIndex].cumulativeFundingRate;

// line 163-165: writes to the same index
setFundingRate(newFundingRate, cumulativeFundingRate);
setInsuranceFundingRate(iPoolFundingRate, iPoolFundingRateValue);

// line 168: increments the index -> next call again reads the uninitialized slot
currentFundingIndex = currentFundingIndex + 1;
```

### Excluded Reason: multi-transaction
- `updateFundingRate` is `internal` and is only called from `recordTrade` (external)
- Each `recordTrade` call is a separate transaction
- Bug manifestation condition: in the current transaction, an uninitialized slot is read while `currentFundingIndex` was incremented in a previous transaction
- The first call (index=0) is normal (initial value 0 is correct); cumulative loss occurs from the second call onward
- IntentChecker performs single-transaction analysis, so it cannot track state changes across transactions

---

## web3bugs_51_H_03

- **Contract**: SwapUtils (library)
- **Function**: _xp (two overloads)
- **Bug Lines**: 666, 676
- **Status**: `excluded,multi-transaction`

### Bug Description
The `_xp()` functions directly use `self.tokenPrecisionMultipliers` (the stored value), but the correct behavior is to compute the multiplier in real time from the interpolated target price based on the current `block.timestamp` via `_getTargetPricePrecise()`. The stored multiplier is only updated at the time of `rampTargetPrice()` / `stopRampTargetPrice()` calls, so a stale value is used during the ramp period.

### Excluded Reason: multi-transaction
- The multiplier is set in the `rampTargetPrice()` call (tx1)
- Subsequent swap/addLiquidity calls (tx2~N) cause `_xp()` to use the stale multiplier
- The "staleness" of the multiplier arises from the elapsed time between transactions (changes in `block.timestamp`)
- Within a single transaction, `tokenPrecisionMultipliers` is merely a state value set in a prior tx; "staleness" cannot be judged

---

## web3bugs_5_H_12

- **Contract**: Pools
- **Function**: getAddedAmount (internal)
- **Bug line (original)**: 201
- **Pattern**: erroneous_accounting
- **Status**: `annotated` (was: `not_detectable,interface-call-return-top`)

### Bug Description
In the else branch of `getAddedAmount(address _token, address _pool)`, `addedAmount = _balance - mapToken_tokenAmount[_pool]` is performed. Since the function should compute the added amount of `_token`, the correct key is `_token`, but the wrong key `_pool` is used. When `_token != _pool`, an incorrect result is returned. This can be exploited via `sync(token1, token2)` and similar calls to corrupt accounting.

### Dependencies
- iERC20 interface (balanceOf)

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| SymAddress | address(this) | addr0 | 24 | The contract itself |
| SymAddress | _token | addr1 | 24 | Function parameter |
| SymAddress | _pool | addr2 | 24 | Function parameter, ≠ _token |
| SymAddress | VADER | addr3 | 24 | state variable, ≠ _token (skip if branch) |
| SymAddress | USDV | addr4 | 24 | state variable, ≠ _token (skip else if branch) |
| IReturn | iERC20(_token).balanceOf(address(this)) | [200, 200] | 24 | Current balance |
| StateVar | mapToken_tokenAmount[_token] | [100, 100] | 24 | Stored amount of _token |
| StateVar | mapToken_tokenAmount[_pool] | [50, 50] | 24 | Stored amount of _pool, ≠ _token's |

- Else branch entry condition: _token ≠ VADER, _token ≠ USDV (all distinct via SymAddress)
- Underflow check: _balance(200) >= mapToken_tokenAmount[_pool](50) ✓, _balance(200) >= mapToken_tokenAmount[_token](100) ✓

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| Post | 34 | returnExpression == _balance - mapToken_tokenAmount[_token] | violated | 5.md H-12: function contract naturally derivable from the function name (getAddedAmount) + mapping name (mapToken_tokenAmount) + parameter (_token) semantics. Correct result 100 (200-100) vs buggy result 150 (200-50) → violated |

---

## web3bugs_16_H_06

- **Contract**: GasOracle
- **Function**: latestAnswer
- **Bug Line**: 32, 33, 35
- **Status**: `not_detectable (L3: unsupported-construct-top)`

### Bug Description
In `latestAnswer()`, the raw values from `gasOracle.latestAnswer()` (line 32) and `priceOracle.latestAnswer()` (line 33) are passed directly to `PRBMathUD60x18.mul()` (line 35) without 18-decimals conversion via `toWad()`. If the Chainlink oracle's decimals are not 18, the result scale is wrong. The `toWad()` function exists but is never called.

### Reason Not Detectable
- Interface calls are now supported, so the return values of `gasOracle.latestAnswer()` and `priceOracle.latestAnswer()` are not TOP
- However, `PRBMathUD60x18.mul(gasPrice, ethPrice)` (line 35) → the PRBMath library uses inline assembly internally → result is TOP (L3)
- Since the result is TOP, scale errors cannot be verified via annotation
- Secondarily, the bug itself is also a `toWad()` omission (missing-code pattern), but L3 is the primary blocker

---

## web3bugs_14_H_03

- **Contract**: BadgerYieldSource
- **Function**: balanceOfToken
- **Bug Line**: 36
- **Status**: `excluded,missing-dependency`

### Bug Description
In `balanceOfToken()`, `badger.balanceOf(address(badgerSett))` (line 36) returns only the badger physically held in the Sett contract, omitting funds deployed to strategies. The correct implementation should use `badgerSett.balance()`, which returns the total balance (Sett + Controller + Strategy).

### Excluded Reason
- The interface definition files for `IBadgerSett` and `IBadger` do not exist in the repository
- Without dependencies, IntentChecker cannot recognize the interfaces, making analysis itself impossible

---

## web3bugs_25_H_05

- **Contract**: CTokenMultiOracle
- **Function**: _setSource
- **Bug Line**: 110
- **Status**: `not_detectable (L4a: inexpressible-expected-value)`

### Bug Description
In `_setSource()` (line 110), `decimals_` is hardcoded to 18. However, Compound's exchange rate is scaled as `1 * 10^(18 - 8 + underlyingTokenDecimals)`, so the correct decimals are `10 + underlyingTokenDecimals` (e.g., USDC=16, DAI=28). The wrong decimals are used in the price scaling computation of `_peek()`/`_get()`, causing price errors.

### Reason Not Detectable
- Buggy value: `decimals_ = 18` (hardcoded constant)
- Correct value: `18 - 8 + underlyingTokenDecimals` — `underlyingTokenDecimals` is a variable that does not exist in the code
- Computing the correct value requires a new intermediate computation not present in the current code, such as `CToken.underlying()` → `IERC20.decimals()`
- The correct decimals cannot be expressed by an arithmetic combination of existing variables in the program (L4a)

---

## web3bugs_61_H_04

- **Contract**: YearnYield
- **Function**: getTokensForShares
- **Bug Line**: 180
- **Status**: `not_detectable (L4a: interface-call-return-top)`

### Bug Description
In `getTokensForShares()` (line 180), the result of `IyVault.getPricePerFullShare()` is divided by `1e18`, but Yearn's `getPricePerFullShare()` returns at `vault.decimals()` precision (= underlying token decimals). The correct implementation is `div(10 ** vault.decimals())`. Conversion errors occur for tokens not using 18 decimals (e.g., USDC=6).

### Reason Not Detectable (L4a: inexpressible-expected-value)
- Interface calls are now supported, so `getPricePerFullShare()` return value is not TOP
- However, the correct divisor `10 ** vault.decimals()`:
  1. `vault.decimals()` is not called in the buggy code → no variable in scope holds the value
  2. The annotation grammar does not allow function calls → `10 ** IyVault(...).decimals()` cannot be expressed
  3. The correct divisor cannot be expressed as an arithmetic combination of existing variables
- Same pattern as 25_H_01: the correct denominator depends on the return value of a function call not present in the code → L4a

---

## web3bugs_79_H_02

- **Contract**: LaunchEvent
- **Function**: createPair
- **Bug Line**: 398
- **Status**: `not_detectable (L5b: wrong-code)`

### Bug Description
In `createPair()` (line 398), when below the floor price, `tokenAllocated = (wavaxReserve * 10**token.decimals()) / floorPrice` is computed. Since `floorPrice` is on a 1e18 scale, the correct computation is `wavaxReserve * 1e18 / floorPrice`. Severe errors occur for tokens not using 18 decimals (e.g., WBTC=8).

### Reason Not Detectable (L5b: wrong-code)
- Interface calls are now supported, so the return value of `token.decimals()` is not TOP
- However, the annotation `tokenAllocated == wavaxReserve * 1e18 / floorPrice` is the fix code itself
- The natspec "scaled to 1e18" provides the scaling factor, but applying it to the formula = fixing the bug
- Unlike 5_H_07 (which provides the complete formula in a comment), the natspec provides only the scaling factor → constructing the formula requires bug awareness → L5b

---

## web3bugs_29_H_08

- **Contract**: HybridPool
- **Function**: _getReserves
- **Bug Line**: 255, 256
- **Status**: `not_detectable (L3: unsupported-construct-top)`

### Bug Description
In `_updateReserves()`, `_balance()` already converts BentoBox shares→amounts and stores the result in `reserve0`/`reserve1`. However, in `_getReserves()` (lines 255-256), the reserves (already in amounts) are converted again via `_toAmount()` (double conversion). All swap/mint/burn operations use the wrong reserves.

### Reason Not Detectable
- Not an interface call, but a low-level `staticcall` + `abi.decode` pattern:
  - `__balance()`: `bento.staticcall(abi.encodeWithSelector(...))` → `abi.decode(___balance, (uint256))`
  - `_toAmount()`: `bento.staticcall(abi.encodeWithSelector(...))` → `abi.decode(_output, (uint256))`
- `staticcall` is a low-level external call and untrackable; `abi.decode` is an L3 unsupported construct → return value TOP
- `_balance()` → TOP, `_updateReserves()`: `reserve0 = uint128(TOP)` → TOP in storage
- `_getReserves()`: `_toAmount(token0, TOP)` → TOP
- Regardless of interface support, `staticcall` + `abi.decode` is the blocker (L3)

---

## web3bugs_78_H_02

- **Contract**: RebaseProxy
- **Function**: mint
- **Bug line (original)**: 36
- **Pattern**: erroneous_accounting
- **Status**: `annotated` (was: `not_detectable,interface-call-return-top`)

### Bug Description
In `mint()` (line 36), `proxy = (baseBalance * ONE) / _redeemRate` is computed, but `baseBalance` is the total balance after the transfer (including pre-existing balance). The correct implementation is `(amount * ONE) / _redeemRate` (based on the deposited amount). If a pre-existing balance is present, over-minting occurs.
- Report: sponsor (gititGoro) confirmed

### Dependencies
- `TokenProxyLike.sol` (exists in dependencies/): `ONE = 1 ether` (constant, inlined), `baseToken` (internal state variable)
- ERC20 (inherited from OpenZeppelin): `_mint()`, `_balances`, `_totalSupply` — **Issue 8 (access to inherited private state variables) required**

### Required Implementation
- **Issue 8**: Need to access the inherited ERC20's `_balances[to]` and `_totalSupply` private state variables

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| StateVar | _totalSupply | [1000000000000000000000, 1000000000000000000000] | 19 | 1000e18, inherited from ERC20 (Issue 8) |
| StateVar | _balances[to] | [0, 0] | 19 | Receiver initial balance 0, inherited from ERC20 (Issue 8) |
| IReturn | IERC20(baseToken).balanceOf(address(this)) | [1500000000000000000000, 1500000000000000000000] | 19 | 1500e18 |
| IReturn | IERC20(baseToken).transferFrom() | true | 19 | require passes |
| LocalVar | amount | [500000000000000000000, 500000000000000000000] | 19 | 500e18 deposit amount |

- ONE = 1e18 (TokenProxyLike constant, inlined during pre-analysis)
- @IReturn cannot distinguish pre/post transfer → both return 1500e18
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
In `_calculatePrincipalWithdrawable()`, `borrowLimit` (line 43) is used as the denominator, but when the start fee is applied, `borrowLimit < totalSupply[_id]`. Function comment: "total lent amount - principal borrowed) * lenders lp balance / total lent amount" — the denominator should be `totalSupply`. If `balanceOf > borrowLimit`, withdrawal exceeds the available amount → revert.
- Report: sponsor confirmed (judge resolved)

### Dependencies
**Inheritance:**
- `ERC1155Upgradeable`: provides `balanceOf()` (Issue 8: inherited private state variables)
- `ReentrancyGuardUpgradeable`
- `IPooledCreditLineEnums`: enum definitions
- `ILenderPool`: interface

**using:**
- `SafeMath` for uint256
- `SafeERC20` for IERC20

**State variable types (interfaces):**
- `ISavingsAccount` (`101_ISavingsAccount.sol` exists)
- `IPooledCreditLine`: `getPrincipal()` call
- `IVerification`
- `IERC20`

### Debug Annotations
| Type | Variable | Value | Line | Comment |
|------|----------|-------|------|---------|
| StateVar | pooledCLConstants[_id].borrowLimit | [99000, 99000] | 43 | borrowLimit after fee deduction |
| IReturn | POOLED_CREDIT_LINE.getPrincipal(_id) | [0, 0] | 43 | not borrowed |
| IReturn | balanceOf(_lender, _id) | [100000, 100000] | 43 | sole lender = totalSupply |
| LocalVar | _id | [1, 1] | 43 | pool id |

- _borrowedTokens = 99000
- _totalLiquidityWithdrawable = 99000 - 0 = 99000
- _principalWithdrawable = 99000 * 100000 / 99000 = 100000
- Buggy: 100000 > 99000 (exceeds available)
- Correct (when totalSupply is used): 99000 * 100000 / 100000 = 99000

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| During | 45 | _principalWithdrawable <= _totalLiquidityWithdrawable | violated | Individual withdrawal amount ≤ total available amount. Basic accounting invariant. Buggy: 100000 > 99000 → violated |

---

## web3bugs_101_H_02

- **Contract**: LenderPool
- **Function**: terminate
- **Bug Line**: 389, 400
- **Status**: `not_detectable (L5b: wrong-code)`

### Bug Description
In `terminate()`, `_actualNotBorrowedInShares` (line 389) is computed via a mixed token/share calculation, then combined with `_totalInterestInShares` and passed to `withdrawShares` (line 400). Mixing token amounts and shares produces an incorrect value. The correct implementation simply uses `_sharesHeld` directly to withdraw all shares.

### Reason Not Detectable (L5b: wrong-code)
- Interface calls are now supported, so the return values of `getPrincipal()` and `getSharesForTokens()` are not TOP
- However, the correct value is simply `_sharesHeld` (terminate = withdraw all shares)
- The buggy code computes `_totalBorrowAsset` via complex mixed token/share calculations, but the correct implementation directly uses `_sharesHeld`
- Knowing that `_sharesHeld` is the answer = knowing that the complex calculation is unnecessary = bug awareness → L5b

---

## web3bugs_192_H_01

- **Contract**: Lock
- **Function**: extendLock
- **Bug Line**: 90, 91 (original)
- **Status**: `not_detectable (L5a: missing-state-update)`

### Bug Description
In `extendLock()`, tokens are received (`transferFrom`, line 90) but the `totalLocked[_asset] += _amount` update is missing. Subsequently, when `release()` is called, `totalLocked[asset] -= lockAmount` underflows, causing funds to be locked permanently.

### Reason Not Detectable
- The issue is not an erroneous numeric operation inside `extendLock()`, but the missing `totalLocked[_asset] += _amount` code that should be there
- Expressible as a `totalLocked[_asset] Changed` or `Before < After` post-condition, but writing this annotation requires already knowing that "totalLocked must be updated"
- `lock()` correctly performs `totalLocked += _amount`, but the developer overlooked the consistency that the same update is needed in `extendLock()` → bug awareness required (L5a: missing-state-update)

---

## web3bugs_36_H_02

- **Contract**: Basket
- **Function**: auctionBurn
- **Bug Line**: 105 (original)
- **Status**: `not_detectable (L4d: missing-state-update)`

### Bug Description
In `auctionBurn()`, the `ibRatio` update is missing after `_burn()`. While `handleFees()` performs the `ibRatio` update due to fees, there is no `ibRatio = ibRatio * startSupply / (startSupply - amount)` update for the supply decrease caused by the burn. When other users subsequently call `burn()`, the lower ibRatio in `pushUnderlying()` causes them to receive fewer underlying tokens.

### Reason Not Detectable
- The `_burn()` operation in `auctionBurn()` is correct; what is missing is the `ibRatio` update code after the burn
- Since `handleFees()` already changes `ibRatio`, a simple `Changed` annotation is satisfied. Knowing that an additional update due to burn is needed enables a more precise annotation
- In `burn()`, the `handleFees()` → `pushUnderlying()` → `_burn()` order naturally reflects ibRatio, but the developer overlooked the consistency that a separate update is required in `auctionBurn()` → grammatically, the multi-var product invariant (`ibRatio × totalSupply` preservation) is outside the expressive range of Post/During in the annotation grammar → L4d (Algorithm/Usable, only L4d case)

---

## web3bugs_65_H_01

- **Contract**: Basket
- **Function**: handleFees
- **Bug Line**: 136, 137 (original)
- **Status**: `not_detectable (L5a: missing-state-update)`

### Bug Description
In `handleFees()`, when `startSupply == 0`, the function returns immediately via `return;` while omitting the `lastFee = block.timestamp` update. On subsequent mint/burn, the stale `lastFee` is used to compute fees, applying fees to the period when supply was 0.

### Reason Not Detectable
- Of the three branches in `handleFees()`, two (`lastFee == 0`, normal `else`) perform `lastFee = block.timestamp`, but only the `startSupply == 0` branch omits it
- Expressible as a `lastFee Changed` post-condition, but writing the annotation requires knowing that "lastFee must always be updated even when supply is 0" → bug awareness required (L5a: missing-state-update)

---

## web3bugs_62_H_03

- **Contract**: Stream
- **Function**: recoverTokens (bug line 672), root cause: claimReward
- **Bug Line**: 672 (original, symptom manifestation point)
- **Status**: `not_detectable (L5a: missing-state-update)`

### Bug Description
In `claimReward()`, reward tokens are transferred (line 575) but `rewardTokenAmount` is not decreased. `rewardTokenAmount` is only increased in `fundStream()`. Subsequently, in `recoverTokens()`, the `excess = balanceOf(this) - (rewardTokenAmount + rewardTokenFeeAmount)` computation underflows or evaluates to 0 due to the stale `rewardTokenAmount`, making token recovery impossible.

### Reason Not Detectable
- The root cause is the missing `rewardTokenAmount -= rewardAmt` in `claimReward()` (missing state update)
- Expressible as a `rewardTokenAmount Changed` or `Before > After` post-condition, but writing the annotation requires knowing that "rewardTokenAmount must be decreased when reward is transferred" → bug awareness required (L5a: missing-state-update)
- Bug line 672 itself also has a `balanceOf()` external call → TOP (L2a) as a secondary blocker

---

## web3bugs_62_H_10

- **Contract**: Stream
- **Function**: recoverTokens (bug line 654), root cause: creatorClaimSoldTokens
- **Bug Line**: 654 (original, symptom manifestation point)
- **Status**: `not_detectable (L5a: missing-state-update)`

### Bug Description
In `creatorClaimSoldTokens()`, deposit tokens are transferred (line 597) but `depositTokenAmount` and `redeemedDepositTokens` are not updated. Subsequently, in `recoverTokens()`, the `excess = balanceOf(this) - (depositTokenAmount - redeemedDepositTokens)` computation underflows or yields a wrong excess due to the stale values.

### Reason Not Detectable
- The root cause is the missing `redeemedDepositTokens = depositTokenAmount` or `depositTokenAmount = 0` in `creatorClaimSoldTokens()` (missing state update)
- Same pattern as 62_H_03: tracking variable not updated in the token transfer function
- Annotation is expressible but requires bug awareness (L5a: missing-state-update)
- Bug line 654 itself also has a `balanceOf()` external call → TOP (L2a) as a secondary blocker

---

## web3bugs_35_H_10

- **Contract**: ConcentratedLiquidityPool
- **Function**: burn
- **Bug Line**: 217 (original)
- **Status**: `not_detectable (L4c: missing-state-update)`

### Bug Description
When removing a position in `burn()`, only the fee amounts are deducted via `reserve0 -= amount0fees` / `reserve1 -= amount1fees`, while the actual liquidity removal amounts (`amount0`, `amount1`) are not deducted. Subsequent `reserve`-based computations use inflated reserve values, distorting price/liquidity.

### Reason Not Detectable
- Missing state update where `reserve0 -= amount0` is omitted (L4c: Value/Usable, grammar limit — Entry/Exit direction is expressible but magnitude-only difference is required while arithmetic postEntryExit is not supported)
- Expressible as `@Post reserve0 == Before(reserve0) - amount0`, but writing the annotation requires knowing that "reserve must be deducted by amount0 on burn" → bug awareness required
- Additionally, since parameters (`lower`, `upper`, `amount`, `recipient`, `unwrapBento`) are passed via `abi.decode`, concrete values cannot be set via debugging annotations → all decoded variables are TOP

---

## web3bugs_35_H_08

- **Contract**: ConcentratedLiquidityPool
- **Function**: mint, burn
- **Bug Lines (original)**: 176 (mint), 242 (burn)
- **Status**: `not_detectable (L3: unsupported-construct-top)`

### Bug Description
In `mint()` and `burn()`, the liquidity update condition uses strict inequalities `priceLower < currentPrice && currentPrice < priceUpper`. When `priceLower == currentPrice` (the current price exactly matches the position's lower bound), liquidity is not updated, distorting swap amounts. The correct condition is `priceLower <= currentPrice`.

### Reason Not Detectable
- **Primary blocker: abi.decode → TOP (L3)**
  - `mint()` line 142: `abi.decode(data, (MintParams))` → all mint parameters TOP
  - `burn()` lines 232-235: `abi.decode(data, ...)` → all burn parameters TOP
  - `priceLower = TickMath.getSqrtRatioAtTick(TOP)` → TOP
  - Condition `TOP < concrete` → both branches explored → boundary edge case indistinguishable
- **Even without abi.decode**: setting the exact boundary value `priceLower == currentPrice` via debug annotation is required, and this edge case is not caught by general range settings
- 35_H_10 and 35_H_12 in the same contract also have abi.decode as a secondary blocker

---

## web3bugs_113_H_05

- **Contract**: NFTPairWithOracle
- **Function**: _lend
- **Bug Line (original)**: 316
- **Status**: `not_detectable (L5b: wrong-validation-operator)`

### Bug Description
The require condition in `_lend()` checks `params.ltvBPS >= accepted.ltvBPS`, but from the lender's perspective lower LTV is favorable, so `params.ltvBPS <= accepted.ltvBPS` is correct. Example: a borrower requests 86% LTV and the lender only accepts up to 80%, but the buggy code executes the loan at 86% → unfavorable to the lender.

### Reason Not Detectable
- **Wrong operator in require condition (L5d)**: should be `<=` instead of `>=`, but the require itself is an intuitive validation statement and is not an annotation target. Expressing the correct condition separately as a During annotation is possible, but redundantly re-validating an already-written require requires knowing that the require is wrong → bug awareness required
- **Buggy parameter not reflected in subsequent computation**: `ltvBPS` is only used in the require check; subsequent amount calculations (`totalShare`, `openFeeShare`, `protocolFeeShare`) are all based on `params.valuation` → ltvBPS mismatch is not reflected in state variables
- **Secondary blocker (L2a)**: `feesEarnedShare += protocolFeeShare` involves `bentoBox.toShare()` interface call → TOP
- The actual effect of ltvBPS appears in the liquidation threshold of the separate `removeCollateral()` function (separate transaction)

---

## web3bugs_61_H_02

- **Contract**: SavingsAccountUtil (library)
- **Function**: savingsAccountTransfer
- **Bug Lines (original)**: 75, 77, 79
- **Status**: `not_detectable (L4a: wrapper-return-indifference)`

### Bug Description
`savingsAccountTransfer()` ignores the actual return value (shares) of `_savingsAccount.transfer()`/`transferFrom()` and returns the input parameter `_amount` as-is. When price per share ≠ 1, the actual shares differ from `_amount`, so the caller records an incorrect shares amount, causing fund loss (cancelPool failure, liquidation failure, etc.).

### Reason Not Detectable (L4a: wrapper-return-indifference)
- **L4a reclassification rationale** (l4_l5_classification.csv reclass_reason: `annotation_plans_md_said_L5a_but_self_contradictory_limitation_types_md_says_L4a_confirmed`)
- Wrapper library function with no own state. The return value is never captured by an assignment in the code, so it is not bound to a named variable in annotation scope → grammar expressibility limit
- Since IReturn is modeled as arg-indifferent for state-modifying interface transfer calls, the buggy version (returning _amount) and the correct version (returning transfer()) are not distinguished via the semantic channel → L4a (pure Type B wrapper)
- Case7 twin (wrapper return misrouting drop pattern, pps/shares mismatch)

---

## web3bugs_110_H_01

- **Contract**: StakedCitadel
- **Function**: balance
- **Bug Lines (original)**: 293, 294
- **Status**: `not_detectable (L4b: missing-code — view function, missing call site)`

### Bug Description
`balance()` returns only `token.balanceOf(address(this))` (vault balance), omitting `IStrategy(strategy).balanceOf()` (strategy balance). The correct implementation is the sum of vault + strategy. This value is used in the entire accounting (`_depositFor`, `_withdraw`, `_handleFees`, etc.), severely distorting shares mint/burn computations.

### Reason Not Detectable (L4b: missing-code)
- **L4b reclassification rationale** (l4_l5_classification.csv reclass_reason: `annotation_plans_L5a_but_view_function_missing_call_site_G3_I9_L4b`)
- `balance()` is a view function — no state changes, no state var subject to @Post Entry/Exit/changed
- Since the missing `IStrategy(strategy).balanceOf()` call itself does not exist in the code, the call site (G3) referenced by the annotation is absent → cannot express `returnExpression == balanceOf(this) + strategy.balanceOf()` via grammar
- Per I9 principle: grammar expressibility (missing call site) precedes the bug awareness layer → L4b (not L5a)
- Case11/Case16/Case20 family (vault/strategy split pattern)

---

## web3bugs_17_H_02

- **Contract**: Buoy3Pool
- **Function**: safetyCheck
- **Bug line (original)**: 88
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L4b: inexpressible-intent — missing scope vars)`

### Bug Description
The stablecoin price ratio check in `safetyCheck()` is incomplete:
1. Only `a/b` and `a/c` ratios are checked; `b/c` is not checked → by transitivity, `b/c` is only guaranteed within `2 * BASIS_POINTS` range
2. `a/b` in range ≠ `b/a` in range (asymmetric)
3. NatSpec specifies "Curve + external oracle" check, but no oracle call is made
- Report: sponsor (kristian-gro) confirmed, b/c check added

### Reason Not Detectable (L4b: inexpressible-intent)
- **L4b reclassification rationale** (l4_l5_classification.csv reclass_reason: `annotation_plans_md_said_L5a_but_post_condition_not_expressible_due_to_missing_scope_vars_limitation_types_L4b_confirmed`)
- The previous L5a (missing-code) interpretation was in the direction of "adding b/c check code", but in actual annotation writing, the required scope variables (`b/c` ratio, external oracle result) do not exist in the local/state scope of the view function `safetyCheck()` → inexpressible by the grammar itself → L4b
- Interface calls are now supported, so the return value of `curvePool.get_dy()` is not TOP, but the named variables for the transitivity-completing expression (`b/c`) are outside the function scope → L4b (grammar expressibility limit)

---

## web3bugs_59_H_05

- **Contract**: AuctionEscapeHatch
- **Function**: exitEarly
- **Bug lines (original)**: 83, 87
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L4a: wrong-code)`

### Bug Description
In `exitEarly()`, when `auction.amendAccountParticipation(msg.sender, _auctionId, amount, maltQuantity)` is called, `maltQuantity` is the value with profit penalty applied (less than the actual amount). `amount` (the entire commitment) is deducted as-is, but only `maltQuantity` (with penalty applied) is deducted, so the `userMaltPurchased / userCommitment` ratio gradually increases. Repeated calls enable excessive profit.
- Report: sponsor (0xScotch) confirmed

### Reason Not Detectable (L4a: wrong-code)
- **L4a reclassification rationale** (l4_l5_classification.csv reclass_reason: `annotation_plans_md_says_L5b_but_limitation_types_md_says_L4a_objective_judgment_L4a`)
- `amendAccountParticipation` is a state-modifying external call — verifying state changes in the external contract is outside annotation scope (→ same family as L4a inexpressible-expected-value: the correct value of arg[N] is the original pre-penalty quantity, but this value does not exist as a named variable in the program)
- IReturn arg indifference: when checking `func.arg[N]` in the annotation grammar, there is no comparison target in scope against the original pre-penalty value → structural expressibility limit → L4a
- Per I9 principle, despite being wrong-code, missing scope vars is more fundamental, so unified as L4a (Case4 twin, pre-vs-post penalty value collapse)

---

## web3bugs_70_H_09

- **Contract**: USDV
- **Function**: mint, burn
- **Bug lines (original)**: 76 (mint), 109 (burn)
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L5b: wrong-code)`

### Bug Description
`mint()`: `uAmount = (vPrice * vAmount) / 1e18` — if `vPrice` is in USD/Vader units, the result is a USD amount, not a USDV amount.
`burn()`: `vAmount = (uPrice * uAmount) / 1e18` — same pattern. The formula must change depending on the meaning of the oracle price.
- Report: sponsor not confirmed (judge resolved)

### Reason Not Detectable (L5b: wrong-code)
- Interface calls are now supported, so the return values of `lbt.getVaderPrice()` and `lbt.getUSDVPrice()` are not TOP
- However, the correct price conversion formula depends on the unit/meaning of the price returned by the oracle
- Whether `vPrice * vAmount / 1e18` or `vAmount * 1e18 / vPrice` is correct requires understanding the oracle spec
- Domain knowledge / bug awareness → L5b

---

## numscout_EthereumGod

- **Contract**: EthereumGod
- **Function**: swapAndLiquify
- **Bug lines (original)**: 937, 941, 942, 956
- **Pattern**: precision_loss_trend
- **Status**: `not_detectable (L2a: interface-call-return-top)`

### Bug Description
In `swapAndLiquify()`, the chained div/mul operations of fee splitting accumulate precision loss. When distributing marketing fee and liquidity fee, multi-step division/multiplication truncates intermediate values, causing errors in the final distribution amounts.

### Reason Not Detectable (L2a: interface-call-return-top)
- ~~`address(this).balance` → L3 unsupported construct~~ → providable as GlobalVar via Issue 7 implementation
- However, `address(this).balance` is read **twice**:
  1. `initialBalance = address(this).balance` (line 948, before swap)
  2. `address(this).balance.sub(initialBalance)` (line 955, after swap)
- Between the two reads, `swapTokensForEth(toSwapForEth)` (line 952) is executed
  - Internally calls `uniswapV2Router.swapExactTokensForETHSupportingFeeOnTransferTokens()`
  - **state-modifying interface call** → @IReturn not applicable
  - The swap transfers ETH to the contract → balance changes
- Static GlobalVar provides only one value → cannot express the balance difference before/after swap
- `fromSwap = (balance after swap) - initialBalance` → if the two balances are equal, this becomes 0 and is meaningless
- Primary blocker: balance change cannot be tracked due to state-modifying interface call (same pattern as 5_H_15)

---

## numscout_HippoHotel

- **Contract**: HippoHotel
- **Function**: withdraw
- **Bug line (original)**: 1937
- **Pattern**: precision_loss_trend
- **Status**: `excluded (E7: inherent-truncation)`

### Numscout Detection
Numscout detected the `precision_loss_trend` pattern in `balance.mul(25).div(100)` (line 1937). A heuristic match indicating that truncation may occur in a `mul().div()` chain.

### Original Code (lines 1935-1940)
```solidity
function withdraw() external onlyOwner {
    uint256 balance = address(this).balance;         // L1936
    uint256 balance2 = balance.mul(25).div(100);     // L1937 ← Numscout detection point
    payable(wallet2).transfer(balance2);              // L1938
    payable(wallet1).transfer(balance.sub(balance2)); // L1939
}
```

### Excluded Reason (E7: inherent-truncation)

**1. The code already uses the optimal operation order (mul-first)**
- `balance.mul(25).div(100)` = `balance * 25 / 100` (mul-first)
- Equal to or better than div-first `balance.div(100).mul(25)`

**2. Alternative implementations yield the same result — no "correct code" exists**
- `floor(balance * 25 / 100)` = `floor(balance / 4)` (mathematical identity)
- Verification: balance=1003 → `1003*25/100 = 250`, `1003/4 = 250` → identical
- Any integer arithmetic implementation yields the same result as `floor(balance * 0.25)`

**3. No fund loss**
- wallet2: `balance2 = 250`
- wallet1: `balance - balance2 = 1003 - 250 = 753`
- Total: `250 + 753 = 1003 = balance` (complete distribution; remainder allocated to wallet1)

**4. Buggy/correct cannot be distinguished via intent annotation**
- `balance2 == balance * 25 / 100` → exactly what the code does, so always satisfied
- `balance2 * 100 == balance * 25` (lossless verification) → violated for any implementation when balance % 4 ≠ 0
- `balance2 == balance / 4` → always satisfied (mathematical identity)
- Every intent evaluates identically in buggy and correct versions

**5. Numscout false positive analysis**
- Numscout's `precision_loss_trend` pattern heuristically detects truncation possibilities in `mul().div()` chains
- In this case truncation does occur (75 wei loss when balance=1003), but this is a mathematical property of integer arithmetic, not a coding mistake
- The alternative code does not produce a different result, so it does not qualify as a "fixable bug"

---

## web3bugs_58_H_04

- **Contract**: AaveVault
- **Function**: tvl (line 47), _push, _pull
- **Bug Line (original)**: 47
- **Status**: `not_detectable (L4b: ordering-problem)`

### Bug Description
`tvl()` returns the cached `_tvls` array. In `_push()`, `updateTvls()` is called **after** the Aave lending pool deposit, so the caller (LPIssuer) computes shares based on the old tvl. Since shares are issued against the tvl before Aave's rebasing aToken interest is reflected, excessive shares are minted, allowing an attacker to siphon interest.

### Reason Not Detectable (L4b: ordering-problem)
- **L4b reclassification rationale** (l4_l5_classification.csv reclass_reason: `annotation_plans_L5a_but_ordering_problem_not_expressible_L4b_per_function_type`)
- The bug essence is the **operation ordering** inside `_push()`: `updateTvls()` is called after the deposit rather than before
- Each function is correct in isolation (`tvl()` view, `_push()` deposit+updateTvls order, `updateTvls()` reflects balanceOf). The ordering bug is not a relationship within a single function scope but a call-flow property of "stale cache exposed to caller"
- No annotation grammar element (e.g., `@During before(updateTvls) before(deposit)`) exists to express ordering → grammar expressibility limit → L4b (not L5a)

---

## web3bugs_47_H_02

- **Contract**: WrappedIbbtcEth
- **Function**: transferFrom
- **Bug Line (original)**: 111
- **Pattern**: erroneous_accounting
- **Status**: `annotated`

### Bug Description
In `transferFrom()`, converting `amount` to `amountInShares` and passing it to `_transfer` is correct, but the `_approve` call also deducts allowance using `amountInShares`. Allowance is in balance units (rebalanced amount), not shares units, so when `pricePerShare > 1e18` the deduction is too small, allowing a spender to transfer more than the approved amount.

### Annotation Plan

**Contraction**: `target_contracts_contraction/web3bugs_47_H_02.sol` (29 lines)
- Includes `balanceToShares()` + `transferFrom()`

**Dependencies**:
- `47_ERC20Upgradeable.sol`: `_transfer`, `_approve`, `_allowances`, `_balances`
- `47_SafeMathUpgradeable.sol`: `.mul()`, `.div()`, `.sub()`, `.add()`
- `47_ContextUpgradeable.sol`: `_msgSender()` → `msg.sender`
- `47_Initializable.sol`, `47_IERC20Upgradeable.sol`, `47_AddressUpgradeable.sol`, `ICore.sol`

**Debug annotations (line 22, start of transferFrom)**:
- `// @LocalVar sender = symbolicAddress 1`
- `// @LocalVar recipient = symbolicAddress 2`
- `// @LocalVar amount = [100, 100]`
- `// @StateVar _allowances[1][101] = [1000, 1000]`
- `// @StateVar pricePerShare = [2000000000000000000, 2000000000000000000]`
- `// @StateVar _balances[1] = [500, 500]`

**Intent annotation**:
- `@Post _allowances[1][101] == 900` (or `@During` after line 26)
- Buggy code: 1000 - 50(amountInShares) = 950 → **violated**
- Correct code: 1000 - 100(amount) = 900 → **satisfied**

**Rationale**: 47.md H-02 — approve is not overridden, so allowance is in balance units, but transferFrom deducts in shares units. Per the ERC20 standard, allowance deduction must be in the user-specified amount units.

---

## web3bugs_62_H_08

- **Contract**: Stream
- **Function**: updateStreamInternal
- **Bug Lines (original)**: 226;229;230
- **Pattern**: inconsistent_state_updates
- **Status**: `annotated`

### Bug Description
In `updateStreamInternal()`, `ts.lastUpdate` is updated only inside the `if (acctTimeDelta > 0 && ts.tokens > 0)` block. When a user fully withdraws (`ts.tokens == 0`) and then stakes again, the if block is skipped on the updateStream call (since `ts.tokens == 0`), so `ts.lastUpdate` is not refreshed. On a later withdraw, the stale `ts.lastUpdate` causes `ts.tokens` decay to be miscomputed, allowing withdrawal of more tokens than actually owed.

### Annotation Plan

**Contraction**: `target_contracts_contraction/web3bugs_62_H_08.sol` (183 lines)
- Includes `lastApplicableTime()`, `rewardPerToken()`, `earned()`, `updateStreamInternal()`

**Dependencies**: None (all called functions are within the same contract)

**Debug annotations (line 146, start of updateStreamInternal)**:

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

**Intent annotation (line 182, just before updateStreamInternal returns)**:
- `// @Post tokensNotYetStreamed[101].lastUpdate == [1000, 1000]`

**Verification scenario** (ts.tokens == 0, block.timestamp >= startTime):
1. `rewardPerToken()`: totalVirtualBalance==0 → return 100 (unchanged)
2. `earned()`: 0 * (100-100) / 1e18 + 0 = 0
3. `acctTimeDelta = 1000 - 800 = 200`
4. `200 > 0 && 0 > 0` → FALSE → ts.lastUpdate update skipped
5. Buggy: `tokensNotYetStreamed[101].lastUpdate == 800` ≠ 1000 → **VIOLATION**
6. Correct (update ts.lastUpdate outside the if block): `tokensNotYetStreamed[101].lastUpdate == 1000` → **SATISFIED**

**Rationale**: `updateStreamInternal` is a stream state update function, so it is a natural invariant that `ts.lastUpdate` is refreshed to the current timestamp on each call. The intent "after calling the update function, lastUpdate == block.timestamp" can be written without bug-awareness.

---

## web3bugs_51_H_02

- **Contract**: SwapUtils (library)
- **Function**: rampTargetPrice
- **Bug Lines (original)**: 1573;1578
- **Pattern**: erroneous_accounting
- **Status**: `annotated`

### Bug Description
The sanity check in `rampTargetPrice()` uses `MAX_RELATIVE_PRICE_CHANGE` (10^16, 1% delta) as a multiplier, making the require condition always false.
- decrease: `future * 10^16 / 10^18 = future * 0.01 >= initial` → since future < initial, always false
- increase: `future <= initial * 10^16 / 10^18 = initial * 0.01` → since future >= initial, always false

Correct formula: must use `MAX_RELATIVE_PRICE_CHANGE + WEI_UNIT` (= 1.01 multiplier). As a result, the target price can never be updated.

### Annotation Plan

**Contraction**: `target_contracts_contraction/web3bugs_51_H_02.sol` (125 lines)
- `_getTargetPricePrecise()` (L80-98), `rampTargetPrice()` (L100-124)

**Dependencies**: `_getTargetPricePrecise` — internal function in the same library, no external calls

**Debug annotations (line 105, start of rampTargetPrice, 8 items)**:

Global:
- `// @GlobalVar block.timestamp = [2000000, 2000000]`

TargetPrice storage self fields (state variables, 5 items):
- `// @StateVar self.initialTargetPriceTime = [1000000, 1000000]`
- `// @StateVar self.futureTargetPriceTime = [1500000, 1500000]`
- `// @StateVar self.futureTargetPrice = [1000000000000000000, 1000000000000000000]`
- `// @StateVar self.initialTargetPrice = [1000000000000000000, 1000000000000000000]`
- `// @StateVar self.originalPrecisionMultipliers[0] = [1000000000000000000, 1000000000000000000]`

Function parameters (local variables, 2 items):
- `// @LocalVar futureTargetPrice_ = [990000000000000000, 990000000000000000]`
- `// @LocalVar futureTime_ = [3209600, 3209600]`

**Intent annotation (line 113, buggy require)**:
- `// @During require passable`

**Verification scenario** (attempt to decrease target price by 1%):
1. L105: `2000000 >= 1000000 + 86400` → ✓ (1 day elapsed)
2. L106: `3209600 >= 2000000 + 1209600` → ✓ (MIN_RAMP_TIME satisfied)
3. L107: `990000000000000000 >= 0` → ✓
4. L109: `_getTargetPricePrecise(self)` → `block.timestamp(2M) >= futureTargetPriceTime(1.5M)` → else → returns `10^18`
5. L110: `futureTargetPricePrecise = 990000000000000000 * 1 = 990000000000000000`
6. L112: `990000000000000000 < 10^18` → true (decrease branch)
7. L113: `990000000000000000 * 10^16 / 10^18 = 9900000000000000` → `9900000000000000 >= 10^18` → **FALSE → REVERT**
8. `@During require passable` → **VIOLATED** ✓

**Correct code verification** (using `MAX_RELATIVE_PRICE_CHANGE + WEI_UNIT`):
- `990000000000000000 * (10^16 + 10^18) / 10^18 = 990000000000000000 * 1.01 = 999900000000000000`
- `999900000000000000 >= 10^18` → FALSE (0.1% gap) — but a 1% decrease is within the 1% limit and should pass
- The actual check is `futureTargetPricePrecise.mul(MAX_RELATIVE_PRICE_CHANGE.add(WEI_UNIT)).div(WEI_UNIT) >= initialTargetPricePrecise`
- `990000000000000000 * 1010000000000000000 / 1000000000000000000 = 999900000000000000`
- `999900000000000000 >= 1000000000000000000` → FALSE → not exactly 1% but slightly short
- Retry with a 0.99% decrease: `futureTargetPrice_ = 991000000000000000` → `991 * 1.01 = 1000.91 * 10^15 = 1000910000000000000 >= 10^18` → TRUE ✓
- Price changes within the legitimate range become possible → `@During require passable` → **SATISFIED**

**Rationale**: `rampTargetPrice` is a target price update function, so it is a natural expectation that the require passes when called with reasonable inputs (price changes within 1%). `@During require passable` expresses the intent "this function should operate normally" without bug-awareness.

**Note**: The `@During require passable` annotation requires implementation per Issue 6 (code_modification_issues.md).

---

## numscout_BoostToken_indivisible

- **Contract**: BoostToken
- **Function**: sendETHToTeam
- **Bug Lines (original)**: 933;934;935;936
- **Pattern**: indivisible_amount
- **Status**: `annotated`

### Bug Description
When `sendETHToTeam(amount)` distributes ETH to four wallets, it uses integer divisions such as `amount.div(4)`, `amount.div(12)`, `amount.div(9)`. When `amount` is smaller than LCM(4,12,9)=36, all division results are 0, so no wallet receives ETH and the funds remain in the contract.

### Annotation Plan

**Contraction**: `Dataset/Numscout/contraction/indivisible_amount/BoostToken_contraction.sol`
- `sendETHToTeam(uint256 amount)` (L135-140)

**Dependencies**: None (transfer is a native ETH transfer)

**Debug annotations (line 135, start of sendETHToTeam, 1 item)**:

- `// @LocalVar amount = [3, 3]`
  - amount=3: div(4)=0, div(12)=0, div(9)=0 → all transfer amounts are 0

**Intent annotations (L136-L139, one per transfer line, 4 items)**:

- L136: `// @During transfer.arg[0] > 0`
  - amount.div(4) = 0 → 0 > 0 → **VIOLATED** ✓
- L137: `// @During transfer.arg[0] > 0`
  - amount.div(12).mul(5) = 0*5 = 0 → 0 > 0 → **VIOLATED** ✓
- L138: `// @During transfer.arg[0] > 0`
  - amount.div(9).mul(2) = 0*2 = 0 → 0 > 0 → **VIOLATED** ✓
- L139: `// @During transfer.arg[0] > 0`
  - amount.div(9) = 0 → 0 > 0 → **VIOLATED** ✓

**Verification scenario** (amount=3 wei):
1. L136: `3.div(4) = 0` → `_devWalletAddress.transfer(0)` → transfer.arg[0] = 0 → `0 > 0` → **VIOLATED**
2. L137: `3.div(12) = 0`, `0.mul(5) = 0` → transfer.arg[0] = 0 → **VIOLATED**
3. L138: `3.div(9) = 0`, `0.mul(2) = 0` → transfer.arg[0] = 0 → **VIOLATED**
4. L139: `3.div(9) = 0` → transfer.arg[0] = 0 → **VIOLATED**

**Correct code verification** (add minimum-amount check: `require(amount >= 36)`):
- amount=3 → require fails → revert → intent unreachable → vacuously satisfied
- amount=36 → div(4)=9, div(12).mul(5)=15, div(9).mul(2)=8, div(9)=4 → all > 0 → **SATISFIED**

**Rationale**: "Each designated recipient must receive a positive amount" is a natural expectation of a fund-distribution function. No bug-awareness needed.

---

## numscout_HIT

- **Contract**: HIT
- **Function**: getTokens
- **Bug Lines (original)**: 126;144
- **Pattern**: profit_opportunity
- **Status**: `annotated`

### Bug Description
The `getTokens()` function computes the distribution amount as `toGive = value + msg.value * 10000000` (L63). Even when `msg.value = 0` (no ETH paid), `toGive = value` (5000e18, 5000 tokens) is distributed for free. The function is `payable` but lacks a `require(msg.value > 0)` check → unlimited free token acquisition is possible.

### Annotation Plan

**Contraction**: `Dataset/Numscout/contraction/profit_opportunity/HIT_contraction.sol`
- `getTokens()` (L54-80), `distr()` (L41-52)

**Dependencies**: `distr()` — internal function in the same contract

**Debug annotations (line 54, start of getTokens, 7 items)**:

Global:
- `// @GlobalVar msg.value = [0, 0]`
  - msg.sender is preset to 101 (no setup needed)

State:
- `// @StateVar value = [5000000000000000000000, 5000000000000000000000]`
  - 5000e18 (initial value)
- `// @StateVar totalRemaining = [800000000000000000000000000, 800000000000000000000000000]`
  - 800Me18
- `// @StateVar totalDistributed = [200000000000000000000000000, 200000000000000000000000000]`
  - 200Me18
- `// @StateVar totalSupply = [1000000000000000000000000000, 1000000000000000000000000000]`
  - 1Be18
- `// @StateVar distributionFinished = false`
  - To pass the canDistr modifier
- `// @StateVar blacklist[msg.sender] = false`
  - To pass the onlyWhitelist modifier

**Intent annotation (line 69, distr call, 1 item)**:

- `// @During toGive => msg.value`
  - Implication: "If tokens are distributed (toGive > 0), there must be a payment (msg.value > 0)"
  - antecedent: toGive = [5000e18, 5000e18] → non-zero → satisfied (true)
  - consequent: msg.value = [0, 0] → zero → violated (false)
  - true ⇒ false → **VIOLATED** ✓

**Verification scenario** (msg.value=0, no ETH paid):
1. canDistr: `!false` → pass
2. onlyWhitelist: `blacklist[101] == false` → pass
3. L55: `5000e18 > 800Me18` → false, skip
4. L59: `require(5000e18 <= 800Me18)` → pass
5. L63: `toGive = 5000e18 + 0 * 10000000 = 5000e18`
6. L65: `800Me18 <= 200Me18` → false, skip
7. L69: `distr(101, 5000e18)` → 5000 tokens distributed for free
8. `@During toGive => msg.value` → [5000e18] ⇒ [0] → **VIOLATED** ✓

**Correct code verification** (with `require(msg.value > 0)` added):
- msg.value=0 → require fails → revert → intent unreachable → vacuously satisfied

**Alternative correct code** (`toGive = msg.value * 10000000`, free value removed):
- toGive = 0 * 10000000 = 0
- `@During toGive => msg.value`: antecedent `0 != 0` → violated (false) → vacuously true → **SATISFIED** ✓

**Rationale**: "Token distribution (toGive > 0) must presuppose payment (msg.value > 0)" is a natural invariant of an exchange function. No bug-awareness needed.

---

## numscout_WANGMI

- **Contract**: WANGMI
- **Function**: _transfer
- **Bug line (original)**: 428
- **Pattern**: div_in_path
- **Status**: `annotated`

### Bug Description
When processing the sell fee in `_transfer()`, line 428 reads `tokensForLiquidity = tokensForLiquidity.add(fees.mul(sellLiquidityFee).div(sellTotalFees))` — `fees.mul(3).div(12)` truncates to `0` when `fees < 4`. As a result, even when sells occur, `tokensForLiquidity` does not increase (accumulation drop-out). A textbook Div In Path pattern.

### Annotation Plan

**Contraction/input**: `evaluation/RQ1/cases/div_in_path/WANGMI_input.json` (contract WANGMI, _transfer override)

**Dependencies**: IUniswapV2Router02, ERC20, Ownable, Context (OpenZeppelin style)

**Debug annotations (line 384, start of _transfer)**:
- `// @LocalVar _from = symbolicAddress 1`
- `// @LocalVar to = symbolicAddress 2`
- `// @LocalVar amount = [33, 33]` — small quantity to demonstrate truncation against sellTotalFees=12
- `// @StateVar uniswapV2Pair = symbolicAddress 2` — to == pair, so the sell branch is taken
- `// @StateVar sellLiquidityFee = [3, 3]`, `sellTxFee = [9, 9]` → sellTotalFees = 12
- `// @StateVar tokensForLiquidity = [100, 100]` (initial value)
- (Additional env settings: isLaunched=true, maxTx/Wallet pass-through, isExcludedFromFees=false, etc.)

Intermediate computation: `fees = 33 * 12 / 100 = 3`, `fees.mul(3).div(12) = 3*3/12 = 0` → tokensForLiquidity += 0 → no increase.

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| During | 428 | tokensForLiquidity(Before < After) | violated | When a sell occurs the fee should accumulate, but truncation makes Before == After → violated |

**Rationale**: One of the 7 cases for paper §6.2 Guideline 3 (multi-step arithmetic). `fees * sellLiquidityFee / sellTotalFees` has a boundary where truncation always makes sell-fee accumulation 0. Captured directly via Before/After directionality.

---

## numscout_Nokon

- **Contract**: Nokon
- **Function**: buy
- **Bug line (original)**: 51
- **Pattern**: exchange_problem
- **Status**: `annotated`

### Bug Description
`buy()` line 51: `uint256 amountToBuy = msg.value / ethRateFix * calculateRate()` — division-first followed by multiplication, so when `msg.value < ethRateFix`, `msg.value / ethRateFix = 0` truncates and the result is `amountToBuy = 0`. An exchange_problem pattern in which the user pays ETH but receives no tokens.

### Annotation Plan

**Contraction/input**: `evaluation/RQ1/cases/exchange_problem/Nokon_input.json`

**Dependencies**: None (only `using SafeMath`; calculateRate is an internal function)

**Debug annotations (line 49, start of buy)**:
- `// @GlobalVar msg.value = [50000000000500000, 50000000000500000]` — 0.05 ETH plus a small amount (greater than ethRateFix = 10000000000)
- `// @StateVar presell = true`
- `// @StateVar balances[address(this)] = [2000000000000, 2000000000000]` — sufficient dex holdings

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| During | 51 | amountToBuy * ethRateFix >= msg.value * 250000 | violated | A rearrangement of the ideal mul-first formula `msg.value * rate / ethRateFix`. Lower bound based on calculateRate's minimum 250000. Buggy code uses division-first and truncates → violated |

**Rationale**: paper §6.2 Guideline 3 (multi-step arithmetic). A textbook pattern where division-first yields a different result than the intended `msg.value × rate / ethRateFix`. Compared against the ideal multiplication-first formula to expose the precision gap.

---

## flyinointment_SwordCrowdsale

- **Source**: Fly-in-the-Ointment (Greedy Contract dataset, paper §4.2 Dataset Collection, Table 1)
- **Contract**: SwordCrowdsale
- **Function**: refundMoney
- **Bug line (original)**: 77-79 (the `bug_line=33` in dataset.csv refers to the contraction)
- **Pattern**: greedy_contract
- **Status**: `annotated`

### Bug Description
`refundMoney()` refunds ETH to a contributor but does not decrement `weiRaised`. It only updates `contributorList[_address].contributionAmount = 0` and `.tokensIssued = 0`; `weiRaised -= amount` is missing. When `forwardAllRaisedFunds()` is called, the `wallet.transfer(weiRaised)` line attempts to send more ETH than the actual balance → permanent revert, funds permanently locked in the contract (Greedy Contract).

### Annotation Plan

**Contraction/input**: `evaluation/RQ1/cases/greedy_contract/SwordCrowdsale_input.json`

**Dependencies**: Ownable, Context (uses onlyOwner modifier)

**Debug annotations (line 76, start of refundMoney)**:
- `// @StateVar contributorList[_address].contributionAmount = [100, 100]` — refund amount
- `// @StateVar weiRaised = [1000, 1000]` — initial cumulative raised amount
- owner/msg.sender setup is to pass the onlyOwner modifier

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| Post | 81 (just after refundMoney returns) | weiRaised(Entry > Exit) | violated | On a successful refund, the cumulative raised amount must decrease. Buggy: Entry=1000, Exit=1000 → `Entry > Exit` false → violated |

**Rationale**: Paper Tab 1 NumScout(7) + Flyinointment(1) + Web3Bugs(81) = 89 dataset composition; the only Flyinointment-origin case. Representative application of paper §6.2 Guideline 1 (directional annotation via Entry/Exit) — the natural directional intent that `weiRaised` must decrease after a refund.

---

## numscout_BoostToken_operator

- **Contract**: BoostToken
- **Function**: sendETHToTeam
- **Bug lines (original)**: 141; 142
- **Pattern**: operator_order_issue
- **Status**: `annotated`

### Bug Description
Two lines inside `sendETHToTeam(uint256 amount)`:
- Line 141: `_marketingWalletAddress.transfer(amount.div(12).mul(5))` — `amount / 12 * 5`, division-first. The intent is 5/12 of amount.
- Line 142: `_dipWalletAddress.transfer(amount.div(9).mul(2))` — `amount / 9 * 2`, division-first. The intent is 2/9 of amount.

In both cases, when `amount < 12` (or `< 9`), `amount.div(k) = 0` → truncation → transfer amount is 0. Operator order issue: the correct order is `amount * 5 / 12` (mul-first).

### Annotation Plan

**Contraction/input**: `evaluation/RQ1/cases/operator_order_issue/BoostToken_input.json`

**Dependencies**: Ownable, Context, SafeMath, Address (OpenZeppelin)

**Debug annotations (line 140, start of sendETHToTeam)**:
- `// @LocalVar amount = [68, 68]` — within the 68 < 12 * 9 = 108 range, demonstrates that `68/12*5 = 5*5 = 25` is less than `68*5/12 = 28`

### Intent Annotations
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| During | 141 | transfer.arg[0] >= amount * 5 / 12 | violated | The marketing wallet transfer amount must be at least the mul-first lower bound. Buggy: 5*5=25 < 68*5/12=28 → violated |
| During | 142 | transfer.arg[0] >= amount * 2 / 9 | violated | The dip wallet transfer amount must be at least the mul-first lower bound. Buggy: 7*2=14 < 68*2/9=15 → violated |

**Rationale**: Representative case for paper §6.2 Guideline 3 (multi-step arithmetic, 7 of 20). Specialized @During using the function-arg form (`func.arg[N] relOp expr`).

---

## web3bugs_8_H_03

- **Contract**: NFTXVaultUpgradeable
- **Function**: getRandomTokenIdFromFund
- **Bug line (original)**: 414
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L3: unsupported-construct-top)`

### Bug Description
`getRandomTokenIdFromFund()` does not consider the ERC1155 `quantity1155` when picking randomly. That is, ERC1155 slots with quantity > 1 are sampled with the same single probability, miscomputing the weight (reports/8.md H-03).
- Report: submission `code-423n4/2021-05-nftx-findings/issues/56`

### Reason Not Detectable (L3: unsupported-construct-top)
- The random value is computed as `keccak256(abi.encodePacked(block.timestamp, block.difficulty, ...)) % holdings.length`
- The abstract interpreter treats `keccak256` as an opaque builtin → the result propagates as TOP
- The "skew of the probability distribution" the bug check depends on is not a value-level invariant — under a TOP state, buggy/correct yield the same result (both TOP)
- The ERC1155 probability weight can only be proved via a counting argument → not distinguishable in the interval domain of intent annotations → L3

---

## web3bugs_35_H_11

- **Contract**: Ticks (library)
- **Function**: cross
- **Bug lines (original)**: 40, 49
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L5b: wrong-code)`

### Bug Description
In `Ticks.cross()`, the mapping between swap direction and the field to update is inverted (reports/35.md H-11):
- `zeroForOne == true` (token0 → token1 swap, pool tick decreases): the buggy code updates `feeGrowthOutside0`, but `token1 fees outside` should be updated
- `zeroForOne == false`: symmetrically, `feeGrowthOutside0` is updated instead of `feeGrowthOutside1`
- In other words, `0` and `1` should be swapped

### Reason Not Detectable (L5b: wrong-code)
- Struct field access and state array writes are both supported, so this is not L1/L2/L3
- The correct annotation is `@Post changed(ticks[nextTickToCross].feeGrowthOutside1, true)` (zeroForOne branch basis, see l4_l5 csv annotation_text)
- This annotation presupposes **field-direction knowledge** ("zeroForOne → update outside1") — only writable if the developer already knows the correct direction → bug awareness → L5b
- annotation_tier: weak (directional, included in paper §6.2 Guideline 1 "7 of 14 L5 expressible")

### Intent Annotation (from l4_l5 csv)
| Type | Expression | Expected | Rationale |
|------|------------|----------|-----------|
| Post | changed(ticks[nextTickToCross].feeGrowthOutside1, true) | violated | In the zeroForOne branch, outside1 should be updated, but the buggy code updates only outside0 → unchanged → violated |

---

## web3bugs_52_H_15

- **Contract**: VaderRouter
- **Function**: _swap
- **Bug line (original)**: 326
- **Pattern**: erroneous_accounting
- **Status**: `not_detectable (L4b: wrong-code — router wrapper)`

### Bug Description
In the 3-path hop of `VaderRouter._swap()`, the reserve argument order between pools is swapped (reports/52.md H-15):
- Intended: foreign → native (pool0) → different foreign (pool1)
- Buggy: in the first hop, the native amount condition check operates on the foreign basis → `require(nativeAmountIn == amountIn <= nativeBalance - nativeReserve == 0)` reverts
- Report: `code-423n4/2021-11-vader-findings/issues/161` (sponsor confirmed)

### Reason Not Detectable (L4b: wrong-code)
- **L4b classification rationale** (l4_l5_classification.csv: `original_class=L4b, final_class=L4b, reclass_reason=limitation_types_md_self_inconsistent_L4b_list_and_L5b_examples_both_contain_this_case_I9_principle_picks_L4b`)
- VaderRouter is a router wrapper — no state changes, only an external call to `BasePool.swap()`
- `VaderMath.calculateSwap()` is a pure library, but the annotation grammar cannot directly call functions → the correct expected swap result is inexpressible
- All 3 paths revert, so there is no check point where the intent is reached (silent sanction via require)
- I9 principle: arg[N] lint-level (router wrapper, no state) → L4b archetype (52_H_16 twin)

### Intent Annotation (attempt)
| Type | Line | Expression | Expected | Rationale |
|------|------|------------|----------|-----------|
| (cannot attempt) | 326 | (`VaderMath.calculateSwap(...)` function call is outside the annotation grammar) | — | Cannot be written due to router wrapper + external pool call + grammar restrictions |
