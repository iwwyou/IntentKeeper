# Other Coding Mistakes Analysis

## Summary

| Contract | Bug Type | Location | Intent Model Mapping |
|----------|----------|----------|---------------------|
| Anyswap V4 Router (0xd1c5966f) | Missing Return Value Check | Line 324-325 in `anySwapFeeTo()` | Partially detectable with @Post annotation (balance checks) |
| Compound Comptroller (0x374abb8c) | Incorrect Return Value Usage | Line 4626 in `claimComp()` | Detectable with @Post annotation (balance invariant) |
| Anyswap V4 Router (0x6b7a8789) | Missing Return Value Check | Line 332-333 in `anySwapFeeTo()` | Partially detectable with @Post annotation (balance checks) |

---

## 1. Anyswap V4 Router (July 10, 2021 - 0xd1c5966f)

**File**: `20210710_Anyswap_SR_AnyswapV4Router_0xd1c5966f.sol`

**Bug Location**: Lines 322-326 in `anySwapFeeTo()` function

```solidity
// extracts mpc fee from bridge fees
function anySwapFeeTo(address token, uint amount) external onlyMPC {
    address _mpc = mpc();
    AnyswapV1ERC20(token).mint(_mpc, amount);
    AnyswapV1ERC20(token).withdrawVault(_mpc, amount, _mpc);  // Line 325 - Missing return value check
}
```

**Problem**: The function calls `withdrawVault()` which returns a `uint` value (likely the actual withdrawn amount), but the return value is completely ignored. According to the AnyswapV1ERC20 interface (line 151), `withdrawVault()` returns a uint:

```solidity
function withdrawVault(address from, uint amount, address to) external returns (uint);
```

This can lead to:
1. Silent failures where the withdrawal doesn't transfer the expected amount
2. Loss of tracking of actual vs intended withdrawal amounts
3. Potential for vault manipulation if the return value indicates partial withdrawals

**Root Cause**: Developer mistake - not checking external call return values. This is especially dangerous for cross-chain bridge operations where funds could be locked or lost.

**Intent Annotation** (Partially Detectable):
```solidity
/// @Post IERC20(AnyswapV1ERC20(token).underlying()).balanceOf(_mpc) >= old(IERC20(AnyswapV1ERC20(token).underlying()).balanceOf(_mpc)) + amount
function anySwapFeeTo(address token, uint amount) external onlyMPC {
    address _mpc = mpc();
    AnyswapV1ERC20(token).mint(_mpc, amount);
    AnyswapV1ERC20(token).withdrawVault(_mpc, amount, _mpc);
}
```

**Detectability**: Partially detectable. A @Post annotation can verify the balance increase, but cannot directly detect the ignored return value. Static analysis would be needed to flag unchecked return values.

---

## 2. Compound Comptroller (September 29, 2021 - 0x374abb8c)

**File**: `20210929_Compound_CSR_Comptroller_0x374abb8c.sol`

**Bug Location**: Lines 4625-4627 in `claimComp()` function, specifically line 4626

```solidity
for (uint j = 0; j < holders.length; j++) {
    compAccrued[holders[j]] = grantCompInternal(holders[j], compAccrued[holders[j]]);
}
```

With the `grantCompInternal` function at lines 4637-4645:

```solidity
/**
 * @notice Transfer COMP to the user
 * @dev Note: If there is not enough COMP, we do not perform the transfer all.
 * @param user The address of the user to transfer COMP to
 * @param amount The amount of COMP to (possibly) transfer
 * @return The amount of COMP which was NOT transferred to the user
 */
function grantCompInternal(address user, uint amount) internal returns (uint) {
    Comp comp = Comp(getCompAddress());
    uint compRemaining = comp.balanceOf(address(this));
    if (amount > 0 && amount <= compRemaining) {
        comp.transfer(user, amount);
        return 0;
    }
    return amount;  // Returns the amount that was NOT transferred
}
```

**Problem**: The logic is fundamentally broken. `grantCompInternal()` returns the amount that was **NOT** transferred (the leftover amount), but line 4626 assigns this return value back to `compAccrued[holders[j]]`. This means:

1. **If transfer succeeds**: Returns 0, so `compAccrued[holders[j]] = 0` (correct - clears the accrued amount)
2. **If transfer fails**: Returns the original amount, so `compAccrued[holders[j]] = amount` (WRONG - this keeps the full amount as "accrued" without actually transferring it)

This creates a critical issue where:
- Users who fail to receive COMP keep their accrued balance
- They can repeatedly call `claimComp()` trying to drain the contract
- When funds become available, these "sticky" accrued balances can be claimed, potentially draining the protocol

