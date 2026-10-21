pragma solidity ^0.8.0;

contract Swap is EmergencyPausable, ReentrancyGuard {
    using SafeERC20 for IERC20;
    using SafeMath for uint256;
    using Math for uint256;

    address payable public feeRecipient;
    uint256 public swapFee;
    uint256 public constant SWAP_FEE_DIVISOR = 100_000;

    function fillZrxQuote(IERC20 zrxBuyTokenAddress, address payable zrxTo, bytes calldata zrxData, uint256 ethAmount) internal returns (uint256, uint256) {
        uint256 originalERC20Balance = 0;
        if(!signifiesETHOrZero(address(zrxBuyTokenAddress))) {
            originalERC20Balance = zrxBuyTokenAddress.balanceOf(address(this));
        }
        uint256 originalETHBalance = address(this).balance;

        (bool success,) = zrxTo.call{value: ethAmount}(zrxData);
        require(success, "Swap::fillZrxQuote: Failed to fill quote");

        uint256 ethDelta = address(this).balance.subOrZero(originalETHBalance);
        uint256 erc20Delta;
        if(!signifiesETHOrZero(address(zrxBuyTokenAddress))) {
            erc20Delta = zrxBuyTokenAddress.balanceOf(address(this)).subOrZero(originalERC20Balance);
            require(erc20Delta > 0, "Swap::fillZrxQuote: Didn't receive bought token");
        } else {
            require(ethDelta > 0, "Swap::fillZrxQuote: Didn't receive bought ETH");
        }

        return (erc20Delta, ethDelta);
    }

    function signifiesETHOrZero(address tokenAddress) internal pure returns (bool) {
        return (tokenAddress == address(0) || tokenAddress == address(0x00eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee));
    }

}
