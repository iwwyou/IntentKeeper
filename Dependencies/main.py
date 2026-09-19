#!/usr/bin/env python3
"""
Dependencies 사전분석 스크립트

libraries/, interfaces/, contracts/ 폴더의 .sol 파일을 분석하여
objectfile/ 에 pkl로 저장한다.

분석 순서:
1. interfaces/ → InterfaceCFG (ifc_*.pkl)
2. libraries/  → LibraryCFG   (lib_*.pkl)
3. contracts/  → ContractCFG  (con_*.pkl)

Usage:
    python Dependencies/main.py                    # 전체 분석
    python Dependencies/main.py --type interfaces  # interface만
    python Dependencies/main.py --type libraries   # library만
    python Dependencies/main.py --file IERC20.sol  # 특정 파일만
"""

import re
import sys
import pathlib
import pickle
import argparse
from typing import List, Dict

# 상위 디렉토리를 sys.path에 추가
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from Analyzer.SolidityAnalyzer import SolidityAnalyzer
from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.EnhancedYulVisitor import EnhancedYulVisitor
from Utils.Helper import ParserHelpers
from Utils.YulHelper import YulParserHelpers

# ── 디렉토리 설정 ──
BASE_DIR    = pathlib.Path(__file__).parent
LIB_DIR     = BASE_DIR / "libraries"
IFC_DIR     = BASE_DIR / "interfaces"
CON_DIR     = BASE_DIR / "contracts"
OBJ_DIR     = BASE_DIR / "objectfile"


# ── soltotestjson 패턴 (soltotestjson.py와 동일) ──
_only_ws   = re.compile(r"^\s*$")
_open_blk  = re.compile(r"\{\s*$")
_empty_blk = re.compile(r"\{\s*\}\s*$")
_one_liner = re.compile(r";\s*$")
_only_clo  = re.compile(r"^\s*}\s*$")
_comment   = re.compile(r"^\s*//")


def slice_solidity(source: str) -> List[Dict]:
    """Solidity 소스를 라인 단위 JSON records로 변환 (soltotestjson.py와 동일)"""
    lines = source.splitlines()
    inputs = []
    cur_line = 1
    i = 0
    in_assembly = 0  # assembly brace depth 추적
    in_enum = False    # enum body 추적

    while i < len(lines):
        raw = lines[i]
        txt = raw.strip()

        # 0-E) enum 내부: 멤버를 } 까지 모아서 한 record로 전달
        if in_enum:
            enum_start = cur_line
            enum_end = cur_line
            collected = []
            while i < len(lines):
                raw2 = lines[i]; txt2 = raw2.strip()
                if _only_ws.match(raw2):
                    cur_line += 1; i += 1; continue
                if '}' in txt2:
                    before_brace = txt2.split('}')[0].strip()
                    if before_brace:
                        collected.extend(m.strip() for m in before_brace.split(',') if m.strip())
                        enum_end = cur_line
                    cur_line += 1; i += 1; break
                collected.extend(m.strip() for m in txt2.split(',') if m.strip())
                enum_end = cur_line
                cur_line += 1; i += 1
            in_enum = False
            if collected:
                inputs.append({"code": ", ".join(collected), "startLine": enum_start, "endLine": enum_start, "event": "add"})
            continue

        # 0) assembly 내부: 줄 단위로 처리 (Yul은 ; 없으므로)
        if in_assembly > 0:
            if _only_ws.match(raw):
                inputs.append({"code": "\n", "startLine": cur_line, "endLine": cur_line, "event": "add"})
                cur_line += 1; i += 1; continue
            if _only_clo.match(txt):
                in_assembly -= 1
                cur_line += 1; i += 1; continue
            # assembly 내 nested { }
            in_assembly += txt.count('{') - txt.count('}')
            if in_assembly < 0:
                in_assembly = 0
            inputs.append({"code": txt, "startLine": cur_line, "endLine": cur_line, "event": "add"})
            cur_line += 1; i += 1; continue

        # 1) 빈 줄
        if _only_ws.match(raw):
            inputs.append({"code": "\n", "startLine": cur_line, "endLine": cur_line, "event": "add"})
            cur_line += 1; i += 1; continue

        # 2) 단독 '}'
        if _only_clo.match(txt):
            cur_line += 1; i += 1; continue

        # 2.3) '} else/catch/while ...' 패턴
        close_before = False
        if txt.startswith('}') and ('else' in txt or 'catch' in txt or 'while' in txt):
            txt = txt[1:].strip()
            close_before = True

        # 2.5) 주석 라인
        if _comment.match(raw):
            rec = {"code": txt, "startLine": cur_line, "endLine": cur_line, "event": "add"}
            if close_before: rec["closeBefore"] = True
            inputs.append(rec)
            cur_line += 1; i += 1; continue

        # 3-pre) '{}' empty block
        if _empty_blk.search(txt):
            rec = {"code": txt, "startLine": cur_line, "endLine": cur_line, "event": "add"}
            if close_before: rec["closeBefore"] = True
            inputs.append(rec)
            cur_line += 1; i += 1; continue

        # 3) '{' 로 끝나는 헤더 줄
        if _open_blk.search(txt):
            block_code = f"{txt}\n}}"
            rec = {"code": block_code, "startLine": cur_line, "endLine": cur_line + 1, "event": "add"}
            if close_before: rec["closeBefore"] = True
            inputs.append(rec)
            # assembly { 진입 시 in_assembly 활성화
            if txt.startswith('assembly'):
                in_assembly = 1
            elif txt.startswith('enum'):
                in_enum = True
            cur_line += 1; i += 1; continue

        # 4) 세미콜론으로 끝나는 한 줄 문장
        if _one_liner.search(txt):
            rec = {"code": txt, "startLine": cur_line, "endLine": cur_line, "event": "add"}
            if close_before: rec["closeBefore"] = True
            inputs.append(rec)
            cur_line += 1; i += 1; continue

        # 5) 다중 라인 문장
        start_line = cur_line
        accumulated = [txt]
        cur_line += 1; i += 1
        found_block_header = False

        while i < len(lines):
            next_raw = lines[i]
            next_txt = next_raw.strip()

            if _only_ws.match(next_raw):
                cur_line += 1; i += 1; continue

            accumulated.append(next_txt)
            cur_line += 1; i += 1

            if _empty_blk.search(next_txt):
                break
            if _open_blk.search(next_txt):
                found_block_header = True
                break
            if _one_liner.search(next_txt):
                break

        if found_block_header:
            merged_code = " ".join(accumulated)
            block_code = f"{merged_code}\n}}"
            rec = {"code": block_code, "startLine": start_line, "endLine": cur_line, "event": "add"}
            if close_before: rec["closeBefore"] = True
            inputs.append(rec)
            if merged_code.strip().startswith('assembly'):
                in_assembly = 1
        else:
            merged_code = " ".join(accumulated)
            rec = {"code": merged_code, "startLine": start_line, "endLine": cur_line - 1, "event": "add"}
            if close_before: rec["closeBefore"] = True
            inputs.append(rec)

    return inputs


