"""
RQ1 per-case metrics collection for the 20 mitigated cases.

Metrics (all extracted from the contracted case JSON only; dependency code is
pre-analyzed and cached, so it does not affect per-case analysis time):

  1. lines              — source lines covered by code records (annotations excluded)
  2. internal_calls     — bare-identifier call sites whose target is defined or
                          declared inside this JSON (same contraction)
  3. external_calls     — method-style `.method(...)` call sites (library
                          via `using X for Y`, interface method on a variable,
                          CapName(expr).method(...), etc.)
  4. control_flow       — loops (for/while) + branches (if/else if/else)
                          + guards (require/assert)
  5. debug_total        — @StateVar + @LocalVar + @GlobalVar + @IReturn count

Outputs:
  - evaluation/RQ1/rq1_metrics.csv
  - evaluation/RQ1/rq1_correlations.csv
  - evaluation/RQ1/rq1_run{i}.csv (when --runs > 0)

Usage:
    .venv/Scripts/python.exe evaluation/RQ1/collect_metrics.py           # use existing rq1_results.csv
    .venv/Scripts/python.exe evaluation/RQ1/collect_metrics.py --runs 3  # run 3x, average
"""

import argparse
import csv
import json
import re
import shutil
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
MAIN_EVAL_DIR = PROJECT_ROOT / "evaluation" / "RQ1"
MAIN_RESULTS = MAIN_EVAL_DIR / "rq1_results.csv"
OUT_CSV = MAIN_EVAL_DIR / "rq1_metrics.csv"
CORR_CSV = MAIN_EVAL_DIR / "rq1_correlations.csv"

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


# ─────────────────────────────────────────────────────────────
# Source-level metric extraction
# ─────────────────────────────────────────────────────────────

ANNOTATION_PREFIXES = (
    "// @StateVar", "// @LocalVar", "// @GlobalVar", "// @IReturn",
    "// @During", "// @Post", "// @Debugging",
)

# Identifiers that syntactically look like `name(` but are not function calls.
KEYWORD_CALLS = {
    "if", "for", "while", "switch", "return", "emit", "do", "else",
    "try", "catch", "throw", "new", "delete", "revert",
    "require", "assert",        # counted as guards
    "hex", "type",
}

_FUNC_HEAD_RE = re.compile(r"^\s*(?:function|modifier)\s+(\w+)\s*\(")
# Lines whose `name(` pattern is a declaration, not a call-site.
_DEF_HEAD_RE  = re.compile(r"^\s*(?:function|modifier|constructor|event)\b")
_USING_RE     = re.compile(r"^\s*using\s+(\w+)\s+for\s+")
_FOR_RE       = re.compile(r"\bfor\s*\(")
_WHILE_RE     = re.compile(r"\bwhile\s*\(")
_IF_RE        = re.compile(r"\bif\s*\(")
_ELSE_STD_RE  = re.compile(r"\belse(?!\s*if\b)")   # else not followed by if
_REQUIRE_RE   = re.compile(r"\brequire\s*\(")
_ASSERT_RE    = re.compile(r"\bassert\s*\(")
_METHOD_CALL_RE = re.compile(r"(?:(\w+)\s*)?\.\s*(\w+)\s*\(")
_BARE_CALL_RE   = re.compile(r"(?<![\w.])(\w+)\s*\(")


def _is_annotation(code: str) -> bool:
    return any(code.startswith(p) for p in ANNOTATION_PREFIXES)


def _collect_internal_names(recs) -> set[str]:
    """Collect function/modifier names declared OR defined inside this JSON."""
    names: set[str] = set()
    for r in recs:
        if not isinstance(r, dict):
            continue
        code = r.get("code", "").strip()
        if not code or code.startswith("//"):
            continue
        m = _FUNC_HEAD_RE.match(code)
        if m:
            names.add(m.group(1))
    return names


def _count_external_calls(code: str) -> int:
    """Count `.method(...)` sites; skip `abi.method(...)` (encoding built-ins)."""
    n = 0
    for m in _METHOD_CALL_RE.finditer(code):
        obj = m.group(1)  # the identifier immediately before the dot, if any
        if obj == "abi":
            continue
        n += 1
    return n


