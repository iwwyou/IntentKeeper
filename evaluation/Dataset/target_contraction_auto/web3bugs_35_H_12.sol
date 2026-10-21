pragma solidity >=0.8.0;

contract ConcentratedLiquidityPool is IPool {
    using Ticks for mapping(int24 => Ticks.Tick);

    event Burn(address indexed sender, uint256 amount0, uint256 amount1, address indexed recipient);

    bytes32 public constant override poolIdentifier = "Trident:ConcentratedLiquidity";

    uint24 internal constant MAX_FEE = 100000;

    uint128 internal immutable MAX_TICK_LIQUIDITY;
    uint24 internal immutable tickSpacing;
    uint24 internal immutable swapFee;

    address internal immutable barFeeTo;
    IBentoBoxMinimal internal immutable bento;
    IMasterDeployer internal immutable masterDeployer;

    address internal immutable token0;
    address internal immutable token1;

    uint128 public liquidity;

    uint160 internal secondsPerLiquidity;
    uint32 internal lastObservation;

    uint256 public feeGrowthGlobal0;
    uint256 public feeGrowthGlobal1;

    uint256 public barFee;

    uint128 internal token0ProtocolFee;
    uint128 internal token1ProtocolFee;

    uint128 internal reserve0;
    uint128 internal reserve1;

    uint160 internal price;
    int24 internal nearestTick;

    uint256 internal unlocked;
    modifier lock() {
        require(unlocked == 1, "LOCKED");
        unlocked = 2;
        _;
        unlocked = 1;
    }

    mapping(int24 => Ticks.Tick) public ticks;
    mapping(address => mapping(int24 => mapping(int24 => Position))) public positions;

    struct Position {
        uint128 liquidity;
        uint256 feeGrowthInside0Last;
        uint256 feeGrowthInside1Last;
    }

    struct SwapCache {
        uint256 feeAmount;
        uint256 totalFeeAmount;
        uint256 protocolFee;
        uint256 feeGrowthGlobal;
        uint256 currentPrice;
        uint256 currentLiquidity;
        uint256 input;
        int24 nextTickToCross;
    }

    struct MintParams {
        int24 lowerOld;
        int24 lower;
        int24 upperOld;
        int24 upper;
        uint256 amount0Desired;
        uint256 amount1Desired;
        bool token0native;
        bool token1native;
        address positionOwner;
        address positionRecipient;
    }

    function burn(bytes calldata data) public override lock returns (IPool.TokenAmount[] memory withdrawnAmounts) {
        (int24 lower, int24 upper, uint128 amount, address recipient, bool unwrapBento) = abi.decode(data, (int24, int24, uint128, address, bool));

        uint160 priceLower = TickMath.getSqrtRatioAtTick(lower);
        uint160 priceUpper = TickMath.getSqrtRatioAtTick(upper);
        uint160 currentPrice = price;

        unchecked {
            if (priceLower < currentPrice && currentPrice < priceUpper) {
                liquidity -= amount;
            }
        }

        (uint256 amount0, uint256 amount1) = _getAmountsForLiquidity(uint256(priceLower), uint256(priceUpper), uint256(currentPrice), uint256(amount));

        (uint256 amount0fees, uint256 amount1fees) = _updatePosition(msg.sender, lower, upper, -int128(amount));

        unchecked {
            amount0 += amount0fees;
            amount1 += amount1fees;
        }

        withdrawnAmounts = new TokenAmount[](2);
        withdrawnAmounts[0] = TokenAmount({token: token0, amount: amount0});
        withdrawnAmounts[1] = TokenAmount({token: token1, amount: amount1});

        unchecked {
            reserve0 -= uint128(amount0fees);
            reserve1 -= uint128(amount1fees);
        }

        _transferBothTokens(recipient, amount0, amount1, unwrapBento);

        nearestTick = Ticks.remove(ticks, lower, upper, amount, nearestTick);
        emit Burn(msg.sender, amount0, amount1, recipient);
    }

    function _getAmountsForLiquidity(uint256 priceLower, uint256 priceUpper, uint256 currentPrice, uint256 liquidityAmount) internal pure returns (uint128 token0amount, uint128 token1amount) {
        if (priceUpper <= currentPrice) {
            token1amount = uint128(DyDxMath.getDy(liquidityAmount, priceLower, priceUpper, true));
        } else if (currentPrice <= priceLower) {
            token0amount = uint128(DyDxMath.getDx(liquidityAmount, priceLower, priceUpper, true));
        } else {
            token0amount = uint128(DyDxMath.getDx(liquidityAmount, currentPrice, priceUpper, true));
            token1amount = uint128(DyDxMath.getDy(liquidityAmount, priceLower, currentPrice, true));
        }
    }

    function _updatePosition(address owner, int24 lower, int24 upper, int128 amount) internal returns (uint256 amount0fees, uint256 amount1fees) {
        Position storage position = positions[owner][lower][upper];

        (uint256 growth0current, uint256 growth1current) = rangeFeeGrowth(lower, upper);
        amount0fees = FullMath.mulDiv(growth0current - position.feeGrowthInside0Last, position.liquidity, 0x100000000000000000000000000000000);

        amount1fees = FullMath.mulDiv(growth1current - position.feeGrowthInside1Last, position.liquidity, 0x100000000000000000000000000000000);

        if (amount < 0) {
            position.liquidity -= uint128(-amount);
        }
        if (amount > 0) {
            position.liquidity += uint128(amount);
        }

        require(position.liquidity < MAX_TICK_LIQUIDITY, "MAX_TICK_LIQUIDITY");

        position.feeGrowthInside0Last = growth0current;
        position.feeGrowthInside1Last = growth1current;
    }

    function _transferBothTokens(address to, uint256 shares0, uint256 shares1, bool unwrapBento) internal {
        if (unwrapBento) {
            bento.withdraw(token0, address(this), to, 0, shares0);
            bento.withdraw(token1, address(this), to, 0, shares1);
        } else {
            bento.transfer(token0, address(this), to, shares0);
            bento.transfer(token1, address(this), to, shares1);
        }
    }

    function rangeFeeGrowth(int24 lowerTick, int24 upperTick) public view returns (uint256 feeGrowthInside0, uint256 feeGrowthInside1) {
        int24 currentTick = nearestTick;

        Ticks.Tick storage lower = ticks[lowerTick];
        Ticks.Tick storage upper = ticks[upperTick];

        uint256 _feeGrowthGlobal0 = feeGrowthGlobal0;
        uint256 _feeGrowthGlobal1 = feeGrowthGlobal1;
        uint256 feeGrowthBelow0;
        uint256 feeGrowthBelow1;
        uint256 feeGrowthAbove0;
        uint256 feeGrowthAbove1;

        if (lowerTick <= currentTick) {
            feeGrowthBelow0 = lower.feeGrowthOutside0;
            feeGrowthBelow1 = lower.feeGrowthOutside1;
        } else {
            feeGrowthBelow0 = _feeGrowthGlobal0 - lower.feeGrowthOutside0;
            feeGrowthBelow1 = _feeGrowthGlobal1 - lower.feeGrowthOutside1;
        }

        if (currentTick < upperTick) {
            feeGrowthAbove0 = upper.feeGrowthOutside0;
            feeGrowthAbove1 = upper.feeGrowthOutside1;
        } else {
            feeGrowthAbove0 = _feeGrowthGlobal0 - upper.feeGrowthOutside0;
            feeGrowthAbove1 = _feeGrowthGlobal1 - upper.feeGrowthOutside1;
        }

        feeGrowthInside0 = _feeGrowthGlobal0 - feeGrowthBelow0 - feeGrowthAbove0;
        feeGrowthInside1 = _feeGrowthGlobal1 - feeGrowthBelow1 - feeGrowthAbove1;
    }

}
