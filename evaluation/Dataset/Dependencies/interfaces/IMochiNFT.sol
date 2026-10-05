pragma solidity ^0.8.0;

interface IMochiNFT {
    struct MochiInfo {
        address asset;
    }

    function asset(uint256 _id) external view returns (address);

    function mint(address _asset, address _owner) external returns (uint256);

    function ownerOf(uint256 _id) external view returns (address);
}
