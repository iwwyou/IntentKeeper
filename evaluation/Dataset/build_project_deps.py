# -*- coding: utf-8 -*-
"""
프로젝트 단위 의존성 pkl 빌드 (2026-10-21, 사용자 승인 — 오류 1번 (b) + 상속 복원의 전제).

입력: projects/<p>/out/build-info/*.json 의 source_id_to_path = forge 가 실제로 컴파일한 소스 전체(npm 포함, 조부모까지).
처리:
  1. 각 소스를 IQDebug 가 파싱할 수 있게 전처리 — tools/contraction_target 의 비코드 제거·enum 한 줄·다줄 문장 합치기·
     문법 충돌 식별자 rename·한 줄 블록 전개. **본문 슬라이싱은 하지 않는다**(의존성은 전부 필요할 수 있다).
  2. 최상위 선언(contract/library/interface)을 **선언별 파일**로 나눈다(분석기의 "파일당 주 선언 1개" 규칙).
     파일 수준 정의(pragma·struct·enum·type·using·error·상수)는 각 조각 앞에 그대로 붙인다.
  3. deps/<p>/{interfaces,libraries,contracts}/<Name>.sol 로 쓰고, `Dependencies/main.py --root deps/<p>` 로 pkl 생성
     (deps/<p>/objectfile/). 같은 이름이 내용이 다르게 두 번 나오면 **충돌로 보고**(덮어쓰지 않음).
타깃 파일도 포함한다 — 같은 프로젝트의 다른 케이스가 그것을 의존할 수 있다(w35 Ticks). 케이스 실행 시 로더가
**그 케이스의 타깃 선언만 제외**한다.

출력: deps/<p>/..., deps/<p>/build.log, deps/build_report.json
사용: .venv/Scripts/python.exe evaluation/Dataset/build_project_deps.py [--only w62] [--prep-only]
"""
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DS = pathlib.Path(__file__).resolve().parent
ROOT = DS.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from contraction_target import (strip_noncode, join_multiline_statements, rename_grammar_clashes,  # noqa: E402
                                _mask_strings, _match_brace, _members, _TYPE_DECL, _KEYWORDS)
from preprocess_contraction import (collapse_enum_members, remove_bare_scoping_blocks,  # noqa: E402
                                    expand_single_line_blocks, collapse_empty_lines)

PROJ = DS / "projects"
DEPS = DS / "deps"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
KIND_DIR = {"interface": "interfaces", "library": "libraries", "contract": "contracts"}


def project_sources(pdir: pathlib.Path) -> list[pathlib.Path]:
    seen, out = set(), []
    for bi in sorted((pdir / "out" / "build-info").glob("*.json")):
        d = json.loads(bi.read_text(encoding="utf-8"))
        for p in (d.get("source_id_to_path") or {}).values():
            path = pathlib.Path(p)
            path = (path if path.is_absolute() else pdir / path).resolve()
            if path not in seen:
                seen.add(path)
                out.append(path)
    if not out:
        raise FileNotFoundError(f"{pdir.name}: build-info 없음 — reassemble.py --build 먼저")
    return out


def prep(source: str) -> str:
    lines = strip_noncode(source)
    lines = collapse_enum_members(lines)
    lines = join_multiline_statements(lines)
    text, _ = rename_grammar_clashes("\n".join(lines))
    lines = remove_bare_scoping_blocks(text.splitlines())
    lines = expand_single_line_blocks(lines)
    return reorder_members("\n".join(collapse_empty_lines(lines)) + "\n")


# ── 멤버 재배치 (2026-10-21 사용자 승인: "일단 재배치해서 수행") ─────────────────────────────────
# 분석기는 컨트랙트 본문을 위→아래 한 번에 소비하므로, Solidity 에선 합법인 전방 참조(뒤에 정의된 함수 호출·modifier·
# struct/enum)를 해석하지 못한다. 의존성은 사용자가 편집하는 코드가 아니므로 선언 순서를 바꿔 전방 참조를 없앤다:
#   using → type 별칭 → enum → struct(멤버 타입 기준 위상정렬) → error → event → 상태변수(원래 순서)
#   → modifier·constructor·함수·fallback/receive (내부 호출·modifier 사용 기준 위상정렬, 동률은 원래 순서)
# 자기 재귀(PRBMathSD59x18.exp2 등)는 자기 간선이라 무시한다(재배치로 풀 수 없음 — 엔진 쪽 문제로 별도).
# 서로 다른 노드 사이의 순환(상호 재귀)은 순서를 정할 수 없으므로 폴백 없이 예외로 보고한다.
_MEMBER_GROUPS = ("using", "type", "enum", "struct", "error", "event", "state", "callable")
_DOTTED_CALL = re.compile(r"(?<![\w.])([A-Za-z_]\w*)\s*\(")


