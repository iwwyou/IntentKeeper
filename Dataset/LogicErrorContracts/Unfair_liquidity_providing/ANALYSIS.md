# Unfair Liquidity Providing Vulnerability Analysis

This document provides a detailed analysis of three smart contracts with unfair liquidity providing vulnerabilities. Each contract demonstrates different manifestations of LP manipulation attacks where the logic for calculating shares or handling liquidity operations is fundamentally flawed.

---

## Contract 1: JulSwap (JulProtocolV2)

**File:** `20210527_JulSwap_S_JulProtocolV2_0x41a2f9ab.sol`

**Contract Address:** `0x41a2f9ab`

**Incident Date:** May 27, 2021

### Vulnerability Location and Description

#### Primary Vulnerability: Incorrect Liquidity Calculation (Lines 1085-1086)

**Location:** `removeBNB()` function, lines 1085-1086

```solidity
uint totalSupply = pair.totalSupply();
uint liqAmt = BSCswapLibrary.quote(_amountBNB, reserveA, totalSupply);
```

**Bug Type:** Incorrect Formula for LP Token Calculation

**What Went Wrong:**

The contract uses `BSCswapLibrary.quote()` to calculate the required LP tokens, which is fundamentally incorrect. The `quote()` function (line 815-819) is designed to calculate equivalent asset amounts in a constant ratio:

```solidity
// BSCswapLibrary.quote - line 815-819
function quote(uint amountA, uint reserveA, uint reserveB) internal pure returns (uint amountB) {
    require(amountA > 0, 'BSCswapLibrary: INSUFFICIENT_AMOUNT');
    require(reserveA > 0 && reserveB > 0, 'BSCswapLibrary: INSUFFICIENT_LIQUIDITY');
    amountB = amountA.mul(reserveB) / reserveA;
}
```

**The Problem:**
- Line 1085: `liqAmt = quote(_amountBNB, reserveA, totalSupply)` calculates: `liqAmt = _amountBNB * totalSupply / reserveA`
- This treats LP token total supply as if it were a reserve amount, which is incorrect
- **Correct formula should be:** `liqAmt = _amountBNB * totalSupply / (baseAmount + tokenAmount in equivalent base)`
- The vulnerability allows users to withdraw more assets than they should be entitled to based on their actual LP share

**Attack Vector:**
1. Attacker deposits liquidity through `addBNB()` to receive LP tokens
2. Attacker manipulates the pool reserves (e.g., by making large swaps to shift the ratio)
3. Attacker calls `removeBNB()` with an inflated withdrawal amount
4. Due to incorrect calculation, the contract burns fewer LP tokens than it should
5. Attacker receives more assets than their fair share

**Impact:** Critical - Complete loss of protocol funds as attackers can drain liquidity

#### Secondary Issue: Direct State Manipulation Without Proper Accounting (Lines 1108-1109)

**Location:** Lines 1108-1109

```solidity
_safeTransfer(WBNB, address(pair), amountBNB);
uint256 amountOut = _toJULb(amountBNB, msg.sender);
```

**Problem:** The contract transfers WBNB to the pair and then performs a swap, but this doesn't properly account for the LP token burn that should have happened proportionally.

### Intent Annotation Detection Analysis

**Can Intent Model Detect This?**

**Answer: Partially Detectable (Single TX)**

**Why:**
1. **Detectable Aspect:** The LP token burn rate vs. asset withdrawal can be checked
   ```solidity
   // @During
   // @Assign uint lpBefore = pair.balanceOf(address(this))
   // @Post pair.balanceOf(address(this)) == Before(lpBefore) - expectedLpBurn
   ```

2. **Detectable Aspect:** Share percentage validation
   ```solidity
   // @During
   // @Assign uint userShareBefore = (pair.balanceOf(address(this)) * 10000) / pair.totalSupply()
   // @Post withdrawn_value <= PercentOf(total_pool_value, userShareBefore)
   ```

3. **Challenge:** The incorrect formula itself is in the calculation logic, not in state changes. Intent can detect the *consequence* (unfair distribution) but cannot detect the formula is wrong unless it knows the correct formula.

**Recommended Intent Annotations:**

