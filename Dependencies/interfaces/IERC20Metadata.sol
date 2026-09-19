pragma solidity ^0.8.0;

interface IERC20Metadata {
    function decimals() external view returns (uint8);

    function approve(address spender, uint256 amount) external returns (bool);
}
