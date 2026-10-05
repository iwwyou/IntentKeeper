pragma solidity =0.8.9;

library UniswapV2OracleLibrary {

    function currentBlockTimestamp() internal view returns (uint32) {
        return uint32(block.timestamp % 2**32);
    }

    function currentCumulativePrices(address pair) internal view returns (uint256 price0Cumulative, uint256 price1Cumulative, uint32 blockTimestamp) {
        blockTimestamp = currentBlockTimestamp();
    }
}
