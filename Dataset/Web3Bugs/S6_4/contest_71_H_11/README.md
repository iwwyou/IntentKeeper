# H-11: PoolTemplate.sol#resume() Wrong implementation of resume() will compensate overmuch redeem amount from index pools

**Contest**: 71
**Reference**: https://code4rena.com/reports/2022-01-insure#h-11-pooltemplatesolresume-wrong-implementation-of-resume-will-compensate-overmuch-redeem-amount-from-index-pools

## Bug Report

## [[H-11] `PoolTemplate.sol#resume()` Wrong implementation of `resume()` will compensate overmuch redeem amount from index pools](https://github.com/code-423n4/2022-01-insure-findings/issues/283)
_Submitted by WatchPug, also found by danb_

Wrong arithmetic.

***

<https://github.com/code-423n4/2022-01-insure/blob/19d1a7819fe7ce795e6d4814e7ddf8b8e1323df3/contracts/PoolTemplate.sol#L700-L717>

```solidity
uint256 _deductionFromIndex = (_debt * _totalCredit * MAGIC_SCALE_1E6) /
            totalLiquidity();
    uint256 _actualDeduction;
    for (uint256 i = 0; i < indexList.length; i++) {
        address _index = indexList[i];
        uint256 _credit = indicies[_index].credit;
        if (_credit > 0) {
            uint256 _shareOfIndex = (_credit * MAGIC_SCALE_1E6) /
                _totalCredit;
            uint256 _redeemAmount = _divCeil(
                _deductionFromIndex,
                _shareOfIndex
            );
            _actualDeduction += IIndexTemplate(_index).compensate(
                _redeemAmount
            );
        }
    }
```

###
