# H-03: Approval for NFT transfers is not removed after transfer

**Contest**: 10
**Reference**: https://code4rena.com/reports/2021-05-visorfinance#h-03-approval-for-nft-transfers-is-not-removed-after-transfer

## Bug Report

## [[H-03] Approval for NFT transfers is not removed after transfer](https://github.com/code-423n4/2021-05-visorfinance-findings/issues/48)
_Submitted by cmichel, also found by gpersoon, and pauliax_

The `Visor.transferERC721` does not reset the approval for the NFT.

An approved delegatee can move the NFT out of the contract once.
It could be moved to a market and bought by someone else who then deposits it again to the same vault.
The first delegatee can steal the NFT and move it out of the contract a second time.

Recommend resetting the approval on transfer.

**[xyz-ctrl (Visor) confirmed](https://github.com/code-423n4/2021-05-visorfinance-findings/issues/48#issuecomment-856953219):**
> We will be mitigating this issue for our next release and before these experimental features are introduced in platform.
> PR pending

**[ztcrypto (Visor) commented](https://github.com/code-423n4/2021-05-visorfinance-findings/issues/48#issuecomment-889192312):**
> duplicate of above ones and fixed


