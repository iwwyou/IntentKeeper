# H-01: ERC4626 mint uses wrong amount

**Contest**: 92
**Reference**: https://code4rena.com/reports/2022-02-tribe-turbo#h-01-erc4626-mint-uses-wrong-amount

## Bug Report

## [[H-01] ERC4626 mint uses wrong `amount`](https://github.com/code-423n4/2022-02-tribe-turbo-findings/issues/27)
_Submitted by cmichel, also found by 0xliumin, CertoraInc, Picodes, and Ruhum_

> The docs/video say `ERC4626.sol` is in scope as its part of `TurboSafe`

The `ERC4626.mint` function mints `amount` instead of `shares`.
This will lead to issues when the `asset <> shares` are not 1-to-1 as will be the case for most vaults over time.
Usually, the asset amount is larger than the share amount as vaults receive asset yield.
Therefore, when minting, `shares` should be less than `amount`.
Users receive a larger share amount here which can be exploited to drain the vault assets.

```solidity
function mint(uint256 shares, address to) public virtual returns (uint256 amount) {
    amount = previewMint(shares); // No need to check for rounding error, previewMint rounds up.

    // Need to transfer before minting or ERC777s could reenter.
    asset.safeTransferFrom(msg.sender, address(this), amount);
    _mint(to, amount);

    emit Deposit(msg.sender, to, amount, shares);

    afterDeposit(amount, shares);
}
```

##
