# -*- coding: utf-8 -*-
"""
타깃 함수 기준 contraction (IntentChecker 의 수동 contraction 을 규칙으로 만든 것).

수동 contraction(기존 48)을 역추적한 결과(PROGRESS §3.1)를 규칙으로 옮겼다:
  1. 비코드 제거      — 기존 preprocess_contraction 과 같은 단계: SPDX/import/주석/constructor 제거
  2. 타깃 슬라이싱    — 타깃 함수에서 출발해 **텍스트로 보이는 호출**(`name(`)과 헤더의 modifier 를 따라간 폐포만 남긴다.
                        함수/modifier 는 폐포에 든 것만, event 는 남은 코드가 `emit` 하는 것만 남긴다.
                        상태변수·struct·enum·using·error·interface 는 모두 남긴다(분석 컨텍스트).
                        receive/fallback 은 제거한다.
  3. enum 멤버 한 줄  — 기존 단계 (문장 합치기보다 먼저: enum 멤버 줄은 `;` 로 끝나지 않는다)
  4. 다줄 문장 합치기 — `;` `{` `}` 로 끝나지 않는 줄을 다음 줄과 합친다. assembly 블록 안은 건드리지 않는다.
  5. 충돌 식별자 rename — intent 문법이 토큰으로 쓰는데 Solidity 에서는 합법 식별자인 단어(`from`, `array`, `Exit` …)를
                        파일 전체에서 `_` 접두어로 바꾼다(문자열 리터럴 제외). 기존 도구는 `from` 이 **파라미터일 때만** 바꿨다.
                        intent 문법은 동결이라 소스 쪽에서 우회한다(memory: intent-grammar-frozen).
  6. bare scoping 블록 제거, 한 줄 블록 전개, 빈 줄 정리 — 기존 단계

수동본과 다른 점(의도): 수동 작업은 케이스마다 일관되지 않았다(일부는 callee 를 지우고, 일부는 무관 함수를 남김).
이 모듈은 같은 규칙을 모든 케이스에 적용한다 — 재현 가능성이 목적이다.

사용: from tools.contraction_target import contract_for_target
      contract_for_target(source_text, ["burn"])  → str
"""
from __future__ import annotations

import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from preprocess_contraction import (  # noqa: E402  (기존 단계 재사용 — 동작을 바꾸지 않는다)
    find_constructor_range, find_block_comment_ranges, RE_SPDX, RE_IMPORT, is_standalone_comment,
    strip_inline_comment, collapse_enum_members, remove_bare_scoping_blocks, expand_single_line_blocks,
    collapse_empty_lines,
)

# intent 문법(Parser/Solidity.g4)의 리터럴 토큰 중 Solidity 키워드가 아닌 것 = 소스에서 식별자로 쓰이면 lexer 가 토큰으로 잘라
# 파싱이 깨진다. (Solidity 예약어 final/in/of/match/null … 은 원래 식별자로 쓸 수 없으므로 제외)
GRAMMAR_CLASH = ("from", "any", "arg", "array", "ceil", "floor", "changed", "not", "PercentOf",
                 "Before", "After", "Entry", "Exit", "Current", "Assign", "Unchanged", "returnExpression",
                 "symbolicAddress", "symbolicBytes", "symbolicString")

_STR = re.compile(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'')
_TYPE_DECL = re.compile(r"\b(?:abstract\s+)?(contract|library|interface)\s+([A-Za-z_]\w*)")
_CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_EMIT = re.compile(r"\bemit\s+([A-Za-z_]\w*)")
_KEYWORDS = {"if", "for", "while", "require", "assert", "return", "returns", "emit", "revert", "new", "mapping",
             "keccak256", "abi", "address", "payable", "type", "super", "this", "function", "modifier", "event",
             "uint", "int", "bytes", "bool", "string", "catch", "try"}


