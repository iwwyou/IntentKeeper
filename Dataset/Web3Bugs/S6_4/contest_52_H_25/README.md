# H-25: Wrong design of swap() results in unexpected and unfavorable outputs

**Contest**: 52
**Reference**: https://code4rena.com/reports/2021-11-vader#h-25-wrong-design-of-swap-results-in-unexpected-and-unfavorable-outputs

## Bug Report

## [[H-25] Wrong design of `swap()` results in unexpected and unfavorable outputs](https://github.com/code-423n4/2021-11-vader-findings/issues/213)
_Submitted by WatchPug_

The current formula to calculate the `amountOut` for a swap is:

<https://github.com/code-423n4/2021-11-vader/blob/429970427b4dc65e37808d7116b9de27e395ce0c/contracts/dex/math/VaderMath.sol#L99-L111>

```solidity
function calculateSwap(
    uint256 amountIn,
    uint256 reserveIn,
    uint256 reserveOut
) public pure returns (uint256 amountOut) {
    // x * Y * X
    uint256 numerator = amountIn * reserveIn * reserveOut;

    // (x + X) ^ 2
    uint256 denominator = pow(amountIn + reserveIn);

    amountOut = numerator / denominator;
}
```

We believe the design (the formula) is wrong and it will result in unexpected and unfavorable outputs.

Specifically, if the `amountIn` is larger than the `reserveIn`, the `amountOut` starts to decrease.

####
