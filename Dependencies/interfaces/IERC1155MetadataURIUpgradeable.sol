pragma solidity >=0.6.2 <0.8.0;

interface IERC1155MetadataURIUpgradeable is IERC1155Upgradeable {
    function uri(uint256 id) external view returns (string memory);
}
