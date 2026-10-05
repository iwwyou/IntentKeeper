pragma solidity 0.8.4;
abstract contract TokenProxyLike is IERC20 {
    address internal baseToken;
    uint constant internal ONE = 1 ether;

    function mint(address to, uint256 amount) public virtual returns (uint);
    function redeem(address to, uint256 amount) public virtual returns (uint);
}
