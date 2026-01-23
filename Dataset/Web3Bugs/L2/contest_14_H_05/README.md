# H-05: IdleYieldSource doesn’t use mantissa calculations

**Contest**: 14
**Reference**: https://code4rena.com/reports/2021-06-pooltogether#h-05-idleyieldsource-doesnt-use-mantissa-calculations

## Bug Report

## [[H-05] `IdleYieldSource` doesn't use mantissa calculations](https://github.com/code-423n4/2021-06-pooltogether-findings/issues/103)
_Submitted by tensors_

Because mantissa calculations are not used in this case to account for decimals, the arithmetic can zero out the number of shares or tokens that should be given.

For example, say I deposit 1 token, expecting 1 share in return. On [L95](https://github.com/sunnyRK/IdleYieldSource-PoolTogether/blob/6dcc419e881a4f0f205c07c58f4db87520b6046d/contracts/IdleYieldSource.sol#L95), if the `totalUnderlyingAssets` is increased to be larger than the number of total shares, then the division would output 0 and I wouldn't get any shares.

Recommend  implementing mantissa calculations like in the contract for the AAVE  yield.

**[PierrickGT (PoolTogether) confirmed and patched](https://github.com/code-423n4/2021-06-pooltogether-findings/issues/103#issuecomment-873072563):**
 > PR: https://github.com/pooltogether/idle-yield-source/pull/5


