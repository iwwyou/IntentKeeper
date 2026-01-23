# H-08: Wrong liquidity units calculation

**Contest**: 5
**Reference**: https://code4rena.com/reports/2021-04-vader#h-08-wrong-liquidity-units-calculation

## Bug Report

## [[H-08] Wrong liquidity units calculation](https://github.com/code-423n4/2021-04-vader-findings/issues/204)

The spec defines the number of LP units to be minted as `units = (P (a B + A b))/(2 A B) * slipAdjustment = P * (part1 + part2) / part3 * slipAdjustments` but the `Utils.calcLiquidityUnits` function computes `((P * part1) + part2) / part3 * slipAdjustments`.

The associativity on `P * part1` is wrong, and `part2` is not multiplied by `P`.

The math from the spec is not correctly implemented and could lead to the protocol being economically exploited, as redeeming the minted LP tokens does not result in the initial tokens anymore.

Recommend fixing the equation.

**[strictly-scarce (vader) confirmed](https://github.com/code-423n4/2021-04-vader-findings/issues/204#issuecomment-830609695):**
> Valid, but funds not at risk.


