// SPDX-License-Identifier: MIT
// RECONSTRUCTED (IQDebug evaluation): the code4rena 2021-04-marginswap snapshot omits contracts/interfaces/.
// Members recovered from the only call sites in the dependency pool (Fund.sol:48,67).
// Interfaces emit no bytecode; function selectors depend only on these signatures.
pragma solidity >=0.6.0 <0.9.0;

interface IWETH {
    function deposit() external payable;
    function withdraw(uint256) external;
}