def scan_type_aliases(directories: list[pathlib.Path]) -> dict[str, str]:
    """모든 .sol 파일에서 type alias (type X is Y;) 사전 수집"""
    aliases = {}
    _type_re = re.compile(r'type\s+(\w+)\s+is\s+(\w+)\s*;')
    for d in directories:
        if not d.exists():
            continue
        for sol in d.glob("*.sol"):
            source = sol.read_text(encoding='utf-8')
            for alias, underlying in _type_re.findall(source):
                aliases[alias] = underlying
    return aliases


def scan_interface_names(directories: list[pathlib.Path]) -> set[str]:
    """모든 .sol 파일에서 interface 이름 사전 수집"""
    names = set()
    _ifc_re = re.compile(r'interface\s+(\w+)')
    for d in directories:
        if not d.exists():
            continue
        for sol in d.glob("*.sol"):
            source = sol.read_text(encoding='utf-8')
            for name in _ifc_re.findall(source):
                names.add(name)
    return names


def scan_file_level_structs(directories: list[pathlib.Path]) -> dict:
    """모든 .sol 파일에서 file-level struct (contract/library/interface 바깥) 사전 수집.
    반환: { struct_name: StructDefinition }"""
    from Utils.CFG import StructDefinition
    from Domain.Type import SolType

    structs = {}
    for d in directories:
        if not d.exists():
            continue
        for sol in d.glob("*.sol"):
            source = sol.read_text(encoding='utf-8')
            lines = source.splitlines()
            brace_depth = 0
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if brace_depth == 0 and re.match(r'struct\s+(\w+)\s*\{', line):
                    m = re.match(r'struct\s+(\w+)\s*\{', line)
                    struct_name = m.group(1)
                    sd = StructDefinition(struct_name)
                    i += 1
                    while i < len(lines):
                        mline = lines[i].strip()
                        if mline.startswith('}'):
                            break
                        mm = re.match(r'(\w+)\s+(\w+)\s*;', mline)
                        if mm:
                            sol_type = SolType()
                            type_str = mm.group(1)
                            sol_type.typeCategory = "elementary"
                            sol_type.elementaryTypeName = type_str
                            if type_str.startswith("uint"):
                                sol_type.intTypeLength = int(type_str[4:]) if len(type_str) > 4 else 256
                            elif type_str.startswith("int"):
                                sol_type.intTypeLength = int(type_str[3:]) if len(type_str) > 3 else 256
                            sd.add_member(mm.group(2), sol_type)
                        i += 1
                    structs[struct_name] = sd
                else:
                    brace_depth += line.count('{') - line.count('}')
                    if brace_depth < 0:
                        brace_depth = 0
                i += 1
    return structs


