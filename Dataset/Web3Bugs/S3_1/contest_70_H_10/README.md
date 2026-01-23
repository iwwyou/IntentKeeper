# H-10: previousPrices Is Never Updated Upon Syncing Token Price

**Contest**: 70
**Reference**: https://code4rena.com/reports/2021-12-vader#h-10-previousprices-is-never-updated-upon-syncing-token-price

## Bug Report

## [[H-10] `previousPrices` Is Never Updated Upon Syncing Token Price](https://github.com/code-423n4/2021-12-vader-findings/issues/103)
_Submitted by leastwood_

The `LiquidityBasedTWAP` contract attempts to accurately track the price of `VADER` and `USDV` while still being resistant to flash loan manipulation and short-term volatility. The `previousPrices` array is meant to track the last queried price for the two available paths, namely `VADER` and `USDV`.

The `setupVader` function configures the `VADER` token by setting `previousPrices` and adding a token pair. However, `syncVaderPrice` does not update `previousPrices` after syncing, causing `currentLiquidityEvaluation` to be dependent on the initial price for `VADER`. As a result, liquidity weightings do not accurately reflect the current and most up to date price for `VADER`.

This same issue also affects how `USDV` calculates `currentLiquidityEvaluation`.

This issue is of high risk and heavily impacts the accuracy of the TWAP implementation as the set price for `VADER/USDV` diverges from current market prices. For example, as the Chainlink oracle price and initial price for `VADER` diverge, `currentLiquidityEvaluation` will begin to favour either on-chain or off-chain price data depending on which price result is greater. The following calculation for `currentLiquidityEvaluation` outlines this behaviour.

    currentLiquidityEvaluation =
        (reserveNative * previousPrices[uint256(Paths.VADER)]) +
        (reserveForeign * getChainlinkPrice(pairData.foreignAsset));

###
