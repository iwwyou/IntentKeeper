pragma solidity 0.8.1;

contract CompositeMultiOracle is IOracle, AccessControl {
    using CastBytes32Bytes6 for bytes32;

    uint8 public constant override decimals = 18;

    struct Source {
        address source;
        uint8 decimals;
    }

    mapping(bytes6 => mapping(bytes6 => Source)) public sources;
    mapping(bytes6 => mapping(bytes6 => bytes6[])) public paths;

    function peek(bytes32 base, bytes32 quote, uint256 amount) external view virtual override returns (uint256 value, uint256 updateTime) {
        uint256 price = 1e18;
        bytes6 base_ = base.b6();
        bytes6 quote_ = quote.b6();
        bytes6[] memory path = paths[base_][quote_];
        for (uint256 p = 0; p < path.length; p++) {
            (price, updateTime) = _peek(base_, path[p], price, updateTime);
            base_ = path[p];
        }
        (price, updateTime) = _peek(base_, quote_, price, updateTime);
        value = price * amount / 1e18;
    }

    function _peek(bytes6 base, bytes6 quote, uint256 priceIn, uint256 updateTimeIn) private view returns (uint priceOut, uint updateTimeOut) {
        Source memory source = sources[base][quote];
        require (source.source != address(0), "Source not found");
        (priceOut, updateTimeOut) = IOracle(source.source).peek(base, quote, 10 ** source.decimals);
        priceOut = priceIn * priceOut / (10 ** source.decimals);
        updateTimeOut = (updateTimeOut < updateTimeIn) ? updateTimeOut : updateTimeIn;
    }

}
