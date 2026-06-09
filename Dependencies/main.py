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


# 전역 사전 등록 (Phase 0에서 수집, analyze_file에서 주입)
_global_type_aliases: dict[str, str] = {}
_global_interface_names: set[str] = set()
_global_library_cfgs: dict = {}  # 이전 분석된 library CFG 누적 (cross-library 호출용)
_global_file_level_structs: dict = {}  # file-level struct 사전 수집

# parent pkl 검색용 패턴 (contract, abstract contract, interface, library)
_is_re = re.compile(r'(?:abstract\s+)?(?:contract|interface|library)\s+\w+\s+is\s+([^{]+)')

def _load_parent_pkls(source: str, ca) -> None:
    """소스에서 'X is A, B, C' 파싱 → objectfile에서 parent pkl 로드 (재귀)"""
    m = _is_re.search(source)
    if not m:
        return
    parent_names = [p.strip().split('(')[0].strip() for p in m.group(1).split(',')]
    for pname in parent_names:
        if not pname or pname in ca.contract_cfgs:
            continue
        # pkl 검색: con_*.pkl 또는 ifc_*.pkl
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
    # 이전 분석된 library CFG 주입 (cross-library 호출 resolve용)
    _pre_existing_libs = set(_global_library_cfgs.keys())
    if _global_library_cfgs:
        ca.library_cfgs.update(_global_library_cfgs)
        ca.contract_cfgs.update(_global_library_cfgs)  # 호환성
    # parent pkl 로드: 소스에서 'is Parent1, Parent2' 파싱 → pkl 있으면 로드
    _load_parent_pkls(source, ca)
    _pre_existing_all = set(ca.contract_cfgs.keys()) | set(ca.library_cfgs.keys())

    for rec in records:
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
        close_before = rec.get("closeBefore", False)
        try:
            sa.update_code(s, e, code, ev, close_before)
        except Exception:
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
        # 새로 분석된 library만 식별 (주입된 기존 library 제외)
        new_libs = [k for k in ca.library_cfgs if k not in _pre_existing_all]
        if new_libs:
            name = new_libs[0]
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
        else:
            print(f"  [경고] library_cfgs 비어있음")
            return None

    elif mode == "interface":
        # 새로 분석된 interface만 식별 (로드된 parent pkl 제외)
        new_ifcs = [k for k in ca.contract_cfgs if k not in _pre_existing_all]
        if not new_ifcs:
            m = re.search(r'interface\s+(\w+)', source)
            if m and m.group(1) in ca.contract_cfgs:
                new_ifcs = [m.group(1)]
        if new_ifcs:
            name = new_ifcs[0]
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
        else:
            print(f"  [경고] interface 미발견")
            return None

    elif mode == "contract":
        # 새로 분석된 contract만 식별 (주입된 기존 library/parent 제외)
        new_cons = [k for k in ca.contract_cfgs if k not in _pre_existing_all]
        if not new_cons:
            # 이름 충돌로 감지 안 된 경우: 소스에서 contract 이름 직접 추출
            m = re.search(r'(?:abstract\s+)?contract\s+(\w+)', source)
            if m and m.group(1) in ca.contract_cfgs:
                new_cons = [m.group(1)]
        if new_cons:
            name = new_cons[0]
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
    _global_type_aliases = scan_type_aliases([IFC_DIR, LIB_DIR, CON_DIR])
    _global_interface_names = scan_interface_names([IFC_DIR, LIB_DIR, CON_DIR])
    _global_file_level_structs = scan_file_level_structs([IFC_DIR, LIB_DIR, CON_DIR])
    if _global_type_aliases:
        print(f"\n[Phase 0] Type aliases: {_global_type_aliases}")
    if _global_interface_names:
        print(f"[Phase 0] Interfaces: {sorted(_global_interface_names)}")
    if _global_file_level_structs:
        print(f"[Phase 0] File-level structs: {list(_global_file_level_structs.keys())}")

    # ── 분석 순서: interfaces → libraries → contracts ──

    # 1) Interfaces
    if args.type in ("interfaces", "all"):
        ifc_files = sorted(IFC_DIR.rglob("*.sol")) if IFC_DIR.exists() else []
        print(f"\n[Phase 1] Interfaces: {len(ifc_files)}개")
        for f in ifc_files:
            name = analyze_file(f, "interface")
            if name:
                results["interfaces"].append(name)

    # 2) Libraries (의존 순서 고려: 다른 library를 호출하는 파일을 뒤로)
    if args.type in ("libraries", "all"):
        lib_files = sorted(LIB_DIR.glob("*.sol")) if LIB_DIR.exists() else []
        # cross-library 의존: UFixed18 → Fixed18, FullMath → FixedPoint
        _late = {"Fixed18.sol", "FixedPoint.sol"}
        lib_files_ordered = [f for f in lib_files if f.name not in _late] + \
                            [f for f in lib_files if f.name in _late]
        print(f"\n[Phase 2] Libraries: {len(lib_files_ordered)}개")
        for f in lib_files_ordered:
            name = analyze_file(f, "library")
            if name:
                results["libraries"].append(name)

    # 3) Contracts (서브폴더 포함)
    #    library → parent contract → child contract 순서로 분석
    #    의존관계를 수동으로 파악하여 하드코딩 (자동 정렬은 복잡도 대비 이점 없음)
    if args.type in ("contracts", "all"):
        # ── 분석 순서 정의: (상대경로, 모드) ──
        #   library 먼저 → parent contract → child contract
        _con_order = [
            # --- 루트 (의존 없음) ---
            ("solmate_ERC20.sol",           "contract"),
            ("LockeERC20.sol",              "contract"),
            ("Pausable.sol",                "contract"),
            ("78_OZ_ERC20.sol",             "contract"),
            ("TokenProxyLike.sol",          "contract"),
            # --- 루트 (library) ---
            ("AddressProviderKeys.sol",     "library"),
            ("AddressProviderMeta.sol",     "library"),
            # --- 루트 (의존 있음) ---
            ("AuthorizationBase.sol",       "contract"),
            ("Authorization.sol",           "contract"),   # is AuthorizationBase
            ("Preparable.sol",              "contract"),
            ("ReentrancyGuardUpgradeable.sol", "contract"),  # is Initializable (pkl)
            # --- 47/ : library → parent → child ---
            ("47/SafeMathUpgradeable.sol",  "library"),
            ("47/AddressUpgradeable.sol",   "library"),
            ("47/Initializable.sol",        "contract"),
            ("47/ContextUpgradeable.sol",   "contract"),   # is Initializable
            ("47/ERC20Upgradeable.sol",     "contract"),   # is Initializable, ContextUpgradeable
            # --- 51/ : library → parent → child ---
            ("51/Context.sol",              "contract"),
            ("51/Ownable.sol",              "contract"),   # is Context
            ("51/ERC20.sol",                "contract"),   # is Context
            ("51/ERC20Burnable.sol",        "contract"),   # is ERC20
            ("51/LPToken.sol",              "contract"),   # is ERC20Burnable, Ownable
            # --- 112/ : library → contract ---
            ("112/Roles.sol",               "library"),
            ("112/Controller.sol",          "contract"),
            # --- 45/ ---
            ("45/Controller.sol",           "contract"),
            # --- ERC1155 계열 ---
            ("ERC165Upgradeable.sol",       "contract"),   # is Initializable (pkl)
            ("ERC1155Upgradeable.sol",      "contract"),   # is Initializable, ..., ERC165Upgradeable
        ]

        print(f"\n[Phase 3] Contracts: {len(_con_order)}개 (수동 순서)")
        for rel_path, mode in _con_order:
            f = CON_DIR / rel_path
            if not f.exists():
                print(f"  [건너뜀] {rel_path} (파일 없음)")
                continue
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
