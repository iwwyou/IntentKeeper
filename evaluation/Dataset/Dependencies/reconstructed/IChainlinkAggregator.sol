// SPDX-License-Identifier: MIT
// RECONSTRUCTED (IQDebug evaluation): the code4rena 2021-06-gro snapshot (code-423n4/2021-06-gro@main) imports
// contracts/interfaces/IChainlinkAggregator.sol from Buoy3Pool.sol and mocks/MockAggregator.sol, but the file is
// absent from the repository tree. Members recovered from the only implementer in the snapshot
// (mocks/MockAggregator.sol: `latestRound() external view override returns (uint256)`,
// `latestAnswer() external view override returns (int256)`) and the call sites in Buoy3Pool.sol:207,214-216.
// Interfaces emit no bytecode; function selectors depend only on these signatures.
pragma solidity >=0.6.0 <0.7.0;

interface IChainlinkAggregator {
    function latestRound() external view returns (uint256);

    function latestAnswer() external view returns (int256);
}
