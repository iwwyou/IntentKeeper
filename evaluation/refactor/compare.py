# -*- coding: utf-8 -*-
"""
기준선 비교 — baseline_cases / micro_cases 덤프 두 개를 비교해 케이스별 차이를 요약한다.

  .venv/Scripts/python.exe evaluation/refactor/compare.py baseline/p0_legacy.json baseline/p1a_legacy.json
  .venv/Scripts/python.exe evaluation/refactor/compare.py baseline/micro_p0.json baseline/micro_p1a.json [-v]
"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = pathlib.Path(__file__).resolve().parent


def load(p):
    p = pathlib.Path(p)
    if not p.is_absolute():
        p = HERE / p
    return json.loads(p.read_text(encoding="utf-8"))


def node_diff(a: dict, b: dict):
    """{node: {state...}} 두 개 → 변경 목록."""
    out = []
    for n in sorted(set(a) | set(b)):
        if n not in a:
            out.append(f"+node {n}")
            continue
        if n not in b:
            out.append(f"-node {n}")
            continue
        sa, sb = a[n].get("state", {}), b[n].get("state", {})
        for k in sorted(set(sa) | set(sb)):
            if sa.get(k) != sb.get(k):
                out.append(f"{n}.{k}: {sa.get(k)} -> {sb.get(k)}")
    return out


def main():
    a, b = load(sys.argv[1]), load(sys.argv[2])
    verbose = "-v" in sys.argv
    same = 0
    for cid in sorted(set(a) | set(b)):
        x, y = a.get(cid, {}), b.get(cid, {})
        lines = []
        if x.get("verdict") != y.get("verdict"):
            lines.append(f"verdict {x.get('verdict')} -> {y.get('verdict')}")
        import re as _re
        _norm = lambda s: [_re.sub(r"0x[0-9A-Fa-f]+", "0x?", l) for l in (s or "").splitlines()[:1]]
        ex, ey = _norm(x.get("error")), _norm(y.get("error"))
        if ex != ey:
            lines.append(f"error {ex} -> {ey}")
        if [r.get("status") for r in x.get("results", [])] != [r.get("status") for r in y.get("results", [])]:
            lines.append(f"results {[r.get('status') for r in x.get('results', [])]} -> "
                         f"{[r.get('status') for r in y.get('results', [])]}")
        if x.get("verdicts") != y.get("verdicts"):
            lines.append(f"verdicts {x.get('verdicts')} -> {y.get('verdicts')}")
        # baseline_cases: runs[i].nodes / micro: states
        rx, ry = x.get("runs"), y.get("runs")
        if rx is not None or ry is not None:
            rx, ry = rx or [], ry or []
            if len(rx) != len(ry):
                lines.append(f"runs {len(rx)} -> {len(ry)}")
            for i, (p, q) in enumerate(zip(rx, ry)):
                d = node_diff(p.get("nodes", {}), q.get("nodes", {}))
                if d:
                    lines.append(f"run{i}: {len(d)} state diffs" + ("" if not verbose else "\n      " + "\n      ".join(d[:40])))
                if p.get("slots") != q.get("slots"):
                    lines.append(f"run{i}: slots {sorted(set(p.get('slots', [])) ^ set(q.get('slots', [])))}")
                if p.get("return_vals") != q.get("return_vals"):
                    lines.append(f"run{i}: return_vals {p.get('return_vals')} -> {q.get('return_vals')}")
        if "states" in x or "states" in y:
            d = node_diff(x.get("states", {}), y.get("states", {}))
            if d:
                lines.append(f"{len(d)} state diffs" + ("" if not verbose else "\n      " + "\n      ".join(d[:40])))
        if "A_equal" in x or "A_equal" in y:
            if x.get("A_equal") != y.get("A_equal"):
                lines.append(f"A_equal {x.get('A_equal')} -> {y.get('A_equal')}")
        if lines:
            print(f"## {cid}")
            for l in lines:
                print("   ", l)
        else:
            same += 1
    print(f"\nidentical: {same} / {len(set(a) | set(b))}")
    ta = sum(v.get("elapsed_s") or 0 for v in a.values())
    tb = sum(v.get("elapsed_s") or 0 for v in b.values())
    if ta or tb:
        print(f"total elapsed: {ta:.1f}s -> {tb:.1f}s")


if __name__ == "__main__":
    main()
