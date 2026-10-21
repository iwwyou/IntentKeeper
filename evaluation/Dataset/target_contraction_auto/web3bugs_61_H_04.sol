pragma solidity 0.7.6;

contract YearnYield is IYield, Initializable, OwnableUpgradeable, ReentrancyGuard {
    using SafeERC20 for IERC20;
    using SafeMath for uint256;

    address payable public savingsAccount;

    mapping(address => address) public override liquidityToken;

    function getTokensForShares(uint256 shares, address asset) public view override returns (uint256 amount) {
        if (shares == 0) {
            return 0;
        }
        amount = IyVault(liquidityToken[asset]).getPricePerFullShare().mul(shares).div(1e18);
    }

}
