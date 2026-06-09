pragma solidity =0.8.9;

interface IVaderPoolV2 {
    function cumulativePrices(address foreignAsset) external view returns (uint256 price0CumulativeLast, uint256 price1CumulativeLast, uint32 blockTimestampLast);
    function mintSynth(address foreignAsset, uint256 nativeDeposit, address sender, address to) external returns (uint256 amountSynth);
    function burnSynth(address foreignAsset, uint256 synthAmount, address to) external returns (uint256 amountNative);
    function mintFungible(address foreignAsset, uint256 nativeDeposit, uint256 foreignDeposit, address sender, address to) external returns (uint256 liquidity);
    function burnFungible(address foreignAsset, uint256 liquidity, address to) external returns (uint256 amountNative, uint256 amountForeign);
    function burn(uint256 id, address to) external returns (uint256 amountNative, uint256 amountForeign, uint256 coveredLoss);
    function setQueue(bool _queueActive) external;
    function setTokenSupport(address foreignAsset, bool support, uint256 nativeDeposit, uint256 foreignDeposit, address sender, address to) external returns (uint256 liquidity);
    function setFungibleTokenSupport(address foreignAsset) external;
    function setGasThrottle(bool _gasThrottleEnabled) external;
}
