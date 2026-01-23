# H-05: Mistake while checking LTV to lender accepted LTV

**Contest**: 113
**Reference**: https://code4rena.com/reports/2022-04-abranft#h-05-mistake-while-checking-ltv-to-lender-accepted-ltv

## Bug Report

## [[H-05] Mistake while checking LTV to lender accepted LTV](https://github.com/code-423n4/2022-04-abranft-findings/issues/55)
_Submitted by catchup, also found by WatchPug, gzeon, and hyh_

It comments in the `\_lend()` function that lender accepted conditions must be at least as good as the borrower is asking for.
The line which checks the accepted LTV (lender's LTV) against borrower asking LTV is:
`params.ltvBPS >= accepted.ltvBPS`,
This means lender should be offering a lower LTV, which must be the opposite way around.
I think this may have the potential to strand the lender, if he enters a lower LTV.
For example borrower asking LTV is 86%. However, lender enters his accepted LTV as 80%.
lend() will execute with 86% LTV and punish the lender, whereas it should revert and acknowledge the lender that his bid is not good enough.

##
