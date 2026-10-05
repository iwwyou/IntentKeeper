pragma solidity 0.8.9;

contract LpIssuer is IERC721Receiver, ILpIssuer, ERC20, ReentrancyGuard {
    using SafeERC20 for IERC20;
    uint256 private _subvaultNft;
    IVaultGovernance internal _vaultGovernance;
    address[] internal _vaultTokens;
    mapping(address => bool) internal _vaultTokensIndex;
    uint256 private _nft;
    uint256[] private _lpPriceHighWaterMarks;
    uint256[] private _existentials;

    uint256 public lastFeeCharge;

    function _chargeFees(
        uint256 thisNft,
        uint256[] memory tvls,
        uint256 supply,
        uint256[] memory deltaTvls,
        uint256 deltaSupply,
        bool isWithdraw
    ) internal {
        ILpIssuerGovernance vg = ILpIssuerGovernance(address(_vaultGovernance));
        uint256 elapsed = block.timestamp - lastFeeCharge;
        if (elapsed < vg.delayedProtocolParams().managementFeeChargeDelay) {
            return;
        }
        lastFeeCharge = block.timestamp;
        uint256 baseSupply = supply;
        if (isWithdraw) {
            baseSupply = 0;
            if (supply > deltaSupply) {
                baseSupply = supply - deltaSupply;
            }
        }

        if (baseSupply == 0) {
            for (uint256 i = 0; i < tvls.length; i++) {
                _lpPriceHighWaterMarks[i] = (deltaTvls[i] * CommonLibrary.PRICE_DENOMINATOR) / deltaSupply;
            }
            return;
        }

        uint256[] memory baseTvls = new uint256[](tvls.length);
        for (uint256 i = 0; i < baseTvls.length; i++) {
            if (isWithdraw) {
                baseTvls[i] = tvls[i] - deltaTvls[i];
            } else {
                baseTvls[i] = tvls[i];
            }
        }

        ILpIssuerGovernance.DelayedStrategyParams memory strategyParams = vg.delayedStrategyParams(thisNft);
        if (strategyParams.managementFee > 0) {
            uint256 toMint = (strategyParams.managementFee * baseSupply * elapsed) /
                (CommonLibrary.DENOMINATOR * CommonLibrary.YEAR);
            _mint(strategyParams.strategyTreasury, toMint);           
        }
        uint256 protocolFee = vg.delayedProtocolPerVaultParams(thisNft).protocolFee;
        if (protocolFee > 0) {
            address treasury = vg.internalParams().protocolGovernance.protocolTreasury();
            uint256 toMint = (protocolFee * baseSupply * elapsed) / (CommonLibrary.DENOMINATOR * CommonLibrary.YEAR);
            _mint(treasury, toMint);           
        }
        uint256 performanceFee = strategyParams.performanceFee;
        uint256[] memory hwms = _lpPriceHighWaterMarks;
        if (performanceFee > 0) {
            uint256 minLpPriceFactor = type(uint256).max;
            for (uint256 i = 0; i < baseTvls.length; i++) {
                uint256 hwm = hwms[i];
                uint256 lpPrice = (baseTvls[i] * CommonLibrary.PRICE_DENOMINATOR) / baseSupply;
                if (lpPrice > hwm) {
                    uint256 delta = (lpPrice * CommonLibrary.DENOMINATOR) / hwm;
                    if (delta < minLpPriceFactor) {
                        minLpPriceFactor = delta;
                    }
                } else {
                    return;
                }
            }
            for (uint256 i = 0; i < tvls.length; i++) {
                _lpPriceHighWaterMarks[i] += (hwms[i] * minLpPriceFactor) / CommonLibrary.DENOMINATOR;
            }
            address treasury = strategyParams.strategyPerformanceTreasury;
            uint256 toMint = (baseSupply * minLpPriceFactor) / CommonLibrary.DENOMINATOR;
            _mint(treasury, toMint);            
        }
    }
}
