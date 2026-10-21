pragma solidity 0.8.1;

contract CTokenMultiOracle is IOracle, AccessControl, Constants {
    using CastBytes32Bytes6 for bytes32;

    uint8 public constant override decimals = 18;

    event SourceSet(bytes6 indexed baseId, bytes6 indexed quoteId, address indexed source);

    struct Source {
        address source;
        uint8 decimals;
        bool inverse;
    }

    mapping(bytes6 => mapping(bytes6 => Source)) public sources;

    function _setSource(bytes6 cTokenId, bytes6 underlying, address source) internal {
        uint8 decimals_ = 18;
        require (decimals_ <= 18, "Unsupported decimals");
        sources[cTokenId][underlying] = Source({
            source: source, decimals: decimals_, inverse: false
        });
        sources[underlying][cTokenId] = Source({
            source: source, decimals: decimals_, inverse: true
        });
        emit SourceSet(cTokenId, underlying, source);
        emit SourceSet(underlying, cTokenId, source);
    }
}
