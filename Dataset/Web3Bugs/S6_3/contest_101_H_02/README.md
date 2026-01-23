# H-02: PooledCreditLine: termination likely fails because _principleWithdrawable is treated as shares

**Contest**: 101
**Reference**: https://code4rena.com/reports/2022-03-sublime#h-02-pooledcreditline-termination-likely-fails-because-_principlewithdrawable-is-treated-as-shares

## Bug Report

## [[H-02] `PooledCreditLine`: termination likely fails because `_principleWithdrawable` is treated as shares](https://github.com/code-423n4/2022-03-sublime-findings/issues/21)
_Submitted by hickuphh3, also found by rayn and WatchPug_

[LenderPool.sol#L404-L406](https://github.com/sublime-finance/sublime-v1/blob/46536a6d25df4264c1b217bd3232af30355dcb95/contracts/PooledCreditLine/LenderPool.sol#L404-L406)<br>

`_principalWithdrawable` is denominated in the borrowAsset, but subsequently treats it as the share amount to be withdrawn.

```jsx
// _notBorrowed = borrowAsset amount that isn't borrowed
// totalSupply[_id] = ERC1155 total supply of _id
// _borrowedTokens = borrower's specified borrowLimit
uint256 _principalWithdrawable = _notBorrowed.mul(totalSupply[_id]).div(_borrowedTokens);

SAVINGS_ACCOUNT.withdrawShares(_borrowAsset, _strategy, _to, _principalWithdrawable.add(_totalInterestInShares), false);
```

##
