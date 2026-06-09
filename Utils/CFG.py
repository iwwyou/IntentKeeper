import networkx as nx
from typing import Any
from Domain.IR import *
from Domain.Variable import *

class CFGNode:
    def __init__(self, name,
                 # ───── condition / branch role flags ─────────────────────────
                 condition_node: bool = False,
                 condition_node_type: str | None = None,  # "if" | "else_if" | "require" | "while" | "for" | "do_while" …
                 branch_node: bool = False,               # pruned-dummy/basic after a cond
                 is_true_branch: bool = False,
                 # ───── loop / join / sink flags ──────────────────────────────
                 join_point_node: bool = False,           # 🔹 명시적 조인 노드
                 fixpoint_evaluation_node: bool = False,  # φ / back-edge 합류 노드
                 loop_exit_node: bool = False,            # while/for False-branch 종착
                 is_for_increment: bool = False,          # for(i;cond;i++) 의 incr 블록
                 is_loop_body: bool = False,              # 루프 본문 블록 여부(선택)
                 # ───── misc ─────────────────────────────────────────────────
                 unchecked_block: bool = False,
                 src_line: int | None = None):
        self.name = name

        # condition / branch
        self.condition_node = condition_node
        self.condition_expr = None
        self.condition_node_type = condition_node_type  # 표준화: "else_if", "do_while" 사용
        self.branch_node = branch_node
        self.is_true_branch = is_true_branch

        # join / loop / φ
        self.join_point_node = join_point_node
        self.fixpoint_evaluation_node = fixpoint_evaluation_node
        self.loop_exit_node = loop_exit_node
        self.is_for_increment = is_for_increment
        self.is_loop_body = is_loop_body

        # φ/조인 관련 보조 env
        self.fixpoint_evaluation_node_vars = {}  # while-header 진입 시점 env 스냅샷
        self.join_baseline_env = None

        # unchecked
        self.unchecked_block = unchecked_block

        # payload
        self.statements: list[Statement] = []   # 블록 내 명령어
        self.variables: dict[str, Variables] = {}  # var_name -> Variables
        self.before_envs: dict[int, dict[str, Variables]] = {}

        # sink kinds
        self.function_exit_node = False         # 함수 정상 종료(기본 EXIT)
        self.return_exit_node = False           # 🔹 명시적 return 전용 sink
        self.error_exit_node = False            # 🔹 revert/require 실패 전용 sink

        # return values (for exit aggregation)
        self.return_vals: dict[int, object] = {}

        self.src_line = src_line
        self.function_evaluated = None

        # intent annotations attached to this node
        self.intents: list[dict] = []  # @During, @Post 등

    def add_variable_declaration_statement(self, typeObj, varName, initExpr, line_no):

        # Statement 생성
        variableDeclarationStatment = Statement(
            statement_type='variableDeclaration',
            type_obj=typeObj,
            var_name=varName,
            init_expr=initExpr,
            src_line=line_no
        )

        self.statements.append(variableDeclarationStatment)

    def add_assign_statement(self, exprLeft, exprOperator, exprRight, line_no):

        # Statement 생성
        assignment_stmt = Statement(
            statement_type='assignment',
            left=exprLeft,
            operator=exprOperator,
            right=exprRight,
            src_line=line_no
        )
        self.statements.append(assignment_stmt)

    def add_unary_statement(self, operand, operator, line_no):
        """
        ++x, --y, delete z 같은 단항 연산 전용 스테이트먼트를 블록에 추가.
        ─ operand  : Expression (피연산자)
        ─ operator : '++' | '--' | 'delete' …
        ─ line_no  : 소스 코드 라인 번호
        """
        unary_stmt = Statement(
            statement_type='unary',
            operand=operand,
            operator=operator,
            src_line=line_no,
        )
        self.statements.append(unary_stmt)

        # 변수 정보 업데이트는 update_left_Var 관련 함수에서 수행

    def add_function_call_statement(self, function_expr: Expression, line_no):
        """
        함수 호출문을 CFG에 추가합니다.
        :param function_expr: 함수 호출 Expression 객체
        """
        function_call_stmt = Statement(
            statement_type='functionCall',
            function_expr=function_expr,
            src_line=line_no
        )
        self.statements.append(function_call_stmt)

    def add_return_statement(self, return_expr: Expression, line_no):
        """
        반환 구문을 CFG에 추가하고, 반환 값을 업데이트합니다.
        :param return_expr: 반환할 Expression 객체
        """
        return_stmt = Statement(
            statement_type='return',
            return_expr=return_expr,
            src_line=line_no
        )
        self.statements.append(return_stmt)

    def add_continue_statement(self, line_no):
        continue_stmt = Statement(statement_type='continue',
                                  src_line=line_no)
        self.statements.append(continue_stmt)

    def add_break_statement(self, line_no):
        break_stmt = Statement(statement_type='break',
                               src_line=line_no)
        self.statements.append(break_stmt)

    def add_revert_statement(self, revert_identifier=None, string_literal=None, call_argument_list=None,
                             line_no=None):
        # 4. Revert 문장을 Statement 객체로 만들어서 현재 블록에 추가
        revert_statement = Statement(
            statement_type="revert",
            identifier=revert_identifier,
            string_literal=string_literal,
            arguments=call_argument_list,
            src_line=line_no
        )
        self.statements.append(revert_statement)

    def get_variable(self, var_name: str) -> Variables:
        """
        변수 이름을 받아 관련 변수를 반환합니다.
        :param var_name: 변수 이름 (identifier)
        :return: Variables 객체
        """
        return self.variables.get(var_name)
    
    def serialize_for_storage(self) -> dict:
        """CFGNode를 저장을 위해 직렬화"""
        serialized_statements = []
        for stmt in self.statements:
            if hasattr(stmt, 'serialize_for_storage'):
                serialized_statements.append(stmt.serialize_for_storage())
            else:
                serialized_statements.append(str(stmt))
        
        serialized_variables = {}
        for var_name, var_obj in self.variables.items():
            if hasattr(var_obj, 'serialize_for_storage'):
                serialized_variables[var_name] = var_obj.serialize_for_storage()
            else:
                serialized_variables[var_name] = str(var_obj)
        
        return {
            'name': self.name,
            'condition_node': self.condition_node,
            'condition_node_type': self.condition_node_type,
            'branch_node': self.branch_node,
            'is_true_branch': self.is_true_branch,
            'join_point_node': self.join_point_node,
            'fixpoint_evaluation_node': self.fixpoint_evaluation_node,
            'is_for_increment': self.is_for_increment,
            'loop_exit_node': self.loop_exit_node,
            'is_loop_body': self.is_loop_body,
            'unchecked_block': self.unchecked_block,
            'function_exit_node': self.function_exit_node,
            'src_line': self.src_line,
            'statements': serialized_statements,
            'variables': serialized_variables
        }

