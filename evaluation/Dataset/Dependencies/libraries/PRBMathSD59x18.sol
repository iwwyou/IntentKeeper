pragma solidity >=0.8.0;

library PRBMathSD59x18 {
    int256 internal constant LOG2_E = 1442695040888963407;

    int256 internal constant HALF_SCALE = 5e17;

    int256 internal constant MAX_SD59x18 = 57896044618658097711785492504343953926634992332820282019728792003956564819967;

    int256 internal constant MAX_WHOLE_SD59x18 = 57896044618658097711785492504343953926634992332820282019728000000000000000000;

    int256 internal constant MIN_SD59x18 = -57896044618658097711785492504343953926634992332820282019728792003956564819968;

    int256 internal constant MIN_WHOLE_SD59x18 = -57896044618658097711785492504343953926634992332820282019728000000000000000000;

    int256 internal constant SCALE = 1e18;

    function abs(int256 x) internal pure returns (int256 result) {
        unchecked {
            require(x > MIN_SD59x18);
            result = x < 0 ? -x : x;
        }
    }

    function avg(int256 x, int256 y) internal pure returns (int256 result) {
        unchecked {
            result = (x >> 1) + (y >> 1) + (x & y & 1);
        }
    }

    function ceil(int256 x) internal pure returns (int256 result) {
        require(x <= MAX_WHOLE_SD59x18);
        unchecked {
            int256 remainder = x % SCALE;
            if (remainder == 0) {
                result = x;
            } else {
                result = x - remainder;
                if (x > 0) {
                    result += SCALE;
                }
            }
        }
    }

    function div(int256 x, int256 y) internal pure returns (int256 result) {
        require(x > type(int256).min);
        require(y > type(int256).min);

        uint256 ax;
        uint256 ay;
        unchecked {
            ax = x < 0 ? uint256(-x) : uint256(x);
            ay = y < 0 ? uint256(-y) : uint256(y);
        }

        uint256 resultUnsigned = PRBMathCommon.mulDiv(ax, uint256(SCALE), ay);
        require(resultUnsigned <= uint256(type(int256).max));

        uint256 sx;
        uint256 sy;
        assembly {
            sx := sgt(x, sub(0, 1))
            sy := sgt(y, sub(0, 1))
        }

        result = sx ^ sy == 1 ? -int256(resultUnsigned) : int256(resultUnsigned);
    }

    function e() internal pure returns (int256 result) {
        result = 2718281828459045235;
    }

    function exp(int256 x) internal pure returns (int256 result) {
        if (x < -41446531673892822322) {
            return 0;
        }

        require(x < 88722839111672999628);

        unchecked {
            int256 doubleScaleProduct = x * LOG2_E;
            result = exp2((doubleScaleProduct + HALF_SCALE) / SCALE);
        }
    }

    function exp2(int256 x) internal pure returns (int256 result) {
        if (x < 0) {
            if (x < -59794705707972522261) {
                return 0;
            }

            unchecked {
                result = 1e36 / exp2(-x);
            }
        } else {
            require(x < 128e18);

            unchecked {
                uint256 x128x128 = (uint256(x) << 128) / uint256(SCALE);

                result = int256(PRBMathCommon.exp2(x128x128));
            }
        }
    }

    function floor(int256 x) internal pure returns (int256 result) {
        require(x >= MIN_WHOLE_SD59x18);
        unchecked {
            int256 remainder = x % SCALE;
            if (remainder == 0) {
                result = x;
            } else {
                result = x - remainder;
                if (x < 0) {
                    result -= SCALE;
                }
            }
        }
    }

    function frac(int256 x) internal pure returns (int256 result) {
        unchecked {
            result = x % SCALE;
        }
    }

    function fromInt(int256 x) internal pure returns (int256 result) {
        unchecked {
            require(x >= MIN_SD59x18 / SCALE && x <= MAX_SD59x18 / SCALE);
            result = x * SCALE;
        }
    }

    function gm(int256 x, int256 y) internal pure returns (int256 result) {
        if (x == 0) {
            return 0;
        }

        unchecked {
            int256 xy = x * y;
            require(xy / x == y);

            require(xy >= 0);

            result = int256(PRBMathCommon.sqrt(uint256(xy)));
        }
    }

    function inv(int256 x) internal pure returns (int256 result) {
        unchecked {
            result = 1e36 / x;
        }
    }

    function ln(int256 x) internal pure returns (int256 result) {
        unchecked {
            result = (log2(x) * SCALE) / LOG2_E;
        }
    }

    function log10(int256 x) internal pure returns (int256 result) {
        require(x > 0);

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
            default {
                result := MAX_SD59x18
            }
        }

        if (result == MAX_SD59x18) {
            unchecked {
                result = (log2(x) * SCALE) / 332192809488736234;
            }
        }
    }

    function log2(int256 x) internal pure returns (int256 result) {
        require(x > 0);
        unchecked {
            int256 sign;
            if (x >= SCALE) {
                sign = 1;
            } else {
                sign = -1;
                assembly {
                    x := div(1000000000000000000000000000000000000, x)
                }
            }

            uint256 n = PRBMathCommon.mostSignificantBit(uint256(x / SCALE));

            result = int256(n) * SCALE;

            int256 y = x >> n;

            if (y == SCALE) {
                return result * sign;
            }

            for (int256 delta = int256(HALF_SCALE); delta > 0; delta >>= 1) {
                y = (y * y) / SCALE;

                if (y >= 2 * SCALE) {
                    result += delta;

                    y >>= 1;
                }
            }
            result *= sign;
        }
    }

    function mul(int256 x, int256 y) internal pure returns (int256 result) {
        require(x > MIN_SD59x18);
        require(y > MIN_SD59x18);

        unchecked {
            uint256 ax;
            uint256 ay;
            ax = x < 0 ? uint256(-x) : uint256(x);
            ay = y < 0 ? uint256(-y) : uint256(y);

            uint256 resultUnsigned = PRBMathCommon.mulDivFixedPoint(ax, ay);
            require(resultUnsigned <= uint256(MAX_SD59x18));

            uint256 sx;
            uint256 sy;
            assembly {
                sx := sgt(x, sub(0, 1))
                sy := sgt(y, sub(0, 1))
            }
            result = sx ^ sy == 1 ? -int256(resultUnsigned) : int256(resultUnsigned);
        }
    }

    function pi() internal pure returns (int256 result) {
        result = 3141592653589793238;
    }

    function pow(int256 x, int256 y) internal pure returns (int256 result) {
        if (x == 0) {
            return y == 0 ? SCALE : int256(0);
        } else {
            result = exp2(mul(log2(x), y));
        }
    }

    function powu(int256 x, uint256 y) internal pure returns (int256 result) {
        uint256 absX = uint256(abs(x));

        uint256 absResult = y & 1 > 0 ? absX : uint256(SCALE);

        for (y >>= 1; y > 0; y >>= 1) {
            absX = PRBMathCommon.mulDivFixedPoint(absX, absX);

            if (y & 1 > 0) {
                absResult = PRBMathCommon.mulDivFixedPoint(absResult, absX);
            }
        }

        require(absResult <= uint256(MAX_SD59x18));

        bool isNegative = x < 0 && y & 1 == 1;
        result = isNegative ? -int256(absResult) : int256(absResult);
    }

    function scale() internal pure returns (int256 result) {
        result = SCALE;
    }

    function sqrt(int256 x) internal pure returns (int256 result) {
        require(x >= 0);
        require(x < 57896044618658097711785492504343953926634992332820282019729);
        unchecked {
            result = int256(PRBMathCommon.sqrt(uint256(x * SCALE)));
        }
    }

    function toInt(int256 x) internal pure returns (int256 result) {
        unchecked {
            result = x / SCALE;
        }
    }
}
