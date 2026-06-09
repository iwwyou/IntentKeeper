# Analyzer/SolidityAnalyzer.py
"""
Solidity 소스 코드의 최상위 분석기.

소스 코드 저장 및 라인 관리(insert/shift/delete)를 담당하고,
file-level 구조(struct, type alias)를 자체 처리한다.
Contract-level 분석은 ContractAnalyzer에 위임한다.
"""
import re
from Domain.Type import SolType


class SolidityAnalyzer:

    def __init__(self):
        # ── Source storage ──────────────────────────────────────
        self.full_code = None
        self.full_code_lines = {}   # line_no -> code string
        self.line_info = {}         # line_no -> {"open": int, "close": int, "cfg_nodes": []}

        # ── Source management state ────────────────────────────
        self.current_start_line = None
        self.current_end_line = None
        self.current_edit_event = None
        self.current_close_before = False

        # ── File-level definitions ─────────────────────────────
        self.file_level_structs = {}    # {"StructName": {field_name: SolType, ...}}
        self.type_aliases = {}          # {"TypeName": "underlyingElementaryType"}
        self._current_file_struct = None  # 현재 열린 file-level struct 이름

        # ── ContractAnalyzer 생성 (self 참조 전달) ──────────────
        from Analyzer.ContractAnalyzer import ContractAnalyzer
        self.contract_analyzer = ContractAnalyzer(solidity_analyzer=self)

    # =================================================================
    #  Source management (update_code, _insert_lines, etc.)
    # =================================================================

    def update_code(self, start_line: int, end_line: int, new_code: str,
                    event: str, close_before: bool = False):
        """소스 코드 업데이트의 진입점."""
        self.current_start_line = start_line
        self.current_end_line = end_line
        self.current_edit_event = event
        self.current_close_before = close_before

        # CA에도 동기화 (CA의 process_* 메서드들이 current_start_line 등을 사용)
        ca = self.contract_analyzer
        ca.current_start_line = start_line
        ca.current_end_line = end_line
        ca.current_edit_event = event
        ca.current_close_before = close_before

        if event not in {"add", "modify", "delete"}:
            raise ValueError(f"unknown event '{event}'")

        if event == "add":
            lines = new_code.split("\n")
            # During annotation inline: 기존 코드가 있는 라인에 붙는 경우 밀기 불필요
            if self._is_during_inline(new_code, start_line):
                self.analyze_context(start_line, new_code)
                return
            self._insert_lines(start_line, lines)

        elif event == "modify":
            raw_lines = new_code.split("\n")
            norm_lines = self.normalize_compound_control_lines(raw_lines)
            if (end_line - start_line + 1) != len(norm_lines):
                self.update_code(start_line, end_line, "", event="delete")
                self.update_code(start_line, start_line + len(norm_lines) - 1,
                                 "\n".join(norm_lines), event="add")
                return

            ln = start_line
            for line in norm_lines:
                self.full_code_lines[ln] = line
                self.update_brace_count(ln, line)
                if self._should_trigger_analysis(line):
                    self.analyze_context(ln, line)
                ln += 1

        elif event == "delete":
            offset = end_line - start_line + 1

            # 기존 라인 제거
            for ln in range(start_line, end_line + 1):
                self.full_code_lines.pop(ln, None)
                self.line_info.pop(ln, None)
                ca.recorder.ledger.pop(ln, None)

            # 뒤쪽 라인 당기기
            keys_to_shift = sorted([ln for ln in self.full_code_lines if ln > end_line])
            for old_ln in keys_to_shift:
                new_ln = old_ln - offset
                self.full_code_lines[new_ln] = self.full_code_lines.pop(old_ln)
                self._shift_source_meta(old_ln, new_ln)
                ca._shift_cfg_meta(old_ln, new_ln)

        # full-code 재조합
        self.full_code = "\n".join(
            self.full_code_lines[ln] for ln in sorted(self.full_code_lines))

        # add/modify 후 전체 블록의 컨텍스트 설정
        if event in {"add", "modify"} and new_code.strip():
            self.analyze_context(start_line, new_code)

    def _insert_lines(self, start: int, new_lines: list[str]):
        new_lines = self.normalize_compound_control_lines(new_lines)
        # offset = 소스 스팬 (endLine - startLine + 1)
        if self.current_end_line is not None and self.current_end_line >= start:
            offset = self.current_end_line - start + 1
        else:
            offset = len(new_lines)

        # start 라인에 control flow 노드가 있고, 새 코드가 연속되는 control flow인지 체크
        skip_shift_at_start = False
        if start in self.line_info:
            cfg_nodes = self.line_info[start].get('cfg_nodes', [])
            first_new_line = new_lines[0].strip() if new_lines else ""

            for node in cfg_nodes:
                if (getattr(node, 'join_point_node', False) and
                    (first_new_line.startswith('else if') or first_new_line.startswith('else')) and
                    self.current_close_before):
                    skip_shift_at_start = True
                    break
                if (getattr(node, 'is_do_end', False) and
                    first_new_line.startswith('while') and
                    self.current_close_before):
                    skip_shift_at_start = True
                    break
                if (node.name.startswith('try_false_stub') and
                    first_new_line.startswith('catch') and
                    self.current_close_before):
                    skip_shift_at_start = True
                    break

        # 뒤 라인 밀기
        shift_from = start + 1 if skip_shift_at_start else start
        # skip_shift_at_start: start 라인을 재사용하므로 실제 필요한 shift 양은 1 줄음
        actual_offset = offset - 1 if skip_shift_at_start else offset
        ca = self.contract_analyzer

        for old_ln in sorted([ln for ln in self.full_code_lines if ln >= shift_from], reverse=True):
            self.full_code_lines[old_ln + actual_offset] = self.full_code_lines.pop(old_ln)
            self._shift_source_meta(old_ln, old_ln + actual_offset)
            ca._shift_cfg_meta(old_ln, old_ln + actual_offset)

        # 삽입 - 실제 코드 줄은 스팬 끝에, 빈 슬롯은 앞에 채운다
        write_count = min(len(new_lines), offset)
        write_start = start + offset - write_count

        # 앞쪽 빈 슬롯 채우기
        for i in range(write_start - start):
            ln = start + i
            if ln not in self.full_code_lines:
                self.full_code_lines[ln] = ""
            if ln not in self.line_info:
                self.line_info[ln] = {"open": 0, "close": 0, "cfg_nodes": []}

        # 실제 코드 줄 쓰기
        for i in range(write_count):
            ln = write_start + i
            line = new_lines[i]
            self.full_code_lines[ln] = line
            self.update_brace_count(ln, line)
            if self._should_trigger_analysis(line):
                self.analyze_context(ln, line)

    def _shift_source_meta(self, old_ln: int, new_ln: int):
        """소스 메타데이터(line_info) key 이동"""
        if old_ln in self.line_info:
            self.line_info[new_ln] = self.line_info.pop(old_ln)

    def _should_trigger_analysis(self, code_line: str) -> bool:
        s = (code_line or "").strip()
        if not s:
            return False
        if s == "}":
            return False
        if s.startswith("pragma ") or s.startswith("import "):
            return False
        if s.startswith("//"):
            return s.startswith("// @")
        if s.endswith(";"):
            return True
        if ')' in s and '{' in s and not s.startswith(('if', 'for', 'while', 'else')):
            return True
        return bool(re.match(
            r"^(abstract\s+contract|contract|library|interface|function|constructor|modifier|"
            r"struct|enum|event|if|else(\s+if)?\b|for|while|do\b|try|catch|unchecked|assembly)\b", s))

    def normalize_compound_control_lines(self, lines: list[str]) -> list[str]:
        out: list[str] = []
        pat = re.compile(r'}\s*(?=else\b|while\b)')
        for s in lines:
            rest = s
            while True:
                m = pat.search(rest)
                if not m:
                    out.append(rest)
                    break
                left = rest[:m.start()] + "}"
                right = rest[m.end():].lstrip()
                out.append(left)
                rest = right
        return out

    def update_brace_count(self, line_number, code):
        open_braces = code.count('{')
        close_braces = code.count('}')
        if line_number not in self.line_info:
            self.line_info[line_number] = {"open": 0, "close": 0, "cfg_nodes": []}
        info = self.line_info[line_number]
        info['open'] = open_braces
        info['close'] = close_braces

    def _is_during_inline(self, code: str, start_line: int) -> bool:
        """During annotation이 기존 코드 라인에 있어 밀기가 불필요한 inline인지 확인.
        During만 해당 — 다른 annotation(@GlobalVar, @StateVar, @Post 등)은 항상 standalone."""
        stripped = code.strip()
        if not stripped.startswith("// @During"):
            return False
        return (start_line in self.full_code_lines and
                self.full_code_lines[start_line].strip() != "")

    def get_full_code(self):
        return self.full_code

    def compile_check(self) -> None:
        from solcx import (install_solc, set_solc_version, compile_source,
                           get_installed_solc_versions)
        from solcx.exceptions import SolcError

        wanted = '0.8.0'
        if wanted not in get_installed_solc_versions():
            print(f"[info] installing solc {wanted} …")
            install_solc(wanted)
        set_solc_version(wanted)
        try:
            compile_source(self.full_code)
            print("[ok] solidity compiled successfully")
        except SolcError as e:
            print("[err] Solidity compiler reported:\n", e)
        except Exception as e:
            print("[err] unexpected:", e)

    # =================================================================
    #  Context analysis dispatcher
    # =================================================================

    def analyze_context(self, start_line, code):
        """Context dispatcher: file-level → 자체 처리, contract-level → CA 위임."""
        stripped = (code or "").strip()
        if not stripped or stripped == "}":
            return
        if stripped.startswith("pragma ") or stripped.startswith("import "):
            return

        # debug annotations → 항상 CA
        if stripped.startswith("// @"):
            self.contract_analyzer.analyze_context(start_line, code)
            return

        # assembly 내부 감지: parent가 assembly이면 context를 "assembly"로 설정
        parent = self.contract_analyzer.find_parent_context(start_line)
        if parent == "assembly":
            ca = self.contract_analyzer
            ca.current_context_type = "assembly"
            ca.current_target_contract = ca.find_contract_context(start_line)
            ca.current_target_function = ca.find_function_context(start_line)
            return

        # file-level 판별: enclosing contract가 없으면 file level
        contract = self.contract_analyzer.find_contract_context(start_line)
        if contract is None:
            if self._handle_file_level(start_line, code, stripped):
                return  # SA가 처리함

        # 나머지는 CA에 위임 (contract-level + contract/library/interface 정의)
        self.contract_analyzer.analyze_context(start_line, code)

    def _handle_file_level(self, start_line, code, stripped):
        """File-level 구조 처리. 처리했으면 True 반환."""
        ca = self.contract_analyzer

        # type alias: type Fixed18 is int256;
        if stripped.startswith("type ") and " is " in stripped and stripped.endswith(";"):
            ca.current_context_type = "fileLevelTypeAlias"
            ca.current_target_contract = None
            ca.current_target_function = None
            ca.current_target_struct = None
            return True

        # struct definition header: struct X {
        if stripped.startswith("struct ") and "{" in stripped:
            ca.current_context_type = "fileLevelStruct"
            ca.current_target_contract = None
            ca.current_target_function = None
            ca.current_target_struct = None
            return True

        # struct member (inside file-level struct)
        if stripped.endswith(";") and self._current_file_struct is not None:
            parent = ca.find_parent_context(start_line)
            if parent == "struct":
                ca.current_context_type = "fileLevelStructMember"
                ca.current_target_contract = None
                ca.current_target_function = None
                ca.current_target_struct = ca.find_struct_context(start_line)
                return True

        return False  # SA가 처리하지 못함 → CA에 위임

    # =================================================================
    #  File-level process 메서드
    # =================================================================

    def process_file_level_struct_definition(self, struct_name: str):
        """file-level struct 정의 시작 (contract level과 동일하게 StructDefinition 사용)"""
        from Domain.Variable import StructDefinition
        self._current_file_struct = struct_name
        self.file_level_structs[struct_name] = StructDefinition(struct_name)

    def process_file_level_struct_member(self, var_name: str, type_obj):
        """file-level struct member 추가"""
        if self._current_file_struct and self._current_file_struct in self.file_level_structs:
            self.file_level_structs[self._current_file_struct].add_member(var_name, type_obj)

    def end_file_level_struct(self):
        """file-level struct 정의 종료"""
        self._current_file_struct = None

    def process_type_alias(self, alias_name: str, underlying_type: str):
        """user-defined value type alias 등록 (e.g., type Fixed18 is int256)"""
        self.type_aliases[alias_name] = underlying_type

    # =================================================================
    #  File-level 조회 API
    # =================================================================

    def get_file_level_struct(self, name: str):
        """file-level struct 정의 조회 (StructDefinition 또는 None)"""
        return self.file_level_structs.get(name)

    def resolve_type(self, type_name: str) -> str | None:
        """user-defined type alias를 underlying type으로 resolve.
        alias가 없으면 None 반환."""
        return self.type_aliases.get(type_name)
