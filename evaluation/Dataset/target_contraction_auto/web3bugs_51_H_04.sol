pragma solidity 0.6.12;

library SwapUtils {
    using SafeERC20 for IERC20;
    using SafeMath for uint256;
    using MathUtils for uint256;

    struct Swap {
        uint256 initialA;
        uint256 futureA;
        uint256 initialATime;
        uint256 futureATime;
        uint256 initialA2;
        uint256 futureA2;
        uint256 initialA2Time;
        uint256 futureA2Time;
        uint256 swapFee;
        uint256 adminFee;
        uint256 defaultWithdrawFee;
        LPToken lpToken;
        IERC20[] pooledTokens;
        uint256[] tokenPrecisionMultipliers;
        uint256[] balances;
        mapping(address => uint256) depositTimestamp;
        mapping(address => uint256) withdrawFeeMultiplier;
    }

    struct TargetPrice {
        uint256 initialTargetPrice;
        uint256 futureTargetPrice;
        uint256 initialTargetPriceTime;
        uint256 futureTargetPriceTime;

        uint256[2] originalPrecisionMultipliers;
    }

    struct CalculateWithdrawOneTokenDYInfo {
        uint256 d0;
        uint256 d1;
        uint256 newY;
        uint256 feePerToken;
        uint256 preciseA;
    }

    struct AddLiquidityInfo {
        uint256 d0;
        uint256 d1;
        uint256 d2;
        uint256 preciseA;
    }

    struct RemoveLiquidityImbalanceInfo {
        uint256 d0;
        uint256 d1;
        uint256 d2;
        uint256 preciseA;
    }

    uint256 private constant WEI_UNIT = 10**18;

    uint8 public constant POOL_PRECISION_DECIMALS = 18;

    uint256 private constant FEE_DENOMINATOR = 10**10;

    uint256 public constant MAX_SWAP_FEE = 10**8;

    uint256 public constant MAX_ADMIN_FEE = 10**10;

    uint256 public constant MAX_WITHDRAW_FEE = 10**8;

    uint256 private constant MAX_LOOP_LIMIT = 256;

    uint256 public constant TARGET_PRICE_PRECISION = 1;
    uint256 public constant A_PRECISION = 100;
    uint256 public constant MAX_A = 10**6;
    uint256 private constant MAX_A_CHANGE = 2;
    uint256 private constant MAX_RELATIVE_PRICE_CHANGE = 10**16;
    uint256 private constant MIN_RAMP_TIME = 14 days;

    function _getAPrecise(Swap storage self) internal view returns (uint256) {
        uint256 t1 = self.futureATime;
        uint256 a1 = self.futureA;

        if (block.timestamp < t1) {
            uint256 t0 = self.initialATime;
            uint256 a0 = self.initialA;
            if (a1 > a0) {
                return a0.add(a1.sub(a0).mul(block.timestamp.sub(t0)).div(t1.sub(t0)));
            } else {
                return a0.sub(a0.sub(a1).mul(block.timestamp.sub(t0)).div(t1.sub(t0)));
            }
        } else {
            return a1;
        }
    }

    function _getA2Precise(Swap storage self) internal view returns (uint256) {
        uint256 t1 = self.futureA2Time;
        uint256 a1 = self.futureA2;

        if (block.timestamp < t1) {
            uint256 t0 = self.initialA2Time;
            uint256 a0 = self.initialA2;
            if (a1 > a0) {
                return a0.add(a1.sub(a0).mul(block.timestamp.sub(t0)).div(t1.sub(t0)));
            } else {
                return a0.sub(a0.sub(a1).mul(block.timestamp.sub(t0)).div(t1.sub(t0)));
            }
        } else {
            return a1;
        }
    }

    function getD(uint256[] memory xp, uint256 a) internal pure returns (uint256) {
        uint256 numTokens = xp.length;
        uint256 s;
        for (uint256 i = 0; i < numTokens; i++) {
            s = s.add(xp[i]);
        }
        if (s == 0) {
            return 0;
        }

        uint256 prevD;
        uint256 d = s;
        uint256 nA = a.mul(numTokens);

        for (uint256 i = 0; i < MAX_LOOP_LIMIT; i++) {
            uint256 dP = d;
            for (uint256 j = 0; j < numTokens; j++) {
                dP = dP.mul(d).div(xp[j].mul(numTokens));
            }
            prevD = d;

            d = nA.mul(s).div(A_PRECISION).add(dP.mul(numTokens)).mul(d).div(nA.mul(d).div(A_PRECISION).add(numTokens.add(1).mul(dP)).sub(d));
            if (d.within1(prevD)) {
                return d;
            }
        }

        revert("D does not converge");
    }

    function getD(Swap storage self) internal view returns (uint256) {
        uint256 a = determineA(self, _xp(self));
        return getD(_xp(self), a);
    }

    function _xp(uint256[] memory balances, uint256[] memory precisionMultipliers) internal pure returns (uint256[] memory) {
        uint256 numTokens = balances.length;
        require(numTokens == precisionMultipliers.length, "Balances must match multipliers");
        uint256[] memory xp = new uint256[](numTokens);
        for (uint256 i = 0; i < numTokens; i++) {
            xp[i] = balances[i].mul(precisionMultipliers[i]);
        }
        return xp;
    }

    function _xp(Swap storage self, uint256[] memory balances) internal view returns (uint256[] memory) {
        return _xp(balances, self.tokenPrecisionMultipliers);
    }

    function _xp(Swap storage self) internal view returns (uint256[] memory) {
        return _xp(self.balances, self.tokenPrecisionMultipliers);
    }

    function determineA(Swap storage self, uint256[] memory xp) internal view returns(uint256) {
        if( xp[0] < xp[1] ) {
            return _getAPrecise(self);
        } else {
            return _getA2Precise(self);
        }
    }

    function getYC(Swap storage self, uint8 tokenIndexFrom, uint8 tokenIndexTo, uint256 x, uint256[] memory xp) internal view returns (uint256) {
        uint256 numTokens = self.pooledTokens.length;
        require(tokenIndexFrom != tokenIndexTo, "Can't compare token to itself");
        require(tokenIndexFrom < numTokens && tokenIndexTo < numTokens, "Tokens must be in pool");

        uint256 a = determineA(self, xp);

        uint256 d = getD(xp, a);

        uint256 y = getY(self, tokenIndexFrom, tokenIndexTo, x, xp, a, d);

        uint256 aNew = _xpCalc(self, tokenIndexFrom, tokenIndexTo, x, y);

        if (aNew == a){
            return y;
        } else {
            return getY(self, tokenIndexFrom, tokenIndexTo, x, xp, aNew, d);
        }

    }

    function _xpCalc(Swap storage self, uint8 tokenIndexFrom, uint8 tokenIndexTo, uint256 x, uint256 y) internal view returns (uint256) {
        uint256 xpNew0;
        uint256 xpNew1;

        if( tokenIndexFrom == 0 && tokenIndexTo == 1) {
            xpNew0 = x;
            xpNew1 = y;
        }
        else if( tokenIndexFrom == 1 && tokenIndexTo == 0) {
            xpNew0 = y;
            xpNew1 = x;
        }

        if (xpNew0 < xpNew1) {
            return _getAPrecise(self);
        } else {
            return _getA2Precise(self);
        }
    }

    function getY(Swap storage self, uint8 tokenIndexFrom, uint8 tokenIndexTo, uint256 x, uint256[] memory xp, uint256 a, uint256 d) internal view returns (uint256) {
        uint256 numTokens = self.pooledTokens.length;
        require(tokenIndexFrom != tokenIndexTo, "Can't compare token to itself");
        require(tokenIndexFrom < numTokens && tokenIndexTo < numTokens, "Tokens must be in pool");

        uint256 c = d;
        uint256 s;
        uint256 nA = numTokens.mul(a);

        uint256 _x;
        for (uint256 i = 0; i < numTokens; i++) {
            if (i == tokenIndexFrom) {
                _x = x;
            } else if (i != tokenIndexTo) {
                _x = xp[i];
            } else {
                continue;
            }
            s = s.add(_x);
            c = c.mul(d).div(_x.mul(numTokens));
        }
        c = c.mul(d).mul(A_PRECISION).div(nA.mul(numTokens));
        uint256 b = s.add(d.mul(A_PRECISION).div(nA));
        uint256 yPrev;
        uint256 y = d;

        for (uint256 i = 0; i < MAX_LOOP_LIMIT; i++) {
            yPrev = y;
            y = y.mul(y).add(c).div(y.mul(2).add(b).sub(d));
            if (y.within1(yPrev)) {
                return y;
            }
        }
        revert("Approximation did not converge");
    }

}