class CFG:
    def __init__(self, cfg_type):
        self.graph = nx.DiGraph()
        self.cfg_type = cfg_type
        self.entry_node = CFGNode("ENTRY")
        self.exit_node = CFGNode("EXIT")
        self.exit_node.function_exit_node = True  # 🔹 명시
        self.graph.add_node(self.entry_node)
        self.graph.add_node(self.exit_node)
        self.graph.add_edge(self.entry_node, self.exit_node)

    def get_entry_node(self):
        return self.entry_node

    def get_exit_node(self):
        return self.exit_node
    
    def serialize_graph_structure(self) -> dict:
        """그래프 구조를 직렬화"""
        nodes = []
        edges = []
        
        for node in self.graph.nodes():
            if hasattr(node, 'serialize_for_storage'):
                nodes.append(node.serialize_for_storage())
            else:
                nodes.append({'name': str(node)})
        
        for edge in self.graph.edges(data=True):
            source_name = edge[0].name if hasattr(edge[0], 'name') else str(edge[0])
            target_name = edge[1].name if hasattr(edge[1], 'name') else str(edge[1])
            edges.append({
                'source': source_name,
                'target': target_name,
                'data': edge[2]
            })
        
        return {
            'nodes': nodes,
            'edges': edges
        }


class ContractCFG(CFG):
    def __init__(self, contract_name):
        super().__init__('contract')
        self.contract_name = contract_name
        self.is_interface = False
        self.state_variable_node = None

        self.structDefs = {}  # name -> StructDefinition 객체
        self.structVars = {} # name -> StructVariable 객체

        self.enumDefs = {} # name -> EnumDefinition 객체
        self.enumVars = {} # name -> EnumVariable 객체

        self.constructor = None  # FunctionCFG (Constructor Type)
        self.fallback = None
        self.receive = None

        #self.modifiers = {}  # name -> FunctionCFG
        self.functions = {}  # name -> {signature -> FunctionCFG}  (overloading 지원)

        # Event 정의 저장
        self.events = {}  # name -> EventDefinition (parameters list)

        self.globals: dict[str, GlobalVariable] = {}

        # Using directive 지원: type -> [LibraryCFG, ...]  (같은 타입에 여러 library 가능)
        self.using_libraries: dict[str, list['LibraryCFG']] = {}
        self.using_all_libraries: list['LibraryCFG'] = []   # using Library for *;

        # 상속 지원: parent contracts
        self.parent_contracts: list[str] = []  # ['Context', 'Ownable'] - MRO 순서
        self.parent_cfgs: dict[str, 'ContractCFG'] = {}  # name -> ContractCFG 참조

    def initialize_state_variable_node(self):
        self.state_variable_node = CFGNode('State_Variable')
        self.graph.add_node(self.state_variable_node)

        # 기존 entry node의 successor를 새로운 state variable node의 successor로 설정
        successors = list(self.graph.successors(self.entry_node))
        for succ in successors:
            self.graph.add_edge(self.state_variable_node, succ)
            self.graph.remove_edge(self.entry_node, succ)

        # 새로운 state variable node를 entry node의 successor로 설정
        self.graph.add_edge(self.entry_node, self.state_variable_node)


    # Enum 정의 추가
    def define_enum(self, enum_name, enum_def):
        if enum_name not in self.enumDefs:
            self.enumDefs[enum_name] = enum_def
        else:
            raise ValueError(f"Enum {enum_name} is already defined.")

    # Struct 정의 추가
    def define_struct(self, struct_def_obj):
        self.structDefs[struct_def_obj.struct_name] = struct_def_obj

    def add_enum_member(self, enum_name, member_name):
        if enum_name in self.enumDefs:
            self.enumDefs[enum_name].add_member(member_name)
        else:
            raise ValueError(f"Enum {enum_name} is not defined.")

    def add_struct_member(self, struct_def_name, var_name, var_obj):
        if struct_def_name in self.structDefs :
            self.structDefs[struct_def_name].add_member(var_name, var_obj)
        else :
            raise ValueError(f"Struct {struct_def_name} is not defined/")

    def add_state_variable(self, variable, expr=None, line_no=None): # variable : Variables, expr : Interval
        self.state_variable_node.add_assign_statement(
            exprLeft=variable,  # 좌변
            exprRight=expr,  # 우변 (Expression | None)
            exprOperator='=',  # 연산자
            line_no=line_no
        )

        self.state_variable_node.variables[variable.identifier] = variable

    def add_constant_variable(self, variable, expr=None):
        if not self.state_variable_node:
            self.state_variable_node = CFGNode('State_Variable')
            self.graph.add_node(self.state_variable_node)

        # 상수 변수 정보를 노드에 추가
        variable.constant_expression = expr  # Store expression as attribute
        self.state_variable_node.variables[variable.identifier] = variable

    def add_constructor_to_cfg(self, constructor_cfg):
        # 1. 상태변수 노드의 successor가 생성자가 되도록 설정
        if self.state_variable_node:
            # 상태변수 노드의 모든 successor를 가져옴
            successors = list(self.graph.successors(self.state_variable_node))
            for succ in successors:
                # 기존 상태변수 노드의 successor를 생성자의 exit_node와 연결
                self.graph.add_edge(constructor_cfg.exit_node, succ)
                # 상태변수 노드의 기존 successor 간선 삭제
                self.graph.remove_edge(self.state_variable_node, succ)

            # 상태변수 노드를 생성자의 entry_node와 연결
            self.graph.add_edge(self.state_variable_node, constructor_cfg.entry_node)
        else:
            # 상태변수 노드가 없을 경우 entry_node와 생성자 entry_node 연결
            self.graph.add_edge(self.entry_node, constructor_cfg.entry_node)

        # 2. ContractCFG에 생성자 CFG 추가
        self.constructor = constructor_cfg

    #def get_modifier_cfg(self, modifier_name):
    #    # modifier가 존재하면 해당 CFG를 반환하고, 없으면 None을 반환
    #    return self.modifiers.get(modifier_name)

    def add_function_cfg(self, function_name, function_cfg):
        sig = self._build_signature(function_cfg)
        if function_name not in self.functions:
            self.functions[function_name] = {}
        self.functions[function_name][sig] = function_cfg

    def update_function_cfg(self, function_name, function_cfg):
        """기존에 등록된 함수의 CFG를 동일 signature로 업데이트"""
        if function_name not in self.functions:
            self.add_function_cfg(function_name, function_cfg)
            return
        sub = self.functions[function_name]
        sig = self._build_signature(function_cfg)
        if sig in sub:
            sub[sig] = function_cfg
        elif len(sub) == 1:
            # signature 불일치지만 1개뿐이면 교체 (process 중 업데이트)
            key = next(iter(sub))
            sub[key] = function_cfg
        else:
            sub[sig] = function_cfg

    def get_function_cfg(self, function_name, param_types=None):
        """함수 CFG 반환. overload 시 param_types로 매칭."""
        # constructor 특별 처리
        if function_name == "constructor" and self.constructor is not None:
            return self.constructor
        sub = self.functions.get(function_name)
        if sub is None:
            return None
        if len(sub) == 1:
            return next(iter(sub.values()))
        if param_types is not None:
            sig = "(" + ",".join(param_types) + ")"
            return sub.get(sig)
        return next(iter(sub.values()))  # default: 첫 번째

    @staticmethod
    def _build_signature(fcfg) -> str:
        """FunctionCFG의 파라미터 타입으로 signature 생성"""
        if hasattr(fcfg, 'parameter_types') and fcfg.parameter_types:
            return "(" + ",".join(fcfg.parameter_types) + ")"
        return "()"
    
    def add_using_library(self, library_cfg: 'LibraryCFG', target_type: str = None, prepend: bool = False):
        """
        using directive 처리: using LibraryName for TargetType;
        target_type이 None이면 모든 타입에 적용 (using LibraryName for *;)
        prepend=True이면 리스트 앞에 삽입 (명시적 선언이 상속보다 우선)
        """
        if target_type is None:
            if library_cfg not in self.using_all_libraries:
                if prepend:
                    self.using_all_libraries.insert(0, library_cfg)
                else:
                    self.using_all_libraries.append(library_cfg)
        else:
            if target_type not in self.using_libraries:
                self.using_libraries[target_type] = []
            if library_cfg not in self.using_libraries[target_type]:
                if prepend:
                    self.using_libraries[target_type].insert(0, library_cfg)
                else:
                    self.using_libraries[target_type].append(library_cfg)

    def find_library_function(self, target_type: str, function_name: str, param_types=None, n_args: int = None) -> 'FunctionCFG':
        """
        target_type에 대한 라이브러리 함수를 찾아 반환
        예: find_library_function("uint256", "mul") -> SafeMath.mul
        n_args가 주어지면 인자 개수가 일치하는 overload를 우선 반환
        """
        def _search_libs(libs):
            for library_cfg in libs:
                if n_args is not None and function_name in library_cfg.functions:
                    for sig, fc in library_cfg.functions[function_name].items():
                        if len(fc.parameters) == n_args:
                            return fc
                else:
                    result = library_cfg.get_function_cfg(function_name, param_types)
                    if result is not None:
                        return result
            return None

        # 특정 타입에 대한 라이브러리 검색
        if target_type in self.using_libraries:
            result = _search_libs(self.using_libraries[target_type])
            if result:
                return result

        # using * 라이브러리들에서 검색
        result = _search_libs(self.using_all_libraries)
        if result:
            return result

        return None
    
    def iter_all_functions(self):
        """모든 FunctionCFG를 (name, fcfg) 튜플로 순회"""
        for name, sub in self.functions.items():
            for sig, fcfg in sub.items():
                yield name, fcfg

    def serialize_for_storage(self) -> dict:
        """ContractCFG를 저장을 위해 직렬화"""
        serialized_functions = {}
        for func_name, fcfg in self.iter_all_functions():
            key = func_name
            if hasattr(fcfg, 'serialize_for_storage'):
                serialized_functions[key] = fcfg.serialize_for_storage()
            else:
                serialized_functions[key] = str(fcfg)
        
        serialized_globals = {}
        for var_name, var_obj in self.globals.items():
            if hasattr(var_obj, 'serialize_for_storage'):
                serialized_globals[var_name] = var_obj.serialize_for_storage()
            else:
                serialized_globals[var_name] = str(var_obj)
        
        serialized_using_libraries = {}
        for target_type, lib_list in self.using_libraries.items():
            serialized_using_libraries[target_type] = []
            for lib_cfg in lib_list:
                if hasattr(lib_cfg, 'serialize_for_storage'):
                    serialized_using_libraries[target_type].append(lib_cfg.serialize_for_storage())
                else:
                    serialized_using_libraries[target_type].append(str(lib_cfg))
        
        serialized_using_all_libraries = []
        for lib_cfg in self.using_all_libraries:
            if hasattr(lib_cfg, 'serialize_for_storage'):
                serialized_using_all_libraries.append(lib_cfg.serialize_for_storage())
            else:
                serialized_using_all_libraries.append(str(lib_cfg))

        def _ser_struct_def(def_obj):
            return {
                "struct_name": def_obj.struct_name,
                "members": [
                    {
                        "member_name": m["member_name"],
                        "member_type": getattr(m["member_type"], "elementaryTypeName", None)
                                       or getattr(m["member_type"], "typeCategory", None)
                                       or str(m["member_type"])
                    }
                    for m in def_obj.members
                ]
            }

        def _ser_enum_def(def_obj):
            return {
                "enum_name": def_obj.enum_name,
                "members": list(def_obj.members)
            }

        return {
            'cfg_type': self.cfg_type,
            'contract_name': self.contract_name,
            'functions': serialized_functions,
            'globals': serialized_globals,
            'structDefs': {k: _ser_struct_def(v) for k, v in self.structDefs.items()},
            'structVars': self.structVars,  # 필요 없으면 빼도 됨 (아니면 안전화)
            'enumDefs': {k: _ser_enum_def(v) for k, v in self.enumDefs.items()},
            'enumVars': self.enumVars,  # 필요 없으면 빼도 됨
            'using_libraries': serialized_using_libraries,
            'using_all_libraries': serialized_using_all_libraries,
            'constructor': ...,
            'fallback': ...,
            'receive': ...,
            'graph_structure': self.serialize_graph_structure()
        }


