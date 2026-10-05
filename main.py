import json
from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.EnhancedYulVisitor import EnhancedYulVisitor
from Analyzer.SolidityAnalyzer import SolidityAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper                        import ParserHelpers     # ★ here
from Utils.YulHelper                     import YulParserHelpers
import time

sa                = SolidityAnalyzer()
contract_analyzer = sa.contract_analyzer
snapman           = contract_analyzer.snapman
batch_mgr         = DebugBatchManager(contract_analyzer, snapman)


def load_dependencies():
    """Dependencies/objectfile의 pkl + 입력 소스에서 interface 이름을 사전 등록"""
    import pathlib, pickle, re
    base = pathlib.Path(__file__).parent
    # 1) pkl에서 interface 이름 수집
    obj_dirs = [base / "Dependencies" / "objectfile", base / "Libraries" / "objectfile"]
    for obj_dir in obj_dirs:
        if not obj_dir.exists():
            continue
        for pkl_path in sorted(obj_dir.glob("*.pkl")):
            name = pkl_path.stem
            if name.startswith("ifc_"):
                # prefix 제거: ifc_5_iERC20 → iERC20
                raw_name = name[4:]
                parts = raw_name.split("_", 1)
                ifc_name = parts[1] if len(parts) > 1 and parts[0].isdigit() else raw_name
                contract_analyzer.interface_names.add(ifc_name)
                # interface CFG 로드 → IReturn, interface call return type 등에서 사용
                try:
                    with open(pkl_path, 'rb') as f:
                        raw = pickle.load(f)
                    if isinstance(raw, dict) and "cfg" in raw:
                        ifc_cfg = raw["cfg"]
                        sa.file_level_structs.update(raw.get("file_level_structs", {}))
                        sa.type_aliases.update(raw.get("type_aliases", {}))
                    else:
                        ifc_cfg = raw
                    contract_analyzer.contract_cfgs[ifc_name] = ifc_cfg
                except Exception:
                    pass
            elif name.startswith("lib_"):
                # library CFG 로드 → library 함수 호출 해석에 사용
                # prefix 제거: lib_47_SafeMathUpgradeable → SafeMathUpgradeable
                parts = name[4:].split("_", 1)
                lib_name = parts[1] if len(parts) > 1 and parts[0].isdigit() else name[4:]
                try:
                    with open(pkl_path, 'rb') as f:
                        raw = pickle.load(f)
                    if isinstance(raw, dict) and "cfg" in raw:
                        lib_cfg = raw["cfg"]
                        sa.file_level_structs.update(raw.get("file_level_structs", {}))
                        sa.type_aliases.update(raw.get("type_aliases", {}))
                    else:
                        lib_cfg = raw
                    contract_analyzer.library_cfgs[lib_name] = lib_cfg
                    contract_analyzer.contract_cfgs[lib_name] = lib_cfg
                except Exception:
                    pass
            elif name.startswith("con_"):
                # contract CFG 로드 → 상속 parent contract 해석에 사용
                # prefix 제거: con_47_ERC20Upgradeable → ERC20Upgradeable
                parts = name[4:].split("_", 1)
                con_name = parts[1] if len(parts) > 1 and parts[0].isdigit() else name[4:]
                try:
                    with open(pkl_path, 'rb') as f:
                        raw = pickle.load(f)
                    if isinstance(raw, dict) and "cfg" in raw:
                        con_cfg = raw["cfg"]
                        sa.file_level_structs.update(raw.get("file_level_structs", {}))
                        sa.type_aliases.update(raw.get("type_aliases", {}))
                    else:
                        con_cfg = raw
                    contract_analyzer.contract_cfgs[con_name] = con_cfg
                except Exception:
                    pass
    # 2) type alias + file-level enum 사전 수집
    #    file-level enum(컨트랙트/인터페이스 밖 최상위 enum)은 pkl 에 구워져 있지 않다
    #    (오프라인 빌드가 enum 을 추적 안 함) → type alias 와 같은 regex 사전-스캔으로 보완.
    _type_re = re.compile(r'type\s+(\w+)\s+is\s+(\w+)\s*;')
    _enum_re = re.compile(r'enum\s+(\w+)\s*\{([^}]*)\}', re.DOTALL)
    type_scan_dirs = [
        base / "Dependencies" / "libraries",
        base / "Dependencies" / "contracts",
        base / "Dependencies" / "interfaces",
        base / "Libraries",
    ]
    for d in type_scan_dirs:
        if not d.exists():
            continue
        for sol in d.rglob("*.sol"):
            text = sol.read_text(encoding='utf-8', errors='ignore')
            for alias, underlying in _type_re.findall(text):
                sa.type_aliases[alias] = underlying
            for enum_name, body in _enum_re.findall(text):
                members = [m.strip() for m in body.split(',') if m.strip()]
                if members:
                    sa.file_level_enums[enum_name] = members
    if sa.type_aliases:
        print(f"[Dependencies] {len(sa.type_aliases)} type aliases registered: {sa.type_aliases}")
    if sa.file_level_enums:
        print(f"[Dependencies] {len(sa.file_level_enums)} file-level enums registered")

    # 3) 입력 소스 + original dependencies에서 interface 이름 regex 사전 수집 (Phase 0과 동일)
    _ifc_re = re.compile(r'interface\s+(\w+)')
    scan_dirs = [
        base / "evaluation" / "Dataset" / "target_contraction",
        base / "evaluation" / "Dataset" / "Dependencies" / "pool",
        base / "Dataset" / "Numscout" / "contraction",
    ]
    for d in scan_dirs:
        if not d.exists():
            continue
        for sol in d.rglob("*.sol"):
            for name in _ifc_re.findall(sol.read_text(encoding='utf-8', errors='ignore')):
                contract_analyzer.interface_names.add(name)
    if contract_analyzer.interface_names:
        print(f"[Dependencies] {len(contract_analyzer.interface_names)} interfaces registered")


