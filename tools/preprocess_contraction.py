"""
Contraction 전처리 스크립트
- web3bugs .sol 파일에서 import, 주석, constructor, SPDX 라인 제거
- target_contracts_contraction/ 폴더의 web3bugs_*.sol 파일 대상
- dependencies/ 폴더는 건드리지 않음
"""

from __future__ import annotations
import re, pathlib, sys, argparse

# ── 대상 디렉토리 ──
BASE_DIR = pathlib.Path(__file__).parent / "target_contracts_contraction"

# ── 패턴 ──
RE_SPDX       = re.compile(r"^\s*//\s*SPDX-License-Identifier.*$")
RE_IMPORT     = re.compile(r"^\s*import\s+")
RE_PRAGMA     = re.compile(r"^\s*pragma\s+")
RE_STANDALONE = re.compile(r"^\s*(//|/\*\*|\*\s|/\*|\*/)")  # 독립 주석 라인
RE_INLINE_CMT = re.compile(r"\s*(//(?!/\s*@(?:During|Post|StateVar|LocalVar|GlobalVar)).*)$")  # intent annotation은 보존
RE_BLOCK_CMT_SINGLE = re.compile(r"/\*.*?\*/")  # 한 줄 안의 /* ... */


def is_standalone_comment(line: str) -> bool:
    """순수 주석 라인인지 판별 (코드 없이 주석만)"""
    stripped = line.strip()
    if not stripped:
        return False
    # // 또는 /// 로 시작
    if stripped.startswith("//"):
        return True
    # /* 로 시작하는 블록 주석 시작
    if stripped.startswith("/*"):
        return True
    # * 로 시작 (블록 주석 중간)
    if stripped.startswith("*"):
        return True
    return False


def strip_inline_comment(line: str) -> str:
    """코드 뒤의 인라인 주석 제거 (문자열 리터럴 안의 // 는 보존)"""
    # intent annotation 주석은 보존
    stripped = line.strip()
    if re.search(r"//\s*@(During|Post|StateVar|LocalVar|GlobalVar)", line):
        return line

    result = []
    in_string = None  # None, "'", '"'
    i = 0
    while i < len(line):
        ch = line[i]

        # 문자열 리터럴 처리
        if ch in ('"', "'") and in_string is None:
            in_string = ch
            result.append(ch)
            i += 1
            continue
        elif ch == in_string:
            in_string = None
            result.append(ch)
            i += 1
            continue

        if in_string is None:
            # // 발견 → 여기서 잘라냄
            if ch == '/' and i + 1 < len(line) and line[i + 1] == '/':
                break
            # /* 발견 → 같은 줄에 */ 있으면 제거, 없으면 잘라냄
            if ch == '/' and i + 1 < len(line) and line[i + 1] == '*':
                end = line.find("*/", i + 2)
                if end != -1:
                    i = end + 2  # /* ... */ 건너뛰기
                    continue
                else:
                    break

        result.append(ch)
        i += 1

    return "".join(result).rstrip()


def find_constructor_range(lines: list[str]) -> list[tuple[int, int]]:
    """constructor 블록의 시작-끝 인덱스 쌍 반환 (0-based)"""
    ranges = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        # constructor 시작 탐지
        if re.match(r"^\s*constructor\s*[\(\{]", stripped) or stripped == "constructor" or stripped.startswith("constructor "):
            start = i
            # brace 카운트로 블록 끝 찾기
            brace_count = 0
            found_open = False
            j = i
            while j < len(lines):
                for ch in lines[j]:
                    if ch == '{':
                        brace_count += 1
                        found_open = True
                    elif ch == '}':
                        brace_count -= 1
                if found_open and brace_count == 0:
                    ranges.append((start, j))
                    i = j + 1
                    break
                j += 1
            else:
                # 끝까지 못찾으면 그냥 넘어감
                i += 1
        else:
            i += 1
    return ranges