class AbstractContractCFG(ContractCFG):
    """
    Abstract Contract를 위한 CFG 클래스
    - ContractCFG를 상속받아 동일한 구조를 가짐
    - is_abstract 플래그로 구분
    - abstract 함수 (body 없음)도 FunctionCFG로 생성 (entry→exit만)
    """
    def __init__(self, contract_name):
        super().__init__(contract_name)
        self.cfg_type = 'abstract_contract'
        self.is_abstract = True

    def serialize_for_storage(self) -> dict:
        """AbstractContractCFG를 저장을 위해 직렬화"""
        base_serialized = super().serialize_for_storage()
        base_serialized['cfg_type'] = 'abstract_contract'
        base_serialized['is_abstract'] = True
        return base_serialized


class FunctionCFG(CFG):
    def __init__(self, function_type, function_name=None):
        super().__init__('function')
        self.function_type = function_type  # constructor, fallback, receive, function, modifier
        self.function_name = function_name
        self.modifiers: dict[str, "FunctionCFG"] = {}
        self.related_variables: dict[str, Variables] = {}
        self.parameters: list[str] = []
        self.parameter_types: list[str] = []  # overloading 지원: ["uint256", "address", ...]
        self.return_types: list[SolType] = []
        self.return_vars: list[Variables] = []
        self.assign_env: dict[str, Variables] = {}   # 최초 스냅샷 전용
        self.ireturn_registry: dict[tuple, object] = {}  # @IReturn: (contractVar, funcName, index|None) → interval
        self.interface_var_types: dict[str, str] = {}  # 지역변수 중 interface 타입: var_name → interfaceName
        self.mutability: str | None = None  # "view", "pure", "payable", or None (default/nonpayable)

        # ── 분리된 sink 노드들 생성(빌더가 연결) ────────────────────────
        self.exit_node.function_exit_node = True
        self.return_exit = CFGNode("RETURN")
        self.return_exit.return_exit_node = True
        self.error_exit = CFGNode("ERROR")
        self.error_exit.error_exit_node = True
        self.graph.add_node(self.return_exit)
        self.graph.add_node(self.error_exit)

    # ── helpers ----------------------------------------------------------
    def get_return_exit_node(self) -> CFGNode:
        return self.return_exit

    def get_error_exit_node(self) -> CFGNode:
        return self.error_exit


    def update_block(self, block_node: CFGNode):
        if self.graph.has_node(block_node):
            self.graph.nodes[block_node].update(block_node.__dict__)
        else:
            raise ValueError(f"There is no {block_node} in FunctionCFG")

    # 🔹 두 형태 모두 허용: (var_obj) 또는 (name, var_obj)
    def add_related_variable(self, *args):
        if len(args) == 1:
            var_obj = args[0]
            self.related_variables[var_obj.identifier] = var_obj
        elif len(args) == 2:
            name, var_obj = args
            self.related_variables[name] = var_obj
        else:
            raise TypeError("add_related_variable expects (var_obj) or (name, var_obj)")

    def get_predecessor_node(self, cfg_node):
        if not self.graph.has_node(cfg_node):
            raise ValueError(f"There is no node in graph about {cfg_node}")
        preds = list(self.graph.predecessors(cfg_node))
        if not preds:
            raise ValueError("There is no predecessor")
        return preds

    def get_related_variable(self, var_name):
        return self.related_variables.get(var_name, None)

    def integrate_modifier(self, modifier_cfg):
        successors = list(self.graph.successors(self.get_entry_node()))
        self.graph.add_edge(self.get_entry_node(), modifier_cfg.get_entry_node())
        for succ in successors:
            self.graph.add_edge(modifier_cfg.get_exit_node(), succ)
            self.graph.remove_edge(self.get_entry_node(), succ)

    def get_true_block(self, condition_node):
        successors = list(self.graph.successors(condition_node))
        for successor in successors:
            if self.graph.edges[condition_node, successor].get('condition', False) is True:
                return successor
        return None

    def get_false_block(self, condition_node):
        successors = list(self.graph.successors(condition_node))
        for successor in successors:
            if self.graph.edges[condition_node, successor].get('condition', False) is False:
                return successor
        return None
    
    def serialize_for_storage(self) -> dict:
        """FunctionCFG를 저장을 위해 직렬화"""
        serialized_related_variables = {}
        for var_name, var_obj in self.related_variables.items():
            if hasattr(var_obj, 'serialize_for_storage'):
                serialized_related_variables[var_name] = var_obj.serialize_for_storage()
            else:
                serialized_related_variables[var_name] = str(var_obj)
        
        serialized_assign_env = {}
        for var_name, var_obj in self.assign_env.items():
            if hasattr(var_obj, 'serialize_for_storage'):
                serialized_assign_env[var_name] = var_obj.serialize_for_storage()
            else:
                serialized_assign_env[var_name] = str(var_obj)
        
        serialized_return_types = []
        for ret_type in self.return_types:
            if hasattr(ret_type, 'serialize_for_storage'):
                serialized_return_types.append(ret_type.serialize_for_storage())
            else:
                serialized_return_types.append(str(ret_type))
        
        return {
            'cfg_type': self.cfg_type,
            'function_type': self.function_type,
            'function_name': self.function_name,
            'parameters': self.parameters,
            'return_types': serialized_return_types,
            'return_vars': self.return_vars,
            'related_variables': serialized_related_variables,
            'assign_env': serialized_assign_env,
            'modifiers': self.modifiers,
            'graph_structure': self.serialize_graph_structure()
        }


