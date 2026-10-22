# -*- coding: utf-8 -*-
"""
리팩터링 기준선(Phase 0) — 48 expressible 케이스를 돌려 **노드별 상태·판정·디버깅 슬롯·시간**을 덤프한다.
(REFACTOR_PLAN.md §4 Phase 0)

run_cases.py 와 같은 레코드 재생 경로(main.py 싱글턴, 케이스별 새 프로세스)를 쓰되,
debug flush 마다 Engine 의 freeze 게이트(`_capture_debug_fcfg`)로 해석 직후 fcfg 를 떠서 저장한다.
엔진 코드는 건드리지 않는다 — flush 를 감싸는 것은 이 하네스 안에서만.

사용:
  .venv/Scripts/python.exe evaluation/refactor/baseline_cases.py --tag p0            # legacy 케이스(RQ1/cases)
  .venv/Scripts/python.exe evaluation/refactor/baseline_cases.py --tag p0 --rebuilt  # cases_rebuilt + 프로젝트 deps
  .venv/Scripts/python.exe evaluation/refactor/baseline_cases.py --tag p0 --only web3bugs_5_H_07
출력: evaluation/refactor/baseline/<tag>_<legacy|rebuilt>.json
"""
import argparse
import contextlib
import csv
import io
import json
import os
import pathlib
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IV = ROOT / "evaluation" / "intent_validation"
DS = ROOT / "evaluation" / "Dataset"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
OUT = HERE / "baseline"

import re  # noqa: E402


class rc:
    """run_cases.py 의 헬퍼 사본. (run_cases.py:163 이 커밋 상태에서 SyntaxError 라 import 할 수 없다 — 보고됨)"""
    CASES = ROOT / "evaluation" / "RQ1" / "cases"
    SPECIAL = {
        "numscout_WANGMI": "div_in_path/WANGMI_input.json",
        "numscout_Nokon": "exchange_problem/Nokon_input.json",
        "flyinointment_SwordCrowdsale": "greedy_contract/SwordCrowdsale_input.json",
        "numscout_BoostToken_operator": "operator_order_issue/BoostToken_input.json",
        "numscout_BoostToken_indivisible": "indivisible_amount/BoostToken_input.json",
        "numscout_HIT": "profit_opportunity/HIT_input.json",
        "numscout_EthereumGod": "numscout_EthereumGod/numscout_EthereumGod.json",
    }
    ANN = re.compile(r"^\s*//\s*(@\w+)")

    @classmethod
    def case_path(cls, cid):
        if cid in cls.SPECIAL:
            return cls.CASES / cls.SPECIAL[cid]
        return cls.CASES / cid / f"{cid}.json"

    @staticmethod
    def to_current_syntax(code):
        s = code.lstrip()
        if s.startswith("//"):
            s = s[2:].lstrip()
        if s.startswith("@LocalVar"):
            s = "@Param" + s[len("@LocalVar"):]
        return s

    @staticmethod
    def verdict(results):
        st = [str(r["status"] or "").lower() for r in results]
        if not st:
            return "None"
        for key, name in (("violat", "Violated"), ("warn", "Warning"), ("unreach", "Unreachable"),
                          ("satisf", "Satisfied"), ("success", "Satisfied")):
            if any(key in s for s in st):
                return name
        return "Other:" + ",".join(sorted(set(st)))

    @staticmethod
    def declared_names(sol_path):
        text = re.sub(r"//[^\n]*", "", sol_path.read_text(encoding="utf-8"))
        return sorted(set(re.findall(r"^\s*(?:abstract\s+)?(?:contract|library|interface)\s+(\w+)", text, re.M)))


def _dump_fcfg(fz, ca) -> dict:
    """frozen fcfg → {function, nodes:{name:{lines, stmts, state}}, return_vals}."""
    import engine_api
    nodes = {}
    for n in sorted(fz.graph.nodes(), key=lambda x: x.name):
        stmts = [f"{getattr(s, 'statement_type', '?')}@{getattr(s, 'src_line', None)}"
                 for s in getattr(n, "statements", []) or []]
        try:
            state = engine_api._serialize_node_state(n, ca.recorder)
        except Exception as ex:                      # 기록만 — 기준선은 현 동작을 그대로 남긴다
            state = {"__serialize_error__": f"{type(ex).__name__}: {ex}"}
        nodes[n.name] = {"succ": sorted(s.name for s in fz.graph.successors(n)), "stmts": stmts, "state": state}
    ex = fz.get_exit_node()
    rv = {str(k): str(v) for k, v in (getattr(ex, "return_vals", {}) or {}).items()}
    return {"function": getattr(fz, "function_name", None), "nodes": nodes, "return_vals": rv}


def _slots(fz, ca) -> list:
    import engine_api
    ccf = ca.contract_cfgs.get(ca.current_target_contract)
    try:
        sl = engine_api._derive_debug_slots(fz, ccf, "", getattr(fz, "function_name", "") or "",
                                            ca.interface_names, ca.contract_cfgs)
        return sorted(f"{s.kind}:{s.key}:{s.valueKind}" for s in sl)
    except Exception as ex:
        return [f"__slot_error__ {type(ex).__name__}: {ex}"]


