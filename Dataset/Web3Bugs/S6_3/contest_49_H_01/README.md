# H-01: OverlayV1UniswapV3Market computes wrong market liquidity

**Contest**: 49
**Reference**: https://code4rena.com/reports/2021-11-overlay#h-01-overlayv1uniswapv3market-computes-wrong-market-liquidity

## Bug Report

## [[H-01] `OverlayV1UniswapV3Market` computes wrong market liquidity](https://github.com/code-423n4/2021-11-overlay-findings/issues/83)
_Submitted by cmichel_

The `OverlayV1UniswapV3Market.fetchPricePoint` tries to compute the market depth in OVL terms as `marketLiquidity (in ETH) / ovlPrice (in ETH per OVL)`.
To get the market liquidity *in ETH* (and not the other token pair), it uses the `ethIs0` boolean.

```solidity
_marketLiquidity = ethIs0
    ? ( uint256(_liquidity) << 96 ) / _sqrtPrice
    : FullMath.mulDiv(uint256(_liquidity), _sqrtPrice, X96);
```

However, `ethIs0` boolean refers to the `ovlFeed`, whereas the `_liquidity` refers to the `marketFeed`, and therefore the `ethIs0` boolean has nothing to do with the *market* feed where the liquidity is taken from:

```solidity
// in constructor, if token0 is eth refers to ovlFeed
ethIs0 = IUniswapV3Pool(_ovlFeed).token0() == _eth;

// in fetchPricePoint, _liquidity comes from different market feed
( _ticks, _liqs ) = IUniswapV3Pool(marketFeed).observe(_secondsAgo);
_marketLiquidity = ethIs0
    ? ( uint256(_liquidity) << 96 ) / _sqrtPrice
    : FullMath.mulDiv(uint256(_liquidity), _sqrtPrice, X96);
```

###
