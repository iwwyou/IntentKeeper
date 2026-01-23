# H-06: Wrong price scale for GasOracle

**Contest**: 16
**Reference**: https://code4rena.com/reports/2021-06-tracer#h-06-wrong-price-scale-for-gasoracle

## Bug Report

## [[H-06] Wrong price scale for `GasOracle`](https://github.com/code-423n4/2021-06-tracer-findings/issues/93)
_Submitted by cmichel_

The `GasOracle` uses two chainlink oracles (GAS in ETH with some decimals, USD per ETH with some decimals) and multiplies their raw return values to get the gas price in USD.

However, the scaling depends on the underlying decimals of the two oracles and could be anything.
But the code assumes it's in 18 decimals.

> "Returned value is USD/Gas * 10^18 for compatibility with rest of calculations"

There is a `toWad` function that seems to involve scaling but it is never used.

The impact is that, If the scale is wrong, the gas price can be heavily inflated or under-reported.

Recommend checking `chainlink.decimals()` to know the decimals of the oracle answers and scale the answers to 18 decimals such that no matter the decimals of the underlying oracles, the `latestAnswer` function always returns the answer in 18 decimals.

**[raymogg (Tracer) confirmed and disagreed with severity](https://github.com/code-423n4/2021-06-tracer-findings/issues/93#issuecomment-873750451):**
 > Disagree with severity as while the statement that the underlying decimals of the oracles could be anything, we will be using production Chainlink feeds for which the decimals are known at the time of deploy.
>
> This is still however an issue as you don't want someone using different oracles (eg non Chainlink) that have different underlying decimals and not realising that this contract will not support that.

**[cemozerr (Judge) commented](https://github.com/code-423n4/2021-06-tracer-findings/issues/93#issuecomment-882123137):**
 > Marking this a high-risk issue as it poses a big threat to users deploying their own markets


