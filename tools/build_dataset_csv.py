"""Build evaluation/RQ1/dataset.csv master index."""
import csv, re, os
from collections import Counter

rows = []

# === 1. NUMSCOUT (8 entries) ===
numscout = [
    {
        "id": "numscout_WANGMI",
        "source": "numscout",
        "source_label": "div_in_path",
        "contract": "WANGMI",
        "function": "_transfer",
        "bug_line": "428",
        "pattern": "div_in_path",
        "description": "fees.mul(sellLiquidityFee).div(sellTotalFees) precision loss causes tokensForLiquidity to not increase",
        "source_file": "Dataset/Numscout/contraction/div_in_path/WANGMI_contraction.json",
        "status": "annotated",
    },
    {
        "id": "numscout_Nokon",
        "source": "numscout",
        "source_label": "exchange_problem",
        "contract": "Nokon",
        "function": "buy",
        "bug_line": "51",
        "pattern": "exchange_problem",
        "description": "msg.value/ethRateFix*calculateRate() division-first causes precision loss in token amount",
        "source_file": "Dataset/Numscout/contraction/exchange_problem/Nokon_contraction.json",
        "status": "annotated",
    },
    {
        "id": "numscout_SwordCrowdsale",
        "source": "numscout",
        "source_label": "greedy_contract",
        "contract": "SwordCrowdsale",
        "function": "refundMoney",
        "bug_line": "33",
        "pattern": "greedy_contract",
        "description": "weiRaised -= amount missing causes Ether to be permanently locked",
        "source_file": "Dataset/Numscout/contraction/greedy_contract/SwordCrowdsale_contraction.json",
        "status": "annotated",
    },
    {
        "id": "numscout_BoostToken_operator",
        "source": "numscout",
        "source_label": "operator_order_issue",
        "contract": "BoostToken",
        "function": "sendETHToTeam",
        "bug_line": "141;142",
        "pattern": "operator_order_issue",
        "description": "amount.div(12).mul(5) and amount.div(9).mul(2) division-first causes precision loss",
        "source_file": "Dataset/Numscout/contraction/operator_order_issue/BoostToken_contraction.json",
        "status": "annotated",
    },
    {
        "id": "numscout_BoostToken_indivisible",
        "source": "numscout",
        "source_label": "indivisible_amount",
        "contract": "BoostToken",
        "function": "sendETHToTeam",
        "bug_line": "933;934;935;936",
        "pattern": "indivisible_amount",
        "description": "amount.div(4), amount.div(12), amount.div(9) produce zero for small amounts",
        "source_file": "Dataset/Numscout/contraction/indivisible_amount/BoostToken_contraction.sol",
        "status": "pending",
    },
    {
        "id": "numscout_EthereumGod",
        "source": "numscout",
        "source_label": "precision_loss_trend",
        "contract": "EthereumGod",
        "function": "swapAndLiquify",
        "bug_line": "937;941;942;956",
        "pattern": "precision_loss_trend",
        "description": "Multiple chained div/mul operations in fee splitting accumulate precision loss",
        "source_file": "Dataset/Numscout/contraction/precision_loss_trend/EthereumGod_contraction.sol",
        "status": "pending",
    },
    {
        "id": "numscout_HippoHotel",
        "source": "numscout",
        "source_label": "precision_loss_trend",
        "contract": "HippoHotel",
        "function": "withdrawAll",
        "bug_line": "1937",
        "pattern": "precision_loss_trend",
        "description": "balance.mul(25).div(100) truncation causes uneven fund distribution",
        "source_file": "Dataset/Numscout/contraction/precision_loss_trend/HippoHotel_contraction.sol",
        "status": "pending",
    },
    {
        "id": "numscout_HIT",
        "source": "numscout",
        "source_label": "profit_opportunity",
        "contract": "HIT",
        "function": "getTokens",
        "bug_line": "126;144",
        "pattern": "profit_opportunity",
        "description": "Exchange rounding allows receiving tokens without sufficient payment",
        "source_file": "Dataset/Numscout/contraction/profit_opportunity/HIT_contraction.sol",
        "status": "pending",
    },
]
rows.extend(numscout)

