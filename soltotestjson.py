# split_solidity_to_inputs.py  (patch)

from __future__ import annotations
import re, json, sys, argparse, pathlib
from typing import List, Dict

# ── 패턴 ──────────────────────────────────────────────────────────────
_only_ws   = re.compile(r"^\s*$")          # 공백/탭 뿐
_open_blk  = re.compile(r"\{\s*$")         # … {
_empty_blk = re.compile(r"\{\s*\}\s*$")   # … {}  (empty block body)
_one_liner = re.compile(r";\s*$")          # … ;
_only_clo  = re.compile(r"^\s*}\s*$")      # }
_comment   = re.compile(r"^\s*//")          # // 주석

def slice_solidity(source: str) -> List[Dict[str, str | int]]:
    """
    (1) 세미콜론 한 줄
    (2) 헤더 + ‘}’ 를 같은 청크로 갖는 1-line-block
    (3) 완전히 빈 줄
    위 3종만 생성하며, 독립적인 ‘}’ 는 JSON으로 **내보내지 않는다.**
    """
    lines: List[str] = source.splitlines()
    inputs: List[Dict[str, str | int]] = []

    cur_line = 1        # 실제 소스 라인 번호 (1-based)
    i = 0               # lines[] 인덱스

    while i < len(lines):
        raw = lines[i]
        txt = raw.rstrip()                # 우측 공백 제거
        txt = txt.lstrip()                # 좌측 들여쓰기 제거

        # 1) 빈 줄 ──────────────────────────────────────────────
        if _only_ws.match(raw):
            inputs.append({"code": "\n", "startLine": cur_line, "endLine": cur_line, "event": "add"})
            cur_line += 1
            i += 1
            continue

        # 2) 단독 '}'  ── JSON으로는 내보내지 않고 라인만 소비 ──
        if _only_clo.match(txt):
            cur_line += 1
            i += 1
            continue

        # 2.3) '} else/catch/while ...' 패턴 ── 앞의 '}'를 분리하고 나머지만 처리 ──
        close_before = False
        if txt.startswith('}') and ('else' in txt or 'catch' in txt or 'while' in txt):
            txt = txt[1:].strip()   # '}' 제거 → 'else if(...) {' 또는 'else {' 등
            close_before = True

        # 2.5) 주석 라인 ── 별도 청크로 처리 ──
        if _comment.match(raw):
            rec = {"code": txt, "startLine": cur_line, "endLine": cur_line, "event": "add"}
            if close_before: rec["closeBefore"] = True
            inputs.append(rec)
            cur_line += 1
            i += 1
            continue

        # 3-pre) '{}' 로 끝나는 empty block ── 그 자체로 완결된 레코드 ──
        if _empty_blk.search(txt):
            rec = {"code": txt, "startLine": cur_line, "endLine": cur_line, "event": "add"}
            if close_before: rec["closeBefore"] = True
            inputs.append(rec)
            cur_line += 1
            i += 1
            continue

        # 3) '{' 로 끝나는 헤더 줄  ──────────────────────────────
        if _open_blk.search(txt):
            block_code = f"{txt}\n}}"                    # header + 가짜 닫는 괄호
            rec = {
                "code":      block_code,
                "startLine": cur_line,
                "endLine":   cur_line + 1,                # 헤더+1 ⇒ 2-line block
                "event": "add"
            }
            if close_before: rec["closeBefore"] = True
            inputs.append(rec)
            cur_line += 1        # ※ 실제 소스엔 닫는 '}' 가 없으므로 +1만
            i += 1
            continue

        # 4) 세미콜론으로 끝나는 한 줄 문장  ─────────────────────
        if _one_liner.search(txt):
            rec = {"code": txt, "startLine": cur_line, "endLine": cur_line, "event": "add"}
            if close_before: rec["closeBefore"] = True
            inputs.append(rec)
            cur_line += 1
            i += 1
            continue

        # 5) 다중 라인 문장 (세미콜론으로 끝나지 않는 줄) ──────────
        #    세미콜론 또는 '{' 를 만날 때까지 줄들을 누적
        start_line = cur_line
        accumulated = [txt]
        cur_line += 1
        i += 1
        found_block_header = False

        while i < len(lines):
            next_raw = lines[i]
            next_txt = next_raw.strip()

            # 빈 줄이면 건너뛰되 라인 번호는 증가
            if _only_ws.match(next_raw):
                cur_line += 1
                i += 1
                continue

            accumulated.append(next_txt)
            cur_line += 1
            i += 1

            # '{}' 로 끝나면 → empty block, 완결된 레코드
            if _empty_blk.search(next_txt):
                break

            # '{' 로 끝나면 → 블록 헤더로 처리 (body는 별도 레코드)
            if _open_blk.search(next_txt):
                found_block_header = True
                break

            # 세미콜론으로 끝나면 다중 라인 문장 종료
            if _one_liner.search(next_txt):
                break

        if found_block_header:
            # 블록 헤더: header + 가짜 닫는 괄호
            merged_code = " ".join(accumulated)
            block_code = f"{merged_code}\n}}"
            rec = {
                "code":      block_code,
                "startLine": start_line,
                "endLine":   cur_line,       # header 끝 라인 + 1 (가짜 })
                "event": "add"
            }
            if close_before: rec["closeBefore"] = True
            inputs.append(rec)
        else:
            # 일반 다중 라인 문장 (세미콜론으로 종료)
            merged_code = " ".join(accumulated)
            rec = {
                "code": merged_code,
                "startLine": start_line,
                "endLine": cur_line - 1,
                "event": "add"
            }
            if close_before: rec["closeBefore"] = True
            inputs.append(rec)
        continue

    return inputs


# ─────────────── CLI entry ───────────────
if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Split a Solidity file into websocket-server input chunks (JSON).")
    p.add_argument("solidity_file")
    p.add_argument("-o", "--output")
    args = p.parse_args()

    try:
        src = pathlib.Path(args.solidity_file).read_text(encoding="utf-8")
    except FileNotFoundError:
        sys.exit(f"✖ File not found: {args.solidity_file}")

    try:
        chunks = slice_solidity(src)
    except ValueError as e:
        sys.exit(f"✖ Parsing error: {e}")

    json_str = json.dumps(chunks, indent=2, ensure_ascii=False)
    if args.output:
        pathlib.Path(args.output).write_text(json_str, encoding="utf-8")
        print(f"✓ JSON written to {args.output}")
    else:
        print(json_str)
