# Web3Bugs - Single Transaction Numeric Bugs

> **Source**: https://github.com/ZhangZhuoSJTU/Web3Bugs
> **Total Bugs in Dataset**: 493
> **Single TX Numeric Bugs**: 110

---

## Summary

| Label | Category | Count | Description |
|-------|----------|-------|-------------|
| L2 | Rounding/Precision Loss | 7 | Simple oracle - detectable by precision loss checker |
| L7 | Integer Overflow/Underflow | 17 | Simple oracle - detectable by overflow checker |
| S6-1 | Incorrect Calculating Order | 8 | Semantic - wrong order of operations |
| S6-2 | Unexpected Return Value | 4 | Semantic - return value deviates from expected |
| S6-3 | Wrong Numbers in Calculation | 18 | Semantic - e.g., x = a + b => x = a + c |
| S6-4 | Other Accounting Errors | 56 | Semantic - e.g., x = a + b => x = a - b |

---

## Detailed Bug List

### L2: Rounding/Precision Loss (7 bugs)

> Simple oracle - detectable by precision loss checker

1. **IdleYieldSource doesn’t use mantissa calculations**
   - Contest: 14, Bug: H-05
   - Reference: https://code4rena.com/reports/2021-06-pooltogether#h-05-idleyieldsource-doesnt-use-mantissa-calculations

2. **customPrecisionMultipliers would be rounded to zero and break the pool**
   - Contest: 51, Bug: H-07
   - Reference: https://code4rena.com/reports/2021-11-bootfinance#h-07-customprecisionmultipliers-would-be-rounded-to-zero-and-break-the-pool

3. **USDV and VADER rate can be wrong**
   - Contest: 52, Bug: H-08
   - Reference: https://code4rena.com/reports/2021-11-vader#h-08-usdv-and-vader-rate-can-be-wrong

4. **IndexTemplate.sol#compensate() will most certainly fail**
   - Contest: 71, Bug: H-08
   - Reference: https://code4rena.com/reports/2022-01-insure#h-08-indextemplatesolcompensate-will-most-certainly-fail

5. **Users will lose a majority or even all of the rewards when the amount of total shares is too large**
   - Contest: 97, Bug: H-05
   - Reference: due to precision loss"
   - Comment: https://code4rena.com/reports/2022-03-biconomy#h-05-users-will-lose-a-majority-or-even-all-of-the-rewards-when-the-amount-of-total-shares-is-too-large-due-to-precision-loss

6. **Mint spread collateral-less and conjuring collateral claims out of thin air with implicit arithmetic rounding and flawed int to uint conversion**
   - Contest: 98, Bug: H-02
   - Reference: https://code4rena.com/reports/2022-03-rolla#h-02-mint-spread-collateral-less-and-conjuring-collateral-claims-out-of-thin-air-with-implicit-arithmetic-rounding-and-flawed-int-to-uint-conversion

7. **DropPerSecond is not updated homogeneously**
   - Contest: 105, Bug: H-01
   - Reference: the rewards emission can be much higher than expected in some cases"
   - Comment: https://code4rena.com/reports/2022-03-paladin#h-01-droppersecond-is-not-updated-homogeneously-the-rewards-emission-can-be-much-higher-than-expected-in-some-cases

---

### L7: Integer Overflow/Underflow (17 bugs)

> Simple oracle - detectable by overflow checker

1. **Missing overflow check in flashLoan**
   - Contest: 8, Bug: H-01
   - Reference: https://code4rena.com/reports/2021-05-nftx#h-01-missing-overflow-check-in-flashloan

2. **YearnV2YieldSource wrong subtraction in withdraw**
   - Contest: 14, Bug: H-02
   - Reference: https://code4rena.com/reports/2021-06-pooltogether#h-02-yearnv2yieldsource-wrong-subtraction-in-withdraw

3. **implicit underflows**
   - Contest: 17, Bug: H-01
   - Reference: https://code4rena.com/reports/2021-06-gro#h-01-implicit-underflows

