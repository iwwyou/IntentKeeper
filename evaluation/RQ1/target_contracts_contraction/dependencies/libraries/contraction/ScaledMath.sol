pragma solidity 0.8.9;

library ScaledMath {
    uint256 internal constant DECIMAL_SCALE = 1e18;
    uint256 internal constant ONE = 1e18;

    function scaledMul(uint256 a, uint256 b) internal pure returns (uint256) {
        return (a * b) / DECIMAL_SCALE;
    }

    function scaledDiv(uint256 a, uint256 b) internal pure returns (uint256) {
        return (a * DECIMAL_SCALE) / b;
    }

    function scaledDivRoundUp(uint256 a, uint256 b) internal pure returns (uint256) {
        return (a * DECIMAL_SCALE + b - 1) / b;
    }

    function divRoundUp(uint256 a, uint256 b) internal pure returns (uint256) {
        return (a + b - 1) / b;
    }
}
