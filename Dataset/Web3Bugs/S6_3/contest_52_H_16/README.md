# H-16: VaderRouter.calculateOutGivenIn calculates wrong swap

**Contest**: 52
**Reference**: https://code4rena.com/reports/2021-11-vader#h-16-vaderroutercalculateoutgivenin-calculates-wrong-swap

## Bug Report

## [[H-16] `VaderRouter.calculateOutGivenIn` calculates wrong swap](https://github.com/code-423n4/2021-11-vader-findings/issues/162)
_Submitted by cmichel_

The 3-path hop in `VaderRouter.calculateOutGivenIn` is supposed to first swap **foreign** assets to native assets **in pool0**, and then the received native assets to different foreign assets again **in pool1**.

The first argument of `VaderMath.calculateSwap(amountIn, reserveIn, reserveOut)` must refer to the same token as the second argument `reserveIn`.
The code however mixes these positions up and first performs a swap in `pool1` instead of `pool0`:

```solidity
function calculateOutGivenIn(uint256 amountIn, address[] calldata path)
    external
    view
    returns (uint256 amountOut)
{
  if(...) {
  } else {
    return
        VaderMath.calculateSwap(
            VaderMath.calculateSwap(
                // @audit the inner trade should not be in pool1 for a forward swap. amountIn foreign => next param should be foreignReserve0
                amountIn,
                nativeReserve1,
                foreignReserve1
            ),
            foreignReserve0,
            nativeReserve0
        );
  }

 /** @audit instead should first be trading in pool0!
    VaderMath.calculateSwap(
        VaderMath.calculateSwap(
            amountIn,
            foreignReserve0,
            nativeReserve0
        ),
        nativeReserve1,
        foreignReserve1
    );
  */
```

###
