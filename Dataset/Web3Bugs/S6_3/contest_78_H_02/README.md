# H-02: wrong minting amount

**Contest**: 78
**Reference**: https://code4rena.com/reports/2022-01-behodler#h-02-wrong-minting-amount

## Bug Report

## [[H-02] wrong minting amount](https://github.com/code-423n4/2022-01-behodler-findings/issues/297)
_Submitted by danb_

<https://github.com/code-423n4/2022-01-behodler/blob/main/contracts/TokenProxies/RebaseProxy.sol#L36>

```solidity
uint256 proxy = (baseBalance * ONE) / _redeemRate;
```

should be:
```solidity
uint256 proxy = (amount * ONE) / _redeemRate;
```

**[gititGoro (Behodler) confirmed, but disagreed with High severity and commented](https://github.com/code-423n4/2022-01-behodler-findings/issues/297#issuecomment-1030508474):**
 > Should be a balanceBefore and balanceAfter calculation with the diff being wrapped.

**[Jack the Pug (judge) commented](https://github.com/code-423n4/2022-01-behodler-findings/issues/297#issuecomment-1041248898):**
 > Valid `high`. The issue description can be more comprehensive though.



***