def _count_internal_calls(code: str, internal_names: set[str]) -> int:
    """Count bare `<id>(` sites where <id> is in `internal_names` and not a keyword."""
    n = 0
    for m in _BARE_CALL_RE.finditer(code):
        ident = m.group(1)
        if ident in KEYWORD_CALLS:
            continue
        if ident in internal_names:
            n += 1
    return n


def extract_source_metrics(json_path: Path) -> dict:
    """Parse the case JSON and compute the 5 metrics + helper counters."""
    recs = json.loads(json_path.read_text(encoding="utf-8"))

    internal_names = _collect_internal_names(recs)

    ann = {
        "debug_statevar": 0, "debug_localvar": 0,
        "debug_globalvar": 0, "debug_ireturn": 0,
        "intent_during": 0, "intent_post": 0,
    }

    loop_count    = 0
    branch_count  = 0
    guard_count   = 0
    internal_calls = 0
    external_calls = 0

    covered_lines: set[int] = set()
    using_libraries: set[str] = set()

    for r in recs:
        if not isinstance(r, dict):
            continue
        code = r.get("code", "").strip()
        start = r.get("startLine", 0) or 0
        end = r.get("endLine", start) or start
        if not code or code == "\n":
            continue

        if code.startswith("// @StateVar"):  ann["debug_statevar"]  += 1; continue
        if code.startswith("// @LocalVar"):  ann["debug_localvar"]  += 1; continue
        if code.startswith("// @GlobalVar"): ann["debug_globalvar"] += 1; continue
        if code.startswith("// @IReturn"):   ann["debug_ireturn"]   += 1; continue
        if code.startswith("// @During"):    ann["intent_during"]   += 1; continue
        if code.startswith("// @Post"):      ann["intent_post"]     += 1; continue
        if code.startswith("// @Debugging"): continue
        if code.startswith("//"):            continue

        # Real source line range
        for ln in range(start, end + 1):
            covered_lines.add(ln)

        um = _USING_RE.match(code)
        if um:
            using_libraries.add(um.group(1))

        # Control flow
        loop_count   += len(_FOR_RE.findall(code))
        loop_count   += len(_WHILE_RE.findall(code))
        n_if         = len(_IF_RE.findall(code))       # includes "else if"
        n_plain_else = len(_ELSE_STD_RE.findall(code)) # else not followed by if
        branch_count += n_if + n_plain_else
        guard_count  += len(_REQUIRE_RE.findall(code))
        guard_count  += len(_ASSERT_RE.findall(code))

        # Call sites — but skip function/modifier/constructor/event header lines,
        # whose `name(` occurrences are declarations, not call sites.
        if not _DEF_HEAD_RE.match(code):
            external_calls += _count_external_calls(code)
            internal_calls += _count_internal_calls(code, internal_names)

    control_flow = loop_count + branch_count + guard_count
    num_records = sum(
        1 for r in recs
        if isinstance(r, dict) and r.get("code", "").strip()
    )

    return {
        "num_records": num_records,
        "lines": len(covered_lines),
        "internal_calls": internal_calls,
        "external_calls": external_calls,
        "control_flow": control_flow,
        # helper sub-counters for debugging / verification
        "loop_count": loop_count,
        "branch_count": branch_count,
        "guard_count": guard_count,
        "using_directives": len(using_libraries),
        **ann,
        "debug_total": (
            ann["debug_statevar"] + ann["debug_localvar"]
            + ann["debug_globalvar"] + ann["debug_ireturn"]
        ),
        "intent_total": ann["intent_during"] + ann["intent_post"],
    }


# ─────────────────────────────────────────────────────────────
# run_all.py result loading
# ─────────────────────────────────────────────────────────────