4. **IndexPool pow overflows when weightRatio > 10.**
   - Contest: 29, Bug: H-03
   - Reference: https://code4rena.com/reports/2021-09-sushitrident#h-03-indexpool-pow-overflows-when-weightratio--10

5. **Unsafe cast in IndexPool mint leads to attack**
   - Contest: 29, Bug: H-09
   - Reference: https://code4rena.com/reports/2021-09-sushitrident#h-09-unsafe-cast-in-indexpool-mint-leads-to-attack

6. **Overflow in the mint function of IndexPool causes LPs’ funds to be stolen**
   - Contest: 29, Bug: H-13
   - Reference: https://code4rena.com/reports/2021-09-sushitrident#h-13-overflow-in-the-mint-function-of-indexpool-causes-lps-funds-to-be-stolen

7. **Unsafe cast in ConcentratedLiquidityPool.burn leads to attack**
   - Contest: 35, Bug: H-01
   - Reference: https://code4rena.com/reports/2021-09-sushitrident-2#h-01-unsafe-cast-in-concentratedliquiditypoolburn-leads-to-attack

8. **Overflow in the mint function of ConcentratedLiquidityPool causes LPs’ funds to be stolen**
   - Contest: 35, Bug: H-04
   - Reference: https://code4rena.com/reports/2021-09-sushitrident-2#h-04-overflow-in-the-mint-function-of-concentratedliquiditypool-causes-lps-funds-to-be-stolen

9. **Incorrect usage of typecasting in _getAmountsForLiquidity lets an attacker steal funds from the pool**
   - Contest: 35, Bug: H-05
   - Reference: https://code4rena.com/reports/2021-09-sushitrident-2#h-05-incorrect-usage-of-typecasting-in-_getamountsforliquidity-lets-an-attacker-steal-funds-from-the-pool

10. **range fee growth underflow**
   - Contest: 35, Bug: H-09
   - Reference: https://code4rena.com/reports/2021-09-sushitrident-2#h-09-range-fee-growth-underflow

11. **ConcentratedLiquidityPool: rangeFeeGrowth and secondsPerLiquidity math needs to be unchecked**
   - Contest: 35, Bug: H-14
   - Reference: https://code4rena.com/reports/2021-09-sushitrident-2#h-14-concentratedliquiditypool-rangefeegrowth-and-secondsperliquidity-math-needs-to-be-unchecked

12. **ConcentratedLiquidityPool: initialPrice should be checked to be within allowable range**
   - Contest: 35, Bug: H-15
   - Reference: https://code4rena.com/reports/2021-09-sushitrident-2#h-15-concentratedliquiditypool-initialprice-should-be-checked-to-be-within-allowable-range

13. **Liquidation will never work with non-zero discounts**
   - Contest: 42, Bug: H-07
   - Reference: https://code4rena.com/reports/2021-10-mochi#h-07-liquidation-will-never-work-with-non-zero-discounts

14. **DOS while dealing with erc20 when value(i.e amount*decimals)  is high but less than type(uint112).max**
   - Contest: 62, Bug: H-09
   - Reference: https://code4rena.com/reports/2021-11-streaming#h-09-dos-while-dealing-with-erc20-when-valueie-amountdecimals--is-high-but-less-than-typeuint112max

15. **UniswapV2PriceOracle.sol currentCumulativePrices() will revert when priceCumulative addition overflow**
   - Contest: 90, Bug: H-02
   - Reference: https://code4rena.com/reports/2022-04-phuture#h-02-uniswapv2priceoraclesol-currentcumulativeprices-will-revert-when-pricecumulative-addition-overflow

16. **LiquidityProviders.sol The share price of the LP can be manipulated and making future liquidityProviders unable to removeLiquidity()**
   - Contest: 97, Bug: H-02
   - Reference: https://code4rena.com/reports/2022-03-biconomy#h-02-liquidityproviderssol-the-share-price-of-the-lp-can-be-manipulated-and-making-future-liquidityproviders-unable-to-removeliquidity

