# Web3Bugs S6-* Bug Locations

> Total: 86 bugs

## S6-1: Incorrect Calculating Order (8 bugs)

| # | Contest | Bug | Description | File | Lines | Function |
|---|---------|-----|-------------|------|-------|----------|
| 1 | 18 | H-01 | "Reward computation is wrong" | contracts\LendingPair.sol | 187 | accrueAccount |
| 2 | 35 | H-12 | "ConcentratedLiquidityPool: secondsPerLiquidity sh... | - | - | - |
| 3 | 43 | H-02 | "unstake should update exchange rates first" | - | - | - |
| 4 | 45 | H-01 | "borrow must accrueInterest first" | contracts\interfaces\IUToken.sol | 129 | borrow |
| 5 | 45 | H-02 | "Wrong implementation of CreditLimitByMedian.sol#g... | CreditLimitByMedian.sol | 27-78 | - |
| 6 | 83 | H-02 | "Masterchef: Improper handling of deposit fee" | MasterChef.sol | 170-172 | - |
| 7 | 102 | H-01 | "Oracle price does not compound" | ScalingPriceOracle.sol | 136 | - |
| 8 | 112 | H-01 | "User can steal all rewards due to checkpoint afte... | StakerVault.sol | 112-119 | - |

## S6-2: Unexpected Return Value (4 bugs)

| # | Contest | Bug | Description | File | Lines | Function |
|---|---------|-----|-------------|------|-------|----------|
| 1 | 3 | H-04 | "Inconsistent usage of applyInterest" | - | - | - |
| 2 | 61 | H-02 | "Wrong returns of SavingsAccountUtil.depositFromSa... | contracts\Pool\Pool.sol | 236 | _deposit |
| 3 | 101 | H-01 | "LenderPool: Principal withdrawable is incorrectly... | LenderPool.sol | 594-599 | - |
| 4 | 110 | H-01 | "StakedCitadel doesn’t use correct balance for int... | Vault.sol | 262 | - |

## S6-3: Wrong Numbers in Calculation (18 bugs)

| # | Contest | Bug | Description | File | Lines | Function |
|---|---------|-----|-------------|------|-------|----------|
| 1 | 5 | H-15 | "Wrong slippage protection on Token -> Token trade... | vader-protocol\contracts\Router.sol | 133 | swapWithSynthsWithLimit |
| 2 | 14 | H-01 | "User could lose underlying tokens when redeeming ... | IdleYieldSource.sol | 129-131 | - |
| 3 | 14 | H-03 | "BadgerYieldSource balanceOfToken share calculatio... | Sett.sol | 126 | - |
| 4 | 16 | H-02 | "Use of incorrect index leads to incorrect updatio... | - | - | - |
| 5 | 29 | H-11 | "ConstantProductPool.burnSingle swap amount comput... | trident\contracts\interfaces\IPool.sol | 36 | burnSingle |
| 6 | 30 | H-01 | "Controller.setCap sets wrong vault balance" | contracts\v3\controllers\Controller.sol | 242 | setCap |
| 7 | 32 | H-01 | "Use of tokenB’s price instead of tokenA in determ... | - | - | - |
| 8 | 35 | H-10 | "ConcentratedLiquidityPool.burn() Wrong implementa... | ConcentratedLiquidityPool.sol | 263-267 | - |
| 9 | 42 | H-01 | "Vault fails to track debt correctly that leads to... | MochiVault.sol | 242-249 | - |
| 10 | 47 | H-02 | "Approved spender can spend too many tokens" | - | - | - |
| 11 | 49 | H-01 | "OverlayV1UniswapV3Market computes wrong market li... | contracts\OverlayV1UniswapV3Market.sol | 90 | fetchPricePoint |
| 12 | 51 | H-06 | "Ideal balance is not calculated correctly when pr... | SwapUtils.sol | 1227-1245 | - |
| 13 | 52 | H-16 | "VaderRouter.calculateOutGivenIn calculates wrong ... | contracts\dex\router\VaderRouter.sol | 453 | calculateOutGivenIn |
| 14 | 62 | H-10 | "recoverTokens doesn’t work when isSale is true" | - | - | - |
| 15 | 66 | H-02 | "Yeti token rebase checks the additional token amo... | packages\contracts\contracts\YETI\sYETIToken.sol | 282 | rebase |
| 16 | 78 | H-02 | "wrong minting amount" | - | - | - |
| 17 | 92 | H-01 | "ERC4626 mint uses wrong amount" | src\TurboRouter.sol | 84 | mint |
| 18 | 101 | H-02 | "PooledCreditLine: termination likely fails becaus... | LenderPool.sol | 404-406 | - |

