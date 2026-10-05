pragma solidity ^0.6.12;

library BoringMath {
    function mul(uint256 a, uint256 b) internal pure returns (uint256 c) {
        c = a * b;
        require(a == 0 || c / a == b, "BoringMath: Mul Overflow");
    }
}
