pragma solidity >=0.6.2 <0.8.0;

interface IERC1155Upgradeable is IERC165Upgradeable {
    function balanceOf(address account, uint256 id) external view returns (uint256);

    function balanceOfBatch(address[] calldata accounts, uint256[] calldata ids) external view returns (uint256[] memory);

    function setApprovalForAll(address operator, bool approved) external;

    function isApprovedForAll(address account, address operator) external view returns (bool);

    function safeTransferFrom(address _from, address to, uint256 id, uint256 amount, bytes calldata data) external;

    function safeBatchTransferFrom(address _from, address to, uint256[] calldata ids, uint256[] calldata amounts, bytes calldata data) external;
}
