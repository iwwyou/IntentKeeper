# -*- coding: utf-8 -*-
"""48 expressible 케이스를 **engine_api 경로**(도구와 같은 경로)로 돌린다 (2026-10-22, 사용자 결정 — 평가 드라이버 이전).
케이스마다 새 프로세스. 출력:
  · evaluation/intent_validation/results_api_<tag>.json  (판정·기대값 비교·slot_missing)
  · evaluation/refactor/baseline/<tag>_api.json           (compare.py 용 노드 상태 덤프, 같은 스키마)
사용: .venv/Scripts/python.exe evaluation/intent_validation/run_cases_api.py --tag a0 [--only <case>]
"""
import argparse
import csv
import json
import os
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DS = ROOT / "evaluation" / "Dataset"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(DS))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--one")
    ap.add_argument("--only")
    ap.add_argument("--tag", default="api")
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()
    if a.one:
        import contextlib, io
        import api_driver
        from reassemble import project_key
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = api_driver.run_case(a.one, DS / "deps" / project_key(api_driver.case_row(a.one)))
        print("@@JSON@@" + json.dumps(r, ensure_ascii=False))
        return
    from run_cases import verdict, expected
    rows = [r for r in csv.DictReader(open(DS / "cases74.csv", encoding="utf-8")) if r["expressible"] == "Yes"]
    exp = expected()
    out = {}
    for r in rows:
        cid = r["case_id"]
        if a.only and cid != a.only:
            continue
        try:
            proc = subprocess.run([str(PY), __file__, "--one", cid], capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=a.timeout, cwd=ROOT,
                                  env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            line = next((l for l in proc.stdout.splitlines() if l.startswith("@@JSON@@")), None)
            d = json.loads(line[8:]) if line else {"error": "no result line", "stderr": proc.stderr[-1500:]}
        except subprocess.TimeoutExpired:
            d = {"error": f"timeout {a.timeout}s"}
        d["verdict"] = verdict(d.get("results", []))
        d["expected"] = exp.get(cid, "")
        out[cid] = d
        e = (" ERR " + d["error"].splitlines()[0][:70]) if d.get("error") else ""
        sm = f" slot_missing={len(d.get('slot_missing', []))}" if d.get("slot_missing") else ""
        print(f"{cid:<34} {d['verdict']:<12} expected={d['expected'][:14]:<14} t={d.get('elapsed_s', '-')}s{sm}{e}",
              flush=True)
    for path in (HERE / f"results_api_{a.tag}.json", ROOT / "evaluation" / "refactor" / "baseline" / f"{a.tag}_api.json"):
        prev = json.loads(path.read_text(encoding="utf-8")) if (a.only and path.exists()) else {}
        prev.update(out)
        path.write_text(json.dumps(prev, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    from collections import Counter
    print("\nverdicts:", dict(Counter(v.get("verdict") for v in out.values())))
    print("match expected:", sum(1 for v in out.values() if v.get("expected", "").startswith(v.get("verdict", "?"))),
          "/", len(out))


if __name__ == "__main__":
    main()
