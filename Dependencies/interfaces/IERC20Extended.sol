pragma solidity =0.8.9;

interface IERC20Extended {
    function name() external view returns (string memory);

    function symbol() external view returns (string memory);

    function mint(address to, uint256 amount) external;

    function burn(uint256 amount) external;
}
