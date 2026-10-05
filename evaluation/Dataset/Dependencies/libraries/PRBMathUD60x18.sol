pragma solidity >=0.8.0;

library PRBMathUD60x18 {
    uint256 internal constant HALF_SCALE = 5e17;

    uint256 internal constant LOG2_E = 1442695040888963407;

    uint256 internal constant MAX_UD60x18 = 115792089237316195423570985008687907853269984665640564039457584007913129639935;

    uint256 internal constant MAX_WHOLE_UD60x18 = 115792089237316195423570985008687907853269984665640564039457000000000000000000;

    uint256 internal constant SCALE = 1e18;

    function avg(uint256 x, uint256 y) internal pure returns (uint256 result) {
        unchecked {
            result = (x >> 1) + (y >> 1) + (x & y & 1);
        }
    }

    function ceil(uint256 x) internal pure returns (uint256 result) {
        require(x <= MAX_WHOLE_UD60x18);
        assembly {
            let remainder := mod(x, SCALE)

            let delta := sub(SCALE, remainder)

            result := add(x, mul(delta, gt(remainder, 0)))
        }
    }

    function div(uint256 x, uint256 y) internal pure returns (uint256 result) {
        result = PRBMathCommon.mulDiv(x, SCALE, y);
    }

    function e() internal pure returns (uint256 result) {
        result = 2718281828459045235;
    }

    function exp(uint256 x) internal pure returns (uint256 result) {
        require(x < 88722839111672999628);

        unchecked {
            uint256 doubleScaleProduct = x * LOG2_E;
            result = exp2((doubleScaleProduct + HALF_SCALE) / SCALE);
        }
    }

    function exp2(uint256 x) internal pure returns (uint256 result) {
        require(x < 128e18);

        unchecked {
            uint256 x128x128 = (x << 128) / SCALE;

            result = PRBMathCommon.exp2(x128x128);
        }
    }

    function floor(uint256 x) internal pure returns (uint256 result) {
        assembly {
            let remainder := mod(x, SCALE)

            result := sub(x, mul(remainder, gt(remainder, 0)))
        }
    }

    function frac(uint256 x) internal pure returns (uint256 result) {
        assembly {
            result := mod(x, SCALE)
        }
    }

    function fromUint(uint256 x) internal pure returns (uint256 result) {
        unchecked {
            require(x <= MAX_UD60x18 / SCALE);
            result = x * SCALE;
        }
    }

    function gm(uint256 x, uint256 y) internal pure returns (uint256 result) {
        if (x == 0) {
            return 0;
        }

        unchecked {
            uint256 xy = x * y;
            require(xy / x == y);

            result = PRBMathCommon.sqrt(xy);
        }
    }

    function inv(uint256 x) internal pure returns (uint256 result) {
        unchecked {
            result = 1e36 / x;
        }
    }

    function ln(uint256 x) internal pure returns (uint256 result) {
        unchecked {
            result = (log2(x) * SCALE) / LOG2_E;
        }
    }

    function log10(uint256 x) internal pure returns (uint256 result) {
        require(x >= SCALE);

        assembly {
            switch x
            case 1 { result := mul(SCALE, sub(0, 18)) }
            case 10 { result := mul(SCALE, sub(1, 18)) }
            case 100 { result := mul(SCALE, sub(2, 18)) }
            case 1000 { result := mul(SCALE, sub(3, 18)) }
            case 10000 { result := mul(SCALE, sub(4, 18)) }
            case 100000 { result := mul(SCALE, sub(5, 18)) }
            case 1000000 { result := mul(SCALE, sub(6, 18)) }
            case 10000000 { result := mul(SCALE, sub(7, 18)) }
            case 100000000 { result := mul(SCALE, sub(8, 18)) }
            case 1000000000 { result := mul(SCALE, sub(9, 18)) }
            case 10000000000 { result := mul(SCALE, sub(10, 18)) }
            case 100000000000 { result := mul(SCALE, sub(11, 18)) }
            case 1000000000000 { result := mul(SCALE, sub(12, 18)) }
            case 10000000000000 { result := mul(SCALE, sub(13, 18)) }
            case 100000000000000 { result := mul(SCALE, sub(14, 18)) }
            case 1000000000000000 { result := mul(SCALE, sub(15, 18)) }
            case 10000000000000000 { result := mul(SCALE, sub(16, 18)) }
            case 100000000000000000 { result := mul(SCALE, sub(17, 18)) }
            case 1000000000000000000 { result := 0 }
            case 10000000000000000000 { result := SCALE }
            case 100000000000000000000 { result := mul(SCALE, 2) }
            case 1000000000000000000000 { result := mul(SCALE, 3) }
            case 10000000000000000000000 { result := mul(SCALE, 4) }
            case 100000000000000000000000 { result := mul(SCALE, 5) }
            case 1000000000000000000000000 { result := mul(SCALE, 6) }
            case 10000000000000000000000000 { result := mul(SCALE, 7) }
            case 100000000000000000000000000 { result := mul(SCALE, 8) }
            case 1000000000000000000000000000 { result := mul(SCALE, 9) }
            case 10000000000000000000000000000 { result := mul(SCALE, 10) }
            case 100000000000000000000000000000 { result := mul(SCALE, 11) }
            case 1000000000000000000000000000000 { result := mul(SCALE, 12) }
            case 10000000000000000000000000000000 { result := mul(SCALE, 13) }
            case 100000000000000000000000000000000 { result := mul(SCALE, 14) }
            case 1000000000000000000000000000000000 { result := mul(SCALE, 15) }
            case 10000000000000000000000000000000000 { result := mul(SCALE, 16) }
            case 100000000000000000000000000000000000 { result := mul(SCALE, 17) }
            case 1000000000000000000000000000000000000 { result := mul(SCALE, 18) }
            case 10000000000000000000000000000000000000 { result := mul(SCALE, 19) }
            case 100000000000000000000000000000000000000 { result := mul(SCALE, 20) }
            case 1000000000000000000000000000000000000000 { result := mul(SCALE, 21) }
            case 10000000000000000000000000000000000000000 { result := mul(SCALE, 22) }
            case 100000000000000000000000000000000000000000 { result := mul(SCALE, 23) }
            case 1000000000000000000000000000000000000000000 { result := mul(SCALE, 24) }
            case 10000000000000000000000000000000000000000000 { result := mul(SCALE, 25) }
            case 100000000000000000000000000000000000000000000 { result := mul(SCALE, 26) }
            case 1000000000000000000000000000000000000000000000 { result := mul(SCALE, 27) }
            case 10000000000000000000000000000000000000000000000 { result := mul(SCALE, 28) }
            case 100000000000000000000000000000000000000000000000 { result := mul(SCALE, 29) }
            case 1000000000000000000000000000000000000000000000000 { result := mul(SCALE, 30) }
            case 10000000000000000000000000000000000000000000000000 { result := mul(SCALE, 31) }
            case 100000000000000000000000000000000000000000000000000 { result := mul(SCALE, 32) }
            case 1000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 33) }
            case 10000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 34) }
            case 100000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 35) }
            case 1000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 36) }
            case 10000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 37) }
            case 100000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 38) }
            case 1000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 39) }
            case 10000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 40) }
            case 100000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 41) }
            case 1000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 42) }
            case 10000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 43) }
            case 100000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 44) }
            case 1000000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 45) }
            case 10000000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 46) }
            case 100000000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 47) }
            case 1000000000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 48) }
            case 10000000000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 49) }
            case 100000000000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 50) }
            case 1000000000000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 51) }
            case 10000000000000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 52) }
            case 100000000000000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 53) }
            case 1000000000000000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 54) }
            case 10000000000000000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 55) }
            case 100000000000000000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 56) }
            case 1000000000000000000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 57) }
            case 10000000000000000000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 58) }
            case 100000000000000000000000000000000000000000000000000000000000000000000000000000 { result := mul(SCALE, 59) }
            default {
                result := MAX_UD60x18
            }
        }

        if (result == MAX_UD60x18) {
            unchecked {
                result = (log2(x) * SCALE) / 332192809488736234;
            }
        }
    }

    function log2(uint256 x) internal pure returns (uint256 result) {
        require(x >= SCALE);
        unchecked {
            uint256 n = PRBMathCommon.mostSignificantBit(x / SCALE);

            result = n * SCALE;

            uint256 y = x >> n;

            if (y == SCALE) {
                return result;
            }

            for (uint256 delta = HALF_SCALE; delta > 0; delta >>= 1) {
                y = (y * y) / SCALE;

                if (y >= 2 * SCALE) {
                    result += delta;

                    y >>= 1;
                }
            }
        }
    }

    function mul(uint256 x, uint256 y) internal pure returns (uint256 result) {
        result = PRBMathCommon.mulDivFixedPoint(x, y);
    }

    function pi() internal pure returns (uint256 result) {
        result = 3141592653589793238;
    }

    function pow(uint256 x, uint256 y) internal pure returns (uint256 result) {
        if (x == 0) {
            return y == 0 ? SCALE : uint256(0);
        } else {
            result = exp2(mul(log2(x), y));
        }
    }

    function powu(uint256 x, uint256 y) internal pure returns (uint256 result) {
        result = y & 1 > 0 ? x : SCALE;

        for (y >>= 1; y > 0; y >>= 1) {
            x = PRBMathCommon.mulDivFixedPoint(x, x);

            if (y & 1 > 0) {
                result = PRBMathCommon.mulDivFixedPoint(result, x);
            }
        }
    }

    function scale() internal pure returns (uint256 result) {
        result = SCALE;
    }

    function sqrt(uint256 x) internal pure returns (uint256 result) {
        require(x < 115792089237316195423570985008687907853269984665640564039458);
        unchecked {
            result = PRBMathCommon.sqrt(x * SCALE);
        }
    }

    function toUint(uint256 x) internal pure returns (uint256 result) {
        unchecked {
            result = x / SCALE;
        }
    }
}
