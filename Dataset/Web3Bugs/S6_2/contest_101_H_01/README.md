# H-01: LenderPool: Principal withdrawable is incorrectly calculated if start() is invoked with non-zero start fee

**Contest**: 101
**Reference**: https://code4rena.com/reports/2022-03-sublime#h-01-lenderpool-principal-withdrawable-is-incorrectly-calculated-if-start-is-invoked-with-non-zero-start-fee

## Bug Report

## [[H-01] `LenderPool`: Principal withdrawable is incorrectly calculated if start() is invoked with non-zero start fee](https://github.com/code-423n4/2022-03-sublime-findings/issues/19)
_Submitted by hickuphh3_

[LenderPool.sol#L594-L599](https://github.com/sublime-finance/sublime-v1/blob/46536a6d25df4264c1b217bd3232af30355dcb95/contracts/PooledCreditLine/LenderPool.sol#L594-L599)<br>
[LenderPool.sol#L399-L404](https://github.com/sublime-finance/sublime-v1/blob/46536a6d25df4264c1b217bd3232af30355dcb95/contracts/PooledCreditLine/LenderPool.sol#L399-L404)<br>

The `_principalWithdrawable` calculated will be more than expected if `_start()` is invoked with a non-zero start fee, because the borrow limit is reduced by the fee, resulting in `totalSupply[id]` not being 1:1 with the borrow limit.

```jsx
function _calculatePrincipalWithdrawable(uint256 _id, address _lender) internal view returns (uint256) {
  uint256 _borrowedTokens = pooledCLConstants[_id].borrowLimit;
  uint256 _totalLiquidityWithdrawable = _borrowedTokens.sub(POOLED_CREDIT_LINE.getPrincipal(_id));
  uint256 _principalWithdrawable = _totalLiquidityWithdrawable.mul(balanceOf(_lender, _id)).div(_borrowedTokens);
  return _principalWithdrawable;
}
```

##
