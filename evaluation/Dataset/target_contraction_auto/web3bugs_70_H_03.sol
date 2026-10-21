pragma solidity =0.8.9;

contract LiquidityBasedTWAP is ILiquidityBasedTWAP, Ownable {

    using FixedPoint for FixedPoint.uq112x112;
    using FixedPoint for FixedPoint.uq144x112;

    address public immutable vader;
    IVaderPoolV2 public immutable vaderPool;

    IUniswapV2Pair[] public vaderPairs;
    IERC20[] public usdvPairs;

    uint256 public override maxUpdateWindow;
    uint256[2] public totalLiquidityWeight;
    uint256[2] public override previousPrices;
    mapping(address => ExchangePair) public twapData;
    mapping(address => IAggregatorV3) public oracles;

    function getChainlinkPrice(address asset) public view returns (uint256) {
        IAggregatorV3 oracle = oracles[asset];

        (uint80 roundID, int256 price, , , uint80 answeredInRound) = oracle.latestRoundData();

        require(answeredInRound >= roundID, "LBTWAP::getChainlinkPrice: Stale Chainlink Price");

        require(price > 0, "LBTWAP::getChainlinkPrice: Chainlink Malfunction");

        return uint256(price);
    }

    function _calculateUSDVPrice(uint256[] memory liquidityWeights, uint256 totalUSDVLiquidityWeight) internal view returns (uint256) {
        uint256 totalUSD;
        uint256 totalUSDV;
        uint256 totalPairs = usdvPairs.length;

        for (uint256 i; i < totalPairs; ++i) {
            IERC20 foreignAsset = usdvPairs[i];
            ExchangePair storage pairData = twapData[address(foreignAsset)];

            uint256 foreignPrice = getChainlinkPrice(address(foreignAsset));

            totalUSD += (foreignPrice * liquidityWeights[i]) / totalUSDVLiquidityWeight;

            totalUSDV += (pairData.nativeTokenPriceAverage.mul(pairData.foreignUnit).decode144() * liquidityWeights[i]) / totalUSDVLiquidityWeight;
        }

        return (totalUSD * 1 ether) / totalUSDV;
    }

}
