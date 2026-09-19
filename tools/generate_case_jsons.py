#!/usr/bin/env python3
"""
19건 annotated case JSON 생성 스크립트.
형식: code records → intent records → debug records
"""
import json, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
from soltotestjson import slice_solidity

BASE = pathlib.Path(__file__).parent
CONTRACTION = BASE / "target_contracts_contraction"
NS_CONTRACTION = BASE.parent.parent / "Dataset" / "Numscout" / "contraction"
CASES = BASE / "cases"


def make_annotation_record(code: str, line: int) -> dict:
    return {"code": code, "startLine": line, "endLine": line, "event": "add"}


def generate_case(sol_path: pathlib.Path, out_path: pathlib.Path,
                  intents: list[tuple[int, str]],
                  debugs: list[tuple[int, str]]):
    """
    sol_path: contraction .sol
    out_path: output .json
    intents: [(line, annotation_text), ...]
    debugs: [(start_line, annotation_text), ...] — line numbers increment from start_line
    """
    source = sol_path.read_text(encoding='utf-8')
    records = slice_solidity(source)

    # Intent records
    for line, text in intents:
        records.append(make_annotation_record(text, line))

    # Debug records: BEGIN + annotations + END
    if debugs:
        base_line = debugs[0][0]
        records.append(make_annotation_record("// @Debugging BEGIN", base_line))
        for i, (start_line, text) in enumerate(debugs):
            records.append(make_annotation_record(text, start_line + i))
        end_line = base_line + len(debugs)
        records.append(make_annotation_record("// @Debugging END", end_line))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"  {out_path.name}: {len(records)} records ({len(intents)} intent + {len(debugs)} debug)")