load_dependencies()


def simulate_inputs(records, silent=False):
    in_testcase = False

    for rec in records:
        code, s, e, ev = \
            rec["code"], rec["startLine"], rec["endLine"], rec["event"]
        close_before = rec.get("closeBefore", False)

        # ───── Solidity 소스 반영 (add/modify/delete) ─────
        sa.update_code(s, e, code, ev, close_before)

        stripped = code.lstrip()

        # ---------- BEGIN / END ---------------------------------
        if stripped.startswith("// @Debugging BEGIN"):
            batch_mgr.reset()
            in_testcase = True
            continue

        if stripped.startswith("// @Debugging END"):
            batch_mgr.flush()           # 전체 해석
            in_testcase = False
            continue

        # ---------- 주석(어노테이션) ----------------------
        if stripped.startswith("// @"):
            # Intent annotation (@During, @Post)은 코드의 일부로 영구 등록
            # → batch_mgr(snapshot/restore)를 거치지 않음
            if stripped.startswith("// @During") or stripped.startswith("// @Post"):
                # update_code 는 루프 맨 위에서 이미 이 레코드에 대해 호출됨(close_before 포함).
                # 여기서 다시 호출하면 같은 라인에 두 번 적용되어, 첫 호출 시점엔 아직 없던
                # 상태(multi-line statement 의 startLine 텍스트가 빈 경우 등)를 오판해
                # 불필요한 라인 밀기가 발생한다.
                tree = ParserHelpers.generate_parse_tree(code, "intentUnit")
                EnhancedSolidityVisitor(contract_analyzer).visit(tree)
                continue

            # Debug annotation (@LocalVar, @StateVar, @GlobalVar, @IReturn)
            # list 기반 batch 전환(2026-07-03): 라인 키가 없어졌으므로 modify/delete 는
            # 개별 라인 갱신이 불가 → add 로 누적만. (레거시 CLI 경로, 회귀 무시 승인됨)
            if ev != "delete":
                batch_mgr.add(code)

            # BEGIN~END 밖이면 즉시 해석
            if not in_testcase:
                batch_mgr.flush()
            continue

        # ---------- 일반 Solidity / Yul 한 줄 --------------------
        if code.strip():           # 공백 라인은 생략
            ctx = contract_analyzer.get_current_context_type()
            if ctx == "assembly":
                # Yul parser + visitor
                tree = YulParserHelpers.generate_parse_tree(code)
                EnhancedYulVisitor(contract_analyzer).visit(tree)
            else:
                tree = ParserHelpers.generate_parse_tree(code, ctx, True)
                EnhancedSolidityVisitor(contract_analyzer).visit(tree)

            if not silent:
                analysis = contract_analyzer.get_line_analysis(s, e)
                for ln, recs in analysis.items():
                    for r in recs:
                        print(f"L{ln:3} | {r['kind']:>12} | {r['vars']}")


if __name__ == "__main__":
    import sys, pathlib
    if len(sys.argv) < 2:
        print("Usage: python main.py <case.json>")
        sys.exit(1)
    path = sys.argv[1]
    records = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    print(f"=== {pathlib.Path(path).name} ({len(records)} records) ===\n")
    t0 = time.perf_counter()
    simulate_inputs(records)
    elapsed = time.perf_counter() - t0
    print(f"\n[TIMING] {elapsed:.4f}s")