def scan_file_level_enums(directories: list[pathlib.Path]) -> dict:
    """모든 .sol 파일에서 file-level enum (contract/library/interface 바깥) 사전 수집.
    반환: { enum_name: [member, ...] }

    ★ `SolidityAnalyzer.file_level_enums` 필드도, 그 소비처(`Evaluation.py`,
      `Refine.py`)도 이미 있었는데 **pkl 생성 경로에만 수집이 없었다**.
      루트 `main.py`(load_dependencies) 와 `engine_api.py` 는 regex 로 수집한다.
      그래서 `enum AssetClass {...}` 처럼 파일 최상위에 선언된 enum(Solidity 0.8+)이
      `interface IMochiProfile { function assetClass(...) returns (AssetClass); }`
      에서 해석되지 않았다(IMochiProfile 2건 · IMochiVault 3건).

    ※ 기존 scan_* 3종은 `d.glob("*.sol")`(비재귀)라 `contracts/112/` 같은 하위
      디렉토리를 놓친다. 이 함수는 `rglob` 을 쓴다 — 기존 3종의 비재귀는 별건으로 남긴다.
    """
    enums: dict[str, list[str]] = {}
    for d in directories:
        if not d.exists():
            continue
        for sol in d.rglob("*.sol"):
            lines = sol.read_text(encoding='utf-8').splitlines()
            brace_depth = 0
            i = 0
            while i < len(lines):
                line = re.sub(r'//.*', '', lines[i]).strip()
                m = re.match(r'enum\s+(\w+)\s*\{', line) if brace_depth == 0 else None
                if m:
                    enum_name = m.group(1)
                    members: list[str] = []
                    rest = line[m.end():]
                    i2 = i
                    buf = [rest]
                    while '}' not in buf[-1] and i2 + 1 < len(lines):
                        i2 += 1
                        buf.append(re.sub(r'//.*', '', lines[i2]))
                    body = " ".join(buf)
                    body = body[:body.index('}')] if '}' in body else body
                    for tok in body.split(','):
                        tok = tok.strip()
                        if re.fullmatch(r'\w+', tok):
                            members.append(tok)
                    if members:
                        enums[enum_name] = members
                    i = i2
                else:
                    brace_depth += line.count('{') - line.count('}')
                    if brace_depth < 0:
                        brace_depth = 0
                i += 1
    return enums


# 전역 사전 등록 (Phase 0에서 수집, analyze_file에서 주입)
_global_type_aliases: dict[str, str] = {}
_global_interface_names: set[str] = set()
_global_library_cfgs: dict = {}  # 이전 분석된 library CFG 누적 (cross-library 호출용)
_global_file_level_structs: dict = {}  # file-level struct 사전 수집
_global_file_level_enums: dict = {}    # file-level enum 사전 수집 (name -> [member,...])

# parent pkl 검색용 패턴 (contract, abstract contract, interface, library)
_is_re = re.compile(r'(?:abstract\s+)?(?:contract|interface|library)\s+\w+\s+is\s+([^{]+)')

# ── 분석 순서 = 위상정렬 (하드코딩 _late/_con_order 대체) ───────────────────
#
# 왜 필요한가: 라이브러리/컨트랙트는 "먼저 분석된 것"만 참조를 해소할 수 있다.
#   * 라이브러리 호출  A.f() : A 의 CFG 가 _global_library_cfgs 에 있어야 함
#   * 상속 `X is A`         : A 의 pkl 이 objectfile 에 있어야 함(_load_parent_pkls)
# 예전엔 Phase 2 가 **알파벳순** + 예외 3개(_late), Phase 3 가 **수동 목록**(_con_order)
# 이었다. 그래서 DyDxMath(D) 가 FullMath(F)/UnsafeMath(U) 보다 먼저 분석돼
#   [ERR] L27 ctx=simpleStatement: This 'UnsafeMath' is may be array or struct but may not be declared
# 로 대입문이 통째로 실패 -> 함수 본문이 빈 채 pkl 로 저장됐다(조용한 오분석).
#
# 실패 시 폴백하지 않는다: 순환 참조나 이름 충돌은 그대로 예외를 던진다.

_decl_re = re.compile(
    r'^[ \t]*(?:abstract[ \t]+)?(library|interface|contract)[ \t]+([A-Za-z_]\w*)', re.M)
_libcall_re = re.compile(r'\b([A-Z]\w*)[ \t]*\.[ \t]*\w+[ \t]*\(')
_using_re = re.compile(r'\busing[ \t]+([A-Za-z_]\w*)[ \t]+for\b')
_MODE_OF = {"library": "library", "interface": "interface", "contract": "contract"}


def _strip_comments(src: str) -> str:
    src = re.sub(r'/\*.*?\*/', ' ', src, flags=re.S)
    return re.sub(r'//[^\n]*', ' ', src)


def _declared_in(src: str) -> list[tuple[str, str]]:
    """파일이 선언하는 (kind, name) 목록. 최상위 선언만."""
    return [(m.group(1), m.group(2)) for m in _decl_re.finditer(_strip_comments(src))]


def _refs_in(src: str) -> set[str]:
    """이 파일이 **먼저 분석돼 있어야** 하는 이름들."""
    t = _strip_comments(src)
    out: set[str] = set()
    for m in _is_re.finditer(t):                       # 상속: X is A, B
        for part in m.group(1).split(','):
            n = part.strip().split('(')[0].strip()
            if n:
                out.add(n)
    out |= {m.group(1) for m in _libcall_re.finditer(t)}   # A.f()
    out |= {m.group(1) for m in _using_re.finditer(t)}     # using A for T
    return out


