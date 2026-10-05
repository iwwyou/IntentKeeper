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

        (uint80 roundID, int256 price, , , uint80 answeredInRound) = oracle
            .latestRoundData();

        require(
            answeredInRound >= roundID,
            "LBTWAP::getChainlinkPrice: Stale Chainlink Price"
        );

        require(price > 0, "LBTWAP::getChainlinkPrice: Chainlink Malfunction");

        return uint256(price);
    }

    function _updateVaderPrice(
        IUniswapV2Pair pair,
        ExchangePair storage pairData,
        uint256 timeElapsed
    ) internal returns (uint256 currentLiquidityEvaluation) {
        bool isFirst = pair.token0() == vader;

        (uint256 reserve0, uint256 reserve1, ) = pair.getReserves();

        (uint256 reserveNative, uint256 reserveForeign) = isFirst
            ? (reserve0, reserve1)
            : (reserve1, reserve0);

        (
            uint256 price0Cumulative,
            uint256 price1Cumulative,
            uint256 currentMeasurement
        ) = UniswapV2OracleLibrary.currentCumulativePrices(address(pair));

        uint256 nativeTokenPriceCumulative = isFirst
            ? price0Cumulative
            : price1Cumulative;

        unchecked {
            pairData.nativeTokenPriceAverage = FixedPoint.uq112x112(
                uint224(
                    (nativeTokenPriceCumulative -
                        pairData.nativeTokenPriceCumulative) / timeElapsed
                )
            );
        }

        pairData.nativeTokenPriceCumulative = nativeTokenPriceCumulative;

        pairData.lastMeasurement = currentMeasurement;

        currentLiquidityEvaluation =
            (reserveNative * previousPrices[uint256(Paths.VADER)]) +
            (reserveForeign * getChainlinkPrice(pairData.foreignAsset));
    }

    function syncVaderPrice()
        public
        override
        returns (
            uint256[] memory pastLiquidityWeights,
            uint256 pastTotalLiquidityWeight
        )
    {
        uint256 _totalLiquidityWeight;
        uint256 totalPairs = vaderPairs.length;
        pastLiquidityWeights = new uint256[](totalPairs);
        pastTotalLiquidityWeight = totalLiquidityWeight[uint256(Paths.VADER)];

        for (uint256 i; i < totalPairs; ++i) {
            IUniswapV2Pair pair = vaderPairs[i];
            ExchangePair storage pairData = twapData[address(pair)];
            uint256 timeElapsed = block.timestamp - pairData.lastMeasurement;

            if (timeElapsed < pairData.updatePeriod) {
                continue;
            }

            uint256 pastLiquidityEvaluation = pairData.pastLiquidityEvaluation;
            uint256 currentLiquidityEvaluation = _updateVaderPrice(
                pair,
                pairData,
                timeElapsed
            );

            pastLiquidityWeights[i] = pastLiquidityEvaluation;

            pairData.pastLiquidityEvaluation = currentLiquidityEvaluation;

            _totalLiquidityWeight += currentLiquidityEvaluation;
        }

        totalLiquidityWeight[uint256(Paths.VADER)] = _totalLiquidityWeight;
    }    
}