def find_block_comment_ranges(lines: list[str]) -> list[tuple[int, int]]:
    """여러 줄 블록 주석 /* ... */ 의 시작-끝 인덱스 쌍 반환"""
    ranges = []
    i = 0
    in_block = False
    start = 0
    while i < len(lines):
        line = lines[i]
        if not in_block:
            # /* 가 있고 같은 줄에 */ 가 없는 경우 → 멀티라인 블록 주석 시작
            idx = line.find("/*")
            if idx != -1:
                # 문자열 리터럴 안인지 간단 체크 (완벽하진 않지만)
                before = line[:idx]
                if before.count('"') % 2 == 0 and before.count("'") % 2 == 0:
                    end_idx = line.find("*/", idx + 2)
                    if end_idx == -1:
                        # 멀티라인 블록 주석 시작
                        in_block = True
                        start = i
                        # 이 줄에 코드가 /* 앞에 있으면 주석 부분만 제거해야 하지만
                        # 간단하게 독립 주석 라인으로 판단
                        if line[:idx].strip() == "":
                            pass  # 순수 주석 시작 라인
        else:
            if "*/" in line:
                in_block = False
                end_idx = line.find("*/")
                after = line[end_idx + 2:].strip()
                if after == "":
                    ranges.append((start, i))
                else:
                    # */ 뒤에 코드가 있으면 시작~i-1 까지만
                    ranges.append((start, i - 1))
        i += 1
    # 닫히지 않은 블록 주석
    if in_block:
        ranges.append((start, len(lines) - 1))
    return ranges


def remove_bare_scoping_blocks(lines: list[str]) -> list[str]:
    """bare scoping block { } 제거 + 내부 코드 dedent 4칸"""
    result = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        # 단독 '{' 라인 탐지
        if stripped == '{':
            # 이전 비어있지 않은 라인 확인
            prev_line = ""
            for j in range(len(result) - 1, -1, -1):
                if result[j].strip():
                    prev_line = result[j].strip()
                    break

            # 이전 라인이 ';' 또는 ')' + ';' 로 끝나면 bare scoping block
            # (제어문 헤더는 ')' 로 끝나고 ';' 없음, 키워드 단독은 해당 안됨)
            if prev_line.endswith(';') or prev_line.endswith('}'):
                # 매칭되는 '}' 찾기
                brace_indent = len(lines[i]) - len(lines[i].lstrip())
                brace_count = 1
                block_start = i + 1
                block_end = None
                j = i + 1
                while j < len(lines):
                    for ch in lines[j]:
                        if ch == '{':
                            brace_count += 1
                        elif ch == '}':
                            brace_count -= 1
                    if brace_count == 0:
                        block_end = j
                        break
                    j += 1

                if block_end is not None:
                    # 내부 코드 dedent (4 spaces)
                    for k in range(block_start, block_end):
                        line = lines[k]
                        if line.strip() == '':
                            result.append(line)
                            continue
                        line_indent = len(line) - len(line.lstrip())
                        if line_indent >= brace_indent + 4:
                            result.append(' ' * brace_indent + line[brace_indent + 4:])
                        else:
                            result.append(line)
                    i = block_end + 1  # skip closing '}'
                    continue

        result.append(lines[i])
        i += 1

    return result


# ── Solidity 예약어가 파라미터/변수명으로 쓰인 경우 치환 ──
# ANTLR lexer가 'from' 등을 키워드로 인식하여 파서 오류 발생
_RESERVED_AS_PARAM = {'from'}  # 필요 시 추가

def rename_reserved_params(lines: list[str]) -> list[str]:
    """예약어가 식별자(파라미터명, 변수명)로 쓰인 경우 _ prefix 추가.
    1단계: 파라미터 선언에서 예약어 감지 → 치환 대상 확정
    2단계: 전체 파일에서 해당 예약어의 모든 식별자 사용을 일괄 치환
    """
    source = "\n".join(lines)

    for word in _RESERVED_AS_PARAM:
        # 파라미터 선언에서 사용되는지 확인 (type [indexed] from, | type from))
        param_pattern = re.compile(
            rf'\b(?:address|uint\d*|int\d*|bytes\d*|bool|string)\s+(?:indexed\s+)?{word}\s*[,);]'
        )
        if param_pattern.search(source):
            # 단어 경계 기준으로 모든 식별자 위치의 from → _from
            # 단, 문자열 리터럴 안이나 다른 단어의 일부(fromBalance 등)는 제외
            source = re.sub(rf'\b{word}\b', f'_{word}', source)

    return source.split("\n")


