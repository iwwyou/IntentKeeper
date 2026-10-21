pragma solidity >=0.8.0;

contract ConstantProductPool is IPool, TridentERC20 {

    event Burn(address indexed sender, uint256 amount0, uint256 amount1, address indexed recipient);
    event Sync(uint256 reserve0, uint256 reserve1);

    uint256 internal constant MINIMUM_LIQUIDITY = 1000;

    uint8 internal constant PRECISION = 112;
    uint256 internal constant MAX_FEE = 10000;
    uint256 internal constant MAX_FEE_SQUARE = 100000000;
    uint256 internal constant E18 = uint256(10)**18;
    uint256 public immutable swapFee;
    uint256 internal immutable MAX_FEE_MINUS_SWAP_FEE;

    address public immutable barFeeTo;
    address public immutable bento;
    address public immutable masterDeployer;
    address public immutable token0;
    address public immutable token1;

    uint256 public barFee;
    uint256 public price0CumulativeLast;
    uint256 public price1CumulativeLast;
    uint256 public kLast;

    uint112 internal reserve0;
    uint112 internal reserve1;
    uint32 internal blockTimestampLast;

    bytes32 public constant override poolIdentifier = "Trident:ConstantProduct";

    uint256 internal unlocked;
    modifier lock() {
        require(unlocked == 1, "LOCKED");
        unlocked = 2;
        _;
        unlocked = 1;
    }

    function burnSingle(bytes calldata data) public override lock returns (uint256 amountOut) {
        (address tokenOut, address recipient, bool unwrapBento) = abi.decode(data, (address, address, bool));
        (uint112 _reserve0, uint112 _reserve1, uint32 _blockTimestampLast) = _getReserves();
        (uint256 balance0, uint256 balance1) = _balance();
        uint256 _totalSupply = totalSupply;
        uint256 liquidity = balanceOf[address(this)];

        unchecked {
            _totalSupply += _mintFee(_reserve0, _reserve1, _totalSupply);
        }

        uint256 amount0 = (liquidity * balance0) / _totalSupply;
        uint256 amount1 = (liquidity * balance1) / _totalSupply;

        _burn(address(this), liquidity);
        unchecked {
            if (tokenOut == token1) {
                amount1 += _getAmountOut(amount0, _reserve0 - amount0, _reserve1 - amount1);
                _transfer(token1, amount1, recipient, unwrapBento);
                balance1 -= amount1;
                amountOut = amount1;
                amount0 = 0;
            } else {
                require(tokenOut == token0, "INVALID_OUTPUT_TOKEN");
                amount0 += _getAmountOut(amount1, _reserve1 - amount1, _reserve0 - amount0);
                _transfer(token0, amount0, recipient, unwrapBento);
                balance0 -= amount0;
                amountOut = amount0;
                amount1 = 0;
            }
        }
        _update(balance0, balance1, _reserve0, _reserve1, _blockTimestampLast);
        kLast = TridentMath.sqrt(balance0 * balance1);
        emit Burn(msg.sender, amount0, amount1, recipient);
    }

    function _getReserves() internal view returns (uint112 _reserve0, uint112 _reserve1, uint32 _blockTimestampLast) {
        _reserve0 = reserve0;
        _reserve1 = reserve1;
        _blockTimestampLast = blockTimestampLast;
    }

    function _balance() internal view returns (uint256 balance0, uint256 balance1) {
        (, bytes memory _balance0) = bento.staticcall(abi.encodeWithSelector(0xf7888aec, token0, address(this)));
        balance0 = abi.decode(_balance0, (uint256));
        (, bytes memory _balance1) = bento.staticcall(abi.encodeWithSelector(0xf7888aec, token1, address(this)));
        balance1 = abi.decode(_balance1, (uint256));
    }

    function _update(uint256 balance0, uint256 balance1, uint112 _reserve0, uint112 _reserve1, uint32 _blockTimestampLast) internal {
        require(balance0 <= type(uint112).max && balance1 <= type(uint112).max, "OVERFLOW");
        if (blockTimestampLast == 0) {
            reserve0 = uint112(balance0);
            reserve1 = uint112(balance1);
        } else {
            uint32 blockTimestamp = uint32(block.timestamp % 2**32);
            if (blockTimestamp != _blockTimestampLast && _reserve0 != 0 && _reserve1 != 0) {
                unchecked {
                    uint32 timeElapsed = blockTimestamp - _blockTimestampLast;
                    uint256 price0 = (uint256(_reserve1) << PRECISION) / _reserve0;
                    price0CumulativeLast += price0 * timeElapsed;
                    uint256 price1 = (uint256(_reserve0) << PRECISION) / _reserve1;
                    price1CumulativeLast += price1 * timeElapsed;
                }
            }
            reserve0 = uint112(balance0);
            reserve1 = uint112(balance1);
            blockTimestampLast = blockTimestamp;
        }
        emit Sync(balance0, balance1);
    }

    function _mintFee(uint112 _reserve0, uint112 _reserve1, uint256 _totalSupply) internal returns (uint256 liquidity) {
        uint256 _kLast = kLast;
        if (_kLast != 0) {
            uint256 computed = TridentMath.sqrt(uint256(_reserve0) * _reserve1);
            if (computed > _kLast) {
                liquidity = (_totalSupply * (computed - _kLast) * barFee) / computed / MAX_FEE;
                if (liquidity != 0) {
                    _mint(barFeeTo, liquidity);
                }
            }
        }
    }

    function _getAmountOut(uint256 amountIn, uint256 reserveAmountIn, uint256 reserveAmountOut) internal view returns (uint256 amountOut) {
        uint256 amountInWithFee = amountIn * MAX_FEE_MINUS_SWAP_FEE;
        amountOut = (amountInWithFee * reserveAmountOut) / (reserveAmountIn * MAX_FEE + amountInWithFee);
    }

    function _transfer(address token, uint256 shares, address to, bool unwrapBento) internal {
        if (unwrapBento) {
            (bool success, ) = bento.call(abi.encodeWithSelector(0x97da6d30, token, address(this), to, 0, shares));
            require(success, "WITHDRAW_FAILED");
        } else {
            (bool success, ) = bento.call(abi.encodeWithSelector(0xf18d03cc, token, address(this), to, shares));
            require(success, "TRANSFER_FAILED");
        }
    }

}
