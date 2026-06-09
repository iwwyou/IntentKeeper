"""
RQ1 전체 케이스 실행 + CSV 출력

각 케이스를 main.py subprocess로 실행하여
분석 시간(dependency 제외), intent 타입, 결과를 수집한다.
출력은 evaluation/RQ1/rq1_results.csv 로 저장된다.
3-run 평균/표준편차 + 5개 complexity metric 까지 모은 rq1_metrics.csv
는 collect_metrics.py 가 본 스크립트를 N 회 호출해서 만든다.

Usage:
    python evaluation/RQ1/run_all.py                # 전체 실행 + CSV 출력
    python evaluation/RQ1/run_all.py --case Nokon   # 특정 케이스만
"""

import subprocess, sys, os, json, re, csv, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

# ── 케이스 목록 (서브폴더/파일) ──
# 구버전 루트 JSON 제외, 서브폴더 내 최신 JSON만 사용
CASE_JSONS = [
    "cases/div_in_path/WANGMI_input.json",
    "cases/exchange_problem/Nokon_input.json",
    "cases/greedy_contract/SwordCrowdsale_input.json",
    "cases/operator_order_issue/BoostToken_input.json",
    "cases/indivisible_amount/BoostToken_input.json",
    "cases/profit_opportunity/HIT_input.json",
    "cases/web3bugs_5_H_07/web3bugs_5_H_07.json",
    "cases/web3bugs_5_H_08/web3bugs_5_H_08.json",
    "cases/web3bugs_5_H_12/web3bugs_5_H_12.json",
    "cases/web3bugs_45_H_01/web3bugs_45_H_01.json",
    "cases/web3bugs_47_H_02/web3bugs_47_H_02.json",
    "cases/web3bugs_51_H_02/web3bugs_51_H_02.json",
    "cases/web3bugs_56_H_02/web3bugs_56_H_02.json",
    "cases/web3bugs_58_H_02/web3bugs_58_H_02.json",
    "cases/web3bugs_60_H_01/web3bugs_60_H_01.json",
    "cases/web3bugs_62_H_08/web3bugs_62_H_08.json",
    "cases/web3bugs_70_H_10/web3bugs_70_H_10.json",
    "cases/web3bugs_77_H_01/web3bugs_77_H_01.json",
    "cases/web3bugs_78_H_02/web3bugs_78_H_02.json",
    "cases/web3bugs_101_H_01/web3bugs_101_H_01.json",
]


def classify_during(body: str) -> str:
    if "Before" in body and "After" in body:
        return "BeforeAfter"
    if "Assign" in body and "Current" in body:
        return "AssignCurrent"
    if body.startswith("require feasible"):
        return "Feasible"
    if ".arg[" in body:
        return "FunctionArg"
    if "=>" in body:
        return "Implication"
    return "RelationalCmp"


def classify_post(body: str) -> str:
    if "Entry" in body and "Exit" in body:
        return "EntryExit"
    if body.startswith("returnExpression"):
        return "ReturnExprCmp"
    if "changed(" in body:
        return "VarChanged"
    return "RelationalCmp"


def analyze_intents(json_path: Path) -> dict:
    """JSON에서 intent annotation 유형 집계 (unique per case)"""
    recs = json.loads(json_path.read_text(encoding="utf-8"))
    num_records = len(recs)

    during_set = set()
    post_set = set()
    for r in recs:
        if not isinstance(r, dict):
            continue
        code = r.get("code", "").strip()
        if code.startswith("// @During "):
            during_set.add(code[len("// @During "):])
        elif code.startswith("// @Post "):
            post_set.add(code[len("// @Post "):])

    counts = {
        "num_records": num_records,
        "during_total": len(during_set),
        "during_BeforeAfter": 0,
        "during_RelationalCmp": 0,
        "during_FunctionArg": 0,
        "during_Implication": 0,
        "during_Feasible": 0,
        "post_total": len(post_set),
        "post_EntryExit": 0,
        "post_RelationalCmp": 0,
        "post_ReturnExprCmp": 0,
        "post_VarChanged": 0,
    }

    for body in during_set:
        key = "during_" + classify_during(body)
        if key in counts:
            counts[key] += 1

    for body in post_set:
        key = "post_" + classify_post(body)
        if key in counts:
            counts[key] += 1

    return counts