def _topo_order(files: list[pathlib.Path], label: str) -> list[tuple[pathlib.Path, str]]:
    """(경로, mode) 를 의존 순서대로. 같은 층위는 경로순으로 고정(재현성)."""
    primary: dict[pathlib.Path, tuple[str, str]] = {}
    refs: dict[pathlib.Path, set[str]] = {}
    for f in files:
        src = f.read_text(encoding='utf-8')
        primary[f] = _primary_decl(f, src)      # 규칙 위반이면 여기서 터진다
        # ★ 상속·라이브러리호출·using(_refs_in) 에 더해 **타입 참조**(_type_refs_in)도
        #   의존으로 센다. 그러지 않으면
        #     `contract RoleAware { Roles public immutable roles; ... }`
        #   처럼 상속하지 않고 타입으로만 쓰는 경우 순서가 뒤집힌다
        #   (실측: RoleAware=13 < contracts/Roles.sol=14 → con_Roles.pkl 이 아직 없어
        #    _load_type_ref_pkls 가 로드할 게 없었다 = F19(a) 효과 0의 원인).
        #   순환 위험 때문에 3개 Phase 전수 검증함: interfaces 73 / libraries 32 /
        #   contracts 30 모두 순환 없음, RoleAware 13 -> 23 · Roles.sol 14 -> 13.
        #   ※ `_refs_in` 자체는 건드리지 않는다 — 합집합을 여기서만 만든다.
        refs[f] = _refs_in(src) | _type_refs_in(src)

    # 이름 -> 정의 파일들. **주 선언만** 인덱싱한다 — 보조 선언(예: SafeTransferLib.sol
    # 안의 contract ERC20 스텁)은 실제 정의처가 아니므로 순서 판단에 넣지 않는다.
    # 동명이인은 여전히 존재한다: contracts/Roles.sol vs contracts/112/Roles.sol
    by_name: dict[str, list[pathlib.Path]] = {}
    for f, (_, n) in primary.items():
        by_name.setdefault(n, []).append(f)

    def resolve(name: str, src_file: pathlib.Path) -> pathlib.Path | None:
        cands = by_name.get(name)
        if not cands:
            return None                    # 이 집합 밖(인터페이스/기존 pkl) — 순서 무관
        same = [c for c in cands if c.parent == src_file.parent]
        if len(same) > 1:
            raise ValueError(
                f"[{label}] 이름 '{name}' 이 같은 디렉토리에 여러 번 정의됨 - "
                f"{src_file.name} 에서 결정 불가: {[str(c) for c in same]}")
        if same:
            return None if same[0] == src_file else same[0]
        if len(cands) == 1:
            return None if cands[0] == src_file else cands[0]
        raise ValueError(
            f"[{label}] 이름 '{name}' 이 여러 곳에 정의됨 - {src_file.name} 에서 어느 것을 "
            f"쓰는지 결정 불가: {[str(c) for c in cands]}")

    deps: dict[pathlib.Path, set[pathlib.Path]] = {f: set() for f in files}
    for f in files:
        for n in refs[f]:
            t = resolve(n, f)
            if t is not None:
                deps[f].add(t)

    ordered: list[pathlib.Path] = []
    done: set[pathlib.Path] = set()
    remaining = sorted(files, key=lambda x: str(x))
    while remaining:
        ready = [f for f in remaining if deps[f] <= done]
        if not ready:                      # 순환 - 폴백 없이 터뜨린다
            stuck = {f.name: sorted(d.name for d in deps[f] - done) for f in remaining}
            raise ValueError(f"[{label}] 순환 참조로 순서를 정할 수 없음: {stuck}")
        for f in ready:
            ordered.append(f)
            done.add(f)
        remaining = [f for f in remaining if f not in done]

    return [(f, _MODE_OF[primary[f][0]]) for f in ordered]


def _primary_decl(path: pathlib.Path, src: str) -> tuple[str, str]:
    """이 파일의 **주 선언** (kind, name).

    pkl 이름과 분석 모드를 여기서 정한다. 예전엔 "이번에 새로 생긴 CFG 이름 중
    첫 번째"(`new_libs[0]` 등)를 썼는데, 그건 **분석 순서에 따라 결과가 바뀌는**
    방식이라 위상정렬로 순서를 바로잡자 `SafeTransferLib.sol` 이
    `con_ERC20.pkl (0 functions)` 로 저장되는 회귀가 드러났다.

    판정 규칙 (Dependencies/ 135개 파일 전수 확인 결과에 근거):
      1. 최상위 선언이 **하나면** 그것이 주 선언.
         - 파일명과 달라도 된다: Fixed18.sol->Fixed18Lib, LibPerpetuals.sol->Perpetuals,
           UFixed18.sol->UFixed18Lib, 78_OZ_ERC20.sol->ERC20, solmate_ERC20.sol->ERC20
      2. 여러 개면 **파일명(stem)과 일치하는 것**이 주 선언.
         - 해당 사례: SafeTransferLib.sol = [contract ERC20, library SafeTransferLib]
           -> library SafeTransferLib 이 주 선언, contract ERC20 은 타입 스텁일 뿐이다.
      3. 그래도 못 정하면 **예외**. 폴백해서 엉뚱한 선언을 고르지 않는다
         (그게 위 회귀의 원인이었다).
    """
    ds = _declared_in(src)
    if not ds:
        raise ValueError(f"{path.name}: 최상위 선언(library/interface/contract)을 찾지 못함")
    if len(ds) == 1:
        return ds[0]
    same = [d for d in ds if d[1] == path.stem]
    if len(same) == 1:
        return same[0]
    raise ValueError(
        f"{path.name}: 최상위 선언이 여러 개인데 파일명 '{path.stem}' 과 일치하는 것이 "
        f"{len(same)}개라 주 선언을 결정할 수 없다: {ds}")


