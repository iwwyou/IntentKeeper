pragma solidity ^0.8.0;

struct TokenPrice {
    uint256 blockLastUpdated;
    uint256 tokenPer1k;
    address[] liquidationPairs;
    address[] inverseLiquidationPairs;
    address[] liquidationTokens;
    address[] inverseLiquidationTokens;
}

abstract contract PriceAware is RoleAware {
    address public immutable peg;
    mapping(address => TokenPrice) public tokenPrices;
    uint16 public priceUpdateWindow = 8;
    uint256 public UPDATE_RATE_PERMIL = 80;
    uint256 public UPDATE_MAX_PEG_AMOUNT = 50_000;
    uint256 public UPDATE_MIN_PEG_AMOUNT = 1_000;

    function _setPriceVal(
        TokenPrice storage tokenPrice,
        uint256 inAmount,
        uint256 outAmount,
        uint256 weightPerMil
    ) internal {
        uint256 updatePer1k = (1000 ether * inAmount) / (outAmount + 1);
        tokenPrice.tokenPer1k =
            (tokenPrice.tokenPer1k *
                (1000 - weightPerMil) +
                updatePer1k *
                weightPerMil) /
            1000;
    }

    function setPriceVal(
        TokenPrice storage tokenPrice,
        uint256 inAmount,
        uint256 outAmount
    ) internal {
        _setPriceVal(tokenPrice, inAmount, outAmount, UPDATE_RATE_PERMIL);
        tokenPrice.blockLastUpdated = block.number;
    }

    function viewCurrentPriceInPeg(address token, uint256 inAmount)
        public
        view
        returns (uint256)
    {
        if (token == peg) {
            return inAmount;
        } else {
            TokenPrice storage tokenPrice = tokenPrices[token];
            uint256[] memory pathAmounts =
                UniswapStyleLib.getAmountsOut(
                    inAmount,
                    tokenPrice.liquidationPairs,
                    tokenPrice.liquidationTokens
                );
            uint256 outAmount = pathAmounts[pathAmounts.length - 1];
            return outAmount;
        }
    }

    function getPriceFromAMM(address token, uint256 inAmount)
        internal
        virtual
        returns (uint256)
    {
        if (token == peg) {
            return inAmount;
        } else {
            TokenPrice storage tokenPrice = tokenPrices[token];
            uint256[] memory pathAmounts =
                UniswapStyleLib.getAmountsOut(
                    inAmount,
                    tokenPrice.liquidationPairs,
                    tokenPrice.liquidationTokens
                );
            uint256 outAmount = pathAmounts[pathAmounts.length - 1];

            if (
                outAmount > UPDATE_MIN_PEG_AMOUNT &&
                outAmount < UPDATE_MAX_PEG_AMOUNT
            ) {
                setPriceVal(tokenPrice, inAmount, outAmount);
            }

            return outAmount;
        }
    }

    function getCurrentPriceInPeg(
        address token,
        uint256 inAmount,
        bool forceCurBlock
    ) public returns (uint256) {
        TokenPrice storage tokenPrice = tokenPrices[token];
        if (forceCurBlock) {
            if (
                block.number - tokenPrice.blockLastUpdated > priceUpdateWindow
            ) {
                return getPriceFromAMM(token, inAmount);
            } else {
                return viewCurrentPriceInPeg(token, inAmount);
            }
        } else if (tokenPrice.tokenPer1k == 0) {
            return getPriceFromAMM(token, inAmount);
        }

        if (block.number - tokenPrice.blockLastUpdated > priceUpdateWindow) {
            getPriceFromAMM(token, inAmount);
        }

        return (inAmount * 1000 ether) / tokenPrice.tokenPer1k;
    }
}
