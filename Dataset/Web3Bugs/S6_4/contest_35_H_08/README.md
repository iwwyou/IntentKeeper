# H-08: Wrong inequality when adding/removing liquidity in current price range

**Contest**: 35
**Reference**: https://code4rena.com/reports/2021-09-sushitrident-2#h-08-wrong-inequality-when-addingremoving-liquidity-in-current-price-range

## Bug Report

## [[H-08] Wrong inequality when adding/removing liquidity in current price range](https://github.com/code-423n4/2021-09-sushitrident-2-findings/issues/34)
_Submitted by cmichel_

The `ConcentratedLiquidityPool.mint/burn` functions add/remove `liquidity` when `(priceLower < currentPrice && currentPrice < priceUpper)`.
Shouldn't it also be changed if `priceLower == currentPrice`?

###
