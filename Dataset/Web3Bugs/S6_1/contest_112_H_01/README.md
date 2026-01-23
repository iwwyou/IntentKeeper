# H-01: User can steal all rewards due to checkpoint after transfer

**Contest**: 112
**Reference**: https://code4rena.com/reports/2022-04-backd#h-01-user-can-steal-all-rewards-due-to-checkpoint-after-transfer

## Bug Report

## [[H-01] User can steal all rewards due to checkpoint after transfer](https://github.com/code-423n4/2022-04-backd-findings/issues/36)
_Submitted by 0xDjango, also found by unforgiven_

[StakerVault.sol#L112-L119](https://github.com/code-423n4/2022-04-backd/blob/c856714a50437cb33240a5964b63687c9876275b/backd/contracts/StakerVault.sol#L112-L119)<br>

I believe this to be a high severity vulnerability that is potentially included in the currently deployed `StakerVault.sol` contract also. The team will be contacted immediately following the submission of this report.

In `StakerVault.sol`, the user checkpoints occur AFTER the balances are updated in the `transfer()` function. The user checkpoints update the amount of rewards claimable by the user. Since their rewards will be updated after transfer, a user can send funds between their own accounts and repeatedly claim maximum rewards since the pool's inception.

In every actionable function except `transfer()` of `StakerVault.sol`, a call to `ILpGauge(lpGauge).userCheckpoint()` is correctly made BEFORE the action effects.

##
