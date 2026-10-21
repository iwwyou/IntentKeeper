pragma solidity 0.6.12;

library SwapUtils {
    using SafeERC20 for IERC20;
    using SafeMath for uint256;
    using MathUtils for uint256;

    event AddLiquidity(address indexed provider, uint256[] tokenAmounts, uint256[] fees, uint256 invariant, uint256 lpTokenSupply);

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

    function _feePerToken(Swap storage self) internal view returns (uint256) {
        return self.swapFee.mul(self.pooledTokens.length).div(self.pooledTokens.length.sub(1).mul(4));
    }

    function addLiquidity(Swap storage self, uint256[] memory amounts, uint256 minToMint) external returns (uint256) {
        require(amounts.length == self.pooledTokens.length, "Amounts must match pooled tokens");

        uint256[] memory fees = new uint256[](self.pooledTokens.length);

        AddLiquidityInfo memory v = AddLiquidityInfo(0, 0, 0, 0);

        if (self.lpToken.totalSupply() != 0) {
            v.d0 = getD(self);
        }

        uint256[] memory newBalances = self.balances;

        for (uint256 i = 0; i < self.pooledTokens.length; i++) {
            require(self.lpToken.totalSupply() != 0 || amounts[i] > 0, "Must supply all tokens in pool");

            if (amounts[i] != 0) {
                uint256 beforeBalance = self.pooledTokens[i].balanceOf(address(this));
                self.pooledTokens[i].safeTransferFrom(msg.sender, address(this), amounts[i]);

                amounts[i] = self.pooledTokens[i].balanceOf(address(this)).sub(beforeBalance);
            }

            newBalances[i] = self.balances[i].add(amounts[i]);
        }

        v.preciseA = determineA(self, _xp(self, newBalances));
        v.d1 = getD(_xp(self, newBalances), v.preciseA);
        require(v.d1 > v.d0, "D should increase");

        v.d2 = v.d1;
        if (self.lpToken.totalSupply() != 0) {
            uint256 feePerToken = _feePerToken(self);
            for (uint256 i = 0; i < self.pooledTokens.length; i++) {
                uint256 idealBalance = v.d1.mul(self.balances[i]).div(v.d0);
                fees[i] = feePerToken.mul(idealBalance.difference(newBalances[i])).div(FEE_DENOMINATOR);
                self.balances[i] = newBalances[i].sub(fees[i].mul(self.adminFee).div(FEE_DENOMINATOR));
                newBalances[i] = newBalances[i].sub(fees[i]);
            }
            v.d2 = getD(_xp(self, newBalances), determineA(self, _xp(self, newBalances)));
        } else {
            self.balances = newBalances;
        }

        uint256 toMint;
        if (self.lpToken.totalSupply() == 0) {
            toMint = v.d1;
        } else {
            toMint = v.d2.sub(v.d0).mul(self.lpToken.totalSupply()).div(v.d0);
        }

        require(toMint >= minToMint, "Couldn't mint min requested");

        self.lpToken.mint(msg.sender, toMint);

        emit AddLiquidity(msg.sender, amounts, fees, v.d1, self.lpToken.totalSupply());

        return toMint;
    }

}