def collapse_enum_members(lines: list[str]) -> list[str]:
    """enum 멤버들을 한 줄로 합치기.
    enum Paths {       →  enum Paths {
        VADER,         →      VADER, USDV
        USDV           →  }
    }
    """
    result = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        # enum header 감지: "enum Name {"
        if stripped.startswith('enum ') and stripped.endswith('{'):
            indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
            result.append(lines[i])  # enum header 유지
            i += 1
            # 멤버들 수집
            members = []
            while i < len(lines):
                mstrip = lines[i].strip()
                if mstrip == '}':
                    break
                if mstrip and mstrip != '{':
                    # trailing comma 제거 후 수집
                    members.append(mstrip.rstrip(',').strip())
                i += 1
            # 한 줄로 합쳐서 추가
            if members:
                result.append(f"{indent}    {', '.join(members)}")
            # 닫는 } 추가
            if i < len(lines):
                result.append(lines[i])  # }
                i += 1
        else:
            result.append(lines[i])
            i += 1
    return result


RE_SINGLE_IF_START = re.compile(r"^(\s*)(if\s*)\(")

RE_SINGLE_UNCHECKED = re.compile(
    r"^(\s*)"                    # (1) 들여쓰기
    r"unchecked\s*\{\s*"         # unchecked {
    r"(.+;)\s*\}\s*$"           # (2) statement; }
)


def _find_matching_paren(s: str, open_idx: int) -> int:
    """s[open_idx]는 '(' 여야 함. 괄호 깊이를 세어 매칭되는 ')'의 인덱스 반환."""
    depth = 0
    for i in range(open_idx, len(s)):
        if s[i] == '(':
            depth += 1
        elif s[i] == ')':
            depth -= 1
            if depth == 0:
                return i
    return -1


def _expand_single_line_if(line: str):
    """'if (cond) stmt;' -> ['if (cond) {', '    stmt;', '}'] 형태로 확장.
    괄호 깊이를 직접 세어 if 조건의 닫는 괄호를 찾는다 (greedy regex는
    statement 쪽에 괄호가 있으면 조건의 끝을 잘못 찾아 코드를 깨뜨림 —
    예: 'if (x > 0) result = (a * b) >> 128;' 에서 result=... 안의 ')'를
    조건의 닫는 괄호로 착각하는 문제, PRBMathCommon.exp2()에서 발견).
    """
    m = RE_SINGLE_IF_START.match(line)
    if not m:
        return None
    indent = m.group(1)
    open_idx = len(m.group(0)) - 1  # '(' 위치
    close_idx = _find_matching_paren(line, open_idx)
    if close_idx == -1:
        return None
    condition = line[m.end(2):close_idx + 1]  # "(...)"
    rest = line[close_idx + 1:].strip()
    if not rest.endswith(';') or rest.startswith('{'):
        return None
    return [f"{indent}if {condition} {{", f"{indent}    {rest}", f"{indent}}}"]


# 빈 블록 `{ }` — `{` 가 **먼저** 오고 바로 닫히는 줄만.
#   `function f(...) { }` / `modifier m() {}` / 단독 `{ }`
# ★ `} else {`, `} else if (...) {`, `} catch ... {`, `} while (...)` 는 **절대 제외**.
#   저건 `}` 가 먼저 와서 **이전 블록을 닫는** 것이고, 슬라이서의 `closeBefore`
#   메커니즘이 전담한다(앞의 `}` 를 떼어 closeBefore=True 로 표시). 건드리면 블록 join 이 깨진다.
#   → `(?!\s*\})` 로 `}` 시작 줄을 명시적으로 배제한다.
# ★ `interface X is Y {}` / `contract X {}` / `library X {}` 도 제외.
#   슬라이서가 `{` 로 끝나는 헤더에 **가짜 `}`** 를 붙여 2줄 블록으로 만들기 때문에
#   실제 `}` 와 충돌할 수 있고, 현재 `_empty_blk` 분기로 정상 처리되고 있다.
RE_SINGLE_EMPTY = re.compile(r'^(\s*)(?!\s*\})(?P<head>[^{}]*\{)\s*\}\s*$')
RE_TYPE_DECL = re.compile(r'^\s*(?:abstract\s+)?(?:interface|contract|library)\b')


def _expand_empty_block(line: str):
    """'... { }' -> ['... {', '}'] 로 확장. 대상이 아니면 None.

    ★ 왜 필요한가: `find_function_context` 는 위로 거슬러 올라가며
      "닫힌 만큼 상쇄하고 남은 첫 `{`" 를 찾는데, **한 줄에 `{` 와 `}` 가 같이 있으면**
      `open > 0` 인 순간 곧바로 멈추고 같은 줄의 `close` 를 무시한다.
      그래서 **이미 닫힌 함수**를 "열려 있다" 고 착각하고,
      그 뒤에 오는 상태변수를 함수 내부 문장으로 오분류한다
      (`uint256[44] private __gap;` → ctx=simpleStatement).
    """
    if RE_TYPE_DECL.match(line):
        return None
    m = RE_SINGLE_EMPTY.match(line)
    if not m:
        return None
    indent = m.group(1)
    return [m.group("head").rstrip(), f"{indent}}}"]


