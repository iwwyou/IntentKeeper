# H-01: borrow must accrueInterest first

**Contest**: 45
**Reference**: https://code4rena.com/reports/2021-10-union#h-01-borrow-must-accrueinterest-first

## Bug Report

## [[H-01] `borrow` must `accrueInterest` first](https://github.com/code-423n4/2021-10-union-findings/issues/66)
_Submitted by cmichel_

The `UToken.borrow` function first checks the borrowed balance and the old credit limit *before* accruing the actual interest on the market:

```solidity
// @audit this uses the old value
require(borrowBalanceView(msg.sender) + amount + fee <= maxBorrow, "UToken: amount large than borrow size max");

require(
    // @audit this calls uToken.calculateInterest(account) which returns old value
    uint256(_getCreditLimit(msg.sender)) >= amount + fee,
    "UToken: The loan amount plus fee is greater than credit limit"
);

// @audit accrual only happens here
require(accrueInterest(), "UToken: accrue interest failed");
```

Thus the borrowed balance of the user does not include the latest interest as it uses the old global `borrowIndex` but the new `borrowIndex` is only set in `accrueInterest`.

###
