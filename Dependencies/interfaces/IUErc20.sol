pragma solidity ^0.8.4;

interface IUErc20 is IERC20MetadataUpgradeable {
    function mint(address account, uint256 amount) external;

    function burn(address account, uint256 amount) external;

    function permit(
        address holder,
        address spender,
        uint256 nonce,
        uint256 expiry,
        bool allowed,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external;
}
