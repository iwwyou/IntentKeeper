# H-04: Inconsistent usage of applyInterest

**Contest**: 3
**Reference**: https://code4rena.com/reports/2021-04-marginswap#h-04-inconsistent-usage-of-applyinterest

## Bug Report

## [[H-04] Inconsistent usage of `applyInterest`](https://github.com/code-423n4/2021-04-marginswap-findings/issues/64)

It is unclear if the function `applyInterest` is supposed to return a new balance with the interest applied or only the accrued interest? There are various usages of it, some calls add the return value to the old amount:

```solidity
return
bond.amount +
applyInterest(bond.amount, cumulativeYield, yieldQuotientFP);
and some not:

balanceWithInterest = applyInterest(
balance,
yA.accumulatorFP,
yieldQuotientFP
);
```

This makes the code misbehave and return the wrong values for the balance and accrued interest.

Recommend making it consistent in all cases when calling this function.