class InterfaceCFG:
    """
    Solidity Interface를 위한 CFG 클래스
    - Interface는 함수 body가 없으므로 CFG를 상속하지 않음
    - 함수 시그니처만 저장 (파라미터, 반환 타입)
    - Interface 타입 변수는 AddressSet으로 처리
    - Interface 메서드 호출은 Top 반환
    """
    def __init__(self, interface_name: str):
        self.interface_name = interface_name
        self.cfg_type = 'interface'

        # 함수 시그니처: name -> {'parameters': [...], 'returns': [...]}
        self.function_signatures: dict[str, dict] = {}

        # 상속 지원 (interface도 다른 interface 상속 가능)
        self.parent_interfaces: list[str] = []
        self.parent_cfgs: dict[str, 'InterfaceCFG'] = {}

    def add_function_signature(self, func_name: str, parameters: list, returns: list):
        """Interface 함수 시그니처 추가"""
        self.function_signatures[func_name] = {
            'parameters': parameters,
            'returns': returns
        }

    def has_function(self, func_name: str) -> bool:
        """함수 시그니처 존재 여부 확인"""
        if func_name in self.function_signatures:
            return True
        # 부모 interface에서도 검색
        for parent_cfg in self.parent_cfgs.values():
            if parent_cfg.has_function(func_name):
                return True
        return False

    def get_function_signature(self, func_name: str) -> dict | None:
        """함수 시그니처 반환"""
        if func_name in self.function_signatures:
            return self.function_signatures[func_name]
        for parent_cfg in self.parent_cfgs.values():
            sig = parent_cfg.get_function_signature(func_name)
            if sig:
                return sig
        return None

    def serialize_for_storage(self) -> dict:
        """InterfaceCFG를 저장을 위해 직렬화"""
        return {
            'cfg_type': self.cfg_type,
            'interface_name': self.interface_name,
            'function_signatures': self.function_signatures,
            'parent_interfaces': self.parent_interfaces
        }


