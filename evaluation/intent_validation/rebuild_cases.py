# -*- coding: utf-8 -*-
"""
(b) 케이스 재구성 (2026-10-21, 사용자 승인): 원본 기반 자동 contraction 위에 기존 IntentChecker 어노테이션을 같은 위치에 다시 얹는다.

왜: IntentChecker 수동 케이스는 부모·interface 일부를 본문에 옮겨 붙이는 식으로 평탄화되어 있었고(예: 52_H_23 의
`using UQ112x112 for uint224` 누락), RQ1 은 원본 기반 contraction 을 쓰므로 두 RQ 의 분석 대상 소스가 달라진다.
기존 케이스는 evaluation/_baseline_intentchecker/ 에 기준선으로 보존돼 있다(비교용).

입력:
  - 소스: evaluation/Dataset/target_contraction_auto/<case>.sol (tools/contraction_target, 타깃 + callee 폐포, 상속 유지)
  - 어노테이션: 기존 케이스 JSON(evaluation/RQ1/cases/…, 2026-10-21 데이터 수정 반영본)
배치 규칙:
  - 디버그 배치(`// @Debugging BEGIN` … `END` 와 그 사이 값): 타깃 함수 헤더 다음 줄부터 원래 순서대로.
  - `@During`: 기존 케이스에서 그 어노테이션이 붙은 문장(인라인 줄)을 공백 무시로 비교해, 새 소스 **타깃 함수 안의**
    같은 문장(같은 등장 순번) 줄에 인라인으로 붙인다. 못 찾거나 모호하면 **실패로 보고**(추측 배치 금지).
  - `@Post`: 타깃 함수의 닫는 `}` 줄(그 줄에 add → `}` 가 밀리고 @Post 가 본문 마지막 줄).
  - 자동 contraction 이 rename 한 식별자(`from`→`_from` …)는 어노테이션 안의 같은 식별자도 바꾼다.
출력: evaluation/intent_validation/cases_rebuilt/<case>.json, rebuild_report.json
사용: .venv/Scripts/python.exe evaluation/intent_validation/rebuild_cases.py [--only <case>]
"""
import argparse
import csv
import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
from check_case_records import replay, function_spans  # noqa: E402
from run_cases import case_path  # noqa: E402
from Dependencies.main import slice_solidity  # noqa: E402

DS = ROOT / "evaluation" / "Dataset"
AUTO = DS / "target_contraction_auto"
OUT = HERE / "cases_rebuilt"
ANN = re.compile(r"^\s*//\s*@(\w+)")


def norm(s):
    return re.sub(r"\s+", "", s)


def code_lines_in(lines, span):
    h, c = span
    return [(ln, lines[ln]) for ln in sorted(lines) if h < ln < c and lines[ln].strip()
            and not ANN.match(lines[ln])]


def anchor_of_during(orig_recs, k, target):
    """기존 케이스에서 rec#k(@During)가 붙은 문장의 (정규화 텍스트, 타깃 함수 안 같은 텍스트 중 순번)."""
    lines, tags, _, cl = replay(orig_recs[:k + 1])
    ln = next((l for l, items in tags.items() for kk, _ in items if kk == k), None)
    if ln is None:
        return None, "기존 케이스에서 @During 위치를 재생하지 못함"
    code = lines.get(ln, "")
    if not code.strip() or ANN.match(code):
        # 별도 줄 @During: 엔진은 `_find_prev_cfg_node` 로 **바로 앞에서 CFG 노드가 있는 줄**에 붙인다
        # → 그 앞 코드 줄에 인라인으로 붙이는 것과 같은 노드다. 가장 가까운 앞 코드 줄을 앵커로 삼는다.
        prev = next((l for l in range(ln - 1, 0, -1)
                     if lines.get(l, "").strip() and not ANN.match(lines.get(l, ""))), None)
        if prev is None:
            return None, f"별도 줄 @During(L{ln}) 앞에 코드 줄이 없음"
        ln, code = prev, lines[prev]
    spans, _ = function_spans(lines, cl)
    sp = next((s for s in spans.get(target, []) if s[0] <= ln < s[1]), None)
    if sp is None:
        return None, f"@During L{ln} 이 기존 케이스의 타깃 '{target}' 본문 밖"
    cand = [(l, c) for l, c in code_lines_in(lines, sp)] + ([(sp[0], lines[sp[0]])] if ln == sp[0] else [])
    same = [l for l, c in sorted(cand) if norm(c) == norm(code)]
    return (norm(code), same.index(ln)), None


def contract_span(lines, contract):
    """`contract|library|abstract contract|interface <contract> … {` 의 (헤더 줄, 닫는 줄). 없으면 None."""
    # 범위 = 그 선언 헤더 ~ 다음 최상위 선언 헤더 직전 (함수 소속 판정에는 이것으로 충분하고,
    # 문자열 안 중괄호에 흔들리는 중괄호 세기보다 견고하다)
    top = re.compile(r"^\s*(?:abstract\s+)?(?:contract|library|interface)\s+(\w+)\b")
    keys = sorted(lines)
    heads = [(ln, top.match(lines[ln]).group(1)) for ln in keys if top.match(lines[ln])]
    for i, (ln, name) in enumerate(heads):
        if name == contract:
            end = heads[i + 1][0] - 1 if i + 1 < len(heads) else keys[-1]
            return ln, end
    return None