17. **Certain fee configuration enables vaults to be drained**
   - Contest: 192, Bug: H-03
   - Reference: https://code4rena.com/reports/2022-12-tigris#h-03-certain-fee-configuration-enables-vaults-to-be-drained

---

### S6-1: Incorrect Calculating Order (8 bugs)

> Semantic - wrong order of operations

1. **Reward computation is wrong**
   - Contest: 18, Bug: H-01
   - Reference: https://code4rena.com/reports/2021-07-wildcredit#h-01-reward-computation-is-wrong

2. **ConcentratedLiquidityPool: secondsPerLiquidity should be modified whenever pool liquidity changes**
   - Contest: 35, Bug: H-12
   - Reference: https://code4rena.com/reports/2021-09-sushitrident-2#h-12-concentratedliquiditypool-secondsperliquidity-should-be-modified-whenever-pool-liquidity-changes

3. **unstake should update exchange rates first**
   - Contest: 43, Bug: H-02
   - Reference: https://code4rena.com/reports/2021-10-covalent#h-02-unstake-should-update-exchange-rates-first

4. **borrow must accrueInterest first**
   - Contest: 45, Bug: H-01
   - Reference: https://code4rena.com/reports/2021-10-union#h-01-borrow-must-accrueinterest-first

5. **Wrong implementation of CreditLimitByMedian.sol#getLockedAmount() makes it unable to unlock lockedAmount in CreditLimitByMedian model**
   - Contest: 45, Bug: H-02
   - Reference: https://code4rena.com/reports/2021-10-union#h-02-wrong-implementation-of-creditlimitbymediansolgetlockedamount-makes-it-unable-to-unlock-lockedamount-in-creditlimitbymedian-model

6. **Masterchef: Improper handling of deposit fee**
   - Contest: 83, Bug: H-02
   - Reference: https://code4rena.com/reports/2022-02-concur#h-02-masterchef-improper-handling-of-deposit-fee

7. **Oracle price does not compound**
   - Contest: 102, Bug: H-01
   - Reference: https://code4rena.com/reports/2022-03-volt#h-01-oracle-price-does-not-compound

8. **User can steal all rewards due to checkpoint after transfer**
   - Contest: 112, Bug: H-01
   - Reference: https://code4rena.com/reports/2022-04-backd#h-01-user-can-steal-all-rewards-due-to-checkpoint-after-transfer

---

### S6-2: Unexpected Return Value (4 bugs)

> Semantic - return value deviates from expected

1. **Inconsistent usage of applyInterest**
   - Contest: 3, Bug: H-04
   - Reference: https://code4rena.com/reports/2021-04-marginswap#h-04-inconsistent-usage-of-applyinterest

2. **Wrong returns of SavingsAccountUtil.depositFromSavingsAccount() can cause fund loss**
   - Contest: 61, Bug: H-02
   - Reference: https://code4rena.com/reports/2021-12-sublime#h-02-wrong-returns-of-savingsaccountutildepositfromsavingsaccount-can-cause-fund-loss

3. **LenderPool: Principal withdrawable is incorrectly calculated if start() is invoked with non-zero start fee**
   - Contest: 101, Bug: H-01
   - Reference: https://code4rena.com/reports/2022-03-sublime#h-01-lenderpool-principal-withdrawable-is-incorrectly-calculated-if-start-is-invoked-with-non-zero-start-fee

4. **StakedCitadel doesn’t use correct balance for internal accounting**
   - Contest: 110, Bug: H-01
   - Reference: https://code4rena.com/reports/2022-04-badger-citadel#h-01-stakedcitadel-doesnt-use-correct-balance-for-internal-accounting

---

### S6-3: Wrong Numbers in Calculation (18 bugs)

> Semantic - e.g., x = a + b => x = a + c

