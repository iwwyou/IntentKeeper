pragma solidity 0.6.12;

contract LPToken is ERC20Burnable, Ownable {
    using SafeMath for uint256;

    ISwap public swap;

    mapping(address => uint256) public mintedAmounts;

    function mint(
        address recipient,
        uint256 amount
    ) external onlyOwner {
        require(amount != 0, "amount == 0");

        uint256 totalMinted = mintedAmounts[recipient].add(amount);
        mintedAmounts[recipient] = totalMinted;
        _mint(recipient, amount);
    }

    function _beforeTokenTransfer(
        address _from,
        address to,
        uint256 amount
    ) internal override(ERC20) {
        super._beforeTokenTransfer(_from, to, amount);
        swap.updateUserWithdrawFee(to, amount);
    }
}
