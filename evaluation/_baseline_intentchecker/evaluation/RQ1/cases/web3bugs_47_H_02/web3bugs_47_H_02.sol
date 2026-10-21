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
        // @LocalVar sender = symbolicAddress 1
        // @LocalVar recipient = symbolicAddress 2
        // @LocalVar amount = [100, 100]
        // @StateVar _allowances[1][101] = [1000, 1000]
        // @StateVar pricePerShare = [2000000000000000000, 2000000000000000000]
        // @StateVar _balances[1] = [500, 500]
        uint256 amountInShares = balanceToShares(amount);

        _transfer(sender, recipient, amountInShares);
        // @Post _allowances[1][101] == 900
        _approve(sender, _msgSender(), _allowances[sender][_msgSender()].sub(amountInShares, "ERC20: transfer amount exceeds allowance"));
        return true;
    }
}