# 중괄호 없는 else — `else <stmt>;` (선행 `}` 선택)
# ★ `else {` / `} else {` / `else if (...)` 는 **절대 제외**한다:
#   · `else {` 는 이미 블록이다
#   · `else if` 는 슬라이서의 `interactiveIfElseUnit` 경로가 전담한다
#   `(?!\s*(?:\{|if))` 로 둘을 명시적으로 배제한다.
# 전수 조사(Dependencies + RQ1 + Dataset): 대상 85건, 제외된 `else` 줄 2,500여 건
#   (`} else {` 2051 · `} else if (...) {` 등) — 오탐 0.
RE_SINGLE_ELSE = re.compile(
    r"^(\s*)(\}\s*)?else(?![A-Za-z0-9_])(?!\s*(?:\{|if(?![A-Za-z0-9_])))\s*(?P<stmt>.+;)\s*$")


def _expand_single_line_else(line: str):
    """'else stmt;' -> ['else {', '    stmt;', '}'] 로 확장. 대상이 아니면 None.

    ★ 왜 필요한가: 슬라이서/분류기는 `else` 가 **블록을 여는 것**을 전제한다.
      `else r = ratio << (127 - msb);` 처럼 한 줄에 문장까지 있으면
      `[ANTLR] extraneous input 'else'` 로 파싱이 깨진다(TickMath.sol:129 실측).

    ★ 선행 `}` 는 **그대로 보존한다** — 슬라이서가 `}` 로 시작하고 `else` 를 포함하는
      줄에서 앞의 `}` 를 떼어 `closeBefore=True` 로 표시하는 메커니즘이 있으므로,
      `} else stmt;` 는 `} else {` / `stmt;` / `}` 가 되어야 그 경로를 그대로 탄다.
    """
    m = RE_SINGLE_ELSE.match(line)
    if not m:
        return None
    indent = m.group(1)
    closer = (m.group(2) or "").strip()          # '}' 또는 ''
    stmt = m.group("stmt").strip()
    head = f"{indent}{closer + ' ' if closer else ''}else {{"
    return [head, f"{indent}    {stmt}", f"{indent}}}"]


# ── 일반 정규화: 입력 1개 = statement 1개 (2026-10-22, 의존성 빌드용) ─────────────────────────────
# 위의 패턴별 확장(if/else/unchecked/빈 블록)이 다루지 않는 나머지 형태를 편다:
#   · 한 줄 블록   `if (x) { return false; }` / `modifier m() { _; }` / `} else { a; b; }`
#   · 한 줄 다중 문장 `uint a = f(); uint b = g();`
#   · 중괄호 없는 for/while/else-if 본문 `for (...) x[i] = y;`
# 엔진 슬라이서(`Dependencies.main._one_statement_violation`)는 이런 입력을 오류로 거부한다(타깃은 입력 쪽 책임,
# 의존성은 빌드 시 여기서 정규화). 판정은 문자열 리터럴·라인 주석을 건너뛰고 **괄호 밖** `;` 와 블록 `{}` 만 본다.
# 블록 `{` = 괄호 밖이고 짝 `}` 사이에 괄호 밖 `;` 가 있는 중괄호(호출 옵션 `{value: v}`·struct 리터럴은 `;` 가 없다).
_CTRL_HEAD = re.compile(r"^(?:\}\s*)?(?:else\s+)?(?:if|for|while)\s*\(")


def _scan_top(s: str):
    """(괄호 밖 `;` 위치들, 괄호 밖 `{`→짝 `}` 위치 사전, 주석 시작 위치). 문자열 리터럴은 건너뛴다."""
    semis, braces, stack, depth, q, i = [], {}, [], 0, None, 0
    cut = len(s)
    while i < len(s):
        c = s[i]
        if q:
            if c == "\\":
                i += 2
                continue
            if c == q:
                q = None
        elif c in "\"'":
            q = c
        elif s.startswith("//", i):
            cut = i
            break
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == ";" and depth == 0:
            semis.append(i)
        elif c == "{" and depth == 0:
            stack.append(i)
        elif c == "}" and depth == 0 and stack:
            braces[stack.pop()] = i
        i += 1
    return semis, braces, cut


