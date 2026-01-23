# SolidityGuardian/Analyzers/ContractAnalyzer.py
from Utils.CFG import *
from solcx import (
    install_solc,
    set_solc_version,
    compile_source,
    get_installed_solc_versions
)
from solcx.exceptions import SolcError
from Domain.AddressSet import address_manager, AddressSet
from Domain.Annotation import DuringAnnotation, PostAnnotation, CompoundDuringAnnotation, CompoundPostAnnotation
from Utils.Helper import *
from Utils.Snapshot import *
from Analyzer.DynamicCFGBuilder import DynamicCFGBuilder
from Analyzer.RecordManager import RecordManager
from Analyzer.StaticCFGFactory import StaticCFGFactory
from Analyzer.CFGSerializerPickle import CFGSerializerPickle as CFGSerializer
from Interpreter.Semantics.Evaluation import Evaluation
from Interpreter.Semantics.Update import Update
from Interpreter.Semantics.DebugInitializer import DebugInitializer
from Interpreter.Semantics.Refine import Refine
from Interpreter.Engine import Engine
from Analyzer.GuardianVerificationEngine import GuardianVerificationEngine
import pathlib
import re

class ContractAnalyzer:

    def __init__(self):
        self.addr_mgr = address_manager  # 싱글톤 AddressManager
        self.snapman = SnapshotManager()
        self._batch_targets: set[FunctionCFG] = set()  # 🔹추가

        self.full_code = None
        self.full_code_lines = {} # 라인별 코드를 저장하는 딕셔너리
        self.line_info = {} # 각 라인에서 `{`와 `}`의 개수를 저장하는 딕셔너리

        self.current_start_line = None
        self.current_end_line = None

        self.current_context_type = None
        self.current_target_contract = None
        self.current_target_function = None
        self.current_target_function_cfg = None
        self.current_target_struct = None

        self.current_edit_event = None
        self._record_enabled = False
        self._seen_stmt_ids: set[int] = set()
        self._last_touched_lines = None

        # ★ statement + annotation 분리 정보 저장 (test.py에서 사용)
        self.last_statement_part = None
        self.last_annotation_part = None

        # Pragma 정보
        self.pragma_version = None  # pragma solidity 버전
        self.pragma_directives = []  # 모든 pragma directive 저장

        # for Multiple Contract
        self.contract_cfgs = {} # name -> ContractCFG
        self.library_cfgs = {}  # name -> LibraryCFG
        self.interface_cfgs = {}  # name -> InterfaceCFG
        
        # 라이브러리 파일 저장 경로 (기본값: Libraries 디렉토리)
        self.libraries_dir = pathlib.Path(__file__).parent.parent / "Libraries"
        
        # CFG 직렬화/역직렬화 담당
        self.cfg_serializer = CFGSerializer()

        self.evaluator = Evaluation(self)
        self.updater = Update(self)
        self.debug_initializer = DebugInitializer(self)
        self.refiner = Refine(self)
        self.engine = Engine(self)
        self.builder = DynamicCFGBuilder(self)
        self.guardian_verifier = GuardianVerificationEngine(self)
        self.recorder = RecordManager()

        self.analysis_per_line = self.recorder.ledger

    """
    Prev analysis part
    """
    INTENT_MARKERS = (
        "// @GlobalVar", "// @StateVar", "// @LocalVar",
        "// @During", "// @Post"
    )


    # ────────────────────────────────────────────────────────────────
    #  ContractAnalyzer   (class body 안)
    # ----------------------------------------------------------------
    def _shift_meta(self, old_ln: int, new_ln: int):
        """
        소스 라인 이동(old_ln → new_ln)에 맞춰
        line_info / recorder.ledger / Statement.src_line / CFGNode.src_line 동기화
        """
        # ① line_info에 등록된 cfg_nodes들의 src_line 보정 (먼저 수행)
        if old_ln in self.line_info:
            info = self.line_info[old_ln]
            if isinstance(info.get("cfg_nodes"), list):
                for node in info["cfg_nodes"]:
                    if hasattr(node, "src_line") and node.src_line == old_ln:
                        node.src_line = new_ln

        # ② line_info & recorder.ledger 이동
        dicts_to_shift = (self.line_info, self.recorder.ledger)
        for d in dicts_to_shift:
            if old_ln in d:
                # (간단버전) 덮어쓰기. 이미 new_ln 에 값이 있으면 합치고 싶다면 merge 로직을 쓰세요.
                d[new_ln] = d.pop(old_ln)

        # ③ 이미 생성된 CFG-Statement 들의 src_line 보정
        stmt_count = 0
        for ccf in self.contract_cfgs.values():
            for fcfg in ccf.functions.values():
                for blk in fcfg.graph.nodes:
                    # CFGNode 자체의 src_line도 업데이트
                    if getattr(blk, "src_line", None) == old_ln:
                        blk.src_line = new_ln
                    # Statement들의 src_line 업데이트
                    for st in blk.statements:
                        if getattr(st, "src_line", None) == old_ln:
                            st.src_line = new_ln
                            stmt_count += 1
        if stmt_count > 0:
            pass
            # print(f"DEBUG _shift_meta: Shifted {stmt_count} statements from line {old_ln} to {new_ln}")

    def _insert_lines(self, start: int, new_lines: list[str]):
        new_lines = self.normalize_compound_control_lines(new_lines)
        offset = len(new_lines)

        # start 라인에 control flow 노드가 있고, 새 코드가 연속되는 control flow인지 체크
        skip_shift_at_start = False
        if start in self.line_info:
            cfg_nodes = self.line_info[start].get('cfg_nodes', [])
            first_new_line = new_lines[0].strip() if new_lines else ""

            # 같은 control flow의 연속인 경우:
            # 1. if/else-if의 join + else/else-if
            # 2. do의 끝 + while
            # 3. try의 stub + catch
            for node in cfg_nodes:
                # if/else-if join + else/else-if
                if (getattr(node, 'join_point_node', False) and
                    (first_new_line.startswith('else if') or first_new_line.startswith('else'))):
                    skip_shift_at_start = True
                    break
                # do end + while
                if (getattr(node, 'is_do_end', False) and
                    first_new_line.startswith('while')):
                    skip_shift_at_start = True
                    break
                # try false_stub + catch
                if (node.name.startswith('try_false_stub') and
                    first_new_line.startswith('catch')):
                    skip_shift_at_start = True
                    break

        # 뒤 라인 밀기 (skip_shift_at_start이면 start+1부터)
        shift_from = start + 1 if skip_shift_at_start else start
        for old_ln in sorted([ln for ln in self.full_code_lines if ln >= shift_from], reverse=True):
            self.full_code_lines[old_ln + offset] = self.full_code_lines.pop(old_ln)
            self._shift_meta(old_ln, old_ln + offset)

        # 삽입
        for i, ln in enumerate(range(start, start + offset)):
            line = new_lines[i]
            self.full_code_lines[ln] = line
            self.update_brace_count(ln, line)  # ★ 항상 카운트
            if self._should_trigger_analysis(line):  # ★ 트리거 라인만 분석
                self.analyze_context(ln, line)

    def update_code(self, start_line: int, end_line: int, new_code: str, event: str):
        self.current_start_line = start_line
        self.current_end_line = end_line
        self.current_edit_event = event

        if event not in {"add", "modify", "delete"}:
            raise ValueError(f"unknown event '{event}'")

        if event == "add":
            # ★ 같은 라인에 annotation 추가하는 경우 (append, shift 없음)
            # 예: 라인 10에 "uint256 x = 10;"이 있고, "// @During x == 10"을 추가
            if (start_line in self.full_code_lines and
                new_code.strip().startswith("// @")):
                # 기존 라인 끝에 annotation 추가
                existing = self.full_code_lines[start_line]
                self.full_code_lines[start_line] = existing.rstrip() + "  " + new_code.strip()
                self.update_brace_count(start_line, self.full_code_lines[start_line])
                if self._should_trigger_analysis(new_code):
                    self.analyze_context(start_line, self.full_code_lines[start_line])
            else:
                # 기존 로직 (새 라인 삽입, shift 발생)
                lines = new_code.split("\n")
                self._insert_lines(start_line, lines)  # _insert_lines 내부에서 정규화


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
                self.update_brace_count(ln, line)  # ★ 추가
                if self._should_trigger_analysis(line):  # ★ 추가
                    self.analyze_context(ln, line)
                ln += 1

        elif event == "delete":
            offset = end_line - start_line + 1

            # 기존 라인 제거
            for ln in range(start_line, end_line + 1):
                self.full_code_lines.pop(ln, None)
                self.line_info.pop(ln, None)
                self.recorder.ledger.pop(ln, None)  # ← recorder 같이 비움

            # 뒤쪽 라인 당기기
            keys_to_shift = sorted([ln for ln in self.full_code_lines if ln > end_line])
            for old_ln in keys_to_shift:
                new_ln = old_ln - offset
                self.full_code_lines[new_ln] = self.full_code_lines.pop(old_ln)
                self._shift_meta(old_ln, new_ln)

        # full-code 재조합
        self.full_code = "\n".join(self.full_code_lines[ln] for ln in sorted(self.full_code_lines))

        # add/modify 후 전체 블록의 컨텍스트 설정
        # 여러 줄짜리 정의(함수/constructor/modifier 등)의 경우,
        # 마지막 라인('}')이 분석을 스킵하므로 컨텍스트가 설정되지 않음
        # 따라서 전체 코드 블록을 대상으로 한 번 더 analyze_context 호출
        if event in {"add", "modify"} and new_code.strip():
            self.analyze_context(start_line, new_code)

    def normalize_compound_control_lines(self, lines: list[str]) -> list[str]:
        """
        한 물리 라인에 '} else if', '} else', '} while' 이 붙어있는 경우
        '}' 과 그 뒤 토큰을 서로 다른 라인으로 나눠
        [논리] 라인 배열로 정규화한다.
        """
        out: list[str] = []
        # '}' 바로 뒤에 else/while 이 오는 모든 케이스를 split
        pat = re.compile(r'}\s*(?=else\b|while\b)')

        for s in lines:
            rest = s
            while True:
                m = pat.search(rest)
                if not m:
                    out.append(rest)
                    break
                # '}' 까지를 앞라인, 그 뒤(else|while...)를 다음 라인으로
                left = rest[:m.start()] + "}"
                right = rest[m.end():].lstrip()
                out.append(left)
                rest = right
        return out

    # ContractAnalyzer.py (클래스 내부)
    def _should_trigger_analysis(self, code_line: str) -> bool:
        s = (code_line or "").strip()
        if not s:
            return False
        if s == "}":  # 단독 '}'는 분석 스킵(괄호 카운트만)
            return False
        if s.startswith("//"):
            return s.startswith("// @")  # 디버그 주석만 분석
        if s.endswith(";"):
            return True  # 일반 문장
        # 여러 줄짜리 함수/modifier/constructor 정의의 끝 부분
        # 예: "    ) external isAllowed {"
        if ')' in s and '{' in s and not s.startswith(('if', 'for', 'while', 'else')):
            return True
        # 블록 헤더 키워드
        return bool(re.match(
            r"^(abstract\s+contract|contract|library|interface|function|constructor|modifier|"
            r"struct|enum|event|if|else(\s+if)?\b|for|while|do\b|try|catch|unchecked|assembly)\b", s))

    def compile_check(self) -> None:
        wanted = '0.8.0'

        # ① 아직 안 깔려 있으면 다운로드
        if wanted not in get_installed_solc_versions():
            print(f"[info] installing solc {wanted} …")
            install_solc(wanted)  # 네트워크·권한 오류나면 여기서 예외 발생

        # ② 방금(또는 이전에) 받은 버전을 active 로 지정
        set_solc_version(wanted)

        # ③ 실제 컴파일
        try:
            compile_source(self.full_code)
            print("[ok] solidity compiled successfully")
        except SolcError as e:
            print("[err] Solidity compiler reported:\n", e)
        except Exception as e:
            print("[err] unexpected:", e)

    def update_brace_count(self, line_number, code):
        open_braces = code.count('{')
        close_braces = code.count('}')
        # 기존 정보 보존하면서 업데이트
        if line_number not in self.line_info:
            self.line_info[line_number] = {"open": 0, "close": 0, "cfg_nodes": []}
        info = self.line_info[line_number]
        info['open'] = open_braces
        info['close'] = close_braces

    def analyze_context(self, start_line, new_code):
        stripped_code = (new_code or "").strip()

        # 단독 '}'는 컨텍스트 분석 불필요 (괄호 정보만으로 충분)
        if stripped_code == "}":
            return

        # pragma는 contract 외부에 있으므로 특별 처리
        if stripped_code.startswith("pragma"):
            self.current_context_type = "pragma"
            return

        # import도 contract 외부
        if stripped_code.startswith("import"):
            self.current_context_type = "import"
            return

        # ★ statement + annotation이 같은 줄에 있는지 확인
        # 예: uint256 x = 10;  // @During x == 10
        statement_part = None
        annotation_part = None

        if '// @' in stripped_code:
            if stripped_code.startswith('// @'):
                # annotation만 있음
                annotation_part = stripped_code
            else:
                # statement + annotation 분리
                idx = stripped_code.index('// @')
                statement_part = stripped_code[:idx].strip()
                annotation_part = stripped_code[idx:].strip()
        else:
            # statement만 있음
            statement_part = stripped_code

        # ★ 분리 정보 저장 (test.py에서 사용)
        self.last_statement_part = statement_part
        self.last_annotation_part = annotation_part

        # ★ Annotation이 있으면 intentUnit context 설정
        if annotation_part:
            self.current_context_type = "intentUnit"
            self.current_target_contract = self.find_contract_context(start_line)
            self.current_target_function = self.find_function_context(start_line)
            # annotation만 있는 경우 여기서 종료
            if not statement_part:
                return

        # ★ Statement가 있으면 기존 로직으로 처리
        if not statement_part:
            return

        # 매 분석마다 초기화 (annotation이 없는 경우에만)
        if not annotation_part:
            self.current_context_type = None
            self.current_target_contract = None
            self.current_target_function = None
            self.current_target_struct = None

        # ★ statement_part를 기준으로 컨텍스트 분석
        stripped_code = statement_part

        # 새로 추가된 코드 블록의 컨텍스트를 분석
        if stripped_code.endswith(';'):
            if 'while' in stripped_code :
                self.current_context_type = "doWhileWhile"
                pass

            parent_context = self.find_parent_context(start_line)
            if parent_context in ["contract", "library", "interface",
                                  "abstract contract"]:  # 시작 규칙 : interactiveSourceUnit
                if 'constant' in stripped_code or 'immutable' in stripped_code:
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
                self.current_target_function = self.find_function_context(start_line)

        elif ',' in stripped_code:
            # 함수 정의인지 확인 (괄호 열고 닫힌 경우는 함수 파라미터로 가정)
            if '(' in stripped_code and ')' in stripped_code:
                self.current_context_type = "functionDefinition"
                self.current_target_contract = self.find_contract_context(start_line)
                self.current_target_function = self.find_function_context(start_line)

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
                    check_code = self.full_code_lines.get(check_line, '').strip()
                    if check_code.startswith('function'):
                        self.current_context_type = 'function'
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

            self.current_target_function = self.find_function_context(start_line)


        # 최종적으로 context가 제대로 파악되지 않은 경우
        # 여러 줄짜리 정의문의 중간 줄이거나, 컨텍스트 분석이 불필요한 줄은 조용히 넘어감
        if not self.current_target_contract and self.current_context_type:
            # context_type은 설정되었는데 contract를 찾지 못한 경우에만 오류
            raise ValueError(f"Contract context not found for line {start_line}")
        if self.current_context_type == "simpleStatement" and not self.current_target_function:
            raise ValueError(f"Function context not found for simple statement at line {start_line}")

    def find_parent_context(self, line_number):
        close_brace_count = 0

        # 위로 거슬러 올라가면서 `{`와 `}`의 짝을 찾기
        for line in range(line_number - 1, 0, -1):
            brace_info = self.line_info.get(line, {'open': 0, 'close': 0, 'cfg_nodes': []})
            open_braces = brace_info['open']
            close_braces = brace_info['close']

            if close_brace_count > 0:
                close_brace_count -= open_braces
                if close_brace_count <= 0:
                    close_brace_count = 0
            else:
                if open_braces > 0:
                    return self.determine_top_level_context(self.full_code_lines[line])
                close_brace_count += close_braces

        return "unknown"

    def find_contract_context(self, line_number):
        # 위로 거슬러 올라가면서 해당 라인이 속한 컨트랙트를 찾습니다.
        close_brace_count = 0

        for line in range(line_number, 0, -1):
            brace_info = self.line_info.get(line, {'open': 0, 'close': 0, 'cfg_nodes': []})
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
                    code_line = self.full_code_lines.get(line, '').strip()
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

    def find_function_context(self, line_number):
        # 위로 거슬러 올라가면서 해당 라인이 속한 함수를 찾습니다.
        # 방법 1: '{' 문자가 있는 라인을 찾고, 그 라인부터 위로 function 키워드를 찾는다

        # 먼저 가장 가까운 '{' 문자가 있는 라인을 찾기
        open_brace_line = None
        close_brace_count = 0

        for line in range(line_number, 0, -1):
            brace_info = self.line_info.get(line, {'open': 0, 'close': 0, 'cfg_nodes': []})
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
            return None

        # '{' 문자가 있는 라인부터 위로 올라가면서 function/constructor/modifier 키워드를 찾기
        for line in range(open_brace_line, 0, -1):
            code_line = self.full_code_lines.get(line, "").strip()
            if not code_line:
                continue

            # function, constructor, modifier 키워드를 찾으면 함수 이름 추출
            if code_line.startswith("function "):
                # 함수 이름 추출
                parts = code_line.split()
                if len(parts) >= 2:
                    function_name = parts[1].split('(')[0]
                    return function_name
            elif code_line.startswith("constructor"):
                return "constructor"
            elif code_line.startswith("modifier "):
                parts = code_line.split()
                if len(parts) >= 2:
                    modifier_name = parts[1].split('(')[0]
                    return modifier_name
            elif code_line.startswith("fallback"):
                return "fallback"
            elif code_line.startswith("receive"):
                return "receive"

            # contract/struct/interface 등을 만나면 함수가 아니므로 중단
            if any(code_line.startswith(kw) for kw in ["contract ", "library ", "interface ", "struct ", "enum "]):
                break

        return None

    def find_struct_context(self, line_number):
        # 위로 거슬러 올라가면서 해당 라인이 속한 함수를 찾습니다.
        for line in range(line_number, 0, -1):
            brace_info = self.line_info.get(line, {'open': 0, 'close': 0, 'cfg_nodes': []})
            cfg_nodes = brace_info.get('cfg_nodes', [])
            if brace_info['open'] > 0 and cfg_nodes:
                context_type = self.determine_top_level_context(self.full_code_lines[line])
                if context_type == "struct":
                    return self.full_code_lines[line].split()[1]

    def determine_top_level_context(self, code_line):
        try:
            # 코드 라인의 내용에 따라 최상위 컨텍스트를 결정
            stripped_code = code_line.strip()

            if stripped_code.startswith("contract"):
                return "contract"
            elif stripped_code.startswith("interface"):
                return "interface"
            elif stripped_code.startswith("library"):
                return "library"
            elif stripped_code.startswith("function"):
                return "function"
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

    def get_full_code(self):
        return self.full_code

    def get_current_context_type(self):
        return self.current_context_type

    """
    cfg part    
    """

    # ContractAnalyzer.py  (일부)

    def make_contract_cfg(self, contract_name: str, parent_contracts: list[str] = None):
        """
        contract-level CFG를 처음 만들 때 한 번 호출.
        address 계열 글로벌은 UnsignedIntegerInterval(160bit) 로,
        uint  계열은 [0,0] 256-bit Interval 로 초기화한다.

        Args:
            contract_name: 컨트랙트 이름
            parent_contracts: 상속받는 부모 컨트랙트 이름 리스트 (MRO 순서)
        """
        self.current_target_contract = contract_name
        cfg = StaticCFGFactory.make_contract_cfg(self, contract_name)

        # 상속 관계 설정
        if parent_contracts:
            self._setup_inheritance(cfg, parent_contracts)

        self.line_info[self.current_start_line]['cfg_nodes'] = [cfg]

    def make_abstract_contract_cfg(self, contract_name: str, parent_contracts: list[str] = None):
        """
        abstract contract-level CFG를 처음 만들 때 한 번 호출.
        ContractCFG와 동일하지만 AbstractContractCFG 클래스 사용.

        Args:
            contract_name: 컨트랙트 이름
            parent_contracts: 상속받는 부모 컨트랙트 이름 리스트 (MRO 순서)
        """
        from Utils.CFG import AbstractContractCFG

        self.current_target_contract = contract_name

        # 이미 존재하면 재사용
        if contract_name in self.contract_cfgs:
            cfg = self.contract_cfgs[contract_name]
            self.line_info[self.current_start_line]['cfg_nodes'] = [cfg]
            return

        # AbstractContractCFG 생성
        cfg = AbstractContractCFG(contract_name)

        # 글로벌 변수 설정 (StaticCFGFactory의 로직 재사용)
        cfg.globals = StaticCFGFactory._create_global_variables(self)

        # 글로벌 변수 등록
        for gv in cfg.globals.values():
            self.register_var(gv)

        # contract_cfgs에 저장
        self.contract_cfgs[contract_name] = cfg

        # 상속 관계 설정
        if parent_contracts:
            self._setup_inheritance(cfg, parent_contracts)

        self.line_info[self.current_start_line]['cfg_nodes'] = [cfg]

    def _setup_inheritance(self, cfg, parent_contracts: list[str]):
        """
        상속 관계를 설정한다.
        - parent_contracts 리스트 저장
        - parent_cfgs에 부모 CFG 참조 연결
        - 부모의 state variables 복사
        - 부모의 struct/enum 정의 복사

        Args:
            cfg: 현재 컨트랙트/abstract 컨트랙트 CFG
            parent_contracts: 부모 컨트랙트 이름 리스트
        """
        cfg.parent_contracts = parent_contracts

        for parent_name in parent_contracts:
            # 부모 CFG 찾기 (이미 분석되어 있어야 함)
            parent_cfg = self.contract_cfgs.get(parent_name)
            if parent_cfg:
                cfg.parent_cfgs[parent_name] = parent_cfg

                # 부모의 state variables 복사
                if parent_cfg.state_variable_node:
                    if not cfg.state_variable_node:
                        cfg.initialize_state_variable_node()
                    for var_name, var_obj in parent_cfg.state_variable_node.variables.items():
                        # 이미 존재하지 않는 경우에만 복사
                        if var_name not in cfg.state_variable_node.variables:
                            # 변수 복사 (얕은 복사로 참조 공유)
                            cfg.state_variable_node.variables[var_name] = var_obj

                # 부모의 struct 정의 복사
                for struct_name, struct_def in parent_cfg.structDefs.items():
                    if struct_name not in cfg.structDefs:
                        cfg.structDefs[struct_name] = struct_def

                # 부모의 enum 정의 복사
                for enum_name, enum_def in parent_cfg.enumDefs.items():
                    if enum_name not in cfg.enumDefs:
                        cfg.enumDefs[enum_name] = enum_def

    def make_interface_cfg(self, interface_name: str, parent_interfaces: list[str] = None):
        """
        Interface CFG를 생성한다.
        Interface는 함수 body가 없으므로 시그니처만 저장.

        Args:
            interface_name: Interface 이름
            parent_interfaces: 상속받는 부모 interface 이름 리스트
        """
        from Utils.CFG import InterfaceCFG

        # 이미 존재하면 재사용
        if interface_name in self.interface_cfgs:
            return

        # InterfaceCFG 생성
        interface_cfg = InterfaceCFG(interface_name)

        # 부모 interface 연결
        if parent_interfaces:
            interface_cfg.parent_interfaces = parent_interfaces
            for parent_name in parent_interfaces:
                parent_cfg = self.interface_cfgs.get(parent_name)
                if parent_cfg:
                    interface_cfg.parent_cfgs[parent_name] = parent_cfg

        # interface_cfgs에 저장
        self.interface_cfgs[interface_name] = interface_cfg

        # contract_cfgs에도 저장 (타입 검색 호환성)
        self.contract_cfgs[interface_name] = interface_cfg

        self.line_info[self.current_start_line]['cfg_nodes'] = [interface_cfg]

    def make_library_cfg(self, library_name: str):
        """
        library-level CFG를 처음 만들 때 한 번 호출.
        라이브러리는 state variable이 없고 함수만 포함한다.
        """
        from Utils.CFG import LibraryCFG

        self.current_target_contract = library_name  # 라이브러리도 contract로 처리
        library_cfg = LibraryCFG(library_name)

        # 라이브러리 CFG를 저장
        self.library_cfgs[library_name] = library_cfg
        self.contract_cfgs[library_name] = library_cfg  # 호환성을 위해 contract_cfgs에도 저장

        # line_info 업데이트 (전체 파싱 모드에서는 current_start_line이 None일 수 있음)
        if self.current_start_line is not None:
            if self.current_start_line not in self.line_info:
                self.line_info[self.current_start_line] = {'open': 0, 'close': 0, 'cfg_nodes': []}
            self.line_info[self.current_start_line]['cfg_nodes'] = [library_cfg]
        
    def process_using_directive(self, library_name: str, target_type: str = None):
        """
        using directive 처리: using LibraryName for TargetType;
        현재 컨트랙트에 라이브러리를 연결한다.
        """
        # 현재 컨트랙트 CFG 가져오기
        current_contract_cfg = self.contract_cfgs.get(self.current_target_contract)
        if not current_contract_cfg:
            raise ValueError(f"No contract CFG found for {self.current_target_contract}")
            
        # 라이브러리 CFG 찾기 또는 로드
        library_cfg = self.load_library_cfg(library_name)
        if not library_cfg:
            raise ValueError(f"Library '{library_name}' not found. Please ensure it's defined or available.")
            
        # 컨트랙트에 라이브러리 연결
        current_contract_cfg.add_using_library(library_cfg, target_type)

    # for interactiveEnumDefinition in Solidity.g4
    def process_enum_definition(self, enum_name):
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)

        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 새로운 EnumDefinition 객체 생성
        enum_def = EnumDefinition(enum_name)
        contract_cfg.define_enum(enum_name, enum_def)

        # brace_count 업데이트
        self.line_info[self.current_start_line]['cfg_nodes'] = [enum_def]

    def process_enum_item(self, items):
        # 현재 타겟 컨트랙트의 CFG 가져오기
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)

        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # brace_count에서 가장 최근의 enum 정의를 찾습니다.
        enum_def = None
        for line in reversed(range(self.current_start_line + 1)):
            context = self.line_info.get(line)
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
        self.line_info[self.current_start_line]['cfg_nodes'] = [contract_cfg.structDefs]

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
                if variable_obj.typeInfo.structTypeName in contract_cfg.structDefs.keys():
                    struct_def = contract_cfg.structDefs[variable_obj.typeInfo.structTypeName]
                    variable_obj.initialize_struct(struct_def)
                else :
                    ValueError(f"This struct def {variable_obj.typeInfo.structTypeName} is undefined")
            elif isinstance(variable_obj, MappingVariable) :
                pass
            elif isinstance(variable_obj,EnumVariable) :
                pass
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
        for function_cfg in contract_cfg.functions.values():
            function_cfg.add_related_variable(variable_obj.identifier, variable_obj)

        # 6. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 7. brace_count 업데이트
        self.line_info[self.current_start_line]['cfg_nodes'] = [contract_cfg.state_variable_node]

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
            raise ValueError(f"{type_name.capitalize()} variables cannot be declared as constant: '{variable_obj.identifier}'")

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
        else:
            # 기타 지원되지 않는 타입
            raise ValueError(f"Type category '{variable_obj.typeInfo.typeCategory}' cannot be declared as constant: '{variable_obj.identifier}'")

        variable_obj.isConstant = True  # constant 플래그 설정

        self.register_var(variable_obj)

        # 3. ContractCFG 에 추가 (state 변수와 동일 API 사용)
        contract_cfg.add_state_variable(variable_obj, expr=init_expr, line_no=self.current_start_line)

        # 4. 이미 생성된 모든 FunctionCFG 에 read-only 변수로 연동
        for fn_cfg in contract_cfg.functions.values():
            fn_cfg.add_related_variable(variable_obj.identifier, variable_obj)

        # 5. 전역 map 업데이트
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 6. brace_count 갱신 → IDE/커서 매핑
        self.line_info[self.current_start_line]["cfg_nodes"] = [contract_cfg.state_variable_node]

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
        self.line_info[self.current_start_line]['cfg_nodes'] = [mod_cfg.get_entry_node()]
        self.line_info[self.current_end_line]['cfg_nodes'] = [mod_cfg.get_exit_node()]

    # ContractAnalyzer.py  ----------------------------------------------

    def process_modifier_invocation(self,
                                    fn_cfg: FunctionCFG,
                                    modifier_name: str) -> None:
        """
        fn_cfg  ← 방금 만들고 있는 함수-CFG
        modifier_name  ← 'onlyOwner' 처럼 한 개

        ① 컨트랙트에 등록돼 있는 modifier-CFG 가져오기
        ② modifier-CFG 를 *얕은 복사* 하여 fn_cfg.graph 에 붙인다.
        ③ placeholder 노드(들)를 fn-entry/exit 로 스플라이스
        """

        contract_cfg = self.contract_cfgs[self.current_target_contract]

        # ── ① modifier 존재 확인 ──────────────────────────────────
        if modifier_name not in contract_cfg.functions:
            raise ValueError(f"Modifier '{modifier_name}' is not defined.")

        mod_cfg: FunctionCFG = contract_cfg.functions[modifier_name]

        self.builder.splice_modifier(fn_cfg, mod_cfg, modifier_name)

    def process_constructor_definition(self, name, params, modifiers):
        ccf = self.contract_cfgs[self.current_target_contract]

        ctor_cfg = StaticCFGFactory.make_constructor_cfg(
            self, name, params, modifiers
        )
        ccf.add_constructor_to_cfg(ctor_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

        # brace_count - 디폴트 entry 등록
        self.line_info[self.current_start_line]["cfg_nodes"] = [ctor_cfg.get_entry_node()]

    # ContractAnalyzer.py  ─ process_function_definition  (address-symb ✚ 최신 Array/Struct 초기화 반영)

    def process_function_definition(
            self,
            function_name: str,
            parameters: list[tuple[SolType, str]],
            modifiers: list[str],
            returns: list[Variables] | None,
    ):
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if contract_cfg is None:
            raise ValueError(f"Contract CFG for {self.current_target_contract} not found.")

        fcfg = StaticCFGFactory.make_function_cfg(self, function_name, parameters, modifiers, returns)

        contract_cfg.functions[function_name] = fcfg
        self.contract_cfgs[self.current_target_contract] = contract_cfg
        self.line_info[self.current_start_line]["cfg_nodes"] = [fcfg.get_entry_node()]
        # Don't overwrite existing nodes in line_info for end_line, just add EXIT if not present
        if self.current_end_line not in self.line_info:
            self.line_info[self.current_end_line] = {"open": 0, "close": 0, "cfg_nodes": []}
        exit_node = fcfg.get_exit_node()
        if exit_node not in self.line_info[self.current_end_line]["cfg_nodes"]:
            self.line_info[self.current_end_line]["cfg_nodes"].append(exit_node)

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
            v = MappingVariable(
                identifier=var_name,
                key_type=type_obj.mappingKeyType,
                value_type=type_obj.mappingValueType,
                scope="local",
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
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
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
                if v.typeInfo.structTypeName not in ccf.structDefs:
                    raise ValueError(f"Undefined struct {v.typeInfo.structTypeName}")
                v.initialize_struct(ccf.structDefs[v.typeInfo.structTypeName])

            # ── enum 기본 (첫 멤버)
            elif isinstance(v, EnumVariable):
                enum_def = ccf.enumDefs.get(v.typeInfo.enumTypeName)
                if enum_def:
                    v.valueIndex = 0
                    v.value = enum_def.members[0]

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
            line_info=self.line_info,  # ← builder가 필요하다면 전달
        )
        if stmt_blk.is_loop_body :
            self.recorder.record_variable_declaration(
                line_no=self.current_start_line,
                var_name=var_name,
                var_obj=v,
            )

        self.engine.reinterpret_from(fcfg, stmt_blk)

        # ────────────────── ④ 저장 & 정리 ────────────────────
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
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
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
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
            line_info=self.line_info,
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

        # 저장 & 정리
        ccf.functions[self.current_target_function] = fcfg
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
            v.initialize_struct(ccf.structDefs[v.typeInfo.structTypeName])

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

    # Analyzer/ContractAnalyzer.py
    def process_assignment_expression(self, expr: Expression) -> None:
        # 1. CFG 컨텍스트 --------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
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
            line_info=self.line_info,
        )

        self.engine.reinterpret_from(fcfg, stmt_blk)

        # 4. constructor 특수 처리 & 저장 -------------------------------
        if fcfg.function_type == "constructor":
            state_vars = ccf.state_variable_node.variables

            # ③ scope=='state' 인 항목을 그대로 복사해 덮어쓰기
            for name, var in state_vars.items():
                if getattr(var, "scope", None) != "state":
                    continue
                state_vars[name] = VariableEnv.copy_variables({name: var})[name]

        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    # --------------------------------------------------------------
    #  ++x / --x   (prefix·suffix 공통)
    # --------------------------------------------------------------
    def handle_unary_incdec(self, expr: Expression,
                             op_sign: str,  # "+=" | "-="
                             stmt_kind: str):  # "unary_prefix" | "unary_suffix"
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("active FunctionCFG not found")
        fcfg = self.current_target_function_cfg

        cur_blk = self.builder.get_current_block()

        # ① 현재 값 읽기 → 타입에 맞는 "1" Interval 준비 -------------
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
            line_info=self.line_info,
        )

        self.engine.reinterpret_from(fcfg, stmt_blk)

        # ④ constructor 특수 처리 + 저장 ---------------------------
        if fcfg == "constructor":
            state_vars = ccf.state_variable_node.variables

            # ③ scope=='state' 인 항목을 그대로 복사해 덮어쓰기
            for name, var in state_vars.items():
                if getattr(var, "scope", None) != "state":
                    continue
                state_vars[name] = VariableEnv.copy_variables({name: var})[name]

        self.current_target_function_cfg.update_block(cur_blk)
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    # --------------------------------------------------------------
    #  delete <expr>
    # --------------------------------------------------------------
    def handle_delete(self, target_expr: Expression):
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
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
            line_info=self.line_info,
        )

        self.engine.reinterpret_from(fcfg, stmt_blk)

        self.current_target_function_cfg.update_block(cur_blk)
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
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
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
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

        # ③ CFG 노드/엣지 정리  ----------------------------------------
        stmt_blk = self.builder.build_function_call_statement(
            cur_block=cur_blk,
            expr=expr,
            line_no=self.current_start_line,
            fcfg=fcfg,
            line_info=self.line_info,
        )

        self.engine.reinterpret_from(fcfg, stmt_blk)

        # ④ constructor 특수 처리  -------------------------------------
        if fcfg == "constructor":
            state_vars = ccf.state_variable_node.variables
            # ‣ scope=='state' 인 항목만 deep-copy 로 덮어쓰기
            for name, var in state_vars.items():
                if getattr(var, "scope", None) != "state":
                    continue
                state_vars[name] = VariableEnv.copy_variables({name: var})[name]

        # ⑤ CFG 저장  ---------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_payable_function_call(self, expr):
        """
        payable(addr) 함수 호출 처리
        - address를 payable address로 변환
        - 추상 해석에서는 address와 동일하게 AddressSet 반환
        """
        # 1. CFG 컨텍스트
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            return

        cur_blk = self.builder.get_current_block()
        if cur_blk is None:
            return

        # 2. 인자 평가 (payable(addr)의 addr)
        if expr.arguments:
            arg_val = self.evaluator.evaluate_expression(
                expr.arguments[0], cur_blk.variables, None, None
            )
            # payable 변환 결과는 AddressSet
            # (실제 평가는 Evaluation.py의 type conversion에서 처리됨)

        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_function_call_options(self, expr):
        # Handle function calls with options
        pass

    def process_if_statement(self, condition_expr: Expression) -> None:
        # ── 1. CFG 컨텍스트 ─────────────────────────────────────────────
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
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
            line_info=self.line_info,
            end_line=self.current_end_line,
        )

        self.engine.reinterpret_from(fcfg, join)

        # ── 4. 저장 & 마무리 ───────────────────────────────────────────
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_else_if_statement(self, condition_expr: Expression) -> None:
        ccf = self.contract_cfgs[self.current_target_contract]
        fcfg = ccf.get_function_cfg(self.current_target_function)
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
            line_info=self.line_info,
            end_line=end_line,
        )

        # seed: 외부 join을 우선, 없으면 로컬 join
        outer = self.builder.find_outer_join_near(anchor_line=self.current_start_line,
                                                  fcfg=fcfg, direction="backward",
                                                  include_anchor=False)
        seed = outer or local_join
        self.engine.reinterpret_from(fcfg, seed)

        ccf.functions[self.current_target_function] = fcfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_else_statement(self) -> None:
        # ── 1. CFG 컨텍스트 --------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
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
            line_info=self.line_info,
            end_line=self.current_end_line,
        )

        self.engine.reinterpret_from(fcfg, join)

        # ── 5. 저장 ----------------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_while_statement(self, condition_expr: Expression) -> None:
        # 1. CFG 컨텍스트 ---------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
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
            line_info=self.line_info,
            end_line=getattr(self, "current_end_line", None),  # ★ 추가
        )

        # ★ reinterpret: loop-exit을 seed로
        self.engine.reinterpret_from(self.current_target_function_cfg, exit_node)

        # 4. 저장 ----------------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_for_statement(
            self,
            initial_statement: dict | None = None,
            condition_expr: Expression | None = None,
            increment_expr: Expression | None = None,
    ) -> None:
        # 1. CFG 컨텍스트 --------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
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
            line_info=self.line_info,
            end_line=getattr(self, "current_end_line", None),  # ★ 추가
        )

        # ★ reinterpret: loop-exit을 seed로
        self.engine.reinterpret_from(self.current_target_function_cfg, exit_node)

        # 6. 저장 ---------------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_continue_statement(self) -> None:
        # 1) CFG 컨텍스트
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'continue'.")

        # 2) 현재 블록
        cur_blk = self.builder.get_current_block()

        # ★ 빌더가 loop-exit 을 반환
        exit_node = self.builder.build_continue_statement(
            cur_block=cur_blk,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # ★ reinterpret seed = loop-exit
        self.engine.reinterpret_from(self.current_target_function_cfg, exit_node)

        # 5) 저장
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_break_statement(self) -> None:
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'break'.")

        cur_blk = self.builder.get_current_block()

        # ★ 빌더가 loop-exit 을 반환
        exit_node = self.builder.build_break_statement(
            cur_block=cur_blk,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # ★ reinterpret seed = loop-exit
        self.engine.reinterpret_from(self.current_target_function_cfg, exit_node)

        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_assembly_assignment(self, var_name: str) -> None:
        """
        Assembly 블록 내 변수 할당 처리:
        - 해당 변수가 Solidity 스코프에 존재하면 Top으로 설정
        - Assembly에서 값을 직접 조작하므로 정확한 값 추적 불가
        """
        # 1. CFG 컨텍스트
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            return  # 함수 컨텍스트 없으면 무시

        cur_blk = self.builder.get_current_block()
        if cur_blk is None:
            return

        # 2. 변수가 현재 스코프에 존재하는지 확인
        if var_name not in cur_blk.variables:
            return  # Yul 로컬 변수거나 존재하지 않는 변수

        var_obj = cur_blk.variables[var_name]

        # 3. Statement 생성 (assembly 타입)
        stmt = Statement(statement_type='assembly', variable_name=var_name)
        cur_blk.statements.append(stmt)

        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    # Analyzer/ContractAnalyzer.py
    def process_return_statement(self, return_expr: Expression | None = None) -> None:
        # ── 1. CFG 컨텍스트 -------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'return'.")

        cur_blk = self.builder.get_current_block()

        # ── 2. 값 평가 ------------------------------------------------------
        r_val = None
        if return_expr is not None:
            r_val = self.evaluator.evaluate_expression(
                return_expr, cur_blk.variables, None, None
            )

        # ★ 빌더가 '재배선 전' succ 들을 반환
        succ_before = self.builder.build_return_statement(
            cur_block=cur_blk,
            return_expr=return_expr,
            return_val=r_val,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # ── 4. 기록 ---------------------------------------------------------
        self.recorder.record_return(
            line_no=self.current_start_line,
            return_expr=return_expr,
            return_val=r_val,
            fn_cfg=self.current_target_function_cfg,
        )

        # ★ reinterpret seed = 연결하기 '전' succ(들)
        if succ_before:
            self.engine.reinterpret_from(self.current_target_function_cfg, succ_before)

        # ── 5. CFG 저장 -----------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    # Analyzer/ContractAnalyzer.py
    def process_revert_statement(
            self,
            revert_identifier: str | None = None,
            string_literal: str | None = None,
            call_argument_list: list[Expression] | None = None,
    ) -> None:
        # ── 1. CFG context ---------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'revert'.")

        cur_blk = self.builder.get_current_block()

        # ★ 빌더가 '재배선 전' succ 들을 반환
        succ_before = self.builder.build_revert_statement(
            cur_block=cur_blk,
            revert_id=revert_identifier,
            string_literal=string_literal,
            call_args=call_argument_list,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # ★ reinterpret seed = 연결하기 '전' succ(들)
        if succ_before:
            self.engine.reinterpret_from(self.current_target_function_cfg, succ_before)

        # ── 4. save CFG ------------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    # Analyzer/ContractAnalyzer.py
    def process_require_statement(
            self,
            condition_expr: Expression,
            string_literal: str | None,
    ) -> None:
        # 1) CFG context -----------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
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
            line_info=self.line_info,
        )

        # ★ reinterpret seed = true-분기 succ(들)
        if true_succs:
            self.engine.reinterpret_from(self.current_target_function_cfg, true_succs)

        # 5) 저장 ------------------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    # Analyzer/ContractAnalyzer.py
    def process_assert_statement(
            self,
            condition_expr: Expression,
            string_literal: str | None,
    ) -> None:
        # 1) CFG context -----------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
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
            line_info=self.line_info,
        )

        # ★ reinterpret seed = true-분기 succ(들)
        if true_succs:
            self.engine.reinterpret_from(self.current_target_function_cfg, true_succs)

        # 5) 저장 -------------------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
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
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)

        # ── modifier placeholder ('_') --------------------------------------
        if (ident == "_" and self.current_target_function_cfg
                and self.current_target_function_cfg.function_type == "modifier"):
            cur_blk = self.builder.get_current_block()

            # ⬇️  새 helper 호출
            self.builder.build_modifier_placeholder(
                cur_block=cur_blk,
                fcfg=self.current_target_function_cfg,
                line_no=self.current_start_line,
                line_info=self.line_info,
            )
            return  # 값-해석 없음

        # … 이하 "일반 identifier" 처리는 기존 로직 유지 …

    # Analyzer/ContractAnalyzer.py
    def process_unchecked_indicator(self) -> None:
        # ── 1. CFG 컨텍스트 --------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'unchecked'.")

        # ── 2. 현재 블록, 빌더 호출 -------------------------------------
        cur_blk = self.builder.get_current_block()

        self.builder.build_unchecked_block(
            cur_block=cur_blk,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # ── 3. 저장 ------------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    # Analyzer/ContractAnalyzer.py  내부 메소드들 추가/교체

    def process_do_statement(self):
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        fcfg = self.current_target_function_cfg
        if not fcfg:
            raise ValueError("No current target function to attach do-while.")

        pred = self.builder.get_current_block()  # prev 앵커
        self.builder.build_do_statement(
            cur_block=pred, line_no=self.current_start_line,
            fcfg=fcfg, line_info = self.line_info
        )

    def process_do_while_statement(self, condition_expr):
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
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
            line_info = self.line_info
        )

        # ★ seed = loop exit
        self.engine.reinterpret_from(fcfg, exit_node)

    def process_try_statement(self, function_expr, returns):
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        fcfg = self.current_target_function_cfg
        if not fcfg:
            raise ValueError("No current target function for try.")

        pred = self.builder.get_current_block()  # 이전 블록 기준

        # returns 로컬 생성(⊥) 후 true 블록 env 에 심기
        cond, true_blk, false_stub, join = self.builder.build_try_skeleton(
            cur_block=pred, function_expr=function_expr,
            line_no=self.current_start_line, fcfg=fcfg, line_info=self.line_info
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

    def process_catch_clause(self, catch_ident, params):
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
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
            line_no=self.current_start_line, fcfg=fcfg, line_info=self.line_info
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
        self.current_target_function_cfg = cfg.get_function_cfg(self.current_target_function)

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

        # ↳ 주소형이면 AddressManager 에 기록
        if g.typeInfo.elementaryTypeName == "address" and isinstance(g.value, AddressSet):
            addr_set = g.value
            if addr_set.is_singleton():  # singleton 형식
                nid = addr_set.get_singleton_id()
                address_manager.register_id(nid, g.identifier)
                address_manager.bind_var(g.identifier, addr_set)

        self._batch_targets.add(self.current_target_function_cfg)

        self.current_target_function_cfg = None

    # ─────────────────────────────────────────────────────────────
    def process_state_var_for_debug(self, lhs_expr: Expression, value):

        try:
            ccf  = self.contract_cfgs[self.current_target_contract]
            self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
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
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
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

    # -----------------------------------------------------------
    # ANNOTATION STORAGE HELPERS
    # -----------------------------------------------------------
    
    def store_during_annotation(self, annotation_type: str, line_no: int, **params):
        """During annotation을 brace_count에 저장"""
        if line_no not in self.line_info:
            self.line_info[line_no] = {'open': 0, 'close': 0, 'cfg_nodes': []}

        if 'during_annotations' not in self.line_info[line_no]:
            self.line_info[line_no]['during_annotations'] = []

        # DuringAnnotation 객체 생성
        annotation = DuringAnnotation(annotation_type, line_no, **params)
        self.line_info[line_no]['during_annotations'].append(annotation)

    def store_post_annotation(self, annotation_type: str, line_no: int, **params):
        """Post annotation을 brace_count에 저장"""
        if line_no not in self.line_info:
            self.line_info[line_no] = {'open': 0, 'close': 0, 'cfg_nodes': []}

        if 'post_annotations' not in self.line_info[line_no]:
            self.line_info[line_no]['post_annotations'] = []

        # PostAnnotation 객체 생성
        annotation = PostAnnotation(annotation_type, line_no, **params)
        self.line_info[line_no]['post_annotations'].append(annotation)

    def get_function_lines(self, function_name: str) -> tuple[int, int] | None:
        """함수의 시작/끝 라인 번호 반환"""
        ccf = self.contract_cfgs.get(self.current_target_contract)
        if not ccf or function_name not in ccf.functions:
            return None

        fcfg = ccf.functions[function_name]
        entry_node = fcfg.get_entry_node()

        # 함수 시작 라인 찾기
        start_line = None
        for ln, info in self.line_info.items():
            cfg_nodes = info.get('cfg_nodes', [])
            if entry_node in cfg_nodes:
                start_line = ln
                break

        if start_line is None:
            return None

        # 함수 끝 라인 찾기 (brace 균형으로 계산)
        balance = 0
        for ln in range(start_line, max(self.line_info.keys()) + 1):
            info = self.line_info.get(ln, {})
            balance += info.get('open', 0) - info.get('close', 0)
            if balance == 0 and ln > start_line:
                return (start_line, ln)

        return None

    # -----------------------------------------------------------
    # DURING-INTENT PROCESSOR (논리 연산자 지원)
    # -----------------------------------------------------------

    def process_during(self, clauses: list, logic_ops: list):
        """
        논리 연산자로 연결된 during clause들을 처리
        1. 복합 annotation으로 저장
        2. 정적 분석 수행 (interval 기반)
        3. 결과 기록

        Args:
            clauses: List[dict] - 각 clause 정보
            logic_ops: List[str] - 논리 연산자 ('&&' or '||')
        """
        line_no = self.current_start_line

        # 1. 복합 annotation 생성 및 저장
        compound = CompoundDuringAnnotation(line_no, clauses, logic_ops)

        if line_no not in self.line_info:
            self.line_info[line_no] = {}
        if 'during_annotations' not in self.line_info[line_no]:
            self.line_info[line_no]['during_annotations'] = []

        self.line_info[line_no]['during_annotations'].append(compound)

        # 2. 정적 분석 수행 (interval 기반)
        result = self._verify_compound_during_static(clauses, logic_ops, line_no)

        # 3. 결과 기록
        self.recorder.record_verification_result(line_no, "during", result)

        return result

    def _verify_compound_during_static(self, clauses: list, logic_ops: list, line_no: int) -> dict:
        """
        정적 분석: 각 clause를 검증하고 논리 연산자로 조합
        """
        results = []

        # 각 clause 검증
        for clause in clauses:
            result = self._verify_during_clause_static(clause, line_no)
            results.append(result)

        # 논리 연산자로 조합
        if len(results) == 0:
            return {"status": "error", "message": "No clauses to verify"}
        elif len(results) == 1:
            return results[0]
        else:
            return self._combine_logic_results(results, logic_ops)

    def _verify_during_clause_static(self, clause: dict, line_no: int) -> dict:
        """개별 during clause 정적 검증"""
        kind = clause["kind"]

        if kind == "beforeAfter":
            return self.guardian_verifier.verify_during_before_after(
                var_ref=clause["var"],
                comp_op=clause["op"],
                line_no=line_no,
                cfg_node=self._cfg_node_at(line_no)
            )
        elif kind == "assignCurrent":
            return self.guardian_verifier.verify_during_assign_current(
                var_ref=clause["var"],
                comp_op=clause["op"],
                line_no=line_no,
                cfg_node=self._cfg_node_at(line_no)
            )
        elif kind == "retExpr":
            return self.guardian_verifier.verify_during_return_expression(
                comp_op=clause["op"],
                value_expr=clause["rhs"],
                line_no=line_no,
                cfg_node=self._cfg_node_at(line_no)
            )
        elif kind == "retIndex":
            return self.guardian_verifier.verify_during_return_index(
                index=clause["index"],
                comp_op=clause["op"],
                value_expr=clause["rhs"],
                line_no=line_no,
                cfg_node=self._cfg_node_at(line_no)
            )
        elif kind == "retVar":
            return self.guardian_verifier.verify_during_return_variable(
                var_ref=clause["lhs"],
                comp_op=clause["op"],
                value_expr=clause["rhs"],
                line_no=line_no,
                cfg_node=self._cfg_node_at(line_no)
            )
        elif kind == "direct":
            return self.guardian_verifier.verify_during_direct_comparison(
                lhs_expr=clause["lhs"],
                comp_op=clause["op"],
                rhs_expr=clause["rhs"],
                line_no=line_no,
                cfg_node=self._cfg_node_at(line_no)
            )
        elif kind == "implication":
            return self.guardian_verifier.verify_during_implication(
                antecedent=clause["antecedent"],
                consequent=clause["consequent"],
                line_no=line_no,
                cfg_node=self._cfg_node_at(line_no)
            )
        elif kind == "functionArg":
            return self.guardian_verifier.verify_during_function_arg(
                func_name=clause["func_name"],
                arg_index=clause["arg_index"],
                comp_op=clause["op"],
                rhs_expr=clause["rhs"],
                line_no=line_no,
                cfg_node=self._cfg_node_at(line_no)
            )
        # percentOf, ceil, floor 등 추가 가능
        else:
            return {"status": "error", "message": f"Unknown clause kind: {kind}"}

    # -----------------------------------------------------------
    # POST-INTENT PROCESSOR (논리 연산자 지원)
    # -----------------------------------------------------------

    def process_post(self, clauses: list, logic_ops: list):
        """
        논리 연산자로 연결된 post clause들을 처리
        1. 복합 annotation으로 저장
        2. 정적 분석 수행 (interval 기반)
        3. 결과 기록

        Args:
            clauses: List[dict] - 각 clause 정보
            logic_ops: List[str] - 논리 연산자 ('&&' or '||')
        """
        line_no = self.current_start_line

        # 1. 복합 annotation 생성 및 저장
        compound = CompoundPostAnnotation(line_no, clauses, logic_ops)

        if line_no not in self.line_info:
            self.line_info[line_no] = {}
        if 'post_annotations' not in self.line_info[line_no]:
            self.line_info[line_no]['post_annotations'] = []

        self.line_info[line_no]['post_annotations'].append(compound)

        # 2. 정적 분석 수행 (interval 기반)
        result = self._verify_compound_post_static(clauses, logic_ops, line_no)

        # 3. 결과 기록
        self.recorder.record_verification_result(line_no, "post", result)

        return result

    def _verify_compound_post_static(self, clauses: list, logic_ops: list, line_no: int) -> dict:
        """
        정적 분석: 각 clause를 검증하고 논리 연산자로 조합
        """
        results = []

        # 각 clause 검증
        for clause in clauses:
            result = self._verify_post_clause_static(clause, line_no)
            results.append(result)

        # 논리 연산자로 조합
        if len(results) == 0:
            return {"status": "error", "message": "No clauses to verify"}
        elif len(results) == 1:
            return results[0]
        else:
            return self._combine_logic_results(results, logic_ops)

    def _verify_post_clause_static(self, clause: dict, line_no: int) -> dict:
        """개별 post clause 정적 검증"""
        kind = clause["kind"]

        if kind == "entryExit":
            return self.guardian_verifier.verify_post_entry_exit(
                var_ref=clause["var"],
                comp_op=clause["op"],
                line_no=line_no,
                fn_cfg=self.current_target_function_cfg
            )
        elif kind == "unchanged":
            return self.guardian_verifier.verify_post_unchanged(
                var_ref=clause["var"],
                line_no=line_no,
                fn_cfg=self.current_target_function_cfg
            )
        elif kind == "retExpr":
            return self.guardian_verifier.verify_post_return_expression(
                comp_op=clause["op"],
                value_expr=clause["rhs"],
                line_no=line_no,
                fn_cfg=self.current_target_function_cfg
            )
        elif kind == "retIndex":
            return self.guardian_verifier.verify_post_return_index(
                index=clause["index"],
                comp_op=clause["op"],
                value_expr=clause["rhs"],
                line_no=line_no,
                fn_cfg=self.current_target_function_cfg
            )
        elif kind == "retVar":
            return self.guardian_verifier.verify_post_return_variable(
                var_ref=clause["lhs"],
                comp_op=clause["op"],
                value_expr=clause["rhs"],
                line_no=line_no,
                fn_cfg=self.current_target_function_cfg
            )
        elif kind == "direct":
            return self.guardian_verifier.verify_post_direct_comparison(
                lhs_expr=clause["lhs"],
                comp_op=clause["op"],
                rhs_expr=clause["rhs"],
                line_no=line_no,
                fn_cfg=self.current_target_function_cfg
            )
        elif kind == "implication":
            return self.guardian_verifier.verify_post_implication(
                antecedent=clause["antecedent"],
                consequent=clause["consequent"],
                line_no=line_no,
                fn_cfg=self.current_target_function_cfg
            )
        # percentOf, ceil, floor 등 추가 가능
        else:
            return {"status": "error", "message": f"Unknown clause kind: {kind}"}

    # -----------------------------------------------------------
    # 논리 연산 결과 조합
    # -----------------------------------------------------------

    def _combine_logic_results(self, results: list, logic_ops: list) -> dict:
        """
        논리 연산자에 따라 검증 결과 조합

        Args:
            results: List[dict] - 각 clause의 검증 결과
            logic_ops: List[str] - '&&' or '||'

        Returns:
            최종 조합된 검증 결과
        """
        if not results:
            return {"status": "error", "message": "No results"}

        if len(results) == 1:
            return results[0]

        final = results[0]

        for i, op in enumerate(logic_ops):
            next_result = results[i + 1]

            if op == '&&':
                # AND: 둘 다 success여야 success
                if final.get("status") == "success" and next_result.get("status") == "success":
                    final = {
                        "status": "success",
                        "message": f"({final.get('message', 'ok')}) && ({next_result.get('message', 'ok')})",
                        "left": final,
                        "right": next_result,
                        "operator": "&&"
                    }
                elif final.get("status") == "violation" or next_result.get("status") == "violation":
                    final = {
                        "status": "violation",
                        "message": f"AND violated",
                        "left": final,
                        "right": next_result,
                        "operator": "&&"
                    }
                else:
                    final = {
                        "status": "unknown",
                        "message": f"AND uncertain",
                        "left": final,
                        "right": next_result,
                        "operator": "&&"
                    }

            else:  # '||'
                # OR: 하나라도 success면 success
                if final.get("status") == "success" or next_result.get("status") == "success":
                    final = {
                        "status": "success",
                        "message": f"OR satisfied",
                        "left": final,
                        "right": next_result,
                        "operator": "||"
                    }
                elif final.get("status") == "violation" and next_result.get("status") == "violation":
                    final = {
                        "status": "violation",
                        "message": f"OR violated",
                        "left": final,
                        "right": next_result,
                        "operator": "||"
                    }
                else:
                    final = {
                        "status": "unknown",
                        "message": f"OR uncertain",
                        "left": final,
                        "right": next_result,
                        "operator": "||"
                    }

        return final

    def get_line_analysis(self, start_ln: int, end_ln: int) -> dict[int, list[dict]]:
        """
        [start_ln, end_ln] 구간에 대해
        { line_no: [ {kind: ..., vars:{...}}, ... ], ... }  형태 반환
        (구간 안에 기록이 없으면 key 자체가 없다)
        """
        return {
            ln: self.analysis_per_line[ln]
            for ln in range(start_ln, end_ln + 1)
            if ln in self.analysis_per_line
        }

    def send_report_to_front(
            self,
            patched_lines: list[tuple[str, int, int]] | None = None
    ) -> None:

        # 0) ‘어떤 라인을 보여줄지’ 결정 ---------------------------
        touched: set[int] = set()

        # (A) 호출 측에서 주석 라인을 넘겨준 경우
        if patched_lines:
            for _code, s, e in patched_lines:
                touched.update(range(s, e + 1))

        # (B) 주석 라인을 안 받았거나, 비어 있다면
        #     ⇢ 방금 재-해석한 함수 전체 라인 사용
        if not touched and getattr(self, "_last_func_lines", None):
            s, e = self._last_func_lines
            touched.update(range(s, e + 1))

        if not touched:
            print("※ send_report_to_front : 보여줄 라인이 없습니다.")
            return

        # 1) 라인별 분석 결과 수집 -------------------------------
        lmin, lmax = min(touched), max(touched)
        payload = self.get_line_analysis(lmin, lmax)

        if not payload:
            print("※ 분석 결과가 없습니다.")
            return

        print("\n=======  ANALYSIS  =======")
        for ln in sorted(payload):
            for rec in payload[ln]:
                kind = rec.get("kind", "?")
                vars_ = rec.get("vars", {})
                print(f"{ln:4} │ {kind:<12} │ {vars_}")
        print("==========================\n")

    # ContractAnalyzer.py  (클래스 내부)

    def flush_reinterpret_target(self) -> None:
        if not self._batch_targets:
            return
        fcfg = self._batch_targets.pop()
        self.engine.interpret_function_cfg(fcfg, None)

        ln_set = {st.src_line
                  for blk in fcfg.graph.nodes
                  for st in blk.statements
                  if getattr(st, "src_line", None)}
        self._last_func_lines = (min(ln_set), max(ln_set)) if ln_set else None

    # helper – 라인 ↦ CFG 노드 ↦ 변수 환경
    def _env_at_line(self, line_no: int):
        node = self.line_info.get(line_no, {}).get("cfg_node")
        if node is None:
            raise ValueError(f"No CFG node bound to line {line_no}")
        return node.variables, node  # (env, node object)

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

    def _cfg_node_at(self, line_no: int):
        cfg_nodes = (self.line_info.get(line_no, {}) or {}).get("cfg_nodes", [])
        return cfg_nodes[0] if cfg_nodes else None


    def load_library_cfg(self, library_name: str) -> 'LibraryCFG':
        """
        라이브러리 CFG를 로드한다.
        1. 메모리에 이미 있으면 반환
        2. 없으면 파일에서 로드 시도
        3. 그래도 없으면 None 반환
        """
        # 1. 메모리에서 찾기
        if library_name in self.library_cfgs:
            return self.library_cfgs[library_name]

        # 2. CFGSerializer를 통해 파일에서 로드
        library_cfg = self.cfg_serializer.load_library_cfg(library_name)
        if library_cfg:
            self.library_cfgs[library_name] = library_cfg
            return library_cfg

        # 3. 찾을 수 없음
        return None

    # ─────────────────────────────────────────────────────────────
    #  pragma / event / emit 처리
    # ─────────────────────────────────────────────────────────────
    def process_pragma_directive(self, pragma_name: str, pragma_value: str):
        """
        pragma directive 처리
        예: pragma solidity ^0.8.0; → pragma_name="solidity", pragma_value="^0.8.0"
        """
        directive = {"name": pragma_name, "value": pragma_value}
        self.pragma_directives.append(directive)

        # solidity 버전 pragma면 버전 정보 저장
        if pragma_name == "solidity":
            self.pragma_version = pragma_value

    def process_event_definition(self, event_name: str, parameters: list):
        """
        event 정의 처리
        parameters: list of (SolType, param_name, is_indexed)
        """
        if not self.current_target_contract:
            return

        if self.current_target_contract not in self.contract_cfgs:
            return

        ccf = self.contract_cfgs[self.current_target_contract]
        ccf.events[event_name] = {
            "name": event_name,
            "parameters": parameters  # [(SolType, name, indexed), ...]
        }

    def process_emit_statement(self, event_name: str, arguments: list):
        """
        emit 문 처리 - FunctionCFG의 현재 블록에 emit statement 추가
        """
        if not self.current_target_contract or not self.current_target_function:
            return

        ccf = self.contract_cfgs.get(self.current_target_contract)
        if not ccf:
            return

        fcfg = ccf.functions.get(self.current_target_function)
        if not fcfg:
            return

        # 현재 블록에 emit statement 추가
        cur_block = self.builder.get_current_block()
        if cur_block:
            stmt = Statement(statement_type='emit', variable_name=event_name)
            stmt.emit_arguments = arguments
            stmt.src_line = self.current_start_line
            cur_block.statements.append(stmt)