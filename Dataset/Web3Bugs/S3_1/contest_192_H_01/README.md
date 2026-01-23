# H-01: Lock.sol: assets deposited with Lock.extendLock function are lost

**Contest**: 192
**Reference**: https://code4rena.com/reports/2022-12-tigris#h-01-locksol-assets-deposited-with-lockextendlock-function-are-lost

## Bug Report

## [[H-01] Lock.sol: assets deposited with Lock.extendLock function are lost](https://github.com/code-423n4/2022-12-tigris-findings/issues/23)
*Submitted by [HollaDieWaldfee](https://github.com/code-423n4/2022-12-tigris-findings/issues/23), also found by [sha256yan](https://github.com/code-423n4/2022-12-tigris-findings/issues/560), [kaliberpoziomka8552](https://github.com/code-423n4/2022-12-tigris-findings/issues/558), [0xsomeone](https://github.com/code-423n4/2022-12-tigris-findings/issues/447), [cccz](https://github.com/code-423n4/2022-12-tigris-findings/issues/330), [0xbepresent](https://github.com/code-423n4/2022-12-tigris-findings/issues/264), [ali\_shehab](https://github.com/code-423n4/2022-12-tigris-findings/issues/262), [Ruhum](https://github.com/code-423n4/2022-12-tigris-findings/issues/253), [rvierdiiev](https://github.com/code-423n4/2022-12-tigris-findings/issues/180), and [csanuragjain](https://github.com/code-423n4/2022-12-tigris-findings/issues/132)*

<https://github.com/code-423n4/2022-12-tigris/blob/496e1974ee3838be8759e7b4096dbee1b8795593/contracts/Lock.sol#L10> 

<https://github.com/code-423n4/2022-12-tigris/blob/496e1974ee3838be8759e7b4096dbee1b8795593/contracts/Lock.sol#L61-L76> 

<https://github.com/code-423n4/2022-12-tigris/blob/496e1974ee3838be8759e7b4096dbee1b8795593/contracts/Lock.sol#L84-L92> 

<https://github.com/code-423n4/2022-12-tigris/blob/496e1974ee3838be8759e7b4096dbee1b8795593/contracts/Lock.sol#L98-L105>

##