def _split_one_statement(s: str) -> list[str] | None:
    """한 줄 `s`(들여쓰기 제외)를 '1 줄 = 1 statement' 줄들로. 이미 그 형태면 None. 결과 줄은 상대 들여쓰기(4칸) 포함."""
    s = s.strip()
    semis, braces, cut = _scan_top(s)
    code = s[:cut].rstrip()
    # 중괄호 없는 제어문 본문: `if/for/while (...) stmt;` / `else if (...) stmt;` (do-while 꼬리 `} while (c);` 제외)
    m = _CTRL_HEAD.match(code)
    if m:
        close = _find_matching_paren(code, m.end() - 1)
        rest = code[close + 1:].strip() if close != -1 else ""
        if rest and not rest.startswith("{") and rest != ";":
            body = _split_one_statement(rest) or [rest]
            return [code[:close + 1] + " {"] + ["    " + b for b in body] + ["}"]
    if code.startswith(("else", "} else")) and not re.match(r"^(?:\}\s*)?else\s*(?:\{|if\b)", code):
        rest = re.sub(r"^(?:\}\s*)?else\s*", "", code)
        if rest.endswith(";"):
            head = ("} " if code.startswith("}") else "") + "else {"
            body = _split_one_statement(rest) or [rest]
            return [head] + ["    " + b for b in body] + ["}"]
    # 첫 블록 `{` (본문에 `;` 가 있는 것) 와 첫 `;` 중 앞선 것 기준으로 자른다
    blk = next((o for o, c in sorted(braces.items()) if any(o < p < c for p in semis)), None)
    first_semi = semis[0] if semis else None
    if blk is not None and (first_semi is None or blk < first_semi):
        close = braces[blk]
        head = code[:blk].rstrip() + " {"
        inner = code[blk + 1:close].strip()
        tail = code[close + 1:].strip()
        body = []
        for part in (_split_one_statement(inner) or [inner]):
            body.append("    " + part)
        out = [head] + body
        if tail:
            rest = _split_one_statement(tail) or [tail]
            if tail.startswith(("else", "catch", "while")):
                out.append("} " + rest[0])
                out.extend(rest[1:])
            else:
                out.append("}")
                out.extend(rest)
        else:
            out.append("}")
        return out
    if first_semi is not None and code[first_semi + 1:].strip():
        first = code[:first_semi + 1]
        rest = code[first_semi + 1:].strip()
        return [first] + (_split_one_statement(rest) or [rest])
    return None


def normalize_one_statement_per_line(lines: list[str]) -> list[str]:
    """`_split_one_statement` 를 줄마다 적용(원래 들여쓰기 유지). 문자열 리터럴 줄바꿈이 없는 정규화된 소스 전제."""
    out = []
    for line in lines:
        indent = line[:len(line) - len(line.lstrip())]
        parts = _split_one_statement(line) if line.strip() and not line.strip().startswith("//") else None
        if parts is None:
            out.append(line)
        else:
            out.extend(indent + p for p in parts)
    return out


def expand_single_line_blocks(lines: list[str]) -> list[str]:
    """single-line if/unchecked 블록을 multi-line으로 확장"""
    result = []
    for line in lines:
        expanded_if = _expand_single_line_if(line)
        if expanded_if is not None:
            result.extend(expanded_if)
            continue
        expanded_empty = _expand_empty_block(line)
        if expanded_empty is not None:
            result.extend(expanded_empty)
            continue
        expanded_else = _expand_single_line_else(line)
        if expanded_else is not None:
            result.extend(expanded_else)
            continue
        m_unc = RE_SINGLE_UNCHECKED.match(line)
        if m_unc:
            indent = m_unc.group(1)
            statement = m_unc.group(2)
            result.append(f"{indent}unchecked {{")
            result.append(f"{indent}    {statement}")
            result.append(f"{indent}}}")
        else:
            result.append(line)
    # 패턴별 확장이 다루지 않는 나머지(한 줄 블록·다중 문장·중괄호 없는 for/while)
    return normalize_one_statement_per_line(result)


