# H-01: Wrong fee calculation after totalSupply was 0

**Contest**: 65
**Reference**: https://code4rena.com/reports/2021-12-defiprotocol#h-01-wrong-fee-calculation-after-totalsupply-was-0

## Bug Report

## [[H-01] Wrong fee calculation after `totalSupply` was 0](https://github.com/code-423n4/2021-12-defiprotocol-findings/issues/58)
_Submitted by kenzo_

`handleFees` does not update `lastFee` if `startSupply == 0`.
This means that wrongly, extra fee tokens would be minted once the basket is resupplied and `handleFees` is called again.

##