def load_rq1_results(csv_path: Path = MAIN_RESULTS) -> dict:
    if not csv_path.exists():
        return {}
    out = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["case"], row.get("category", ""))
            out[key] = {
                "analysis_time_sec": float(row.get("analysis_time_sec", 0) or 0),
                "result": row.get("result", ""),
            }
    return out


def run_rq1_evaluation() -> None:
    runner = MAIN_EVAL_DIR / "run_all.py"
    print(f"[info] Running {runner} ...")
    subprocess.run([sys.executable, str(runner)], check=False)


def run_rq1_n_times(n: int) -> dict:
    timings = defaultdict(list)
    last_results = {}

    for i in range(1, n + 1):
        print(f"\n========== run {i}/{n} ==========")
        run_rq1_evaluation()

        if not MAIN_RESULTS.exists():
            print(f"[error] {MAIN_RESULTS} not produced after run {i}")
            continue

        snapshot = MAIN_EVAL_DIR / f"rq1_run{i}.csv"
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(MAIN_RESULTS, snapshot)
        print(f"[ok] snapshot → {snapshot}")

        rq1 = load_rq1_results()
        for key, data in rq1.items():
            timings[key].append(data["analysis_time_sec"])
            last_results[key] = data["result"]

    out = {}
    for key, times in timings.items():
        if not times:
            continue
        out[key] = {
            "analysis_time_mean": statistics.mean(times),
            "analysis_time_stdev": statistics.stdev(times) if len(times) > 1 else 0.0,
            "analysis_time_min": min(times),
            "analysis_time_max": max(times),
            "n_runs": len(times),
            "all_times": times,
            "result": last_results.get(key, ""),
        }
    return out


def load_existing_time_rows(path: Path) -> dict:
    """Load analysis-time fields from an existing rq1_metrics.csv, keyed by display case."""
    if not path.exists():
        return {}
    out = {}
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            case = row.get("case", "").strip()
            if not case:
                continue
            out[case] = {
                "analysis_time_mean": float(row.get("analysis_time_mean", 0) or 0),
                "analysis_time_stdev": float(row.get("analysis_time_stdev", 0) or 0),
                "analysis_time_min": float(row.get("analysis_time_min", 0) or 0),
                "analysis_time_max": float(row.get("analysis_time_max", 0) or 0),
                "n_runs": int(float(row.get("n_runs", 0) or 0)),
                "result": row.get("result", ""),
            }
    return out


# ─────────────────────────────────────────────────────────────
# Analysis
# ─────────────────────────────────────────────────────────────

def collect_rows(case_jsons, rq1_agg: dict, fallback_times: dict) -> list[dict]:
    rows = []
    for rel in case_jsons:
        path = MAIN_EVAL_DIR / rel
        case_name = path.stem.replace("_input", "")
        category = path.parent.name
        display = (
            case_name
            if case_name.startswith("web3bugs_")
            else f"{category}_{case_name}"
        )
        metrics = extract_source_metrics(path)
        agg = rq1_agg.get((case_name, category), {})

        if "analysis_time_mean" in agg:
            time_fields = {
                "analysis_time_mean": round(agg["analysis_time_mean"], 4),
                "analysis_time_stdev": round(agg["analysis_time_stdev"], 4),
                "analysis_time_min": round(agg["analysis_time_min"], 4),
                "analysis_time_max": round(agg["analysis_time_max"], 4),
                "n_runs": agg["n_runs"],
            }
            result_val = agg.get("result", "")
        elif "analysis_time_sec" in agg:
            t = agg["analysis_time_sec"]
            time_fields = {
                "analysis_time_mean": round(t, 4),
                "analysis_time_stdev": 0.0,
                "analysis_time_min": round(t, 4),
                "analysis_time_max": round(t, 4),
                "n_runs": 1 if t > 0 else 0,
            }
            result_val = agg.get("result", "")
        elif display in fallback_times:
            fb = fallback_times[display]
            time_fields = {
                "analysis_time_mean": round(fb["analysis_time_mean"], 4),
                "analysis_time_stdev": round(fb["analysis_time_stdev"], 4),
                "analysis_time_min": round(fb["analysis_time_min"], 4),
                "analysis_time_max": round(fb["analysis_time_max"], 4),
                "n_runs": fb["n_runs"],
            }
            result_val = fb.get("result", "")
        else:
            time_fields = {
                "analysis_time_mean": 0.0, "analysis_time_stdev": 0.0,
                "analysis_time_min": 0.0, "analysis_time_max": 0.0,
                "n_runs": 0,
            }
            result_val = ""

        rows.append({
            "case": display,
            **time_fields,
            "result": result_val,
            **metrics,
        })
    return rows


