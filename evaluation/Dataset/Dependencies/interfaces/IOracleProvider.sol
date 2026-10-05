pragma solidity 0.8.9;

interface IOracleProvider {
    function getPriceUSD(address baseAsset) external view returns (uint256);

    function getPriceETH(address baseAsset) external view returns (uint256);
}
