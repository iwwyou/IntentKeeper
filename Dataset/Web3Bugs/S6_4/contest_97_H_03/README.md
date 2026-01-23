# H-03: Wrong formula when add fee incentivePool can lead to loss of funds.

**Contest**: 97
**Reference**: https://code4rena.com/reports/2022-03-biconomy#h-03-wrong-formula-when-add-fee-incentivepool-can-lead-to-loss-of-funds

## Bug Report

## [[H-03] Wrong formula when add fee `incentivePool` can lead to loss of funds.](https://github.com/code-423n4/2022-03-biconomy-findings/issues/38)
_Submitted by minhquanym, also found by cmichel, hickuphh3, and WatchPug_

[LiquidityPool.sol#L319-L322](https://github.com/code-423n4/2022-03-biconomy/blob/db8a1fdddd02e8cc209a4c73ffbb3de210e4a81a/contracts/hyphen/LiquidityPool.sol#L319-L322)<br>

The `getAmountToTransfer` function of `LiquidityPool` updates `incentivePool[tokenAddress]` by adding some fee to it but the formula is wrong and the value of `incentivePool[tokenAddress]` will be divided by `BASE_DIVISOR` (10000000000) each time.
After just a few time, the value of `incentivePool[tokenAddress]` will become zero and that amount of `tokenAddress` token will be locked in contract.

##
