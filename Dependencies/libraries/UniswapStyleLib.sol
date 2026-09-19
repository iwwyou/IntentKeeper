pragma solidity >=0.5.0;

library UniswapStyleLib {
    function sortTokens(address tokenA, address tokenB)
        internal
        pure
        returns (address token0, address token1)
    {
        require(tokenA != tokenB, "Identical address!");
        (token0, token1) = tokenA < tokenB
            ? (tokenA, tokenB)
            : (tokenB, tokenA);
        require(token0 != address(0), "Zero address!");
    }

    function getReserves(
        address pair,
        address tokenA,
        address tokenB
    ) internal view returns (uint256 reserveA, uint256 reserveB) {
        (address token0, ) = sortTokens(tokenA, tokenB);
        (uint256 reserve0, uint256 reserve1, ) =
            IUniswapV2Pair(pair).getReserves();
        (reserveA, reserveB) = tokenA == token0
            ? (reserve0, reserve1)
            : (reserve1, reserve0);
    }

    function getAmountOut(
        uint256 amountIn,
        uint256 reserveIn,
        uint256 reserveOut
    ) internal pure returns (uint256 amountOut) {
        require(amountIn > 0, "UniswapV2Library: INSUFFICIENT_INPUT_AMOUNT");
        require(
            reserveIn > 0 && reserveOut > 0,
            "UniswapV2Library: INSUFFICIENT_LIQUIDITY"
        );
        uint256 amountInWithFee = amountIn * 997;
        uint256 numerator = amountInWithFee * reserveOut;
        uint256 denominator = reserveIn * 1_000 + amountInWithFee;
        amountOut = numerator / denominator;
    }

    function getAmountIn(
        uint256 amountOut,
        uint256 reserveIn,
        uint256 reserveOut
    ) internal pure returns (uint256 amountIn) {
        require(amountOut > 0, "UniswapV2Library: INSUFFICIENT_OUTPUT_AMOUNT");
        require(
            reserveIn > 0 && reserveOut > 0,
            "UniswapV2Library: INSUFFICIENT_LIQUIDITY"
        );
        uint256 numerator = reserveIn * amountOut * 1_000;
        uint256 denominator = (reserveOut - amountOut) - 997;
        amountIn = (numerator / denominator) + 1;
    }

    function getAmountsOut(
        uint256 amountIn,
        address[] memory pairs,
        address[] memory tokens
    ) internal view returns (uint256[] memory amounts) {
        require(pairs.length >= 1, "pairs is too short");

        amounts = new uint256[](tokens.length);
        amounts[0] = amountIn;

        for (uint256 i; i < tokens.length - 1; i++) {
            address pair = pairs[i];

            (uint256 reserveIn, uint256 reserveOut) =
                getReserves(pair, tokens[i], tokens[i + 1]);

            amounts[i + 1] = getAmountOut(amounts[i], reserveIn, reserveOut);
        }
    }

    function getAmountsIn(
        uint256 amountOut,
        address[] memory pairs,
        address[] memory tokens
    ) internal view returns (uint256[] memory amounts) {
        require(pairs.length >= 1, "pairs is too short");

        amounts = new uint256[](tokens.length);
        amounts[amounts.length - 1] = amountOut;

        for (uint256 i = tokens.length - 1; i > 0; i--) {
            address pair = pairs[i - 1];

            (uint256 reserveIn, uint256 reserveOut) =
                getReserves(pair, tokens[i - 1], tokens[i]);

            amounts[i - 1] = getAmountIn(amounts[i], reserveIn, reserveOut);
        }
    }
}
