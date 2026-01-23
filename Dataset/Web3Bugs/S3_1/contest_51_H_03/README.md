# H-03: SwapUtils.sol Wrong implementation

**Contest**: 51
**Reference**: https://code4rena.com/reports/2021-11-bootfinance#h-03-swaputilssol-wrong-implementation

## Bug Report

## [[H-03] `SwapUtils.sol` Wrong implementation](https://github.com/code-423n4/2021-11-bootfinance-findings/issues/252)
_Submitted by WatchPug_

Based on the context, the `tokenPrecisionMultipliers` used in price calculation should be calculated in realtime based on `initialTargetPrice`, `futureTargetPrice`, `futureTargetPriceTime` and current time, just like `getA()` and `getA2()`.

However, in the current implementation, `tokenPrecisionMultipliers` used in price calculation is the stored value, it will only be changed when the owner called `rampTargetPrice()` and `stopRampTargetPrice()`.

As a result, the `targetPrice` set by the owner will not be effective until another `targetPrice` is being set or `stopRampTargetPrice()` is called.

###