# 타입 위치에 등장하는 대문자 식별자 (선언/리턴 위치만 — 함수 호출 `X(` 는 제외)
_typedecl_re = re.compile(
    r'(?m)^\s*([A-Z]\w*)\s+(?:public\s+|private\s+|internal\s+|external\s+|'
    r'immutable\s+|constant\s+|override\s+|memory\s+|storage\s+|calldata\s+)*\w+\s*[;=]')
_typeret_re = re.compile(r'returns\s*\(\s*([A-Z]\w*)\s*[\),]')


def _type_refs_in(src: str) -> set[str]:
    """**타입 위치**에 쓰인 대문자 이름들 (상태변수/지역변수 선언, 리턴 타입).

    ★ `_refs_in` 은 상속·라이브러리호출·using 만 본다. 그래서
      `contract RoleAware { Roles public immutable roles; ... }` 처럼
      **상속하지 않고 타입으로만 쓰는** 경우를 전혀 잡지 못했다.
      그 결과 `RoleAware.sol` 분석 시 `contract_cfgs` 가 비어
      `Type 'Roles' is not defined as struct, enum, or type alias` 가 나고,
      그 한 줄에서 `roles` 를 쓰는 함수 4개가 통째로 빈 채 pkl 로 저장됐다.

    ※ `_refs_in`(위상정렬용)은 **건드리지 않는다** — 거기에 타입 참조를 넣으면
      순환이 생겨 `_topo_order` 가 예외를 던질 수 있다. 여기는 "pkl 을 더 로드"할
      뿐이라 순서 판정과 무관하다.
    """
    t = _strip_comments(src)
    out = {m.group(1) for m in _typedecl_re.finditer(t)}
    out |= {m.group(1) for m in _typeret_re.finditer(t)}
    # 엘리멘터리/키워드 오탐 제거
    out -= {'SPDX', 'True', 'False'}
    return {n for n in out if not n[0].islower()}


def _load_pkl_for(pname: str, ca) -> bool:
    """이름 하나에 대해 pkl 을 찾아 ca.contract_cfgs 에 넣는다. 로드했으면 True.

    ⚠ 후보가 **정확히 1개일 때만** 로드한다. `Controller` 처럼
      `con_112_Controller.pkl` / `con_45_Controller.pkl` 이 공존하는 이름은
      어느 프로젝트 것인지 알 수 없으므로 **조용히 아무거나 집지 않는다**
      (기존 코드는 두 접두를 모두 돌며 나중 것이 이기는 구조였다).
    """
    cands: list[pathlib.Path] = []
    for prefix in ('con_', 'ifc_'):
        cands += list(OBJ_DIR.glob(f'{prefix}*_{pname}.pkl'))
        cands += list(OBJ_DIR.glob(f'{prefix}{pname}.pkl'))
    cands = sorted(set(cands))
    if len(cands) != 1:
        return False
    try:
        with open(cands[0], 'rb') as f:
            raw = pickle.load(f)
    except Exception:
        return False
    ca.contract_cfgs[pname] = raw["cfg"] if isinstance(raw, dict) and "cfg" in raw else raw
    return True


def _load_type_ref_pkls(source: str, ca) -> None:
    """타입으로만 참조되는 contract/interface 의 pkl 을 추가 로드.

    ⚠ 가드 주의: 바로 위(analyze_file)에서
        ca.contract_cfgs.update(_global_library_cfgs)   # 호환성
      로 **라이브러리가 contract_cfgs 에도** 들어간다. 그래서 단순히
      `if pname in ca.contract_cfgs: continue` 로 막으면, 동명의 라이브러리가
      진짜 contract pkl 의 로드를 가로막는다
      (`contracts/Roles.sol`=contract vs `contracts/112/Roles.sol`=library →
       RoleAware.sol 의 `Roles public immutable roles;` 가 계속 실패했다).
      **이미 있는 것이 진짜 contract/interface CFG 일 때만** 건너뛴다.
    """
    from Utils.CFG import LibraryCFG
    for pname in sorted(_type_refs_in(source)):
        cur = ca.contract_cfgs.get(pname)
        if cur is not None and not isinstance(cur, LibraryCFG):
            continue
        _load_pkl_for(pname, ca)


