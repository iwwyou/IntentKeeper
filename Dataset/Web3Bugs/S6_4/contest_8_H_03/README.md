# H-03: getRandomTokenIdFromFund yields wrong probabilities for ERC1155

**Contest**: 8
**Reference**: https://code4rena.com/reports/2021-05-nftx#h-03-getrandomtokenidfromfund-yields-wrong-probabilities-for-erc1155

## Bug Report

## [[H-03] `getRandomTokenIdFromFund` yields wrong probabilities for ERC1155](https://github.com/code-423n4/2021-05-nftx-findings/issues/56)

`NFTXVaultUpgradeable.getRandomTokenIdFromFund` does not work with ERC1155 as it does not take the deposited `quantity1155` into account.

Assume `tokenId0` has a count of 100, and `tokenId1` has a count of 1.
Then `getRandomId` would have a pseudo-random 1:1 chance for token 0 and 1 when in reality it should be 100:1.

This might make it easier for an attacker to redeem more valuable NFTs as the probabilities are off.

Recommend taking the quantities of each token into account (`quantity1155`) which probably requires a design change as it is currently hard to do without iterating over all tokens.

**[0xKiwi (NFTX) acknowledged](https://github.com/code-423n4/2021-05-nftx-findings/issues/56)**

**[cemozer (Judge) commented](https://github.com/code-423n4/2021-05-nftx-findings/issues/56#issuecomment-848266608):**
 > Marking this as high risk as an attacker can weed out high-value NFTs from a vault putting other users funds at risk


