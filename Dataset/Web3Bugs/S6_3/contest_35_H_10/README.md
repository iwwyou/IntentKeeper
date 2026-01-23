# H-10: ConcentratedLiquidityPool.burn() Wrong implementation

**Contest**: 35
**Reference**: https://code4rena.com/reports/2021-09-sushitrident-2#h-10-concentratedliquiditypoolburn-wrong-implementation

## Bug Report

## [[H-10] `ConcentratedLiquidityPool.burn()` Wrong implementation](https://github.com/code-423n4/2021-09-sushitrident-2-findings/issues/24)
_Submitted by WatchPug_

The reserves should be updated once LP tokens are burned to match the actual total bento shares hold by the pool.

However, the current implementation only updated reserves with the fees subtracted.

Makes the `reserve0` and `reserve1` smaller than the current `balance0` and `balance1`.

###
