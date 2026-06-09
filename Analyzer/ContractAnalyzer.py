from Utils.CFG import *
from Domain.AddressSet import address_manager, AddressSet
from Domain.Interval import IntegerInterval, UnsignedIntegerInterval, BoolInterval
from Domain.Type import SolType
from Utils.Helper import *
from Utils.Snapshot import *
from Analyzer.DynamicCFGBuilder import DynamicCFGBuilder
from Analyzer.RecordManager import RecordManager
from Analyzer.StaticCFGFactory import StaticCFGFactory
from Interpreter.Semantics.Evaluation import Evaluation
from Interpreter.Semantics.Update import Update
from Interpreter.Semantics.DebugInitializer import DebugInitializer
from Interpreter.Semantics.Refine import Refine
from Interpreter.Engine import Engine
from Analyzer.GuardianVerificationEngine import GuardianVerificationEngine

import re

class ContractAnalyzer:

    def __init__(self, solidity_analyzer):
        # SolidityAnalyzer 참조 — 소스 저장소(full_code_lines, full_code, line_info)는 sa가 소유
        self.sa = solidity_analyzer

        self.addr_mgr = address_manager  # 싱글톤 AddressManager
        self.snapman = SnapshotManager()
        self._batch_targets: set[FunctionCFG] = set()  # 🔹추가

        self.current_start_line = None
        self.current_end_line = None

        self.current_context_type = None
        self.current_target_contract = None
        self.current_target_function = None
        self.current_target_function_param_types: list[str] | None = None
        self.current_target_function_cfg = None
        self.current_target_struct = None

        self.current_edit_event = None
        self._record_enabled = False
        self._seen_stmt_ids: set[int] = set()
        self._last_touched_lines = None

        # for Multiple Contract
        self.contract_cfgs = {} # name -> CFG
        self.library_cfgs = {} # name -> LibraryCFG
        self.interface_names: set[str] = set()  # interface 이름 등록 (타입 인식용)
        self._interface_ranges: list[tuple[int, int]] = []  # (start, end) 라인 범위

        # ★ 함수 호출 순서 문제 해결용
        # Evaluation.py에서 함수가 아직 분석 안 되어서 Top 반환 시 함수명 저장
        self.pending_callee_name = None
        # callee_name -> List[(caller_fcfg, call_node)] 매핑
        self.pending_calls: dict[str, list] = {}

        self.evaluator = Evaluation(self)
        self.updater = Update(self)
        self.debug_initializer = DebugInitializer(self)
        self.refiner = Refine(self)
        self.engine = Engine(self)
        self.builder = DynamicCFGBuilder(self)
        self.recorder = RecordManager()
        self.guardian_verifier = GuardianVerificationEngine(self)

        self.analysis_per_line = self.recorder.ledger

        # ★ Intent annotation 저장용
        self.during_annotations: dict[int, list] = {}  # line_no -> [clause_dicts]
        self.post_annotations: dict[int, list] = {}    # line_no -> [clause_dicts]

        # ★ Pragma 정보 저장용
        self.pragma_directives: dict[str, str] = {}  # pragma_name -> pragma_value

    """
    Prev analysis part
    """

    # ────────────────────────────────────────────────────────────────
    #  Pragma 처리
    # ----------------------------------------------------------------
    def process_pragma_directive(self, pragma_name: str, pragma_value: str):
        """
        pragma directive를 처리하고 저장
        예: pragma solidity ^0.6.12;
        """
        self.pragma_directives[pragma_name] = pragma_value
        # 필요시 solidity 버전에 따른 처리 추가 가능

    # ────────────────────────────────────────────────────────────────
    #  ContractAnalyzer   (class body 안)
    # ----------------------------------------------------------------
    def _shift_cfg_meta(self, old_ln: int, new_ln: int):
        """
        소스 라인 이동(old_ln → new_ln)에 맞춰
        recorder.ledger / CFGNode.src_line / Statement.src_line 동기화.
        (line_info key 이동은 SolidityAnalyzer._shift_source_meta가 담당)
        """
        # ① line_info에 등록된 cfg_nodes들의 src_line 보정
        if old_ln in self.sa.line_info:
            info = self.sa.line_info[old_ln]
            if isinstance(info.get("cfg_nodes"), list):
                for node in info["cfg_nodes"]:
                    if hasattr(node, "src_line") and node.src_line == old_ln:
                        node.src_line = new_ln

        # ② recorder.ledger 이동
        if old_ln in self.recorder.ledger:
            self.recorder.ledger[new_ln] = self.recorder.ledger.pop(old_ln)

        # ③ 이미 생성된 CFG-Statement 들의 src_line 보정
        for ccf in self.contract_cfgs.values():
            for _, fcfg in ccf.iter_all_functions():
                for blk in fcfg.graph.nodes:
                    if getattr(blk, "src_line", None) == old_ln:
                        blk.src_line = new_ln
                    for st in blk.statements:
                        if getattr(st, "src_line", None) == old_ln:
                            st.src_line = new_ln

    def analyze_context(self, start_line, new_code):
        stripped_code = (new_code or "").strip()

        # 단독 '}'는 컨텍스트 분석 불필요 (괄호 정보만으로 충분)
        if stripped_code == "}":
            return

        # pragma, import는 contract 밖이므로 분석 불필요
        if stripped_code.startswith('pragma ') or stripped_code.startswith('import '):
            return

        if stripped_code.startswith('// @'):
            self.current_context_type = "debugUnit"
            self.current_target_contract = self.find_contract_context(start_line)
            self.current_target_function, self.current_target_function_param_types = self.find_function_context(start_line)
            return  # 이 함수 종료

        # 매 분석마다 초기화
        self.current_context_type = None
        self.current_target_contract = None
        self.current_target_function = None
        self.current_target_function_param_types = None
        self.current_target_struct = None

        # 새로 추가된 코드 블록의 컨텍스트를 분석
        if stripped_code.endswith(';'):
            if 'while' in stripped_code :
                self.current_context_type = "doWhileWhile"
                pass

            parent_context = self.find_parent_context(start_line)
            if parent_context in ["contract", "library", "interface",
                                  "abstract contract"]:  # 시작 규칙 : interactiveSourceUnit
                if parent_context == "interface":
                    # interface body: function 시그니처만 파서→visitor 경유로 처리
                    if stripped_code.startswith('function '):
                        self.current_context_type = "functionDefinition"
                        self.current_target_contract = self.find_contract_context(start_line)
                    else:
                        return  # event 등 non-function interface body는 스킵
                else:
                    if stripped_code.startswith('using '):
                        self.current_context_type = "usingDirective"
                    elif stripped_code.startswith('event '):
                        self.current_context_type = "event"
                    elif 'constant' in stripped_code or 'immutable' in stripped_code:
                        self.current_context_type = "constantVariableDeclaration"
                    else:
                        self.current_context_type = "stateVariableDeclaration"
                    self.current_target_contract = self.find_contract_context(start_line)
            elif parent_context == "struct":  # 시작 규칙 : interactiveStructUnit
                self.current_context_type = "structMember"
                self.current_target_contract = self.find_contract_context(start_line)
                self.current_target_struct = self.find_struct_context(start_line)
            else:  # constructor, function, --- # 시작 규칙 : interactiveBlockUnit
                self.current_context_type = "simpleStatement"
                self.current_target_contract = self.find_contract_context(start_line)
                self.current_target_function, self.current_target_function_param_types = self.find_function_context(start_line)

        elif ',' in stripped_code and '{' not in stripped_code:
            # 함수 정의인지 확인 (괄호 열고 닫힌 경우는 함수 파라미터로 가정)
            if '(' in stripped_code and ')' in stripped_code:
                self.current_context_type = "functionDefinition"
                self.current_target_contract = self.find_contract_context(start_line)
                self.current_target_function, self.current_target_function_param_types = self.find_function_context(start_line)

            # enum인지 확인
            else:
                parent_context = self.find_parent_context(start_line)
                if parent_context == "enum":
                    self.current_context_type = "enumMember"
                    self.current_target_contract = self.find_contract_context(start_line)

        elif '{' in stripped_code: # definition 및 block 관련
            # 여러 줄짜리 함수/modifier/constructor 정의의 마지막 줄일 수 있음
            # 예: "    ) external isAllowed {"
            # 이 경우 위로 올라가서 function/modifier/constructor를 찾아야 함
            if ')' in stripped_code and not stripped_code.startswith(('function', 'constructor', 'modifier', 'contract', 'struct', 'enum', 'if', 'for', 'while', 'else')):
                # 위로 올라가서 function/modifier/constructor 키워드 찾기
                for check_line in range(start_line - 1, 0, -1):
                    check_code = self.sa.full_code_lines.get(check_line, '').strip()
                    if check_code.startswith('function'):
                        self.current_context_type = 'functionDefinition'
                        self.current_target_contract = self.find_contract_context(start_line)
                        # print(f"[analyze_context] Line {start_line}: Found function, contract={self.current_target_contract}")
                        self.current_target_function = None  # 아직 함수가 생성되지 않음
                        return
                    elif check_code.startswith('modifier'):
                        self.current_context_type = 'modifier'
                        self.current_target_contract = self.find_contract_context(start_line)
                        return
                    elif check_code.startswith('constructor'):
                        self.current_context_type = 'constructor'
                        self.current_target_contract = self.find_contract_context(start_line)
                        return
                    # 빈 줄이나 파라미터 줄은 계속 위로
                    if not check_code or check_code.startswith(('address', 'uint', 'int', 'bool', 'string', 'bytes')):
                        continue
                    else:
                        break  # 다른 코드를 만나면 중단

            # Determine context type first
            ctx = self.determine_top_level_context(new_code)

            # statement 라인 (변수 선언, 대입 등)은 top-level context가 아님
            # BUT control flow (if/else/for/while etc) should be processed
            if ctx == 'simpleStatement':
                # function/constructor 내부의 일반 statement
                # current_context_type/contract/function은 그대로 유지
                return  # 더 이상 진행하지 않음
            elif '=' in stripped_code and ctx not in ['if', 'else_if', 'else', 'for', 'while', 'do_while', 'try', 'catch'] \
                    and not stripped_code.startswith(('function', 'constructor', 'modifier')):
                # 기타 assignment가 있는 statement
                return  # 더 이상 진행하지 않음
            else:
                self.current_context_type = ctx
                self.current_target_contract = self.find_contract_context(start_line)

            if self.current_context_type in ["contract", "library", "interface", "abstract contract"]:
                return

            self.current_target_function, self.current_target_function_param_types = self.find_function_context(start_line)


        # 최종적으로 context가 제대로 파악되지 않은 경우
        # 여러 줄짜리 정의문의 중간 줄이거나, 컨텍스트 분석이 불필요한 줄은 조용히 넘어감
        if not self.current_target_contract and self.current_context_type:
            # file-level struct/enum은 contract 바깥 → 스킵 (Phase 0에서 별도 수집)
            if self.current_context_type in ("struct", "structMember"):
                self.current_context_type = None
                return
            # context_type은 설정되었는데 contract를 찾지 못한 경우에만 오류
            raise ValueError(f"Contract context not found for line {start_line}")
        if self.current_context_type == "simpleStatement" and not self.current_target_function:
            raise ValueError(f"Function context not found for simple statement at line {start_line}")

    def find_parent_context(self, line_number):
        close_brace_count = 0

        # 위로 거슬러 올라가면서 `{`와 `}`의 짝을 찾기
        for line in range(line_number - 1, 0, -1):
            brace_info = self.sa.line_info.get(line, {'open': 0, 'close': 0, 'cfg_nodes': []})
            open_braces = brace_info['open']
            close_braces = brace_info['close']

            if close_brace_count > 0:
                close_brace_count -= open_braces
                if close_brace_count <= 0:
                    close_brace_count = 0
            else:
                if open_braces > 0:
                    return self.determine_top_level_context(self.sa.full_code_lines[line])
                close_brace_count += close_braces

        return "unknown"

    def find_contract_context(self, line_number):
        # 위로 거슬러 올라가면서 해당 라인이 속한 컨트랙트를 찾습니다.
        close_brace_count = 0

        for line in range(line_number, 0, -1):
            brace_info = self.sa.line_info.get(line, {'open': 0, 'close': 0, 'cfg_nodes': []})
            open_braces = brace_info['open']
            close_braces = brace_info['close']

            # '}' 카운팅: 닫힌 괄호를 먼저 센다
            if close_brace_count > 0:
                close_brace_count -= open_braces
                if close_brace_count <= 0:
                    close_brace_count = 0
            else:
                # '{' 발견: 이 라인이 컨트랙트 선언인지 확인
                if open_braces > 0:
                    code_line = self.sa.full_code_lines.get(line, '').strip()
                    context_type = self.determine_top_level_context(code_line)
                    if context_type in ["contract", "library", "interface", "abstract contract"]:
                        # contract 이름 추출
                        parts = code_line.split()
                        # "abstract contract Name" or "contract Name" 형식
                        if "contract" in parts:
                            idx = parts.index("contract")
                            if idx + 1 < len(parts):
                                result = parts[idx + 1].split('{')[0].strip()
                                return result
                        elif "library" in parts:
                            idx = parts.index("library")
                            if idx + 1 < len(parts):
                                result = parts[idx + 1].split('{')[0].strip()
                                return result
                        elif "interface" in parts:
                            idx = parts.index("interface")
                            if idx + 1 < len(parts):
                                result = parts[idx + 1].split('{')[0].strip()
                                return result
                # 닫힌 괄호 누적
                close_brace_count += close_braces

        return None

    @staticmethod
    def _extract_param_types(full_sig: str) -> list[str] | None:
        """함수 시그니처 문자열에서 파라미터 타입 목록 추출.
        예: 'function sub(uint256 a, uint256 b, string memory errorMessage) ...'
            → ['uint256', 'uint256', 'string']
        """
        paren_start = full_sig.find('(')
        if paren_start < 0:
            return None
        # 첫 번째 '(' ~ 매칭되는 ')' 범위 추출
        depth = 0
        paren_end = -1
        for i in range(paren_start, len(full_sig)):
            if full_sig[i] == '(':
                depth += 1
            elif full_sig[i] == ')':
                depth -= 1
                if depth == 0:
                    paren_end = i
                    break
        if paren_end < 0:
            return None
        inner = full_sig[paren_start + 1:paren_end].strip()
        if not inner:
            return []
        param_types = []
        for param in inner.split(','):
            tokens = param.strip().split()
            if tokens:
                # 첫 토큰이 타입 (memory/storage/calldata 제외)
                param_types.append(tokens[0])
        return param_types

    def find_function_context(self, line_number):
        """위로 거슬러 올라가면서 해당 라인이 속한 함수를 찾고,
        (함수이름, 파라미터타입리스트) 튜플을 반환한다.
        overload 구분을 위해 파라미터 타입 정보도 추출한다."""

        # 먼저 가장 가까운 '{' 문자가 있는 라인을 찾기
        open_brace_line = None
        close_brace_count = 0

        for line in range(line_number, 0, -1):
            brace_info = self.sa.line_info.get(line, {'open': 0, 'close': 0, 'cfg_nodes': []})
            open_braces = brace_info['open']
            close_braces = brace_info['close']

            if close_brace_count > 0:
                close_brace_count -= open_braces
                if close_brace_count <= 0:
                    close_brace_count = 0
            else:
                if open_braces > 0:
                    open_brace_line = line
                    break
                close_brace_count += close_braces

        if open_brace_line is None:
            return None, None

        # '{' 문자가 있는 라인부터 위로 올라가면서 function/constructor/modifier 키워드를 찾기
        for line in range(open_brace_line, 0, -1):
            code_line = self.sa.full_code_lines.get(line, "").strip()
            if not code_line:
                continue

            # function, constructor, modifier 키워드를 찾으면 함수 이름 + 파라미터 추출
            if code_line.startswith("function "):
                parts = code_line.split()
                if len(parts) >= 2:
                    function_name = parts[1].split('(')[0]
                    # 파라미터 타입 추출 — multi-line 대응
                    full_sig = code_line
                    if '(' in full_sig and ')' not in full_sig:
                        for next_ln in range(line + 1, open_brace_line + 1):
                            full_sig += " " + self.sa.full_code_lines.get(next_ln, "").strip()
                            if ')' in full_sig:
                                break
                    param_types = self._extract_param_types(full_sig)
                    # type alias resolve (UFixed18 → uint256 등)
                    if param_types:
                        param_types = [self.sa.type_aliases.get(t, t) for t in param_types]
                    return function_name, param_types
            elif code_line.startswith("constructor"):
                # constructor 파라미터도 추출
                full_sig = code_line
                if '(' in full_sig and ')' not in full_sig:
                    for next_ln in range(line + 1, open_brace_line + 1):
                        full_sig += " " + self.sa.full_code_lines.get(next_ln, "").strip()
                        if ')' in full_sig:
                            break
                param_types = self._extract_param_types(full_sig)
                if param_types:
                    param_types = [self.sa.type_aliases.get(t, t) for t in param_types]
                return "constructor", param_types
            elif code_line.startswith("modifier "):
                parts = code_line.split()
                if len(parts) >= 2:
                    modifier_name = parts[1].split('(')[0]
                    return modifier_name, None
            elif code_line.startswith("fallback"):
                return "fallback", None
            elif code_line.startswith("receive"):
                return "receive", None

            # contract/struct/interface 등을 만나면 함수가 아니므로 중단
            if any(code_line.startswith(kw) for kw in ["contract ", "library ", "interface ", "struct ", "enum "]):
                break

        return None, None

    def find_struct_context(self, line_number):
        # 위로 거슬러 올라가면서 해당 라인이 속한 함수를 찾습니다.
        for line in range(line_number, 0, -1):
            brace_info = self.sa.line_info.get(line, {'open': 0, 'close': 0, 'cfg_nodes': []})
            cfg_nodes = brace_info.get('cfg_nodes', [])
            if brace_info['open'] > 0 and cfg_nodes:
                context_type = self.determine_top_level_context(self.sa.full_code_lines[line])
                if context_type == "struct":
                    return self.sa.full_code_lines[line].split()[1]

    def determine_top_level_context(self, code_line):
        try:
            # 코드 라인의 내용에 따라 최상위 컨텍스트를 결정
            stripped_code = code_line.strip()

            if stripped_code.startswith("abstract contract"):
                return "abstract contract"
            elif stripped_code.startswith("contract"):
                return "contract"
            elif stripped_code.startswith("interface"):
                return "interface"
            elif stripped_code.startswith("library"):
                return "library"
            elif stripped_code.startswith("function"):
                return "functionDefinition"
            elif stripped_code.startswith("constructor"):
                return "constructor"
            elif stripped_code.startswith("fallback"):
                return "fallback"
            elif stripped_code.startswith("receive"):
                return "receive"
            elif stripped_code.startswith("modifier"):
                return "modifier"
            elif stripped_code.startswith("struct"):
                return "struct"
            elif stripped_code.startswith("enum"):
                return "enum"
            elif stripped_code.startswith("event"):
                return "event"
            elif stripped_code.startswith("if"):
                return "if"
            elif stripped_code.startswith("else if"):
                return "else_if"
            elif stripped_code.startswith("else"):
                return "else"
            elif stripped_code.startswith("for"):
                return "for"
            elif stripped_code.startswith("while"):
                return "while"
            elif stripped_code.startswith("do"):
                return "do_while"
            elif stripped_code.startswith("try"):
                return "try"
            elif stripped_code.startswith("catch"):
                return "catch"
            elif stripped_code.startswith("assembly"):
                return "assembly"
            elif stripped_code.startswith("unchecked"):
                return "unchecked"
            elif stripped_code.startswith("return") :
                return "return"
            else:
                # User-defined type 변수 선언 또는 일반 statement
                # (예: LockedStake memory x = ..., mapping assignment 등)
                return "simpleStatement"

        except ValueError as e:
            print(f"Error: {e}")
            return "unknown"

    def get_current_context_type(self):
        return self.current_context_type

    """
    cfg part    
    """

    # ContractAnalyzer.py  (일부)

    def make_contract_cfg(self, contract_name: str, parent_contracts: list = None):
        """
        contract-level CFG를 처음 만들 때 한 번 호출.
        address 계열 글로벌은 UnsignedIntegerInterval(160bit) 로,
        uint  계열은 [0,0] 256-bit Interval 로 초기화한다.
        """
        self.current_target_contract = contract_name
        cfg = StaticCFGFactory.make_contract_cfg(self, contract_name)
        if parent_contracts:
            cfg.parent_contracts = parent_contracts
            for pname in parent_contracts:
                if pname in self.contract_cfgs:
                    cfg.parent_cfgs[pname] = self.contract_cfgs[pname]
            self._inherit_using_libraries(cfg)

        if self.current_start_line and self.current_start_line in self.sa.line_info:
            self.sa.line_info[self.current_start_line]['cfg_nodes'] = [cfg]

    def make_abstract_contract_cfg(self, contract_name: str, parent_contracts: list = None):
        """
        abstract contract-level CFG를 처음 만들 때 한 번 호출.
        abstract contract는 직접 배포할 수 없지만 상속용으로 등록.
        """
        self.current_target_contract = contract_name
        cfg = StaticCFGFactory.make_contract_cfg(self, contract_name)
        cfg.is_abstract = True
        if parent_contracts:
            cfg.parent_contracts = parent_contracts
            for pname in parent_contracts:
                if pname in self.contract_cfgs:
                    cfg.parent_cfgs[pname] = self.contract_cfgs[pname]
            self._inherit_using_libraries(cfg)

        if self.current_start_line and self.current_start_line in self.sa.line_info:
            self.sa.line_info[self.current_start_line]['cfg_nodes'] = [cfg]

    def _inherit_using_libraries(self, cfg):
        """부모 contract의 using_libraries / using_all_libraries를 자식 cfg에 상속"""
        for parent_cfg in cfg.parent_cfgs.values():
            for target_type, libs in parent_cfg.using_libraries.items():
                for lib in (libs if isinstance(libs, list) else [libs]):
                    cfg.add_using_library(lib, target_type)
            for lib in parent_cfg.using_all_libraries:
                cfg.add_using_library(lib, None)

    def make_library_cfg(self, library_name: str):
        """
        library-level CFG를 처음 만들 때 한 번 호출.
        라이브러리는 state variable이 없고 함수만 포함한다.
        """
        from Utils.CFG import LibraryCFG

        self.current_target_contract = library_name  # 라이브러리도 contract로 처리
        library_cfg = LibraryCFG(library_name)
        library_cfg.globals = StaticCFGFactory._create_global_variables(self)

        # 라이브러리 CFG를 저장
        self.library_cfgs[library_name] = library_cfg
        self.contract_cfgs[library_name] = library_cfg  # 호환성을 위해 contract_cfgs에도 저장

        if self.current_start_line and self.current_start_line in self.sa.line_info:
            self.sa.line_info[self.current_start_line]['cfg_nodes'] = [library_cfg]

    def make_interface_cfg(self, interface_name: str, parent_interfaces: list = None):
        """
        Interface 선언 처리. ContractCFG를 생성하고 is_interface=True로 설정.
        contract_cfgs에 등록하여 brace tracking, context 추적이 정상 동작하게 한다.
        Interface 함수는 body 없이 FunctionCFG(entry→exit)로 등록.
        """
        self.current_target_contract = interface_name
        self.interface_names.add(interface_name)

        cfg = ContractCFG(interface_name)
        cfg.is_interface = True
        self.contract_cfgs[interface_name] = cfg

        if parent_interfaces:
            cfg.parent_contracts = parent_interfaces
            for p in parent_interfaces:
                self.interface_names.add(p)
                if p in self.contract_cfgs:
                    cfg.parent_cfgs[p] = self.contract_cfgs[p]

        if self.current_start_line and self.current_start_line in self.sa.line_info:
            self.sa.line_info[self.current_start_line]['cfg_nodes'] = [cfg]


    # for interactiveEnumDefinition in Solidity.g4
    def process_enum_definition(self, enum_name):
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)

        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 새로운 EnumDefinition 객체 생성
        enum_def = EnumDefinition(enum_name)
        contract_cfg.define_enum(enum_name, enum_def)

        # brace_count 업데이트
        self.sa.line_info[self.current_start_line]['cfg_nodes'] = [enum_def]

    def process_enum_item(self, items):
        # 현재 타겟 컨트랙트의 CFG 가져오기
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)

        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # brace_count에서 가장 최근의 enum 정의를 찾습니다.
        enum_def = None
        for line in reversed(range(self.current_start_line + 1)):
            context = self.sa.line_info.get(line)
            if context:
                cfg_nodes = context.get('cfg_nodes', [])
                if cfg_nodes and isinstance(cfg_nodes[0], EnumDefinition):
                    enum_def = cfg_nodes[0]
                    break

        if enum_def is not None:
            # EnumDefinition에 아이템 추가
            for item in items:
                enum_def.add_member(item)
        else:
            raise ValueError(f"Unable to find EnumDefinition context for line {self.current_start_line}")

    def process_using_directive(self, library_name: str, target_type: str | None):
        """
        using LibraryName for TypeName; 또는 using LibraryName for *; 처리
        - target_type이 None이면 모든 타입에 적용 (using_all_libraries)
        - target_type이 있으면 해당 타입에만 적용 (using_libraries)
        """
        import pickle
        import os

        # ContractCFG 또는 LibraryCFG에서 using directive 등록
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)
        if not contract_cfg:
            # library 내부의 using directive인지 확인
            contract_cfg = self.library_cfgs.get(self.current_target_contract)
        if not contract_cfg:
            return  # 컨트랙트/라이브러리 밖의 using directive는 무시

        # 라이브러리 CFG 로드 — library_cfgs 우선, pkl fallback
        library_cfg = self.library_cfgs.get(library_name)

        if library_cfg is None:
            base_dir = os.path.dirname(__file__)
            search_paths = [
                os.path.join(base_dir, "..", "Dependencies", "objectfile", f"lib_{library_name}.pkl"),
                os.path.join(base_dir, "..", "Libraries", "objectfile", f"{library_name}.pkl"),
            ]
            for pkl_path in search_paths:
                if os.path.exists(pkl_path):
                    try:
                        with open(pkl_path, "rb") as f:
                            raw = pickle.load(f)
                        library_cfg = raw["cfg"] if isinstance(raw, dict) and "cfg" in raw else raw
                        break
                    except Exception:
                        pass

        if library_cfg is None:
            return

        # LibraryCFG를 using_libraries/using_all_libraries에 등록
        # 자식 contract가 명시적으로 선언한 using은 부모로부터 상속된 것보다 우선되어야 하므로
        # 리스트 앞쪽(우선순위 높음)에 삽입
        contract_cfg.add_using_library(library_cfg, target_type, prepend=True)

    def resolve_library_struct(self, library_name: str, member_name: str):
        """
        Library.Struct qualified name을 resolve.
        using_libraries에 등록된 LibraryCFG들과 library_cfgs에서 검색.
        """
        # 1) 현재 contract/library의 using_libraries에서 검색
        ccfg = self.contract_cfgs.get(self.current_target_contract) or \
               self.library_cfgs.get(self.current_target_contract)
        if ccfg:
            all_libs = []
            for libs in ccfg.using_libraries.values():
                all_libs.extend(libs if isinstance(libs, list) else [libs])
            all_libs.extend(ccfg.using_all_libraries)
            for lib in all_libs:
                if getattr(lib, 'library_name', None) == library_name:
                    if member_name in lib.structDefs:
                        return lib.structDefs[member_name]
                    if member_name in lib.enumDefs:
                        return lib.enumDefs[member_name]

        # 2) library_cfgs에서 직접 검색 (현재 분석 중인 library)
        lib = self.library_cfgs.get(library_name)
        if lib:
            if member_name in lib.structDefs:
                return lib.structDefs[member_name]

        # 3) pkl에서 직접 로드 (fallback: library + interface + contract)
        import pickle, os
        base_dir = os.path.dirname(__file__)
        for pkl_path in [
            os.path.join(base_dir, "..", "Dependencies", "objectfile", f"lib_{library_name}.pkl"),
            os.path.join(base_dir, "..", "Libraries", "objectfile", f"{library_name}.pkl"),
            os.path.join(base_dir, "..", "Dependencies", "objectfile", f"ifc_{library_name}.pkl"),
            os.path.join(base_dir, "..", "Dependencies", "objectfile", f"con_{library_name}.pkl"),
        ]:
            if os.path.exists(pkl_path):
                try:
                    with open(pkl_path, "rb") as f:
                        raw = pickle.load(f)
                    cfg = raw["cfg"] if isinstance(raw, dict) and "cfg" in raw else raw
                    if member_name in cfg.structDefs:
                        return cfg.structDefs[member_name]
                    if hasattr(cfg, 'enumDefs') and member_name in cfg.enumDefs:
                        return cfg.enumDefs[member_name]
                except Exception:
                    pass
        return None

    # for interactiveStructDefinition in Solidity.g4
    def process_struct_definition(self, struct_name):
        contract_cfg = self.contract_cfgs[self.current_target_contract]

        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        struct_def = StructDefinition(struct_name=struct_name)

        contract_cfg.define_struct(struct_def)

        # 10. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # brace_count 업데이트
        self.sa.line_info[self.current_start_line]['cfg_nodes'] = [contract_cfg.structDefs]

    def process_struct_member(self, var_name, type_obj):
        # 1. 현재 타겟 컨트랙트의 CFG를 가져옴
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 2. 현재 타겟 구조체를 확인하고 멤버 추가
        if not self.current_target_struct:
            raise ValueError("No target struct to add members to.")

        contract_cfg.add_struct_member(self.current_target_struct, var_name, type_obj)

        # 10. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

    def process_state_variable(self, variable_obj, init_expr=None):
        # 1. 현재 타겟 컨트랙트의 CFG 가져오기
        contract_cfg = self.contract_cfgs[self.current_target_contract]

        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        if not contract_cfg.state_variable_node:
            contract_cfg.initialize_state_variable_node()

        # 우변 표현식을 저장하기 위해 init_expr를 확인
        if init_expr is None: # 초기화가 없으면
            if isinstance(variable_obj, ArrayVariable) :
                # arrayBaseType이 elementary type인 경우에만 elementaryTypeName 체크
                if variable_obj.typeInfo.arrayBaseType.typeCategory == "elementary":
                    if variable_obj.typeInfo.arrayBaseType.elementaryTypeName.startswith("int") :
                        variable_obj.initialize_elements(IntegerInterval(0, 0, 256))
                    elif variable_obj.typeInfo.arrayBaseType.elementaryTypeName.startswith("uint") :
                        variable_obj.initialize_elements(UnsignedIntegerInterval(0, 0, 256))
                    elif variable_obj.typeInfo.arrayBaseType.elementaryTypeName.startswith("bool") :
                        variable_obj.initialize_elements(BoolInterval(0, 0))
                    elif variable_obj.typeInfo.arrayBaseType.elementaryTypeName in ["address", "address payable", "string", "bytes", "Byte", "Fixed", "Ufixed"] :
                        variable_obj.initialize_not_abstracted_type()
                # struct, enum 등 다른 타입의 배열은 동적으로 초기화됨 (필요 시)
            elif isinstance(variable_obj, StructVariable) :
                struct_name = variable_obj.typeInfo.structTypeName
                if struct_name in contract_cfg.structDefs:
                    struct_def = contract_cfg.structDefs[struct_name]
                    variable_obj.initialize_struct(struct_def, struct_defs=contract_cfg.structDefs)
                elif self.sa.get_file_level_struct(struct_name) is not None:
                    # file-level struct fallback
                    all_defs = dict(contract_cfg.structDefs)
                    all_defs.update(self.sa.file_level_structs)
                    variable_obj.initialize_struct(self.sa.file_level_structs[struct_name], struct_defs=all_defs)
                else :
                    raise ValueError(f"This struct def {struct_name} is undefined")
            elif isinstance(variable_obj, MappingVariable) :
                # struct/enum value type 지원을 위해 정의 전달
                # 현재 contract + file-level + parent 체인 합산
                all_structs = dict(contract_cfg.structDefs)
                all_enums = dict(contract_cfg.enumDefs)
                if self.sa.file_level_structs:
                    all_structs.update(self.sa.file_level_structs)
                for pcfg in getattr(contract_cfg, 'parent_cfgs', {}).values():
                    all_structs.update(getattr(pcfg, 'structDefs', {}))
                    all_enums.update(getattr(pcfg, 'enumDefs', {}))
                variable_obj.struct_defs = all_structs
                variable_obj.enum_defs = all_enums
            elif isinstance(variable_obj,EnumVariable) :
                pass
            elif variable_obj.typeInfo.typeCategory == "interface" or \
                 (hasattr(variable_obj.typeInfo, 'interfaceName') and variable_obj.typeInfo.interfaceName):
                # interface 타입 state variable → AddressSet.top() + _cast_interface
                ifc_name = variable_obj.typeInfo.interfaceName or variable_obj.typeInfo.elementaryTypeName
                if ifc_name:
                    variable_obj.value = AddressSet.top()
                    variable_obj.value._cast_interface = ifc_name
            elif variable_obj.typeInfo.typeCategory == "elementary":
                et = variable_obj.typeInfo.elementaryTypeName
                # ── ① int / uint / bool 은 종전 로직 유지
                if et.startswith(("int", "uint", "bool")):
                    variable_obj.value = self.evaluator.calculate_default_interval(et)
                elif et == "address":
                    # 초기화식이 없으면 TOP AddressSet
                    variable_obj.value = AddressSet.top()
                elif et.startswith("bytes") and len(et) > 5:  # bytes32, bytes16 등
                    # bytes32의 기본값은 bytes32(0)
                    variable_obj.value = self.evaluator.calculate_default_interval(et)
                # (string / bytes 등 - 추상화 안 할 타입은 심볼릭 문자열 그대로)
                else:
                    variable_obj.value = f"symbol_{variable_obj.identifier}"
        else : # 초기화 식이 있으면
            if isinstance(variable_obj, ArrayVariable) :
                inlineArrayValues = self.evaluator.evaluate_expression(
                    init_expr,
                    contract_cfg.state_variable_node.variables,
                    None,
                    None)

                for value in inlineArrayValues :
                    variable_obj.elements.append(value)
            elif isinstance(variable_obj, StructVariable) : # 관련된 경우 없을듯
                pass
            elif isinstance(variable_obj, MappingVariable) : # 관련된 경우 없을 듯
                pass
            elif variable_obj.typeInfo.typeCategory == "elementary" :
                variable_obj.value = self.evaluator.evaluate_expression(
                    init_expr,
                    contract_cfg.state_variable_node.variables,
                    None,
                    None)

        self.register_var(variable_obj)

        # 4. 상태 변수를 ContractCFG에 추가
        contract_cfg.add_state_variable(variable_obj, expr=init_expr, line_no=self.current_start_line)

        # 5. ContractCFG에 있는 모든 FunctionCFG에 상태 변수 추가
        #    copy를 저장하여 분석 중 _make_bottom() in-place mutation이 전파되지 않도록 함
        for _, function_cfg in contract_cfg.iter_all_functions():
            function_cfg.add_related_variable(variable_obj.identifier, VariableEnv.copy_single_variable(variable_obj))

        # 6. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 7. brace_count 업데이트
        self.sa.line_info[self.current_start_line]['cfg_nodes'] = [contract_cfg.state_variable_node]

    # ---------------------------------------------------------------------------
    # ② constant 변수 처리 (CFG·심볼 테이블 반영)
    # ---------------------------------------------------------------------------
    def process_constant_variable(self, variable_obj, init_expr):
        # 1. 컨트랙트 CFG 확보
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if contract_cfg is None:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 2. 반드시 초기화식이 있어야 함 (constant 변수는 항상 초기화 필요)
        if init_expr is None:
            raise ValueError(f"Constant variable '{variable_obj.identifier}' must have an initializer.")

        # 3. constant로 선언 불가능한 타입 검증
        if isinstance(variable_obj, (ArrayVariable, StructVariable, MappingVariable)):
            type_name = type(variable_obj).__name__.replace('Variable', '').lower()
            raise ValueError(
                f"{type_name.capitalize()} variables cannot be declared as constant: '{variable_obj.identifier}'")

        if not contract_cfg.state_variable_node:
            contract_cfg.initialize_state_variable_node()

        # 4. 평가 컨텍스트는 현재까지의 state-variable 노드 변수들
        state_vars = contract_cfg.state_variable_node.variables

        # 5. constant 표현식 평가 (value types와 string만 지원)
        if isinstance(variable_obj, EnumVariable):
            # 열거형도 value type이므로 지원
            value = self.evaluator.evaluate_expression(init_expr, state_vars, None, None)
            if value is None:
                raise ValueError(f"Unable to evaluate constant enum expression for '{variable_obj.identifier}'")
            variable_obj.value = value
        elif variable_obj.typeInfo.typeCategory == "elementary":
            # value types (int, uint, bool, address 등)과 string 지원
            et = variable_obj.typeInfo.elementaryTypeName
            if et in ["string", "bytes"] or et.startswith(("int", "uint", "bool")) or et == "address":
                value = self.evaluator.evaluate_expression(init_expr, state_vars, None, None)
                if value is None:
                    raise ValueError(f"Unable to evaluate constant expression for '{variable_obj.identifier}'")
                variable_obj.value = value
            else:
                raise ValueError(f"Type '{et}' cannot be declared as constant: '{variable_obj.identifier}'")
        elif variable_obj.typeInfo.typeCategory == "interface":
            # interface 타입 constant (e.g., IUniswapV2Router02 public constant x = IUniswapV2Router02(addr))
            # → address로 취급
            value = self.evaluator.evaluate_expression(init_expr, state_vars, None, None)
            if value is not None:
                variable_obj.value = value
            else:
                from Domain.AddressSet import AddressSet
                variable_obj.value = AddressSet.top()
        else:
            # 기타 지원되지 않는 타입
            raise ValueError(
                f"Type category '{variable_obj.typeInfo.typeCategory}' cannot be declared as constant: '{variable_obj.identifier}'")

        variable_obj.isConstant = True  # constant 플래그 설정

        self.register_var(variable_obj)

        # 3. ContractCFG 에 추가 (state 변수와 동일 API 사용)
        contract_cfg.add_state_variable(variable_obj, expr=init_expr, line_no=self.current_start_line)

        # 4. 이미 생성된 모든 FunctionCFG 에 read-only 변수로 연동
        for _, fn_cfg in contract_cfg.iter_all_functions():
            fn_cfg.add_related_variable(variable_obj.identifier, VariableEnv.copy_single_variable(variable_obj))

        # 5. 전역 map 업데이트
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 6. brace_count 갱신 → IDE/커서 매핑
        self.sa.line_info[self.current_start_line]["cfg_nodes"] = [contract_cfg.state_variable_node]

    def process_modifier_definition(self,
                                    modifier_name: str,
                                    parameters: dict[str, SolType] | None = None) -> None:
        """
        modifier 정의를 분석하여 FunctionCFG 로 등록
        parameters: { param_name : SolType, ... }  또는 None
        """
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if contract_cfg is None:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        mod_cfg = StaticCFGFactory.make_modifier_cfg(self, contract_cfg, modifier_name, parameters)

        # 3) CFG 저장
        self.sa.line_info[self.current_start_line]['cfg_nodes'] = [mod_cfg.get_entry_node()]
        self.sa.line_info[self.current_end_line]['cfg_nodes'] = [mod_cfg.get_exit_node()]

    # ContractAnalyzer.py  ----------------------------------------------

    def process_modifier_invocation(self,
                                    fn_cfg: FunctionCFG,
                                    modifier_name: str) -> None:
        """
        fn_cfg  ← 방금 만들고 있는 함수-CFG
        modifier_name  ← 'onlyOwner' 처럼 한 개

        ① 컨트랙트에 등록돼 있는 modifier-CFG 가져오기 (상속된 modifier 포함)
        ② modifier-CFG 를 *얕은 복사* 하여 fn_cfg.graph 에 붙인다.
        ③ placeholder 노드(들)를 fn-entry/exit 로 스플라이스
        """

        contract_cfg = self.contract_cfgs[self.current_target_contract]

        # ── ① modifier 존재 확인 (현재 컨트랙트 + 부모 컨트랙트) ────────
        mod_cfg: FunctionCFG | None = None

        # 현재 컨트랙트에서 찾기
        mod_cfg = contract_cfg.get_function_cfg(modifier_name)
        if mod_cfg is None:
            # 부모 컨트랙트에서 찾기
            for parent_name in getattr(contract_cfg, 'parent_contracts', []):
                parent_cfg = self.contract_cfgs.get(parent_name)
                if parent_cfg:
                    mod_cfg = parent_cfg.get_function_cfg(modifier_name)
                    if mod_cfg is not None:
                        break

        if mod_cfg is None:
            raise ValueError(f"Modifier '{modifier_name}' is not defined.")

        self.builder.splice_modifier(fn_cfg, mod_cfg, modifier_name)

    def process_constructor_definition(self, name, params, modifiers):
        ccf = self.contract_cfgs[self.current_target_contract]

        ctor_cfg = StaticCFGFactory.make_constructor_cfg(
            self, name, params, modifiers
        )
        ccf.add_constructor_to_cfg(ctor_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

        # brace_count - 디폴트 entry 등록
        self.sa.line_info[self.current_start_line]["cfg_nodes"] = [ctor_cfg.get_entry_node()]

        # EXIT 노드를 end line에 등록 (body 문장이 forward 검색 시 찾을 수 있도록)
        if self.current_end_line not in self.sa.line_info:
            self.sa.line_info[self.current_end_line] = {"open": 0, "close": 0, "cfg_nodes": []}
        exit_node = ctor_cfg.get_exit_node()
        if exit_node not in self.sa.line_info[self.current_end_line]["cfg_nodes"]:
            self.sa.line_info[self.current_end_line]["cfg_nodes"].append(exit_node)

    # ContractAnalyzer.py  ─ process_function_definition  (address-symb ✚ 최신 Array/Struct 초기화 반영)

    def process_function_definition(
            self,
            function_name: str,
            parameters: list[tuple[SolType, str]],
            modifiers: list[str],
            returns: list[Variables] | None,
            mutability: str | None = None,
    ):
        # ★ 이전 함수 분석 완료 처리 - pending_calls 재분석
        if self.current_target_function and self.current_target_function in self.pending_calls:
            prev_func = self.current_target_function
            for (caller_fcfg, call_node) in self.pending_calls[prev_func]:
                self.engine.reinterpret_from(caller_fcfg, call_node)
            del self.pending_calls[prev_func]

        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if contract_cfg is None:
            raise ValueError(f"Contract CFG for {self.current_target_contract} not found.")

        # Interface 함수: body 없이 entry→exit + return_types만 등록
        if getattr(contract_cfg, 'is_interface', False):
            fcfg = FunctionCFG(function_type="function", function_name=function_name)
            fcfg.mutability = mutability
            for r_type, r_name in (returns or []):
                fcfg.return_types.append(r_type)
            contract_cfg.add_function_cfg(function_name, fcfg)
            if self.current_start_line in self.sa.line_info:
                self.sa.line_info[self.current_start_line]["cfg_nodes"] = [fcfg.get_entry_node()]
            return

        fcfg = StaticCFGFactory.make_function_cfg(self, function_name, parameters, modifiers, returns)
        fcfg.mutability = mutability

        contract_cfg.add_function_cfg(function_name, fcfg)
        self.contract_cfgs[self.current_target_contract] = contract_cfg
        self.sa.line_info[self.current_start_line]["cfg_nodes"] = [fcfg.get_entry_node()]
        # Don't overwrite existing nodes in line_info for end_line, just add EXIT if not present
        if self.current_end_line not in self.sa.line_info:
            self.sa.line_info[self.current_end_line] = {"open": 0, "close": 0, "cfg_nodes": []}
        exit_node = fcfg.get_exit_node()
        if exit_node not in self.sa.line_info[self.current_end_line]["cfg_nodes"]:
            self.sa.line_info[self.current_end_line]["cfg_nodes"].append(exit_node)

    def _create_variable_object(
            self,
            type_obj: SolType,
            var_name: str,
            ccf
    ) -> Variables | ArrayVariable | StructVariable | MappingVariable | EnumVariable:
        """
        Helper function to create a variable object based on type information.
        """
        v: Variables | ArrayVariable | StructVariable | MappingVariable | EnumVariable

        # 2-A  배열
        if type_obj.typeCategory == "array":
            v = ArrayVariable(
                identifier=var_name,
                base_type=type_obj.arrayBaseType,
                array_length=type_obj.arrayLength,
                is_dynamic=type_obj.isDynamicArray,
                scope="local",
            )

        # 2-B  구조체
        elif type_obj.typeCategory == "struct":
            v = StructVariable(
                identifier=var_name,
                struct_type=type_obj.structTypeName,
                scope="local",
            )

        # 2-C  enum
        elif type_obj.typeCategory == "enum":
            v = EnumVariable(identifier=var_name, enum_type=type_obj.enumTypeName, scope="local")

        # 2-D  매핑
        elif type_obj.typeCategory == "mapping":
            ccf_local = self.contract_cfgs.get(self.current_target_contract)
            all_structs = dict(ccf_local.structDefs) if ccf_local else {}
            all_enums = dict(ccf_local.enumDefs) if ccf_local else {}
            if self.sa.file_level_structs:
                all_structs.update(self.sa.file_level_structs)
            if ccf_local:
                for pcfg in getattr(ccf_local, 'parent_cfgs', {}).values():
                    all_structs.update(getattr(pcfg, 'structDefs', {}))
                    all_enums.update(getattr(pcfg, 'enumDefs', {}))
            v = MappingVariable(
                identifier=var_name,
                key_type=type_obj.mappingKeyType,
                value_type=type_obj.mappingValueType,
                scope="local",
                struct_defs=all_structs,
                enum_defs=all_enums,
            )

        # 2-E  elementary
        else:
            v = Variables(identifier=var_name, scope="local")
            v.typeInfo = type_obj

        return v

    def process_variable_declaration(
            self,
            type_obj: SolType,
            var_name: str,
            init_expr: Expression | None = None
    ):

        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("variableDeclaration: active FunctionCFG not found")
        fcfg = self.current_target_function_cfg

        cur_blk = self.builder.get_current_block()

        # ───────────────────────────────────────────────────────────────
        # 2. 변수 객체 생성 (헬퍼 함수 사용)
        # ----------------------------------------------------------------
        v = self._create_variable_object(type_obj, var_name, ccf)

        if init_expr is None:
            # ── 배열 기본
            if isinstance(v, ArrayVariable):
                bt = v.typeInfo.arrayBaseType
                if isinstance(bt, SolType):
                    et = bt.elementaryTypeName
                    if et and et.startswith("int"):
                        bits = bt.intTypeLength or 256
                        v.initialize_elements(IntegerInterval.top(bits))
                    elif et and et.startswith("uint"):
                        bits = bt.intTypeLength or 256
                        v.initialize_elements(UnsignedIntegerInterval.top(bits))
                    elif et == "bool":
                        v.initialize_elements(BoolInterval.top())
                    else:
                        v.initialize_not_abstracted_type()

            # ── 구조체 기본
            elif isinstance(v, StructVariable):
                struct_name = v.typeInfo.structTypeName
                if struct_name in ccf.structDefs:
                    v.initialize_struct(ccf.structDefs[struct_name], struct_defs=ccf.structDefs)
                elif self.sa.get_file_level_struct(struct_name) is not None:
                    all_defs = dict(ccf.structDefs)
                    all_defs.update(self.sa.file_level_structs)
                    v.initialize_struct(self.sa.file_level_structs[struct_name], struct_defs=all_defs)
                else:
                    raise ValueError(f"Undefined struct {struct_name}")

            # ── enum 기본 (첫 멤버)
            elif isinstance(v, EnumVariable):
                enum_def = ccf.enumDefs.get(v.typeInfo.enumTypeName)
                if enum_def:
                    v.valueIndex = 0
                    v.value = enum_def.members[0]

            # ── interface 타입 기본
            elif isinstance(v, Variables) and \
                 (v.typeInfo.typeCategory == "interface" or
                  (hasattr(v.typeInfo, 'interfaceName') and v.typeInfo.interfaceName)):
                ifc_name = v.typeInfo.interfaceName
                if ifc_name:
                    v.value = AddressSet.top()
                    v.value._cast_interface = ifc_name

            # ── elementary 기본
            elif isinstance(v, Variables):
                et = v.typeInfo.elementaryTypeName
                if et.startswith("int"):
                    type_len = v.typeInfo.intTypeLength or 256
                    v.value = IntegerInterval.top(type_len)
                elif et.startswith("uint"):
                    type_len = v.typeInfo.intTypeLength or 256
                    v.value = UnsignedIntegerInterval.top(type_len)
                elif et == "bool":
                    v.value = BoolInterval.top()
                elif et == "address":
                    v.value = AddressSet.top()
                elif et.startswith("bytes") and len(et) > 5:  # bytes32, bytes16 등
                    from Domain.BytesSet import BytesSet
                    byte_size = int(et[5:])  # "bytes32" -> 32
                    v.value = BytesSet.top(byte_size)
                else:  # bytes/string
                    v.value = f"symbol_{var_name}"

        # ───────────────────────────────────────────────────────────────
        # 3-b. 초기화식이 존재하는 경우
        # ----------------------------------------------------------------
        else:
            resolved = self.evaluator.evaluate_expression(init_expr,
                                                cur_blk.variables, None, None)

            # ───────────────────── 구조체 / 배열 / 매핑 ─────────────────────
            if isinstance(resolved, (StructVariable, ArrayVariable, MappingVariable)):
                v = VariableEnv.deep_clone_variable(resolved, var_name)  # ★ 새 객체 생성

            # ───────────────────── enum 초기화 ─────────────────────────────
            elif isinstance(v, EnumVariable):
                enum_def = ccf.enumDefs.get(v.typeInfo.enumTypeName)
                if enum_def is None:
                    raise ValueError(f"undefined enum {v.typeInfo.enumTypeName}")

                if isinstance(resolved, EnumVariable):
                    v.valueIndex = resolved.valueIndex
                    v.value = resolved.value
                elif isinstance(resolved, str) and not resolved.isdigit():
                    member = resolved.split('.')[-1]
                    v.valueIndex = enum_def.members.index(member)
                    v.value = member
                else:  # 숫자 또는 digit 문자열
                    idx = int(resolved, 0)
                    v.valueIndex = idx
                    v.value = enum_def.members[idx]

            # ───────────────────── 나머지(기존 로직) ─────────────────────
            else:
                if isinstance(v, ArrayVariable):
                    for e in resolved:
                        v.elements.append(e)
                elif isinstance(v, Variables):
                    v.value = resolved
                elif isinstance(v, StructVariable) and isinstance(resolved, StructVariable):
                    v.copy_from(resolved)

        # ────────────────── ③ CFG-빌더 / 레코더 위임 ─────────
        #    · 그래프/노드 업데이트는 cfg_builder에게
        #    · 분석 기록은 rec_mgr 에게
        stmt_blk = self.builder.build_variable_declaration(
            cur_block=cur_blk,
            var_obj=v,
            type_obj=type_obj,
            init_expr=init_expr,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.sa.line_info,  # ← builder가 필요하다면 전달
        )
        if stmt_blk.is_loop_body :
            self.recorder.record_variable_declaration(
                line_no=self.current_start_line,
                var_name=var_name,
                var_obj=v,
            )

        self.engine.reinterpret_from(fcfg, stmt_blk)
        self._sync_constructor_state(fcfg, ccf, stmt_blk)

        # ────────────────── ④ 저장 & 정리 ────────────────────
        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf
        self.current_target_function_cfg = None

    def process_variable_declaration_tuple(
            self,
            var_declarations: list[tuple[SolType, str]],  # [(type_obj, var_name), ...]
            init_expr: Expression | None = None
    ):
        """
        튜플 변수 선언 처리
        예: (bool success, bytes memory data) = addr.call(...)

        여러 변수를 한꺼번에 선언하므로, CFG 업데이트는 한 번만 수행
        """
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("variableDeclarationTuple: active FunctionCFG not found")
        fcfg = self.current_target_function_cfg

        cur_blk = self.builder.get_current_block()

        # 각 변수 객체 생성 및 초기화
        var_objects = []
        for idx, (type_obj, var_name) in enumerate(var_declarations):
            v = self._create_variable_object(type_obj, var_name, ccf)

            # ───────────────────────────────────────────────────────────────
            # init_expr가 있는 경우: 튜플 expression 결과에서 해당 인덱스 추출
            # ───────────────────────────────────────────────────────────────
            if init_expr is not None:
                # init_expr를 evaluate하면 tuple 결과가 나올 수 있음
                # 현재는 간단하게 평가하되, 튜플 결과는 리스트로 가정
                resolved = self.evaluator.evaluate_expression(init_expr,
                                                              cur_blk.variables, None, None)

                # resolved가 튜플/리스트인 경우 idx번째 요소 사용
                if isinstance(resolved, (list, tuple)) and idx < len(resolved):
                    init_val = resolved[idx]

                    # 구조체/배열/매핑
                    if isinstance(init_val, (StructVariable, ArrayVariable, MappingVariable)):
                        v = VariableEnv.deep_clone_variable(init_val, var_name)

                    # enum 초기화
                    elif isinstance(v, EnumVariable):
                        enum_def = ccf.enumDefs.get(v.typeInfo.enumTypeName)
                        if enum_def is None:
                            raise ValueError(f"undefined enum {v.typeInfo.enumTypeName}")

                        if isinstance(init_val, EnumVariable):
                            v.valueIndex = init_val.valueIndex
                            v.value = init_val.value
                        elif isinstance(init_val, str) and not init_val.isdigit():
                            member = init_val.split('.')[-1]
                            v.valueIndex = enum_def.members.index(member)
                            v.value = member
                        else:  # 숫자
                            idx_num = int(init_val, 0)
                            v.valueIndex = idx_num
                            v.value = enum_def.members[idx_num]

                    # 나머지 (elementary)
                    else:
                        if isinstance(v, ArrayVariable):
                            for e in init_val:
                                v.elements.append(e)
                        elif isinstance(v, Variables):
                            v.value = init_val
                        elif isinstance(v, StructVariable) and isinstance(init_val, StructVariable):
                            v.copy_from(init_val)

                else:
                    # 튜플 결과가 아니거나 인덱스 범위 밖 → 기본 초기화
                    self._initialize_variable_default(v, ccf, var_name)

            # ───────────────────────────────────────────────────────────────
            # init_expr가 없는 경우: 기본 초기화
            # ───────────────────────────────────────────────────────────────
            else:
                self._initialize_variable_default(v, ccf, var_name)

            var_objects.append((v, type_obj))

        # CFG 빌더 / 레코더 위임 (튜플 전체를 한 statement로 처리)
        stmt_blk = self.builder.build_variable_declaration_tuple(
            cur_block=cur_blk,
            var_objects=var_objects,
            init_expr=init_expr,
            line_no=self.current_start_line,
            fcfg=fcfg,
            line_info=self.sa.line_info,
        )

        # 레코더 기록 (loop body인 경우)
        if stmt_blk.is_loop_body:
            for v, type_obj in var_objects:
                self.recorder.record_variable_declaration(
                    line_no=self.current_start_line,
                    var_name=v.identifier,
                    var_obj=v,
                )

        # reinterpret (한 번만)
        self.engine.reinterpret_from(fcfg, stmt_blk)
        self._sync_constructor_state(fcfg, ccf, stmt_blk)

        # 저장 & 정리
        ccf.update_function_cfg(self.current_target_function, fcfg)
        self.contract_cfgs[self.current_target_contract] = ccf
        self.current_target_function_cfg = None

    def _initialize_variable_default(self, v, ccf, var_name):
        """Helper function to initialize variable with default values."""
        # 배열 기본
        if isinstance(v, ArrayVariable):
            bt = v.typeInfo.arrayBaseType
            if isinstance(bt, SolType):
                et = bt.elementaryTypeName
                if et and et.startswith("int"):
                    bits = bt.intTypeLength or 256
                    v.initialize_elements(IntegerInterval.top(bits))
                elif et and et.startswith("uint"):
                    bits = bt.intTypeLength or 256
                    v.initialize_elements(UnsignedIntegerInterval.top(bits))
                elif et == "bool":
                    v.initialize_elements(BoolInterval.top())
                else:
                    v.initialize_not_abstracted_type()

        # 구조체 기본
        elif isinstance(v, StructVariable):
            if v.typeInfo.structTypeName not in ccf.structDefs:
                raise ValueError(f"Undefined struct {v.typeInfo.structTypeName}")
            v.initialize_struct(ccf.structDefs[v.typeInfo.structTypeName], struct_defs=ccf.structDefs)

        # enum 기본 (첫 멤버)
        elif isinstance(v, EnumVariable):
            enum_def = ccf.enumDefs.get(v.typeInfo.enumTypeName)
            if enum_def:
                v.valueIndex = 0
                v.value = enum_def.members[0]

        # elementary 기본
        elif isinstance(v, Variables):
            et = v.typeInfo.elementaryTypeName
            if et.startswith("int"):
                type_len = v.typeInfo.intTypeLength or 256
                v.value = IntegerInterval.top(type_len)
            elif et.startswith("uint"):
                type_len = v.typeInfo.intTypeLength or 256
                v.value = UnsignedIntegerInterval.top(type_len)
            elif et == "bool":
                v.value = BoolInterval.top()
            elif et == "address":
                v.value = AddressSet.top()
            else:  # bytes/string
                v.value = f"symbol_{var_name}"

    # ──────────────────────────────────────────────────────────────────────
    # Constructor → state_variable_node 전파 헬퍼
    # ──────────────────────────────────────────────────────────────────────
    def _sync_constructor_state(self, fcfg, ccf, latest_block) -> None:
        """생성자 내 상태변수 변경을 state_variable_node에 전파"""
        if getattr(fcfg, "function_type", None) != "constructor":
            return
        sv_node = getattr(ccf, "state_variable_node", None)
        if not sv_node:
            return
        # latest_block이 리스트/튜플이면 첫 번째 요소 사용
        blk = latest_block
        if isinstance(blk, (list, tuple, set)):
            blk = next(iter(blk), None)
        if blk is None:
            return
        block_vars = getattr(blk, "variables", {})
        for name in list(sv_node.variables.keys()):
            if name in block_vars:
                sv_node.variables[name].value = block_vars[name].value

    # Analyzer/ContractAnalyzer.py
    def process_yul_assignment(self, lhs: Expression, rhs: Expression) -> None:
        """Yul assembly 내 대입문: 기존 Solidity 변수에 대입 (prod0 := ...)"""
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            return
        fcfg = self.current_target_function_cfg
        cur_blk = self.builder.get_current_block()

        # 미지원 Yul built-in → TOP
        if getattr(rhs, 'context', '') == 'YulUnsupportedContext':
            r_val = UnsignedIntegerInterval.top()
        else:
            r_val = self.evaluator.evaluate_expression(rhs, cur_blk.variables, None, None)

        self.updater.update_left_var(lhs, r_val, '=', cur_blk.variables, None, None, True)

        stmt_blk = self.builder.build_assignment_statement(
            cur_block=cur_blk,
            expr=Expression(left=lhs, operator='=', right=rhs, context="YulAssignmentContext"),
            line_no=self.current_start_line, fcfg=fcfg, line_info=self.sa.line_info,
        )
        self.engine.reinterpret_from(fcfg, stmt_blk)
        self._sync_constructor_state(fcfg, ccf, stmt_blk)
        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_yul_variable_declaration(self, var_name: str, rhs: Expression | None) -> None:
        """Yul let 선언: 새 uint256 변수 생성 (let mm := ...)"""
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            return
        fcfg = self.current_target_function_cfg
        cur_blk = self.builder.get_current_block()

        # Yul 변수는 항상 uint256
        t = SolType()
        t.typeCategory = "elementary"
        t.elementaryTypeName = "uint256"
        t.intTypeLength = 256

        v = Variables(identifier=var_name, scope="local")
        v.typeInfo = t

        if rhs is None or getattr(rhs, 'context', '') == 'YulUnsupportedContext':
            v.value = UnsignedIntegerInterval.top()
        else:
            v.value = self.evaluator.evaluate_expression(rhs, cur_blk.variables, None, None)

        cur_blk.variables[var_name] = v

        stmt_blk = self.builder.build_variable_declaration(
            cur_block=cur_blk, var_obj=v, type_obj=t, init_expr=rhs,
            line_no=self.current_start_line, fcfg=fcfg, line_info=self.sa.line_info,
        )
        self.engine.reinterpret_from(fcfg, stmt_blk)
        self._sync_constructor_state(fcfg, ccf, stmt_blk)
        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_assignment_expression(self, expr: Expression) -> None:
        # 1. CFG 컨텍스트 --------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("No active function CFG.")
        fcfg = self.current_target_function_cfg

        cur_blk = self.builder.get_current_block()

        # 2. 값 해석 + 변수 갱신  -----------------------------------------
        r_val = self.evaluator.evaluate_expression(
            expr.right, cur_blk.variables, None, None
        )

        self.updater.update_left_var(
            expr.left,
            r_val,
            expr.operator,
            cur_blk.variables,
            None, None, True
        )

        # 3. CFG 노드/엣지 정리  -----------------------------------------
        stmt_blk = self.builder.build_assignment_statement(
            cur_block=cur_blk,
            expr=expr,
            line_no=self.current_start_line,
            fcfg=fcfg,
            line_info=self.sa.line_info,
        )

        self.engine.reinterpret_from(fcfg, stmt_blk)
        self._sync_constructor_state(fcfg, ccf, stmt_blk)

        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    # --------------------------------------------------------------
    #  ++x / --x   (prefix·suffix 공통)
    # --------------------------------------------------------------
    def handle_unary_incdec(self, expr: Expression,
                             op_sign: str,  # "+=" | "-="
                             stmt_kind: str):  # "unary_prefix" | "unary_suffix"
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("active FunctionCFG not found")
        fcfg = self.current_target_function_cfg

        cur_blk = self.builder.get_current_block()

        # ① 현재 값 읽기 → 타입에 맞는 “1” Interval 준비 -------------
        cur_val = self.evaluator.evaluate_expression(
            expr, cur_blk.variables, None, None)

        if isinstance(cur_val, UnsignedIntegerInterval):
            one = UnsignedIntegerInterval(1, 1, cur_val.type_length)
        elif isinstance(cur_val, IntegerInterval):
            one = IntegerInterval(1, 1, cur_val.type_length)
        elif isinstance(cur_val, BoolInterval):
            one = BoolInterval(1, 1)  # 거의 안 쓰임 – 방어 코드
        else:
            raise ValueError(f"unsupported ++/-- type {type(cur_val).__name__}")

        # ② 실제 값 패치 (+ Recorder 자동 기록) -----------------------
        self.updater.update_left_var(
            expr, one, op_sign, cur_blk.variables, None, None, True
        )

        # ③ CFG Statement 삽입 -------------------------------------
        stmt_blk = self.builder.build_unary_statement(
            cur_block=cur_blk,
            expr=expr,
            op_token=stmt_kind,  # 기록용 토큰 – 원하면 '++' 등으로
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.sa.line_info,
        )

        self.engine.reinterpret_from(fcfg, stmt_blk)
        self._sync_constructor_state(fcfg, ccf, stmt_blk)

        self.current_target_function_cfg.update_block(cur_blk)
        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    # --------------------------------------------------------------
    #  delete <expr>
    # --------------------------------------------------------------
    def handle_delete(self, target_expr: Expression):
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("active FunctionCFG not found")
        fcfg = self.current_target_function_cfg

        cur_blk = self.builder.get_current_block()
        vars_env = cur_blk.variables

        # ① 대상 객체 resolve  (update-free 버전)
        var_obj = self.updater.resolve_lhs_expr(target_expr, vars_env)
        if var_obj is None:
            raise ValueError("LHS cannot be resolved.")

        # ② 값 wipe  ----------------------------------------------
        def _wipe(obj):
            if isinstance(obj, MappingVariable):
                obj.mapping.clear()
            elif isinstance(obj, ArrayVariable):
                obj.elements.clear()
            elif isinstance(obj, StructVariable):
                for m in obj.members.values(): _wipe(m)
            elif isinstance(obj, EnumVariable):
                obj.value = IntegerInterval(0, 0, 256)
            elif isinstance(obj, Variables):
                et = getattr(obj.typeInfo, "elementaryTypeName", "")
                bit = getattr(obj.typeInfo, "intTypeLength", 256) or 256
                if et.startswith("uint"):
                    obj.value = UnsignedIntegerInterval(0, 0, bit)
                elif et.startswith("int"):
                    obj.value = IntegerInterval(0, 0, bit)
                elif et == "bool":
                    obj.value = BoolInterval(0, 0)
                elif et == "address":
                    obj.value = AddressSet(ids={0})  # address(0) singleton
                else:
                    obj.value = f"symbolic_zero_{obj.identifier}"

        _wipe(var_obj)

        # ④ CFG Statement 삽입 & 저장 ------------------------------
        stmt_blk = self.builder.build_unary_statement(
            cur_block=cur_blk,
            expr=target_expr,
            op_token="delete",
            line_no=self.current_start_line,
            fcfg=fcfg,
            line_info=self.sa.line_info,
        )

        self.engine.reinterpret_from(fcfg, stmt_blk)
        self._sync_constructor_state(fcfg, ccf, stmt_blk)

        self.current_target_function_cfg.update_block(cur_blk)
        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    # ───────────────────────────────────────────────────────────
    def process_unary_prefix_operation(self, expr: Expression):
        if expr.operator == "++":
            self.handle_unary_incdec(expr.expression, "+=", "unary_prefix")
        elif expr.operator == "--":
            self.handle_unary_incdec(expr.expression, "-=", "unary_prefix")
        elif expr.operator == "delete":
            self.handle_delete(expr.expression)
        else:
            raise ValueError(f"Unsupported prefix operator {expr.operator}")

    def process_unary_suffix_operation(self, expr: Expression):
        if expr.operator == "++":
            self.handle_unary_incdec(expr.expression, "+=", "unary_suffix")
        elif expr.operator == "--":
            self.handle_unary_incdec(expr.expression, "-=", "unary_suffix")
        else:
            raise ValueError(f"Unsupported suffix operator {expr.operator}")

    # ==================================================================
    #  함수 호출 처리
    # ==================================================================
    # ==================================================================
    #  함수 호출 처리
    # ==================================================================
    def process_function_call(self, expr: Expression) -> None:
        # ① CFG 컨텍스트 -------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("No active function CFG.")
        fcfg = self.current_target_function_cfg

        cur_blk = self.builder.get_current_block()

        # ② 실제 호출 해석  ---------------------------------------------
        _ = self.evaluator.evaluate_function_call_context(
            expr,
            cur_blk.variables,
            None,
            None,
        )
        # (Evaluate → Update 경유로 변수 변화는 자동 기록됨)

        # ②-A) ★ pending call 확인 및 등록 ----------------------------
        if self.pending_callee_name:
            callee = self.pending_callee_name
            if callee not in self.pending_calls:
                self.pending_calls[callee] = []
            # (caller_fcfg, call_node) 저장
            self.pending_calls[callee].append((fcfg, cur_blk))
            self.pending_callee_name = None  # 리셋

        # ③ CFG 노드/엣지 정리  ----------------------------------------
        stmt_blk = self.builder.build_function_call_statement(
            cur_block=cur_blk,
            expr=expr,
            line_no=self.current_start_line,
            fcfg=fcfg,
            line_info=self.sa.line_info,
        )

        self.engine.reinterpret_from(fcfg, stmt_blk)
        self._sync_constructor_state(fcfg, ccf, stmt_blk)

        # ⑤ CFG 저장  ---------------------------------------------------
        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_payable_function_call(self, expr):
        # Handle payable function calls
        pass

    def process_function_call_options(self, expr):
        # Handle function calls with options
        pass

    # ═══════════════════════════════════════════════════════════════════
    #  INTENT ANNOTATION PROCESSORS (@During, @Post)
    # ═══════════════════════════════════════════════════════════════════

    def _cfg_node_at(self, line_no: int):
        """해당 라인의 CFG 노드 반환"""
        info = self.sa.line_info.get(line_no, {})
        nodes = info.get("cfg_nodes", [])
        return nodes[0] if nodes else None

    def _find_prev_cfg_node(self, line_no: int):
        """Standalone annotation용: 이전 코드 라인의 CFG 노드 반환"""
        for ln in range(line_no - 1, 0, -1):
            node = self._cfg_node_at(ln)
            if node is not None:
                return node
        return None

    def process_during(self, clauses: list[dict], logic_ops: list[str]) -> dict:
        """
        @During annotation 처리 (새 문법)
        clauses: list of clause dicts (kind, var, op, etc.)
        logic_ops: list of '&&' or '||'

        Intent를 CFG 노드에 저장하고, 해석 시점에 검증한다.
        """
        line_no = self.current_start_line
        cfg_node = self._cfg_node_at(line_no)

        # annotation 저장 (기존 호환성)
        if line_no not in self.during_annotations:
            self.during_annotations[line_no] = []
        self.during_annotations[line_no].append({"clauses": clauses, "logic_ops": logic_ops})

        # Standalone annotation: 해당 라인에 CFG 노드가 없으면 이전 코드 라인의 노드 탐색
        if cfg_node is None:
            cfg_node = self._find_prev_cfg_node(line_no)

        # CFG 노드에 intent 저장 (해석 시 검증용)
        if cfg_node is not None:
            intent_data = {
                "type": "during",
                "clauses": clauses,
                "logic_ops": logic_ops,
                "line_no": line_no
            }
            cfg_node.intents.append(intent_data)
            return {"status": "pending", "message": "Intent attached to CFG node, will be verified during interpretation"}

        # CFG 노드가 없으면 즉시 검증 (fallback)
        if len(clauses) == 1:
            result = self._verify_during_clause(clauses[0], line_no, cfg_node)
        else:
            result = self._verify_during_compound(clauses, logic_ops, line_no, cfg_node)

        self.recorder.record_verification_result(line_no, "during", result)
        return result

    def _verify_during_clause(self, clause: dict, line_no: int, cfg_node) -> dict:
        """개별 during clause 검증"""
        kind = clause.get("kind")

        if kind == "beforeAfter":
            return self.guardian_verifier.verify_during_before_after(
                var_ref=clause["var"], comp_op=clause["op"],
                line_no=line_no, cfg_node=cfg_node
            )
        elif kind == "assignCurrent":
            return self.guardian_verifier.verify_during_assign_current(
                var_ref=clause["var"], comp_op=clause["op"],
                line_no=line_no, cfg_node=cfg_node
            )
        elif kind == "functionArg":
            return self.guardian_verifier.verify_during_function_arg(
                func_name=clause["func_name"], arg_index=clause["arg_index"],
                comp_op=clause["op"], rhs_expr=clause["rhs"],
                line_no=line_no, cfg_node=cfg_node
            )
        elif kind == "retExpr":
            return self.guardian_verifier.verify_during_return_expression(
                comp_op=clause["op"], value_expr=clause["rhs"],
                line_no=line_no, cfg_node=cfg_node
            )
        elif kind == "retIndex":
            return self.guardian_verifier.verify_during_return_index(
                index=clause["index"], comp_op=clause["op"], value_expr=clause["rhs"],
                line_no=line_no, cfg_node=cfg_node
            )
        elif kind == "retVar":
            return self.guardian_verifier.verify_during_return_variable(
                var_ref=clause["lhs"], comp_op=clause["op"], value_expr=clause["rhs"],
                line_no=line_no, cfg_node=cfg_node
            )
        elif kind == "direct":
            return self.guardian_verifier.verify_during_direct_comparison(
                lhs_expr=clause["lhs"], comp_op=clause["op"], rhs_expr=clause["rhs"],
                line_no=line_no, cfg_node=cfg_node
            )
        elif kind == "implication":
            return self.guardian_verifier.verify_during_implication(
                antecedent=clause["antecedent"], consequent=clause["consequent"],
                line_no=line_no, cfg_node=cfg_node
            )
        else:
            return {"status": "error", "message": f"Unknown during clause kind: {kind}"}

    def _verify_during_compound(self, clauses: list[dict], logic_ops: list[str],
                                 line_no: int, cfg_node) -> dict:
        """복합 during clause 검증 (&& / ||)"""
        results = [self._verify_during_clause(c, line_no, cfg_node) for c in clauses]

        # 간단한 로직: && = 모두 success, || = 하나라도 success
        statuses = [r.get("status") for r in results]

        if all(op == "&&" for op in logic_ops):
            if all(s == "success" for s in statuses):
                final_status = "success"
            elif any(s == "violated" for s in statuses):
                final_status = "violated"
            else:
                final_status = "warning"
        else:  # || 포함
            if any(s == "success" for s in statuses):
                final_status = "success"
            elif all(s == "violated" for s in statuses):
                final_status = "violated"
            else:
                final_status = "warning"

        return {
            "status": final_status,
            "kind": "duringCompound",
            "line": line_no,
            "details": {"clauses": results, "logic_ops": logic_ops}
        }

    def process_post(self, clauses: list[dict], logic_ops: list[str]) -> dict:
        """
        @Post annotation 처리 (새 문법)

        Intent를 함수 exit 노드에 저장하고, 함수 종료 시점에 검증한다.
        """
        line_no = self.current_start_line
        fn_cfg = self.current_target_function_cfg

        # annotation 저장 (기존 호환성)
        if line_no not in self.post_annotations:
            self.post_annotations[line_no] = []
        self.post_annotations[line_no].append({"clauses": clauses, "logic_ops": logic_ops})

        # 함수 exit 노드에 intent 저장 (해석 시 검증용)
        if fn_cfg is not None:
            exit_node = fn_cfg.get_exit_node() if hasattr(fn_cfg, 'get_exit_node') else None
            if exit_node is not None and hasattr(exit_node, 'intents'):
                intent_data = {
                    "type": "post",
                    "clauses": clauses,
                    "logic_ops": logic_ops,
                    "line_no": line_no
                }
                exit_node.intents.append(intent_data)
                return {"status": "pending", "message": "Post intent attached to exit node, will be verified at function end"}

        # fallback: 즉시 검증
        if len(clauses) == 1:
            result = self._verify_post_clause(clauses[0], line_no, fn_cfg)
        else:
            # 복합 clause
            result = self._verify_post_compound(clauses, logic_ops, line_no, fn_cfg)

        self.recorder.record_verification_result(line_no, "post", result)
        return result

    def _verify_post_clause(self, clause: dict, line_no: int, fn_cfg) -> dict:
        """개별 post clause 검증"""
        kind = clause.get("kind")

        if kind == "entryExit":
            return self.guardian_verifier.verify_post_entry_exit(
                var_ref=clause["var"], comp_op=clause["op"],
                line_no=line_no, fn_cfg=fn_cfg
            )
        elif kind == "unchanged":
            return self.guardian_verifier.verify_post_unchanged(
                var_ref=clause["var"], line_no=line_no, fn_cfg=fn_cfg
            )
        elif kind == "retExpr":
            return self.guardian_verifier.verify_post_return_expression(
                comp_op=clause["op"], value_expr=clause["rhs"],
                line_no=line_no, fn_cfg=fn_cfg
            )
        elif kind == "retIndex":
            return self.guardian_verifier.verify_post_return_index(
                index=clause["index"], comp_op=clause["op"], value_expr=clause["rhs"],
                line_no=line_no, fn_cfg=fn_cfg
            )
        elif kind == "retVar":
            return self.guardian_verifier.verify_post_return_variable(
                var_ref=clause["lhs"], comp_op=clause["op"], value_expr=clause["rhs"],
                line_no=line_no, fn_cfg=fn_cfg
            )
        elif kind == "direct":
            return self.guardian_verifier.verify_post_direct_comparison(
                lhs_expr=clause["lhs"], comp_op=clause["op"], rhs_expr=clause["rhs"],
                line_no=line_no, fn_cfg=fn_cfg
            )
        elif kind == "implication":
            return self.guardian_verifier.verify_post_implication(
                antecedent=clause["antecedent"], consequent=clause["consequent"],
                line_no=line_no, fn_cfg=fn_cfg
            )
        else:
            return {"status": "error", "message": f"Unknown post clause kind: {kind}"}

    def _verify_post_compound(self, clauses: list[dict], logic_ops: list[str],
                               line_no: int, fn_cfg) -> dict:
        """복합 post clause 검증 (&& / ||)"""
        results = [self._verify_post_clause(c, line_no, fn_cfg) for c in clauses]

        statuses = [r.get("status") for r in results]

        if all(op == "&&" for op in logic_ops):
            if all(s == "success" for s in statuses):
                final_status = "success"
            elif any(s == "violated" for s in statuses):
                final_status = "violated"
            else:
                final_status = "warning"
        else:
            if any(s == "success" for s in statuses):
                final_status = "success"
            elif all(s == "violated" for s in statuses):
                final_status = "violated"
            else:
                final_status = "warning"

        return {
            "status": final_status,
            "kind": "postCompound",
            "line": line_no,
            "details": {"clauses": results, "logic_ops": logic_ops}
        }

    # ═══════════════════════════════════════════════════════════════════

    def process_if_statement(self, condition_expr: Expression) -> None:
        # ── 1. CFG 컨텍스트 ─────────────────────────────────────────────
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("No active function CFG.")
        fcfg = self.current_target_function_cfg

        cur_blk = self.builder.get_current_block()

        base_env = VariableEnv.copy_variables(cur_blk.variables)
        true_env   = VariableEnv.copy_variables(base_env)
        false_env  = VariableEnv.copy_variables(base_env)

        self.refiner.update_variables_with_condition(true_env, condition_expr, True)
        self.refiner.update_variables_with_condition(false_env, condition_expr, False)

        true_delta = VariableEnv.diff_changed(base_env, true_env)

        if true_delta:  # 아무것도 안 바뀌면 기록 생략
            self.recorder.add_env_record(
                 line_no = self.current_start_line,
                 stmt_type = "branchTrue",
                 env = true_delta,
            )

        # 🔁 join을 즉시 만들고 반환받음
        join = self.builder.build_if_statement(
            cur_block=cur_blk,
            condition_expr=condition_expr,
            true_env=true_env,
            false_env=false_env,
            line_no=self.current_start_line,
            fcfg=fcfg,
            line_info=self.sa.line_info,
            end_line=self.current_end_line,
        )

        self.engine.reinterpret_from(fcfg, join)
        self._sync_constructor_state(fcfg, ccf, join)

        # ── 4. 저장 & 마무리 ───────────────────────────────────────────
        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_else_if_statement(self, condition_expr: Expression) -> None:
        ccf = self.contract_cfgs[self.current_target_contract]
        fcfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if fcfg is None:
            raise ValueError("No active function CFG.")
        self.current_target_function_cfg = fcfg

        # ★ get_current_block이 (prev_cond, outer_join) 튜플을 리턴
        prev_cond, outer_join = self.builder.get_current_block(context="else_if")
        if prev_cond is None:
            raise ValueError("else-if used without a preceding if/else-if.")

        # prev False 분기 base-env
        false_base_env = VariableEnv.copy_variables(prev_cond.variables)
        self.refiner.update_variables_with_condition(false_base_env, prev_cond.condition_expr, False)

        base_env = VariableEnv.copy_variables(false_base_env)
        true_env = VariableEnv.copy_variables(base_env)
        false_env = VariableEnv.copy_variables(base_env)
        self.refiner.update_variables_with_condition(true_env, condition_expr, True)
        self.refiner.update_variables_with_condition(false_env, condition_expr, False)

        delta = VariableEnv.diff_changed(base_env, true_env)
        if delta:
            self.recorder.add_env_record(self.current_start_line, "branchTrue", delta)

        end_line = getattr(self, "current_end_line", None)

        local_join = self.builder.build_else_if_statement(
            prev_cond=prev_cond,
            outer_join=outer_join,  # ★ 전달
            condition_expr=condition_expr,
            false_base_env=false_base_env,  # ← 변경된 시그니처
            true_env=true_env,
            false_env=false_env,
            line_no=self.current_start_line,
            fcfg=fcfg,
            line_info=self.sa.line_info,
            end_line=end_line,
        )

        # seed: 외부 join을 우선, 없으면 로컬 join
        outer = self.builder.find_outer_join_near(anchor_line=self.current_start_line,
                                                  fcfg=fcfg, direction="backward",
                                                  include_anchor=False)
        seed = outer or local_join
        self.engine.reinterpret_from(fcfg, seed)
        self._sync_constructor_state(fcfg, ccf, seed)

        ccf.update_function_cfg(self.current_target_function, fcfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_else_statement(self) -> None:
        # ── 1. CFG 컨텍스트 --------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'else'.")
        fcfg = self.current_target_function_cfg

        # ── 2. 직전 if / else-if 노드 찾기 -----------------------------------
        # ★ get_current_block이 (cond_node, outer_join) 튜플을 리턴
        cond_node, outer_join = self.builder.get_current_block(context="else")
        if cond_node is None:
            raise ValueError("No preceding if/else-if for this 'else'.")

        # ── 3. else 분기용 변수-환경 생성 ------------------------------------
        base_env = VariableEnv.copy_variables(cond_node.variables)
        else_env = VariableEnv.copy_variables(base_env)
        self.refiner.update_variables_with_condition(
            else_env, cond_node.condition_expr, is_true_branch=False
        )

        true_delta = VariableEnv.diff_changed(base_env, else_env)

        if true_delta:  # 아무것도 안 바뀌면 기록 생략
            self.recorder.add_env_record(
                line_no=self.current_start_line,
                stmt_type="branchTrue",
                env=true_delta,
            )

        # 🔁 join 재사용, else를 join에 연결하고 join 반환
        join = self.builder.build_else_statement(
            cond_node=cond_node,
            outer_join=outer_join,  # ★ 전달
            else_env=else_env,
            line_no=self.current_start_line,
            fcfg=fcfg,
            line_info=self.sa.line_info,
            end_line=self.current_end_line,
        )

        self.engine.reinterpret_from(fcfg, join)
        self._sync_constructor_state(fcfg, ccf, join)

        # ── 5. 저장 ----------------------------------------------------------
        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_while_statement(self, condition_expr: Expression) -> None:
        # 1. CFG 컨텍스트 ---------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("No active function CFG.")

        cur_blk = self.builder.get_current_block()

        # 2. 분기별 변수 환경 ----------------------------------------------
        join_env = VariableEnv.copy_variables(cur_blk.variables)

        true_env = VariableEnv.copy_variables(join_env)
        false_env = VariableEnv.copy_variables(join_env)

        self.refiner.update_variables_with_condition(true_env, condition_expr, True)
        self.refiner.update_variables_with_condition(false_env, condition_expr, False)

        # ★ end_line 전달 + exit 노드 받아오기
        exit_node = self.builder.build_while_statement(
            cur_block=cur_blk,
            condition_expr=condition_expr,
            join_env=join_env,
            true_env=true_env,
            false_env=false_env,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.sa.line_info,
            end_line=getattr(self, "current_end_line", None),  # ★ 추가
        )

        # ★ reinterpret: loop-exit을 seed로
        self.engine.reinterpret_from(self.current_target_function_cfg, exit_node)
        self._sync_constructor_state(self.current_target_function_cfg, ccf, exit_node)

        # 4. 저장 ----------------------------------------------------------
        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_for_statement(
            self,
            initial_statement: dict | None = None,
            condition_expr: Expression | None = None,
            increment_expr: Expression | None = None,
    ) -> None:
        # 1. CFG 컨텍스트 --------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("No active function CFG.")

        cur_blk = self.builder.get_current_block()

        # 2. ─────── init-노드 (있을 때만)  &  변수 환경 --------------------
        init_node: CFGNode | None = None

        if initial_statement:
            ctx = initial_statement["context"]

            init_node = CFGNode(f"for_init_{self.current_start_line}")
            init_node.variables = VariableEnv.copy_variables(cur_blk.variables)

            if ctx == "VariableDeclaration":
                v_type = initial_statement["initVarType"]
                v_name = initial_statement["initVarName"]
                init_expr = initial_statement["initValExpr"]

                # 값 해석 + 실제 변수 갱신
                if init_expr is not None:
                    r_val = self.evaluator.evaluate_expression(
                        init_expr, init_node.variables, None, None
                    )
                else:
                    # Solidity 기본값: for init에서 초기화 없으면 0
                    elem = getattr(v_type, 'elementaryTypeName', '') or ''
                    bits = getattr(v_type, 'intTypeLength', None) or 256
                    if elem.startswith('uint'):
                        r_val = UnsignedIntegerInterval(0, 0, bits)
                    elif elem.startswith('int'):
                        r_val = IntegerInterval(0, 0, bits)
                    else:
                        r_val = None

                # 변수 객체 생성 & env 삽입
                v_obj = Variables(identifier=v_name, scope="local")
                v_obj.typeInfo = v_type
                if r_val is not None:
                    v_obj.value = r_val
                init_node.variables[v_name] = v_obj

                # CFG Statement
                init_node.add_variable_declaration_statement(
                    v_type, v_name, init_expr, self.current_start_line
                )

            elif ctx == "Expression":
                assn_expr = initial_statement["initExpr"]  # Assignment 식
                r_val = self.evaluator.evaluate_expression(
                    assn_expr.right, init_node.variables, None, None
                )
                # Update 내부에서 기록까지 수행
                self.updater.update_left_var(
                    assn_expr, r_val, assn_expr.operator, init_node.variables, None, None, False
                )
                # CFG Statement
                init_node.add_assign_statement(
                    assn_expr.left, assn_expr.operator, assn_expr.right,
                    self.current_start_line,
                )
            else:
                raise ValueError(f"[for] unknown init ctx '{ctx}'")

        # 3. ─────── 분기용 변수-환경 (join / true / false) ----------------
        join_env = VariableEnv.copy_variables(init_node.variables if init_node else cur_blk.variables)

        true_env = VariableEnv.copy_variables(join_env)
        false_env = VariableEnv.copy_variables(join_env)

        if condition_expr is not None:
            self.refiner.update_variables_with_condition(true_env, condition_expr, True)
            self.refiner.update_variables_with_condition(false_env, condition_expr, False)

        incr_node: CFGNode | None = None
        if increment_expr is not None:
            incr_node = CFGNode(f"for_incr_{self.current_start_line}",
                                is_for_increment=True)
            incr_node.variables = VariableEnv.copy_variables(true_env)

            # ---- ++ / -- --------------------------------------
            if increment_expr.operator in {"++", "--"}:
                # (1) 변수 환경에 즉시 반영
                one = UnsignedIntegerInterval(1, 1, 256)
                self.updater.update_left_var(
                    increment_expr.expression,  # i
                    one,
                    "+=" if increment_expr.operator == "++" else "-=",
                    incr_node.variables, None, None, False
                )
                # (2) **단항 스테이트먼트**로 기록
                incr_node.add_unary_statement(
                    operand=increment_expr.expression,  # 전체 i++ 식
                    operator=increment_expr.operator,  # '++' or '--'
                    line_no=self.current_start_line,
                )

            # ---- 복합 대입( += n / -= n … ) --------------------
            else:
                r_val = self.evaluator.evaluate_expression(
                    increment_expr.right, incr_node.variables)
                op = increment_expr.operator
                self.updater.update_left_var(
                    increment_expr.left, r_val, op, incr_node.variables, None, None, False)
                incr_node.add_assign_statement(
                    increment_expr.left, op, increment_expr.right,
                    self.current_start_line)

        exit_node = self.builder.build_for_statement(
            cur_block=cur_blk,
            init_node=init_node,
            join_env=join_env,
            cond_expr=condition_expr,
            true_env=true_env,
            false_env=false_env,
            incr_node=incr_node,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.sa.line_info,
            end_line=getattr(self, "current_end_line", None),  # ★ 추가
        )

        # ★ reinterpret: loop-exit을 seed로
        self.engine.reinterpret_from(self.current_target_function_cfg, exit_node)
        self._sync_constructor_state(self.current_target_function_cfg, ccf, exit_node)

        # 6. 저장 ---------------------------------------------------------
        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_continue_statement(self) -> None:
        # 1) CFG 컨텍스트
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'continue'.")

        # 2) 현재 블록
        cur_blk = self.builder.get_current_block()

        # ★ 빌더가 loop-exit 을 반환
        exit_node = self.builder.build_continue_statement(
            cur_block=cur_blk,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.sa.line_info,
        )

        # ★ reinterpret seed = loop-exit
        self.engine.reinterpret_from(self.current_target_function_cfg, exit_node)
        self._sync_constructor_state(self.current_target_function_cfg, ccf, exit_node)

        # 5) 저장
        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_break_statement(self) -> None:
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'break'.")

        cur_blk = self.builder.get_current_block()

        # ★ 빌더가 loop-exit 을 반환
        exit_node = self.builder.build_break_statement(
            cur_block=cur_blk,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.sa.line_info,
        )

        # ★ reinterpret seed = loop-exit
        self.engine.reinterpret_from(self.current_target_function_cfg, exit_node)
        self._sync_constructor_state(self.current_target_function_cfg, ccf, exit_node)

        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    # Analyzer/ContractAnalyzer.py
    def process_return_statement(self, return_expr: Expression | None = None) -> None:
        # ── 1. CFG 컨텍스트 -------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'return'.")

        cur_blk = self.builder.get_current_block()

        # ── 2. 값 평가 ------------------------------------------------------
        r_val = None
        if return_expr is not None:
            r_val = self.evaluator.evaluate_expression(
                return_expr, cur_blk.variables, None, None
            )

        # ★ 빌더가 ‘재배선 전’ succ 들을 반환
        succ_before = self.builder.build_return_statement(
            cur_block=cur_blk,
            return_expr=return_expr,
            return_val=r_val,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.sa.line_info,
        )

        # ── 4. 기록 ---------------------------------------------------------
        self.recorder.record_return(
            line_no=self.current_start_line,
            return_expr=return_expr,
            return_val=r_val,
            fn_cfg=self.current_target_function_cfg,
        )

        # ★ reinterpret seed = 연결하기 ‘전’ succ(들)
        if succ_before:
            self.engine.reinterpret_from(self.current_target_function_cfg, succ_before)
            self._sync_constructor_state(self.current_target_function_cfg, ccf, succ_before)

        # ── 5. CFG 저장 -----------------------------------------------------
        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    # ──────────────────────────────────────────────────────────────────────
    # Event / Emit  (추상 해석에는 영향 없음 — 정의만 기록, emit은 skip)
    # ──────────────────────────────────────────────────────────────────────
    def process_event_definition(self, event_name: str, parameters: list[dict]) -> None:
        """event Transfer(address indexed from, ...) 정의를 ContractCFG에 저장"""
        ccf = self.contract_cfgs[self.current_target_contract]
        ccf.events[event_name] = parameters

    def process_emit_statement(self, event_name: str, arguments: list) -> None:
        """emit 문 — 상태 변경 없으므로 skip"""
        pass

    # Analyzer/ContractAnalyzer.py
    def process_revert_statement(
            self,
            revert_identifier: str | None = None,
            string_literal: str | None = None,
            call_argument_list: list[Expression] | None = None,
    ) -> None:
        # ── 1. CFG context ---------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'revert'.")

        cur_blk = self.builder.get_current_block()

        # ★ 빌더가 ‘재배선 전’ succ 들을 반환
        succ_before = self.builder.build_revert_statement(
            cur_block=cur_blk,
            revert_id=revert_identifier,
            string_literal=string_literal,
            call_args=call_argument_list,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.sa.line_info,
        )

        # ★ reinterpret seed = 연결하기 ‘전’ succ(들)
        if succ_before:
            self.engine.reinterpret_from(self.current_target_function_cfg, succ_before)
            self._sync_constructor_state(self.current_target_function_cfg, ccf, succ_before)

        # ── 4. save CFG ------------------------------------------------------
        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    # Analyzer/ContractAnalyzer.py
    def process_require_statement(
            self,
            condition_expr: Expression,
            string_literal: str | None,
    ) -> None:
        # 1) CFG context -----------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG.")

        cur_blk = self.builder.get_current_block()

        # 2) True-branch 환경 ------------------------------------------------
        base_env = VariableEnv.copy_variables(cur_blk.variables)
        true_env = VariableEnv.copy_variables(base_env)
        self.refiner.update_variables_with_condition(
            true_env, condition_expr, is_true_branch=True
        )

        # ★ 빌더가 true-분기 succ 들을 반환
        true_succs = self.builder.build_require_statement(
            cur_block=cur_blk,
            condition_expr=condition_expr,
            true_env=true_env,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.sa.line_info,
        )

        # ★ reinterpret seed = true-분기 succ(들)
        if true_succs:
            self.engine.reinterpret_from(self.current_target_function_cfg, true_succs)
            self._sync_constructor_state(self.current_target_function_cfg, ccf, true_succs)

        # 5) 저장 ------------------------------------------------------------
        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    # Analyzer/ContractAnalyzer.py
    def process_assert_statement(
            self,
            condition_expr: Expression,
            string_literal: str | None,
    ) -> None:
        # 1) CFG context -----------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG.")

        cur_blk = self.builder.get_current_block()

        # 2) True-branch 환경(조건이 만족되는 경로) ---------------------------
        base_env = VariableEnv.copy_variables(cur_blk.variables)
        true_env = VariableEnv.copy_variables(base_env)
        self.refiner.update_variables_with_condition(
            true_env, condition_expr, is_true_branch=True
        )

        # ★ 빌더가 true-분기 succ 들을 반환
        true_succs = self.builder.build_assert_statement(
            cur_block=cur_blk,
            condition_expr=condition_expr,
            true_env=true_env,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.sa.line_info,
        )

        # ★ reinterpret seed = true-분기 succ(들)
        if true_succs:
            self.engine.reinterpret_from(self.current_target_function_cfg, true_succs)
            self._sync_constructor_state(self.current_target_function_cfg, ccf, true_succs)

        # 5) 저장 -------------------------------------------------------------
        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    # ContractAnalyzer.py  (추가/수정)

    # Analyzer/ContractAnalyzer.py
    def process_identifier_expression(self, ident_expr: Expression) -> None:
        """
        · ident == '_'  and  현재 CFG 가 modifier 이면  placeholder 처리
          그렇지 않으면 그냥 식별자 평가(별도 로직).
        """
        ident = ident_expr.identifier
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)

        # ── modifier placeholder (‘_’) --------------------------------------
        if (ident == "_" and self.current_target_function_cfg
                and self.current_target_function_cfg.function_type == "modifier"):
            cur_blk = self.builder.get_current_block()

            # ⬇️  새 helper 호출
            self.builder.build_modifier_placeholder(
                cur_block=cur_blk,
                fcfg=self.current_target_function_cfg,
                line_no=self.current_start_line,
                line_info=self.sa.line_info,
            )
            return  # 값-해석 없음

        # … 이하 “일반 identifier” 처리는 기존 로직 유지 …

    # Analyzer/ContractAnalyzer.py
    def process_unchecked_indicator(self) -> None:
        # ── 1. CFG 컨텍스트 --------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'unchecked'.")

        # ── 2. 현재 블록, 빌더 호출 -------------------------------------
        cur_blk = self.builder.get_current_block()

        self.builder.build_unchecked_block(
            cur_block=cur_blk,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.sa.line_info,
        )

        # ── 3. 저장 ------------------------------------------------------
        ccf.update_function_cfg(self.current_target_function, self.current_target_function_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

    # Analyzer/ContractAnalyzer.py  내부 메소드들 추가/교체

    def process_do_statement(self):
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        fcfg = self.current_target_function_cfg
        if not fcfg:
            raise ValueError("No current target function to attach do-while.")

        pred = self.builder.get_current_block()  # prev 앵커
        self.builder.build_do_statement(
            cur_block=pred, line_no=self.current_start_line,
            fcfg=fcfg, line_info = self.sa.line_info
        )

    def process_do_while_statement(self, condition_expr):
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        fcfg = self.current_target_function_cfg
        if not fcfg:
            raise ValueError("No current target function to attach do-while.")

        # while 라인에서의 pred 앵커 = do_end_*
        pred = self.builder.get_current_block()
        if not getattr(pred, "is_do_end", False):
            raise ValueError("`while (...)` arrived but preceding `do {}` was not found.")

        # do_entry = pred(do_end)
        G = fcfg.graph
        do_entry = None
        for pp in G.predecessors(pred):
            if getattr(pp, "is_do_entry", False):
                do_entry = pp
                break
        if do_entry is None:
            raise ValueError("do-while: do_entry could not be found behind do_end.")

        # ★ builder 가 exit 노드를 반환하도록
        exit_node = self.builder.build_do_while_statement(
            do_entry=do_entry, while_line=self.current_start_line,
            fcfg=fcfg,
            condition_expr = condition_expr,
            line_info = self.sa.line_info
        )

        # ★ seed = loop exit
        self.engine.reinterpret_from(fcfg, exit_node)
        self._sync_constructor_state(fcfg, ccf, exit_node)

    def process_try_statement(self, function_expr, returns):
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        fcfg = self.current_target_function_cfg
        if not fcfg:
            raise ValueError("No current target function for try.")

        pred = self.builder.get_current_block()  # 이전 블록 기준

        # returns 로컬 생성(⊥) 후 true 블록 env 에 심기
        cond, true_blk, false_stub, join = self.builder.build_try_skeleton(
            cur_block=pred, function_expr=function_expr,
            line_no=self.current_start_line, fcfg=fcfg, line_info=self.sa.line_info
        )

        for i, (ty, nm) in enumerate(returns or []):
            vname = nm or f"_ret{i}"
            vobj = Variables(identifier=vname, scope="local")
            vobj.typeInfo = ty
            # elementary bottom 초기화
            if getattr(ty, "typeCategory", None) == "elementary":
                et = getattr(ty, "elementaryTypeName", "")
                bits = getattr(ty, "intTypeLength", 256) or 256
                if et.startswith("uint"):
                    vobj.value = UnsignedIntegerInterval.top(bits)
                elif et.startswith("int"):
                    vobj.value = IntegerInterval.top(bits)
                elif et == "bool":
                    vobj.value = BoolInterval.top()
                else:
                    vobj.value = None
            else:
                vobj.value = None

            true_blk.variables[vname] = vobj
            fcfg.add_related_variable(vobj)

        # ★ returns 로컬이 true-경로에 추가되었으므로 합류점부터 후속을 최신화
        self.engine.reinterpret_from(fcfg, join)
        self._sync_constructor_state(fcfg, ccf, join)

    def process_catch_clause(self, catch_ident, params):
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        fcfg = self.current_target_function_cfg
        if not fcfg:
            raise ValueError("No current target function for catch.")

        # ★ get_current_block을 사용해서 try condition과 join 찾기
        result = self.builder.get_current_block(context="catch")
        if result is None:
            raise ValueError("`catch` without preceding `try`.")

        # catch는 튜플 또는 단일 노드를 반환할 수 있음
        if isinstance(result, tuple):
            cond, join = result
        else:
            cond = result
            # join을 find_open_try_for_catch로 찾기
            found = self.builder.find_open_try_for_catch(line_no=self.current_start_line, fcfg=fcfg)
            if found is None:
                raise ValueError("`catch`: try found but join not found.")
            _, false_stub, join = found

        # false_stub 찾기 (attach_catch_clause에서 필요)
        false_stub = None
        for s in fcfg.graph.successors(cond):
            if fcfg.graph[cond][s].get("condition") is False:
                false_stub = s
                break

        if false_stub is None:
            raise ValueError("`catch`: false stub not found for try condition.")

        c_entry, c_end = self.builder.attach_catch_clause(
            cond=cond, false_stub=false_stub, join=join,
            line_no=self.current_start_line, fcfg=fcfg, line_info=self.sa.line_info
        )

        # catch 파라미터 로컬
        for ty, nm in (params or []):
            if not nm:
                continue
            v = Variables(identifier=nm, scope="local")
            v.typeInfo = ty
            v.value = None
            c_entry.variables[nm] = v
            fcfg.add_related_variable(v)

        # ★ 합류점에서 재해석 시작
        self.engine.reinterpret_from(fcfg, join)
        self._sync_constructor_state(fcfg, ccf, join)

    def process_global_var_for_debug(self, gv_obj: GlobalVariable):
        """
        @GlobalVar …   처리
          • cfg.globals  갱신
          • FunctionCFG.related_variables  갱신
          •(주소형이면) AddressSymbolicManager 에 변수<->ID 바인딩
          • 영향을 받는 함수만 재해석
        """
        ev = self.current_edit_event
        cfg = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = cfg.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)

        # ── 등록이 처음이면 snapshot ⬇︎
        if gv_obj.identifier not in cfg.globals:
            gv_obj.default_value = gv_obj.value
            cfg.globals[gv_obj.identifier] = gv_obj
            self.snapman.register(gv_obj, self.ser)  # ★ 스냅

        g = cfg.globals[gv_obj.identifier]

        # ── add/modify ───────────────────────────────────────────
        if ev in ("add", "modify"):
            g.debug_override = gv_obj.value
            g.value = gv_obj.value

        # ── delete  → snapshot 복원 + override 해제 ───────────────
        elif ev == "delete":
            self.snapman.restore(g, self.de)  # ★ 롤백
            g.debug_override = None

        else:
            raise ValueError(f"unknown event {ev!r}")

        # ↳ 주소형이면 AddressSymbolicManager 에 기록
        if g.typeInfo.elementaryTypeName == "address" and isinstance(g.value, UnsignedIntegerInterval):
            iv = g.value
            if iv.min_value == iv.max_value:  # [N,N] 형식 ⇒ 고정 ID
                nid = iv.min_value
                self.sm.register_fixed_id(nid, iv)
                self.sm.bind_var(g.identifier, nid)

        self._batch_targets.add(self.current_target_function_cfg)

        self.current_target_function_cfg = None

    # ─────────────────────────────────────────────────────────────
    def process_state_var_for_debug(self, lhs_expr: Expression, value):

        try:
            ccf  = self.contract_cfgs[self.current_target_contract]
            self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
            if self.current_target_function_cfg is None:
                raise ValueError("@StateVar must be inside a function.")

            self.debug_initializer.apply_debug_directive_enhanced(
                scope="state",
                lhs_expr=lhs_expr,
                value=value,
                variables=self.current_target_function_cfg.related_variables,
                edit_event=self.current_edit_event,
            )

            # 함수 다시 해석하도록 배치
            self._batch_targets.add(self.current_target_function_cfg)
        except Exception as e:
            print(f"ERROR in process_state_var_for_debug: {e}")
            import traceback
            traceback.print_exc()

    # ------------------------------------------------------------------
    #  @LocalVar   debug 주석
    # ------------------------------------------------------------------
    def process_local_var_for_debug(self, lhs_expr: Expression, value):
        ccf  = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("@LocalVar must be inside a function.")

        self.debug_initializer.apply_debug_directive_enhanced(
            scope="local",
            lhs_expr=lhs_expr,
            value=value,
            variables=self.current_target_function_cfg.related_variables,
            edit_event=self.current_edit_event,
        )

        self._batch_targets.add(self.current_target_function_cfg)

    # ------------------------------------------------------------------
    #  @IReturn   debug 주석
    # ------------------------------------------------------------------
    def _find_interface_name_for_var(self, var_name: str) -> str | None:
        """
        변수(state var 또는 function parameter)의 typeInfo에서 interface 이름을 찾는다.
        typeCategory == "interface"이면 interfaceName 반환, 아니면 None.
        """
        # 1) state variable 검색
        ccf = self.contract_cfgs.get(self.current_target_contract)
        if ccf:
            sv_node = getattr(ccf, 'state_variable_node', None)
            for var in (sv_node.variables.values() if sv_node else []):
                if var.identifier == var_name and hasattr(var, 'typeInfo') and var.typeInfo:
                    if var.typeInfo.typeCategory == "interface":
                        return var.typeInfo.interfaceName

        # 2) 현재 함수의 parameter / related_variables 검색
        if ccf:
            func_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
            if func_cfg:
                for param_var in func_cfg.related_variables.values():
                    if param_var.identifier == var_name and hasattr(param_var, 'typeInfo') and param_var.typeInfo:
                        if param_var.typeInfo.typeCategory == "interface":
                            return param_var.typeInfo.interfaceName

                # 3) 함수 내 지역변수 중 interface 타입 조회
                if var_name in func_cfg.interface_var_types:
                    return func_cfg.interface_var_types[var_name]

        return None

    def process_ireturn(self, contract_var: str, func_name: str, access_chain: tuple, value):
        """
        @IReturn annotation 처리 (Pattern A: contractVar.funcName().<chain>).
        access_chain: tuple of ("member", name) or ("index", int), e.g.:
          () → 단일 return,  (("index", 0),) → [0],  (("member", "fee"),) → .fee
        """
        # 1) contract_var가 interface type 변수인지 검증
        interface_name = self._find_interface_name_for_var(contract_var)
        if interface_name is None:
            raise ValueError(
                f"@IReturn: '{contract_var}' is not an interface-typed variable."
            )

        # 2) 해당 interface에 func_name 함수가 존재하는지 검증
        interface_cfg = self.contract_cfgs.get(interface_name)
        if interface_cfg is None or func_name not in interface_cfg.functions:
            available = list(interface_cfg.functions.keys()) if interface_cfg else []
            raise ValueError(
                f"@IReturn: function '{func_name}' not found in interface '{interface_name}'. "
                f"Available: {available}"
            )

        # 3) view/pure 함수인지 검증
        fcfg = interface_cfg.get_function_cfg(func_name)
        if fcfg.mutability not in ("view", "pure"):
            raise ValueError(
                f"@IReturn: '{interface_name}.{func_name}' is not view/pure "
                f"(mutability={fcfg.mutability}). "
                f"@IReturn only supports view/pure interface functions."
            )

        # 4) FunctionCFG의 ireturn_registry에 저장
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("@IReturn must be inside a function.")

        key = (contract_var, func_name, access_chain)
        self.current_target_function_cfg.ireturn_registry[key] = value

        # 5) 재해석 배치
        self._batch_targets.add(self.current_target_function_cfg)

    # ------------------------------------------------------------------
    #  @IReturn (Pattern B: explicit cast)  debug 주석
    # ------------------------------------------------------------------
    def process_ireturn_cast(self, interface_name: str, addr_var: str,
                             func_name: str, access_chain: tuple, value):
        """
        @IReturn Pattern B annotation 처리: IInterface(addrVar).funcName().<chain>
        """
        # 1) interface_name이 알려진 interface인지 검증
        if interface_name not in self.interface_names:
            raise ValueError(
                f"@IReturn: '{interface_name}' is not a known interface. "
                f"Known interfaces: {list(self.interface_names)}"
            )

        # 2) 해당 interface에 func_name 함수가 존재하는지 검증
        interface_cfg = self.contract_cfgs.get(interface_name)
        if interface_cfg is None or func_name not in interface_cfg.functions:
            available = list(interface_cfg.functions.keys()) if interface_cfg else []
            raise ValueError(
                f"@IReturn: function '{func_name}' not found in interface '{interface_name}'. "
                f"Available: {available}"
            )

        # 3) view/pure 함수인지 검증
        fcfg = interface_cfg.get_function_cfg(func_name)
        if fcfg.mutability not in ("view", "pure"):
            raise ValueError(
                f"@IReturn: '{interface_name}.{func_name}' is not view/pure "
                f"(mutability={fcfg.mutability}). "
                f"@IReturn only supports view/pure interface functions."
            )

        # 4) FunctionCFG의 ireturn_registry에 저장
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function, param_types=self.current_target_function_param_types)
        if self.current_target_function_cfg is None:
            raise ValueError("@IReturn must be inside a function.")

        key = (interface_name, addr_var, func_name, access_chain)
        self.current_target_function_cfg.ireturn_registry[key] = value

        # 5) 재해석 배치
        self._batch_targets.add(self.current_target_function_cfg)

    # ContractAnalyzer.py (일부)

    def get_line_analysis(self, start_ln: int, end_ln: int,
                          kinds: set[str] | None = None) -> dict[int, list[dict]]:
        kinds = kinds or {"varDeclaration", "assignment", "return", "implicitReturn", "loopDelta"}
        # RecordManager 로 대체
        out: dict[int, list[dict]] = {}
        for ln in range(start_ln, end_ln + 1):
            if ln not in self.recorder.ledger:
                continue
            # kind 필터
            filtered = [rec for rec in self.recorder.ledger[ln] if rec.get("kind") in kinds]
            if filtered:
                out[ln] = filtered
        return out

    def send_report_to_front(self,
                             patched_lines: list[tuple[str, int, int]] | None = None) -> None:
        # 0) 보여줄 라인 결정
        touched: set[int] = set()

        if patched_lines:
            for _code, s, e in patched_lines:
                touched.update(range(s, e + 1))
        elif getattr(self, "_last_func_lines", None):
            s, e = self._last_func_lines
            touched.update(range(s, e + 1))
        elif getattr(self, "_last_touched_lines", None):
            touched |= set(self._last_touched_lines)

        if not touched:
            print("※ send_report_to_front : 보여줄 라인이 없습니다.")
            return

        lmin, lmax = min(touched), max(touched)
        kinds = {"varDeclaration", "assignment", "return", "implicitReturn", "loopDelta"}
        # print(f"DEBUG send_report: Searching lines {lmin}-{lmax}, ledger has keys: {list(self.recorder.ledger.keys())}")
        payload = self.get_line_analysis(lmin, lmax, kinds=kinds)

        if not payload:
            print("※ 분석 결과가 없습니다.")
            return

        print("\n=======  ANALYSIS  =======")
        for ln in sorted(payload):
            for rec in payload[ln]:
                kind = rec.get("kind", "?")
                vars_ = rec.get("vars", {})
                print(f"{ln:4} │ {kind:<14} │ {vars_}")
        print("==========================\n")

    # ContractAnalyzer.py  (클래스 내부)

    def flush_pending_calls(self) -> None:
        """
        코드 입력이 모두 끝난 후 남은 pending_calls를 처리.
        아직 분석 안 된 함수를 호출한 곳들을 재분석.
        """
        if not self.pending_calls:
            return

        # 모든 pending_calls 처리
        for callee_name, call_infos in list(self.pending_calls.items()):
            # 해당 함수가 이제 분석됐는지 확인
            ccf = self.contract_cfgs.get(self.current_target_contract)
            if ccf and callee_name in ccf.functions:
                for (caller_fcfg, call_node) in call_infos:
                    self.engine.reinterpret_from(caller_fcfg, call_node)
                del self.pending_calls[callee_name]

        # 여전히 남은 pending_calls가 있으면 (외부 함수 등) 경고
        if self.pending_calls:
            print(f"[Warning] Unresolved pending_calls: {list(self.pending_calls.keys())}")

    def add_intent_annotation(self, line_no: int, annotation: str) -> dict:
        """
        코드 분석 완료 후 특정 라인에 intent annotation 추가.
        annotation: "// @During x > 0" 또는 "// @Post x(entry > exit)" 형태의 문자열

        - @During: 해당 라인에 첨부만 (라인 밀림 없음)
        - @Post: 새 라인으로 삽입하여 아래 라인들을 밀음 (함수 끝 } 와 함께 이동)

        Returns: verification result dict
        """
        from Utils.Helper import ParserHelpers
        from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor

        # annotation 타입 확인: @Post는 라인 삽입 필요
        stripped = annotation.strip()
        is_post = stripped.startswith("// @Post") or stripped.startswith("@Post")

        # @Post인 경우: 새 라인으로 삽입하여 아래 라인들 밀기
        if is_post:
            self._insert_lines(line_no, [annotation])
            # 삽입 후 해당 라인은 annotation으로 채워짐

        # 1. 해당 라인의 함수 컨텍스트 찾기
        func_name, func_param_types = self.find_function_context(line_no)
        if not func_name:
            return {"status": "error", "message": f"No function context at line {line_no}"}

        # 2. 현재 컨텍스트 설정
        self.current_start_line = line_no
        self.current_end_line = line_no
        self.current_target_function = func_name
        self.current_target_function_param_types = func_param_types

        ccf = self.contract_cfgs.get(self.current_target_contract)
        if ccf:
            self.current_target_function_cfg = ccf.get_function_cfg(func_name, param_types=func_param_types)

        # 3. annotation 파싱 및 처리
        try:
            tree = ParserHelpers.generate_parse_tree(annotation, "IntentUnit")
            visitor = EnhancedSolidityVisitor(self)
            visitor.visit(tree)

            # 4. 결과 반환 (가장 최근에 기록된 verification 결과)
            results = self.recorder.ledger.get(line_no, [])
            for r in reversed(results):
                if r.get("kind") == "verification":
                    return r
            return {"status": "success", "message": "Annotation processed"}

        except Exception as e:
            return {"status": "error", "message": f"Failed to parse annotation: {str(e)}"}

    def flush_reinterpret_target(self) -> None:
        if not self._batch_targets:
            return
        fcfg = self._batch_targets.pop()
        self.engine.interpret_function_cfg_for_debug(fcfg, None)  # ★ 디버깅용 함수 사용

        ln_set = {st.src_line
                  for blk in fcfg.graph.nodes
                  for st in blk.statements
                  if getattr(st, "src_line", None)}
        self._last_func_lines = (min(ln_set), max(ln_set)) if ln_set else None

    # ──────────────────────────────────────────────────────────────
    # Snapshot 전용 내부 헬퍼  ―  외부에서 쓸 일 없으므로 “프라이빗” 네이밍
    # ----------------------------------------------------------------
    @staticmethod
    def ser(v):  # obj → dict
        return v.__dict__

    @staticmethod
    def de(v, snap):  # dict → obj
        v.__dict__.clear()
        v.__dict__.update(snap)

    # 공통 ‘한 줄 helper’
    def register_var(self, var_obj):
        self.snapman.register(var_obj, self.ser)