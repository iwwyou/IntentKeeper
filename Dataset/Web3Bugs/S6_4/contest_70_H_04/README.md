# H-04: Vader TWAP averages wrong

**Contest**: 70
**Reference**: https://code4rena.com/reports/2021-12-vader#h-04-vader-twap-averages-wrong

## Bug Report

## [[H-04] Vader TWAP averages wrong](https://github.com/code-423n4/2021-12-vader-findings/issues/148)
_Submitted by cmichel_

The vader price in `LiquidityBasedTWAP.getVaderPrice` is computed using the `pastLiquidityWeights` and `pastTotalLiquidityWeight` return values of the `syncVaderPrice`.

The `syncVaderPrice` function does not initialize all weights and the total liquidity weight does not equal the sum of the individual weights because it skips initializing the pair with the previous data if the TWAP update window has not been reached yet:

```solidity
function syncVaderPrice()
    public
    override
    returns (
        uint256[] memory pastLiquidityWeights,
        uint256 pastTotalLiquidityWeight
    )
{
    uint256 _totalLiquidityWeight;
    uint256 totalPairs = vaderPairs.length;
    pastLiquidityWeights = new uint256[](totalPairs);
    pastTotalLiquidityWeight = totalLiquidityWeight[uint256(Paths.VADER)];

    for (uint256 i; i < totalPairs; ++i) {
        IUniswapV2Pair pair = vaderPairs[i];
        ExchangePair storage pairData = twapData[address(pair)];
        // @audit-info lastMeasurement is set in _updateVaderPrice to block.timestamp
        uint256 timeElapsed = block.timestamp - pairData.lastMeasurement;
        // @audit-info update period depends on pair
        // @audit-issue if update period not reached => does not initialize pastLiquidityWeights[i]
        if (timeElapsed < pairData.updatePeriod) continue;

        uint256 pastLiquidityEvaluation = pairData.pastLiquidityEvaluation;
        uint256 currentLiquidityEvaluation = _updateVaderPrice(
            pair,
            pairData,
            timeElapsed
        );

        pastLiquidityWeights[i] = pastLiquidityEvaluation;

        pairData.pastLiquidityEvaluation = currentLiquidityEvaluation;

        _totalLiquidityWeight += currentLiquidityEvaluation;
    }

    totalLiquidityWeight[uint256(Paths.VADER)] = _totalLiquidityWeight;
}
```

#####
