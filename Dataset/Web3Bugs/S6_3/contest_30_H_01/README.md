# H-01: Controller.setCap sets wrong vault balance

**Contest**: 30
**Reference**: https://code4rena.com/reports/2021-09-yaxis#h-01-controllersetcap-sets-wrong-vault-balance

## Bug Report

## [[H-01] `Controller.setCap` sets wrong vault balance](https://github.com/code-423n4/2021-09-yaxis-findings/issues/128)
_Submitted by cmichel_

The `Controller.setCap` function sets a cap for a strategy and withdraws any excess amounts (`_diff`).
The vault balance is decreased by the entire strategy balance instead of by this `_diff`:

```solidity
// @audit why not sub _diff?
_vaultDetails[_vault].balance = _vaultDetails[_vault].balance.sub(_balance);
```

###
