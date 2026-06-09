pragma solidity 0.8.10;

struct OptimisticLedger {
    mapping(address => UFixed18) balances;
    UFixed18 total;
    UFixed18 shortfall;
}

library OptimisticLedgerLib {
    using UFixed18Lib for UFixed18;
    using Fixed18Lib for Fixed18;

    function settleAccount(OptimisticLedger storage self, address account, Fixed18 amount)
    internal returns (UFixed18 shortfall) {
        Fixed18 newBalance = Fixed18Lib.from(self.balances[account]).add(amount);

        if (newBalance.sign() == -1) {
            shortfall = self.shortfall.add(newBalance.abs());
            newBalance = Fixed18Lib.ZERO;
        }

        self.balances[account] = newBalance.abs();
        self.shortfall = self.shortfall.add(shortfall);
    }

    function debit(OptimisticLedger storage self, UFixed18 amount) internal {
        self.total = self.total.sub(amount);
    }
}
