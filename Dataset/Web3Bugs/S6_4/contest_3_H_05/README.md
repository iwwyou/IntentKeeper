# H-05: Wrong liquidation logic

**Contest**: 3
**Reference**: https://code4rena.com/reports/2021-04-marginswap#h-05-wrong-liquidation-logic

## Bug Report

## [[H-05] Wrong liquidation logic](https://github.com/code-423n4/2021-04-marginswap-findings/issues/23)

The `belowMaintenanceThreshold` function decides if a trader can be liquidated:

```solidity
function belowMaintenanceThreshold(CrossMarginAccount storage account)
    internal
    returns (bool)
{
    uint256 loan = loanInPeg(account, true);
    uint256 holdings = holdingsInPeg(account, true);
    // The following should hold:
    // holdings / loan >= 1.1
    // =>
    return 100 * holdings >= liquidationThresholdPercent * loan;
}
```

The inequality in the last equation is wrong because it says the higher the holdings (margin + loan) compared to the loan, the higher the chance of being liquidated. The inverse equality was probably intended `return 100 * holdings <= liquidationThresholdPercent * loan;`. Users that shouldn't be liquidated can be liquidated, and users that should be liquidated cannot get liquidated.


