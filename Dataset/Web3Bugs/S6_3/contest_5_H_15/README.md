# H-15: Wrong slippage protection on Token -> Token trades

**Contest**: 5
**Reference**: https://code4rena.com/reports/2021-04-vader#h-15-wrong-slippage-protection-on-token---token-trades

## Bug Report

## [[H-15] Wrong slippage protection on Token -> Token trades](https://github.com/code-423n4/2021-04-vader-findings/issues/209)
The `Router.swapWithSynthsWithLimit` allows trading token to token and specifying slippage protection. A token to token trade consists of two trades:

1. token to base
2. base to token

The slippage protection of the second trade (base to token) is computed wrong:

```solidity
require(iUTILS(UTILS()).calcSwapSlip(
    inputAmount, // should use outToken here from prev trade
    iPOOLS(POOLS).getBaseAmount(outputToken)
  ) <= slipLimit
);
```

It compares the **token** input amount (of the first trade) to the **base** reserve of the second pair.

Slippage protection fails and either the trade is cancelled when it shouldn't be or it is accepted even though the user suffered more losses than expected.

Recommend it should use the base output from the first trade to check for slippage protection. Note that this still just computes the slippage protection of each trade individually. An even better way would be to come up with a formula to compute the slippage on the two trades at once.

**[strictly-scarce (vader) confirmed](https://github.com/code-423n4/2021-04-vader-findings/issues/209#issuecomment-828476313):**
 > Valid, although disagree with severity, the wrongly compute slip amount would just fail the trade or allow the second trade to go thru with no protection.

**[Mervyn853 commented](https://github.com/code-423n4/2021-04-vader-findings/issues/209#issuecomment-830580592):**
 > Our decision matrix for severity:
>
> 0: No-risk: Code style, clarity, off-chain monitoring (events etc), exclude gas-optimisations
> 1: Low Risk: UX, state handling, function incorrect as to spec
> 2: Funds-Not-At-Risk, but can impact the functioning of the protocol, or leak value with a hypothetical attack path with stated assumptions, but external requirements
> 3: Funds can be stolen/lost directly, or indirectly if a valid attack path shown that does not have handwavey hypotheticals.
>
> Recommended: 1


