# H-02: Masterchef: Improper handling of deposit fee

**Contest**: 83
**Reference**: https://code4rena.com/reports/2022-02-concur#h-02-masterchef-improper-handling-of-deposit-fee

## Bug Report

## [[H-02] Masterchef: Improper handling of deposit fee](https://github.com/code-423n4/2022-02-concur-findings/issues/138)
_Submitted by hickuphh3, also found by leastwood_

[MasterChef.sol#L170-L172](https://github.com/code-423n4/2022-02-concur/blob/main/contracts/MasterChef.sol#L170-L172)<br>

If a pool’s deposit fee is non-zero, it is subtracted from the amount to be credited to the user.

```jsx
if (pool.depositFeeBP > 0) {
  uint depositFee = _amount.mul(pool.depositFeeBP).div(_perMille);
  user.amount = SafeCast.toUint128(user.amount + _amount - depositFee);
}
```

However, the deposit fee is not credited to anyone, leading to permanent lockups of deposit fees in the relevant depositor contracts (StakingRewards and ConvexStakingWrapper for now).

##
