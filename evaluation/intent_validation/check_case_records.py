# -*- coding: utf-8 -*-
"""
케이스 레코드 JSON 정합성 검사 (줄 번호 계산 오류 탐지).

SolidityAnalyzer.update_code/_insert_lines 의 삽입 규칙을 **엔진 없이** 그대로 재현해 최종 소스를 만든다:
  - add: span = endLine-startLine+1 (endLine < startLine 이면 코드 줄 수). start 이상 줄을 span 만큼 민 뒤,
         코드 줄을 span 의 **끝**에 쓰고 앞은 빈 줄로 채운다.
  - closeBefore + `else`/`while`/`catch` 로 시작: start 줄을 재사용(밀기 1 줄 감소) — 엔진은 start 줄에 join 노드가 있을 때만
    이렇게 하므로 근사다.
  - `@During` 인라인(기존 코드 줄에 붙음)은 엔진의 `_is_during_inline` 과 같이 밀지 않는다(근사: 그 줄이 비어 있지 않으면 인라인).
검사 항목:
  R1 코드 줄 수 > span            → 엔진은 span 만큼만 쓰고 나머지를 버린다(코드 유실)
  R2 옛 형식: `}` 로 시작하는 레코드에 closeBefore 없음
  R3 최종 소스 중괄호 불균형
  R4 intent/debug 어노테이션이 타깃 함수 본문 밖에 놓임
  R5 같은 줄에 두 번 쓰기(덮어쓰기)
출력: 케이스별 문제 목록 + (옵션) 최종 소스 덤프
사용: .venv/Scripts/python.exe evaluation/intent_validation/check_case_records.py [--dump <case_id>]
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
from run_cases import case_path  # noqa: E402

ANN = re.compile(r"^\s*//\s*@(\w+)")


def replay(recs):
    lines, problems = {}, []
    closers = set()                              # closeBefore 로 앞 블록의 `}` 를 덮어쓴(=암묵적으로 닫은) 줄
    tags = {}                                    # line -> record index (어노테이션 추적)
    for k, r in enumerate(recs):
        code, s, e, ev = r["code"], r["startLine"], r["endLine"], r["event"]
        if ev != "add":
            problems.append(f"rec#{k} event={ev} (검사기는 add 만 재현)")
            continue
        new = code.split("\n")
        st = code.lstrip()
        if st.startswith("}") and not r.get("closeBefore") and len(st) > 1:
            problems.append(f"R2 rec#{k} L{s}: 옛 형식 '}}…' 에 closeBefore 없음: {code.splitlines()[0][:60]!r}")
        is_during = bool(re.match(r"\s*//\s*@During", code))
        if is_during and lines.get(s, "").strip():
            tags.setdefault(s, []).append((k, code.strip()))
            continue
        span = e - s + 1 if e >= s else len(new)
        if len(new) > span and any(x.strip() for x in new[span:] + new[:len(new) - span]):
            problems.append(f"R1 rec#{k} L{s}-{e}: 코드 {len(new)}줄 > span {span} (뒤 {len(new) - span}줄 유실): {new[-1][:50]!r}")
        # 엔진(_insert_lines)은 start 줄에 앞 블록의 닫힘(join 노드)이 있을 때만 그 줄을 재사용한다.
        # 그 줄이 `}` 가 아니면(예: 주석이 지워져 빈 줄이 끼어든 경우, WANGMI) 덮어쓰지 않고 새로 넣는다.
        reuse = bool(r.get("closeBefore")) and st.startswith(("else", "while", "catch", "}")) \
            and lines.get(s, "").strip() == "}"
        shift_from, off = (s + 1, span - 1) if reuse else (s, span)
        for ln in sorted([x for x in lines if x >= shift_from], reverse=True):
            lines[ln + off] = lines.pop(ln)
        for ln in sorted([x for x in tags if x >= shift_from], reverse=True):
            tags[ln + off] = tags.pop(ln)
        closers = {(c + off if c >= shift_from else c) for c in closers}
        # 코드는 span 의 끝에 써진다(ws). ws == s 일 때만 앞 블록의 `}` 줄이 실제로 덮어써진다
        # (WANGMI: span 7·코드 2줄 → `}` 는 그대로 남고 `else if` 는 5줄 아래).
        if reuse and s + span - min(len(new), span) == s:
            closers.add(s)
        wc = min(len(new), span)
        ws = s + span - wc
        for i in range(ws - s):
            lines.setdefault(s + i, "")
        for i in range(wc):
            ln = ws + i
            if lines.get(ln, "").strip() and not reuse:
                problems.append(f"R5 rec#{k}: L{ln} 덮어쓰기 {lines[ln][:40]!r} → {new[i][:40]!r}")
            lines[ln] = new[i]
            if ANN.match(new[i]):
                tags.setdefault(ln, []).append((k, new[i].strip()))
    return lines, tags, problems, closers


def function_spans(lines, closers=()):
    """최종 소스에서 함수 본문 범위 {name: [(head_line, close_line)]} (중괄호 깊이 계산)."""
    keys = sorted(lines)
    spans, stack, depth = {}, [], 0
    for ln in keys:
        t = re.sub(r"//.*", "", lines[ln])
        t = re.sub(r'"(?:\\.|[^"\\])*"', '""', t)
        if ln in closers:                          # 덮어써진 앞 블록의 `}` 를 되살려 센다
            t = "}" + t
        m = re.match(r"\s*(function|modifier)\s+(\w+)|\s*(constructor)\b", t)
        for ch in t:
            if ch == "{":
                depth += 1
                if m:
                    stack.append((m.group(2) or m.group(3), ln, depth))
                    m = None
            elif ch == "}":
                if stack and stack[-1][2] == depth:
                    nm, hl, _ = stack.pop()
                    spans.setdefault(nm, []).append((hl, ln))
                depth -= 1
    return spans, depth


def check(cid, target):
    p = case_path(cid)
    recs = json.loads(p.read_text(encoding="utf-8"))
    lines, tags, problems, closers = replay(recs)
    spans, depth = function_spans(lines, closers)
    if depth != 0:
        problems.append(f"R3 최종 소스 중괄호 불균형 (깊이 {depth})")
    tspans = [sp for t in target.split(";") for sp in spans.get(t, [])]
    if not tspans:
        problems.append(f"R4 타깃 함수 '{target}' 를 최종 소스에서 못 찾음")
    else:
        for ln, items in sorted(tags.items()):
            for k, txt in items:
                kind = ANN.match(txt).group(1)
                if kind == "Debugging":
                    continue
                if not any(h < ln <= c for h, c in tspans):
                    problems.append(f"R4 rec#{k} L{ln} {kind} 가 타깃 '{target}'{tspans} 밖: {txt[:60]!r}")
    return lines, tags, problems, tspans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump")
    a = ap.parse_args()
    rows = [r for r in csv.DictReader(open(ROOT / "evaluation" / "Dataset" / "cases74.csv", encoding="utf-8"))
            if r["expressible"] == "Yes"]
    bad = 0
    for r in rows:
        if a.dump and r["case_id"] != a.dump:
            continue
        lines, tags, problems, tspans = check(r["case_id"], r["function"])
        if a.dump:
            for ln in sorted(lines):
                mark = " <<" if ln in tags else ""
                print(f"{ln:4d} | {lines[ln]}{mark}")
            print("target span:", tspans)
        if problems:
            bad += 1
            print(f"== {r['case_id']} (target {r['function']}, span {tspans})")
            for x in problems:
                print("   ", x)
    if not a.dump:
        print(f"\n문제 있는 케이스: {bad}/{len(rows)}")


if __name__ == "__main__":
    main()
