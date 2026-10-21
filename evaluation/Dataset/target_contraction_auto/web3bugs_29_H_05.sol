pragma solidity >=0.8.0;

contract HybridPool is IPool, TridentERC20 {
    using MathUtils for uint256;

    uint256 internal constant MINIMUM_LIQUIDITY = 10**3;
    uint8 internal constant PRECISION = 112;

    uint256 private constant MAX_LOOP_LIMIT = 256;
    uint256 internal constant MAX_FEE = 10000;
    uint256 public immutable swapFee;

    address public immutable barFeeTo;
    address public immutable bento;
    address public immutable masterDeployer;
    address public immutable token0;
    address public immutable token1;
    uint256 public immutable A;
    uint256 internal immutable N_A;
    uint256 internal constant A_PRECISION = 100;

    uint256 public immutable token0PrecisionMultiplier;
    uint256 public immutable token1PrecisionMultiplier;

    uint256 public barFee;

    uint128 internal reserve0;
    uint128 internal reserve1;

    bytes32 public constant override poolIdentifier = "Trident:HybridPool";

    uint256 internal unlocked;

    function _nonOptimalMintFee(uint256 _amount0, uint256 _amount1, uint256 _reserve0, uint256 _reserve1) internal view returns (uint256 token0Fee, uint256 token1Fee) {
        if (_reserve0 == 0 || _reserve1 == 0) {
            return (0, 0);
        }
        uint256 amount1Optimal = (_amount0 * _reserve1) / _reserve0;

        if (amount1Optimal <= _amount1) {
            token1Fee = (swapFee * (_amount1 - amount1Optimal)) / (2 * MAX_FEE);
        } else {
            uint256 amount0Optimal = (_amount1 * _reserve0) / _reserve1;
            token0Fee = (swapFee * (_amount0 - amount0Optimal)) / (2 * MAX_FEE);
        }
    }

}
