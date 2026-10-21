pragma solidity ^0.8.0;

library Balances {
    using LibMath for int256;
    using LibMath for uint256;
    using PRBMathSD59x18 for int256;
    using PRBMathUD60x18 for uint256;

    uint256 public constant MAX_DECIMALS = 18;

    struct Position {
        int256 quote;
        int256 base;
    }

    struct Trade {
        uint256 price;
        uint256 amount;
        Perpetuals.Side side;
    }

    struct Account {
        Position position;
        uint256 totalLeveragedValue;
        uint256 lastUpdatedIndex;
        uint256 lastUpdatedGasPrice;
    }

    function applyTrade(Position memory position, Trade memory trade, uint256 feeRate) internal pure returns (Position memory) {
        int256 signedAmount = LibMath.toInt256(trade.amount);
        int256 signedPrice = LibMath.toInt256(trade.price);
        int256 quoteChange = PRBMathSD59x18.mul(signedAmount, signedPrice);
        int256 fee = getFee(trade.amount, trade.price, feeRate);

        int256 newQuote = 0;
        int256 newBase = 0;

        if (trade.side == Perpetuals.Side.Long) {
            newBase = position.base + signedAmount;
            newQuote = position.quote - quoteChange + fee;
        } else if (trade.side == Perpetuals.Side.Short) {
            newBase = position.base - signedAmount;
            newQuote = position.quote + quoteChange - fee;
        }

        Position memory newPosition = Position(newQuote, newBase);

        return newPosition;
    }

    function getFee(uint256 amount, uint256 executionPrice, uint256 feeRate) internal pure returns (int256) {
        uint256 quoteChange = PRBMathUD60x18.mul(amount, executionPrice);

        int256 fee = PRBMathUD60x18.mul(quoteChange, feeRate).toInt256();
        return fee;
    }

}
