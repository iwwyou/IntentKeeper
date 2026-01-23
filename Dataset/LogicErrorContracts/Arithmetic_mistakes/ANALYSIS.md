# Arithmetic Mistakes Analysis

## Summary

| Contract | Bug Type | Location | Intent Model Mapping |
|----------|----------|----------|---------------------|
| CoverProtocol Blacksmith | memory/storage order | 699-706 | `@During pool(Before == After)` |
| ValueDeFi Formula | precision loss | 934, 460 | `@Post result in [expected-epsilon, expected+epsilon]` |
| MerlinLab PriceCalculator | wrong reserve ratio | 1041-1043 | `@During price(Assign == reserve1/reserve0)` |
| CreamFinance HomoraBank | missing authorization | 1119-1120, 1433 | N/A (access control) |
| pNetwork Proxy | off-chain validation | N/A | N/A (bridge logic) |

---

## 1. CoverProtocol Blacksmith (20201228)

**File**: `20201228_CoverProtocol_CSR__Blacksmith_0xe0b94a7b.sol`

**Bug Location**: Lines 699-706 in `deposit()` function

```solidity
function deposit(address _lpToken, uint256 _amount) external override {
    // ...
    Pool memory pool = pools[_lpToken];  // Line 699: OLD value copied
    // ...
    updatePool(_lpToken);                 // Line 702: storage UPDATED
    // ...
    _claimCoverRewards(pool, miner);      // Line 706: OLD value used!
}
```

**Problem**: Pool is copied to memory BEFORE `updatePool()`, but used AFTER. Rewards calculated with stale `accRewardsPerToken`.

**Correct Pattern** (in `claimRewards()`):
```solidity
function claimRewards(address _lpToken) public override {
    updatePool(_lpToken);                 // First update
    Pool memory pool = pools[_lpToken];   // Then copy
    _claimCoverRewards(pool, miner);      // Use fresh value
}
```

**Intent Annotation**:
```solidity
// @During pool.accRewardsPerToken(Before == After)  // Should be equal after updatePool
```

---

## 2. ValueDeFi ValueLiquidFormula (20210507)

**File**: `20210507_ValueDeFi_SR_ValueLiquidFormula_0x45f24bae.sol`

**Bug Location**: Lines 444-467 `power()` function, used at line 934

```solidity
function power(uint256 _baseN, uint256 _baseD, uint32 _expN, uint32 _expD)
    internal view returns (uint256, uint8)
{
    uint256 base = (_baseN * FIXED_1) / _baseD;  // Precision loss here
    // ...
    uint256 baseLogTimesExp = (baseLog * _expN) / _expD;  // More precision loss
}
```

**Problem**: Weighted AMM calculation `(baseN/baseD)^(expN/expD)` loses precision through multiple integer divisions.

**Intent Annotation**:
```solidity
// @Post result in PercentOf(expectedValue, 99)  // Within 1% of expected
```

---

## 3. MerlinLab MPriceCalculatorBSC (20210526)

**File**: `20210526_MerlinLab_CR_MPriceCalculatorBSC_0xc4543318.sol`

**Bug Location**: Lines 1041-1043 in `_unsafeValueOfAsset()`

```solidity
if (IPancakePair(pair).token0() == pairToken) {
    valueInBNB = reserve0.mul(amount).div(reserve1);  // WRONG!
} else if (IPancakePair(pair).token1() == pairToken) {
    valueInBNB = reserve1.mul(amount).div(reserve0);  // WRONG!
}
```

**Problem**: Reserve ratio is inverted. If pairToken is token0, we should use `reserve0 * amount / reserve1` for the OTHER token's value, not pairToken's.

**Correct Logic**:
```solidity
// If asset is token0 and pairToken is token1:
// valueInPairToken = reserve1 * assetAmount / reserve0
```

**Intent Annotation**:
```solidity
// @During valueInBNB(Assign == reserve_pairToken * amount / reserve_asset)
```

---

## 4. CreamFinance HomoraBankv2 (20210213)

**File**: `20210213_CreamFinance_CSR_HomoraBankv2_0x33bf0bb8.sol`

**Bug Location**: Lines 1119-1120 `inExec` modifier

```solidity
modifier inExec() {
    require(POSITION_ID != _NO_ID, 'not within execution');
    _;  // No check on WHO is calling!
}

function borrow(address token, uint amount) external override inExec poke(token) {
    // Anyone can manipulate debt if POSITION_ID is set
}
```

**Problem**: Missing authorization check. Only verifies execution state, not caller identity. Attacker's contract can call `borrow()` during execution to manipulate debt.

**Note**: This is more of an access control issue than arithmetic, but classified as "arithmetic mistakes" because it enables debt number manipulation.

---

## 5. pNetwork AdminUpgradeabilityProxy (20210919)

**File**: `20210919_pNetwork_CS_AdminUpgradeabilityProxy_0xd61372d1.sol`

**Bug Location**: Off-chain bridge validation logic (not in this contract)

The on-chain token contract appears correct. The exploit was in the **pBTC bridge's off-chain validation** that allowed double-minting.

---

## Intent Model Applicability

| Bug Type | Single TX? | Intent Detectable? |
|----------|------------|-------------------|
| Memory/Storage order | Yes | Partially (state comparison) |
| Precision loss | Yes | Yes (range validation) |
| Wrong calculation | Yes | Yes (formula validation) |
| Missing auth | Yes | No (access control issue) |
| Off-chain logic | No | No |

**3 out of 5** bugs are directly detectable with numeric intent annotations.