def _member_kind(head: str):
    h = head.strip()
    for kw in ("using", "enum", "struct", "error", "event", "modifier"):
        m = re.match(rf"{kw}\b\s*([A-Za-z_]\w*)?", h)
        if m:
            return ("callable", m.group(1)) if kw == "modifier" else (kw, m.group(1))
    m = re.match(r"type\s+([A-Za-z_]\w*)\s+is\b", h)
    if m:
        return "type", m.group(1)
    m = re.match(r"function\s+([A-Za-z_]\w*)", h)
    if m:
        return "callable", m.group(1)
    m = re.match(r"(constructor|fallback|receive)\s*\(", h) or re.match(r"(function)\s*\(", h)
    if m:
        return "callable", f"<{m.group(1)}>"
    return "state", None


def _paren_span(masked: str, i: int) -> int:
    """masked[i] == '(' 의 짝 ')' 인덱스."""
    depth = 0
    for k in range(i, len(masked)):
        depth += masked[k] in "(["
        depth -= masked[k] in ")]"
        if depth == 0:
            return k
    raise ValueError(f"unbalanced paren at {i}")


def _count_args(masked: str, i: int) -> int:
    """masked[i] == '(' 인 호출/파라미터 목록의 최상위 인자 수."""
    j = _paren_span(masked, i)
    inner = masked[i + 1:j]
    if not inner.strip():
        return 0
    depth, n = 0, 1
    for c in inner:
        depth += c in "([{"
        depth -= c in ")]}"
        n += c == "," and depth == 0
    return n


def _after_params(head: str) -> str:
    """함수/modifier 헤더에서 파라미터 목록 뒤(가시성·modifier·returns) 부분."""
    i = head.find("(")
    return head[_paren_span(head, i) + 1:] if i >= 0 else ""


def _callable_key(name: str, masked_member: str) -> str:
    head = masked_member.split("{", 1)[0]
    if re.match(r"\s*modifier\b", head):
        return f"{name}/m"
    i = head.find("(")
    return f"{name}/{_count_args(head, i) if i >= 0 else 0}"


def _topo_stable(names: list[str], edges: dict[str, set[str]], where: str) -> list[str]:
    """names(원래 순서) 를 '의존 대상이 먼저' 로 정렬. 동률은 원래 순서. 순환이면 예외."""
    order, done, visiting = [], set(), []

    def visit(n):
        if n in done:
            return
        if n in visiting:
            cyc = visiting[visiting.index(n):] + [n]
            raise ValueError(f"[reorder] {where}: 서로 다른 이름 사이 호출 순환 — 순서를 정할 수 없음: {' -> '.join(cyc)}")
        visiting.append(n)
        for d in sorted(edges.get(n, ()), key=names.index):
            visit(d)
        visiting.pop()
        done.add(n)
        order.append(n)

    for n in names:
        visit(n)
    return order


def reorder_members(text: str) -> str:
    masked = _mask_strings(text)
    decls = []
    for m in _TYPE_DECL.finditer(masked):
        if any(o < m.start() < c for _, o, c in decls):
            continue
        ob, semi = masked.find("{", m.end()), masked.find(";", m.end())
        if ob < 0 or (0 <= semi < ob):
            continue
        decls.append((m.group(2), ob, _match_brace(masked, ob)))
    out, prev = [], 0
    for cname, ob, cb in decls:
        mems = []                                            # (group, name, src_text, masked_text)
        for s, e in _members(masked, ob + 1, cb):
            g, n = _member_kind(masked[s:e].split("{", 1)[0])
            mems.append((g, n, text[s:e], masked[s:e]))
        by_group = {g: [x for x in mems if x[0] == g] for g in _MEMBER_GROUPS}

        # struct: 멤버 타입으로 다른 struct 를 쓰면 그것이 먼저
        snames = [x[1] for x in by_group["struct"]]
        sedges = {x[1]: {w for w in re.findall(r"\b([A-Za-z_]\w*)\b", x[3].split("{", 1)[1])
                         if w in snames and w != x[1]} for x in by_group["struct"]}
        sorder = _topo_stable(snames, sedges, f"{cname} struct")
        by_group["struct"].sort(key=lambda x: sorder.index(x[1]))

        # callable: 노드 = (이름, 인자 수) — overload 끼리의 호출(SafeMath.sub(a,b) → sub(a,b,msg))도 순서에 반영한다.
        #   간선 = 본문의 비한정 호출(인자 수가 맞는 overload; 맞는 것이 없으면 같은 이름 전부) + 헤더의 modifier 사용.
        #   같은 이름·같은 인자 수(타입만 다른 overload)는 한 노드로 묶여 원래 순서를 유지한다.
        calls = by_group["callable"]
        keys = [_callable_key(x[1], x[3]) for x in calls]
        cnodes = list(dict.fromkeys(keys))
        by_name: dict[str, list[str]] = {}
        for k in cnodes:
            by_name.setdefault(k.split("/")[0], []).append(k)
        cedges = {k: set() for k in cnodes}
        for k, (_, n, _, mt) in zip(keys, calls):
            head, _, body = mt.partition("{")
            for cm in _DOTTED_CALL.finditer(body):
                name = cm.group(1)
                if name in _KEYWORDS or name not in by_name:
                    continue
                exact = f"{name}/{_count_args(body, cm.end() - 1)}"
                cedges[k] |= {exact} if exact in cedges else set(by_name[name])
            for w in re.findall(r"\b([A-Za-z_]\w*)\b", _after_params(head)):
                if f"{w}/m" in cedges:
                    cedges[k].add(f"{w}/m")
            cedges[k].discard(k)
        corder = _topo_stable(cnodes, cedges, f"{cname} function")
        order_of = {id(x): corder.index(k) for k, x in zip(keys, calls)}
        calls.sort(key=lambda x: order_of[id(x)])

        body = "".join(f"\n    {x[2].strip()}\n" for g in _MEMBER_GROUPS for x in by_group[g])
        out.append(text[prev:ob + 1])
        out.append(body)
        prev = cb
    out.append(text[prev:])
    return "".join(out)


