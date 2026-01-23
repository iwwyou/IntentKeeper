# H-02: LendingPair.liquidateAccount does not accrue and update cumulativeInterestRate

**Contest**: 18
**Reference**: https://code4rena.com/reports/2021-07-wildcredit#h-02-lendingpairliquidateaccount-does-not-accrue-and-update-cumulativeinterestrate

## Bug Report

## [[H-02] `LendingPair.liquidateAccount` does not accrue and update `cumulativeInterestRate`](https://github.com/code-423n4/2021-07-wildcredit-findings/issues/122)
_Submitted by cmichel_

The `LendingPair.liquidateAccount` function does not accrue and update the `cumulativeInterestRate` first, it only calls `_accrueAccountInterest` which does not update and instead uses the old `cumulativeInterestRate`.

The liquidatee (borrower)'s state will not be up-to-date.
I could skip some interest payments by liquidating myself instead of repaying if I'm under-water.
As the market interest index is not accrued, the borrower does not need to pay any interest accrued from the time of the last accrual until now.

Recommend calling `accrueAccount` instead of `_accrueAccountInterest`

**[talegift (Wild Credit) confirmed but disagreed with severity](https://github.com/code-423n4/2021-07-wildcredit-findings/issues/122#issuecomment-880580414):**
 > _Assets not at direct risk, but the function of the protocol or its availability could be impacted, or **leak value** with a hypothetical attack path with stated assumptions, but **external requirements**._
>
> Update to severity - 2

**[ghoul-sol (Judge) commented](https://github.com/code-423n4/2021-07-wildcredit-findings/issues/122#issuecomment-890597983):**
 > No funds are lost however a user can steal "unpaid interest" from the protocol. Keeping high risk.


