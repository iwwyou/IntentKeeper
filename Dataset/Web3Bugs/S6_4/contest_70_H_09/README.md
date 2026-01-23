# H-09: USDV.sol Mint and Burn Amounts Are Incorrect

**Contest**: 70
**Reference**: https://code4rena.com/reports/2021-12-vader#h-09-usdvsol-mint-and-burn-amounts-are-incorrect

## Bug Report

## [[H-09] `USDV.sol` Mint and Burn Amounts Are Incorrect](https://github.com/code-423n4/2021-12-vader-findings/issues/164)
_Submitted by leastwood, also found by TomFrenchBlockchain_

The `USDV.mint` function queries the price of `Vader` from the `LiquidityBasedTwap` contract. The calculation to determine `uAmount` in `mint` is actually performed incorrectly. `uAmount = (vPrice * vAmount) / 1e18;` will return the `USD` amount for the provided `Vader` as `vPrice` is denominated in `USD/Vader`. This `uAmount` is subsequently used when minting tokens for the user (locked for a period of time) and fee to the contract owner.

This same issue also applies to how `vAmount = (uPrice * uAmount) / 1e18;` is calculated in `USDV.burn`.

This is a severe issue, as the `mint` and `burn` functions will always use an incorrect amount of tokens, leading to certain loss by either the protocol (if the user profits) or the user (if the user does not profit).

###
