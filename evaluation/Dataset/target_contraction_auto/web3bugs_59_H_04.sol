pragma solidity >=0.6.6;

contract AuctionBurnReserveSkew is Initializable, Permissions {
  using SafeMath for uint256;

  uint256[] public pegObservations;
  uint256 public auctionAverageLookback = 10;

  IStabilizerNode public stabilizerNode;
  IAuction public auction;

  uint256 public count;

  function getPegDeltaFrequency() public view returns (uint256) {
    uint256 initialIndex = 0;
    uint256 index;

    if (count > auctionAverageLookback) {
      initialIndex = count - auctionAverageLookback;
    }

    uint256 total = 0;

    for (uint256 i = initialIndex; i < count; ++i) {
      index = _getIndexOfObservation(i);
      total = total + pegObservations[index];
    }

    return total * 10000 / auctionAverageLookback;
  }

  function _getIndexOfObservation(uint _index) internal view returns (uint index) {
    return _index % auctionAverageLookback;
  }

}
