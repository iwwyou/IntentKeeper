pragma solidity ^0.8.4;

interface IAssetManager {
    function getPoolBalance(address tokenAddress) external view returns (uint256);

    function getLoanableAmount(address tokenAddress) external view returns (uint256);

    function totalSupply(address tokenAddress) external returns (uint256);

    function totalSupplyView(address tokenAddress) external view returns (uint256);

    function isMarketSupported(address tokenAddress) external view returns (bool);

    function deposit(address token, uint256 amount) external returns (bool);

    function withdraw(
        address token,
        address account,
        uint256 amount
    ) external returns (bool);

    function addToken(address tokenAddress) external;

    function addAdapter(address adapterAddress) external;

    function approveAllMarketsMax(address tokenAddress) external;

    function approveAllTokensMax(address adapterAddress) external;

    function changeWithdrawSequence(uint256[] calldata newSeq) external;

    function rebalance(address tokenAddress, uint256[] calldata percentages) external;

    function claimTokens(address tokenAddress, address recipient) external;

    function claimTokensFromAdapter(
        uint256 index,
        address tokenAddress,
        address recipient
    ) external;

    function moneyMarketsCount() external view returns (uint256);

    function supportedTokensCount() external view returns (uint256);

    function getMoneyMarket(address tokenAddress, uint256 marketId) external view returns (uint256, uint256);

    function debtWriteOff(address tokenAddress, uint256 amount) external;
}
