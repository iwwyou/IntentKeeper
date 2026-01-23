# H-03: Reward token not correctly recovered

**Contest**: 62
**Reference**: https://code4rena.com/reports/2021-11-streaming#h-03-reward-token-not-correctly-recovered

## Bug Report

## [[H-03] Reward token not correctly recovered](https://github.com/code-423n4/2021-11-streaming-findings/issues/214)
_Submitted by cmichel, also found by GeekyLumberjack, kenzo, pedroais, and hyh_

The `Streaming` contract allows recovering the reward token by calling `recoverTokens(rewardToken, recipient)`.

However, the excess amount is computed incorrectly as `ERC20(token).balanceOf(address(this)) - (rewardTokenAmount + rewardTokenFeeAmount)`:

```solidity
function recoverTokens(address token, address recipient) public lock {
    if (token == rewardToken) {
        require(block.timestamp > endRewardLock, "time");

        // check what isnt claimable by depositors and governance
        // @audit-issue rewardTokenAmount increased on fundStream, but never decreased! this excess underflows
        uint256 excess = ERC20(token).balanceOf(address(this)) - (rewardTokenAmount + rewardTokenFeeAmount);
        ERC20(token).safeTransfer(recipient, excess);

        emit RecoveredTokens(token, recipient, excess);
        return;
    }
    // ...
```

Note that `rewardTokenAmount` only ever *increases* (when calling `fundStream`) but it never decreases when claiming the rewards through `claimReward`.
However, `claimReward` transfers out the reward token.

Therefore, the `rewardTokenAmount` never tracks the contract's reward balance and the excess cannot be computed that way.

###
