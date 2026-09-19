pragma solidity ^0.8.0;

/// @title Base lending behavior
abstract contract BaseLending {
    uint256 constant FP32 = 2**32;

    struct YieldAccumulator {
        uint256 accumulatorFP;
        uint256 lastUpdated;
        uint256 hourlyYieldFP;
    }

    /// @dev simple formula for calculating interest relative to accumulator
    function applyInterest(
        uint256 balance,
        uint256 accumulatorFP,
        uint256 yieldQuotientFP
    ) internal pure returns (uint256) {
        // 1 * FP / FP = 1
        return (balance * accumulatorFP) / yieldQuotientFP;
    }
}
