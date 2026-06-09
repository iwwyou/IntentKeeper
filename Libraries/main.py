#!/usr/bin/env python3
"""
라이브러리 분석 및 Pickle 저장 스크립트

soltotestjson 방식으로 라이브러리를 라인 단위로 분석하고,
CFGSerializerPickle로 pkl 파일로 저장합니다.
"""

import re
import sys
import pathlib
from typing import List, Dict

# 상위 디렉토리를 sys.path에 추가
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.CFGSerializerPickle import CFGSerializerPickle
from Utils.Helper import ParserHelpers


# ── soltotestjson 패턴 ──────────────────────────────────────────────────
_only_ws   = re.compile(r"^\s*$")          # 공백/탭 뿐
_open_blk  = re.compile(r"\{\s*$")         # … {
_one_liner = re.compile(r";\s*$")          # … ;
_only_clo  = re.compile(r"^\s*}\s*$")      # }


def slice_solidity(source: str) -> List[Dict[str, str | int]]:
    """
    Solidity 소스 코드를 라인 단위 청크로 변환 (soltotestjson 방식)
    """
    lines: List[str] = source.splitlines()
    inputs: List[Dict[str, str | int]] = []

    cur_line = 1
    i = 0

    while i < len(lines):
        raw = lines[i]
        txt = raw.strip()

        # 1) 빈 줄
        if _only_ws.match(raw):
            inputs.append({"code": "\n", "startLine": cur_line, "endLine": cur_line, "event": "add"})
            cur_line += 1
            i += 1
            continue

        # 2) 단독 '}' - JSON으로 내보내지 않음
        if _only_clo.match(txt):
            cur_line += 1
            i += 1
            continue

        # 3) '{' 로 끝나는 헤더 줄
        if _open_blk.search(txt):
            block_code = f"{txt}\n}}"
            inputs.append({
                "code": block_code,
                "startLine": cur_line,
                "endLine": cur_line + 1,
                "event": "add"
            })
            cur_line += 1
            i += 1
            continue

        # 4) 세미콜론으로 끝나는 한 줄 문장
        if _one_liner.search(txt):
            inputs.append({"code": txt, "startLine": cur_line, "endLine": cur_line, "event": "add"})
            cur_line += 1
            i += 1
            continue

        # 5) 다중 라인 문장
        start_line = cur_line
        accumulated = [txt]
        cur_line += 1
        i += 1

        while i < len(lines):
            next_raw = lines[i]
            next_txt = next_raw.strip()

            if _only_ws.match(next_raw):
                cur_line += 1
                i += 1
                continue

            accumulated.append(next_txt)
            cur_line += 1
            i += 1

            if _one_liner.search(next_txt):
                break

        merged_code = " ".join(accumulated)
        inputs.append({
            "code": merged_code,
            "startLine": start_line,
            "endLine": cur_line - 1,
            "event": "add"
        })

    return inputs


def analyze_library_file(sol_file_path: pathlib.Path) -> str:
    """
    라이브러리 .sol 파일을 분석하여 pkl로 저장

    Returns:
        라이브러리 이름
    """
    print(f"\n{'='*60}")
    print(f"분석 시작: {sol_file_path.name}")
    print(f"{'='*60}")

    # 1. 소스 파일 읽기
    source = sol_file_path.read_text(encoding='utf-8')
    print(f"[1] 소스 파일 읽기 완료 ({len(source)} 문자)")

    # 2. 라인 단위 청크로 변환
    records = slice_solidity(source)
    print(f"[2] 청크 변환 완료 ({len(records)}개 청크)")

    # 3. ContractAnalyzer 초기화
    analyzer = ContractAnalyzer()

    # 4. 라인 단위로 분석 (test_boosttoken.py 방식)
    print(f"[3] 라인 단위 분석 시작...")
    for rec in records:
        code = rec["code"]
        s = rec["startLine"]
        e = rec["endLine"]
        ev = rec["event"]

        # update_code로 소스 코드 저장 및 context 관리
        analyzer.update_code(s, e, code, ev)

        # 일반 Solidity 코드는 EnhancedSolidityVisitor로 파싱
        stripped = code.strip()
        if stripped and not stripped.startswith("// @"):
            ctx = analyzer.get_current_context_type()
            try:
                tree = ParserHelpers.generate_parse_tree(code, ctx, True)
                EnhancedSolidityVisitor(analyzer).visit(tree)
            except Exception as ex:
                pass  # pragma 등 파싱 실패는 무시

    print(f"[4] 분석 완료")

    # 5. 분석된 라이브러리 확인
    print(f"\n[5] 분석 결과:")
    print(f"    - library_cfgs: {list(analyzer.library_cfgs.keys())}")
    print(f"    - contract_cfgs: {list(analyzer.contract_cfgs.keys())}")

    # 라이브러리 이름 추출 (library_cfgs에서)
    if analyzer.library_cfgs:
        library_name = list(analyzer.library_cfgs.keys())[0]
        library_cfg = analyzer.library_cfgs[library_name]

        # 함수 정보 출력
        if hasattr(library_cfg, 'functions') and library_cfg.functions:
            print(f"    - 함수 목록: {list(library_cfg.functions.keys())}")

            # 첫 번째 함수의 노드 확인 (디버깅용)
            first_func_name = list(library_cfg.functions.keys())[0]
            first_func_cfg = library_cfg.functions[first_func_name]
            node_names = [getattr(n, 'name', str(n)) for n in first_func_cfg.graph.nodes]
            print(f"    - '{first_func_name}' 함수 노드: {node_names}")

        # 6. Pickle로 저장
        print(f"\n[6] Pickle 저장...")
        serializer = CFGSerializerPickle()
        saved_path = serializer.save_library_cfg(library_cfg, library_name)
        print(f"    저장 완료: {saved_path}")

        return library_name
    else:
        print(f"    [경고] library_cfgs가 비어있음")
        return None


def main():
    """메인 함수"""
    print("="*60)
    print("라이브러리 분석 및 Pickle 저장 스크립트")
    print("="*60)

    # solfile 디렉토리
    current_dir = pathlib.Path(__file__).parent
    solfile_dir = current_dir / "solfile"

    if not solfile_dir.exists():
        print(f"[오류] solfile 디렉토리가 없습니다: {solfile_dir}")
        return

    # .sol 파일 스캔
    sol_files = list(solfile_dir.glob("*.sol"))
    print(f"\n발견된 .sol 파일: {len(sol_files)}개")
    for f in sol_files:
        print(f"  - {f.name}")

    # 각 파일 분석
    results = {}
    for sol_file in sol_files:
        try:
            library_name = analyze_library_file(sol_file)
            if library_name:
                results[sol_file.name] = library_name
        except Exception as e:
            print(f"[오류] {sol_file.name} 분석 실패: {e}")
            import traceback
            traceback.print_exc()

    # 결과 요약
    print(f"\n{'='*60}")
    print(f"분석 완료: {len(results)}/{len(sol_files)}개 성공")
    print(f"{'='*60}")
    for sol_name, lib_name in results.items():
        print(f"  {sol_name} -> {lib_name}.pkl")

    # objectfile 디렉토리 내용 확인
    objectfile_dir = current_dir / "objectfile"
    if objectfile_dir.exists():
        pkl_files = list(objectfile_dir.glob("*.pkl"))
        print(f"\nobjectfile 디렉토리:")
        for pkl_file in pkl_files:
            size_kb = pkl_file.stat().st_size / 1024
            print(f"  - {pkl_file.name} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