# ── 1. 비코드 제거 (기존 preprocess 의 1~3 단계와 동일) ─────────────────────────
def strip_noncode(source: str) -> list[str]:
    lines = source.splitlines()
    drop = set()
    for s, e in find_constructor_range(lines):
        drop.update(range(s, e + 1))
    for s, e in find_block_comment_ranges(lines):
        drop.update(range(s, e + 1))
    out = []
    for i, line in enumerate(lines):
        if i in drop or RE_SPDX.match(line):
            continue
        st = line.strip()
        if RE_IMPORT.match(st) or is_standalone_comment(st):
            continue
        out.append(strip_inline_comment(line))
    return out


# ── 2. 슬라이싱 ───────────────────────────────────────────────────────────
def _mask_strings(text: str) -> str:
    """문자열 리터럴을 같은 길이의 공백으로 가린다(괄호·중괄호 계산과 식별자 검색에서 제외하려고)."""
    return _STR.sub(lambda m: m.group(0)[0] + " " * (len(m.group(0)) - 2) + m.group(0)[-1], text)


def _match_brace(masked: str, i: int) -> int:
    """masked[i] == '{' 의 짝 '}' 인덱스."""
    depth = 0
    for k in range(i, len(masked)):
        c = masked[k]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return k
    raise ValueError(f"unbalanced brace at {i}")


def _members(masked: str, lo: int, hi: int):
    """컨트랙트 본문 masked[lo:hi] 의 멤버 구간 [(start, end_exclusive)]. 멤버 = 깊이 0 의 `;` 또는 블록 `{…}` 로 끝나는 단위."""
    out, i = [], lo
    while i < hi:
        while i < hi and masked[i].isspace():
            i += 1
        if i >= hi:
            break
        start, paren = i, 0
        while i < hi:
            c = masked[i]
            if c == "(":
                paren += 1
            elif c == ")":
                paren -= 1
            elif c == ";" and paren == 0:
                i += 1
                break
            elif c == "{" and paren == 0:
                i = _match_brace(masked, i) + 1
                break
            i += 1
        out.append((start, i))
    return out


def _classify(head: str):
    h = head.lstrip()
    m = re.match(r"function\s+([A-Za-z_]\w*)", h)
    if m:
        return "function", m.group(1)
    m = re.match(r"modifier\s+([A-Za-z_]\w*)", h)
    if m:
        return "modifier", m.group(1)
    m = re.match(r"event\s+([A-Za-z_]\w*)", h)
    if m:
        return "event", m.group(1)
    if re.match(r"(fallback|receive)\s*\(", h) or re.match(r"function\s*\(", h):
        return "special", None
    return "keep", None


def slice_to_target(text: str, targets: list[str]) -> tuple[str, dict]:
    masked = _mask_strings(text)
    decls = []                                                   # (kind, name, open, close)
    for m in _TYPE_DECL.finditer(masked):
        ob = masked.find("{", m.end())
        semi = masked.find(";", m.end())
        if ob < 0 or (0 <= semi < ob):
            continue
        # 이미 다른 선언 본문 안이면 건너뛴다(최상위만)
        if any(o < m.start() < c for _, _, o, c in decls):
            continue
        decls.append((m.group(1), m.group(2), ob, _match_brace(masked, ob)))

    items = []                                                   # (decl_idx, start, end, kind, name)
    for di, (kind, _, ob, cb) in enumerate(decls):
        for s, e in _members(masked, ob + 1, cb):
            head = masked[s:e].split("{", 1)[0]
            k, n = _classify(head)
            items.append((di, s, e, k, n))

    bodies: dict[str, list[str]] = {}
    for di, s, e, k, n in items:
        if k in ("function", "modifier") and decls[di][0] != "interface":
            bodies.setdefault(n, []).append(masked[s:e])
    modifiers = {n for _, _, _, k, n in items if k == "modifier"}

    seen, work = set(), [t for t in targets if t]
    missing = [t for t in work if t not in bodies]
    while work:
        f = work.pop()
        if f in seen or f not in bodies:
            continue
        seen.add(f)
        for body in bodies[f]:
            for n in _CALL.findall(body):
                if n in bodies and n not in seen and n not in _KEYWORDS:
                    work.append(n)
            head = body.split("{", 1)[0]
            for n in re.findall(r"\b([A-Za-z_]\w*)\b", head):
                if n in modifiers and n not in seen:
                    work.append(n)

    kept_code = " ".join(masked[s:e] for di, s, e, k, n in items if k in ("function", "modifier") and n in seen)
    emitted = set(_EMIT.findall(kept_code))

    drop = []
    for di, s, e, k, n in items:
        if decls[di][0] == "interface":
            continue
        if (k in ("function", "modifier") and n not in seen) or k == "special" or (k == "event" and n not in emitted):
            drop.append((s, e))
    out, prev = [], 0
    for s, e in sorted(drop):
        out.append(text[prev:s])
        prev = e
    out.append(text[prev:])
    info = {"kept_functions": sorted(seen), "missing_targets": missing,
            "dropped": len(drop), "decls": [(k, n) for k, n, _, _ in decls]}
    return "".join(out), info


