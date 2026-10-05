pragma solidity >=0.8.0;

interface IBentoBoxMinimal {
    function balanceOf(address, address) external view returns (uint256);

    function toAmount(
        address token,
        uint256 share,
        bool roundUp
    ) external view returns (uint256 amount);

    function withdraw(
        address token_,
        address from,
        address to,
        uint256 amount,
        uint256 share
    ) external returns (uint256 amountOut, uint256 shareOut);

    function transfer(
        address token,
        address from,
        address to,
        uint256 share
    ) external;
}
