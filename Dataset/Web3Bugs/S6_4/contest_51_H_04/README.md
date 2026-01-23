# H-04: Swaps are not split when trade crosses target price

**Contest**: 51
**Reference**: https://code4rena.com/reports/2021-11-bootfinance#h-04-swaps-are-not-split-when-trade-crosses-target-price

## Bug Report

## [[H-04] Swaps are not split when trade crosses target price](https://github.com/code-423n4/2021-11-bootfinance-findings/issues/216)
_Submitted by cmichel, also found by gzeon_

The protocol uses two amplifier values A1 and A2 for the swap, depending on the target price, see `SwapUtils.determineA`.
The swap curve is therefore a join of two different curves at the target price.
When doing a trade that crosses the target price, it should first perform the trade partially with A1 up to the target price, and then the rest of the trade order with A2.

However, the `SwapUtils.swap / _calculateSwap` function does not do this, it only uses the "new A", see `getYC` step 5.

```solidity
// 5. Check if we switched A's during the swap
if (aNew == a){     // We have used the correct A
    return y;
} else {    // We have switched A's, do it again with the new A
    return getY(self, tokenIndexFrom, tokenIndexTo, x, xp, aNew, d);
}
```

###
