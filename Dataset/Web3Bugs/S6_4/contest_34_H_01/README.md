# H-01: The formula of number of prizes for a degree is wrong

**Contest**: 34
**Reference**: https://code4rena.com/reports/2021-10-pooltogether#h-01-the-formula-of-number-of-prizes-for-a-degree-is-wrong

## Bug Report

## [[H-01] The formula of number of prizes for a degree is wrong](https://github.com/code-423n4/2021-10-pooltogether-findings/issues/33)
_Submitted by WatchPug, also found by cmichel_.

The formula of the number of prizes for a degree per the document: <https://v4.docs.pooltogether.com/protocol/concepts/prize-distribution/#splitting-the-prizes> is:

    Number of prizes for a degree = (2^bit range)^degree - (2^bit range)^(degree-1) - (2^bit range)^(degree-2) - ...

Should be changed to:

    Number of prizes for a degree = (2^bit range)^degree - (2^bit range)^(degree-1)

or

    Number of prizes for a degree = 2^(bit range * degree) - 2^(bit range * (degree-1))

####