# ── 4. 다줄 문장 합치기 ─────────────────────────────────────────────────────
def join_multiline_statements(lines: list[str]) -> list[str]:
    """★ `}` 로 시작하는 줄은 **항상 새 줄**이다(앞 버퍼를 먼저 내보낸다) — 슬라이서가 블록 닫힘/closeBefore 를 줄 단위로
    인식하므로 `}` 를 앞 줄에 붙이면 안 된다. enum 본문(멤버 줄은 `;` 로 끝나지 않는다)도 합치지 않는다."""
    out, buf, in_asm, asm_depth, in_enum = [], None, False, 0, False
    for line in lines:
        st = line.strip()
        if in_enum:
            out.append(line)
            if "}" in st:
                in_enum = False
            continue
        if buf is None and re.match(r"enum\s+\w+\s*\{", st) and "}" not in st:
            out.append(line)
            in_enum = True
            continue
        if buf is not None and st.startswith("}"):
            out.append(buf)
            buf = None
        if in_asm:
            out.append(line)
            asm_depth += line.count("{") - line.count("}")
            if asm_depth <= 0:
                in_asm = False
            continue
        if buf is None and re.match(r"assembly\b", st):
            out.append(line)
            asm_depth = line.count("{") - line.count("}")
            in_asm = asm_depth > 0
            continue
        if buf is not None:
            if not st:
                continue
            sep = "" if buf.endswith("(") or buf.endswith("[") or st.startswith((")", "]", ",", ".")) else " "
            buf = buf + sep + st
        else:
            if not st:
                out.append(line)
                continue
            buf = line.rstrip()
        if buf.rstrip().endswith((";", "{", "}")):
            out.append(buf)
            buf = None
    if buf is not None:
        out.append(buf)
    return out


# ── 5. 충돌 식별자 rename ─────────────────────────────────────────────────
_ASM_HEAD = re.compile(r'\bassembly\s*(?:\([^)]*\)\s*)?\{')


def rename_grammar_clashes(text: str) -> tuple[str, dict]:
    masked = _mask_strings(text)
    # (2026-10-22) assembly 블록 안은 건드리지 않는다 — Yul 은 별도 문법(EnhancedYulVisitor)이라 intent 키워드와
    #   충돌하지 않고, `not` 은 Yul **내장 함수**다. 예전엔 `not(0)` 을 `_not(0)` 으로 바꿔 미지원 함수가 되었고
    #   (값 None) PRBMath/FullMath 의 mulDiv 가 `%` 에서 터졌다(16_H_04/06, 35_H_08/10/12).
    asm = []
    for m in _ASM_HEAD.finditer(masked):
        asm.append((m.end() - 1, _match_brace(masked, m.end() - 1)))
    in_asm = lambda pos: any(a <= pos <= b for a, b in asm)
    counts = {}
    spans = []
    for w in GRAMMAR_CLASH:
        for m in re.finditer(rf"(?<![\w$]){w}(?![\w$])", masked):
            if in_asm(m.start()):
                continue
            spans.append((m.start(), m.end(), w))
        n = sum(1 for s in spans if s[2] == w)
        if n:
            counts[w] = n
    out, prev = [], 0
    for s, e, w in sorted(spans):
        out.append(text[prev:s] + "_" + w)
        prev = e
    out.append(text[prev:])
    return "".join(out), counts