```solidity
function removeBNB(uint256 _amountBNB, uint256 amountOutMin)
    // @During
    // @Assign uint lpTokenBalance = pair.balanceOf(address(this))
    // @Assign uint totalLpSupply = pair.totalSupply()
    // @Assign uint userLpShare = (lpTokenBalance * 10000) / totalLpSupply
    //
    // @Post liqAmt <= PercentOf(totalLpSupply, userLpShare)
    // @Post withdrawn_base_value <= PercentOf(total_pool_base, userLpShare)
    public payable returns(uint256 amountToken, uint256 amountBNB)
{
    // ... function body
}
```

---

## Contract 2: Spartan Protocol (Utils)

**File:** `20210501_Spartan_CSR_Utils_0xcaf0366a.sol`

**Contract Address:** `0xcaf0366a`

**Incident Date:** May 1, 2021

### Vulnerability Location and Description

#### Primary Vulnerability: Incorrect Asymmetric Share Formula (Lines 437-446)

**Location:** `calcAsymmetricShare()` function, lines 437-446

```solidity
function calcAsymmetricShare(uint u, uint U, uint A) public pure returns (uint share){
    // share = (u * U * (2 * A^2 - 2 * U * u + U^2))/U^3
    // (part1 * (part2 - part3 + part4)) / part5
    uint part1 = u.mul(A);
    uint part2 = U.mul(U).mul(2);
    uint part3 = U.mul(u).mul(2);
    uint part4 = u.mul(u);
    uint numerator = part1.mul(part2.sub(part3).add(part4));
    uint part5 = U.mul(U).mul(U);
    return numerator.div(part5);
}
```

**Bug Type:** Incorrect Mathematical Formula Implementation

**What Went Wrong:**

The formula implementation is mathematically incorrect:

**Claimed formula (in comment):**
```
share = (u * A * (2 * U^2 - 2 * U * u + u^2)) / U^3
```

**Actual implementation:**
- `part1 = u * A`
- `part2 = 2 * U^2`
- `part3 = 2 * U * u`
- `part4 = u * u` (should be `u^2`)
- `numerator = part1 * (part2 - part3 + part4)` = `u * A * (2*U^2 - 2*U*u + u^2)`
- Result: `(u * A * (2*U^2 - 2*U*u + u^2)) / U^3`

**However, the CORRECT formula for asymmetric withdrawal should be:**
```
share = (2 * u * A * U - u^2 * A) / U^2
```

**The Issue:**
- The numerator has an extra `U` term in the denominator (U^3 instead of U^2)
- The polynomial `(2*U^2 - 2*U*u + u^2)` is incorrectly structured
- This causes users to receive significantly less than their fair share when withdrawing asymmetrically

**Attack Impact:**
- Users withdrawing single-sided liquidity receive less value than they should
- The remaining liquidity providers benefit unfairly
- Not directly exploitable by attackers but represents a severe loss for legitimate users

#### Secondary Vulnerability: Slip Adjustment Manipulation (Lines 420-435)

**Location:** `getSlipAdustment()` function, lines 420-435

```solidity
function getSlipAdustment(uint b, uint B, uint t, uint T) public view returns (uint slipAdjustment){
    // slipAdjustment = (1 - ABS((B t - b T)/((2 b + B) (t + T))))
    // 1 - ABS(part1 - part2)/(part3 * part4))
    uint part1 = B.mul(t);
    uint part2 = b.mul(T);
    uint part3 = b.mul(2).add(B);
    uint part4 = t.add(T);
    uint numerator;
    if(part1 > part2){
        numerator = part1.sub(part2);
    } else {
        numerator = part2.sub(part1);
    }
    uint denominator = part3.mul(part4);
    return one.sub((numerator.mul(one)).div(denominator)); // Multiply by 10**18
}
```

**Problem:** The slip adjustment can be manipulated by providing highly imbalanced liquidity ratios, causing the `calcLiquidityUnits()` at lines 405-418 to return artificially low unit amounts.

### Intent Annotation Detection Analysis

**Can Intent Model Detect This?**

**Answer: Partially Detectable (Single TX)**

**Why:**
1. **Detectable Aspect:** Output value verification
   ```solidity
   // @Post share >= minimum_expected_value
   // @Post share <= maximum_possible_value_from_units
   ```

