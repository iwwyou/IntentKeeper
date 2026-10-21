pragma solidity 0.8.9;

interface IBkdToken is IERC20 {
    function mint(address account, uint256 amount) external;
}
