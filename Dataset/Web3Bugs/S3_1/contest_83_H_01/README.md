# H-01: Wrong reward token calculation in MasterChef contract

**Contest**: 83
**Reference**: https://code4rena.com/reports/2022-02-concur#h-01-wrong-reward-token-calculation-in-masterchef-contract

## Bug Report

## [[H-01] Wrong reward token calculation in MasterChef contract](https://github.com/code-423n4/2022-02-concur-findings/issues/219)
_Submitted by throttle, also found by cccz, cmichel, and leastwood_

[MasterChef.sol#L86](https://github.com/code-423n4/2022-02-concur/blob/main/contracts/MasterChef.sol#L86)<br>

When adding new token pool for staking in MasterChef contract

```javascript
function add(address _token, uint _allocationPoints, uint16 _depositFee, uint _startBlock)
```

All other, already added, pools should be updated but currently they are not.<br>
Instead, only totalPoints is updated. Therefore, old (and not updated) pools will lose it's share during the next update.<br>
Therefore, user rewards are not computed correctly (will be always smaller).

##