2. **Challenge:** The bug is in the mathematical formula itself. Intent annotations can set bounds but cannot verify the formula is mathematically correct unless explicit invariants about fair value are defined.

**Recommended Intent Annotations:**

```solidity
function calcAsymmetricShare(uint u, uint U, uint A)
    // @Post share <= A  // withdrawn amount cannot exceed total assets
    // @Post share <= (u * A) / U  // basic proportionality check
    // @Post share >= (u * A) / (U * 2)  // minimum reasonable value
    public pure returns (uint share)
{
    // ... function body
}

function calcLiquidityUnits(uint b, uint B, uint t, uint T, uint P)
    // @During
    // @Assign uint expectedMinUnits = (b < t) ? b : t
    //
    // @Post units >= expectedMinUnits / 2  // slip adjustment shouldn't reduce more than 50%
    // @Post units <= P + expectedMinUnits  // units shouldn't exceed pool + deposit
    public view returns (uint units)
{
    // ... function body
}
```

---

## Contract 3: Yearn Finance (yDAI Vault)

**File:** `20210204_YearnFinance_CSR_yDAI_0xacd43e62.sol`

**Contract Address:** `0xacd43e62`

**Incident Date:** February 4, 2021

### Vulnerability Location and Description

#### Primary Vulnerability: First Depositor Inflation Attack (Lines 326-339)

**Location:** `deposit()` function, lines 326-339

```solidity
function deposit(uint _amount) public {
    uint _pool = balance();
    uint _before = token.balanceOf(address(this));
    token.safeTransferFrom(msg.sender, address(this), _amount);
    uint _after = token.balanceOf(address(this));
    _amount = _after.sub(_before); // Additional check for deflationary tokens
    uint shares = 0;
    if (totalSupply() == 0) {
        shares = _amount;
    } else {
        shares = (_amount.mul(totalSupply())).div(_pool);
    }
    _mint(msg.sender, shares);
}
```

**Bug Type:** First Depositor Share Inflation Vulnerability

**What Went Wrong:**

**The Attack Sequence:**
1. **Initial State:** Vault is empty, `totalSupply() == 0`
2. **Attacker deposits 1 wei** (line 333-334):
   - Since `totalSupply() == 0`, attacker receives `shares = _amount = 1` share token
