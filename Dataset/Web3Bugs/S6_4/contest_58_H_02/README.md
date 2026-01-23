# H-02: Wrong implementation of performanceFee can cause users to lose 50% to 100% of their funds

**Contest**: 58
**Reference**: https://code4rena.com/reports/2021-12-mellow#h-02-wrong-implementation-of-performancefee-can-cause-users-to-lose-50-to-100-of-their-funds

## Bug Report

## [[H-02] Wrong implementation of `performanceFee` can cause users to lose 50% to 100% of their funds](https://github.com/code-423n4/2021-12-mellow-findings/issues/91)
_Submitted by WatchPug_

A certain amount of lp tokens (shares of the vault) will be minted to the `strategyPerformanceTreasury` as `performanceFee`, the amount is calculated based on the `minLpPriceFactor`.

However, the current formula for `toMint` is wrong, which issues more than 100% of the current totalSupply of the lp token to the `strategyPerformanceTreasury` each time. Causing users to lose 50% to 100% of their funds after a few times.

<https://github.com/code-423n4/2021-12-mellow/blob/6679e2dd118b33481ee81ad013ece4ea723327b5/mellow-vaults/contracts/LpIssuer.sol#L269-L271>

```solidity
address treasury = strategyParams.strategyPerformanceTreasury;
uint256 toMint = (baseSupply * minLpPriceFactor) / CommonLibrary.DENOMINATOR;
_mint(treasury, toMint);
```

###
