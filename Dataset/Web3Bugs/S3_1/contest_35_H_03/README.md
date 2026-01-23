# H-03: ConcentratedLiquidityPoolManager’s incentives can be stolen

**Contest**: 35
**Reference**: https://code4rena.com/reports/2021-09-sushitrident-2#h-03-concentratedliquiditypoolmanagers-incentives-can-be-stolen

## Bug Report

## [[H-03] `ConcentratedLiquidityPoolManager`'s incentives can be stolen](https://github.com/code-423n4/2021-09-sushitrident-2-findings/issues/37)
_Submitted by cmichel, also found by broccoli, hickuphh3, pauliax, and WatchPug_

The `ConcentratedLiquidityPoolManager` keeps all tokens for all incentives in the same contract. The `reclaimIncentive` function does not reduce the `incentive.rewardsUnclaimed` field and thus one can reclaim tokens several times.
This allows anyone to steal all tokens from all incentives by creating an incentive themself, and once it's expired, repeatedly claim the unclaimed rewards until the token balance is empty.

###
