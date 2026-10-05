pragma solidity ^0.6.12;

interface INFTOracle {
    function get(address nftPair, uint256 tokenId) external returns (bool success, uint256 rate);
}