1. **Wrong slippage protection on Token -> Token trades**
   - Contest: 5, Bug: H-15
   - Reference: https://code4rena.com/reports/2021-04-vader#h-15-wrong-slippage-protection-on-token---token-trades

2. **User could lose underlying tokens when redeeming from the IdleYieldSource**
   - Contest: 14, Bug: H-01
   - Reference: https://code4rena.com/reports/2021-06-pooltogether#h-01-user-could-lose-underlying-tokens-when-redeeming-from-the-idleyieldsource

3. **BadgerYieldSource balanceOfToken share calculation seems wrong**
   - Contest: 14, Bug: H-03
   - Reference: https://code4rena.com/reports/2021-06-pooltogether#h-03-badgeryieldsource-balanceoftoken-share-calculation-seems-wrong

4. **Use of incorrect index leads to incorrect updation of funding rates**
   - Contest: 16, Bug: H-02
   - Reference: https://code4rena.com/reports/2021-06-tracer#h-02-use-of-incorrect-index-leads-to-incorrect-updation-of-funding-rates

5. **ConstantProductPool.burnSingle swap amount computations should use balance**
   - Contest: 29, Bug: H-11
   - Reference: https://code4rena.com/reports/2021-09-sushitrident#h-11-constantproductpoolburnsingle-swap-amount-computations-should-use-balance

6. **Controller.setCap sets wrong vault balance**
   - Contest: 30, Bug: H-01
   - Reference: https://code4rena.com/reports/2021-09-yaxis#h-01-controllersetcap-sets-wrong-vault-balance

7. **Use of tokenB’s price instead of tokenA in determining account health will lead to protocol mis-accounting and insolvency**
   - Contest: 32, Bug: H-01
   - Reference: https://code4rena.com/reports/2021-09-wildcredit#h-01-use-of-tokenbs-price-instead-of-tokena-in-determining-account-health-will-lead-to-protocol-mis-accounting-and-insolvency

8. **ConcentratedLiquidityPool.burn() Wrong implementation**
   - Contest: 35, Bug: H-10
   - Reference: https://code4rena.com/reports/2021-09-sushitrident-2#h-10-concentratedliquiditypoolburn-wrong-implementation

9. **Vault fails to track debt correctly that leads to bad debt**
   - Contest: 42, Bug: H-01
   - Reference: https://code4rena.com/reports/2021-10-mochi#h-01-vault-fails-to-track-debt-correctly-that-leads-to-bad-debt

10. **Approved spender can spend too many tokens**
   - Contest: 47, Bug: H-02
   - Reference: https://code4rena.com/reports/2021-10-badgerdao#h-02-approved-spender-can-spend-too-many-tokens

11. **OverlayV1UniswapV3Market computes wrong market liquidity**
   - Contest: 49, Bug: H-01
   - Reference: https://code4rena.com/reports/2021-11-overlay#h-01-overlayv1uniswapv3market-computes-wrong-market-liquidity

12. **Ideal balance is not calculated correctly when providing imbalanced liquidity**
   - Contest: 51, Bug: H-06
   - Reference: https://code4rena.com/reports/2021-11-bootfinance#h-06-ideal-balance-is-not-calculated-correctly-when-providing-imbalanced-liquidity

13. **VaderRouter.calculateOutGivenIn calculates wrong swap**
   - Contest: 52, Bug: H-16
   - Reference: https://code4rena.com/reports/2021-11-vader#h-16-vaderroutercalculateoutgivenin-calculates-wrong-swap

14. **recoverTokens doesn’t work when isSale is true**
   - Contest: 62, Bug: H-10
   - Reference: https://code4rena.com/reports/2021-11-streaming#h-10-recovertokens-doesnt-work-when-issale-is-true

15. **Yeti token rebase checks the additional token amount incorrectly**
   - Contest: 66, Bug: H-02
   - Reference: https://code4rena.com/reports/2021-12-yetifinance#h-02-yeti-token-rebase-checks-the-additional-token-amount-incorrectly

