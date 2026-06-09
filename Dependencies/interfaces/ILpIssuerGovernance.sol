pragma solidity 0.8.9;

interface ILpIssuerGovernance is IVaultGovernance {
    struct DelayedStrategyParams {
        address strategyTreasury;
        address strategyPerformanceTreasury;
        uint256 managementFee;
        uint256 performanceFee;
    }

    struct DelayedProtocolParams {
        uint256 managementFeeChargeDelay;
    }

    struct StrategyParams {
        uint256 tokenLimitPerAddress;
    }

    struct DelayedProtocolPerVaultParams {
        uint256 protocolFee;
    }

    function delayedProtocolParams() external view returns (DelayedProtocolParams memory);

    function stagedDelayedProtocolParams() external view returns (DelayedProtocolParams memory);

    function delayedProtocolPerVaultParams(uint256 nft) external view returns (DelayedProtocolPerVaultParams memory);

    function stagedDelayedProtocolPerVaultParams(uint256 nft)
        external
        view
        returns (DelayedProtocolPerVaultParams memory);

    function strategyParams(uint256 nft) external view returns (StrategyParams memory);

    function delayedStrategyParams(uint256 nft) external view returns (DelayedStrategyParams memory);

    function stagedDelayedStrategyParams(uint256 nft) external view returns (DelayedStrategyParams memory);

    function setStrategyParams(uint256 nft, StrategyParams calldata params) external;

    function stageDelayedProtocolPerVaultParams(uint256 nft, DelayedProtocolPerVaultParams calldata params) external;

    function commitDelayedProtocolPerVaultParams(uint256 nft) external;

    function stageDelayedStrategyParams(uint256 nft, DelayedStrategyParams calldata params) external;

    function commitDelayedStrategyParams(uint256 nft) external;

    function stageDelayedProtocolParams(DelayedProtocolParams calldata params) external;

    function commitDelayedProtocolParams() external;
}