def _load_parent_pkls(source: str, ca) -> None:
    """소스에서 'X is A, B, C' 파싱 → objectfile 에서 **조상** pkl 로드 (전이적).

    ★ docstring 에는 원래 "(재귀)" 라고 써 있었지만 **실제로는 직계 부모만** 로드했다.
      소스의 `X is A, B, C` 를 한 번 파싱하고 A/B/C 만 넣을 뿐, A 의 부모는 보지 않았다.
      실측: Controller.sol 분석 시 contract_cfgs = ['Authorization','IController','Preparable']
      로 **AuthorizationBase 가 빠져** 있었다.
      이제 로드한 조상의 `parent_contracts` 를 따라 워크리스트로 끝까지 훑는다.

    ※ modifier/함수 조회 자체는 `ContractAnalyzer._find_in_ancestors` 가 pkl 에 직렬화된
      `parent_cfgs` 로도 도달하므로, 이 수정은 그것과 **독립적으로** 타입 해석 등
      `contract_cfgs` 를 직접 보는 경로를 위한 것이다.
    """
    m = _is_re.search(source)
    if not m:
        return
    pending = [p.strip().split('(')[0].strip() for p in m.group(1).split(',')]
    seen: set[str] = set()
    while pending:
        pname = pending.pop(0)
        if not pname or pname in seen:
            continue
        seen.add(pname)
        if pname in ca.contract_cfgs:
            # 이미 있어도 그 **조상**은 아직 없을 수 있다
            pending.extend(getattr(ca.contract_cfgs[pname], 'parent_contracts', []) or [])
            continue
        # pkl 검색: con_*.pkl 또는 ifc_*.pkl
        #   ※ 두 접두를 모두 시도하는 기존 동작(둘 다 있으면 나중 것이 이김)을 그대로 둔다.
        for prefix in ('con_', 'ifc_'):
            candidates = list(OBJ_DIR.glob(f'{prefix}*_{pname}.pkl')) + \
                         list(OBJ_DIR.glob(f'{prefix}{pname}.pkl'))
            for pkl_path in candidates:
                try:
                    with open(pkl_path, 'rb') as f:
                        raw = pickle.load(f)
                    if isinstance(raw, dict) and "cfg" in raw:
                        parent_cfg = raw["cfg"]
                    else:
                        parent_cfg = raw
                    ca.contract_cfgs[pname] = parent_cfg
                    break
                except Exception:
                    pass
        if pname in ca.contract_cfgs:
            pending.extend(getattr(ca.contract_cfgs[pname], 'parent_contracts', []) or [])


