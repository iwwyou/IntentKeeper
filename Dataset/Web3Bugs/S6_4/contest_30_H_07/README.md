# H-07: Vault.balance() mixes normalized and standard amounts

**Contest**: 30
**Reference**: https://code4rena.com/reports/2021-09-yaxis#h-07-vaultbalance-mixes-normalized-and-standard-amounts

## Bug Report

## [[H-07] `Vault.balance()` mixes normalized and standard amounts](https://github.com/code-423n4/2021-09-yaxis-findings/issues/132)
_Submitted by cmichel_

The `Vault.balance` function uses the `balanceOfThis` function which scales ("normalizes") all balances to 18 decimals.
```solidity
for (uint8 i; i < _tokens.length; i++) {
    address _token = _tokens[i];
    // everything is padded to 18 decimals
    _balance = _balance.add(_normalizeDecimals(_token, IERC20(_token).balanceOf(address(this))));
}
```
Note that `balance()`'s second term `IController(manager.controllers(address(this))).balanceOf()` is not normalized.
The code is adding a non-normalized amount (for example 6 decimals only for USDC) to a normalized (18 decimals).

###
