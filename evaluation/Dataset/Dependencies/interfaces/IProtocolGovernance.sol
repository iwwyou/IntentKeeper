pragma solidity 0.8.9;

interface IProtocolGovernance is IDefaultAccessControl {
    struct Params {
        bool permissionless;
        uint256 maxTokensPerVault;
        uint256 governanceDelay;
        address protocolTreasury;
    }

    function claimAllowlist() external view returns (address[] memory);

    function pendingClaimAllowlistAdd() external view returns (address[] memory);

    function tokenWhitelist() external view returns (address[] memory);

    function pendingTokenWhitelistAdd() external view returns (address[] memory);

    function vaultGovernances() external view returns (address[] memory);

    function pendingVaultGovernancesAdd() external view returns (address[] memory);

    function isAllowedToClaim(address addr) external view returns (bool);

    function isAllowedToken(address addr) external view returns (bool);

    function isVaultGovernance(address addr) external view returns (bool);

    function permissionless() external view returns (bool);

    function maxTokensPerVault() external view returns (uint256);

    function governanceDelay() external view returns (uint256);

    function protocolTreasury() external view returns (address);

    function setPendingParams(Params memory newParams) external;

    function setPendingClaimAllowlistAdd(address[] calldata addresses) external;

    function setPendingTokenWhitelistAdd(address[] calldata addresses) external;

    function setPendingVaultGovernancesAdd(address[] calldata addresses) external;

    function commitParams() external;

    function commitClaimAllowlistAdd() external;

    function commitTokenWhitelistAdd() external;

    function commitVaultGovernancesAdd() external;

    function removeFromClaimAllowlist(address addr) external;

    function removeFromTokenWhitelist(address addr) external;

    function removeFromVaultGovernances(address addr) external;
}