def run_case(json_rel: str) -> dict:
    """main.py subprocess로 케이스 실행, 결과 파싱"""
    base = Path(__file__).parent
    json_path = base / json_rel

    case_name = json_path.stem.replace("_input", "")
    category = json_path.parent.name

    # intent 분류
    intent_counts = analyze_intents(json_path)

    # subprocess 실행
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    main_py = str(PROJECT_ROOT / "main.py")
    json_str = str(json_path)

    try:
        proc = subprocess.run(
            [sys.executable, main_py, json_str],
            capture_output=True, timeout=180, env=env,
            cwd=str(PROJECT_ROOT),
        )
        out = proc.stdout.decode("utf-8", errors="replace")
        err = proc.stderr.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return {
            "case": case_name, "category": category,
            **intent_counts,
            "analysis_time_sec": 180.0,
            "result": "TIMEOUT", "violation_count": 0, "warning_count": 0,
            "max_risk": "", "error": "timeout",
        }

    # 결과 파싱
    # VIOLATION / VIOLATED 양쪽 매칭, risk= 있든 없든 카운트
    v_lines = re.findall(r"INTENT VIOLAT(?:ION|ED)\].*", out)
    post_v_lines = re.findall(r"POST INTENT VIOLAT(?:ION|ED)\].*", out)
    w_lines = re.findall(r"INTENT WARNING\].*", out)

    all_v_lines = v_lines + post_v_lines
    v_count = len(all_v_lines)
    w_count = len(w_lines)

    all_risks = [float(m) for line in all_v_lines + w_lines
                 for m in re.findall(r"risk=([0-9.]+)", line)]
    max_risk = max(all_risks) if all_risks else 0.0

    if v_count > 0:
        result = "VIOLATED"
    elif w_count > 0:
        result = "WARNING"
    else:
        # error check
        err_match = re.search(r"(ValueError|AttributeError|TypeError|KeyError):.*", err + out)
        if err_match:
            result = "ERROR"
        else:
            result = "SATISFIED"

    # timing 파싱
    timing_match = re.search(r"\[TIMING\]\s+([0-9.]+)s", out)
    analysis_time = float(timing_match.group(1)) if timing_match else 0.0

    error_msg = ""
    if result == "ERROR":
        err_line = re.search(r"(ValueError|AttributeError|TypeError|KeyError):.*", err + out)
        error_msg = err_line.group(0)[:100] if err_line else "unknown error"

    return {
        "case": case_name, "category": category,
        **intent_counts,
        "analysis_time_sec": round(analysis_time, 4),
        "result": result,
        "violation_count": v_count,
        "warning_count": w_count,
        "max_risk": max_risk,
        "error": error_msg,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RQ1 전체 실행")
    parser.add_argument("--case", help="특정 케이스만 실행 (부분 매칭)")
    parser.add_argument("--csv", default="evaluation/RQ1/rq1_results.csv", help="CSV 출력 경로")
    args = parser.parse_args()

    targets = CASE_JSONS
    if args.case:
        targets = [j for j in CASE_JSONS if args.case.lower() in j.lower()]
        if not targets:
            print(f"'{args.case}'에 매칭되는 케이스 없음")
            return

    print(f"=== RQ1 Evaluation: {len(targets)} cases ===\n")

    results = []
    for i, json_rel in enumerate(targets, 1):
        case_name = Path(json_rel).stem.replace("_input", "")
        print(f"[{i}/{len(targets)}] {case_name} ...", end=" ", flush=True)
        row = run_case(json_rel)
        results.append(row)
        print(f"{row['result']} ({row['analysis_time_sec']}s)")

    # CSV 출력
    csv_path = PROJECT_ROOT / args.csv
    fieldnames = [
        "case", "category", "num_records", "analysis_time_sec",
        "during_total", "during_BeforeAfter", "during_RelationalCmp",
        "during_FunctionArg", "during_Implication", "during_Feasible",
        "post_total", "post_EntryExit", "post_RelationalCmp",
        "post_ReturnExprCmp", "post_VarChanged",
        "result", "violation_count", "warning_count", "max_risk", "error",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # 요약
    v_total = sum(r["violation_count"] for r in results)
    w_total = sum(r["warning_count"] for r in results)
    violated_cases = sum(1 for r in results if r["result"] == "VIOLATED")
    error_cases = sum(1 for r in results if r["result"] == "ERROR")
    times = [r["analysis_time_sec"] for r in results]
    total_time = sum(times)
    avg_time = total_time / len(times) if times else 0

    print(f"\n{'='*50}")
    print(f"Results: {violated_cases} VIOLATED / {len(results)} cases")
    if error_cases:
        print(f"         {error_cases} ERROR")
    print(f"Time:    total={total_time:.2f}s  avg={avg_time:.2f}s  "
          f"min={min(times):.2f}s  max={max(times):.2f}s")
    print(f"CSV:     {csv_path}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
