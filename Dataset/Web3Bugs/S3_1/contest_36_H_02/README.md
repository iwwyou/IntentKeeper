# H-02: Basket.sol#auctionBurn() A failed auction will freeze part of the funds

**Contest**: 36
**Reference**: https://code4rena.com/reports/2021-09-defiprotocol#h-02-basketsolauctionburn-a-failed-auction-will-freeze-part-of-the-funds

## Bug Report

## [[H-02] `Basket.sol#auctionBurn()` A failed auction will freeze part of the funds](https://github.com/code-423n4/2021-09-defiprotocol-findings/issues/134)
_Submitted by WatchPug_

<https://github.com/code-423n4/2021-09-defiProtocol/blob/main/contracts/contracts/Basket.sol#L102-L108>

Given the `auctionBurn()` function will `_burn()` the auction bond without updating the `ibRatio`. Once the bond of a failed auction is burned, the proportional underlying tokens won't be able to be withdrawn, in other words, being frozen in the contract.

###
