# H-08: Vault.withdraw mixes normalized and standard amounts

**Contest**: 30
**Reference**: https://code4rena.com/reports/2021-09-yaxis#h-08-vaultwithdraw-mixes-normalized-and-standard-amounts

## Bug Report

## [[H-08] `Vault.withdraw` mixes normalized and standard amounts](https://github.com/code-423n4/2021-09-yaxis-findings/issues/131)
_Submitted by cmichel, also found by hickuphh3 and jonah1005_

The `Vault.balance` function uses the `balanceOfThis` function which scales ("normalizes") all balances to 18 decimals.
```solidity
for (uint8 i; i < _tokens.length; i++) {
    address _token = _tokens[i];
    // everything is padded to 18 decimals
    _balance = _balance.add(_normalizeDecimals(_token, IERC20(_token).balanceOf(address(this))));
}
```
Note that `balance()`'s second term `IController(manager.controllers(address(this))).balanceOf()` is not normalized, but it must be.

This leads to many issues through the contracts that use `balance` but don't treat these values as normalized values.
For example, in `Vault.withdraw`, the computed `_amount` value is normalized (in 18 decimals).
But the `uint256 _balance = IERC20(_output).balanceOf(address(this));` value is not normalized but compared to the normalized `_amount` and even subtracted:

```solidity
// @audit compares unnormalzied output to normalized output
if (_balance < _amount) {
    IController _controller = IController(manager.controllers(address(this)));
    // @audit cannot directly subtract unnormalized
    uint256 _toWithdraw = _amount.sub(_balance);
    if (_controller.strategies() > 0) {
        _controller.withdraw(_output, _toWithdraw);
    }
    uint256 _after = IERC20(_output).balanceOf(address(this));
    uint256 _diff = _after.sub(_balance);
    if (_diff < _toWithdraw) {
        _amount = _balance.add(_diff);
    }
}
```

###
