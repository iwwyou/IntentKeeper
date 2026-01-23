# RQ1 Dataset: Single-Transaction Numeric Logic Errors

> **Total: 127 bugs** (Web3Bugs S6-*: 86 + Numscout: 41)

---

## 1. Web3Bugs S6-* (86 bugs)

Source: https://github.com/ZhangZhuoSJTU/Web3Bugs

### S6-1: Incorrect Calculating Order (8 bugs)

| # | Contest | Bug | Description | Reference |
|---|---------|-----|-------------|-----------|
| 1 | 18 | H-01 | Reward computation is wrong | [link](https://code4rena.com/reports/2021-07-wildcredit#h-01-reward-computation-is-wrong) |
| 2 | 35 | H-12 | secondsPerLiquidity should be modified whenever pool liquidity changes | [link](https://code4rena.com/reports/2021-09-sushitrident-2#h-12-concentratedliquiditypool-secondsperliquidity-should-be-modified-whenever-pool-liquidity-changes) |
| 3 | 43 | H-02 | unstake should update exchange rates first | [link](https://code4rena.com/reports/2021-10-covalent#h-02-unstake-should-update-exchange-rates-first) |
| 4 | 45 | H-01 | borrow must accrueInterest first | [link](https://code4rena.com/reports/2021-10-union#h-01-borrow-must-accrueinterest-first) |
| 5 | 45 | H-02 | Wrong implementation of getLockedAmount() | [link](https://code4rena.com/reports/2021-10-union#h-02-wrong-implementation-of-creditlimitbymediansolgetlockedamount-makes-it-unable-to-unlock-lockedamount-in-creditlimitbymedian-model) |
| 6 | 83 | H-02 | Masterchef: Improper handling of deposit fee | [link](https://code4rena.com/reports/2022-02-concur#h-02-masterchef-improper-handling-of-deposit-fee) |
| 7 | 102 | H-01 | Oracle price does not compound | [link](https://code4rena.com/reports/2022-03-volt#h-01-oracle-price-does-not-compound) |
| 8 | 112 | H-01 | User can steal all rewards due to checkpoint after transfer | [link](https://code4rena.com/reports/2022-04-backd#h-01-user-can-steal-all-rewards-due-to-checkpoint-after-transfer) |

### S6-2: Unexpected Return Value (4 bugs)

| # | Contest | Bug | Description | Reference |
|---|---------|-----|-------------|-----------|
| 1 | 3 | H-04 | Inconsistent usage of applyInterest | [link](https://code4rena.com/reports/2021-04-marginswap#h-04-inconsistent-usage-of-applyinterest) |
| 2 | 61 | H-02 | Wrong returns of depositFromSavingsAccount() can cause fund loss | [link](https://code4rena.com/reports/2021-12-sublime#h-02-wrong-returns-of-savingsaccountutildepositfromsavingsaccount-can-cause-fund-loss) |
| 3 | 101 | H-01 | Principal withdrawable incorrectly calculated with non-zero start fee | [link](https://code4rena.com/reports/2022-03-sublime#h-01-lenderpool-principal-withdrawable-is-incorrectly-calculated-if-start-is-invoked-with-non-zero-start-fee) |
| 4 | 110 | H-01 | StakedCitadel doesn't use correct balance for internal accounting | [link](https://code4rena.com/reports/2022-04-badger-citadel#h-01-stakedcitadel-doesnt-use-correct-balance-for-internal-accounting) |

### S6-3: Wrong Numbers in Calculation (18 bugs)

| # | Contest | Bug | Description | Reference |
|---|---------|-----|-------------|-----------|
| 1 | 5 | H-15 | Wrong slippage protection on Token -> Token trades | [link](https://code4rena.com/reports/2021-04-vader#h-15-wrong-slippage-protection-on-token---token-trades) |
| 2 | 14 | H-01 | User could lose underlying tokens when redeeming | [link](https://code4rena.com/reports/2021-06-pooltogether#h-01-user-could-lose-underlying-tokens-when-redeeming-from-the-idleyieldsource) |
| 3 | 14 | H-03 | BadgerYieldSource balanceOfToken share calculation wrong | [link](https://code4rena.com/reports/2021-06-pooltogether#h-03-badgeryieldsource-balanceoftoken-share-calculation-seems-wrong) |
| 4 | 16 | H-02 | Use of incorrect index leads to incorrect funding rates | [link](https://code4rena.com/reports/2021-06-tracer#h-02-use-of-incorrect-index-leads-to-incorrect-updation-of-funding-rates) |
| 5 | 29 | H-11 | burnSingle swap amount should use balance | [link](https://code4rena.com/reports/2021-09-sushitrident#h-11-constantproductpoolburnsingle-swap-amount-computations-should-use-balance) |
| 6 | 30 | H-01 | Controller.setCap sets wrong vault balance | [link](https://code4rena.com/reports/2021-09-yaxis#h-01-controllersetcap-sets-wrong-vault-balance) |
| 7 | 32 | H-01 | Use of tokenB's price instead of tokenA | [link](https://code4rena.com/reports/2021-09-wildcredit#h-01-use-of-tokenbs-price-instead-of-tokena-in-determining-account-health-will-lead-to-protocol-mis-accounting-and-insolvency) |
| 8 | 35 | H-10 | ConcentratedLiquidityPool.burn() Wrong implementation | [link](https://code4rena.com/reports/2021-09-sushitrident-2#h-10-concentratedliquiditypoolburn-wrong-implementation) |
| 9 | 42 | H-01 | Vault fails to track debt correctly | [link](https://code4rena.com/reports/2021-10-mochi#h-01-vault-fails-to-track-debt-correctly-that-leads-to-bad-debt) |
| 10 | 47 | H-02 | Approved spender can spend too many tokens | [link](https://code4rena.com/reports/2021-10-badgerdao#h-02-approved-spender-can-spend-too-many-tokens) |
| 11 | 49 | H-01 | Computes wrong market liquidity | [link](https://code4rena.com/reports/2021-11-overlay#h-01-overlayv1uniswapv3market-computes-wrong-market-liquidity) |
| 12 | 51 | H-06 | Ideal balance not calculated correctly | [link](https://code4rena.com/reports/2021-11-bootfinance#h-06-ideal-balance-is-not-calculated-correctly-when-providing-imbalanced-liquidity) |
| 13 | 52 | H-16 | VaderRouter.calculateOutGivenIn calculates wrong swap | [link](https://code4rena.com/reports/2021-11-vader#h-16-vaderroutercalculateoutgivenin-calculates-wrong-swap) |
| 14 | 62 | H-10 | recoverTokens doesn't work when isSale is true | [link](https://code4rena.com/reports/2021-11-streaming#h-10-recovertokens-doesnt-work-when-issale-is-true) |
| 15 | 66 | H-02 | Yeti token rebase checks amount incorrectly | [link](https://code4rena.com/reports/2021-12-yetifinance#h-02-yeti-token-rebase-checks-the-additional-token-amount-incorrectly) |
| 16 | 78 | H-02 | Wrong minting amount | [link](https://code4rena.com/reports/2022-01-behodler#h-02-wrong-minting-amount) |
| 17 | 92 | H-01 | ERC4626 mint uses wrong amount | [link](https://code4rena.com/reports/2022-02-tribe-turbo#h-01-erc4626-mint-uses-wrong-amount) |
| 18 | 101 | H-02 | _principleWithdrawable is treated as shares | [link](https://code4rena.com/reports/2022-03-sublime#h-02-pooledcreditline-termination-likely-fails-because-_principlewithdrawable-is-treated-as-shares) |

### S6-4: Other Accounting Errors (56 bugs)

| # | Contest | Bug | Description | Reference |
|---|---------|-----|-------------|-----------|
| 1 | 3 | H-05 | Wrong liquidation logic | [link](https://code4rena.com/reports/2021-04-marginswap#h-05-wrong-liquidation-logic) |
| 2 | 5 | H-07 | Wrong calcAsymmetricShare calculation | [link](https://code4rena.com/reports/2021-04-vader#h-07-wrong-calcasymmetricshare-calculation) |
| 3 | 5 | H-08 | Wrong liquidity units calculation | [link](https://code4rena.com/reports/2021-04-vader#h-08-wrong-liquidity-units-calculation) |
| 4 | 5 | H-12 | getAddedAmount can return wrong results | [link](https://code4rena.com/reports/2021-04-vader#h-12-getaddedamount-can-return-wrong-results) |
| 5 | 8 | H-03 | getRandomTokenIdFromFund yields wrong probabilities | [link](https://code4rena.com/reports/2021-05-nftx#h-03-getrandomtokenidfromfund-yields-wrong-probabilities-for-erc1155) |
| 6 | 12 | H-03 | YieldMath.sol Log2: >= or > ? | [link](https://code4rena.com/reports/2021-05-yield#h-03-yieldmathsol--log2--or--) |
| 7 | 16 | H-04 | Logic error in fee subtraction | [link](https://code4rena.com/reports/2021-06-tracer#h-04-logic-error-in-fee-subtraction) |
| 8 | 16 | H-06 | Wrong price scale for GasOracle | [link](https://code4rena.com/reports/2021-06-tracer#h-06-wrong-price-scale-for-gasoracle) |
| 9 | 17 | H-02 | Buoy3Pool.safetyCheck is not precise | [link](https://code4rena.com/reports/2021-06-gro#h-02-buoy3poolsafetycheck-is-not-precise-and-has-some-assumptions) |
| 10 | 25 | H-01 | CompositeMultiOracle returns wrong decimals | [link](https://code4rena.com/reports/2021-08-yield#h-01-compositemultioracle-returns-wrong-decimals-for-prices) |
| 11 | 25 | H-03 | ERC20Rewards breaks when setting different token | [link](https://code4rena.com/reports/2021-08-yield#h-03-erc20rewards-breaks-when-setting-a-different-token) |
| 12 | 25 | H-05 | Exchange rates from Compound assumed 18 decimals | [link](https://code4rena.com/reports/2021-08-yield#h-05-exchange-rates-from-compound-are-assumed-with-18-decimals) |
| 13 | 29 | H-05 | hybrid pool uses wrong non_optimal_mint_fee | [link](https://code4rena.com/reports/2021-09-sushitrident#h-05-hybrid-pool-uses-wrong-non_optimal_mint_fee) |
| 14 | 29 | H-08 | HybridPool's reserve converted to amount twice | [link](https://code4rena.com/reports/2021-09-sushitrident#h-08-hybridpools-reserve-is-converted-to-amount-twice) |
| 15 | 29 | H-14 | Incorrect usage of _pow in IndexPool | [link](https://code4rena.com/reports/2021-09-sushitrident#h-14-incorrect-usage-of-_pow-in-_computesingleoutgivenpoolin-of-indexpool) |
| 16 | 29 | H-15 | Incorrect multiplication in IndexPool | [link](https://code4rena.com/reports/2021-09-sushitrident#h-15-incorrect-multiplication-in-_computesingleoutgivenpoolin-of-indexpool) |
| 17 | 30 | H-07 | Vault.balance() mixes normalized and standard amounts | [link](https://code4rena.com/reports/2021-09-yaxis#h-07-vaultbalance-mixes-normalized-and-standard-amounts) |
| 18 | 30 | H-08 | Vault.withdraw mixes normalized and standard amounts | [link](https://code4rena.com/reports/2021-09-yaxis#h-08-vaultwithdraw-mixes-normalized-and-standard-amounts) |
| 19 | 31 | H-01 | veCVXStrategy.manualRebalance has wrong logic | [link](https://code4rena.com/reports/2021-09-bvecvx#h-01-vecvxstrategymanualrebalance-has-wrong-logic) |
| 20 | 34 | H-01 | Wrong formula for number of prizes | [link](https://code4rena.com/reports/2021-10-pooltogether#h-01-the-formula-of-number-of-prizes-for-a-degree-is-wrong) |
| 21 | 35 | H-08 | Wrong inequality when adding/removing liquidity | [link](https://code4rena.com/reports/2021-09-sushitrident-2#h-08-wrong-inequality-when-addingremoving-liquidity-in-current-price-range) |
| 22 | 35 | H-11 | Incorrect feeGrowthGlobal accounting when crossing ticks | [link](https://code4rena.com/reports/2021-09-sushitrident-2#h-11-concentratedliquiditypool-incorrect-feegrowthglobal-accounting-when-crossing-ticks) |
| 23 | 39 | H-02 | Taker is charged fees twice | [link](https://code4rena.com/reports/2021-09-swivel#h-02-swivel-taker-is-charged-fees-twice-in-exitvaultfillingvaultinitiate) |
| 24 | 42 | H-05 | debts calculation is not accurate | [link](https://code4rena.com/reports/2021-10-mochi#h-05-debts-calculation-is-not-accurate) |
| 25 | 44 | H-02 | Wrong calculation of erc20Delta and ethDelta | [link](https://code4rena.com/reports/2021-10-tally#h-02-wrong-calculation-of-erc20delta-and-ethdelta) |
| 26 | 51 | H-02 | Can not update target price | [link](https://code4rena.com/reports/2021-11-bootfinance#h-02-can-not-update-target-price) |
| 27 | 51 | H-04 | Swaps are not split when trade crosses target price | [link](https://code4rena.com/reports/2021-11-bootfinance#h-04-swaps-are-not-split-when-trade-crosses-target-price) |
| 28 | 52 | H-04 | TwapOracle doesn't calculate VADER:USDV correctly | [link](https://code4rena.com/reports/2021-11-vader#h-04-twaporacle-doesnt-calculate-vaderusdv-exchange-rate-correctly) |
| 29 | 52 | H-09 | VaderPoolV2 incorrectly calculates IL protection | [link](https://code4rena.com/reports/2021-11-vader#h-09-vaderpoolv2-incorrectly-calculates-the-amount-of-il-protection-to-send-to-lps) |
| 30 | 52 | H-15 | VaderRouter._swap performs wrong swap | [link](https://code4rena.com/reports/2021-11-vader#h-15-vaderrouter_swap-performs-wrong-swap) |
| 31 | 52 | H-23 | Synth tokens can get over-minted | [link](https://code4rena.com/reports/2021-11-vader#h-23-synth-tokens-can-get-over-minted) |
| 32 | 52 | H-25 | Wrong design of swap() results in unfavorable outputs | [link](https://code4rena.com/reports/2021-11-vader#h-25-wrong-design-of-swap-results-in-unexpected-and-unfavorable-outputs) |
| 33 | 52 | H-28 | Incorrect Price Consultation Results | [link](https://code4rena.com/reports/2021-11-vader#h-28-incorrect-price-consultation-results) |
| 34 | 52 | H-34 | Incorrect Accrual Of sumNative and sumUSD | [link](https://code4rena.com/reports/2021-11-vader#h-34-incorrect-accrual-of-sumnative-and-sumusd-in-producing-consultation-results-) |
| 35 | 56 | H-02 | CDP.sol update overwrites user's credit | [link](https://code4rena.com/reports/2021-11-yaxis#h-02-cdpsol-update-overwrites-users-credit-on-every-positive-increment) |
| 36 | 58 | H-02 | Wrong implementation of performanceFee | [link](https://code4rena.com/reports/2021-12-mellow#h-02-wrong-implementation-of-performancefee-can-cause-users-to-lose-50-to-100-of-their-funds) |
| 37 | 59 | H-04 | getPegDeltaFrequency() Wrong implementation | [link](https://code4rena.com/reports/2021-11-malt#h-04-auctionburnreserveskewgetpegdeltafrequency-wrong-implementation-can-result-in-an-improper-amount-of-excess-liquidity-extension-balance-to-be-used-at-the-end-of-an-auction-) |
| 38 | 59 | H-05 | exitEarly updates state of auction wrongly | [link](https://code4rena.com/reports/2021-11-malt#h-05-auctioneschapehatchsolexitearly-updates-state-of-the-auction-wrongly) |
| 39 | 60 | H-01 | Wrong shortfall calculation | [link](https://code4rena.com/reports/2021-12-perennial#h-01-wrong-shortfall-calculation) |
| 40 | 61 | H-01 | oracle is used wrong way | [link](https://code4rena.com/reports/2021-12-sublime#h-01-in-creditline_borrowtokenstoliquidate-oracle-is-used-wrong-way) |
| 41 | 61 | H-04 | Yearn token shares conversion decimal issue | [link](https://code4rena.com/reports/2021-12-sublime#h-04-yearn-token--shares-conversion-decimal-issue) |
| 42 | 62 | H-01 | Wrong calculation of excess depositToken | [link](https://code4rena.com/reports/2021-11-streaming#h-01-wrong-calculation-of-excess-deposittoken-allows-stream-creator-to-retrieve-deposittokenflashloanfeeamount-which-may-cause-fund-loss-to-users) |
| 43 | 62 | H-03 | Reward token not correctly recovered | [link](https://code4rena.com/reports/2021-11-streaming#h-03-reward-token-not-correctly-recovered) |
| 44 | 70 | H-03 | Oracle doesn't calculate USDV/VADER price correctly | [link](https://code4rena.com/reports/2021-12-vader#h-03-oracle-doesnt-calculate-usdvvader-price-correctly) |
| 45 | 70 | H-04 | Vader TWAP averages wrong | [link](https://code4rena.com/reports/2021-12-vader#h-04-vader-twap-averages-wrong) |
| 46 | 70 | H-05 | Oracle returns improperly scaled USDV/VADER price | [link](https://code4rena.com/reports/2021-12-vader#h-05-oracle-returns-an-improperly-scaled-usdvvader-price) |
| 47 | 70 | H-08 | Reserve does not properly apply prices | [link](https://code4rena.com/reports/2021-12-vader#h-08-reserve-does-not-properly-apply-prices-of-vader-and-usdv-tokens) |
| 48 | 70 | H-09 | USDV.sol Mint and Burn Amounts Are Incorrect | [link](https://code4rena.com/reports/2021-12-vader#h-09-usdvsol-mint-and-burn-amounts-are-incorrect) |
| 49 | 71 | H-11 | Wrong implementation of resume() | [link](https://code4rena.com/reports/2022-01-insure#h-11-pooltemplatesolresume-wrong-implementation-of-resume-will-compensate-overmuch-redeem-amount-from-index-pools) |
| 50 | 77 | H-01 | Wrong formula of delta Ro | [link](https://code4rena.com/reports/2022-01-elasticswap#h-01-in-the-case-of-single-asset-entry-new-liquidity-providers-will-suffer-fund-loss-due-to-wrong-formula-of-%CE%B4ro) |
| 51 | 79 | H-02 | Wrong token allocation for decimals != 18 | [link](https://code4rena.com/reports/2022-01-trader-joe#h-02-wrong-token-allocation-computation-for-token-decimals--18-if-floor-price-not-reached) |
| 52 | 97 | H-03 | Wrong formula when add fee incentivePool | [link](https://code4rena.com/reports/2022-03-biconomy#h-03-wrong-formula-when-add-fee-incentivepool-can-lead-to-loss-of-funds) |
| 53 | 113 | H-05 | Mistake while checking LTV to lender accepted LTV | [link](https://code4rena.com/reports/2022-04-abranft#h-05-mistake-while-checking-ltv-to-lender-accepted-ltv) |
| 54 | 192 | H-06 | Incorrect calculation of new price while adding position | [link](https://code4rena.com/reports/2022-12-tigris#h-06-incorrect-calculation-of-new-price-while-adding-position) |
| 55 | 192 | H-09 | Users can bypass maxWinPercent limit | [link](https://code4rena.com/reports/2022-12-tigris#h-09-users-can-bypass-the-maxwinpercent-limit-using-a-partially-closing) |
| 56 | 192 | H-11 | Not enough margin pulled when adding to position | [link](https://code4rena.com/reports/2022-12-tigris#h-11-not-enough-margin-pulled-or-burned-from-user-when-adding-to-a-position) |

---

## 2. Numscout (41 vulnerabilities in 35 contracts)

Source: NumScout paper dataset

### Pattern Distribution

| Pattern | Count | Description |
|---------|-------|-------------|
| div_in_path | 7 | Division results used in conditions |
| operator_order_issue | 5 | Wrong arithmetic order (a/b*c vs a*c/b) |
| indivisible_amount | 19 | Zero result from integer division |
| precision_loss_trend | 3 | Cumulative precision loss |
| exchange_problem | 3 | Exchange calculation rounding errors |
| exchange_rounding | 3 | Exchange rounding direction issues |
| profit_opportunity | 1 | Exploitable profit from rounding |

### Detailed Bug List

#### div_in_path (7)
| # | Contract | Address |
|---|----------|---------|
| 1 | VeChainX | 926476bfc3550ccb424202004b9aab9ac40e32de |
| 2 | Mobius2D | a74642aeae3e2fd79150c910eb5368b64f864b1e |
| 3 | AINU | bc40fad0b36faeb1595aa90d4136d01c08c99092 |
| 4 | GameTime | 122ad2495b1af2a14c5c4b4ca59adfcd79c2dcb3 |
| 5 | WANGMI | 39da420ac0d9a6d8e05c5d9acac75377decfbb42 |
| 6 | dAvInci | 9BAcb4E17328d11b334dA6d48BEC3EC55CEC0858 |
| 7 | UberDelta | d546551924a883b604d4127b0af309c95ba9ba6d |

#### operator_order_issue (5)
| # | Contract | Address |
|---|----------|---------|
| 1 | Nokon | 259562c54c07aca61e12ee12c62016eaf3fd7852 |
| 2 | BoostToken | 4E0fCa55a6C3A94720ded91153A27F60E26B9AA8 |
| 3 | LescoinPreSale | 6a57883b5748bf3631ac2e0d43bf0d6f6cbcd16b |
| 4 | CryptoflipCar | 7e2adafce6033c1272708b58aeab1164017417d2 |
| 5 | UshiOni | 0e90b59e6b1f28d89a647f3224e24af44e824baf |

#### indivisible_amount (19)
| # | Contract | Address |
|---|----------|---------|
| 1 | DOODL | cfc49b91cc35f6ff7c209f7c070bf6e1b66fb151 |
| 2 | ParsecCrowdsale | 3c1634291868ddffa037222991babfccd8400921 |
| 3 | AXNETDEX | acf999bfa9347e8ebe6816ed30bf44b127233177 |
| 4 | CityMayor | 4bdde1e9fbaef2579dd63e2abbf0be445ab93f10 |
| 5 | PapaFloki | 9e86f530866bf7b3e8b23e613495c696f713c3c9 |
| 6 | TheVerdyctResurgence | af83df4264395f7082639db543cdbca3cc9a477c |
| 7 | DODO | 04e5e1a11f92be3560bf58a76723e6fe4dc09abd |
| 8 | DICKEY | 6Fb259f21359E740e6a96Be095f81212A80e831e |
| 9 | BabyDogeDoo | e50b077ecaf6105a70f992fa83b0fdc6a062a349 |
| 10 | MegaBull | 08892eebfad12c909c0cb15ebea385ec997ce1ef |
| 11 | eKISHU | 38195c86c5a32af913f05ba2c82e4c07fdeb2427 |
| 12 | Konnichiwa | 63278489e04Cd2224DAa4e425E57282135db7Af3 |
| 13 | BoostToken | 4E0fCa55a6C3A94720ded91153A27F60E26B9AA8 |
| 14 | SUPERCATS | 05fc938cc60fb71381514877d66478bab7e2e1ce |
| 15 | HYPERLOOP | 7b8741bd212b4f2d0a1b53008670d2b0174a1cd9 |
| 16 | Shibbit | 47e661f80a5fecb42137c97ecd910e2436f3ccad |
| 17 | DiceGame | 84b7d95165328d790a34cc5d7ecf528be55c65ed |
| 18 | UshiOni | 0e90b59e6b1f28d89a647f3224e24af44e824baf |
| 19 | FusionSSJ2 | 638a3d66e4a6a6db13fae6050b36f7067ccaacf9 |

#### precision_loss_trend (3)
| # | Contract | Address |
|---|----------|---------|
| 1 | EthereumGod | 2f0b287275Fc50a1Cb854797927A12a98d3b9460 |
| 2 | HippoHotel | bfBa224810655e7B5D94190700768fa8aBDB9eAa |
| 3 | CryptoflipCar | 7e2adafce6033c1272708b58aeab1164017417d2 |

#### exchange_problem (3)
| # | Contract | Address |
|---|----------|---------|
| 1 | Nokon | 259562c54c07aca61e12ee12c62016eaf3fd7852 |
| 2 | LescoinPreSale | 6a57883b5748bf3631ac2e0d43bf0d6f6cbcd16b |
| 3 | HIT | 2af6139c39c05e0597c0ac12c60b303c38aa69e7 |

#### exchange_rounding (3)
| # | Contract | Address |
|---|----------|---------|
| 1 | Nokon | 259562c54c07aca61e12ee12c62016eaf3fd7852 |
| 2 | LescoinPreSale | 6a57883b5748bf3631ac2e0d43bf0d6f6cbcd16b |
| 3 | HIT | 2af6139c39c05e0597c0ac12c60b303c38aa69e7 |

#### profit_opportunity (1)
| # | Contract | Address |
|---|----------|---------|
| 1 | HIT | 2af6139c39c05e0597c0ac12c60b303c38aa69e7 |

---

## 3. Summary Statistics

| Dataset | Category | Count |
|---------|----------|-------|
| Web3Bugs | S6-1 (Incorrect Calculating Order) | 8 |
| Web3Bugs | S6-2 (Unexpected Return Value) | 4 |
| Web3Bugs | S6-3 (Wrong Numbers in Calculation) | 18 |
| Web3Bugs | S6-4 (Other Accounting Errors) | 56 |
| **Web3Bugs Total** | | **86** |
| Numscout | All patterns | 41 |
| **Grand Total** | | **127** |

---

## 4. Next Steps

For each bug, we need to:
1. Analyze the bug location and root cause
2. Write appropriate Intent annotations
3. Run IntentChecker and record results
4. Document whether the bug is detectable with Intent annotations
