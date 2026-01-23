# H-11: Not enough margin pulled or burned from user when adding to a position

**Contest**: 192
**Reference**: https://code4rena.com/reports/2022-12-tigris#h-11-not-enough-margin-pulled-or-burned-from-user-when-adding-to-a-position

## Bug Report

## [[H-11] Not enough margin pulled or burned from user when adding to a position](https://github.com/code-423n4/2022-12-tigris-findings/issues/659)
*Submitted by [minhtrng](https://github.com/code-423n4/2022-12-tigris-findings/issues/659), also found by [Aymen0909](https://github.com/code-423n4/2022-12-tigris-findings/issues/644), [hansfriese](https://github.com/code-423n4/2022-12-tigris-findings/issues/505), [0Kage](https://github.com/code-423n4/2022-12-tigris-findings/issues/488), [Jeiwan](https://github.com/code-423n4/2022-12-tigris-findings/issues/433), [bin2chen](https://github.com/code-423n4/2022-12-tigris-findings/issues/325), [KingNFT](https://github.com/code-423n4/2022-12-tigris-findings/issues/209), [HollaDieWaldfee](https://github.com/code-423n4/2022-12-tigris-findings/issues/194), and [rvierdiiev](https://github.com/code-423n4/2022-12-tigris-findings/issues/130)*

When adding to a position, the amount of margin pulled from the user is not as much as it should be, which leaks value from the protocol, lowering the collateralization ratio of `tigAsset`.

##