def main():
    print("=== Generating case JSONs ===\n")

    # ── 1. web3bugs_5_H_07 (already done manually, skip)

    # ── 2. web3bugs_5_H_08
    generate_case(
        CONTRACTION / "web3bugs_5_H_08.sol",
        CASES / "web3bugs_5_H_08" / "web3bugs_5_H_08.json",
        intents=[(40, "// @During _units == P * (t * B + T * b) / ((T * B) * 2)")],
        debugs=[(33, "// @LocalVar b = [100, 100]"),
                (33, "// @LocalVar B = [1000, 1000]"),
                (33, "// @LocalVar t = [100, 100]"),
                (33, "// @LocalVar T = [1000, 1000]"),
                (33, "// @LocalVar P = [500, 500]")],
    )

    # ── 3. web3bugs_5_H_12
    generate_case(
        CONTRACTION / "web3bugs_5_H_12.sol",
        CASES / "web3bugs_5_H_12" / "web3bugs_5_H_12.json",
        intents=[(34, "// @Post returnExpression == _balance - mapToken_tokenAmount[_token]")],
        debugs=[(24, "// @LocalVar _token = symbolicAddress 1"),
                (24, "// @LocalVar _pool = symbolicAddress 2"),
                (24, "// @StateVar VADER = symbolicAddress 3"),
                (24, "// @StateVar USDV = symbolicAddress 4"),
                (24, "// @StateVar mapToken_tokenAmount[1] = [100, 100]"),
                (24, "// @StateVar mapToken_tokenAmount[2] = [50, 50]"),
                (24, "// @IReturn iERC20(_token).balanceOf() = [200, 200]")],
    )

    # ── 4. web3bugs_56_H_02
    generate_case(
        CONTRACTION / "web3bugs_56_H_02.sol",
        CASES / "web3bugs_56_H_02" / "web3bugs_56_H_02.json",
        intents=[(46, "// @Post totalCredit(entry <= exit)")],
        debugs=[(37, "// @StateVar _self.totalCredit = [1000, 1000]"),
                (37, "// @StateVar _self.totalDebt = [0, 0]"),
                (37, "// @StateVar _self.totalDeposited = [1000, 1000]"),
                (37, "// @StateVar _self.lastAccumulatedYieldWeight.x = [1000000000000000000, 1000000000000000000]"),
                (37, "// @StateVar _ctx.accumulatedYieldWeight.x = [1200000000000000000, 1200000000000000000]")],
    )

    # ── 5. web3bugs_60_H_01
    generate_case(
        CONTRACTION / "web3bugs_60_H_01.sol",
        CASES / "web3bugs_60_H_01" / "web3bugs_60_H_01.json",
        intents=[(23, "// @During self.shortfall == 150")],
        debugs=[(15, "// @StateVar self.shortfall = [100, 100]"),
                (15, "// @StateVar self.balances[account] = [50, 50]"),
                (15, "// @LocalVar amount = [-100, -100]")],
    )

    # ── 6. web3bugs_77_H_01
    generate_case(
        CONTRACTION / "web3bugs_77_H_01.sol",
        CASES / "web3bugs_77_H_01" / "web3bugs_77_H_01.json",
        intents=[(38, "// @Post returnExpression >= 363")],
        debugs=[(35, "// @LocalVar _totalSupplyOfLiquidityTokens = [1000, 1000]"),
                (35, "// @LocalVar _tokenQtyAToAdd = [4000, 4000]"),
                (35, "// @LocalVar _internalTokenAReserveQty = [5000, 5000]"),
                (35, "// @LocalVar _tokenBDecayChange = [4000, 4000]"),
                (35, "// @LocalVar _tokenBDecay = [9000, 9000]")],
    )

    # ── 7. web3bugs_51_H_02
    generate_case(
        CONTRACTION / "web3bugs_51_H_02.sol",
        CASES / "web3bugs_51_H_02" / "web3bugs_51_H_02.json",
        intents=[(113, "// @During require feasible")],
        debugs=[(105, "// @GlobalVar block.timestamp = [2000000, 2000000]"),
                (105, "// @StateVar self.initialTargetPriceTime = [1000000, 1000000]"),
                (105, "// @StateVar self.futureTargetPriceTime = [1500000, 1500000]"),
                (105, "// @StateVar self.futureTargetPrice = [1000000000000000000, 1000000000000000000]"),
                (105, "// @StateVar self.initialTargetPrice = [1000000000000000000, 1000000000000000000]"),
                (105, "// @StateVar self.originalPrecisionMultipliers[0] = [1000000000000000000, 1000000000000000000]"),
                (105, "// @LocalVar futureTargetPrice_ = [990000000000000000, 990000000000000000]"),
                (105, "// @LocalVar futureTime_ = [3209600, 3209600]")],
    )

    # ── 8. web3bugs_58_H_02
    generate_case(
        CONTRACTION / "web3bugs_58_H_02.sol",
        CASES / "web3bugs_58_H_02" / "web3bugs_58_H_02.json",
        intents=[(85, "// @During toMint < baseSupply")],
        debugs=[(23, "// @StateVar lastFeeCharge = [0, 0]"),
                (23, "// @StateVar _lpPriceHighWaterMarks[0] = [1900000000000000000, 1900000000000000000]"),
                (23, "// @StateVar _lpPriceHighWaterMarks[1] = [2900000000000000000, 2900000000000000000]"),
                (23, "// @LocalVar thisNft = [1, 1]"),
                (23, "// @LocalVar tvls[0] = [2000000000000000000000, 2000000000000000000000]"),
                (23, "// @LocalVar tvls[1] = [3000000000000000000000, 3000000000000000000000]"),
                (23, "// @LocalVar supply = [1000000000000000000000, 1000000000000000000000]"),
                (23, "// @LocalVar deltaTvls[0] = [100000000000000000000, 100000000000000000000]"),
                (23, "// @LocalVar deltaTvls[1] = [150000000000000000000, 150000000000000000000]"),
                (23, "// @LocalVar deltaSupply = [100000000000000000000, 100000000000000000000]"),
                (23, "// @LocalVar isWithdraw = false"),
                (23, "// @IReturn vg.delayedProtocolParams().managementFeeChargeDelay = [0, 0]"),
                (23, "// @IReturn vg.delayedStrategyParams().managementFee = [0, 0]"),
                (23, "// @IReturn vg.delayedStrategyParams().performanceFee = [100000000, 100000000]"),
                (23, "// @IReturn vg.delayedStrategyParams().strategyPerformanceTreasury = symbolicAddress 1"),
                (23, "// @IReturn vg.delayedProtocolPerVaultParams().protocolFee = [0, 0]")],
    )

    # ── 9. web3bugs_62_H_08
    generate_case(
        CONTRACTION / "web3bugs_62_H_08.sol",
        CASES / "web3bugs_62_H_08" / "web3bugs_62_H_08.json",
        intents=[(182, "// @Post tokensNotYetStreamed[101].lastUpdate == 1000")],
        debugs=[(146, "// @GlobalVar block.timestamp = [1000, 1000]"),
                (146, "// @StateVar endStream = [2000, 2000]"),
                (146, "// @StateVar startTime = [500, 500]"),
                (146, "// @StateVar streamDuration = [1500, 1500]"),
                (146, "// @StateVar depositDecimalsOne = [1000000000000000000, 1000000000000000000]"),
                (146, "// @StateVar lastUpdate = [1000, 1000]"),
                (146, "// @StateVar cumulativeRewardPerToken = [100, 100]"),
                (146, "// @StateVar totalVirtualBalance = [0, 0]"),
                (146, "// @StateVar unstreamed = [0, 0]"),
                (146, "// @StateVar tokensNotYetStreamed[101].tokens = [0, 0]"),
                (146, "// @StateVar tokensNotYetStreamed[101].lastUpdate = [800, 800]"),
                (146, "// @StateVar tokensNotYetStreamed[101].rewards = [0, 0]"),
                (146, "// @StateVar tokensNotYetStreamed[101].lastCumulativeRewardPerToken = [100, 100]"),
                (146, "// @StateVar tokensNotYetStreamed[101].virtualBalance = [0, 0]")],
    )

    # ── 10. web3bugs_70_H_10
    generate_case(
        CONTRACTION / "web3bugs_70_H_10.sol",
        CASES / "web3bugs_70_H_10" / "web3bugs_70_H_10.json",
        intents=[(114, "// @Post changed(previousPrices[0], true)")],
        debugs=[(85, "// @GlobalVar block.timestamp = [10000, 10000]"),
                (85, "// @StateVar previousPrices[0] = [1000000000000000, 1000000000000000]"),
                (85, "// @StateVar vaderPairs.length = [1, 1]"),
                (85, "// @StateVar totalLiquidityWeight[0] = [1, 1]"),
                (85, "// @StateVar twapData[1].lastMeasurement = [1000, 1000]"),
                (85, "// @StateVar twapData[1].updatePeriod = [60, 60]"),
                (85, "// @StateVar twapData[1].pastLiquidityEvaluation = [1, 1]"),
                (85, "// @StateVar twapData[1].nativeTokenPriceCumulative = [0, 0]")],
    )

    # ── Numscout cases ──

    # ── 11. numscout_WANGMI
    generate_case(
        NS_CONTRACTION / "div_in_path" / "WANGMI_contraction.sol",
        CASES / "div_in_path" / "WANGMI_input.json",
        intents=[(428, "// @During tokensForLiquidity(Before < After)")],
        debugs=[(384, "// @LocalVar _from = symbolicAddress 1"),
                (384, "// @LocalVar to = symbolicAddress 2"),
                (384, "// @LocalVar amount = [33, 33]"),
                (384, "// @StateVar uniswapV2Pair = symbolicAddress 2"),
                (384, "// @StateVar sellLiquidityFee = [3, 3]"),
                (384, "// @StateVar sellTxFee = [9, 9]"),
                (384, "// @StateVar tokensForLiquidity = [100, 100]"),
                (384, "// @StateVar tokensForTax = [50, 50]"),
                (384, "// @StateVar isLaunched = true"),
                (384, "// @StateVar maxTxLimit = [1000, 1000]"),
                (384, "// @StateVar maxWalletLimit = [10000, 10000]"),
                (384, "// @StateVar swapAtAmount = [10000, 10000]"),
                (384, "// @StateVar swapping = false"),
                (384, "// @StateVar isExcludedFromTxLimit[_from] = true"),
                (384, "// @StateVar isExcludedFromTxLimit[to] = true"),
                (384, "// @StateVar isExcludedFromFees[_from] = false"),
                (384, "// @StateVar isExcludedFromFees[to] = false"),
                (384, "// @StateVar isBlacklisted[_from] = false"),
                (384, "// @StateVar isExcludedFromWalletLimit[to] = true"),
                (384, "// @GlobalVar block.number = [10, 10]"),
                (384, "// @StateVar launchBlock = [5, 5]")],
    )

    # ── 12. numscout_Nokon
    generate_case(
        NS_CONTRACTION / "exchange_problem" / "Nokon_contraction.sol",
        CASES / "exchange_problem" / "Nokon_input.json",
        intents=[(51, "// @During amountToBuy * ethRateFix >= msg.value * 250000")],
        debugs=[(49, "// @GlobalVar msg.value = [50000000000500000, 50000000000500000]"),
                (49, "// @StateVar presell = true"),
                (49, "// @StateVar balances[1] = [2000000000000, 2000000000000]")],
    )

    # ── 13. numscout_SwordCrowdsale
    generate_case(
        NS_CONTRACTION / "greedy_contract" / "SwordCrowdsale_contraction.sol",
        CASES / "greedy_contract" / "SwordCrowdsale_input.json",
        intents=[(81, "// @Post weiRaised(Entry > Exit)")],
        debugs=[(76, "// @StateVar contributorList[_address].contributionAmount = [100, 100]"),
                (76, "// @StateVar weiRaised = [1000, 1000]")],
    )

    # ── 14. numscout_BoostToken_operator
    generate_case(
        NS_CONTRACTION / "operator_order_issue" / "BoostToken_contraction.sol",
        CASES / "operator_order_issue" / "BoostToken_input.json",
        intents=[(141, "// @During transfer.arg[0] >= amount * 5 / 12"),
                 (142, "// @During transfer.arg[0] >= amount * 2 / 9")],
        debugs=[(140, "// @LocalVar amount = [68, 68]")],
    )

    # ── 15. numscout_BoostToken_indivisible
    generate_case(
        NS_CONTRACTION / "indivisible_amount" / "BoostToken_contraction.sol",
        CASES / "indivisible_amount" / "BoostToken_input.json",
        intents=[(136, "// @During transfer.arg[0] > 0"),
                 (137, "// @During transfer.arg[0] > 0"),
                 (138, "// @During transfer.arg[0] > 0"),
                 (139, "// @During transfer.arg[0] > 0")],
        debugs=[(135, "// @LocalVar amount = [3, 3]")],
    )

    # ── 16. numscout_HIT
    generate_case(
        NS_CONTRACTION / "profit_opportunity" / "HIT_contraction.sol",
        CASES / "profit_opportunity" / "HIT_input.json",
        intents=[(69, "// @During toGive => msg.value")],
        debugs=[(54, "// @GlobalVar msg.value = [0, 0]"),
                (54, "// @StateVar value = [5000000000000000000000, 5000000000000000000000]"),
                (54, "// @StateVar totalRemaining = [800000000000000000000000000, 800000000000000000000000000]"),
                (54, "// @StateVar totalDistributed = [200000000000000000000000000, 200000000000000000000000000]"),
                (54, "// @StateVar totalSupply = [1000000000000000000000000000, 1000000000000000000000000000]"),
                (54, "// @StateVar distributionFinished = false"),
                (54, "// @StateVar blacklist[msg.sender] = false")],
    )

    # ── 17. web3bugs_78_H_02
    generate_case(
        CONTRACTION / "web3bugs_78_H_02.sol",
        CASES / "web3bugs_78_H_02" / "web3bugs_78_H_02.json",
        intents=[(24, "// @Post _balances[to] <= amount")],
        debugs=[(19, "// @StateVar _totalSupply = [1000000000000000000000, 1000000000000000000000]"),
                (19, "// @StateVar _balances[to] = [0, 0]"),
                (19, "// @IReturn IERC20(baseToken).balanceOf() = [1500000000000000000000, 1500000000000000000000]"),
                (19, "// @LocalVar amount = [500000000000000000000, 500000000000000000000]")],
    )

    # ── 18. web3bugs_42_H_01
    generate_case(
        CONTRACTION / "web3bugs_42_H_01.sol",
        CASES / "web3bugs_42_H_01" / "web3bugs_42_H_01.json",
        intents=[(50, "// @During debts >= increasingDebt + 800")],
        debugs=[(29, "// @StateVar debts = [800, 800]"),
                (29, "// @StateVar debtIndex = [1000000000000000000, 1000000000000000000]"),
                (29, "// @GlobalVar block.timestamp = [1000000, 1000000]"),
                (29, "// @StateVar lastAccrued = [1000000, 1000000]"),
                (29, "// @StateVar details[2].collateral = [10000000000000000000, 10000000000000000000]"),
                (29, "// @StateVar details[2].debt = [0, 0]"),
                (29, "// @StateVar details[2].debtIndex = [1000000000000000000, 1000000000000000000]"),
                (29, "// @IReturn engine.mochiProfile().calculateFeeIndex() = [1000000000000000000, 1000000000000000000]"),
                (29, "// @IReturn engine.cssr().update() = [1000000000000000000, 1000000000000000000]"),
                (29, "// @IReturn engine.mochiProfile().maxCollateralFactor() = [800000000000000000, 800000000000000000]"),
                (29, "// @IReturn engine.mochiProfile().creditCap() = [100000000000000000000, 100000000000000000000]"),
                (29, "// @IReturn engine.mochiProfile().minimumDebt() = [0, 0]"),
                (29, "// @IReturn engine.nft().ownerOf() = symbolicAddress 1"),
                (29, "// @IReturn engine.nft().asset() = symbolicAddress 2"),
                (29, "// @LocalVar _id = [2, 2]"),
                (29, "// @LocalVar _amount = [1000, 1000]")],
    )

    # ── (manual) web3bugs_45_H_01, web3bugs_101_H_01, web3bugs_47_H_02

    print(f"\nDone. Generated in {CASES}")


if __name__ == "__main__":
    main()