def rebuild(cid, target, renamed, contract=None):
    orig = json.loads(case_path(cid).read_text(encoding="utf-8"))
    src = (AUTO / f"{cid}.sol").read_text(encoding="utf-8")
    recs = slice_solidity(src)

    def ren(text):
        for w in renamed:
            text = re.sub(rf"(?<![\w$]){w}(?![\w$])", f"_{w}", text)
        return text

    batch, durings, posts, problems = [], [], [], []
    for k, r in enumerate(orig):
        m = ANN.match(r["code"])
        if not m:
            continue
        kind = m.group(1)
        if kind in ("Debugging", "StateVar", "LocalVar", "GlobalVar", "IReturn", "Param"):
            batch.append(ren(r["code"]))
        elif kind == "During":
            anc, err = anchor_of_during(orig, k, target)
            if err:
                problems.append(f"rec#{k} {err}")
            else:
                durings.append((anc, ren(r["code"])))
        elif kind == "Post":
            posts.append(ren(r["code"]))
        else:
            problems.append(f"rec#{k} 알 수 없는 어노테이션 {kind}")

    def target_span(rs):
        lines, _, _, cl = replay(rs)
        sp = function_spans(lines, cl)[0].get(target)
        if not sp:
            raise ValueError(f"새 소스에서 타깃 '{target}' 을 찾지 못함")
        if len(sp) > 1 and contract:
            # 평탄화된 원본에 부모의 같은 이름 함수가 함께 있는 경우(WANGMI: ERC20._transfer vs WANGMI._transfer)
            cs = contract_span(lines, contract)
            if cs:
                sp = [s for s in sp if cs[0] < s[0] < cs[1]]
        if len(sp) > 1:
            raise ValueError(f"새 소스에 타깃 '{target}' 이 {len(sp)}개(오버로드) — 어느 것인지 결정 불가")
        return lines, sp[0]

    # 1) @During — 앵커 문장 줄에 인라인 (코드 줄 수가 안 바뀌므로 먼저 넣어도 이후 위치 계산에 영향 없음)
    for (ntext, idx), text in durings:
        lines, sp = target_span(recs)
        same = [l for l, c in code_lines_in(lines, sp) if norm(c) == ntext]
        if len(same) <= idx:
            problems.append(f"@During 앵커 문장을 새 소스 타깃 본문에서 못 찾음({len(same)}개 일치, 순번 {idx}): {text[:60]!r}")
            continue
        ln = same[idx]
        recs.append({"code": text, "startLine": ln, "endLine": ln, "event": "add"})
    # 2) @Post — 타깃 닫는 줄
    for text in posts:
        lines, sp = target_span(recs)
        recs.append({"code": text, "startLine": sp[1], "endLine": sp[1], "event": "add"})
    # 3) 디버그 배치 — 헤더 다음 줄부터
    if batch:
        lines, sp = target_span(recs)
        ln = sp[0] + 1
        for text in batch:
            recs.append({"code": text, "startLine": ln, "endLine": ln, "event": "add"})
            ln += 1
    return recs, problems, {"during": len(durings), "post": len(posts), "batch": len(batch)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    auto_rep = json.loads((DS / "contraction_auto_report.json").read_text(encoding="utf-8"))
    rows = [r for r in csv.DictReader(open(DS / "cases74.csv", encoding="utf-8")) if r["expressible"] == "Yes"]
    report = {}
    for r in rows:
        cid = r["case_id"]
        if a.only and cid != a.only:
            continue
        renamed = list((auto_rep.get(cid, {}).get("renamed") or {}).keys())
        try:
            recs, problems, counts = rebuild(cid, r["function"], renamed, r["contract"])
        except Exception as ex:
            report[cid] = {"error": f"{type(ex).__name__}: {ex}"}
            print(f"{cid:<34} ERROR {ex}")
            continue
        (OUT / f"{cid}.json").write_text(json.dumps(recs, ensure_ascii=False, indent=1), encoding="utf-8")
        report[cid] = {"problems": problems, **counts, "renamed": renamed}
        print(f"{cid:<34} batch={counts['batch']:2d} during={counts['during']} post={counts['post']}"
              + (f"  PROBLEMS {problems}" if problems else ""))
    rp = HERE / "rebuild_report.json"
    if a.only and rp.exists():
        old = json.loads(rp.read_text(encoding="utf-8")); old.update(report); report = old
    rp.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    bad = [c for c, v in report.items() if v.get("error") or v.get("problems")]
    print(f"\n재구성 문제: {len(bad)}/{len(report)}")


if __name__ == "__main__":
    main()