def analyze_file(sol_path: pathlib.Path, mode: str) -> str | None:
    """
    .sol 파일 사전분석.
    mode: 'library' | 'interface' | 'contract'
    Returns: 저장된 이름 또는 None
    """
    print(f"\n{'='*60}")
    print(f"[{mode}] 분석: {sol_path.name}")
    print(f"{'='*60}")

    source = sol_path.read_text(encoding='utf-8')
    records = slice_solidity(source)
    print(f"  청크: {len(records)}개")

    sa = SolidityAnalyzer()
    ca = sa.contract_analyzer

    # Phase 0에서 수집한 type aliases + interface 이름 + file-level struct 주입
    if _global_type_aliases:
        sa.type_aliases.update(_global_type_aliases)
    if _global_interface_names:
        ca.interface_names.update(_global_interface_names)
    if _global_file_level_structs:
        sa.file_level_structs.update(_global_file_level_structs)
    if _global_file_level_enums:
        sa.file_level_enums.update(_global_file_level_enums)
    # 이전 분석된 library CFG 주입 (cross-library 호출 resolve용)
    _pre_existing_libs = set(_global_library_cfgs.keys())
    if _global_library_cfgs:
        ca.library_cfgs.update(_global_library_cfgs)
        ca.contract_cfgs.update(_global_library_cfgs)  # 호환성
    # parent pkl 로드: 소스에서 'is Parent1, Parent2' 파싱 → pkl 있으면 로드
    _load_parent_pkls(source, ca)
    _load_type_ref_pkls(source, ca)
    _pre_existing_all = set(ca.contract_cfgs.keys()) | set(ca.library_cfgs.keys())

    for rec in records:
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
        close_before = rec.get("closeBefore", False)
        try:
            sa.update_code(s, e, code, ev, close_before)
        except Exception as ex:
            # 진단용 마커 -- 예전엔 여기서 완전히 조용히 삼켰음(원인: 이 실패가
            # 누적되면 해당 함수의 CFG 노드에 statement가 하나도 안 들어간 채
            # pkl로 저장되고, 나중에 그 함수를 호출하면 크래시도 경고도 없이
            # 선언된 리턴변수의 기본값(예: uint160이면 0)을 조용히 반환함 --
            # web3bugs_35_H_10 케이스 빌드 중 TickMath.getSqrtRatioAtTick/
            # DyDxMath.getDx/getDy에서 발견). 동작은 그대로 무시(pass)하되
            # 원인 라인을 보이게 만 한다 -- 전수조사용, 아직 아무 pkl도
            # 이걸로 재생성하지 않았음.
            print(f"  [UPDATE_CODE ERR] L{s}: {ex}")
            pass  # context 분석 실패 시 무시

        stripped = code.strip()
        if stripped and not stripped.startswith("// @"):
            ctx = ca.get_current_context_type()
            try:
                if ctx == "assembly":
                    tree = YulParserHelpers.generate_parse_tree(code)
                    EnhancedYulVisitor(ca).visit(tree)
                else:
                    tree = ParserHelpers.generate_parse_tree(code, ctx, True)
                    EnhancedSolidityVisitor(ca).visit(tree)
            except Exception as ex:
                print(f"  [ERR] L{s} ctx={ctx}: {ex}")

    # ── 결과 추출 + 저장 ──
    OBJ_DIR.mkdir(exist_ok=True, parents=True)

    if mode == "library":
        # pkl 이름 = 파일이 선언한 이름 (순서 의존 제거 — _declared_name 참조)
        _kind, name = _primary_decl(sol_path, source)
        if _kind != "library":
            raise ValueError(
                f"{sol_path.name}: mode='library' 로 분석했는데 주 선언은 "
                f"'{_kind} {name}' 이다 - 분석 순서 판정과 불일치")
        if name not in ca.library_cfgs:
            raise ValueError(
                f"{sol_path.name}: 'library {name}' 을 선언했는데 분석 결과에 없다. "
                f"library_cfgs={sorted(ca.library_cfgs)[:8]}")
        if True:
            cfg = ca.library_cfgs[name]
            parent = sol_path.parent.name
            if parent not in ("libraries", "contracts") and parent.isdigit():
                pkl_name = f"lib_{parent}_{name}.pkl"
            else:
                pkl_name = f"lib_{name}.pkl"
            out = OBJ_DIR / pkl_name
            with open(out, 'wb') as f:
                pickle.dump({"cfg": cfg,
                             "file_level_structs": dict(sa.file_level_structs),
                             "type_aliases": dict(sa.type_aliases)},
                            f, protocol=pickle.HIGHEST_PROTOCOL)
            funcs = list(cfg.functions.keys())
            print(f"  → {pkl_name} ({len(funcs)} functions: {funcs})")
            # cross-library 호출용: 분석 결과를 전역에 누적
            _global_library_cfgs[name] = cfg
            return name

    elif mode == "interface":
        # pkl 이름 = 파일이 선언한 이름 (순서 의존 제거)
        _kind, name = _primary_decl(sol_path, source)
        if _kind != "interface":
            raise ValueError(
                f"{sol_path.name}: mode='interface' 로 분석했는데 주 선언은 "
                f"'{_kind} {name}' 이다 - 분석 순서 판정과 불일치")
        if name not in ca.contract_cfgs:
            raise ValueError(
                f"{sol_path.name}: 'interface {name}' 을 선언했는데 분석 결과에 없다. "
                f"contract_cfgs={sorted(ca.contract_cfgs)[:8]}")
        if True:
            cfg = ca.contract_cfgs[name]
            # 서브폴더(타겟별)의 경우 prefix 추가: ifc_5_iERC20.pkl
            parent = sol_path.parent.name
            if parent not in ("interfaces", "libraries", "contracts") and parent.isdigit():
                pkl_name = f"ifc_{parent}_{name}.pkl"
            else:
                pkl_name = f"ifc_{name}.pkl"
            out = OBJ_DIR / pkl_name
            with open(out, 'wb') as f:
                pickle.dump({"cfg": cfg,
                             "file_level_structs": dict(sa.file_level_structs),
                             "type_aliases": dict(sa.type_aliases)},
                            f, protocol=pickle.HIGHEST_PROTOCOL)
            funcs = list(cfg.functions.keys())
            print(f"  → {pkl_name} ({len(funcs)} functions: {funcs})")
            return name

    elif mode == "contract":
        # pkl 이름 = 파일이 선언한 이름 (순서 의존 제거)
        _kind, name = _primary_decl(sol_path, source)
        if _kind != "contract":
            raise ValueError(
                f"{sol_path.name}: mode='contract' 로 분석했는데 주 선언은 "
                f"'{_kind} {name}' 이다 - 분석 순서 판정과 불일치")
        if name not in ca.contract_cfgs:
            raise ValueError(
                f"{sol_path.name}: 'contract {name}' 을 선언했는데 분석 결과에 없다. "
                f"contract_cfgs={sorted(ca.contract_cfgs)[:8]}")
        if True:
            cfg = ca.contract_cfgs[name]
            # 서브폴더(타겟별)의 경우 prefix 추가: con_112_Controller.pkl
            parent = sol_path.parent.name
            if parent != "contracts" and parent.isdigit():
                pkl_name = f"con_{parent}_{name}.pkl"
            else:
                pkl_name = f"con_{name}.pkl"
            out = OBJ_DIR / pkl_name
            with open(out, 'wb') as f:
                pickle.dump({"cfg": cfg,
                             "file_level_structs": dict(sa.file_level_structs),
                             "type_aliases": dict(sa.type_aliases)},
                            f, protocol=pickle.HIGHEST_PROTOCOL)
            funcs = list(cfg.functions.keys())
            print(f"  → {pkl_name} ({len(funcs)} functions: {funcs})")
            return name
        else:
            print(f"  [경고] contract_cfgs 비어있음")
            return None


