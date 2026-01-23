# H-02: Wrong token allocation computation for token decimals != 18 if floor price not reached

**Contest**: 79
**Reference**: https://code4rena.com/reports/2022-01-trader-joe#h-02-wrong-token-allocation-computation-for-token-decimals--18-if-floor-price-not-reached

## Bug Report

## [[H-02] Wrong token allocation computation for token decimals != 18 if floor price not reached](https://github.com/code-423n4/2022-01-trader-joe-findings/issues/193)
_Submitted by cmichel_

In `LaunchEvent.createPair`, when the floor price is not reached (`floorPrice > wavaxReserve * 1e18 / tokenAllocated`), the tokens to be sent to the pool are lowered to match the raised WAVAX at the floor price.

Note that the `floorPrice` is supposed to have a precision of 18:

> /// @param \_floorPrice Price of each token in AVAX, scaled to 1e18

The `floorPrice > (wavaxReserve * 1e18) / tokenAllocated` check is correct but the `tokenAllocated` computation involves the `token` decimals:

```solidity
// @audit should be wavaxReserve * 1e18 / floorPrice
tokenAllocated = (wavaxReserve * 10**token.decimals()) / floorPrice;
```

This computation does not work for `token`s that don't have 18 decimals.

###