def split_decls(text: str):
    """[(kind, name, piece_text)] — 각 piece = 파일 수준 정의 + 그 선언 하나."""
    masked = _mask_strings(text)
    decls = []
    for m in _TYPE_DECL.finditer(masked):
        if any(s <= m.start() < e for _, _, s, e in decls):
            continue
        ob = masked.find("{", m.end())
        semi = masked.find(";", m.end())
        if ob < 0 or (0 <= semi < ob):
            continue
        # 'abstract contract X' 는 abstract 부터
        start = m.start()
        line_start = masked.rfind("\n", 0, start) + 1
        if masked[line_start:start].strip() == "":
            start = line_start
        decls.append((m.group(1), m.group(2), start, _match_brace(masked, ob) + 1))
    prefix_parts, prev = [], 0
    for _, _, s, e in sorted(decls, key=lambda x: x[2]):
        prefix_parts.append(text[prev:s])
        prev = e
    prefix_parts.append(text[prev:])
    file_level = "\n".join(p.strip("\n") for p in prefix_parts if p.strip())
    return [(k, n, (file_level + "\n\n" if file_level else "") + text[s:e] + "\n") for k, n, s, e in decls]


def build(pkey: str, prep_only: bool) -> dict:
    pdir = PROJ / pkey
    out = DEPS / pkey
    if out.exists():
        shutil.rmtree(out)
    for d in KIND_DIR.values():
        (out / d).mkdir(parents=True)
    written, collisions, origin = {}, [], {}
    for src in project_sources(pdir):
        for kind, name, piece in split_decls(prep(src.read_text(encoding="utf-8", errors="replace"))):
            dst = out / KIND_DIR[kind] / f"{name}.sol"
            if name in written:
                if written[name] != piece:
                    collisions.append({"name": name, "first": origin[name], "second": str(src)})
                continue
            written[name] = piece
            origin[name] = str(src)
            dst.write_text(piece, encoding="utf-8")
    rep = {"declarations": len(written), "collisions": collisions,
           "by_kind": {k: len(list((out / d).glob("*.sol"))) for k, d in KIND_DIR.items()}}
    if collisions or prep_only:
        return rep
    proc = subprocess.run([str(PY), str(ROOT / "Dependencies" / "main.py"), "--root", str(out)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT,
                          env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    log = proc.stdout + proc.stderr
    (out / "build.log").write_text(log, encoding="utf-8")
    rep.update({
        "exit": proc.returncode,
        "pkls": len(list((out / "objectfile").glob("*.pkl"))),
        "ERR": len(re.findall(r"\[ERR\]", log)),
        "UPDATE_CODE_ERR": len(re.findall(r"\[UPDATE_CODE ERR\]", log)),
        "ANTLR": len(re.findall(r"mismatched input|extraneous input|no viable alternative", log)),
        "traceback_tail": log[log.rfind("Traceback"):][:600] if "Traceback" in log else "",
    })
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--prep-only", action="store_true")
    ap.add_argument("--skip-done", action="store_true", help="보고서에 이미 exit 가 있는 프로젝트는 건너뜀(중단 후 재개)")
    a = ap.parse_args()
    DEPS.mkdir(exist_ok=True)
    rp = DEPS / "build_report.json"
    report = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else {}
    for pdir in sorted(PROJ.iterdir()):
        if not pdir.is_dir() or (a.only and pdir.name != a.only):
            continue
        if a.skip_done and "exit" in report.get(pdir.name, {}):
            continue
        rep = build(pdir.name, a.prep_only)
        report[pdir.name] = rep
        rp.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")   # 프로젝트마다 저장
        flag = f" COLLISION {[c['name'] for c in rep['collisions']]}" if rep["collisions"] else ""
        print(f"{pdir.name:<18} decls={rep['declarations']:3d} {rep['by_kind']} pkls={rep.get('pkls', '-')} "
              f"ERR={rep.get('ERR', '-')} UPD={rep.get('UPDATE_CODE_ERR', '-')} ANTLR={rep.get('ANTLR', '-')} "
              f"exit={rep.get('exit', '-')}{flag}", flush=True)
    rp.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
