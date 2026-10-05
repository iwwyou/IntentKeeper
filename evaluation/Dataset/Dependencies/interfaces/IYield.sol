pragma solidity 0.7.6;

interface IYield {
    event LockedTokens(address indexed user, address indexed investedTo, uint256 lpTokensReceived);

    event UnlockedTokens(address indexed investedTo, uint256 collateralReceived);

    event UnlockedShares(address indexed asset, uint256 sharesReleased);

    event SavingsAccountUpdated(address indexed savingsAccount);

    function liquidityToken(address asset) external view returns (address tokenAddress);

    function lockTokens(
        address user,
        address asset,
        uint256 amount
    ) external returns (uint256 sharesReceived);

    function unlockTokens(
        address asset,
        address to,
        uint256 amount
    ) external returns (uint256 tokensReceived);

    function unlockShares(
        address asset,
        address to,
        uint256 amount
    ) external returns (uint256 received);

    function getTokensForShares(uint256 shares, address asset) external returns (uint256 amount);

    function getSharesForTokens(uint256 amount, address asset) external returns (uint256 shares);
}
