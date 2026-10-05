pragma solidity ^0.8.0;

interface IBentoBoxV1 {
    function toShare(IERC20 token, uint256 amount, bool roundUp) external view returns (uint256 share);

    function balanceOf(IERC20 token, address user) external view returns (uint256);

    function transfer(IERC20 token, address from, address to, uint256 share) external;
}
