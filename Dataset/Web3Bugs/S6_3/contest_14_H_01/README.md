# H-01: User could lose underlying tokens when redeeming from the IdleYieldSource

**Contest**: 14
**Reference**: https://code4rena.com/reports/2021-06-pooltogether#h-01-user-could-lose-underlying-tokens-when-redeeming-from-the-idleyieldsource

## Bug Report

## [[H-01] User could lose underlying tokens when redeeming from the `IdleYieldSource`](https://github.com/code-423n4/2021-06-pooltogether-findings/issues/120)
_Submitted by shw_

The `redeemToken` function in `IdleYieldSource` uses `redeemedShare` instead of `redeemAmount` as the input parameter when calling `redeemIdleToken` of the Idle yield source. As a result, users could get fewer underlying tokens than they should.

When burning users' shares, it is correct to use `redeemedShare` (line 130). However, when redeeming underlying tokens from Idle Finance, `redeemAmount` should be used instead of `redeemedShare` (line 131). Usually, the `tokenPriceWithFee()` is greater than `ONE_IDLE_TOKEN`, and thus `redeemedShare` is less than `redeemAmount`, causing users to get fewer underlying tokens than expected.

Recommend changing `redeemedShare` to `redeemAmount` at line [L131](https://github.com/code-423n4/2021-06-pooltogether/blob/main/contracts/yield-source/IdleYieldSource.sol#L129-L131).

**[PierrickGT (PoolTogether) confirmed and patched](https://github.com/code-423n4/2021-06-pooltogether-findings/issues/120#issuecomment-871284667):**
 > PR: https://github.com/pooltogether/idle-yield-source/pull/4


