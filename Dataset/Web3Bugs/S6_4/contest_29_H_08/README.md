# H-08: HybridPool’s reserve is converted to “amount” twice

**Contest**: 29
**Reference**: https://code4rena.com/reports/2021-09-sushitrident#h-08-hybridpools-reserve-is-converted-to-amount-twice

## Bug Report

## [[H-08] `HybridPool`'s reserve is converted to "amount" twice](https://github.com/code-423n4/2021-09-sushitrident-findings/issues/101)
_Submitted by cmichel, also found by 0xsanson and WatchPug_

The `HybridPool`'s reserves are stored as Bento "amounts" (not Bento shares) in `_updateReserves` because `_balance()` converts the current share balance to amount balances.
However, when retrieving the `reserve0/1` storage fields in `_getReserves`, they are converted to amounts a second time.

###
