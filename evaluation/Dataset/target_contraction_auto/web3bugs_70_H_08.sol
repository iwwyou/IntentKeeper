pragma solidity =0.8.9;

contract VaderReserve is IVaderReserve, ProtocolConstants, Ownable {

    using SafeERC20 for IERC20;

    IERC20 public immutable vader;

    address public router;

    uint256 public lastGrant;

    ILiquidityBasedTWAP public lbt;

    function reserve() public view override returns (uint256) {
        return vader.balanceOf(address(this));
    }

    function reimburseImpermanentLoss(address recipient, uint256 amount) external override {
        require(msg.sender == router, "VaderReserve::reimburseImpermanentLoss: Insufficient Priviledges");

        if (lbt.previousPrices(uint256(ILiquidityBasedTWAP.Paths.USDV)) != 0) {
            uint256 usdvPrice = lbt.getUSDVPrice();

            amount = amount / usdvPrice;
        } else {
            uint256 vaderPrice = lbt.getVaderPrice();

            amount = amount * vaderPrice;
        }

        uint256 actualAmount = _min(reserve(), amount);

        vader.safeTransfer(recipient, actualAmount);

        emit LossCovered(recipient, amount, actualAmount);
    }

    function _min(uint256 a, uint256 b) private pure returns (uint256) {
        return a < b ? a : b;
    }

}
