# H-01: Oracle price does not compound

**Contest**: 102
**Reference**: https://code4rena.com/reports/2022-03-volt#h-01-oracle-price-does-not-compound

## Bug Report

## [[H-01] Oracle price does not compound](https://github.com/code-423n4/2022-03-volt-findings/issues/22)
_Submitted by cmichel_

[ScalingPriceOracle.sol#L136](https://github.com/code-423n4/2022-03-volt/blob/f1210bf3151095e4d371c9e9d7682d9031860bbd/contracts/oracle/ScalingPriceOracle.sol#L136)<br>
[ScalingPriceOracle.sol#L113](https://github.com/code-423n4/2022-03-volt/blob/f1210bf3151095e4d371c9e9d7682d9031860bbd/contracts/oracle/ScalingPriceOracle.sol#L113)<br>

The oracle does not correctly compound the monthly APRs - it resets on `fulfill`.<br>
Note that the [`oraclePrice` storage variable](https://github.com/code-423n4/2022-03-volt/blob/f1210bf3151095e4d371c9e9d7682d9031860bbd/contracts/oracle/ScalingPriceOracle.sol#L198) is only set in `_updateCPIData` as part of the oracle `fulfill` callback.<br>
It's set to the old price (price from 1 month ago) plus the interpolation from **`startTime`** to now.<br>
However, `startTime` is **reset** in `requestCPIData` due to the `afterTimeInit` modifier, and therefore when Chainlink calls `fulfill` in response to the CPI request, the `timeDelta = block.timestamp - startTime` is close to zero again and `oraclePrice` is updated to itself again.

This breaks the core functionality of the protocol as the oracle does not track the CPI, it always resets to `1.0` after every `fulfill` instead of compounding it.<br>
In addition, there should also be a way for an attacker to profit from the sudden drop of the oracle price to `1.0` again.

##
