pragma solidity 0.8.9;

interface ILpIssuer {
    function nft() external view returns (uint256);

    function subvaultNft() external view returns (uint256);

    function addSubvault(uint256 nft) external;

    function initialize(uint256 nft) external;

    function deposit(uint256[] calldata tokenAmounts, bytes memory options) external;

    function withdraw(
        address to,
        uint256 lpTokenAmount,
        bytes memory options
    ) external;
}
