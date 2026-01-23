# H-12: getAddedAmount can return wrong results

**Contest**: 5
**Reference**: https://code4rena.com/reports/2021-04-vader#h-12-getaddedamount-can-return-wrong-results

## Bug Report

## [[H-12] `getAddedAmount` can return wrong results](https://github.com/code-423n4/2021-04-vader-findings/issues/206)

The `getAddedAmount` function only works correctly when called with `(VADER/USDV, pool)` or `(pool, pool)`.
However, when called with (`token, pool)` where `token` is neither `VADER/USDV/pool`, it returns the wrong results:

1. It gets the `token` balance
2. And subtracts it from the stored `mapToken_tokenAmount[_pool]` amount which can be that of a completely different token

Anyone can break individual pairs by calling `sync(token1, token2)` where the `token1` balance is less than `mapToken_tokenAmount[token2]`. This will add the difference to `mapToken_tokenAmount[token2]` and break the accounting and result in a wrong swap logic.

Furthermore, this can also be used to swap tokens without having to pay anthing with `swap(token1, token2, member, toBase=false)`.

Recommend adding a require statement in the `else` branch that checks that `_token == _pool`.

**[strictly-scarce (vader) confirmed](https://github.com/code-423n4/2021-04-vader-findings/issues/206#issuecomment-830610039):**
 > Valid, funds can be lost

**[strictly-scarce (vader) commented](https://github.com/code-423n4/2021-04-vader-findings/issues/206#issuecomment-830610281):**
 > Would bundle this issue with:
> https://github.com/code-423n4/2021-04-vader-findings/issues/205



