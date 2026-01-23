# H-02: function lockFunds in TopUpActionLibrary can cause serious fund lose. fee and Capped bypass. It’s not calling stakerVault.increaseActionLockedBalance when transfers stakes.

**Contest**: 112
**Reference**: https://code4rena.com/reports/2022-04-backd#h-02-function-lockfunds-in-topupactionlibrary-can-cause-serious-fund-lose-fee-and-capped-bypass-its-not-calling-stakervaultincreaseactionlockedbalance-when-transfers-stakes

## Bug Report

## [[H-02] function `lockFunds` in `TopUpActionLibrary` can cause serious fund lose. fee and Capped bypass. It's not calling `stakerVault.increaseActionLockedBalance` when transfers stakes.](https://github.com/code-423n4/2022-04-backd-findings/issues/60)
_Submitted by unforgiven_

[TopUpAction.sol#L57-L65](https://github.com/code-423n4/2022-04-backd/blob/c856714a50437cb33240a5964b63687c9876275b/backd/contracts/actions/topup/TopUpAction.sol#L57-L65)<br>

In function TopUpActionLibrary.lockFunds when transfers stakes from payer it doesn't call stakerVault.increaseActionLockedBalance for that payer so stakerVault.actionLockedBalances\[payer] is not get updated for payer and stakerVault.stakedAndActionLockedBalanceOf(payer) is going to show wrong value and any calculation based on this function is gonna be wrong which will cause fund lose and theft and some restriction bypasses.

##