16. **wrong minting amount**
   - Contest: 78, Bug: H-02
   - Reference: https://code4rena.com/reports/2022-01-behodler#h-02-wrong-minting-amount

17. **ERC4626 mint uses wrong amount**
   - Contest: 92, Bug: H-01
   - Reference: https://code4rena.com/reports/2022-02-tribe-turbo#h-01-erc4626-mint-uses-wrong-amount

18. **PooledCreditLine: termination likely fails because _principleWithdrawable is treated as shares**
   - Contest: 101, Bug: H-02
   - Reference: https://code4rena.com/reports/2022-03-sublime#h-02-pooledcreditline-termination-likely-fails-because-_principlewithdrawable-is-treated-as-shares

---

### S6-4: Other Accounting Errors (56 bugs)

> Semantic - e.g., x = a + b => x = a - b

1. **Wrong liquidation logic**
   - Contest: 3, Bug: H-05
   - Reference: https://code4rena.com/reports/2021-04-marginswap#h-05-wrong-liquidation-logic

2. **Wrong calcAsymmetricShare calculation**
   - Contest: 5, Bug: H-07
   - Reference: https://code4rena.com/reports/2021-04-vader#h-07-wrong-calcasymmetricshare-calculation

3. **Wrong liquidity units calculation**
   - Contest: 5, Bug: H-08
   - Reference: https://code4rena.com/reports/2021-04-vader#h-08-wrong-liquidity-units-calculation

4. **getAddedAmount can return wrong results**
   - Contest: 5, Bug: H-12
   - Reference: https://code4rena.com/reports/2021-04-vader#h-12-getaddedamount-can-return-wrong-results

5. **getRandomTokenIdFromFund yields wrong probabilities for ERC1155**
   - Contest: 8, Bug: H-03
   - Reference: https://code4rena.com/reports/2021-05-nftx#h-03-getrandomtokenidfromfund-yields-wrong-probabilities-for-erc1155

6. **YieldMath.sol / Log2: >= or > ?**
   - Contest: 12, Bug: H-03
   - Reference: https://code4rena.com/reports/2021-05-yield#h-03-yieldmathsol--log2--or--

7. **Logic error in fee subtraction**
   - Contest: 16, Bug: H-04
   - Reference: https://code4rena.com/reports/2021-06-tracer#h-04-logic-error-in-fee-subtraction

8. **Wrong price scale for GasOracle**
   - Contest: 16, Bug: H-06
   - Reference: https://code4rena.com/reports/2021-06-tracer#h-06-wrong-price-scale-for-gasoracle

9. **Buoy3Pool.safetyCheck is not precise and has some assumptions**
   - Contest: 17, Bug: H-02
   - Reference: https://code4rena.com/reports/2021-06-gro#h-02-buoy3poolsafetycheck-is-not-precise-and-has-some-assumptions

10. **CompositeMultiOracle returns wrong decimals for prices?**
   - Contest: 25, Bug: H-01
   - Reference: https://code4rena.com/reports/2021-08-yield#h-01-compositemultioracle-returns-wrong-decimals-for-prices

11. **ERC20Rewards breaks when setting a different token**
   - Contest: 25, Bug: H-03
   - Reference: https://code4rena.com/reports/2021-08-yield#h-03-erc20rewards-breaks-when-setting-a-different-token

12. **Exchange rates from Compound are assumed with 18 decimals**
   - Contest: 25, Bug: H-05
   - Reference: https://code4rena.com/reports/2021-08-yield#h-05-exchange-rates-from-compound-are-assumed-with-18-decimals

13. **hybrid pool uses wrong non_optimal_mint_fee**
   - Contest: 29, Bug: H-05
   - Reference: https://code4rena.com/reports/2021-09-sushitrident#h-05-hybrid-pool-uses-wrong-non_optimal_mint_fee

