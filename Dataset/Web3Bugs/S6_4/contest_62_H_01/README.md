# H-01: Wrong calculation of excess depositToken allows stream creator to retrieve depositTokenFlashloanFeeAmount

**Contest**: 62
**Reference**: which may cause fund loss to users"

## Bug Report

## [[H-01] Wrong calculation of excess depositToken allows stream creator to retrieve `depositTokenFlashloanFeeAmount`, which may cause fund loss to users](https://github.com/code-423n4/2021-11-streaming-findings/issues/241)
_Submitted by WatchPug, also found by 0x0x0x, ScopeLift, gpersoon, harleythedog, hyh, gzeon, jonah1005, and kenzo_

<https://github.com/code-423n4/2021-11-streaming/blob/56d81204a00fc949d29ddd277169690318b36821/Streaming/src/Locke.sol#L654-L654>

```solidity
uint256 excess = ERC20(token).balanceOf(address(this)) - (depositTokenAmount - redeemedDepositTokens);
```

In the current implementation, `depositTokenFlashloanFeeAmount` is not excluded when calculating `excess` depositToken. Therefore, the stream creator can call `recoverTokens(depositToken, recipient)` and retrieve `depositTokenFlashloanFeeAmount` if there are any.

As a result:

*   When the protocol `governance` calls `claimFees()` and claim accumulated `depositTokenFlashloanFeeAmount`, it may fail due to insufficient balance of depositToken.
*   Or, part of users' funds (depositToken) will be transferred to the protocol `governance` as fees, causing some users unable to withdraw or can only withdraw part of their deposits.

###
