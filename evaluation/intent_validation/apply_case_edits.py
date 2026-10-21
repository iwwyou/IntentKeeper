# -*- coding: utf-8 -*-
"""
케이스 레코드 JSON 데이터 결함 수정 (2026-10-21, 사용자 승인). 엔진은 건드리지 않는다.

원본은 evaluation/RQ1/cases/_original_backup/<case_id>.json 에 **처음 한 번만** 백업하고, 항상 백업본에서 다시 만든다
(여러 번 실행해도 결과가 같다). 변경 내역 = evaluation/RQ1/cases/CASE_EDITS.md.

1. web3bugs_16_H_04 rec#37: 옛 슬라이서 형식 `} else if (...) {\n}`(closeBefore 없음)
   → 현재 형식 `else if (...) {\n}` + closeBefore=True. startLine 49 = 그 시점 if 블록의 `}` 줄(재생으로 확인).
2. web3bugs_36_H_02, web3bugs_47_H_02: `@Post` 레코드의 startLine 이 타깃 함수가 끝난 뒤(컨트랙트 밖)를 가리킴
   → `@Post` 삽입 직전 상태에서 **타깃 함수의 닫는 `}` 줄**로 옮긴다. 그 줄에 add 하면 `}` 가 한 줄 밀리고
   `@Post` 는 함수 본문의 마지막 줄이 된다.
"""
import csv
import json
import pathlib
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from check_case_records import replay, function_spans  # noqa: E402
from run_cases import case_path  # noqa: E402

BACKUP = ROOT / "evaluation" / "RQ1" / "cases" / "_original_backup"
TARGET = {r["case_id"]: r["function"] for r in csv.DictReader(open(ROOT / "evaluation" / "Dataset" / "cases74.csv", encoding="utf-8"))}


def load_original(cid):
    BACKUP.mkdir(exist_ok=True)
    b = BACKUP / f"{cid}.json"
    if not b.exists():
        shutil.copy2(case_path(cid), b)
    return json.loads(b.read_text(encoding="utf-8"))


def fix_16_H_04(recs):
    r = recs[37]
    assert r["code"].startswith("} else if (trade.side == Perpetuals.Side.Short)"), r["code"]
    lines, _, _, _ = replay(recs[:37])
    assert lines.get(r["startLine"], "").strip() == "}", lines.get(r["startLine"])
    r["code"] = r["code"][1:].lstrip()
    r["closeBefore"] = True
    return [f"rec#37 L{r['startLine']}-{r['endLine']}: '}} else if …' → 'else if …' + closeBefore=True"]


def move_post_to_target_end(recs, target):
    notes = []
    for k, r in enumerate(recs):
        if not re.match(r"\s*//\s*@Post", r["code"]):
            continue
        lines, _, _, closers = replay(recs[:k])
        spans, _ = function_spans(lines, closers)
        assert spans.get(target), f"target {target} not found before rec#{k}"
        close_ln = spans[target][-1][1]
        notes.append(f"rec#{k} @Post startLine {r['startLine']} → {close_ln} (타깃 '{target}' 닫는 줄)")
        r["startLine"] = r["endLine"] = close_ln
    return notes


EDITS = {
    "web3bugs_16_H_04": lambda recs: fix_16_H_04(recs),
    "web3bugs_36_H_02": lambda recs: move_post_to_target_end(recs, TARGET["web3bugs_36_H_02"]),
    "web3bugs_47_H_02": lambda recs: move_post_to_target_end(recs, TARGET["web3bugs_47_H_02"]),
}


def main():
    log = ["# 케이스 레코드 수정 내역", "",
           "원본 = `_original_backup/<case_id>.json` (수정 전 IntentChecker 판). 생성: `evaluation/intent_validation/apply_case_edits.py`.", ""]
    for cid, fn in EDITS.items():
        recs = load_original(cid)
        notes = fn(recs)
        case_path(cid).write_text(json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
        log.append(f"## {cid} (2026-10-21)")
        log += [f"- {n}" for n in notes]
        log.append("")
        print(cid, notes)
    (ROOT / "evaluation" / "RQ1" / "cases" / "CASE_EDITS.md").write_text("\n".join(log), encoding="utf-8")


if __name__ == "__main__":
    main()