14. **HybridPool’s reserve is converted to “amount” twice**
   - Contest: 29, Bug: H-08
   - Reference: https://code4rena.com/reports/2021-09-sushitrident#h-08-hybridpools-reserve-is-converted-to-amount-twice

15. **Incorrect usage of _pow in _computeSingleOutGivenPoolIn of IndexPool**
   - Contest: 29, Bug: H-14
   - Reference: https://code4rena.com/reports/2021-09-sushitrident#h-14-incorrect-usage-of-_pow-in-_computesingleoutgivenpoolin-of-indexpool

16. **Incorrect multiplication in _computeSingleOutGivenPoolIn of IndexPool**
   - Contest: 29, Bug: H-15
   - Reference: https://code4rena.com/reports/2021-09-sushitrident#h-15-incorrect-multiplication-in-_computesingleoutgivenpoolin-of-indexpool

17. **Vault.balance() mixes normalized and standard amounts**
   - Contest: 30, Bug: H-07
   - Reference: https://code4rena.com/reports/2021-09-yaxis#h-07-vaultbalance-mixes-normalized-and-standard-amounts

18. **Vault.withdraw mixes normalized and standard amounts**
   - Contest: 30, Bug: H-08
   - Reference: https://code4rena.com/reports/2021-09-yaxis#h-08-vaultwithdraw-mixes-normalized-and-standard-amounts

19. **veCVXStrategy.manualRebalance has wrong logic**
   - Contest: 31, Bug: H-01
   - Reference: https://code4rena.com/reports/2021-09-bvecvx#h-01-vecvxstrategymanualrebalance-has-wrong-logic

20. **The formula of number of prizes for a degree is wrong**
   - Contest: 34, Bug: H-01
   - Reference: https://code4rena.com/reports/2021-10-pooltogether#h-01-the-formula-of-number-of-prizes-for-a-degree-is-wrong

21. **Wrong inequality when adding/removing liquidity in current price range**
   - Contest: 35, Bug: H-08
   - Reference: https://code4rena.com/reports/2021-09-sushitrident-2#h-08-wrong-inequality-when-addingremoving-liquidity-in-current-price-range

22. **ConcentratedLiquidityPool: incorrect feeGrowthGlobal accounting when crossing ticks**
   - Contest: 35, Bug: H-11
   - Reference: https://code4rena.com/reports/2021-09-sushitrident-2#h-11-concentratedliquiditypool-incorrect-feegrowthglobal-accounting-when-crossing-ticks

23. **Swivel: Taker is charged fees twice in exitVaultFillingVaultInitiate**
   - Contest: 39, Bug: H-02
   - Reference: https://code4rena.com/reports/2021-09-swivel#h-02-swivel-taker-is-charged-fees-twice-in-exitvaultfillingvaultinitiate

24. **debts calculation is not accurate**
   - Contest: 42, Bug: H-05
   - Reference: https://code4rena.com/reports/2021-10-mochi#h-05-debts-calculation-is-not-accurate

25. **Wrong calculation of erc20Delta and ethDelta**
   - Contest: 44, Bug: H-02
   - Reference: https://code4rena.com/reports/2021-10-tally#h-02-wrong-calculation-of-erc20delta-and-ethdelta

26. **Can not update target price**
   - Contest: 51, Bug: H-02
   - Reference: https://code4rena.com/reports/2021-11-bootfinance#h-02-can-not-update-target-price

27. **Swaps are not split when trade crosses target price**
   - Contest: 51, Bug: H-04
   - Reference: https://code4rena.com/reports/2021-11-bootfinance#h-04-swaps-are-not-split-when-trade-crosses-target-price

28. **TwapOracle doesn’t calculate VADER:USDV exchange rate correctly**
   - Contest: 52, Bug: H-04
   - Reference: https://code4rena.com/reports/2021-11-vader#h-04-twaporacle-doesnt-calculate-vaderusdv-exchange-rate-correctly