def write_csv(rows, path: Path) -> None:
    fieldnames = [
        "case",
        "analysis_time_mean", "analysis_time_stdev",
        "analysis_time_min", "analysis_time_max", "n_runs",
        "result",
        # canonical metrics (5)
        "lines", "internal_calls", "external_calls", "control_flow", "debug_total",
        # helpers
        "num_records", "using_directives",
        "loop_count", "branch_count", "guard_count",
        "debug_statevar", "debug_localvar", "debug_globalvar", "debug_ireturn",
        "intent_during", "intent_post", "intent_total",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def pearson(xs, ys) -> float:
    n = len(xs)
    if n == 0:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def compute_correlations(rows):
    numeric_keys = [
        "lines", "internal_calls", "external_calls", "control_flow", "debug_total",
        "loop_count", "branch_count", "guard_count",
        "num_records", "using_directives",
        "debug_statevar", "debug_localvar", "debug_globalvar", "debug_ireturn",
        "intent_during", "intent_post", "intent_total",
    ]
    ys = [r["analysis_time_mean"] for r in rows]
    corrs = []
    for k in numeric_keys:
        xs = [r.get(k, 0) for r in rows]
        corrs.append((k, pearson(xs, ys)))
    corrs.sort(key=lambda t: abs(t[1]), reverse=True)
    return corrs


def write_correlations(corrs, path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "pearson_r_with_analysis_time"])
        for k, v in corrs:
            writer.writerow([k, f"{v:+.4f}"])


def print_correlations(corrs) -> None:
    print("\n=== Pearson correlation with analysis_time_mean ===")
    for k, v in corrs:
        bar = "#" * int(abs(v) * 20)
        print(f"  {k:22s}: {v:+.3f}  {bar}")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RQ1 metrics collection")
    parser.add_argument(
        "--runs", type=int, default=0,
        help="Run run_all.py N times and average. 0 = skip re-running and "
             "re-use analysis_time_* from the existing rq1_metrics.csv if present, "
             "or read rq1_results.csv if that is the only thing available.",
    )
    args = parser.parse_args()

    rq1_agg: dict = {}
    fallback_times = load_existing_time_rows(OUT_CSV)

    if args.runs > 0:
        rq1_agg = run_rq1_n_times(args.runs)
        if not rq1_agg:
            print("[error] No timings collected. Aborting.")
            sys.exit(1)
    else:
        # --runs=0: prefer existing metrics CSV times; if absent, try rq1_results.csv
        if fallback_times:
            print(f"[info] Re-using analysis times from existing {OUT_CSV.name}")
        else:
            if not MAIN_RESULTS.exists():
                print(f"[info] {MAIN_RESULTS} not found and no {OUT_CSV.name} "
                      "to fall back on. Running run_all.py once ...")
                run_rq1_evaluation()
            rq1_agg = load_rq1_results()
            if not rq1_agg:
                print(f"[error] no timing data available. Aborting.")
                sys.exit(1)

    rows = collect_rows(CASE_JSONS, rq1_agg, fallback_times)
    write_csv(rows, OUT_CSV)
    n_runs = rows[0].get("n_runs", 1) if rows else 0
    print(f"\n[ok] Per-case metrics → {OUT_CSV}  ({len(rows)} cases, {n_runs} runs each)")

    corrs = compute_correlations(rows)
    write_correlations(corrs, CORR_CSV)
    print(f"[ok] Correlations → {CORR_CSV}")
    print_correlations(corrs)


if __name__ == "__main__":
    main()
