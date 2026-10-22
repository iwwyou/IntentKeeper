# -*- coding: utf-8 -*-
"""
Intent validation (새 RQ3) — expressible 48 케이스를 **현재 엔진**으로 다시 돌린다.

케이스 파일(evaluation/RQ1/cases/**)은 decision #37 이전 문법(`// @…`)과 `@LocalVar`(2026-10-20 `@Param` 으로 대체)를
그대로 갖고 있다. 파일은 고치지 않고 이 드라이버가 투입 직전에 변환한다(사용자 승인 2026-10-20):
  - 어노테이션 앞의 `//` 제거 (intentUnit 문법은 `@…` 로 시작)
  - `@LocalVar` → `@Param`
`// @Debugging BEGIN/END` 는 배치 경계 표식으로만 쓴다(파싱 대상 아님).

케이스마다 **새 프로세스**에서 돈다 — main.py 의 sa/contract_analyzer/batch_mgr 가 모듈 전역 싱글턴이라
같은 프로세스에서 두 케이스를 돌리면 상태가 섞인다.

판정 집계(케이스 단위): Violated 가 하나라도 있으면 Violated > Warning > Unreachable > Satisfied.
비교 기준 = IntentChecker 결과(Guardian evaluation/RQ2/rq2a_specification_profile.xlsx `validation_outcome`).

사용:
  .venv/Scripts/python.exe evaluation/intent_validation/run_cases.py            # 48개 전체 → results_<tag>.json
  .venv/Scripts/python.exe evaluation/intent_validation/run_cases.py --tag before --only web3bugs_5_H_07
  (내부) run_cases.py --one <case.json>   # 한 케이스를 현재 프로세스에서 돌려 JSON 한 줄 출력
"""
import argparse
import contextlib
import csv
import io
import json
import pathlib
import re
import subprocess
import sys
import time
import os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ROOT / "evaluation" / "RQ1" / "cases"
DS = ROOT / "evaluation" / "Dataset"
PY = ROOT / ".venv" / "Scripts" / "python.exe"

# numscout/flyinointment 케이스의 레코드 파일 (Guardian run_all.py 와 같은 경로)
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


def case_path(cid: str) -> pathlib.Path:
    if cid in SPECIAL:
        return CASES / SPECIAL[cid]
    return CASES / cid / f"{cid}.json"            # 정본 = 폴더 안 파일 (상위 cases/<id>.json 은 옛 초안)


def to_current_syntax(code: str) -> str:
    """`// @LocalVar x = …` → `@Param x = …`, `// @During …` → `@During …`."""
    s = code.lstrip()
    if s.startswith("//"):
        s = s[2:].lstrip()
    if s.startswith("@LocalVar"):
        s = "@Param" + s[len("@LocalVar"):]
    return s


def run_one(path: pathlib.Path) -> dict:
    sys.path.insert(0, str(ROOT))
    import os
    os.chdir(ROOT)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        import main                                   # load_dependencies() 가 import 시점에 돈다 (측정 밖)
        from main import sa, contract_analyzer as ca, batch_mgr
        from Utils.Helper import ParserHelpers
        from Utils.YulHelper import YulParserHelpers
        from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
        from Analyzer.EnhancedYulVisitor import EnhancedYulVisitor
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
                if ANN.match(code):
                    text = to_current_syntax(code)
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
        except Exception as ex:                       # 결과로 보고만 한다 — 폴백 없음
            import traceback
            err = f"{type(ex).__name__}: {ex}\n" + traceback.format_exc()[-1500:]
    elapsed = time.perf_counter() - t0
    res = []
    for ln, ents in sorted(ca.analysis_per_line.items()):
        for en in ents:
            if en.get("type") in ("during_intent", "post_intent"):
                r = en.get("result", {})
                res.append({"line": ln, "type": en["type"], "status": r.get("status"),
                            "risk": r.get("risk_score"), "message": str(r.get("message", ""))[:200]})
    for ln, ents in sorted(ca.recorder.ledger.items()):
        for en in ents:
            if en.get("kind") == "verification":
                res.append({"line": ln, "type": en.get("verification_type"), "status": en.get("status"),
                            "risk": None, "message": str(en.get("message", ""))[:200]})
    log = buf.getvalue()
    return {"results": res, "error": err, "elapsed_s": round(elapsed, 3),
            "antlr_errors": len(re.findall(r"mismatched input|extraneous input|no viable alternative", log)),
            "log_tail": log[-800:]}


