# H-04: Logic error in burnFlashGovernanceAsset can cause locked assets to be stolen

**Contest**: 78
**Reference**: https://code4rena.com/reports/2022-01-behodler#h-04-logic-error-in-burnflashgovernanceasset-can-cause-locked-assets-to-be-stolen

## Bug Report

## [[H-04] Logic error in `burnFlashGovernanceAsset` can cause locked assets to be stolen](https://github.com/code-423n4/2022-01-behodler-findings/issues/305)
_Submitted by shw_

A logic error in the `burnFlashGovernanceAsset` function that resets a user's `pendingFlashDecision` allows that user to steal other user's assets locked in future flash governance decisions. As a result, attackers can get their funds back even if they execute a malicious flash decision and the community burns their assets.

###
