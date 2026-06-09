pragma solidity 0.8.4;

contract RebaseProxy is ERC20, TokenProxyLike {

    function redeemRate() public view returns (uint256) {
        uint256 balanceOfBase = IERC20(baseToken).balanceOf(address(this));
        if (totalSupply() == 0 || balanceOfBase == 0) {
            return ONE;
        }

        return (balanceOfBase * ONE) / totalSupply();
    }

    function mint(address to, uint256 amount)
        public
        override
        returns (uint256)
    {
        uint256 _redeemRate = redeemRate();
        require(IERC20(baseToken).transferFrom(msg.sender, address(this), amount));
        uint256 baseBalance = IERC20(baseToken).balanceOf(address(this));
        uint256 proxy = (baseBalance * ONE) / _redeemRate;
        _mint(to, proxy);
    }
}
