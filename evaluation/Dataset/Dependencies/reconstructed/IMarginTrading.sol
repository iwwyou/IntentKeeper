// SPDX-License-Identifier: BUSL-1.1
// RECONSTRUCTED (IQDebug evaluation): the code4rena 2021-04-marginswap snapshot omits contracts/interfaces/
// and the marginswap GitHub organisation no longer exists. Every member below is (a) called through
// `IMarginTrading(...)` in MarginRouter.sol and (b) implemented with `override` in CrossMarginTrading.sol;
// the signatures are copied from that implementation. Interfaces emit no bytecode; selectors depend only
// on these signatures, so the compiled target (CrossMarginAccounts) is unaffected.
pragma solidity ^0.8.0;

interface IMarginTrading {
    function registerDeposit(address trader, address token, uint256 depositAmount)
        external
        returns (uint256 extinguishableDebt);

    function registerWithdrawal(address trader, address withdrawToken, uint256 withdrawAmount) external;

    function registerBorrow(address trader, address borrowToken, uint256 borrowAmount) external;

    function registerOvercollateralizedBorrow(
        address trader,
        address depositToken,
        uint256 depositAmount,
        address borrowToken,
        uint256 withdrawAmount
    ) external;

    function registerTradeAndBorrow(
        address trader,
        address tokenFrom,
        address tokenTo,
        uint256 inAmount,
        uint256 outAmount
    ) external returns (uint256 extinguishableDebt, uint256 borrowAmount);

    function registerLiquidation(address trader) external;

    function getHoldingAmounts(address trader)
        external
        view
        returns (address[] memory holdingTokens, uint256[] memory holdingAmounts);

    function getBorrowAmounts(address trader)
        external
        view
        returns (address[] memory borrowTokens, uint256[] memory borrowAmounts);
}
