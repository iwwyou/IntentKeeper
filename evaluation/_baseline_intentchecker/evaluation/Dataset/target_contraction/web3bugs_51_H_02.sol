pragma solidity 0.6.12;

library SwapUtils {
    using SafeERC20 for IERC20;
    using SafeMath for uint256;
    using MathUtils for uint256;

    struct Swap {
        uint256 initialA;
        uint256 futureA;
        uint256 initialATime;
        uint256 futureATime;
        uint256 initialA2;
        uint256 futureA2;
        uint256 initialA2Time;
        uint256 futureA2Time;
        uint256 swapFee;
        uint256 adminFee;
        uint256 defaultWithdrawFee;
        LPToken lpToken;
        IERC20[] pooledTokens;
        uint256[] tokenPrecisionMultipliers;
        uint256[] balances;
        mapping(address => uint256) depositTimestamp;
        mapping(address => uint256) withdrawFeeMultiplier;
    }

    struct TargetPrice {
        uint256 initialTargetPrice;
        uint256 futureTargetPrice;
        uint256 initialTargetPriceTime;
        uint256 futureTargetPriceTime;

        uint256[2] originalPrecisionMultipliers;
    }

    struct CalculateWithdrawOneTokenDYInfo {
        uint256 d0;
        uint256 d1;
        uint256 newY;
        uint256 feePerToken;
        uint256 preciseA;
    }

    struct AddLiquidityInfo {
        uint256 d0;
        uint256 d1;
        uint256 d2;
        uint256 preciseA;
    }

    struct RemoveLiquidityImbalanceInfo {
        uint256 d0;
        uint256 d1;
        uint256 d2;
        uint256 preciseA;
    }

    uint256 private constant WEI_UNIT = 10**18;

    uint8 public constant POOL_PRECISION_DECIMALS = 18;

    uint256 private constant FEE_DENOMINATOR = 10**10;

    uint256 public constant MAX_SWAP_FEE = 10**8;

    uint256 public constant MAX_ADMIN_FEE = 10**10;

    uint256 public constant MAX_WITHDRAW_FEE = 10**8;

    uint256 private constant MAX_LOOP_LIMIT = 256;

    uint256 public constant TARGET_PRICE_PRECISION = 1;
    uint256 public constant A_PRECISION = 100;
    uint256 public constant MAX_A = 10**6;
    uint256 private constant MAX_A_CHANGE = 2;
    uint256 private constant MAX_RELATIVE_PRICE_CHANGE = 10**16;
    uint256 private constant MIN_RAMP_TIME = 14 days;

    function _getTargetPricePrecise(TargetPrice storage self) internal view returns (uint256) {
        uint256 t1 = self.futureTargetPriceTime;
        uint256 a1 = self.futureTargetPrice;
        uint256 newTargetPrice;

        if (block.timestamp < t1) {
            uint256 t0 = self.initialTargetPriceTime;
            uint256 a0 = self.initialTargetPrice;
            if (a1 > a0) {
                newTargetPrice = a0.add(a1.sub(a0).mul(block.timestamp.sub(t0)).div(t1.sub(t0)));
            } else {
                newTargetPrice = a0.sub(a0.sub(a1).mul(block.timestamp.sub(t0)).div(t1.sub(t0)));
            }
        } else {
            newTargetPrice = a1;
        }

        return newTargetPrice;
    }

    function rampTargetPrice(
        TargetPrice storage self,
        uint256 futureTargetPrice_,
        uint256 futureTime_
    ) external returns (uint256) {
        require(block.timestamp >= self.initialTargetPriceTime.add(1 days), "Wait 1 day before starting ramp");
        require(futureTime_ >= block.timestamp.add(MIN_RAMP_TIME), "Insufficient ramp time");
        require(futureTargetPrice_ >= 0, "futureTargetPrice_ must be >= 0");

        uint256 initialTargetPricePrecise = _getTargetPricePrecise(self);
        uint256 futureTargetPricePrecise = futureTargetPrice_.mul(TARGET_PRICE_PRECISION);

        if (futureTargetPricePrecise < initialTargetPricePrecise) {
            require(futureTargetPricePrecise.mul(MAX_RELATIVE_PRICE_CHANGE).div(WEI_UNIT) >= initialTargetPricePrecise, "futureTargetPrice_ is too small");
        } else {
            require(futureTargetPricePrecise <= initialTargetPricePrecise.mul(MAX_RELATIVE_PRICE_CHANGE).div(WEI_UNIT), "futureTargetPrice_ is too large");
        }

        self.initialTargetPrice = initialTargetPricePrecise;
        self.futureTargetPrice = futureTargetPricePrecise;
        self.initialTargetPriceTime = block.timestamp;
        self.futureTargetPriceTime = futureTime_;

        return self.originalPrecisionMultipliers[0].mul(initialTargetPricePrecise).div(WEI_UNIT);
    }    
}
