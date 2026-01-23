# H-05: Users will lose a majority or even all of the rewards when the amount of total shares is too large

**Contest**: 97
**Reference**: due to precision loss"

## Bug Report

## [[H-05] Users will lose a majority or even all of the rewards when the amount of total shares is too large, due to precision loss](https://github.com/code-423n4/2022-03-biconomy-findings/issues/140)
_Submitted by WatchPug, also found by hyh_

[LiquidityFarming.sol#L265-L291](https://github.com/code-423n4/2022-03-biconomy/blob/db8a1fdddd02e8cc209a4c73ffbb3de210e4a81a/contracts/hyphen/LiquidityFarming.sol#L265-L291)<br>

```solidity
function getUpdatedAccTokenPerShare(address _baseToken) public view returns (uint256) {
    uint256 accumulator = 0;
    uint256 lastUpdatedTime = poolInfo[_baseToken].lastRewardTime;
    uint256 counter = block.timestamp;
    uint256 i = rewardRateLog[_baseToken].length - 1;
    while (true) {
        if (lastUpdatedTime >= counter) {
            break;
        }
        unchecked {
            accumulator +=
                rewardRateLog[_baseToken][i].rewardsPerSecond *
                (counter - max(lastUpdatedTime, rewardRateLog[_baseToken][i].timestamp));
        }
        counter = rewardRateLog[_baseToken][i].timestamp;
        if (i == 0) {
            break;
        }
        --i;
    }

    // We know that during all the periods that were included in the current iterations,
    // the value of totalSharesStaked[_baseToken] would not have changed, as we only consider the
    // updates to the pool that happened after the lastUpdatedTime.
    accumulator = (accumulator * ACC_TOKEN_PRECISION) / totalSharesStaked[_baseToken];
    return accumulator + poolInfo[_baseToken].accTokenPerShare;
}
```

[LiquidityProviders.sol#L286-L292](https://github.com/code-423n4/2022-03-biconomy/blob/04751283f85c9fc94fb644ff2b489ec339cd9ffc/contracts/hyphen/LiquidityProviders.sol#L286-L292)<br>

```solidity
uint256 mintedSharesAmount;
// Adding liquidity in the pool for the first time
if (totalReserve[token] == 0) {
    mintedSharesAmount = BASE_DIVISOR * _amount;
} else {
    mintedSharesAmount = (_amount * totalSharesMinted[token]) / totalReserve[token];
}
```

In `HyphenLiquidityFarming`, the `accTokenPerShare` is calculated based on the total staked shares.

However, as the `mintedSharesAmount` can easily become very large on `LiquidityProviders.sol`, all the users can lose their rewards due to precision loss.

##
