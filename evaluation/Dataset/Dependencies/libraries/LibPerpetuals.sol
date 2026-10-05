pragma solidity ^0.8.0;

library Perpetuals {
    enum Side {
        Long, Short
    }

    struct Order {
        address maker;
        address market;
        uint256 price;
        uint256 amount;
        Side side;
        uint256 expires;
        uint256 created;
    }

    function orderId(Order memory order) internal pure returns (bytes32) {
        return keccak256(abi.encode(order));
    }

    function calculateAverageExecutionPrice(
        uint256 oldFilledAmount,
        uint256 oldAverage,
        uint256 fillChange,
        uint256 newFillExecutionPrice
    ) internal pure returns (uint256) {
        uint256 oldFactor = PRBMathUD60x18.mul(oldFilledAmount, oldAverage);
        uint256 newFactor = PRBMathUD60x18.mul(fillChange, newFillExecutionPrice);
        uint256 newTotalAmount = oldFilledAmount + fillChange;
        if (newTotalAmount == 0) {
            return 0;
        }
        uint256 average = PRBMathUD60x18.div(oldFactor + newFactor, newTotalAmount);
        return average;
    }

    function calculateTrueMaxLeverage(
        uint256 collateralAmount,
        uint256 poolTarget,
        uint256 defaultMaxLeverage,
        uint256 lowestMaxLeverage,
        uint256 deleveragingCliff,
        uint256 insurancePoolSwitchStage
    ) internal pure returns (uint256) {
        if (poolTarget == 0) {
            return lowestMaxLeverage;
        }
        uint256 percentFull = PRBMathUD60x18.div(collateralAmount, poolTarget);
        percentFull = percentFull * 100;

        if (percentFull >= deleveragingCliff) {
            return defaultMaxLeverage;
        }

        if (percentFull <= insurancePoolSwitchStage) {
            return lowestMaxLeverage;
        }

        if (deleveragingCliff == insurancePoolSwitchStage) {
            return lowestMaxLeverage;
        }

        uint256 gradientNumerator = defaultMaxLeverage - lowestMaxLeverage;
        uint256 gradientDenominator = deleveragingCliff - insurancePoolSwitchStage;
        uint256 maxLeverageNotBumped = PRBMathUD60x18.mul(
            PRBMathUD60x18.div(gradientNumerator, gradientDenominator),
            percentFull
        );
        uint256 b = lowestMaxLeverage -
            PRBMathUD60x18.div(defaultMaxLeverage - lowestMaxLeverage, deleveragingCliff - insurancePoolSwitchStage);
        uint256 realMaxLeverage = maxLeverageNotBumped + b;

        return realMaxLeverage;
    }

    function canMatch(
        Order memory a,
        uint256 aFilled,
        Order memory b,
        uint256 bFilled
    ) internal view returns (bool) {
        uint256 currentTime = block.timestamp;

        bool opposingSides = a.side != b.side;
        bool pricesMatch = a.side == Side.Long ? a.price >= b.price : a.price <= b.price;
        bool marketsMatch = a.market == b.market;
        bool makersDifferent = a.maker != b.maker;
        bool notExpired = currentTime < a.expires && currentTime < b.expires;
        bool notFilled = aFilled < a.amount && bFilled < b.amount;
        bool createdBefore = currentTime >= a.created && currentTime >= b.created;

        return
            pricesMatch && makersDifferent && marketsMatch && opposingSides && notExpired && notFilled && createdBefore;
    }

    function getExecutionPrice(Order memory a, Order memory b) internal pure returns (uint256) {
        bool aIsFirst = a.created <= b.created;
        if (aIsFirst) {
            return a.price;
        } else {
            return b.price;
        }
    }
}
