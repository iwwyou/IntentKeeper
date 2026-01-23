# H-06: Incorrect calculation of new price while adding position

**Contest**: 192
**Reference**: https://code4rena.com/reports/2022-12-tigris#h-06-incorrect-calculation-of-new-price-while-adding-position

## Bug Report

## [[H-06] Incorrect calculation of new price while adding position](https://github.com/code-423n4/2022-12-tigris-findings/issues/236)
*Submitted by [KingNFT](https://github.com/code-423n4/2022-12-tigris-findings/issues/236)*

The formula used for calculating `_newPrice` in `addToPosition()` function of Trading.sol is not correct, users will lose part of their funds/profit while using this function.

The wrong formula

    uint _newPrice = _trade.price*_trade.margin/_newMargin + _price*_addMargin/_newMargin;

The correct formula is

    uint _newPrice = _trade.price * _price * _newMargin /  (_trade.margin * _price + _addMargin * _trade.price);

Why this works?

Given

    P1 = _trade.price
    P2 = _price
    P = _newPrice
    M1 = _trade.margin
    M2 = _addMargin
    M =  M1 + M2 = _newMargin
    L = _trade.leverage
    U1 = M1 * L  = old position in USD
    U2 = M2 * L = new position in USD
    U = U1 + U2 = total position in USD
    E1 = U1 / P1 = old position of base asset, such as ETH, of the pair
    E2 = U2 / P2 = new position of base asset of the pair
    E = E1 + E2 = total position of base asset of the pair

Then

    P = U / E
      = (U1 + U2) / (E1 + E2)
      = (M1 * L + M2 * L) / (U1 / P1 + U2 / P2)
      = P1 * P2 * (M1 * L + M2 * L) / (U1 * P2 + U2 * P1)
      = P1 * P2 * (M1 + M2) * L / (M1 * L * P2 + M2 * L * P1)
      = P1 * P2 * (M1 + M2) * L / [(M1 * P2 + M2 * P1) * L]
      = P1 * P2 * M / (M1 * P2 + M2 * P1)

proven.

##
