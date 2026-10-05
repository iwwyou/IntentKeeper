pragma solidity 0.8.9;

interface IVaultGovernance {
    struct InternalParams {
        IProtocolGovernance protocolGovernance;
        IVaultRegistry registry;
    }

    function initialized() external view returns (bool);

    function factory() external view returns (IVaultFactory);

    function delayedStrategyParamsTimestamp(uint256 nft) external view returns (uint256);

    function delayedProtocolParamsTimestamp() external view returns (uint256);

    function delayedProtocolPerVaultParamsTimestamp(uint256 nft) external view returns (uint256);

    function internalParamsTimestamp() external view returns (uint256);

    function internalParams() external view returns (InternalParams memory);

    function stagedInternalParams() external view returns (InternalParams memory);

    function initialize(IVaultFactory factory) external;

    function deployVault(
        address[] memory vaultTokens,
        bytes memory options,
        address owner
    ) external returns (IVault vault, uint256 nft);

    function stageInternalParams(InternalParams memory newParams) external;

    function commitInternalParams() external;
}