def run_one(path: pathlib.Path) -> dict:
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        import main
        from main import sa, contract_analyzer as ca, batch_mgr
        from Utils.Helper import ParserHelpers
        from Utils.YulHelper import YulParserHelpers
        from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
        from Analyzer.EnhancedYulVisitor import EnhancedYulVisitor

    runs = []
    orig_flush = batch_mgr.flush

    def flush():
        ca._capture_debug_fcfg = True
        ca._frozen_debug_fcfg = None
        t = time.perf_counter()
        try:
            return orig_flush()
        finally:
            dt = time.perf_counter() - t
            fz = getattr(ca, "_frozen_debug_fcfg", None)
            if fz is not None:
                d = _dump_fcfg(fz, ca)
                d["slots"] = _slots(fz, ca)
                d["callees"] = sorted(f"{k[0]}#{k[1]}.{k[2]}" for k in (getattr(ca, "_frozen_callee_states", {}) or {}))
                d["elapsed_s"] = round(dt, 3)
                runs.append(d)
            ca._capture_debug_fcfg = False

    batch_mgr.flush = flush

    recs = json.loads(path.read_text(encoding="utf-8"))
    t0 = time.perf_counter()
    err = None
    with contextlib.redirect_stdout(buf):
        try:
            in_batch = False
            for rec in recs:
                code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
                sa.update_code(s, e, code, ev, rec.get("closeBefore", False))
                st = code.lstrip()
                if st.startswith("// @Debugging BEGIN"):
                    batch_mgr.reset(); in_batch = True; continue
                if st.startswith("// @Debugging END"):
                    batch_mgr.flush(); in_batch = False; continue
                if rc.ANN.match(code):
                    text = rc.to_current_syntax(code)
                    if text.startswith(("@During", "@Post")):
                        EnhancedSolidityVisitor(ca).visit(ParserHelpers.generate_parse_tree(text, "intentUnit"))
                        continue
                    if ev != "delete":
                        batch_mgr.add(text)
                    if not in_batch:
                        batch_mgr.flush()
                    continue
                if code.strip():
                    ctx = ca.get_current_context_type()
                    if ctx == "assembly":
                        EnhancedYulVisitor(ca).visit(YulParserHelpers.generate_parse_tree(code))
                    else:
                        EnhancedSolidityVisitor(ca).visit(ParserHelpers.generate_parse_tree(code, ctx, True))
        except Exception as ex:
            import traceback
            err = f"{type(ex).__name__}: {ex}\n" + traceback.format_exc()[-1500:] if not os.environ.get("IQ_FULL_TB") else traceback.format_exc()
    elapsed = time.perf_counter() - t0

    res = []
    for ln, ents in sorted(ca.analysis_per_line.items()):
        for en in ents:
            if en.get("type") in ("during_intent", "post_intent"):
                r = en.get("result", {})
                res.append({"line": ln, "type": en["type"], "status": r.get("status")})
    for ln, ents in sorted(ca.recorder.ledger.items()):
        for en in ents:
            if en.get("kind") == "verification":
                res.append({"line": ln, "type": en.get("verification_type"), "status": en.get("status")})
    return {"results": res, "runs": runs, "error": err, "elapsed_s": round(elapsed, 3)}


def main_cli():
    ap = argparse.ArgumentParser()
    ap.add_argument("--one")
    ap.add_argument("--only")
    ap.add_argument("--tag", default="p0")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--rebuilt", action="store_true")
    a = ap.parse_args()
    if a.one:
        print("@@JSON@@" + json.dumps(run_one(pathlib.Path(a.one)), ensure_ascii=False))
        return
    rows = [r for r in csv.DictReader(open(DS / "cases74.csv", encoding="utf-8")) if r["expressible"] == "Yes"]
    sys.path.insert(0, str(DS))
    from reassemble import project_key
    out = {}
    for r in rows:
        cid = r["case_id"]
        if a.only and cid != a.only:
            continue
        p = (IV / "cases_rebuilt" / f"{cid}.json") if a.rebuilt else rc.case_path(cid)
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        if a.rebuilt:
            env["IQ_DEPS_ROOT"] = str(DS / "deps" / project_key(r))
            env["IQ_DEPS_EXCLUDE"] = ",".join(rc.declared_names(DS / "target_contraction_auto" / f"{cid}.sol"))
        if not p.exists():
            out[cid] = {"error": f"case file missing: {p}"}
            continue
        try:
            proc = subprocess.run([str(PY), __file__, "--one", str(p)], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=a.timeout, cwd=ROOT, env=env)
            line = next((l for l in proc.stdout.splitlines() if l.startswith("@@JSON@@")), None)
            d = json.loads(line[8:]) if line else {"error": "no result line", "stderr": proc.stderr[-1500:]}
        except subprocess.TimeoutExpired:
            d = {"error": f"timeout {a.timeout}s"}
        d["verdict"] = rc.verdict(d.get("results", []))
        out[cid] = d
        e = (" ERR " + d["error"].splitlines()[0][:80]) if d.get("error") else ""
        print(f"{cid:<34} {d['verdict']:<12} runs={len(d.get('runs', []))} t={d.get('elapsed_s', '-')}s{e}", flush=True)
    OUT.mkdir(exist_ok=True)
    rp = OUT / f"{a.tag}_{'rebuilt' if a.rebuilt else 'legacy'}.json"
    if a.only and rp.exists():
        merged = json.loads(rp.read_text(encoding="utf-8")); merged.update(out); out = merged
    rp.write_text(json.dumps(out, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    from collections import Counter
    print("\nverdicts:", dict(Counter(v.get("verdict") for v in out.values())), "->", rp)


if __name__ == "__main__":
    main_cli()