_DECL_NAME = re.compile(
    r"^(?:(?:abstract\s+)?(?:contract|library|interface)|struct|enum|error|function)\s+([A-Za-z_]\w*)"
    r"|^type\s+([A-Za-z_]\w*)\s+is\b"
    r"|^[A-Za-z_][\w\s\[\]]*?\bconstant\s+([A-Za-z_]\w*)")
_IDENT = re.compile(r"[A-Za-z_]\w*")


def order_declarations(text: str) -> tuple[str, list[str]]:
    """파일 최상위 선언을 **선언 후 사용** 순서로 재배치한다 (2026-10-22 결정). 반환 (텍스트, 앞으로 옮겨진 선언 이름들).

    IQDebug 는 소스를 한 줄씩 증분 소비하므로, 같은 파일에서 **뒤에 선언된** 라이브러리·interface 등을 앞에서 참조하는 것
    (예: numscout_Nokon 의 `using SafeMath for uint256;` 이 파일 끝의 `library SafeMath` 를 참조)은 도구의 입력 전제 위반이다
    (solc 는 허용 — Solidity 에서 최상위 선언 순서는 의미가 없으므로 재배치는 의미를 바꾸지 않는다).
    원래 순서를 최대한 유지하는 안정 위상정렬. 서로를 참조하는 순환은 순서를 정할 수 없으므로 **예외**(폴백 없음).
    순서가 바뀌지 않으면 텍스트를 그대로 돌려준다(공백 배치 보존).
    """
    masked = _mask_strings(text)
    units = _members(masked, 0, len(masked))
    if len(units) < 2:
        return text, []
    names, refs = [], []
    for s, e in units:
        m = _DECL_NAME.match(masked[s:e])
        names.append(next((g for g in m.groups() if g), None) if m else None)
        refs.append(set(_IDENT.findall(masked[s:e])))
    by_name = {n: i for i, n in enumerate(names) if n}
    deps = [{by_name[r] for r in refs[i] if r in by_name and by_name[r] != i} for i in range(len(units))]
    order, placed = [], set()
    while len(order) < len(units):
        ready = [i for i in range(len(units)) if i not in placed and deps[i] <= placed]
        if not ready:
            cyc = [names[i] or f"#{i}" for i in range(len(units)) if i not in placed]
            raise ValueError(f"order_declarations: 최상위 선언 사이 순환 참조 — 순서를 정할 수 없음: {cyc}")
        order.append(ready[0])
        placed.add(ready[0])
    if order == list(range(len(units))):
        return text, []
    moved = [names[i] or f"#{i}" for k, i in enumerate(order) if any(j < i for j in order[k + 1:])]
    return "\n\n".join(text[units[i][0]:units[i][1]].rstrip() for i in order) + "\n", moved


def contract_for_target(source: str, targets: list[str]) -> tuple[str, dict]:
    lines = strip_noncode(source)
    sliced, info = slice_to_target("\n".join(lines), targets)
    lines = collapse_enum_members(sliced.splitlines())
    lines = join_multiline_statements(lines)
    text, renamed = rename_grammar_clashes("\n".join(lines))
    lines = remove_bare_scoping_blocks(text.splitlines())
    lines = expand_single_line_blocks(lines)
    lines = collapse_empty_lines(lines)
    text, moved = order_declarations("\n".join(lines) + "\n")
    info["renamed"] = renamed
    info["moved_forward"] = moved
    return text, info
