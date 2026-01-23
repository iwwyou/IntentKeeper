# H-02: Use of incorrect index leads to incorrect updation of funding rates

**Contest**: 16
**Reference**: https://code4rena.com/reports/2021-06-tracer#h-02-use-of-incorrect-index-leads-to-incorrect-updation-of-funding-rates

## Bug Report

## [[H-02] Use of incorrect index leads to incorrect updation of funding rates](https://github.com/code-423n4/2021-06-tracer-findings/issues/74)
_Submitted by 0xRajeev_

The `updateFundingRate()` function updates the funding rate and insurance funding rate. While the instant/new funding rates are calculated correctly, the cumulative funding rate calculation is incorrect because it is always adding the instant to 0, not the previous value. This is due to the use of `[currentFundingIndex]` which has been updated since the previous call to this function while it should really be using `[currentFundingIndex-1]` to reference the previous funding rate.

The impact of this, is that the cumulative funding rate and insurance funding rates are calculated incorrectly without considering the correct previous values. This affects the settling of accounts across the entire protocol. The protocol logic is significantly impacted, accounts will not be settled as expected, protocol shutdown and contracts will need to be redeployed. Users may lose funds and the protocol takes a reputation hit.

Recommend using `[currentFundingIndex-1]` for non-zero values of `currentFundingIndex` to get the value updated in the previous call on lines L155 and L159 of `Pricing.sol`.

**[raymogg (Tracer) confirmed](https://github.com/code-423n4/2021-06-tracer-findings/issues/74#issuecomment-873752562):**
 > Confirmed as an index issue with funding rate 👍



