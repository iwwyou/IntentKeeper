pragma solidity >=0.8.0;

library MathUtils {
    function within1(uint256 a, uint256 b) internal pure returns (bool wn) {
        wn = difference(a, b) <= 1;
    }

    function difference(uint256 a, uint256 b) internal pure returns (uint256 diff) {
        unchecked {
            if (a > b) {
                diff = a - b;
            }
            diff = b - a;
        }
    }
}