def collapse_empty_lines(lines: list[str]) -> list[str]:
    """연속 빈 줄을 하나로 축소, 파일 끝 빈 줄 제거"""
    result = []
    prev_empty = False
    for line in lines:
        is_empty = line.strip() == ""
        if is_empty:
            if not prev_empty:
                result.append("")
            prev_empty = True
        else:
            result.append(line)
            prev_empty = False
    # 파일 끝/시작 빈 줄 제거
    while result and result[-1].strip() == "":
        result.pop()
    while result and result[0].strip() == "":
        result.pop(0)
    return result


def preprocess(source: str) -> str:
    """전처리 수행: import, 주석, constructor, SPDX 제거"""
    lines = source.splitlines()

    # 1단계: constructor 범위 표시
    constructor_ranges = find_constructor_range(lines)
    constructor_lines = set()
    for start, end in constructor_ranges:
        for i in range(start, end + 1):
            constructor_lines.add(i)

    # 2단계: 멀티라인 블록 주석 범위 표시
    block_comment_ranges = find_block_comment_ranges(lines)
    block_comment_lines = set()
    for start, end in block_comment_ranges:
        for i in range(start, end + 1):
            block_comment_lines.add(i)

    # 3단계: 한 줄씩 처리
    result = []
    for i, line in enumerate(lines):
        # constructor 블록 → 제거
        if i in constructor_lines:
            continue

        # 멀티라인 블록 주석 → 제거
        if i in block_comment_lines:
            continue

        stripped = line.strip()

        # SPDX → 제거
        if RE_SPDX.match(line):
            continue

        # import → 제거
        if RE_IMPORT.match(stripped):
            continue

        # 독립 주석 라인 → 제거
        if is_standalone_comment(stripped):
            continue

        # 인라인 주석 제거
        processed = strip_inline_comment(line)

        # 빈 줄이 된 경우도 포함 (collapse에서 처리)
        result.append(processed)

    # 4단계: 예약어 파라미터명 치환 (from → _from 등)
    result = rename_reserved_params(result)

    # 5단계: enum 멤버 한 줄로 합치기
    result = collapse_enum_members(result)

    # 6단계: bare scoping block 제거 + dedent
    result = remove_bare_scoping_blocks(result)

    # 7단계: single-line if/unchecked 확장 → multi-line
    result = expand_single_line_blocks(result)

    # 8단계: 빈 줄 정리
    result = collapse_empty_lines(result)

    return "\n".join(result) + "\n"


def process_file(filepath: pathlib.Path, dry_run: bool = False) -> dict:
    """단일 파일 전처리. 통계 반환."""
    original = filepath.read_text(encoding="utf-8")
    original_lines = original.splitlines()
    processed = preprocess(original)
    processed_lines = processed.splitlines()

    stats = {
        "file": filepath.name,
        "original_lines": len(original_lines),
        "processed_lines": len(processed_lines),
        "removed": len(original_lines) - len(processed_lines),
    }

    if not dry_run:
        filepath.write_text(processed, encoding="utf-8")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Contraction 전처리: import/주석/constructor 제거")
    parser.add_argument("--dry-run", action="store_true", help="실제 파일 수정 없이 통계만 출력")
    parser.add_argument("--file", type=str, help="특정 파일만 처리 (e.g., web3bugs_35_H_12.sol)")
    args = parser.parse_args()

    if not BASE_DIR.exists():
        sys.exit(f"디렉토리 없음: {BASE_DIR}")

    if args.file:
        files = [BASE_DIR / args.file]
        if not files[0].exists():
            sys.exit(f"파일 없음: {files[0]}")
    else:
        files = sorted(BASE_DIR.glob("web3bugs_*.sol"))

    if not files:
        sys.exit("처리할 web3bugs_*.sol 파일이 없습니다.")

    print(f"{'파일':<35} {'원본':>6} {'결과':>6} {'제거':>6}")
    print("-" * 60)

    total_original = 0
    total_processed = 0
    for f in files:
        stats = process_file(f, dry_run=args.dry_run)
        total_original += stats["original_lines"]
        total_processed += stats["processed_lines"]
        print(f"{stats['file']:<35} {stats['original_lines']:>6} {stats['processed_lines']:>6} {stats['removed']:>6}")

    print("-" * 60)
    print(f"{'합계':<35} {total_original:>6} {total_processed:>6} {total_original - total_processed:>6}")
    print(f"\n총 {len(files)}개 파일 처리 {'(dry-run)' if args.dry_run else '완료'}")


if __name__ == "__main__":
    main()
