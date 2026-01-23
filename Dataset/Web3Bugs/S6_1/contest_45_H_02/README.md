# H-02: Wrong implementation of CreditLimitByMedian.sol#getLockedAmount() makes it unable to unlock lockedAmount in CreditLimitByMedian model

**Contest**: 45
**Reference**: https://code4rena.com/reports/2021-10-union#h-02-wrong-implementation-of-creditlimitbymediansolgetlockedamount-makes-it-unable-to-unlock-lockedamount-in-creditlimitbymedian-model

## Bug Report

## [[H-02] Wrong implementation of `CreditLimitByMedian.sol#getLockedAmount()` makes it unable to unlock `lockedAmount` in `CreditLimitByMedian` model](https://github.com/code-423n4/2021-10-union-findings/issues/80)
_Submitted by WatchPug_

[`CreditLimitByMedian.sol` L27-L78](https://github.com/code-423n4/2021-10-union/blob/4176c366986e6d1a6b3f6ec0079ba547b040ac0f/contracts/user/CreditLimitByMedian.sol#L27-L78)

```solidity
function getLockedAmount(
    LockedInfo[] memory array,
    address account,
    uint256 amount,
    bool isIncrease
) public pure override returns (uint256) {
    if (array.length == 0) return 0;

    uint256 newLockedAmount;
    if (isIncrease) {
        ...
    } else {
        for (uint256 i = 0; i < array.length; i++) {
            if (array[i].lockedAmount > amount) {
                newLockedAmount = array[i].lockedAmount - 1;
            } else {
                newLockedAmount = 0;
            }

            if (account == array[i].staker) {
                return newLockedAmount;
            }
        }
    }

    return 0;
}
```

`getLockedAmount()` is used by `UserManager.sol#updateLockedData()` to update locked amounts.

Based on the context, at L66, `newLockedAmount = array[i].lockedAmount - 1;` should be `newLockedAmount = array[i].lockedAmount - amount;`.

The current implementation is wrong and makes it impossible to unlock `lockedAmount` in `CreditLimitByMedian` model.

####
