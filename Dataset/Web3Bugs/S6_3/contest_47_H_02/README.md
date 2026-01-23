# H-02: Approved spender can spend too many tokens

**Contest**: 47
**Reference**: https://code4rena.com/reports/2021-10-badgerdao#h-02-approved-spender-can-spend-too-many-tokens

## Bug Report

## [[H-02] Approved spender can spend too many tokens](https://github.com/code-423n4/2021-10-badgerdao-findings/issues/43)
_Submitted by cmichel, also found by WatchPug, jonah1005, gzeon, and TomFrench_
The `approve` function has not been overridden and therefore uses the internal *shares*, whereas `transfer(From)` uses the rebalanced amount.

###
