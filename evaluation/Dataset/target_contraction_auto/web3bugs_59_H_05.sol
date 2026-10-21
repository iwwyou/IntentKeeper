pragma solidity >=0.6.6;

struct EarlyExitData {
  uint256 exitedEarly;
  uint256 earlyExitReturn;
  uint256 maltUsed;
}

struct AuctionExits {
  uint256 exitedEarly;
  uint256 earlyExitReturn;
  uint256 maltUsed;
  mapping(address => EarlyExitData) accountExits;
}

contract AuctionEscapeHatch is Initializable, Permissions {
  using SafeMath for uint256;
  using SafeERC20 for ERC20;

  IAuction public auction;
  IDexHandler public dexHandler;
  ERC20 public collateralToken;
  IBurnMintableERC20 public malt;
  uint256 public maxEarlyExitBps = 200;
  uint256 public cooloffPeriod = 60 * 60 * 24;

  mapping(uint256 => AuctionExits) internal auctionEarlyExits;

  event EarlyExit(address account, uint256 amount, uint256 received);

  function exitEarly(uint256 _auctionId, uint256 amount, uint256 minOut) external notSameBlock {
    uint256 maltQuantity = _calculateMaltRequiredForExit(_auctionId, amount);

    malt.mint(address(dexHandler), maltQuantity);
    uint256 amountOut = dexHandler.sellMalt();

    require(amountOut > minOut, "EarlyExit: Insufficient output");

    AuctionExits storage auctionExits = auctionEarlyExits[_auctionId];

    auctionExits.exitedEarly = auctionExits.exitedEarly + amount;
    auctionExits.earlyExitReturn = auctionExits.earlyExitReturn + amountOut;
    auctionExits.maltUsed = auctionExits.maltUsed + maltQuantity;
    auctionExits.accountExits[msg.sender].exitedEarly = auctionExits.accountExits[msg.sender].exitedEarly + amount;
    auctionExits.accountExits[msg.sender].earlyExitReturn = auctionExits.accountExits[msg.sender].earlyExitReturn + amountOut;
    auctionExits.accountExits[msg.sender].maltUsed = auctionExits.accountExits[msg.sender].maltUsed + maltQuantity;

    auction.amendAccountParticipation(msg.sender, _auctionId, amount, maltQuantity);

    collateralToken.safeTransfer(msg.sender, amountOut);
    emit EarlyExit(msg.sender, amount, amountOut);
  }

  function _calculateMaltRequiredForExit(uint256 _auctionId, uint256 amount) internal returns(uint256) {
    (,,,,, uint256 pegPrice,, uint256 auctionEndTime, bool active) = auction.getAuctionCore(_auctionId);

    require(!active, "Cannot exit early on an active auction");
    require(block.timestamp > auctionEndTime, "Auction not over");

    (uint256 userCommitment, uint256 userRedeemed, uint256 userMaltPurchased) = auction.getAuctionParticipationForAccount(msg.sender, _auctionId);

    if (amount > (userCommitment - userRedeemed)) {
      amount = userCommitment - userRedeemed;
    }

    require(amount > 0, "Nothing to claim");

    (uint256 currentPrice,) = dexHandler.maltMarketPrice();

    uint256 maltQuantity = userMaltPurchased.mul(amount).div(userCommitment);

    uint256 fullReturn = maltQuantity.mul(currentPrice) / pegPrice;

    uint256 progressionBps = (block.timestamp - auctionEndTime) * 10000 / cooloffPeriod;
    if (progressionBps > 10000) {
      progressionBps = 10000;
    }

    if (fullReturn > amount) {
      uint256 maxProfit = (fullReturn - amount) * (maxEarlyExitBps * progressionBps / 10000) / 1000;
      uint256 desiredReturn = amount + maxProfit;
      maltQuantity = desiredReturn.mul(pegPrice) / currentPrice;
    }

    return maltQuantity;
  }

}