29. **VaderPoolV2 incorrectly calculates the amount of IL protection to send to LPs**
   - Contest: 52, Bug: H-09
   - Reference: https://code4rena.com/reports/2021-11-vader#h-09-vaderpoolv2-incorrectly-calculates-the-amount-of-il-protection-to-send-to-lps

30. **VaderRouter._swap performs wrong swap**
   - Contest: 52, Bug: H-15
   - Reference: https://code4rena.com/reports/2021-11-vader#h-15-vaderrouter_swap-performs-wrong-swap

31. **Synth tokens can get over-minted**
   - Contest: 52, Bug: H-23
   - Reference: https://code4rena.com/reports/2021-11-vader#h-23-synth-tokens-can-get-over-minted

32. **Wrong design of swap() results in unexpected and unfavorable outputs**
   - Contest: 52, Bug: H-25
   - Reference: https://code4rena.com/reports/2021-11-vader#h-25-wrong-design-of-swap-results-in-unexpected-and-unfavorable-outputs

33. **Incorrect Price Consultation Results**
   - Contest: 52, Bug: H-28
   - Reference: https://code4rena.com/reports/2021-11-vader#h-28-incorrect-price-consultation-results

34. **Incorrect Accrual Of sumNative and sumUSD In Producing Consultation Results**
   - Contest: 52, Bug: H-34
   - Reference: https://code4rena.com/reports/2021-11-vader#h-34-incorrect-accrual-of-sumnative-and-sumusd-in-producing-consultation-results-

35. **CDP.sol update overwrites user’s credit on every positive increment**
   - Contest: 56, Bug: H-02
   - Reference: https://code4rena.com/reports/2021-11-yaxis#h-02-cdpsol-update-overwrites-users-credit-on-every-positive-increment

36. **Wrong implementation of performanceFee can cause users to lose 50% to 100% of their funds**
   - Contest: 58, Bug: H-02
   - Reference: https://code4rena.com/reports/2021-12-mellow#h-02-wrong-implementation-of-performancefee-can-cause-users-to-lose-50-to-100-of-their-funds

37. **AuctionBurnReserveSkew.getPegDeltaFrequency() Wrong implementation can result in an improper amount of excess Liquidity Extension balance to be used at the end of an auction**
   - Contest: 59, Bug: H-04
   - Reference: https://code4rena.com/reports/2021-11-malt#h-04-auctionburnreserveskewgetpegdeltafrequency-wrong-implementation-can-result-in-an-improper-amount-of-excess-liquidity-extension-balance-to-be-used-at-the-end-of-an-auction-

38. **AuctionEschapeHatch.sol#exitEarly updates state of the auction wrongly**
   - Contest: 59, Bug: H-05
   - Reference: https://code4rena.com/reports/2021-11-malt#h-05-auctioneschapehatchsolexitearly-updates-state-of-the-auction-wrongly

39. **Wrong shortfall calculation**
   - Contest: 60, Bug: H-01
   - Reference: https://code4rena.com/reports/2021-12-perennial#h-01-wrong-shortfall-calculation

40. **In CreditLine#_borrowTokensToLiquidate**
   - Contest: 61, Bug: H-01
   - Reference: oracle is used wrong way"
   - Comment: https://code4rena.com/reports/2021-12-sublime#h-01-in-creditline_borrowtokenstoliquidate-oracle-is-used-wrong-way

41. **Yearn token <> shares conversion decimal issue**
   - Contest: 61, Bug: H-04
   - Reference: https://code4rena.com/reports/2021-12-sublime#h-04-yearn-token--shares-conversion-decimal-issue

42. **Wrong calculation of excess depositToken allows stream creator to retrieve depositTokenFlashloanFeeAmount**
   - Contest: 62, Bug: H-01
   - Reference: which may cause fund loss to users"
   - Comment: https://code4rena.com/reports/2021-11-streaming#h-01-wrong-calculation-of-excess-deposittoken-allows-stream-creator-to-retrieve-deposittokenflashloanfeeamount-which-may-cause-fund-loss-to-users

