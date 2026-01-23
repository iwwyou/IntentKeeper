# H-05: AuctionEschapeHatch.sol#exitEarly updates state of the auction wrongly

**Contest**: 59
**Reference**: https://code4rena.com/reports/2021-11-malt#h-05-auctioneschapehatchsolexitearly-updates-state-of-the-auction-wrongly

## Bug Report

## [[H-05] AuctionEschapeHatch.sol#exitEarly updates state of the auction wrongly](https://github.com/code-423n4/2021-11-malt-findings/issues/268)
_Submitted by 0x0x0x_

`AuctionEschapeHatch.sol#exitEarly` takes as input `amount` to represent how much of the

When the user exits an auction with profit, to apply the profit penalty less `maltQuantity` is liquidated compared to how much malt token the liquidated amount corresponds to. The problem is `auction.amendAccountParticipation()` simply subtracts the malt quantity with penalty and full `amount` from users auction stats. This causes a major problem, since in `_calculateMaltRequiredForExit` those values are used for calculation by calculating maltQuantity as follow:

`uint256 maltQuantity = userMaltPurchased.mul(amount).div(userCommitment);`

The ratio of `userMaltPurchased / userCommitment` gets higher after each profit taking (since penalty is applied to substracted `maltQuantity` from `userMaltPurchased`), by doing so a user can earn more than it should. Since after each profit taking users commitment corresponds to proportionally more malt, the user can even reduce profit penalties by dividing `exitEarly` calls in several calls.

In other words, the ratio of `userMaltPurchased / userCommitment` gets higher after each profit taking and user can claim more malt with less commitment. Furthermore after all `userMaltPurchased` is claimed the user can have `userCommitment` left over, which can be used to `claimArbitrage`, when possible.

###
