# H-08: IndexTemplate.sol#compensate() will most certainly fail

**Contest**: 71
**Reference**: https://code4rena.com/reports/2022-01-insure#h-08-indextemplatesolcompensate-will-most-certainly-fail

## Bug Report

## [[H-08] `IndexTemplate.sol#compensate()` will most certainly fail](https://github.com/code-423n4/2022-01-insure-findings/issues/269)
_Submitted by WatchPug_

Precision loss while converting between `the amount of shares` and `the amount of underlying tokens` back and forth is not handled properly.

***

<https://github.com/code-423n4/2022-01-insure/blob/19d1a7819fe7ce795e6d4814e7ddf8b8e1323df3/contracts/IndexTemplate.sol#L438-L447>

```solidity
uint256 _shortage;
if (totalLiquidity() < _amount) {
    //Insolvency case
    _shortage = _amount - _value;
    uint256 _cds = ICDSTemplate(registry.getCDS(address(this)))
        .compensate(_shortage);
    _compensated = _value + _cds;
}
vault.offsetDebt(_compensated, msg.sender);
```

In the current implementation, when someone tries to resume the market after a pending period ends by calling `PoolTemplate.sol#resume()`, `IndexTemplate.sol#compensate()` will be called internally to make a payout. If the index pool is unable to cover the compensation, the CDS pool will then be used to cover the shortage.

However, while `CDSTemplate.sol#compensate()` takes a parameter for the amount of underlying tokens, it uses `vault.transferValue()` to transfer corresponding `_attributions` (shares) instead of underlying tokens.

Due to precision loss, the `_attributions` transferred in the terms of underlying tokens will most certainly be less than the shortage.

At L444, the contract believes that it's been compensated for `_value + _cds`, which is lower than the actual value, due to precision loss.

At L446, when it calls `vault.offsetDebt(_compensated, msg.sender)`, the tx will revert at `require(underlyingValue(msg.sender) >= _amount)`.

As a result, `resume()` can not be done, and the debt can't be repaid.

####