# === 2. WEB3BUGS S6 (86 entries) ===
bugs = {}
with open("C:/Users/isjeon/Web3Bugs/results/bugs.csv", "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        contest_id = row[0].strip()
        bug_id = row[1].strip()
        label = row[2].strip()
        desc = row[4].strip().strip('"')
        ref = row[5].strip()
        key = f"{contest_id}_{bug_id}"
        bugs[key] = {"label": label, "desc": desc, "ref": ref}

with open("Dataset/Web3Bugs/SINGLE_TX_NUMERIC.md", "r", encoding="utf-8") as f:
    content = f.read()

s6_section = content[content.find("### S6-1:"):]
matches = re.findall(r"Contest:\s*(\d+),\s*Bug:\s*(H-\d+)", s6_section)

for contest, bug in matches:
    key = f"{contest}_{bug}"
    info = bugs.get(key, {})
    label = info.get("label", "unknown")
    bug_clean = bug.replace("-", "_")
    dir_name = f"contest_{contest}_{bug_clean}"
    source_label_dir = label.replace("-", "_")
    source_dir = f"Dataset/Web3Bugs/{source_label_dir}/{dir_name}"

    rows.append({
        "id": f"web3bugs_{contest}_{bug_clean}",
        "source": "web3bugs",
        "source_label": label,
        "contract": "",
        "function": "",
        "bug_line": "",
        "pattern": "erroneous_accounting",
        "description": info.get("desc", ""),
        "source_file": source_dir,
        "status": "pending",
    })

# === 3. WEB3BUGS S3-1 in-scope (11 entries) ===
s3_1_in_scope = [
    ("18", "H-02", "LendingPair.liquidateAccount does not accrue and update cumulativeInterestRate"),
    ("24", "H-03", "setYieldSource leads to temporary wrong results in share calculation"),
    ("25", "H-02", "ERC20Rewards returns wrong rewards if no tokens initially exist"),
    ("36", "H-02", "Basket.sol auctionBurn failed auction freezes funds due to missing ibRatio update"),
    ("51", "H-03", "SwapUtils.sol wrong tokenPrecisionMultipliers implementation"),
    ("58", "H-04", "AaveVault does not update TVL on deposit/withdraw causing wrong share calculation"),
    ("62", "H-08", "ts.tokens sometimes calculated incorrectly"),
    ("65", "H-01", "Wrong fee calculation after totalSupply was 0"),
    ("70", "H-10", "previousPrices is never updated upon syncing token price"),
    ("83", "H-01", "Wrong reward token calculation in MasterChef due to stale totalPoints"),
    ("192", "H-01", "Lock.sol extendLock does not update totalLocked causing accounting error"),
]

for contest, bug, desc in s3_1_in_scope:
    bug_clean = bug.replace("-", "_")
    dir_name = f"contest_{contest}_{bug_clean}"
    source_dir = f"Dataset/Web3Bugs/S3_1/{dir_name}"

    rows.append({
        "id": f"web3bugs_{contest}_{bug_clean}",
        "source": "web3bugs",
        "source_label": "S3-1",
        "contract": "",
        "function": "",
        "bug_line": "",
        "pattern": "inconsistent_state_updates",
        "description": desc,
        "source_file": source_dir,
        "status": "pending",
    })

# === WRITE CSV ===
fieldnames = [
    "id", "source", "source_label", "contract", "function",
    "bug_line", "pattern", "description", "source_file", "status",
]
outpath = "evaluation/RQ1/dataset.csv"

with open(outpath, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

# === SUMMARY ===
print(f"Total: {len(rows)} entries written to {outpath}")
print()
print("By source:")
for k, v in sorted(Counter(r["source"] for r in rows).items()):
    print(f"  {k}: {v}")
print()
print("By pattern:")
for k, v in sorted(Counter(r["pattern"] for r in rows).items()):
    print(f"  {k}: {v}")
print()
print("By source_label:")
for k, v in sorted(Counter(r["source_label"] for r in rows).items()):
    print(f"  {k}: {v}")
print()
print("By status:")
for k, v in sorted(Counter(r["status"] for r in rows).items()):
    print(f"  {k}: {v}")