def main():
    parser = argparse.ArgumentParser(description="Dependencies 사전분석")
    parser.add_argument("--type", choices=["interfaces", "libraries", "contracts", "all"],
                        default="all", help="분석 대상 타입")
    parser.add_argument("--file", type=str, help="특정 파일만 분석")
    args = parser.parse_args()

    results = {"interfaces": [], "libraries": [], "contracts": []}

    # 특정 파일만
    if args.file:
        target = pathlib.Path(args.file)
        if not target.exists():
            # 각 디렉토리에서 찾기
            for d, mode in [(IFC_DIR, "interface"), (LIB_DIR, "library"), (CON_DIR, "contract")]:
                candidate = d / args.file
                if candidate.exists():
                    target = candidate
                    result = analyze_file(target, mode)
                    if result:
                        results[f"{mode}s" if mode != "library" else "libraries"].append(result)
                    break
            else:
                print(f"파일 없음: {args.file}")
                return
        return

    # ── Phase 0: type alias + interface 이름 + file-level struct 사전 수집 ──
    global _global_type_aliases, _global_interface_names, _global_file_level_structs
    global _global_file_level_enums
    _global_type_aliases = scan_type_aliases([IFC_DIR, LIB_DIR, CON_DIR])
    _global_interface_names = scan_interface_names([IFC_DIR, LIB_DIR, CON_DIR])
    _global_file_level_structs = scan_file_level_structs([IFC_DIR, LIB_DIR, CON_DIR])
    _global_file_level_enums = scan_file_level_enums([IFC_DIR, LIB_DIR, CON_DIR])
    if _global_type_aliases:
        print(f"\n[Phase 0] Type aliases: {_global_type_aliases}")
    if _global_interface_names:
        print(f"[Phase 0] Interfaces: {sorted(_global_interface_names)}")
    if _global_file_level_structs:
        print(f"[Phase 0] File-level structs: {list(_global_file_level_structs.keys())}")
    if _global_file_level_enums:
        print(f"[Phase 0] File-level enums: {list(_global_file_level_enums.keys())}")

    # ── 분석 순서: interfaces → libraries → contracts ──

    # 1) Interfaces (의존 순서 고려 — Phase 2/3 과 동일하게 위상정렬)
    #    ★ 예전엔 `sorted(rglob)` 알파벳순이었다. F7 이 libraries/contracts 만 고치고
    #      **interfaces 를 빠뜨렸다**. 알파벳순은 의존 방향과 정반대가 될 수 있다:
    #        IPooledCreditLine < IPooledCreditLineDeclarations < IPooledCreditLineEnums
    #      인데 실제 의존은 `IPooledCreditLine is ...Declarations is ...Enums` 이다.
    #      조상이 나중에 분석되면 부모 분석 시점에 조상 pkl 이 없어
    #      `parent_cfgs` 가 **빈 채로** 저장되고(실측: 인터페이스 pkl 전부 parent_cfgs=[]),
    #      `EnhancedSolidityVisitor._find_in_chain` 이 돌 것이 없어
    #      상속된 enum/struct 타입을 못 찾는다
    #      (`Type 'PooledCreditLineStatus' is not defined as struct, enum, or type alias`).
    #      IFC_DIR 73개 파일 전수 확인: 주 선언이 모두 interface 라 모드 불일치 위험 없음.
    if args.type in ("interfaces", "all"):
        ifc_files = sorted(IFC_DIR.rglob("*.sol")) if IFC_DIR.exists() else []
        ifc_ordered = _topo_order(ifc_files, "interfaces")
        print(f"\n[Phase 1] Interfaces: {len(ifc_ordered)}개 (위상정렬)")
        for f, mode in ifc_ordered:
            name = analyze_file(f, mode)
            if name:
                results["interfaces"].append(name)

    # 2) Libraries (의존 순서 고려: 다른 library를 호출하는 파일을 뒤로)
    if args.type in ("libraries", "all"):
        lib_files = sorted(LIB_DIR.glob("*.sol")) if LIB_DIR.exists() else []
        lib_ordered = _topo_order(lib_files, "libraries")
        print(f"\n[Phase 2] Libraries: {len(lib_ordered)}개 (위상정렬)")
        print(f"  순서: {[f.name for f, _ in lib_ordered]}")
        for f, mode in lib_ordered:
            name = analyze_file(f, mode)
            if name:
                results["libraries"].append(name)

    # 3) Contracts (서브폴더 포함)
    #    library → parent contract → child contract 순서로 분석
    #    의존관계를 수동으로 파악하여 하드코딩 (자동 정렬은 복잡도 대비 이점 없음)
    if args.type in ("contracts", "all"):
        con_files = sorted(CON_DIR.rglob("*.sol")) if CON_DIR.exists() else []
        con_ordered = _topo_order(con_files, "contracts")
        print(f"\n[Phase 3] Contracts: {len(con_ordered)}개 (위상정렬)")
        for f, mode in con_ordered:
            print(f"  - {f.relative_to(CON_DIR).as_posix()} [{mode}]")
        for f, mode in con_ordered:
            name = analyze_file(f, mode)
            if name:
                results["contracts"].append(name)

    # ── 결과 요약 ──
    print(f"\n{'='*60}")
    print(f"분석 완료")
    print(f"{'='*60}")
    print(f"  Interfaces: {len(results['interfaces'])} -{results['interfaces']}")
    print(f"  Libraries:  {len(results['libraries'])} -{results['libraries']}")
    print(f"  Contracts:  {len(results['contracts'])} -{results['contracts']}")

    obj_files = list(OBJ_DIR.glob("*.pkl"))
    print(f"\n  objectfile/: {len(obj_files)}개 pkl")
    for p in sorted(obj_files):
        size_kb = p.stat().st_size / 1024
        print(f"    {p.name} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
