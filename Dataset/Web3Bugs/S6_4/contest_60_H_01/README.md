# H-01: Wrong shortfall calculation

**Contest**: 60
**Reference**: https://code4rena.com/reports/2021-12-perennial#h-01-wrong-shortfall-calculation

## Bug Report

## [[H-01] Wrong shortfall calculation](https://github.com/code-423n4/2021-12-perennial-findings/issues/18)
_Submitted by kenzo_

Every time an account is settled, if shortfall is created, due to a wrong calculation shortfall will double in size and add the new shortfall.

###
