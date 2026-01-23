# H-11: ConstantProductPool.burnSingle swap amount computations should use balance

**Contest**: 29
**Reference**: https://code4rena.com/reports/2021-09-sushitrident#h-11-constantproductpoolburnsingle-swap-amount-computations-should-use-balance

## Bug Report

## [[H-11] `ConstantProductPool.burnSingle` swap amount computations should use balance](https://github.com/code-423n4/2021-09-sushitrident-findings/issues/96)
_Submitted by cmichel_

The `ConstantProductPool.burnSingle` function is basically a `burn` followed by a `swap` and must therefore act the same way as calling these two functions sequentially.

The token amounts to redeem (`amount0`, `amount1`) are computed on the **balance** (not the reserve).
However, the swap amount is then computed on the **reserves** and not the balance.
The `burn` function would have updated the `reserve` to the balances and therefore `balance` should be used here:

```solidity
amount1 += _getAmountOut(amount0, _reserve0 - amount0, _reserve1 - amount1);
```

> ⚠️ The same issue occurs in the `HybridPool.burnSingle`.

###