## S6-4: Other Accounting Errors (56 bugs)

| # | Contest | Bug | Description | File | Lines | Function |
|---|---------|-----|-------------|------|-------|----------|
| 1 | 3 | H-05 | "Wrong liquidation logic" | contracts\CrossMarginAccounts.sol | 194 | belowMaintenanceThreshold |
| 2 | 5 | H-07 | "Wrong calcAsymmetricShare calculation" | vader-protocol\contracts\Utils.sol | 266 | calcAsymmetricShare |
| 3 | 5 | H-08 | "Wrong liquidity units calculation" | vader-protocol\contracts\Utils.sol | 229 | calcLiquidityUnits |
| 4 | 5 | H-12 | "getAddedAmount can return wrong results" | - | - | - |
| 5 | 8 | H-03 | "getRandomTokenIdFromFund yields wrong probabiliti... | nftx-protocol-v2\contracts\solidity\NFTXVaultUpgradeable.sol | 413 | getRandomTokenIdFromFund |
| 6 | 12 | H-03 | "YieldMath.sol / Log2: >= or > ?" | contracts\yieldspace\Math64x64.sol | 405 | log_2 |
| 7 | 16 | H-04 | "Logic error in fee subtraction" | LibBalances.sol | 187 | - |
| 8 | 16 | H-06 | "Wrong price scale for GasOracle" | - | - | - |
| 9 | 17 | H-02 | "Buoy3Pool.safetyCheck is not precise and has some... | contracts\interfaces\IBuoy.sol | 8 | safetyCheck |
| 10 | 25 | H-01 | "CompositeMultiOracle returns wrong decimals for p... | contracts\interfaces\external\IERC20Metadata.sol | 25 | decimals |
| 11 | 25 | H-03 | "ERC20Rewards breaks when setting a different toke... | - | - | - |
| 12 | 25 | H-05 | "Exchange rates from Compound are assumed with 18 ... | CTokenMultiOracle.sol | 110 | - |
| 13 | 29 | H-05 | "hybrid pool uses wrong non_optimal_mint_fee" | HybridPool.sol | 425-441 | - |
| 14 | 29 | H-08 | "HybridPool’s reserve is converted to “amount” twi... | - | - | - |
| 15 | 29 | H-14 | "Incorrect usage of _pow in _computeSingleOutGiven... | IndexPool.sol | 279 | - |
| 16 | 29 | H-15 | "Incorrect multiplication in _computeSingleOutGive... | IndexPool.sol | 282 | - |
| 17 | 30 | H-07 | "Vault.balance() mixes normalized and standard amo... | contracts\interfaces\PickleJar.sol | 7 | balance |
| 18 | 30 | H-08 | "Vault.withdraw mixes normalized and standard amou... | contracts\interfaces\DForce.sol | 5 | withdraw |
| 19 | 31 | H-01 | "veCVXStrategy.manualRebalance has wrong logic" | veCVX\contracts\veCVXStrategy.sol | 444 | manualRebalance |
| 20 | 34 | H-01 | "The formula of number of prizes for a degree is w... | v4-core\contracts\DrawCalculator.sol | 414 | _numberOfPrizesForIndex |
| 21 | 35 | H-08 | "Wrong inequality when adding/removing liquidity i... | - | - | - |
| 22 | 35 | H-11 | "ConcentratedLiquidityPool: incorrect feeGrowthGlo... | - | - | - |
| 23 | 39 | H-02 | "Swivel: Taker is charged fees twice in exitVaultF... | gost\build\swivel\Swivel.sol | 268 | exitVaultFillingVaultInitiate |
| 24 | 42 | H-05 | "debts calculation is not accurate" | projects\mochi-core\contracts\interfaces\IMochiVault.sol | 64 | repay |
| 25 | 44 | H-02 | "Wrong calculation of erc20Delta and ethDelta" | Swap.sol | 200-225 | - |
| 26 | 51 | H-02 | "Can not update target price" | SwapUtils.sol | 1571-1581 | - |
| 27 | 51 | H-04 | "Swaps are not split when trade crosses target pri... | customswap\contracts\SwapUtils.sol | 684 | determineA |
| 28 | 52 | H-04 | "TwapOracle doesn’t calculate VADER:USDV exchange ... | Vader.sol | 18-19 | - |
| 29 | 52 | H-09 | "VaderPoolV2 incorrectly calculates the amount of ... | contracts\dex\math\VaderMath.sol | 73 | calculateLoss |
| 30 | 52 | H-15 | "VaderRouter._swap performs wrong swap" | contracts\dex\router\VaderRouter.sol | 304 | _swap |
| 31 | 52 | H-23 | "Synth tokens can get over-minted" | - | - | - |
| 32 | 52 | H-25 | "Wrong design of swap() results in unexpected and ... | contracts\dex\math\VaderMath.sol | 99 | calculateSwap |
| 33 | 52 | H-28 | "Incorrect Price Consultation Results" | - | - | - |
| 34 | 52 | H-34 | "Incorrect Accrual Of sumNative and sumUSD In Prod... | contracts\twap\TwapOracle.sol | 115 | consult |
| 35 | 56 | H-02 | "CDP.sol update overwrites user’s credit on every ... | contracts\v3\alchemix\interfaces\IyVaultV2.sol | 41 | totalDebt |
| 36 | 58 | H-02 | "Wrong implementation of performanceFee can cause ... | - | - | - |
| 37 | 59 | H-04 | "AuctionBurnReserveSkew.getPegDeltaFrequency() Wro... | src\contracts\AuctionBurnReserveSkew.sol | 116 | getPegDeltaFrequency |
| 38 | 59 | H-05 | "AuctionEschapeHatch.sol#exitEarly updates state o... | - | - | - |
| 39 | 60 | H-01 | "Wrong shortfall calculation" | OptimisticLedger.sol | 63 | - |
| 40 | 61 | H-01 | "In CreditLine#_borrowTokensToLiquidate | - | - | - |
| 41 | 61 | H-04 | "Yearn token <> shares conversion decimal issue" | contracts\interfaces\IYield.sol | 69 | getTokensForShares |
| 42 | 62 | H-01 | "Wrong calculation of excess depositToken allows s... | - | - | - |
| 43 | 62 | H-03 | "Reward token not correctly recovered" | Streaming\src\Locke.sol | 646 | recoverTokens |
| 44 | 70 | H-03 | "Oracle doesn’t calculate USDV/VADER price correct... | - | - | - |
| 45 | 70 | H-04 | "Vader TWAP averages wrong" | contracts\dex\pool\BasePool.sol | 148 | mint |
| 46 | 70 | H-05 | "Oracle returns an improperly scaled USDV/VADER pr... | - | - | - |
| 47 | 70 | H-08 | "Reserve does not properly apply prices of VADER a... | - | - | - |
| 48 | 70 | H-09 | "USDV.sol Mint and Burn Amounts Are Incorrect" | contracts\dex\pool\BasePool.sol | 148 | mint |
| 49 | 71 | H-11 | "PoolTemplate.sol#resume() Wrong implementation of... | - | - | - |
| 50 | 77 | H-01 | "In the case of Single Asset Entry | - | - | - |
| 51 | 79 | H-02 | "Wrong token allocation computation for token deci... | contracts\LaunchEvent.sol | 377 | createPair |
| 52 | 97 | H-03 | "Wrong formula when add fee incentivePool can lead... | LiquidityPool.sol | 319-322 | - |
| 53 | 113 | H-05 | "Mistake while checking LTV to lender accepted LTV... | - | - | - |
| 54 | 192 | H-06 | "Incorrect calculation of new price while adding p... | - | - | - |
| 55 | 192 | H-09 | "Users can bypass the maxWinPercent limit using a ... | - | - | - |
| 56 | 192 | H-11 | "Not enough margin pulled or burned from user when... | contracts\Position.sol | 209 | addToPosition |

---

## Summary

- Total S6-* bugs: 86
- File location found: 58 (67%)
- Line numbers found: 58 (67%)