def verdict(results) -> str:
    st = [str(r["status"] or "").lower() for r in results]
    if not st:
        return "None"
    # 엔진이 만족을 경로에 따라 "satisfied" 또는 "success"(Engine._combine_logic_results, 메시지는 "satisfied")로
    # 낸다 — 같은 판정으로 센다. (엔진 쪽 용어 불일치는 PROGRESS 에 별도 보고)
    for key, name in (("violat", "Violated"), ("warn", "Warning"), ("unreach", "Unreachable"),
                      ("satisf", "Satisfied"), ("success", "Satisfied")):
        if any(key in s for s in st):
            return name
    return "Other:" + ",".join(sorted(set(st)))


def expected():
    p = ROOT.parent / "SolidityGuardian" / "evaluation" / "RQ2" / "rq2a_specification_profile.xlsx"
    import zipfile, html
    z = zipfile.ZipFile(p)
    s = z.read("xl/worksheets/sheet1.xml").decode()
    R = []
    for row in re.findall(r"<row [^>]*>(.*?)</row>", s, re.S):
        R.append({m[0]: html.unescape(re.sub(r"<[^>]+>", "", m[2]))
                  for m in re.findall(r'<c r="([A-Z]+)\d+"[^>]*?(/>|>(.*?)</c>)', row, re.S)})
    h = R[0]
    return {r.get("A"): r.get(next(k for k, v in h.items() if v == "validation_outcome"), "") for r in R[1:]}


def declared_names(sol_path):
    """분석 대상 소스가 스스로 선언하는 contract/library/interface 이름 — 로더가 pkl 판을 올리지 않게."""
    text = re.sub(r"//[^\n]*", "", sol_path.read_text(encoding="utf-8"))
    return sorted(set(re.findall(r"^\s*(?:abstract\s+)?(?:contract|library|interface)\s+(\w+)", text, re.M)))


def main_cli():
    ap = argparse.ArgumentParser()
    ap.add_argument("--one")
    ap.add_argument("--only")
    ap.add_argument("--tag", default="current")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--rebuilt", action="store_true",
                    help="(b) 재구성 케이스(cases_rebuilt/) + 프로젝트 단위 의존성(Dataset/deps/<p>) 사용")
    a = ap.parse_args()
    if a.one:
        print("@@JSON@@" + json.dumps(run_one(pathlib.Path(a.one)), ensure_ascii=False))
        return
    rows = [r for r in csv.DictReader(open(DS / "cases74.csv", encoding="utf-8")) if r["expressible"] == "Yes"]
    sys.path.insert(0, str(DS))
    from reassemble import project_key  # 케이스 → forge 프로젝트 키 (w52, n_WANGMI …)
    exp = expected()
    out = {}
    for r in rows:
        cid = r["case_id"]
        if a.only and cid != a.only:
            continue
        p = (HERE / "cases_rebuilt" / f"{cid}.json") if a.rebuilt else case_path(cid)
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        if a.rebuilt:
            env["IQ_DEPS_ROOT"] = str(DS / "deps" / project_key(r))
            env["IQ_DEPS_EXCLUDE"] = ",".join(declared_names(DS / "target_contraction_auto" / f"{cid}.sol"))
        if not p.exists():
            out[cid] = {"error": f"case file missing: {p}"}
            print(f"{cid:<34} MISSING {p}")
            continue
        try:
            proc = subprocess.run([str(PY), __file__, "--one", str(p)], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=a.timeout, cwd=ROOT, env=env)
            line = next((l for l in proc.stdout.splitlines() if l.startswith("@@JSON@@")), None)
            d = json.loads(line[8:]) if line else {"error": "no result line", "stderr": proc.stderr[-1500:]}
        except subprocess.TimeoutExpired:
            d = {"error": f"timeout {a.timeout}s"}
        d["verdict"] = verdict(d.get("results", []))
        d["expected"] = exp.get(cid, "")
        out[cid] = d
        flag = "" if d["expected"].startswith(d["verdict"]) else "  <-- differs"
        e = (" ERR " + d["error"].splitlines()[0][:80]) if d.get("error") else ""
        print(f"{cid:<34} {d['verdict']:<12} expected={d['expected'][:20]:<20} n={len(d.get('results', []))}"
              f" t={d.get('elapsed_s', '-')}s{e}{flag}", flush=True)
    rp = HERE / f"results_{a.tag}.json"
    if a.only and rp.exists():
        merged = json.loads(rp.read_text(encoding="utf-8")); merged.update(out); out = merged
    rp.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print("\nverdicts:", dict(Counter(v.get("verdict") for v in out.values())))
    print("match expected:", sum(1 for v in out.values() if v.get("expected", "").startswith(v.get("verdict", "?"))), "/", len(out))


if __name__ == "__main__":
    main_cli()