class LibraryCFG(CFG):
    """
    Solidity 라이브러리를 위한 CFG 클래스
    라이브러리는 state variable, constructor가 없고 함수만 포함
    하지만 constant 변수는 가질 수 있음
    """
    def __init__(self, library_name):
        super().__init__('library')
        self.library_name = library_name
        self.functions = {}  # name -> {signature -> FunctionCFG}  (overloading 지원)

        # 라이브러리도 constant 변수를 가질 수 있으므로 state_variable_node 지원
        self.state_variable_node = None

        self.structDefs = {}  # name -> StructDefinition 객체
        self.enumDefs = {}   # name -> EnumDefinition 객체

        self.globals: dict[str, 'GlobalVariable'] = {}

        # Library 내부의 using directive 지원 (e.g., using Address for address;)
        self.using_libraries: dict[str, list['LibraryCFG']] = {}
        self.using_all_libraries: list['LibraryCFG'] = []

    def add_function_cfg(self, function_name, function_cfg):
        """라이브러리 함수 CFG 추가"""
        sig = ContractCFG._build_signature(function_cfg)
        if function_name not in self.functions:
            self.functions[function_name] = {}
        self.functions[function_name][sig] = function_cfg

    def get_function_cfg(self, function_name, param_types=None):
        """라이브러리 함수 CFG 반환. overload 시 param_types로 매칭."""
        sub = self.functions.get(function_name)
        if sub is None:
            return None
        if len(sub) == 1:
            return next(iter(sub.values()))
        if param_types is not None:
            sig = "(" + ",".join(param_types) + ")"
            return sub.get(sig)
        return next(iter(sub.values()))

    def has_function(self, function_name: str) -> bool:
        """라이브러리에 해당 함수가 있는지 확인"""
        return function_name in self.functions
        
    def define_struct(self, struct_def_obj):
        """라이브러리 내 구조체 정의 추가"""
        self.structDefs[struct_def_obj.struct_name] = struct_def_obj

    def add_struct_member(self, struct_def_name, var_name, var_obj):
        """라이브러리 내 구조체 멤버 추가"""
        if struct_def_name in self.structDefs:
            self.structDefs[struct_def_name].add_member(var_name, var_obj)
        else:
            raise ValueError(f"Struct {struct_def_name} is not defined in library {self.library_name}.")

    def add_using_library(self, library_cfg: 'LibraryCFG', target_type: str = None, prepend: bool = False):
        """라이브러리 내 using directive 처리
        prepend=True이면 리스트 앞에 삽입 (명시적 선언이 상속보다 우선)"""
        if target_type is None:
            if library_cfg not in self.using_all_libraries:
                if prepend:
                    self.using_all_libraries.insert(0, library_cfg)
                else:
                    self.using_all_libraries.append(library_cfg)
        else:
            if target_type not in self.using_libraries:
                self.using_libraries[target_type] = []
            if library_cfg not in self.using_libraries[target_type]:
                if prepend:
                    self.using_libraries[target_type].insert(0, library_cfg)
                else:
                    self.using_libraries[target_type].append(library_cfg)

    def update_function_cfg(self, function_name, function_cfg):
        """기존에 등록된 함수의 CFG를 동일 signature로 업데이트"""
        if function_name not in self.functions:
            self.add_function_cfg(function_name, function_cfg)
            return
        sub = self.functions[function_name]
        sig = ContractCFG._build_signature(function_cfg)
        if sig in sub:
            sub[sig] = function_cfg
        elif len(sub) == 1:
            key = next(iter(sub))
            sub[key] = function_cfg
        else:
            sub[sig] = function_cfg

    def find_library_function(self, target_type: str, function_name: str, param_types=None, n_args: int = None) -> 'FunctionCFG':
        """라이브러리 내 using directive로 등록된 라이브러리 함수 검색
        n_args가 주어지면 인자 개수가 일치하는 overload를 우선 반환"""
        def _search_libs(libs):
            for lib in libs:
                if n_args is not None and function_name in lib.functions:
                    for sig, fc in lib.functions[function_name].items():
                        if len(fc.parameters) == n_args:
                            return fc
                else:
                    result = lib.get_function_cfg(function_name, param_types)
                    if result is not None:
                        return result
            return None

        if target_type in self.using_libraries:
            result = _search_libs(self.using_libraries[target_type])
            if result:
                return result
        result = _search_libs(self.using_all_libraries)
        if result:
            return result
        return None

    def define_enum(self, enum_name, enum_def):
        """라이브러리 내 열거형 정의 추가"""
        if enum_name not in self.enumDefs:
            self.enumDefs[enum_name] = enum_def
        else:
            raise ValueError(f"Enum {enum_name} is already defined in library {self.library_name}.")
    
    def initialize_state_variable_node(self):
        """라이브러리의 constant 변수를 위한 state variable node 초기화"""
        self.state_variable_node = CFGNode('Library_Constants')
        self.graph.add_node(self.state_variable_node)

        # 기존 entry node의 successor를 새로운 state variable node의 successor로 설정
        successors = list(self.graph.successors(self.entry_node))
        for succ in successors:
            self.graph.add_edge(self.state_variable_node, succ)
            self.graph.remove_edge(self.entry_node, succ)

        # 새로운 state variable node를 entry node의 successor로 설정
        self.graph.add_edge(self.entry_node, self.state_variable_node)
    
    def add_state_variable(self,
                           variable_obj,        # Variables | EnumVariable …
                           expr=None,           # Expression | Interval | None
                           line_no=None):
        """
        라이브러리 constant 변수(= state-level 상수)를 노드에 추가
        ContractCFG 와 동일한 signature 를 유지한다.
        """
        # (1) state-variable 노드가 없으면 생성
        if self.state_variable_node is None:
            self.initialize_state_variable_node()

        # (2) 노드에 ‘대입 스테이트먼트’ 형태로 기록
        #     - CFGNode.add_assign_statement(좌변, 우변, 연산자, line_no)
        self.state_variable_node.add_assign_statement(
            exprLeft     = variable_obj,  # 좌변
            exprOperator = '=',           # 단순 대입
            exprRight    = expr,          # 초기화 식 (없어도 None 허용)
            line_no      = line_no
        )

        # (3) 변수 테이블에 등록
        self.state_variable_node.variables[variable_obj.identifier] = variable_obj
            
    def iter_all_functions(self):
        """모든 FunctionCFG를 (name, fcfg) 튜플로 순회"""
        for name, sub in self.functions.items():
            for sig, fcfg in sub.items():
                yield name, fcfg

    def serialize_for_storage(self) -> dict:
        """라이브러리 CFG를 저장을 위해 직렬화"""
        serialized_functions = {}
        for func_name, fcfg in self.iter_all_functions():
            key = func_name
            if hasattr(fcfg, 'serialize_for_storage'):
                serialized_functions[key] = fcfg.serialize_for_storage()
            else:
                serialized_functions[key] = str(fcfg)

        def _ser_struct_def(def_obj):
            return {
                "struct_name": def_obj.struct_name,
                "members": [
                    {
                        "member_name": m["member_name"],
                        "member_type": getattr(m["member_type"], "elementaryTypeName", None)
                                       or getattr(m["member_type"], "typeCategory", None)
                                       or str(m["member_type"])
                    }
                    for m in def_obj.members
                ]
            }

        def _ser_enum_def(def_obj):
            return {
                "enum_name": def_obj.enum_name,
                "members": list(def_obj.members)
            }

        return {
            'cfg_type': self.cfg_type,
            'library_name': self.library_name,
            'functions': serialized_functions,
            'structDefs': {k: _ser_struct_def(v) for k, v in self.structDefs.items()},
            'enumDefs': {k: _ser_enum_def(v) for k, v in self.enumDefs.items()},
            'graph_structure': self.serialize_graph_structure()
        }