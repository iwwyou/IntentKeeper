# H-03: Critical Oracle Manipulation Risk by Lender

**Contest**: 113
**Reference**: https://code4rena.com/reports/2022-04-abranft#h-03-critical-oracle-manipulation-risk-by-lender

## Bug Report

## [[H-03] Critical Oracle Manipulation Risk by Lender](https://github.com/code-423n4/2022-04-abranft-findings/issues/37)
_Submitted by 0x1337, also found by catchup, cccz, kenzo, GimelSec, BowTiedWardens, gzeon, horsefacts, and hyh_

<https://github.com/code-423n4/2022-04-abranft/blob/5cd4edc3298c05748e952f8a8c93e42f930a78c2/contracts/NFTPairWithOracle.sol#L286-L288>

<https://github.com/code-423n4/2022-04-abranft/blob/5cd4edc3298c05748e952f8a8c93e42f930a78c2/contracts/NFTPairWithOracle.sol#L200-L211>

The intended use of the Oracle is to protect the lender from a drop in the borrower's collateral value. If the collateral value goes up significantly and higher than borrowed amount + interest, the lender should not be able to seize the collateral at the expense of the borrower. However, in the `NFTPairWithOracle` contract, the lender could change the Oracle once a loan is outstanding, and therefore seize the collateral at the expense of the borrower, if the actual value of the collateral has increased significantly. This is a critical risk because borrowers asset could be lost to malicious lenders.

##
