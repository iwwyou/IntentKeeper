// SPDX-License-Identifier: MIT
pragma solidity ^0.6.11;

interface ISettV3 {
    function deposit(uint256 _amount) external;

    function getPricePerFullShare() external view returns (uint256);
}
