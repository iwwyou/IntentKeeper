# H-01: veCVXStrategy.manualRebalance has wrong logic

**Contest**: 31
**Reference**: https://code4rena.com/reports/2021-09-bvecvx#h-01-vecvxstrategymanualrebalance-has-wrong-logic

## Bug Report

## [[H-01] `veCVXStrategy.manualRebalance` has wrong logic](https://github.com/code-423n4/2021-09-bvecvx-findings/issues/47)
_Submitted by cmichel, also found by tabish_

The `veCVXStrategy.manualRebalance` function computes two ratios `currentLockRatio` and `newLockRatio` and compares them.

However, these ratios compute different things and are not comparable:

*   `currentLockRatio = balanceInLock.mul(10**18).div(totalCVXBalance)` is a **percentage value** with 18 decimals (i.e. `1e18 = 100%`). Its max value can at most be `1e18`.
*   `newLockRatio = totalCVXBalance.mul(toLock).div(MAX_BPS)` is a **CVX token amount**. It's unbounded and just depends on the `totalCVXBalance` amount.

The comparison that follows does not make sense:

```solidity
if (newLockRatio <= currentLockRatio) {
  // ...
}
```

###
