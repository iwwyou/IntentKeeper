# H-23: Synth tokens can get over-minted

**Contest**: 52
**Reference**: https://code4rena.com/reports/2021-11-vader#h-23-synth-tokens-can-get-over-minted

## Bug Report

## [[H-23] `Synth` tokens can get over-minted](https://github.com/code-423n4/2021-11-vader-findings/issues/210)
_Submitted by WatchPug_

Per the document:

> It also is capable of using liquidity units as collateral for synthetic assets, of which it will always have guaranteed redemption liquidity for.

However, in the current implementation, `Synth` tokens are minted based on the calculation result. While `nativeDeposit` be added to the reserve, `reserveForeign` will remain unchanged, not deducted nor locked.

Making it possible for `Synth` tokens to get over-minted.

####
