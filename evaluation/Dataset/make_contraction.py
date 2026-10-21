# -*- coding: utf-8 -*-
"""
cases74.csv 의 74 케이스 원본 → 타깃 기반 contraction (tools/contraction_target.py).

출력: evaluation/Dataset/target_contraction_auto/<case_id>.sol   (기존 수동본 target_contraction/ 은 건드리지 않는다)
      evaluation/Dataset/contraction_auto_report.json
  - kept_functions / missing_targets / renamed (충돌 식별자 rename 횟수)
  - manual_functions / set_match : 수동 contraction 이 있는 48 케이스에 대해 남긴 함수 집합 비교
    (수동본 = target_contraction/<id>.sol, 없으면 케이스 레코드 JSON 을 재생해 복원)

사용: .venv/Scripts/python.exe evaluation/Dataset/make_contraction.py [--only <case_id>]
"""
import argparse
import csv
import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DS = pathlib.Path(__file__).resolve().parent
ROOT = DS.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(DS))
sys.path.insert(0, str(ROOT / "evaluation" / "intent_validation"))
from contraction_target import contract_for_target, strip_noncode, _mask_strings  # noqa: E402
from reassemble import load_target, replay_records  # noqa: E402
from run_cases import case_path  # noqa: E402

OUT = DS / "target_contraction_auto"
FN = re.compile(r"\b(?:function|modifier)\s+([A-Za-z_]\w*)\s*\(")


def defined_with_body(src: str) -> set:
    """본문이 있는 function/modifier 이름 집합 (interface 선언 제외)."""
    m = _mask_strings("\n".join(strip_noncode(src)))
    names = set()
    for x in FN.finditer(m):
        j = x.end()
        depth = 1
        while j < len(m) and depth:
            depth += {"(": 1, ")": -1}.get(m[j], 0)
            j += 1
        ob, semi = m.find("{", j), m.find(";", j)
        if ob >= 0 and (semi < 0 or ob < semi):
            names.add(x.group(1))
    return names


def manual_source(cid: str):
    f = DS / "target_contraction" / f"{cid}.sol"
    if f.exists():
        return f.read_text(encoding="utf-8")
    p = case_path(cid)
    if not p.exists():
        return None
    recs = json.loads(p.read_text(encoding="utf-8"))
    return replay_records([r for r in recs if not r["code"].lstrip().startswith("// @")])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    rows = list(csv.DictReader(open(DS / "cases74.csv", encoding="utf-8")))
    report = {}
    for r in rows:
        cid = r["case_id"]
        if a.only and cid != a.only:
            continue
        targets = [t for t in r["function"].split(";") if t]
        text, info = contract_for_target(load_target(r), targets)
        (OUT / f"{cid}.sol").write_text(text, encoding="utf-8")
        man = manual_source(cid) if r["expressible"] == "Yes" else None
        if man is not None:
            mset = defined_with_body(man)
            aset = set(info["kept_functions"])
            info["manual_functions"] = sorted(mset)
            info["set_match"] = mset == aset
            info["auto_only"] = sorted(aset - mset)
            info["manual_only"] = sorted(mset - aset)
        info["lines"] = text.count("\n")
        report[cid] = info
        flag = "" if info.get("set_match", True) else f"  auto_only={info['auto_only'][:5]} manual_only={info['manual_only'][:5]}"
        miss = f"  MISSING_TARGET={info['missing_targets']}" if info["missing_targets"] else ""
        print(f"{cid:<34} kept={len(info['kept_functions']):3d} lines={info['lines']:5d} renamed={info['renamed']}{miss}{flag}")
    rp = DS / "contraction_auto_report.json"
    if a.only and rp.exists():
        merged = json.loads(rp.read_text(encoding="utf-8")); merged.update(report); report = merged
    rp.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    cmp = [v for v in report.values() if "set_match" in v]
    print(f"\n수동본 비교: 함수 집합 일치 {sum(v['set_match'] for v in cmp)}/{len(cmp)}  |  "
          f"타깃 미발견 {sum(1 for v in report.values() if v['missing_targets'])}")


if __name__ == "__main__":
    main()
