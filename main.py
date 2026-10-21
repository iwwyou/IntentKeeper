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


def _load_pkl(pkl_path):
    """pkl 하나 → (cfg, payload). 실패하면 예외 (2026-10-21: 예전엔 `except Exception: pass` 로 조용히 건너뛰어
    해당 의존성이 없는 채 분석이 진행됐다 — 조용한 오분석)."""
    import pickle
    with open(pkl_path, 'rb') as f:
        raw = pickle.load(f)
    if isinstance(raw, dict) and "cfg" in raw:
        sa.file_level_structs.update(raw.get("file_level_structs", {}))
        sa.type_aliases.update(raw.get("type_aliases", {}))
        return raw["cfg"]
    return raw


def load_dependencies(deps_root=None, exclude=()):
    """의존성 pkl + interface 이름 사전 등록.

    deps_root=None : 기존 공용 트리(Dependencies/objectfile, Libraries/objectfile) — 레거시 48 케이스.
    deps_root=<dir>: **프로젝트 단위** 트리 (2026-10-21, evaluation/Dataset/build_project_deps.py 가 만든
                     deps/<p>/{interfaces,libraries,contracts,objectfile}). 그 프로젝트의 선언만 로드하므로
                     프로젝트 간 이름 충돌(OZ ERC20 vs solmate ERC20)이 없다.
    exclude        : 분석 대상 소스가 스스로 선언하는 이름 — pkl 판을 올리지 않는다(같은 선언이 두 판 생기지 않게).
    """
    import pathlib, re
    base = pathlib.Path(__file__).parent
    exclude = set(exclude or ())
    if deps_root is not None:
        root = pathlib.Path(deps_root)
        if not (root / "objectfile").is_dir():
            raise FileNotFoundError(f"project deps not built: {root / 'objectfile'}")
        obj_dirs = [root / "objectfile"]
        src_dirs = [root / "libraries", root / "contracts", root / "interfaces"]
        ifc_scan_dirs = src_dirs
    else:
        obj_dirs = [base / "Dependencies" / "objectfile", base / "Libraries" / "objectfile"]
        src_dirs = [base / "Dependencies" / "libraries", base / "Dependencies" / "contracts",
                    base / "Dependencies" / "interfaces", base / "Libraries"]
        ifc_scan_dirs = [base / "evaluation" / "Dataset" / "target_contraction",
                         base / "evaluation" / "Dataset" / "Dependencies" / "pool",
                         base / "Dataset" / "Numscout" / "contraction"]

    def strip_prefix(raw_name):
        # con_47_ERC20Upgradeable → ERC20Upgradeable (공용 트리의 contest 접두어)
        parts = raw_name.split("_", 1)
        return parts[1] if len(parts) > 1 and parts[0].isdigit() and deps_root is None else raw_name

    # 1) pkl 로드
    for obj_dir in obj_dirs:
        if not obj_dir.exists():
            continue
        for pkl_path in sorted(obj_dir.glob("*.pkl")):
            stem = pkl_path.stem
            kind, raw_name = stem[:4], stem[4:]
            name = strip_prefix(raw_name)
            if name in exclude:
                continue
            if kind == "ifc_":
                contract_analyzer.interface_names.add(name)
                contract_analyzer.contract_cfgs[name] = _load_pkl(pkl_path)
            elif kind == "lib_":
                cfg = _load_pkl(pkl_path)
                contract_analyzer.library_cfgs[name] = cfg
                contract_analyzer.contract_cfgs[name] = cfg
            elif kind == "con_":
                contract_analyzer.contract_cfgs[name] = _load_pkl(pkl_path)
    # 2) type alias + file-level enum 사전 수집
    #    file-level enum(컨트랙트/인터페이스 밖 최상위 enum)은 pkl 에 구워져 있지 않다
    #    (오프라인 빌드가 enum 을 추적 안 함) → type alias 와 같은 regex 사전-스캔으로 보완.
    _type_re = re.compile(r'type\s+(\w+)\s+is\s+(\w+)\s*;')
    _enum_re = re.compile(r'enum\s+(\w+)\s*\{([^}]*)\}', re.DOTALL)
    for d in src_dirs:
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

    # 3) interface 이름 regex 사전 수집 (Phase 0과 동일)
    _ifc_re = re.compile(r'interface\s+(\w+)')
    for d in ifc_scan_dirs:
        if not d.exists():
            continue
        for sol in d.rglob("*.sol"):
            for name in _ifc_re.findall(sol.read_text(encoding='utf-8', errors='ignore')):
                contract_analyzer.interface_names.add(name)
    if contract_analyzer.interface_names:
        print(f"[Dependencies] {len(contract_analyzer.interface_names)} interfaces registered")


# 프로젝트 단위 의존성: 실행 드라이버가 환경변수로 지정 (evaluation/intent_validation/run_cases.py --rebuilt)
import os as _os
load_dependencies(_os.environ.get("IQ_DEPS_ROOT") or None,
                  [x for x in _os.environ.get("IQ_DEPS_EXCLUDE", "").split(",") if x])


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

            # Debug annotation (@Param, @StateVar, @GlobalVar, @IReturn)
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