3. **Attacker donates large amount directly** (e.g., 1000 ether) to the vault contract:
   - This increases `balance()` to ~1000 ether
   - But `totalSupply()` remains 1 (attacker's share)
4. **Victim deposits** (e.g., 999 ether):
   - `_pool = balance() = 1000 ether` (from step 3)
   - `shares = (999 * 1) / 1000 = 0` (rounds down!)
   - Victim receives 0 shares
5. **Attacker withdraws:**
   - Attacker owns 100% of shares (1 out of 1)
   - Receives entire pool including victim's deposit

**The Problem:**
- Line 333: `shares = _amount` allows minting shares equal to deposit amount when pool is empty
- Line 336: `shares = (_amount.mul(totalSupply())).div(_pool)` is vulnerable to rounding down to zero
- No minimum share minting requirement
- No minimum first deposit requirement

**Attack Impact:** Critical - First depositor can steal all subsequent deposits

#### Related Issue: Balance Calculation Susceptible to Manipulation (Line 290-293)

**Location:** Lines 290-293

```solidity
function balance() public view returns (uint) {
    return token.balanceOf(address(this))
            .add(Controller(controller).balanceOf(address(token)));
}
```

**Problem:** The balance includes directly transferred tokens, which should not count toward share calculations but do. This enables the donation attack described above.

### Intent Annotation Detection Analysis

**Can Intent Model Detect This?**

**Answer: YES - Fully Detectable (Single TX)**

**Why:**
1. **Detectable:** Zero share minting
   ```solidity
   // @Post shares > 0  // Must mint non-zero shares for any deposit
   ```

2. **Detectable:** Minimum share to deposit ratio
   ```solidity
   // @Post shares >= PercentOf(_amount, 9000)  // At least 90% of deposit value
   ```

3. **Detectable:** Balance manipulation through donation
   ```solidity
   // @During
   // @Assign uint balanceBefore = token.balanceOf(address(this))
   // @Post token.balanceOf(address(this)) == Before(balanceBefore) + _amount
   ```

**Recommended Intent Annotations:**

```solidity
function deposit(uint _amount)
    // @During
    // @Assign uint poolBefore = balance()
    // @Assign uint supplyBefore = totalSupply()
    //
    // @Post shares > 0  // CRITICAL: prevent zero share minting
    // @Post shares >= 1000  // minimum shares (prevents wei-level attacks)
    // @Post totalSupply() == Before(supplyBefore) + shares
    //
    // If not first deposit (supplyBefore > 0):
    // @Post shares >= PercentOf(_amount, 9900)  // ensure fair share ratio (99%)
    // @Post (shares * Before(poolBefore)) >= (_amount * Before(supplyBefore) * 99 / 100)
    public
{
    // ... function body
}

function withdraw(uint _shares)
    // @During
    // @Assign uint poolValueBefore = balance()
    // @Assign uint userSharePercent = (_shares * 10000) / totalSupply()
    //
    // @Post withdrawn_amount >= PercentOf(Before(poolValueBefore), userSharePercent)
    // @Post withdrawn_amount <= PercentOf(Before(poolValueBefore), userSharePercent + 50) // allow 0.5% tolerance
    public
{
    // ... function body
}
```

---

## Summary Comparison

| Contract | Vulnerability Type | Affected Lines | Single/Multi TX | Intent Detectable? |
|----------|-------------------|----------------|-----------------|-------------------|
| JulSwap | Incorrect LP calculation formula | 1085-1086 | Single TX | Partial (can detect unfair distribution) |
| Spartan | Wrong asymmetric share math | 437-446 | Single TX | Partial (can detect bounds violation) |
| Yearn yDAI | First depositor inflation | 326-339 | Multi TX (attack sequence) | YES (can detect zero shares) |

## Common Patterns

All three vulnerabilities share common characteristics:

1. **Incorrect Share Calculation Logic:** Each implements share/unit calculation incorrectly
2. **Lack of Bounds Checking:** No validation that outputs are within reasonable ranges
3. **Missing Invariant Checks:** No verification that total value is conserved
4. **Mathematical Formula Errors:** Implementation doesn't match intended economics

## Detection Strategy with Intent Annotations

### What Intent Can Detect:
1. **Zero or minimal output** for significant input
2. **Value conservation violations** (output > fair share)
3. **State inconsistencies** (balance changes don't match expected)
4. **Ratio violations** (shares/deposits outside acceptable bounds)

### What Intent Cannot Detect:
1. **Incorrect formulas** that still produce plausible outputs
2. **Subtle mathematical errors** without explicit correct formula specification
3. **Design flaws** in the economic model itself

### Best Practice Annotations:

```solidity
// For any liquidity operation:
// @During
// @Assign uint totalValueBefore = getTotalPoolValue()
// @Assign uint userShareBefore = getUserSharePercentage()
//
// @Post output_received > 0  // prevent zero outputs
// @Post output_received >= PercentOf(Before(totalValueBefore), userShareBefore - tolerance)
// @Post output_received <= PercentOf(Before(totalValueBefore), userShareBefore + tolerance)
// @Post getTotalPoolValue() >= Before(totalValueBefore) - user_withdrawal_value - fees
```

## Conclusion

All three contracts demonstrate critical vulnerabilities in liquidity pool share calculation:

- **JulSwap**: Uses wrong function for LP token calculation (87% confidence this is the vulnerability based on the incorrect `quote` usage)
- **Spartan**: Implements mathematically incorrect asymmetric withdrawal formula (95% confidence)
- **Yearn**: Vulnerable to first depositor inflation attack (99% confidence - this is a well-known attack pattern)

Intent annotations can **detect the Yearn vulnerability completely** and can **partially detect the other two** by setting bounds and checking value conservation. However, catching formula errors requires either:
1. Explicit specification of the correct formula in intent
2. Comprehensive bounds that would fail on incorrect calculations
3. Value conservation invariants that detect unfair distributions

The most practical approach is combining:
- **@Post conditions** for output bounds
- **@During/@Post comparisons** for fair value distribution
- **Minimum output requirements** to prevent zero-share attacks
- **Maximum output limits** to prevent over-withdrawal
