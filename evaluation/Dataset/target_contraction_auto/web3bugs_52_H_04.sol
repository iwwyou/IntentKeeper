pragma solidity =0.8.9;

contract TwapOracle is Ownable {

    using FixedPoint for *;

    struct PairData {
        address pair;
        address token0;
        address token1;
        uint256 price0CumulativeLast;
        uint256 price1CumulativeLast;
        uint32 blockTimestampLast;
        FixedPoint.uq112x112 price0Average;
        FixedPoint.uq112x112 price1Average;
    }

    address public VADER;

    address public USDV;

    bool private _usdvEnabled;

    mapping(address => address) private _aggregators;

    IVaderPoolV2 private _vaderPool;

    uint256 private _updatePeriod;

    PairData[] private _pairs;

    mapping(bytes32 => bool) private _pairExists;

    function consult(address token) public view returns (uint256 result) {
        uint256 pairCount = _pairs.length;
        uint256 sumNative = 0;
        uint256 sumUSD = 0;

        for (uint256 i = 0; i < pairCount; i++) {
            PairData memory pairData = _pairs[i];

            if (token == pairData.token0) {

                sumNative += pairData.price1Average.mul(1).decode144();
                if (pairData.price1Average._x != 0) {
                    require(sumNative != 0);
                }

                (uint80 roundID, int256 price,,, uint80 answeredInRound) = AggregatorV3Interface(_aggregators[pairData.token1]).latestRoundData();

                require(answeredInRound >= roundID, "TwapOracle::consult: stale chainlink price");
                require(price != 0, "TwapOracle::consult: chainlink malfunction");

                sumUSD += uint256(price) * (10**10);
            }
        }
        require(sumNative != 0, "TwapOracle::consult: Sum of native is zero");
        result = ((sumUSD * IERC20Metadata(token).decimals()) / sumNative);
    }

}
