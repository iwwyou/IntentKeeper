

pragma solidity =0.8.9;

library VaderMath {
    

    uint256 public constant ONE = 1 ether;

    

    
    function calculateLiquidityUnits(
        uint256 vaderDeposited,
        uint256 vaderBalance,
        uint256 assetDeposited,
        uint256 assetBalance,
        uint256 totalPoolUnits
    ) public pure returns (uint256) {
        
        uint256 slip = calculateSlipAdjustment(
            vaderDeposited,
            vaderBalance,
            assetDeposited,
            assetBalance
        );

        
        uint256 poolUnitFactor = (vaderBalance * assetDeposited) +
            (vaderDeposited * assetBalance);

        
        uint256 denominator = ONE * 2 * vaderBalance * assetBalance;

        
        return ((totalPoolUnits * poolUnitFactor) / denominator) * slip;
    }

    
    function calculateSlipAdjustment(
        uint256 vaderDeposited,
        uint256 vaderBalance,
        uint256 assetDeposited,
        uint256 assetBalance
    ) public pure returns (uint256) {
        
        uint256 vaderAsset = vaderBalance * assetDeposited;

        
        uint256 assetVader = assetBalance * vaderDeposited;

        
        uint256 denominator = (vaderDeposited + vaderBalance) *
            (assetDeposited + assetBalance);

        
        return ONE - (delta(vaderAsset, assetVader) / denominator);
    }

    
    function calculateLoss(
        uint256 originalVader,
        uint256 originalAsset,
        uint256 releasedVader,
        uint256 releasedAsset
    ) public pure returns (uint256 loss) {
        
        
        

        
        uint256 originalValue = ((originalAsset * releasedVader) /
            releasedAsset) + originalVader;

        
        uint256 releasedValue = ((releasedAsset * releasedVader) /
            releasedAsset) + releasedVader;

        
        if (originalValue > releasedValue) loss = originalValue - releasedValue;
    }

    
    function calculateSwap(
        uint256 amountIn,
        uint256 reserveIn,
        uint256 reserveOut
    ) public pure returns (uint256 amountOut) {
        
        uint256 numerator = amountIn * reserveIn * reserveOut;

        
        uint256 denominator = pow(amountIn + reserveIn);

        amountOut = numerator / denominator;
    }

    
    function calculateSwapReverse(
        uint256 amountOut,
        uint256 reserveIn,
        uint256 reserveOut
    ) public pure returns (uint256 amountIn) {
        
        uint256 XY = reserveIn * reserveOut;

        
        uint256 y2 = amountOut * 2;

        
        uint256 y4 = y2 * 2;

        require(
            y4 < reserveOut,
            "VaderMath::calculateSwapReverse: Desired Output Exceeds Maximum Output Possible (1/4 of Liquidity Pool)"
        );

        
        uint256 numeratorA = root(XY) * root(reserveIn * (reserveOut - y4));

        
        uint256 numeratorB = y2 * reserveIn;
        uint256 numeratorC = XY;

        
        uint256 numerator = numeratorC - numeratorA - numeratorB;

        
        uint256 denominator = y2;

        amountIn = numerator / denominator;
    }

    
    function delta(uint256 a, uint256 b) public pure returns (uint256) {
        return a > b ? a - b : b - a;
    }

    
    function pow(uint256 a) public pure returns (uint256) {
        return a * a;
    }

    
    function root(uint256 a) public pure returns (uint256 c) {
        if (a > 3) {
            c = a;
            uint256 x = a / 2 + 1;
            while (x < c) {
                c = x;
                x = (a / x + x) / 2;
            }
        } else if (a != 0) {
            c = 1;
        }
    }
}
