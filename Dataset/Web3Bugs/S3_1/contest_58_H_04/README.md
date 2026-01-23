# H-04: AaveVault does not update TVL on deposit/withdraw

**Contest**: 58
**Reference**: https://code4rena.com/reports/2021-12-mellow#h-04-aavevault-does-not-update-tvl-on-depositwithdraw

## Bug Report

## [[H-04] AaveVault does not update TVL on deposit/withdraw](https://github.com/code-423n4/2021-12-mellow-findings/issues/41)
_Submitted by cmichel, also found by WatchPug_

Aave uses **rebasing** tokens which means the token balance `aToken.balanceOf(this)` increases over time with the accrued interest.

The `AaveVault.tvl` uses a cached value that needs to be updated using a `updateTvls` call.

This call is not done when depositing tokens which allows an attacker to deposit tokens, get a fair share *of the old tvl*, update the tvl to include the interest, and then withdraw the LP tokens receiving a larger share of the *new tvl*, receiving back their initial deposit + the share of the interest.
This can be done risk-free in a single transaction.

###