**Correct Logic Should Be**: Set `compAccrued[holders[j]] = 0` only when the transfer is successful, or keep the original amount when it fails but with proper state management.

**Root Cause**: Semantic error in handling return values. The function was designed to return "amount left" but the caller treats it incorrectly.

**Intent Annotation** (Detectable):
```solidity
/// @Post compAccrued[holder] == 0 implies IERC20(getCompAddress()).balanceOf(holder) >= old(IERC20(getCompAddress()).balanceOf(holder))
/// @Post compAccrued[holder] > 0 implies IERC20(getCompAddress()).balanceOf(holder) == old(IERC20(getCompAddress()).balanceOf(holder))
function claimComp(address holder) public {
    return claimComp(holder, allMarkets);
}
```

**Detectability**: Highly detectable with Intent annotations. A @Post annotation can verify that if `compAccrued` is cleared (set to 0), the user's balance must have increased. The current buggy code would violate this invariant in edge cases where transfers fail.

---

## 3. Anyswap V4 Router (July 10, 2021 - 0x6b7a8789)

**File**: `20210710_Anyswap_SR_AnyswapV4Router_0x6b7a8789.sol`

**Bug Location**: Lines 330-334 in `anySwapFeeTo()` function

```solidity
// extracts mpc fee from bridge fees
function anySwapFeeTo(address token, uint amount) external onlyMPC {
    address _mpc = mpc();
    AnyswapV1ERC20(token).mint(_mpc, amount);
    AnyswapV1ERC20(token).withdrawVault(_mpc, amount, _mpc);  // Line 333 - Missing return value check
}
```

**Problem**: Identical issue to contract #1. The function calls `withdrawVault()` which returns a `uint` value, but the return value is completely ignored. This is the same vulnerability in a different deployment of the Anyswap router.

According to the AnyswapV1ERC20 interface (line 159), `withdrawVault()` returns a uint:

```solidity
function withdrawVault(address from, uint amount, address to) external returns (uint);
```

This can lead to:
1. Silent failures where the withdrawal doesn't transfer the expected amount
2. Incorrect accounting between wrapped tokens and underlying assets
3. Potential fund loss in cross-chain operations

**Root Cause**: Developer mistake - not checking external call return values in a critical financial operation.

**Intent Annotation** (Partially Detectable):
```solidity
/// @Post IERC20(AnyswapV1ERC20(token).underlying()).balanceOf(_mpc) >= old(IERC20(AnyswapV1ERC20(token).underlying()).balanceOf(_mpc)) + amount
function anySwapFeeTo(address token, uint amount) external onlyMPC {
    address _mpc = mpc();
    AnyswapV1ERC20(token).mint(_mpc, amount);
    AnyswapV1ERC20(token).withdrawVault(_mpc, amount, _mpc);
}
```

**Detectability**: Partially detectable. A @Post annotation can verify the balance increase occurred, but cannot directly detect that a return value was ignored. Static analysis tools would be better suited for flagging unchecked return values.

---

## Key Insights

### Common Patterns

1. **Ignored Return Values**: Two of the three contracts have the same bug - ignoring return values from critical functions. This is a common coding mistake in Solidity where developers call functions that return status/amounts but don't check the results.

2. **Semantic Misuse of Return Values**: The Compound bug shows a more subtle issue - the return value IS used, but it's misunderstood. The function returns "amount NOT transferred" but the code treats it as if it should be stored back as the accrued amount.

### Detection with Intent Annotations

**Fully Detectable (1/3)**:
- Compound Comptroller bug: Can be detected with @Post annotations checking balance invariants against state changes

**Partially Detectable (2/3)**:
- Both Anyswap bugs: @Post annotations can verify the outcome (balance changes) but cannot directly detect that a return value was ignored

**Recommended Approach**:
- Combine Intent annotations with static analysis
- @Post annotations for balance/state invariants
- Static analysis for unchecked return values
- @During annotations could help track intermediate states

### Security Implications

1. **Anyswap Bugs**: Could lead to fund loss in cross-chain bridge operations, affecting user withdrawals
2. **Compound Bug**: Could allow users to repeatedly claim COMP tokens they never received, potentially draining the rewards pool
3. All bugs involve financial operations, making them high-severity

### Prevention

1. Always check return values from external calls
2. Clearly document what return values represent (e.g., "amount transferred" vs "amount NOT transferred")
3. Use Intent annotations to specify post-conditions on balances and state
4. Implement comprehensive unit tests covering failure scenarios
5. Use static analysis tools to flag unchecked return values
