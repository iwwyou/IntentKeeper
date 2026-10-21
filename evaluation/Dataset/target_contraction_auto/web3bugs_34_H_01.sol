pragma solidity 0.8.6;

contract DrawCalculator is IDrawCalculator, Ownable {

    IDrawBuffer public immutable drawBuffer;

    ITicket public immutable ticket;

    IPrizeDistributionBuffer public immutable prizeDistributionBuffer;

    uint8 public constant TIERS_LENGTH = 16;

    function _numberOfPrizesForIndex(uint8 _bitRangeSize, uint256 _prizeTierIndex) internal pure returns (uint256) {
        uint256 bitRangeDecimal = 2**uint256(_bitRangeSize);
        uint256 numberOfPrizesForIndex = bitRangeDecimal**_prizeTierIndex;

        while (_prizeTierIndex > 0) {
            numberOfPrizesForIndex -= bitRangeDecimal**(_prizeTierIndex - 1);
            _prizeTierIndex--;
        }

        return numberOfPrizesForIndex;
    }
}
