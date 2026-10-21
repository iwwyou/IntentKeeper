pragma solidity >=0.6.0 <0.7.0;

contract Buoy3Pool is FixedStablecoins, Controllable, IBuoy, IChainPrice {
    using SafeMath for uint256;
    using SafeERC20 for IERC20;

    uint256 TIME_LIMIT = 3000;
    uint256 public BASIS_POINTS = 20;
    uint256 constant CHAIN_FACTOR = 100;

    ICurve3Pool public immutable override curvePool;
    IERC20 public immutable lpToken;

    mapping(uint256 => uint256) lastRatio;

    address public immutable daiUsdAgg;
    address public immutable usdcUsdAgg;
    address public immutable usdtUsdAgg;

    mapping(address => mapping(address => uint256)) public tokenRatios;

    function safetyCheck() external view override returns (bool) {
        for (uint256 i = 1; i < N_COINS; i++) {
            uint256 _ratio = curvePool.get_dy(int128(0), int128(i), getDecimal(0));
            _ratio = abs(int256(_ratio - lastRatio[i]));
            if (_ratio.mul(PERCENTAGE_DECIMAL_FACTOR).div(CURVE_RATIO_DECIMALS_FACTOR) > BASIS_POINTS) {
                return false;
            }
        }
        return true;
    }

    function abs(int256 x) private pure returns (uint256) {
        return x >= 0 ? uint256(x) : uint256(-x);
    }

}
