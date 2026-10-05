pragma solidity =0.8.9;

interface IBasePoolV2 {
    struct Position {
        address foreignAsset;
        uint256 creation;
        uint256 liquidity;
        uint256 originalNative;
        uint256 originalForeign;
    }

    struct PairInfo {
        uint256 totalSupply;
        uint112 reserveNative;
        uint112 reserveForeign;
        uint32 blockTimestampLast;
    }

    function getReserves(address foreignAsset) external view returns (uint112 reserve0, uint112 reserve1, uint32 blockTimestampLast);
    function nativeAsset() external view returns (address);
    function supported(address token) external view returns (bool);
    function positionForeignAsset(uint256 id) external view returns (address);
    function pairSupply(address foreignAsset) external view returns (uint256);
    function doubleSwap(address foreignAssetA, address foreignAssetB, uint256 foreignAmountIn, address to) external returns (uint256);
    function swap(address foreignAsset, uint256 nativeAmountIn, uint256 foreignAmountIn, address to) external returns (uint256);
    function mint(address foreignAsset, uint256 nativeDeposit, uint256 foreignDeposit, address sender, address to) external returns (uint256 liquidity);
}
