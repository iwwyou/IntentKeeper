pragma solidity >=0.8.0;

library PRBMathCommon {
    uint256 internal constant SCALE = 1e18;

    uint256 internal constant SCALE_LPOTD = 262144;

    uint256 internal constant SCALE_INVERSE = 78156646155174841979727994598816262306175212592076161876661508869554232690281;

    function exp2(uint256 x) internal pure returns (uint256 result) {
        unchecked {
            result = 0x80000000000000000000000000000000;

            if (x & 0x80000000000000000000000000000000 > 0) {
                result = (result * 0x16A09E667F3BCC908B2FB1366EA957D3E) >> 128;
            }
            if (x & 0x40000000000000000000000000000000 > 0) {
                result = (result * 0x1306FE0A31B7152DE8D5A46305C85EDED) >> 128;
            }
            if (x & 0x20000000000000000000000000000000 > 0) {
                result = (result * 0x1172B83C7D517ADCDF7C8C50EB14A7920) >> 128;
            }
            if (x & 0x10000000000000000000000000000000 > 0) {
                result = (result * 0x10B5586CF9890F6298B92B71842A98364) >> 128;
            }
            if (x & 0x8000000000000000000000000000000 > 0) {
                result = (result * 0x1059B0D31585743AE7C548EB68CA417FE) >> 128;
            }
            if (x & 0x4000000000000000000000000000000 > 0) {
                result = (result * 0x102C9A3E778060EE6F7CACA4F7A29BDE9) >> 128;
            }
            if (x & 0x2000000000000000000000000000000 > 0) {
                result = (result * 0x10163DA9FB33356D84A66AE336DCDFA40) >> 128;
            }
            if (x & 0x1000000000000000000000000000000 > 0) {
                result = (result * 0x100B1AFA5ABCBED6129AB13EC11DC9544) >> 128;
            }
            if (x & 0x800000000000000000000000000000 > 0) {
                result = (result * 0x10058C86DA1C09EA1FF19D294CF2F679C) >> 128;
            }
            if (x & 0x400000000000000000000000000000 > 0) {
                result = (result * 0x1002C605E2E8CEC506D21BFC89A23A011) >> 128;
            }
            if (x & 0x200000000000000000000000000000 > 0) {
                result = (result * 0x100162F3904051FA128BCA9C55C31E5E0) >> 128;
            }
            if (x & 0x100000000000000000000000000000 > 0) {
                result = (result * 0x1000B175EFFDC76BA38E31671CA939726) >> 128;
            }
            if (x & 0x80000000000000000000000000000 > 0) {
                result = (result * 0x100058BA01FB9F96D6CACD4B180917C3E) >> 128;
            }
            if (x & 0x40000000000000000000000000000 > 0) {
                result = (result * 0x10002C5CC37DA9491D0985C348C68E7B4) >> 128;
            }
            if (x & 0x20000000000000000000000000000 > 0) {
                result = (result * 0x1000162E525EE054754457D5995292027) >> 128;
            }
            if (x & 0x10000000000000000000000000000 > 0) {
                result = (result * 0x10000B17255775C040618BF4A4ADE83FD) >> 128;
            }
            if (x & 0x8000000000000000000000000000 > 0) {
                result = (result * 0x1000058B91B5BC9AE2EED81E9B7D4CFAC) >> 128;
            }
            if (x & 0x4000000000000000000000000000 > 0) {
                result = (result * 0x100002C5C89D5EC6CA4D7C8ACC017B7CA) >> 128;
            }
            if (x & 0x2000000000000000000000000000 > 0) {
                result = (result * 0x10000162E43F4F831060E02D839A9D16D) >> 128;
            }
            if (x & 0x1000000000000000000000000000 > 0) {
                result = (result * 0x100000B1721BCFC99D9F890EA06911763) >> 128;
            }
            if (x & 0x800000000000000000000000000 > 0) {
                result = (result * 0x10000058B90CF1E6D97F9CA14DBCC1629) >> 128;
            }
            if (x & 0x400000000000000000000000000 > 0) {
                result = (result * 0x1000002C5C863B73F016468F6BAC5CA2C) >> 128;
            }
            if (x & 0x200000000000000000000000000 > 0) {
                result = (result * 0x100000162E430E5A18F6119E3C02282A6) >> 128;
            }
            if (x & 0x100000000000000000000000000 > 0) {
                result = (result * 0x1000000B1721835514B86E6D96EFD1BFF) >> 128;
            }
            if (x & 0x80000000000000000000000000 > 0) {
                result = (result * 0x100000058B90C0B48C6BE5DF846C5B2F0) >> 128;
            }
            if (x & 0x40000000000000000000000000 > 0) {
                result = (result * 0x10000002C5C8601CC6B9E94213C72737B) >> 128;
            }
            if (x & 0x20000000000000000000000000 > 0) {
                result = (result * 0x1000000162E42FFF037DF38AA2B219F07) >> 128;
            }
            if (x & 0x10000000000000000000000000 > 0) {
                result = (result * 0x10000000B17217FBA9C739AA5819F44FA) >> 128;
            }
            if (x & 0x8000000000000000000000000 > 0) {
                result = (result * 0x1000000058B90BFCDEE5ACD3C1CEDC824) >> 128;
            }
            if (x & 0x4000000000000000000000000 > 0) {
                result = (result * 0x100000002C5C85FE31F35A6A30DA1BE51) >> 128;
            }
            if (x & 0x2000000000000000000000000 > 0) {
                result = (result * 0x10000000162E42FF0999CE3541B9FFFD0) >> 128;
            }
            if (x & 0x1000000000000000000000000 > 0) {
                result = (result * 0x100000000B17217F80F4EF5AADDA45554) >> 128;
            }
            if (x & 0x800000000000000000000000 > 0) {
                result = (result * 0x10000000058B90BFBF8479BD5A81B51AE) >> 128;
            }
            if (x & 0x400000000000000000000000 > 0) {
                result = (result * 0x1000000002C5C85FDF84BD62AE30A74CD) >> 128;
            }
            if (x & 0x200000000000000000000000 > 0) {
                result = (result * 0x100000000162E42FEFB2FED257559BDAA) >> 128;
            }
            if (x & 0x100000000000000000000000 > 0) {
                result = (result * 0x1000000000B17217F7D5A7716BBA4A9AF) >> 128;
            }
            if (x & 0x80000000000000000000000 > 0) {
                result = (result * 0x100000000058B90BFBE9DDBAC5E109CCF) >> 128;
            }
            if (x & 0x40000000000000000000000 > 0) {
                result = (result * 0x10000000002C5C85FDF4B15DE6F17EB0E) >> 128;
            }
            if (x & 0x20000000000000000000000 > 0) {
                result = (result * 0x1000000000162E42FEFA494F1478FDE05) >> 128;
            }
            if (x & 0x10000000000000000000000 > 0) {
                result = (result * 0x10000000000B17217F7D20CF927C8E94D) >> 128;
            }
            if (x & 0x8000000000000000000000 > 0) {
                result = (result * 0x1000000000058B90BFBE8F71CB4E4B33E) >> 128;
            }
            if (x & 0x4000000000000000000000 > 0) {
                result = (result * 0x100000000002C5C85FDF477B662B26946) >> 128;
            }
            if (x & 0x2000000000000000000000 > 0) {
                result = (result * 0x10000000000162E42FEFA3AE53369388D) >> 128;
            }
            if (x & 0x1000000000000000000000 > 0) {
                result = (result * 0x100000000000B17217F7D1D351A389D41) >> 128;
            }
            if (x & 0x800000000000000000000 > 0) {
                result = (result * 0x10000000000058B90BFBE8E8B2D3D4EDF) >> 128;
            }
            if (x & 0x400000000000000000000 > 0) {
                result = (result * 0x1000000000002C5C85FDF4741BEA6E77F) >> 128;
            }
            if (x & 0x200000000000000000000 > 0) {
                result = (result * 0x100000000000162E42FEFA39FE95583C3) >> 128;
            }
            if (x & 0x100000000000000000000 > 0) {
                result = (result * 0x1000000000000B17217F7D1CFB72B45E3) >> 128;
            }
            if (x & 0x80000000000000000000 > 0) {
                result = (result * 0x100000000000058B90BFBE8E7CC35C3F2) >> 128;
            }
            if (x & 0x40000000000000000000 > 0) {
                result = (result * 0x10000000000002C5C85FDF473E242EA39) >> 128;
            }
            if (x & 0x20000000000000000000 > 0) {
                result = (result * 0x1000000000000162E42FEFA39F02B772C) >> 128;
            }
            if (x & 0x10000000000000000000 > 0) {
                result = (result * 0x10000000000000B17217F7D1CF7D83C1A) >> 128;
            }
            if (x & 0x8000000000000000000 > 0) {
                result = (result * 0x1000000000000058B90BFBE8E7BDCBE2E) >> 128;
            }
            if (x & 0x4000000000000000000 > 0) {
                result = (result * 0x100000000000002C5C85FDF473DEA871F) >> 128;
            }
            if (x & 0x2000000000000000000 > 0) {
                result = (result * 0x10000000000000162E42FEFA39EF44D92) >> 128;
            }
            if (x & 0x1000000000000000000 > 0) {
                result = (result * 0x100000000000000B17217F7D1CF79E949) >> 128;
            }
            if (x & 0x800000000000000000 > 0) {
                result = (result * 0x10000000000000058B90BFBE8E7BCE545) >> 128;
            }
            if (x & 0x400000000000000000 > 0) {
                result = (result * 0x1000000000000002C5C85FDF473DE6ECA) >> 128;
            }
            if (x & 0x200000000000000000 > 0) {
                result = (result * 0x100000000000000162E42FEFA39EF366F) >> 128;
            }
            if (x & 0x100000000000000000 > 0) {
                result = (result * 0x1000000000000000B17217F7D1CF79AFA) >> 128;
            }
            if (x & 0x80000000000000000 > 0) {
                result = (result * 0x100000000000000058B90BFBE8E7BCD6E) >> 128;
            }
            if (x & 0x40000000000000000 > 0) {
                result = (result * 0x10000000000000002C5C85FDF473DE6B3) >> 128;
            }
            if (x & 0x20000000000000000 > 0) {
                result = (result * 0x1000000000000000162E42FEFA39EF359) >> 128;
            }
            if (x & 0x10000000000000000 > 0) {
                result = (result * 0x10000000000000000B17217F7D1CF79AC) >> 128;
            }

            result *= SCALE;
            result >>= (127 - (x >> 128));
        }
    }

    function mostSignificantBit(uint256 x) internal pure returns (uint256 msb) {
        if (x >= 2**128) {
            x >>= 128;
            msb += 128;
        }
        if (x >= 2**64) {
            x >>= 64;
            msb += 64;
        }
        if (x >= 2**32) {
            x >>= 32;
            msb += 32;
        }
        if (x >= 2**16) {
            x >>= 16;
            msb += 16;
        }
        if (x >= 2**8) {
            x >>= 8;
            msb += 8;
        }
        if (x >= 2**4) {
            x >>= 4;
            msb += 4;
        }
        if (x >= 2**2) {
            x >>= 2;
            msb += 2;
        }
        if (x >= 2**1) {
            msb += 1;
        }
    }

    function mulDiv(
        uint256 x,
        uint256 y,
        uint256 denominator
    ) internal pure returns (uint256 result) {
        uint256 prod0;
        uint256 prod1;
        assembly {
            let mm := mulmod(x, y, not(0))
            prod0 := mul(x, y)
            prod1 := sub(sub(mm, prod0), lt(mm, prod0))
        }

        if (prod1 == 0) {
            require(denominator > 0);
            assembly {
                result := div(prod0, denominator)
            }
            return result;
        }

        require(denominator > prod1);

        uint256 remainder;
        assembly {
            remainder := mulmod(x, y, denominator)

            prod1 := sub(prod1, gt(remainder, prod0))
            prod0 := sub(prod0, remainder)
        }

        unchecked {
            uint256 lpotdod = denominator & (~denominator + 1);
            assembly {
                denominator := div(denominator, lpotdod)

                prod0 := div(prod0, lpotdod)

                lpotdod := add(div(sub(0, lpotdod), lpotdod), 1)
            }

            prod0 |= prod1 * lpotdod;

            uint256 inverse = (3 * denominator) ^ 2;

            inverse *= 2 - denominator * inverse;
            inverse *= 2 - denominator * inverse;
            inverse *= 2 - denominator * inverse;
            inverse *= 2 - denominator * inverse;
            inverse *= 2 - denominator * inverse;
            inverse *= 2 - denominator * inverse;

            result = prod0 * inverse;
            return result;
        }
    }

    function mulDivFixedPoint(uint256 x, uint256 y) internal pure returns (uint256 result) {
        uint256 prod0;
        uint256 prod1;
        assembly {
            let mm := mulmod(x, y, not(0))
            prod0 := mul(x, y)
            prod1 := sub(sub(mm, prod0), lt(mm, prod0))
        }

        uint256 remainder;
        uint256 roundUpUnit;
        assembly {
            remainder := mulmod(x, y, SCALE)
            roundUpUnit := gt(remainder, 499999999999999999)
        }

        if (prod1 == 0) {
            unchecked {
                result = (prod0 / SCALE) + roundUpUnit;
                return result;
            }
        }

        require(SCALE > prod1);

        assembly {
            result := add(
                mul(
                    or(
                        div(sub(prod0, remainder), SCALE_LPOTD),
                        mul(sub(prod1, gt(remainder, prod0)), add(div(sub(0, SCALE_LPOTD), SCALE_LPOTD), 1))
                    ),
                    SCALE_INVERSE
                ),
                roundUpUnit
            )
        }
    }

    function mulDivSigned(
        int256 x,
        int256 y,
        int256 denominator
    ) internal pure returns (int256 result) {
        require(x > type(int256).min);
        require(y > type(int256).min);
        require(denominator > type(int256).min);

        uint256 ax;
        uint256 ay;
        uint256 ad;
        unchecked {
            ax = x < 0 ? uint256(-x) : uint256(x);
            ay = y < 0 ? uint256(-y) : uint256(y);
            ad = denominator < 0 ? uint256(-denominator) : uint256(denominator);
        }

        uint256 resultUnsigned = mulDiv(ax, ay, ad);
        require(resultUnsigned <= uint256(type(int256).max));

        uint256 sx;
        uint256 sy;
        uint256 sd;
        assembly {
            sx := sgt(x, sub(0, 1))
            sy := sgt(y, sub(0, 1))
            sd := sgt(denominator, sub(0, 1))
        }

        result = sx ^ sy ^ sd == 0 ? -int256(resultUnsigned) : int256(resultUnsigned);
    }

    function sqrt(uint256 x) internal pure returns (uint256 result) {
        if (x == 0) {
            return 0;
        }

        uint256 xAux = uint256(x);
        result = 1;
        if (xAux >= 0x100000000000000000000000000000000) {
            xAux >>= 128;
            result <<= 64;
        }
        if (xAux >= 0x10000000000000000) {
            xAux >>= 64;
            result <<= 32;
        }
        if (xAux >= 0x100000000) {
            xAux >>= 32;
            result <<= 16;
        }
        if (xAux >= 0x10000) {
            xAux >>= 16;
            result <<= 8;
        }
        if (xAux >= 0x100) {
            xAux >>= 8;
            result <<= 4;
        }
        if (xAux >= 0x10) {
            xAux >>= 4;
            result <<= 2;
        }
        if (xAux >= 0x8) {
            result <<= 1;
        }

        unchecked {
            result = (result + x / result) >> 1;
            result = (result + x / result) >> 1;
            result = (result + x / result) >> 1;
            result = (result + x / result) >> 1;
            result = (result + x / result) >> 1;
            result = (result + x / result) >> 1;
            result = (result + x / result) >> 1;
            uint256 roundedDownResult = x / result;
            return result >= roundedDownResult ? roundedDownResult : result;
        }
    }
}
