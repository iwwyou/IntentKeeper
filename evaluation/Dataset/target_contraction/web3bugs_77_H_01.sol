pragma solidity 0.8.4;

library MathLib {
    struct InternalBalances {
        uint256 baseTokenReserveQty;
        uint256 quoteTokenReserveQty;
        uint256 kLast;
    }

    struct TokenQtys {
        uint256 baseTokenQty;
        uint256 quoteTokenQty;
        uint256 liquidityTokenQty;
        uint256 liquidityTokenFeeQty;
    }

    uint256 public constant BASIS_POINTS = 10000;
    uint256 public constant WAD = 10**18;

    function wDiv(uint256 a, uint256 b) public pure returns (uint256) {
        return ((a * WAD) + (b / 2)) / b;
    }

    function wMul(uint256 a, uint256 b) public pure returns (uint256) {
        return ((a * b) + (WAD / 2)) / WAD;
    }   

    function calculateLiquidityTokenQtyForSingleAssetEntry(
        uint256 _totalSupplyOfLiquidityTokens,
        uint256 _tokenQtyAToAdd,
        uint256 _internalTokenAReserveQty,
        uint256 _tokenBDecayChange,
        uint256 _tokenBDecay
    ) public pure returns (uint256 liquidityTokenQty) {
        uint256 wGamma = wDiv((wMul(wDiv(_tokenQtyAToAdd, _internalTokenAReserveQty),_tokenBDecayChange * WAD)),_tokenBDecay) / WAD / 2;

        liquidityTokenQty = wDiv(wMul(_totalSupplyOfLiquidityTokens * WAD, wGamma), WAD - wGamma) / WAD;
    }   
}
