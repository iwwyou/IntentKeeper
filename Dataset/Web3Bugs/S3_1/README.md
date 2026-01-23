# S3-1 Bugs

## H-07: account.holdsToken is never set
- Directory: `contest_3_H_07/`
- Reference: https://code4rena.com/reports/2021-04-marginswap#h-07-accountholdstoken-is-never-set

## H-02: NFT transfer approvals are not removed and cannot be revoked thus leading to loss of NFT tokens
- Directory: `contest_10_H_02/`
- Reference: https://code4rena.com/reports/2021-05-visorfinance#h-02-nft-transfer-approvals-are-not-removed-and-cannot-be-revoked-thus-leading-to-loss-of-nft-tokens

## H-03: Approval for NFT transfers is not removed after transfer
- Directory: `contest_10_H_03/`
- Reference: https://code4rena.com/reports/2021-05-visorfinance#h-03-approval-for-nft-transfers-is-not-removed-after-transfer

## H-02: LendingPair.liquidateAccount does not accrue and update cumulativeInterestRate
- Directory: `contest_18_H_02/`
- Reference: https://code4rena.com/reports/2021-07-wildcredit#h-02-lendingpairliquidateaccount-does-not-accrue-and-update-cumulativeinterestrate

## H-05: Approval is not reset if the call to IFulfillHelper fails
- Directory: `contest_19_H_05/`
- Reference: https://code4rena.com/reports/2021-07-connext-findings#h-05-approval-is-not-reset-if-the-call-to-ifulfillhelper-fails

## H-03: setYieldSource leads to temporary wrong results
- Directory: `contest_24_H_03/`
- Reference: https://code4rena.com/reports/2021-07-pooltogether#h-03-setyieldsource-leads-to-temporary-wrong-results

## H-02: ERC20Rewards returns wrong rewards if no tokens initially exist
- Directory: `contest_25_H_02/`
- Reference: https://code4rena.com/reports/2021-08-yield#h-02-erc20rewards-returns-wrong-rewards-if-no-tokens-initially-exist

## H-03: ConcentratedLiquidityPoolManager’s incentives can be stolen
- Directory: `contest_35_H_03/`
- Reference: https://code4rena.com/reports/2021-09-sushitrident-2#h-03-concentratedliquiditypoolmanagers-incentives-can-be-stolen

## H-02: Basket.sol#auctionBurn() A failed auction will freeze part of the funds
- Directory: `contest_36_H_02/`
- Reference: https://code4rena.com/reports/2021-09-defiprotocol#h-02-basketsolauctionburn-a-failed-auction-will-freeze-part-of-the-funds

## H-06: Referrer can drain ReferralFeePoolV0
- Directory: `contest_42_H_06/`
- Reference: https://code4rena.com/reports/2021-10-mochi#h-06-referrer-can-drain-referralfeepoolv0

## H-03: SwapUtils.sol Wrong implementation
- Directory: `contest_51_H_03/`
- Reference: https://code4rena.com/reports/2021-11-bootfinance#h-03-swaputilssol-wrong-implementation

## H-03: MixinTransfer.sol#transferFrom Wrong implementation can potentially allows attackers to reverse transfer and cause fund loss to the users
- Directory: `contest_54_H_03/`
- Reference: https://code4rena.com/reports/2021-11-unlock#h-03-mixintransfersoltransferfrom-wrong-implementation-can-potentially-allows-attackers-to-reverse-transfer-and-cause-fund-loss-to-the-users

## H-04: Approvals not cleared after key transfer
- Directory: `contest_54_H_04/`
- Reference: https://code4rena.com/reports/2021-11-unlock#h-04-approvals-not-cleared-after-key-transfer

## H-04: AaveVault does not update TVL on deposit/withdraw
- Directory: `contest_58_H_04/`
- Reference: https://code4rena.com/reports/2021-12-mellow#h-04-aavevault-does-not-update-tvl-on-depositwithdraw

## H-08: ts.tokens sometimes calculated incorrectly
- Directory: `contest_62_H_08/`
- Reference: https://code4rena.com/reports/2021-11-streaming#h-08-tstokens-sometimes-calculated-incorrectly

## H-01: Wrong fee calculation after totalSupply was 0
- Directory: `contest_65_H_01/`
- Reference: https://code4rena.com/reports/2021-12-defiprotocol#h-01-wrong-fee-calculation-after-totalsupply-was-0

## H-01: Unused ERC20 tokens are not refunded
- Directory: `contest_68_H_01/`
- Reference: and can be stolen by attacker"

## H-10: previousPrices Is Never Updated Upon Syncing Token Price
- Directory: `contest_70_H_10/`
- Reference: https://code4rena.com/reports/2021-12-vader#h-10-previousprices-is-never-updated-upon-syncing-token-price

## H-01: Wrong reward token calculation in MasterChef contract
- Directory: `contest_83_H_01/`
- Reference: https://code4rena.com/reports/2022-02-concur#h-01-wrong-reward-token-calculation-in-masterchef-contract

## H-02: function lockFunds in TopUpActionLibrary can cause serious fund lose. fee and Capped bypass. It’s not calling stakerVault.increaseActionLockedBalance when transfers stakes.
- Directory: `contest_112_H_02/`
- Reference: https://code4rena.com/reports/2022-04-backd#h-02-function-lockfunds-in-topupactionlibrary-can-cause-serious-fund-lose-fee-and-capped-bypass-its-not-calling-stakervaultincreaseactionlockedbalance-when-transfers-stakes

## H-03: Critical Oracle Manipulation Risk by Lender
- Directory: `contest_113_H_03/`
- Reference: https://code4rena.com/reports/2022-04-abranft#h-03-critical-oracle-manipulation-risk-by-lender

## H-01: Lock.sol: assets deposited with Lock.extendLock function are lost
- Directory: `contest_192_H_01/`
- Reference: https://code4rena.com/reports/2022-12-tigris#h-01-locksol-assets-deposited-with-lockextendlock-function-are-lost

