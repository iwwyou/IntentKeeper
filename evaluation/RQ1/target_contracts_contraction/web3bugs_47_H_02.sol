pragma solidity ^0.6.12;

contract WrappedIbbtcEth is Initializable, ERC20Upgradeable {
    address public governance;
    address public pendingGovernance;
    ERC20Upgradeable public ibbtc;

    ICore public core;

    uint256 public pricePerShare;
    uint256 public lastPricePerShareUpdate;

    event SetCore(address core);
    event SetPricePerShare(uint256 pricePerShare, uint256 updateTimestamp);
    event SetPendingGovernance(address pendingGovernance);
    event AcceptPendingGovernance(address pendingGovernance); 

    function balanceToShares(uint256 balance) public view returns (uint256) {
        return balance.mul(1e18).div(pricePerShare);
    }  

    function transferFrom(address sender, address recipient, uint256 amount) public virtual override returns (bool) {
        uint256 amountInShares = balanceToShares(amount);

        _transfer(sender, recipient, amountInShares);
        _approve(sender, _msgSender(), _allowances[sender][_msgSender()].sub(amountInShares, "ERC20: transfer amount exceeds allowance"));
        return true;
    }
}
