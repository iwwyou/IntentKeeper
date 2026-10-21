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

    function _getReserves() internal view returns (uint256 _reserve0, uint256 _reserve1) {
        (_reserve0, _reserve1) = (reserve0, reserve1);
        _reserve0 = _toAmount(token0, _reserve0);
        _reserve1 = _toAmount(token1, _reserve1);
    }

    function _toAmount(address token, uint256 input) internal view returns (uint256 output) {
        (, bytes memory _output) = bento.staticcall(abi.encodeWithSelector(IBentoBoxMinimal.toAmount.selector, token, input, false));
        output = abi.decode(_output, (uint256));
    }

}
