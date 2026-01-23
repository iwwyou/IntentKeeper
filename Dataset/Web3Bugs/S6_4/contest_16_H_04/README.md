# H-04: Logic error in fee subtraction

**Contest**: 16
**Reference**: https://code4rena.com/reports/2021-06-tracer#h-04-logic-error-in-fee-subtraction

## Bug Report

## [[H-04] Logic error in fee subtraction](https://github.com/code-423n4/2021-06-tracer-findings/issues/127)
_Submitted by 0xsanson_

In `LibBalances.applyTrade()`, we need to collect a fee from the trade. However, the current code subtracts a fee from the short position and adds it to the long. The correct implementation is to subtract a fee to both (see `TracerPerpetualSwaps.sol` L272).
This issue causes withdrawals problems, since Tracer thinks it can withdraw the collect fees, leaving the users with an incorrect amount of quote tokens.

Recommend changing `+fee` to `-fee` in the [highlighted line](https://github.com/code-423n4/2021-06-tracer/blob/main/src/contracts/lib/LibBalances.sol#L187).

**[raymogg (Tracer) confirmed](https://github.com/code-423n4/2021-06-tracer-findings/issues/127#issuecomment-873778933):**
 > Valid issue 👍


