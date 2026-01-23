# H-02: unstake should update exchange rates first

**Contest**: 43
**Reference**: https://code4rena.com/reports/2021-10-covalent#h-02-unstake-should-update-exchange-rates-first

## Bug Report

## [[H-02] `unstake` should update exchange rates first](https://github.com/code-423n4/2021-10-covalent-findings/issues/57)
_Submitted by cmichel_

The `unstake` function does not immediately update the exchange rates. It first computes the `validatorSharesRemove = tokensToShares(amount, v.exchangeRate)` **with the old exchange rate**.

Only afterwards, it updates the exchange rates (if the validator is not disabled):

```solidity
// @audit shares are computed here with old rate
uint128 validatorSharesRemove = tokensToShares(amount, v.exchangeRate);
require(validatorSharesRemove > 0, "Unstake amount is too small");

if (v.disabledEpoch == 0) {
    // @audit rates are updated here
    updateGlobalExchangeRate();
    updateValidator(v);
    // ...
}
```

###
