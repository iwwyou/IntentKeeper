# H-03: setYieldSource leads to temporary wrong results

**Contest**: 24
**Reference**: https://code4rena.com/reports/2021-07-pooltogether#h-03-setyieldsource-leads-to-temporary-wrong-results

## Bug Report

## [[H-03] `setYieldSource` leads to temporary wrong results](https://github.com/code-423n4/2021-07-pooltogether-findings/issues/4)
_Submitted by gpersoon_

The use of `setYieldSource` leaves the contract in a temporary inconsistent state because it changes the underlying yield source,
but doesn't (yet) transfer the underlying balances, while the shares stay the same.

The function `balanceOfToken` will show the wrong results, because it is based on `_sharesToToken`, which uses `yieldSource.balanceOfToken(address(this))`, that isn't updated yet.

More importantly `supplyTokenTo` will give the wrong amount of shares back:
First it supplies tokens to the `yieldsource`.
Then is calls `_mintShares`, which calls `_tokenToShares`, which calculates the shares, using `yieldSource.balanceOfToken(address(this))`
This `yieldSource.balanceOfToken(address(this))` only contains the just supplied tokens, but doesn't include the tokens from the previous `YieldSource`.
So the wrong amount of shares is given back to the user; they will be given more shares than appropriate which means they can drain funds later on (once `transferFunds` has been done).

It is possible to make use of this problem in the following way:
- monitor the blockchain until you see `setYieldSource` has been done
- immediately call the function `supplyTokenTo` (which can be called because there is no access control on this function)

```solidity
// https://github.com/pooltogether/swappable-yield-source/blob/main/contracts/SwappableYieldSource.sol
function setYieldSource(IYieldSource _newYieldSource) external `onlyOwnerOrAssetManager` returns (bool) {
  _setYieldSource(_newYieldSource);

function _setYieldSource(IYieldSource _newYieldSource) internal {
..
    yieldSource = _newYieldSource;

 function supplyTokenTo(uint256 amount, address to) external override nonReentrant {
   ..
    yieldSource.supplyTokenTo(amount, address(this));
    _mintShares(amount, to);
  }

 function _mintShares(uint256 mintAmount, address to) internal {
    uint256 shares = `_tokenToShares`(mintAmount);
    require(shares > 0, "SwappableYieldSource/shares-gt-zero");
    _mint(to, shares);
  }

 function _tokenToShares(uint256 tokens) internal returns (uint256) {
    uint256 shares;
    uint256 _totalSupply = totalSupply();
..
      uint256 exchangeMantissa = FixedPoint.calculateMantissa(_totalSupply, yieldSource.balanceOfToken(address(this))); // based on incomplete yieldSource.balanceOfToken(address(this))
      shares = FixedPoint.multiplyUintByMantissa(tokens, exchangeMantissa);


function balanceOfToken(address addr) external override returns (uint256) {
    return _sharesToToken(balanceOf(addr));
  }

 function _sharesToToken(uint256 shares) internal returns (uint256) {
    uint256 tokens;
    uint256 _totalSupply = totalSupply();
..
      uint256 exchangeMantissa = FixedPoint.calculateMantissa(yieldSource.balanceOfToken(address(this)), _totalSupply); // based on incomplete yieldSource.balanceOfToken(address(this))
      tokens = FixedPoint.multiplyUintByMantissa(shares, exchangeMantissa);
```

Reocommend removing the function `setYieldSource`  (e.g. only leave `swapYieldSource`)
Or temporally disable actions like `supplyTokenTo`, `redeemToken` and balanceOfToken, after `setYieldSource` and until `transferFunds` has been done.

**[PierrickGT (PoolTogether) confirmed and resolved](https://github.com/code-423n4/2021-07-pooltogether-findings/issues/4#issuecomment-896981238):**
 > PR: https://github.com/pooltogether/swappable-yield-source/pull/4
> We've mitigated this issue by removing the `transferFunds` and `setYieldSource` external functions and making `swapYieldSource` callable only by the owner that will be a multi sig wallet for governance pools.