43. **Reward token not correctly recovered**
   - Contest: 62, Bug: H-03
   - Reference: https://code4rena.com/reports/2021-11-streaming#h-03-reward-token-not-correctly-recovered

44. **Oracle doesn’t calculate USDV/VADER price correctly**
   - Contest: 70, Bug: H-03
   - Reference: https://code4rena.com/reports/2021-12-vader#h-03-oracle-doesnt-calculate-usdvvader-price-correctly

45. **Vader TWAP averages wrong**
   - Contest: 70, Bug: H-04
   - Reference: https://code4rena.com/reports/2021-12-vader#h-04-vader-twap-averages-wrong

46. **Oracle returns an improperly scaled USDV/VADER price**
   - Contest: 70, Bug: H-05
   - Reference: https://code4rena.com/reports/2021-12-vader#h-05-oracle-returns-an-improperly-scaled-usdvvader-price

47. **Reserve does not properly apply prices of VADER and USDV tokens**
   - Contest: 70, Bug: H-08
   - Reference: https://code4rena.com/reports/2021-12-vader#h-08-reserve-does-not-properly-apply-prices-of-vader-and-usdv-tokens

48. **USDV.sol Mint and Burn Amounts Are Incorrect**
   - Contest: 70, Bug: H-09
   - Reference: https://code4rena.com/reports/2021-12-vader#h-09-usdvsol-mint-and-burn-amounts-are-incorrect

49. **PoolTemplate.sol#resume() Wrong implementation of resume() will compensate overmuch redeem amount from index pools**
   - Contest: 71, Bug: H-11
   - Reference: https://code4rena.com/reports/2022-01-insure#h-11-pooltemplatesolresume-wrong-implementation-of-resume-will-compensate-overmuch-redeem-amount-from-index-pools

50. **In the case of Single Asset Entry**
   - Contest: 77, Bug: H-01
   - Reference: new liquidity providers will suffer fund loss due to wrong formula of ΔRo"
   - Comment: https://code4rena.com/reports/2022-01-elasticswap#h-01-in-the-case-of-single-asset-entry-new-liquidity-providers-will-suffer-fund-loss-due-to-wrong-formula-of-%CE%B4ro

51. **Wrong token allocation computation for token decimals != 18 if floor price not reached**
   - Contest: 79, Bug: H-02
   - Reference: https://code4rena.com/reports/2022-01-trader-joe#h-02-wrong-token-allocation-computation-for-token-decimals--18-if-floor-price-not-reached

52. **Wrong formula when add fee incentivePool can lead to loss of funds.**
   - Contest: 97, Bug: H-03
   - Reference: https://code4rena.com/reports/2022-03-biconomy#h-03-wrong-formula-when-add-fee-incentivepool-can-lead-to-loss-of-funds

53. **Mistake while checking LTV to lender accepted LTV**
   - Contest: 113, Bug: H-05
   - Reference: https://code4rena.com/reports/2022-04-abranft#h-05-mistake-while-checking-ltv-to-lender-accepted-ltv

54. **Incorrect calculation of new price while adding position**
   - Contest: 192, Bug: H-06
   - Reference: https://code4rena.com/reports/2022-12-tigris#h-06-incorrect-calculation-of-new-price-while-adding-position

55. **Users can bypass the maxWinPercent limit using a partially closing**
   - Contest: 192, Bug: H-09
   - Reference: https://code4rena.com/reports/2022-12-tigris#h-09-users-can-bypass-the-maxwinpercent-limit-using-a-partially-closing

56. **Not enough margin pulled or burned from user when adding to a position**
   - Contest: 192, Bug: H-11
   - Reference: https://code4rena.com/reports/2022-12-tigris#h-11-not-enough-margin-pulled-or-burned-from-user-when-adding-to-a-position

---

