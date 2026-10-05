// SPDX-License-Identifier: MIT
pragma solidity 0.6.12;

interface ICvxLocker {
    function maximumBoostPayment() external returns (uint256);

    function lock(
        address _account,
        uint256 _amount,
        uint256 _spendRatio
    ) external;

    function balanceOf(address _user) external view returns (uint256 amount);

    function processExpiredLocks(bool _relock) external;
}
