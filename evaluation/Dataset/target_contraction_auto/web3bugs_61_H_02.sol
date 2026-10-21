pragma solidity 0.7.6;

library SavingsAccountUtil {
    using SafeERC20 for IERC20;

    function savingsAccountTransfer(ISavingsAccount _savingsAccount, address _from, address _to, uint256 _amount, address _token, address _strategy) internal returns (uint256) {
        if (_from == address(this)) {
            _savingsAccount.transfer(_amount, _token, _strategy, _to);
        } else {
            _savingsAccount.transferFrom(_amount, _token, _strategy, _from, _to);
        }
        return _amount;
    }

}
