# H-02: Mint spread collateral-less and conjuring collateral claims out of thin air with implicit arithmetic rounding and flawed int to uint conversion

**Contest**: 98
**Reference**: https://code4rena.com/reports/2022-03-rolla#h-02-mint-spread-collateral-less-and-conjuring-collateral-claims-out-of-thin-air-with-implicit-arithmetic-rounding-and-flawed-int-to-uint-conversion

## Bug Report

## [[H-02] Mint spread collateral-less and conjuring collateral claims out of thin air with implicit arithmetic rounding and flawed int to uint conversion](https://github.com/code-423n4/2022-03-rolla-findings/issues/31)
_Submitted by rayn_

[QuantMath.sol#L137](https://github.com/code-423n4/2022-03-rolla/blob/main/quant-protocol/contracts/libraries/QuantMath.sol#L137)<br>
[QuantMath.sol#L151](https://github.com/code-423n4/2022-03-rolla/blob/main/quant-protocol/contracts/libraries/QuantMath.sol#L151)<br>
[SignedConverter.sol#L28](https://github.com/code-423n4/2022-03-rolla/blob/main/quant-protocol/contracts/libraries/SignedConverter.sol#L28)<br>

This report presents 2 different incorrect behaviour that can affect the correctness of math calculations:

1.  Unattended Implicit rounding in QuantMath.sol `div` and `mul`
2.  Inappropriate method of casting integer to unsigned integer in SignedConverter.sol `intToUint`

Bug 1 affects the correctness when calculating collateral required for `_mintSpread`. Bug 2 expands the attack surface and allows attackers to target the `_claimCollateral` phase instead. Both attacks may result in tokens being stolen from Controller in the worst case, but is most likely too costly to exploit under current BNB chain environment. The potential impact however, should not be taken lightly, since it is known that the ethereum environment in highly volatile and minor changes in the environment can suddenly make those bugs cheap to exploit.

##
