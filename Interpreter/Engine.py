# engine.py (SolDebug 통합 버전)

from __future__ import annotations
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from Analyzer.ContractAnalyzer import ContractAnalyzer

from Domain.Variable import Variables, MappingVariable, ArrayVariable, StructVariable, EnumVariable
from Domain.IR import Expression
from Domain.Interval import UnsignedIntegerInterval, IntegerInterval, BoolInterval
from Domain.AddressSet import AddressSet
from Domain.BytesSet import BytesSet
from Domain.Annotation import CompoundDuringAnnotation, CompoundPostAnnotation
from Utils.CFG import CFGNode, FunctionCFG
from Utils.Helper import VariableEnv
from collections import deque
from typing import cast

class Engine:
    def __init__(self, an: "ContractAnalyzer"):
        self.an = an
        # ── 기록 제어 플래그(기존 Runtime 것이 여기로 이동) ───────────────
        self._record_enabled: bool = True
        self._suppress_stmt_records: bool = False  # 고정점 중 문장 기록 억제
        self._in_widening_mode: bool = False  # widening 중에는 side-effect 억제

    # ── lazy properties (그대로 유지) ──────────────────────────────────
    @property
    def ref(self):
        return self.an.refiner
    @property
    def rec(self):
        return self.an.recorder
    @property
    def eval(self):
        return self.an.evaluator
    @property
    def up(self):
        return self.an.updater


    # =================================================================
    #  (통합) 문장 해석기 – 기존 Runtime.* 가 여기로 이동
    # =================================================================
    def update_statement_with_variables(self, stmt, current_variables, ret_acc=None, node=None):
        typ = stmt.statement_type
        if   typ == 'variableDeclaration':
            return self._interpret_var_decl(stmt, current_variables)
        elif typ == 'assignment':
            return self._interpret_assignment(stmt, current_variables, node=node)
        elif typ == 'unary':
            return self._interpret_unary(stmt, current_variables)
        elif typ == 'functionCall':
            return self._interpret_func_call(stmt, current_variables)
        elif typ == 'return':
            return self._interpret_return(stmt, current_variables, ret_acc)
        elif typ == 'revert':
            return self._interpret_revert(stmt, current_variables)
        elif typ == 'break':
            return self._interpret_break(stmt, current_variables)
        elif typ == 'continue':
            return self._interpret_continue(stmt, current_variables)
        elif typ == 'assembly':
            return self._interpret_assembly(stmt, current_variables)
        else:
            raise ValueError(f"Statement '{typ}' is not implemented.")

    def _interpret_var_decl(self, stmt, variables):
        var_type = stmt.type_obj
        var_name = stmt.var_name
        init_expr = stmt.init_expr

        # ──────────────────────────────────────────────────────────────
        # 1. 변수가 없으면 새로 생성
        # ──────────────────────────────────────────────────────────────
        if var_name not in variables:
            if var_type.typeCategory in ("struct", "array", "mapping"):
                # 초기화식 없으면 타입에 맞는 빈 객체 생성
                if var_type.typeCategory == "array":
                    vobj = ArrayVariable(
                        identifier=var_name,
                        base_type=var_type.arrayBaseType,
                        array_length=var_type.arrayLength,
                        is_dynamic=var_type.isDynamicArray,
                        scope="local"
                    )
                elif var_type.typeCategory == "struct":
                    vobj = StructVariable(
                        identifier=var_name,
                        struct_type=var_type.structTypeName,
                        scope="local"
                    )
                elif var_type.typeCategory == "mapping":
                    vobj = MappingVariable(
                        identifier=var_name,
                        key_type=var_type.mappingKeyType,
                        value_type=var_type.mappingValueType,
                        scope="local"
                    )
                variables[var_name] = vobj
            else:
                # Elementary / interface 타입 처리
                vobj = Variables(identifier=var_name, scope="local")
                vobj.typeInfo = var_type
                if var_type.typeCategory == "interface":
                    ifc_name = getattr(var_type, 'interfaceName', None)
                    vobj.value = AddressSet.top()
                    if ifc_name:
                        vobj.value._cast_interface = ifc_name
                else:
                    et = var_type.elementaryTypeName
                    if et and et.startswith("uint"):
                        bits = var_type.intTypeLength or 256
                        vobj.value = UnsignedIntegerInterval.top(bits)
                    elif et and et.startswith("int"):
                        bits = var_type.intTypeLength or 256
                        vobj.value = IntegerInterval.top(bits)
                    elif et == "bool":
                        vobj.value = BoolInterval.top()
                    elif et == "address":
                        vobj.value = AddressSet.top()
                    else:
                        vobj.value = f"symbol_{var_name}"
                variables[var_name] = vobj

        # ──────────────────────────────────────────────────────────────
        # 2. 초기화식이 있으면 항상 평가 (변수가 이미 있어도)
        # ──────────────────────────────────────────────────────────────
        if init_expr is not None:
            if var_type.typeCategory in ("struct", "array", "mapping"):
                # 구조체/배열/매핑: 초기화식 평가 결과로 변수 대체
                eval_result = self.eval.evaluate_expression(init_expr, variables, None, None)
                if isinstance(eval_result, (StructVariable, ArrayVariable, MappingVariable)):
                    eval_result.identifier = var_name
                    variables[var_name] = eval_result
                    vobj = eval_result
                else:
                    vobj = variables[var_name]
            else:
                # Elementary 타입: 값 평가 후 업데이트
                vobj = variables[var_name]
                eval_result = self.eval.evaluate_expression(init_expr, variables, None, None)

                # 평가 결과가 Variables 객체면 그 value를 추출
                if isinstance(eval_result, Variables) and not isinstance(eval_result, (ArrayVariable, StructVariable, MappingVariable)):
                    vobj.value = getattr(eval_result, 'value', eval_result)
                else:
                    vobj.value = eval_result

                if self._record_enabled and not self._suppress_stmt_records:
                    self.rec.record_variable_declaration(
                        line_no=stmt.src_line,
                        var_name=var_name,
                        var_obj=vobj
                    )
                    # ★ assign_env에 선언 시점 값 기록 (During assignCurrent용)
                    fcfg = self.an.current_target_function_cfg
                    if fcfg is not None:
                        fcfg.assign_env[var_name] = VariableEnv.copy_single_variable(vobj)

        return variables

    def _interpret_assignment(self, stmt, variables, node=None):
        lexp, rexpr, op = stmt.left, stmt.right, stmt.operator
        r_val = (self.eval.evaluate_expression(rexpr, variables, None, None)
                 if isinstance(rexpr, Expression) else rexpr)

        should_record = self._record_enabled and not self._suppress_stmt_records
        line_num = getattr(stmt, 'src_line', None)

        # ★ before_envs: 대입 직전 스냅샷 (동적 재해석 시 During beforeAfter용)
        if should_record and line_num is not None and node is not None:
            node.before_envs[line_num] = VariableEnv.copy_variables(variables)

        # stmt.src_line을 line_no로 전달
        self.up.update_left_var(lexp, r_val, op, variables, None, None, should_record, line_num)
        return variables

    def _interpret_unary(self, stmt, variables):
        op = stmt.operator
        operand = stmt.operand

        if op == '++' or op == 'unary_suffix' or op == 'unary_prefix':
            self.up.update_left_var(operand, 1, '+=', variables, None, None, False)
            return variables
        if op == '--':
            self.up.update_left_var(operand, 1, '-=', variables, None, None, False)
            return variables
        if op == 'delete':
            self.up.update_left_var(operand, 0, '=', variables, None, None,
                                    (self._record_enabled and not self._suppress_stmt_records))
            return variables
        return variables

    def _interpret_func_call(self, stmt, variables):
        # ★ infeasible branch(BOTTOM env)에서는 함수 호출 스킵
        #   → caller_env 반영이 BOTTOM 값을 TOP으로 오염시키는 것을 방지
        if self._is_bottom_env(variables):
            return variables
        self.eval.evaluate_function_call_context(stmt.function_expr, variables, None, None)
        return variables

    def _interpret_return(self, stmt, variables, ret_acc=None):
        rexpr = stmt.return_expr
        if rexpr is None:
            # bare return; (값 없는 리턴)
            r_val = None
        else:
            r_val = self.eval.evaluate_expression(rexpr, variables, None, None)
        if self._record_enabled and not self._suppress_stmt_records:
            self.rec.record_return(
                line_no=stmt.src_line,
                return_expr=rexpr,
                return_val=r_val,
                fn_cfg=self.an.current_target_function_cfg
            )
        exit_node = self.an.current_target_function_cfg.get_exit_node()
        exit_node.return_vals[stmt.src_line] = r_val
        if ret_acc is not None:
            ret_acc.append(r_val); ret_acc.append("__STOP__")
        return variables

    def _interpret_revert(self, stmt, variables):
        return variables
    def _interpret_break(self, stmt, variables):
        return variables
    def _interpret_continue(self, stmt, variables):
        return variables

    def _interpret_assembly(self, stmt, variables):
        """
        Assembly 블록 내 변수 할당 처리:
        - 해당 변수를 Top으로 설정 (assembly에서 정확한 값 추적 불가)
        """
        var_name = getattr(stmt, 'variable_name', None)
        if var_name and var_name in variables:
            var_obj = variables[var_name]
            # 변수 타입에 따라 적절한 Top 값 설정
            if hasattr(var_obj, 'typeInfo') and var_obj.typeInfo:
                et = getattr(var_obj.typeInfo, 'elementaryTypeName', None)
                if et:
                    if et.startswith("uint"):
                        bits = var_obj.typeInfo.intTypeLength or 256
                        var_obj.value = UnsignedIntegerInterval.top(bits)
                    elif et.startswith("int"):
                        bits = var_obj.typeInfo.intTypeLength or 256
                        var_obj.value = IntegerInterval.top(bits)
                    elif et == "bool":
                        var_obj.value = BoolInterval.top()
                    elif et == "address":
                        var_obj.value = AddressSet.top()
                    elif et.startswith("bytes") and len(et) > 5:
                        byte_size = int(et[5:])
                        var_obj.value = BytesSet.top(byte_size)
                    else:
                        var_obj.value = f"assembly_top_{var_name}"
                else:
                    var_obj.value = f"assembly_top_{var_name}"
            else:
                # 타입 정보 없으면 기본적으로 uint256 Top
                var_obj.value = UnsignedIntegerInterval.top()
        return variables

    # =================================================================
    #  Transfer (엔진 내부에서 바로 호출하도록 수정)
    # =================================================================
    def transfer_function(self, node: CFGNode, in_vars: Optional[dict[str, Variables]]) -> dict[str, Variables]:
        env_in = in_vars or {}
        if getattr(node, "fixpoint_evaluation_node", False):
            node.variables = VariableEnv.copy_variables(env_in)
            return env_in
        env_out = VariableEnv.copy_variables(env_in)
        if getattr(node, "statements", None):
            for st in node.statements:
                env_out = self.update_statement_with_variables(st, env_out, node=node)
        node.variables = VariableEnv.copy_variables(env_out)
        return env_out

    # =================================================================
    #  Loop Condition Convergence Check & Iteration Estimation
    # =================================================================
    def _check_loop_condition_converged(self, cond_expr: Expression,
                                       prev_env: dict[str, Variables],
                                       curr_env: dict[str, Variables]) -> bool:
        """
        루프 조건식을 평가하여 조건이 수렴했는지 체크

        조건식의 좌변과 우변을 각각 평가하여 둘 다 singleton으로 수렴했는지 확인

        Args:
            cond_expr: 루프 조건식
            prev_env: 이전 iteration의 변수 환경
            curr_env: 현재 iteration의 변수 환경

        Returns:
            True if 조건식의 좌변/우변이 모두 singleton으로 수렴
        """
        if cond_expr is None or not prev_env or not curr_env:
            return False

        # Binary expression이 아니면 판단 불가
        if not (hasattr(cond_expr, 'left') and hasattr(cond_expr, 'right')):
            return False

        try:
            # 좌변 평가
            prev_left = self.eval.evaluate_expression(cond_expr.left, prev_env, None, None)
            curr_left = self.eval.evaluate_expression(cond_expr.left, curr_env, None, None)

            # 우변 평가
            prev_right = self.eval.evaluate_expression(cond_expr.right, prev_env, None, None)
            curr_right = self.eval.evaluate_expression(cond_expr.right, curr_env, None, None)

            # 좌변 수렴 체크
            left_converged = False
            if VariableEnv.is_interval(prev_left) and VariableEnv.is_interval(curr_left):
                prev_left_singleton = (not prev_left.is_bottom() and
                                      prev_left.min_value == prev_left.max_value)
                curr_left_singleton = (not curr_left.is_bottom() and
                                      curr_left.min_value == curr_left.max_value)
                if prev_left_singleton and curr_left_singleton:
                    left_converged = (prev_left.min_value == curr_left.min_value)

            # 우변 수렴 체크
            right_converged = False
            if VariableEnv.is_interval(prev_right) and VariableEnv.is_interval(curr_right):
                prev_right_singleton = (not prev_right.is_bottom() and
                                       prev_right.min_value == prev_right.max_value)
                curr_right_singleton = (not curr_right.is_bottom() and
                                       curr_right.min_value == curr_right.max_value)
                if prev_right_singleton and curr_right_singleton:
                    right_converged = (prev_right.min_value == curr_right.min_value)

            # 좌변과 우변이 모두 수렴하면 true
            return left_converged and right_converged

        except Exception:
            return False

    def _estimate_loop_iterations(self, head: CFGNode, start_env: dict) -> int:
        """
        Loop 조건식을 평가해서 예상 반복 횟수 추정

        Args:
            head: Loop head node
            start_env: Loop 진입 시점의 변수 환경

        Returns:
            추정 반복 횟수 (기본값: 1, 최대값: 20)
        """
        # Loop head가 condition node가 아니면 기본값
        if not getattr(head, 'condition_node', False):
            return 1

        cond_expr = getattr(head, 'condition_expr', None)
        if cond_expr is None:
            return 1

        # 조건식 평가
        try:
            # Binary expression인지 확인
            if not hasattr(cond_expr, 'operator') or cond_expr.operator not in ['<', '<=', '>', '>=', '!=']:
                return 1

            # 좌변/우변 평가 (Evaluation.py 활용)
            left_val = self.eval.evaluate_expression(cond_expr.left, start_env, None, None)
            right_val = self.eval.evaluate_expression(cond_expr.right, start_env, None, None)

            # Interval인지 확인
            if not (VariableEnv.is_interval(left_val) and VariableEnv.is_interval(right_val)):
                return 1

            # bottom 체크
            if left_val.is_bottom() or right_val.is_bottom():
                return 1

            # 반복 횟수 계산
            if cond_expr.operator in ['<', '<=']:
                # left < right: right의 상한 - left의 하한
                iterations = right_val.max_value - left_val.min_value
                if cond_expr.operator == '<=':
                    iterations += 1
            elif cond_expr.operator in ['>', '>=']:
                # left > right: left의 상한 - right의 하한
                iterations = left_val.max_value - right_val.min_value
                if cond_expr.operator == '>=':
                    iterations += 1
            elif cond_expr.operator == '!=':
                # != 조건은 예측 어려움, 보수적으로 처리
                return 10
            else:
                return 1

            # 합리적인 범위로 제한: [1, 20]
            if iterations <= 0:
                return 1
            elif iterations > 20:
                return 20
            else:
                return int(iterations)

        except Exception as e:
            # 평가 실패 시 기본값
            return 1

    # =================================================================
    #  Fixpoint (루프 중 문장기록 억제)
    # =================================================================
    def fixpoint(self, head: CFGNode) -> CFGNode:
        G = self.an.current_target_function_cfg.graph
        ref = self.ref; rec = self.rec

        def _edge_flow_from_node_out(node, succ, node_out_env):
            base = VariableEnv.copy_variables(node_out_env or {})
            if getattr(node, "condition_node", False):
                ed = G.get_edge_data(node, succ, default=None)
                cond_expr = getattr(node, "condition_expr", None)
                if ed and "condition" in ed and cond_expr is not None:
                    want_true = bool(ed["condition"])
                    ref.update_variables_with_condition(base, cond_expr, want_true)
                    if not self._branch_feasible(base, cond_expr, want_true):
                        return None
            return base

        loop_nodes: set[CFGNode] = self.traverse_loop_nodes(head)
        from collections import defaultdict
        visit_cnt: defaultdict[CFGNode, int] = defaultdict(int)
        in_vars: dict[CFGNode, dict[str, Variables] | None] = {n: None for n in loop_nodes}
        out_vars: dict[CFGNode, dict[str, Variables] | None] = {n: None for n in loop_nodes}

        # ★ fixpoint 시작 전에 join 노드의 cached fixpoint vars 초기화
        for n in loop_nodes:
            if getattr(n, "fixpoint_evaluation_node", False):
                if hasattr(n, "fixpoint_evaluation_node_vars"):
                    delattr(n, "fixpoint_evaluation_node_vars")

        # ★ start_env 계산: join 노드의 경우 back edge를 제외하고 초기 진입 edge만 사용
        start_env = None
        join_node_ref = None
        for p in G.predecessors(head):
            # join 노드인 경우: 그 predecessor 중 loop 내부가 아닌 것만 사용
            if getattr(p, "fixpoint_evaluation_node", False):
                join_node_ref = p
                for pp in G.predecessors(p):
                    # back edge (증감식)는 제외: loop_nodes에 속하는 predecessor는 skip
                    if pp in loop_nodes:
                        continue
                    pp_vars = getattr(pp, "variables", {}) or {}
                    start_env = VariableEnv.join_variables_simple(start_env, pp_vars)
            else:
                # 일반 predecessor
                p_vars = getattr(p, "variables", {}) or {}
                start_env = VariableEnv.join_variables_simple(start_env, p_vars)
        in_vars[head] = start_env or {}

        # ★ join 노드를 loop_nodes에 추가하고 초기값 설정
        # 이렇게 하면 첫 iteration에서 i=1부터 시작됨
        if join_node_ref is not None:
            loop_nodes.add(join_node_ref)
            in_vars[join_node_ref] = VariableEnv.copy_variables(start_env or {})
            out_vars[join_node_ref] = None
            join_node_ref.join_baseline_env = VariableEnv.copy_variables(start_env or {})

        # ── 루프 내부 문장 기록 억제 on
        old_sup = self._suppress_stmt_records
        self._suppress_stmt_records = True

        # Loop 반복 횟수 추정 (조건식 기반)
        widening_threshold = (self._estimate_loop_iterations(head, in_vars[head]))

        # ★ widening - 초기 WL은 head만 (join 노드는 predecessor가 준비되면 자동으로 추가됨)
        W_MAX = 300
        WL = deque([head])
        iteration = 0

        while WL and max(visit_cnt.values(), default=0) < W_MAX:
            node = WL.popleft()
            visit_cnt[node] += 1
            iteration += 1

            # ★ in_vars[node]가 None인 경우 처리
            if in_vars[node] is None:
                # None이면 predecessor들의 out을 join해서 계산
                in_new = None
                for p in G.predecessors(node):
                    if p in loop_nodes and out_vars[p] is not None:
                        flow = _edge_flow_from_node_out(p, node, out_vars[p])
                        if flow is not None:
                            in_new = VariableEnv.join_variables_simple(in_new, flow)
                if in_new is not None:
                    in_vars[node] = in_new

            out_old = out_vars[node]

            # ★ widening 모드 설정 (후속 노드들도 widening threshold 넘으면 추상화)
            old_widening = self._in_widening_mode
            if visit_cnt[node] > widening_threshold:
                self._in_widening_mode = True

            out_raw = self.transfer_function(node, in_vars[node])

            # ★ widening 모드 복원
            self._in_widening_mode = old_widening

            # ★ out_vars에서는 widening 적용하지 않음
            #    표준 abstract interpretation에서 widening은 loop header의 in_vars에서만 적용
            #    out_vars에서 widening하면 loop body로 전파되어 불필요한 over-approximation 발생
            out_joined = VariableEnv.join_variables_simple(out_old, out_raw)

            if getattr(node, "fixpoint_evaluation_node", False):
                node.fixpoint_evaluation_node_vars = VariableEnv.copy_variables(out_joined)

            equal = VariableEnv.variables_equal(out_old, out_joined)

            if equal:
                out_vars[node] = out_joined; continue
            out_vars[node] = out_joined

            for succ in G.successors(node):
                if succ not in loop_nodes:  # 루프 밖은 고정점 후 reinterpret에서 처리
                    continue
                flow = _edge_flow_from_node_out(node, succ, out_joined)
                if flow is None:
                    continue
                if getattr(succ, "fixpoint_evaluation_node", False):
                    succ_widen = (visit_cnt[succ] > widening_threshold)
                else:
                    succ_widen = False

                # ★ fixpoint_evaluation_node (join 노드)의 경우:
                #    모든 predecessor의 최신 flow를 먼저 join한 후 widening 적용
                if getattr(succ, "fixpoint_evaluation_node", False):
                    # 모든 predecessor의 flow를 join
                    all_pred_flows = None
                    for pred in G.predecessors(succ):
                        if pred in loop_nodes:
                            pred_out = out_vars.get(pred) or getattr(pred, "variables", {}) or {}
                        else:
                            # 루프 밖 predecessor (initial entry) - 현재 variables 사용
                            pred_out = getattr(pred, "variables", {}) or {}
                        pred_flow = _edge_flow_from_node_out(pred, succ, pred_out)
                        if pred_flow is not None:
                            all_pred_flows = VariableEnv.join_variables_simple(all_pred_flows, pred_flow)

                    # 이제 old in_vars와 새로 join된 값을 비교하여 widening
                    if all_pred_flows is not None:
                        in_new = (VariableEnv.join_variables_with_widening(in_vars[succ], all_pred_flows)
                                  if succ_widen
                                  else VariableEnv.join_variables_simple(in_vars[succ], all_pred_flows))
                    else:
                        in_new = in_vars[succ]
                else:
                    in_new = (VariableEnv.join_variables_with_widening(in_vars[succ], flow)
                              if succ_widen
                              else VariableEnv.join_variables_simple(in_vars[succ], flow))

                changed_succ = not VariableEnv.variables_equal(in_vars[succ], in_new)

                if changed_succ:
                    in_vars[succ] = VariableEnv.copy_variables(in_new)
                    WL.append(succ)

        # narrowing — widening에서 도달한(reachable) node만 대상
        reachable = [n for n in loop_nodes if out_vars.get(n) is not None]
        WL = deque(reachable); N_MAX = 30
        while WL and N_MAX:
            N_MAX -= 1
            node = WL.popleft()

            new_in = None
            for p in G.predecessors(node):
                src = out_vars.get(p) or getattr(p, "variables", {}) or {}
                flow = _edge_flow_from_node_out(p, node, src)
                if flow is None:
                    continue
                new_in = VariableEnv.join_variables_simple(new_in, flow)

            if not VariableEnv.variables_equal(in_vars[node], new_in):
                in_vars[node] = VariableEnv.copy_variables(new_in or {})

            # ★ unreachable 노드 처리: in_vars가 빈 딕셔너리면 skip
            if not in_vars[node]:
                # 이 노드는 unreachable (모든 predecessor의 flow가 None)
                continue

            tmp_out = self.transfer_function(node, in_vars[node])
            narrowed = (VariableEnv.narrow_variables(out_vars[node], tmp_out)
                        if getattr(node, "fixpoint_evaluation_node", False)
                        else tmp_out)

            if VariableEnv.variables_equal(out_vars[node], narrowed):
                continue
            out_vars[node] = narrowed

            for succ in G.successors(node):
                if succ in loop_nodes:
                    WL.append(succ)


        # 루프 내부 문장 기록 억제 off
        self._suppress_stmt_records = old_sup

        # exit env
        exit_node = self.find_loop_exit_node(head)
        if not exit_node:
            raise ValueError("loop without exit-node")

        exit_env = None
        for p in G.predecessors(exit_node):
            src = out_vars.get(p) or getattr(p, "variables", {}) or {}
            flow = _edge_flow_from_node_out(p, exit_node, src)
            if flow is None:
                continue
            exit_env = VariableEnv.join_variables_simple(exit_env, flow)
        exit_node.variables = VariableEnv.copy_variables(exit_env or {})

        # loopDelta: 헤더(조건) 라인에 기록
        # ★ fixpoint evaluation node(join)의 고정점 상태를 사용 (false edge 정제 전)
        join_node = None
        for p in G.predecessors(head):
            if getattr(p, "fixpoint_evaluation_node", False):
                join_node = p
                break

        if join_node is not None:
            base_env = getattr(join_node, "join_baseline_env", None)
            # ★ fixpoint_evaluation_node_vars: 고정점 도달 후 join 노드의 최종 상태
            fixpoint_env = getattr(join_node, "fixpoint_evaluation_node_vars", None)

            if base_env is not None and fixpoint_env is not None:
                changed_flat = VariableEnv.diff_changed(base_env, fixpoint_env)

                if changed_flat:
                    ln_head = getattr(head, "src_line", None)
                    if ln_head is not None:
                        # loopDelta 기록: diff_changed는 이미 직렬화된 딕셔너리를 반환하므로
                        # _append_or_replace를 직접 호출
                        rec._append_or_replace(
                            ln_head,
                            {"kind": "loopDelta", "vars": changed_flat},
                            replace_rule=lambda old, new: old.get("kind") == new["kind"],
                        )

        return exit_node

    # =================================================================
    #  interpret_function_cfg (Case B: 내부 함수 호출용)
    #  - evaluate_function_call_context 등에서 호출
    #  - 기록 비활성화, caller env의 state/global을 callee에 공유
    # =================================================================
    def interpret_function_cfg(self, fcfg: FunctionCFG, caller_env: dict[str, Variables] | None = None):
        an = self.an
        _old_func = an.current_target_function
        _old_fcfg = an.current_target_function_cfg
        _old_record_enabled = self._record_enabled

        an.current_target_function = fcfg.function_name
        an.current_target_function_cfg = fcfg
        self._record_enabled = False
        an._seen_stmt_ids.clear()

        # caller의 ireturn_registry를 callee에 전파 (sub-function에서도 IReturn 적용)
        _saved_ireturn = dict(fcfg.ireturn_registry)
        if _old_fcfg and _old_fcfg.ireturn_registry:
            for key, val in _old_fcfg.ireturn_registry.items():
                fcfg.ireturn_registry.setdefault(key, val)

        _saved_node_vars = self._reset_node_vars(fcfg)

        entry = fcfg.get_entry_node()
        (start_block,) = fcfg.graph.successors(entry)

        # callee env 초기화: callee 자체 정의(파라미터, 로컬) 기반
        start_block.variables = VariableEnv.copy_variables(fcfg.related_variables)

        # caller env의 state variable / global을 callee에 공유 (같은 storage)
        # - callee에 이미 있는 key도 caller 값으로 덮어씀 (단, 파라미터는 제외)
        if caller_env is not None:
            param_names = set(getattr(fcfg, 'parameters', []))
            for k, v in caller_env.items():
                if k in param_names:
                    continue
                start_block.variables[k] = VariableEnv.copy_single_variable(v)

        return_values = self._run_worklist(fcfg, start_block)

        self._force_join_before_exit(fcfg)
        self._sync_named_return_vars(fcfg)

        # exit env를 node 복원 전에 캡처
        _exit_env = VariableEnv.copy_variables(fcfg.get_exit_node().variables) if caller_env is not None else None

        for blk, saved_vars in _saved_node_vars.items():
            blk.variables = saved_vars

        an.current_target_function = _old_func
        an.current_target_function_cfg = _old_fcfg
        fcfg.ireturn_registry = _saved_ireturn

        # callee의 exit env를 caller에 반영 (state variable 변경 전파)
        # callee 파라미터가 caller의 동명 변수를 오염시키지 않도록 제외
        if caller_env is not None and _exit_env is not None:
            _callee_params = set(getattr(fcfg, 'parameters', []))
            for k, v in _exit_env.items():
                if k in _callee_params:
                    continue
                if k in caller_env:
                    cv = caller_env[k]
                    if isinstance(v, MappingVariable) and isinstance(cv, MappingVariable):
                        cv.mapping = v.mapping
                    elif isinstance(v, ArrayVariable) and isinstance(cv, ArrayVariable):
                        cv.elements = v.elements
                    elif isinstance(v, StructVariable) and isinstance(cv, StructVariable):
                        cv.members = v.members
                    elif isinstance(v, EnumVariable) and isinstance(cv, EnumVariable):
                        cv.value = v.value
                        cv.valueIndex = v.valueIndex
                    elif hasattr(cv, "value"):
                        cv.value = v.value
                    else:
                        caller_env[k] = v
                elif isinstance(v, (MappingVariable, ArrayVariable)):
                    caller_env[k] = v

        self._record_enabled = _old_record_enabled
        return self._extract_return_value(fcfg, return_values)

    # =================================================================
    #  interpret_function_cfg_for_debug (Case A: debug batch flush용)
    #  - ContractAnalyzer.flush에서 호출
    #  - 기록 활성화, assign_env/entry_env 갱신, annotation 처리
    # =================================================================
    def interpret_function_cfg_for_debug(self, fcfg: FunctionCFG, caller_env: dict[str, Variables] | None = None):
        an = self.an; rec = self.rec
        _old_func = an.current_target_function
        _old_fcfg = an.current_target_function_cfg
        _old_record_enabled = self._record_enabled

        an.current_target_function = fcfg.function_name
        an.current_target_function_cfg = fcfg
        self._record_enabled = True
        an._seen_stmt_ids.clear()


        _saved_node_vars = self._reset_node_vars(fcfg)

        # debug-patched related_variables로 assign_env / entry_env 갱신
        fcfg.assign_env = VariableEnv.copy_variables(fcfg.related_variables)
        fcfg.entry_env = VariableEnv.copy_variables(fcfg.related_variables)

        entry = fcfg.get_entry_node()
        (start_block,) = fcfg.graph.successors(entry)

        start_block.variables = VariableEnv.copy_variables(fcfg.related_variables)

        if caller_env is not None:
            for k, v in caller_env.items():
                if k not in start_block.variables:
                    start_block.variables[k] = VariableEnv.copy_single_variable(v)

        return_values = self._run_worklist(fcfg, start_block)

        self._force_join_before_exit(fcfg)
        self._sync_named_return_vars(fcfg)

        # ═══ Post Annotation 처리 ═══
        self._process_post_annotations(fcfg)

        for blk, saved_vars in _saved_node_vars.items():
            blk.variables = saved_vars

        an.current_target_function = _old_func
        an.current_target_function_cfg = _old_fcfg

        # 반환값 (기록 포함)
        result = self._extract_return_value(fcfg, return_values, log_implicit=True)
        self._record_enabled = _old_record_enabled
        return result

    # =================================================================
    #  공통 헬퍼
    # =================================================================
    def _reset_node_vars(self, fcfg: FunctionCFG) -> dict:
        """node variables 백업 및 초기화. 백업 dict 반환."""
        an = self.an
        saved = {blk: dict(blk.variables) for blk in fcfg.graph.nodes}
        for blk in fcfg.graph.nodes:
            blk.variables = {}
            for st in blk.statements:
                ln = getattr(st, "src_line", None)
                if ln is not None and ln in an.analysis_per_line:
                    an.analysis_per_line[ln].clear()
        return saved

    def _run_worklist(self, fcfg: FunctionCFG, start_block) -> list:
        """CFG worklist 순회. return_values 리스트 반환."""
        G = fcfg.graph

        def _is_sink(n: CFGNode) -> bool:
            if getattr(n, "function_exit_node", False): return True
            if getattr(n, "error_exit_node", False):    return True
            if getattr(n, "return_exit_node", False):   return True
            nm = getattr(n, "name", "")
            return nm in {"EXIT", "ERROR", "RETURN"}

        def _edge_env_from_pred(pred: CFGNode, succ: CFGNode):
            base = VariableEnv.copy_variables(getattr(pred, "variables", {}) or {})
            # BOTTOM env는 refine 불필요 (BOTTOM ⊓ cond = BOTTOM)
            if self._is_bottom_env(base):
                return base
            if getattr(pred, "condition_node", False):
                cond_expr = getattr(pred, "condition_expr", None)
                ed = G.get_edge_data(pred, succ, default=None)
                if cond_expr is not None and ed and "condition" in ed:
                    want_true = bool(ed["condition"])
                    self.ref.update_variables_with_condition(base, cond_expr, want_true)
                    if not self._branch_feasible(base, cond_expr, want_true):
                        return None
            return base

        work = deque([start_block])
        visited: set[CFGNode] = set()
        return_values = []

        while work:
            node = work.popleft()
            if node in visited: continue

            preds = list(G.predecessors(node))
            if getattr(node, 'join_point_node', False) and preds:
                unvisited_preds = [p for p in preds if p not in visited]
                if unvisited_preds and len(work) > 0:
                    work.append(node)
                    continue

            visited.add(node)

            if preds:
                joined = None
                for p in preds:
                    if p not in visited:
                        continue
                    flow = _edge_env_from_pred(p, node)
                    if flow is None: continue
                    joined = (VariableEnv.copy_variables(flow) if joined is None
                              else VariableEnv.join_variables_simple(joined, flow))
                if joined is not None:
                    node.variables = joined

            cur_vars = node.variables
            node.evaluated = True

            if self._is_bottom_env(cur_vars):
                for nxt in list(G.successors(node)):
                    if _is_sink(nxt): continue
                    nxt.variables = VariableEnv.copy_variables(cur_vars)
                    work.append(nxt)
                continue

            if node.condition_node:
                condition_expr = node.condition_expr

                if node.condition_node_type in ["if", "else if"]:
                    true_succs  = [s for s in G.successors(node) if G.edges[node, s].get('condition') is True]
                    false_succs = [s for s in G.successors(node) if G.edges[node, s].get('condition') is False]
                    if len(true_succs) != 1 or len(false_succs) != 1:
                        raise ValueError("if/else-if node must have exactly one true and one false successor.")

                    true_variables  = VariableEnv.copy_variables(cur_vars)
                    false_variables = VariableEnv.copy_variables(cur_vars)
                    self.ref.update_variables_with_condition(true_variables,  condition_expr, True)
                    self.ref.update_variables_with_condition(false_variables, condition_expr, False)

                    can_true  = self._branch_feasible(true_variables,  condition_expr, True)
                    can_false = self._branch_feasible(false_variables, condition_expr, False)

                    if not can_true and not can_false:
                        continue

                    t = true_succs[0]; f = false_succs[0]
                    if can_true:
                        t.variables = true_variables;  work.append(t)
                    else:
                        t.variables = VariableEnv.copy_variables(cur_vars)
                        self._set_bottom_env(t.variables); work.append(t)
                    if can_false:
                        f.variables = false_variables; work.append(f)
                    else:
                        f.variables = VariableEnv.copy_variables(cur_vars)
                        self._set_bottom_env(f.variables); work.append(f)
                    continue

                elif node.condition_node_type in ["require", "assert"]:
                    (t,) = [s for s in G.successors(node) if G.edges[node, s].get('condition') is True]
                    true_variables = VariableEnv.copy_variables(cur_vars)
                    self.ref.update_variables_with_condition(true_variables, condition_expr, True)
                    can_true = self._branch_feasible(true_variables, condition_expr, True)

                    if can_true:
                        t.variables = true_variables; work.append(t)
                    else:
                        self._set_bottom_env(t.variables)

                    self._process_node_intents(node, cur_vars, getattr(node, 'src_line', None))
                    continue

                elif node.condition_node_type in ["while", "for", "do_while"]:
                    exit_node = self.fixpoint(node)
                    _succs = list(G.successors(exit_node))
                    for nxt in _succs:
                        if _is_sink(nxt): continue
                        nxt.variables = VariableEnv.copy_variables(exit_node.variables)
                        work.append(nxt)
                    continue

                elif node.condition_node_type == "try":
                    t_succs = [s for s in G.successors(node) if G.edges[node, s].get('condition') is True]
                    f_succs = [s for s in G.successors(node) if G.edges[node, s].get('condition') is False]
                    for s in (t_succs + f_succs):
                        if _is_sink(s): continue
                        s.variables = VariableEnv.copy_variables(cur_vars)
                        work.append(s)
                    continue

                else:
                    raise ValueError(f"Unknown condition node type: {node.condition_node_type}")

            elif getattr(node, "is_for_increment", False):
                for stmt in node.statements:
                    cur_vars = self.update_statement_with_variables(stmt, cur_vars, return_values, node=node)
                for succ in G.successors(node):
                    if _is_sink(succ): continue
                    succ.variables = VariableEnv.copy_variables(node.variables)
                    work.append(succ)
                continue

            else:
                if "__STOP__" in return_values:
                    return_values.remove("__STOP__")

                for stmt in node.statements:
                    cur_vars = self.update_statement_with_variables(stmt, cur_vars, return_values, node=node)

                    # ═══ During Annotation 처리 ═══
                    self._process_during_annotations(stmt, node, cur_vars)

                    if "__STOP__" in return_values:
                        break

                for nxt in list(G.successors(node)):
                    if _is_sink(nxt): continue
                    nxt.variables = VariableEnv.copy_variables(cur_vars)
                    work.append(nxt)

        return return_values

    def _extract_return_value(self, fcfg: FunctionCFG, return_values: list, log_implicit: bool = False):
        """return_values 리스트에서 최종 반환값을 추출."""
        rec = self.rec

        def _log_implicit_return(var_objs: list[Variables]):
            if not log_implicit or not self._record_enabled:
                return
            ln = self._last_executable_line(fcfg)
            if ln is None: return
            if len(var_objs) == 1:
                rec.record_return(line_no=ln, return_expr=None, return_val=var_objs[0].value, fn_cfg=fcfg)
            else:
                env_dict = {v.identifier: v for v in var_objs}
                self.rec.add_env_record(ln, "implicitReturn", env_dict)

        if len(return_values) == 0:
            if fcfg.return_vars:
                _log_implicit_return(fcfg.return_vars)
                if len(fcfg.return_vars) == 1:
                    return fcfg.return_vars[0].value
                return [rv.value for rv in fcfg.return_vars]
            else:
                exit_retvals = list(fcfg.get_return_exit_node().return_vals.values())
                if exit_retvals:
                    joined = exit_retvals[0]
                    for v in exit_retvals[1:]:
                        if hasattr(joined, 'join') and hasattr(v, 'join'):
                            joined = joined.join(v)
                        else:
                            return joined
                    return joined
                return None
        elif len(return_values) == 1:
            return return_values[0]
        else:
            filtered_values = [rv for rv in return_values if rv != "__STOP__"]
            if not filtered_values:
                return None
            joined_ret = filtered_values[0]
            for rv in filtered_values[1:]:
                if hasattr(joined_ret, 'join') and hasattr(rv, 'join'):
                    joined_ret = joined_ret.join(rv)
                else:
                    return joined_ret
            return joined_ret

    # =================================================================
    #  reinterpret_from (변경 없음; self.* 호출로 정리)
    # =================================================================
    def reinterpret_from(self, fcfg: "FunctionCFG", seed_or_seeds) -> None:
        G = fcfg.graph; ref = self.ref
        rec = self.rec  # ★ Recorder
        # --- helpers 동일 (_is_loop_head / _false_succs / _is_sink / _edge_env_from_pred / _compute_in) ---

        # ★ 재해석 시 기록 활성화
        self._record_enabled = True
        self._suppress_stmt_records = False

        seeds = list(seed_or_seeds) if isinstance(seed_or_seeds, (list, tuple, set)) else [seed_or_seeds]
        WL, in_queue = deque(), set()
        out_snapshot: dict[CFGNode, dict[str, Variables] | None] = {}

        # ★ 이번 run에서 이미 비웠던 라인 집합
        cleared_lines: set[int] = set()
        # ★ 이번 run에서 "출력 대상으로 건드린 라인" 집합 (send_report에서 사용)
        touched_lines: set[int] = set()
        def _is_loop_head(n):
            return (getattr(n, "condition_node", False) and
                    getattr(n, "condition_node_type", None) in {"while", "for", "doWhile", "do_while"})
        def _false_succs(n):
            return [s for s in G.successors(n) if G[n][s].get("condition") is False]
        def _is_sink(n):
            if getattr(n, "function_exit_node", False): return True
            if getattr(n, "error_exit_node", False):    return True
            if getattr(n, "return_exit_node", False):   return True
            nm = getattr(n, "name", "")
            return nm in {"EXIT", "ERROR", "RETURN"}
        def _edge_env_from_pred(pred, succ):
            base = VariableEnv.copy_variables(getattr(pred, "variables", {}) or {})
            if getattr(pred, "condition_node", False):
                cond_expr = getattr(pred, "condition_expr", None)
                ed = G.get_edge_data(pred, succ, default=None)
                if cond_expr is not None and ed and "condition" in ed:
                    want_true = bool(ed["condition"])
                    ref.update_variables_with_condition(base, cond_expr, want_true)
                    if not self._branch_feasible(base, cond_expr, want_true):
                        return None
                return base
            return base
        def _compute_in(n):
            acc = None
            for p in G.predecessors(n):
                env_p = _edge_env_from_pred(p, n)
                if env_p is None: continue
                acc = VariableEnv.join_variables_simple(acc, env_p)
            return acc or {}

        def _clear_line_once(ln: int | None) -> None:
            if ln is None or ln in cleared_lines:
                return
            rec.clear_line(ln)
            cleared_lines.add(ln)


        for s in seeds:
            if not _is_sink(s) and s not in in_queue:
                WL.append(s); in_queue.add(s)

        while WL:
            n = WL.popleft(); in_queue.discard(n)

            in_env = _compute_in(n)

            # ── loop head는 fixpoint에서 loopDelta를 기록하므로 특별 처리
            if _is_loop_head(n):
                ln_head = getattr(n, "src_line", None)
                if ln_head is not None: touched_lines.add(ln_head)

                # ★ fixpoint 재실행 전에 join 노드의 스냅샷 초기화
                # 디버그 주석 적용 후 조건이 바뀌었을 수 있으므로 clean slate에서 시작
                for p in G.predecessors(n):
                    if getattr(p, "fixpoint_evaluation_node", False):
                        if hasattr(p, "fixpoint_evaluation_node_vars"):
                            delattr(p, "fixpoint_evaluation_node_vars")

                exit_node = self.fixpoint(n)
                for s in G.successors(exit_node):
                    if not _is_sink(s) and s not in in_queue:
                        WL.append(s); in_queue.add(s)

                continue

            # ── (A) 라인 초기화: 이 노드가 기록을 남길 수 있는 라인들을 선제적으로 clear
            #     - 조건 노드: 자신의 src_line (branchTrue/requireTrue 등)
            #     - 일반/베이식: 각 statement 의 src_line
            ln = getattr(n, "src_line", None)
            if getattr(n, "condition_node", False):
                _clear_line_once(ln)
                if ln is not None: touched_lines.add(ln)
            else:
                for st in getattr(n, "statements", []):
                    ln_st = getattr(st, "src_line", None)
                    _clear_line_once(ln_st)
                    if ln_st is not None: touched_lines.add(ln_st)

            new_out = self.transfer_function(n, in_env)
            n.variables = VariableEnv.copy_variables(new_out)

            # ═══ During Annotation 처리 (일반 노드에서만) ═══
            if not getattr(n, "condition_node", False):
                for st in getattr(n, "statements", []):
                    self._process_during_annotations(st, n, n.variables)

            changed = not VariableEnv.variables_equal(out_snapshot.get(n), new_out)
            out_snapshot[n] = VariableEnv.copy_variables(new_out)

            if changed:
                for s in G.successors(n):
                    if not _is_sink(s) and s not in in_queue:
                        WL.append(s); in_queue.add(s)

            # ★ 이번 reinterpret 에서 '어디를 보여줄지'를 ContractAnalyzer에 남김
            if touched_lines:
                self.an._last_touched_lines = set(touched_lines)

        # ═══ Post Annotation 처리 ═══
        # reinterpret_from은 seed부터 함수 끝(EXIT)까지 영향받는 모든 노드를 재해석하므로
        # 항상 post annotation 검증 수행
        self._process_post_annotations(fcfg)

    # =================================================================
    #  Helpers (branch feasible, bottom, EXIT sync, line utils)
    # =================================================================
    def _branch_feasible(self, env: dict, cond: Expression, assume_true: bool) -> bool:
        r = self.eval.evaluate_expression(cond, env, None, None)
        if isinstance(r, BoolInterval):
            result = (r.max_value == 1) if assume_true else (r.min_value == 0)
            return result
        if VariableEnv.is_interval(r):
            as_bool = VariableEnv.convert_int_to_bool_interval(r)
            result = (as_bool.max_value == 1) if assume_true else (as_bool.min_value == 0)
            return result
        return True

    def _is_bottom_env(self, env: dict) -> bool:
        """env가 infeasible branch를 나타내는지 검사 (하나라도 BOTTOM이면 infeasible)."""
        for v in env.values():
            if self._is_bottom_var(v):
                return True
        return False

    def _is_bottom_var(self, v) -> bool:
        """Variable 하나(또는 하위 원소)가 BOTTOM인지 재귀 검사."""
        if isinstance(v, ArrayVariable):
            return any(self._is_bottom_var(e) for e in v.elements)
        if isinstance(v, StructVariable):
            return any(self._is_bottom_var(m) for m in v.members.values())
        if isinstance(v, MappingVariable):
            return any(self._is_bottom_var(mv) for mv in v.mapping.values())
        val = getattr(v, "value", None)
        if val is not None and hasattr(val, "is_bottom"):
            return val.is_bottom()
        return False

    def _set_bottom_env(self, env: dict[str, Variables]) -> None:
        for v in env.values():
            self._make_bottom(v)

    def _make_bottom(self, v: Variables) -> None:
        if isinstance(v, ArrayVariable):
            for elem in v.elements:
                self._make_bottom(elem)
            return
        if isinstance(v, StructVariable):
            for m in v.members.values():
                self._make_bottom(m)
            return
        if isinstance(v, MappingVariable):
            for mv in v.mapping.values():
                self._make_bottom(mv)
            return
        val = getattr(v, "value", None)
        if isinstance(val, UnsignedIntegerInterval):
            v.value = UnsignedIntegerInterval.bottom(val.type_length); return
        if isinstance(val, IntegerInterval):
            v.value = IntegerInterval.bottom(val.type_length); return
        if isinstance(val, BoolInterval):
            v.value = BoolInterval.bottom(); return
        from Domain.AddressSet import AddressSet
        if isinstance(val, AddressSet):
            bot = AddressSet.bot()
            bot._cast_interface = getattr(val, '_cast_interface', None)
            v.value = bot; return
        v.value = None

    def _force_join_before_exit(self, fcfg: FunctionCFG) -> None:
        g = fcfg.graph; exit_node = fcfg.get_exit_node()
        joined_env: dict[str, Variables] = {}
        for p in list(g.predecessors(exit_node)):
            joined_env = VariableEnv.join_variables_simple(joined_env, getattr(p, "variables", {}) or {})
        exit_node.variables = joined_env

    def _sync_named_return_vars(self, fcfg: FunctionCFG) -> None:
        exit_env = fcfg.get_exit_node().variables
        for i, rv in enumerate(fcfg.return_vars or []):
            if rv.identifier in exit_env:
                src = exit_env[rv.identifier]
                if hasattr(rv, "value"): rv.value = getattr(src, "value", src)
                else: fcfg.return_vars[i] = src

    def _last_executable_line(self, fcfg: FunctionCFG) -> int | None:
        rng = self._function_body_range(fcfg)
        if rng is None: return None
        body_start, body_end = rng
        for ln in range(body_end, body_start - 1, -1):
            code = self.an.sa.full_code_lines.get(ln, "").strip()
            if not code or code == "}" or code.startswith("//"): continue
            return ln
        return None

    def _function_start_line(self, fcfg: FunctionCFG) -> int | None:
        entry = fcfg.get_entry_node()
        for ln, info in (self.an.sa.line_info or {}).items():
            nodes = []
            if isinstance(info.get("cfg_nodes"), list): nodes.extend(info["cfg_nodes"])
            if entry in nodes: return ln
        return None

    def _function_body_range(self, fcfg: FunctionCFG) -> tuple[int, int] | None:
        li = self.an.sa.line_info or {}
        fn_start_ln = self._function_start_line(fcfg)
        if fn_start_ln is None: return None
        def _oc(ln: int) -> tuple[int, int]:
            info = li.get(ln, {}); return int(info.get("open", 0)), int(info.get("close", 0))
        start_balance = 0
        for ln in range(1, fn_start_ln):
            o, c = _oc(ln); start_balance += (o - c)
        body_start = None; balance = start_balance
        max_ln = max(li.keys()) if li else fn_start_ln
        for ln in range(fn_start_ln, max_ln + 1):
            o, c = _oc(ln); balance += (o - c)
            if balance == start_balance + 1 and body_start is None:
                body_start = ln + 1
            if balance == start_balance and body_start is not None:
                return (body_start, ln - 1)
        return None

    # Engine 클래스 내부에 추가
    def traverse_loop_nodes(self, loop_head: CFGNode) -> set[CFGNode]:
        """
        loop_head(while/for/do-while 의 조건 노드)에서 시작해,
        loop-exit 노드(= False 분기에서 loop_exit_node=True)를 '절단점'으로 보고
        그 안쪽 노드들만 수집한다.
        """
        G = self.an.current_target_function_cfg.graph
        visited: set[CFGNode] = set()
        stack = [loop_head]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            for succ in G.successors(cur):
                # 루프 바깥으로 나가는 exit 노드는 확장하지 않음
                if getattr(succ, "loop_exit_node", False):
                    continue
                stack.append(cast(CFGNode, succ))
        return visited

    def is_node_in_loop(self, node: CFGNode, loop_head: CFGNode) -> bool:
        """
        node 가 loop_head 로 정의된 루프 본문에 속하는지 확인.
        loop_exit_node=True 는 바깥으로 간주.
        """
        if getattr(node, "loop_exit_node", False):
            return False
        return node in self.traverse_loop_nodes(loop_head)

    def find_loop_exit_node(self, loop_head: CFGNode) -> CFGNode:
        """
        (가능하면) 헤더의 False-edge 로 표시된 loop-exit 를 먼저 사용하고,
        없다면 traverse 기반으로 '루프 내부 노드들의 후속 중 루프 밖에 있는 유일한 노드'를 찾는다.
        여러 후보면 loop_exit_node=True 를 우선, 그래도 애매하면 오류.
        """
        G = self.an.current_target_function_cfg.graph

        # 1) 가장 신뢰도 높은 경로: 헤더의 False-edge + loop_exit_node=True
        for succ in G.successors(loop_head):
            if G[loop_head][succ].get("condition") is False and getattr(succ, "loop_exit_node", False):
                return cast(CFGNode, succ)

        # 2) traverse 로 루프 내부 집합을 만든 뒤 바깥으로 나가는 successor 를 후보로 수집
        loop_nodes = self.traverse_loop_nodes(loop_head)
        exit_candidates: set[CFGNode] = set()
        for n in loop_nodes:
            for succ in G.successors(n):
                succ = cast(CFGNode, succ)
                if succ not in loop_nodes:
                    exit_candidates.add(succ)

        if not exit_candidates:
            raise ValueError("loop exit node not found")

        # 3) loop_exit_node=True 가 달린 후보가 하나면 그걸 사용
        flagged = [c for c in exit_candidates if getattr(c, "loop_exit_node", False)]
        if len(flagged) == 1:
            return flagged[0]
        if len(flagged) > 1:
            # 헤더의 False-edge 쪽과 맞닿은 것을 우선적으로 선택 (있으면)
            for c in flagged:
                if loop_head in G.predecessors(c) and G[loop_head][c].get("condition") is False:
                    return c
            raise ValueError(f"ambiguous loop exits: {len(flagged)} candidates with loop_exit_node=True")

        # 4) 플래그가 하나도 없으면,
        #    (a) 헤더 False-edge에서 바로 이어지는 후보가 있으면 그걸 사용
        for c in exit_candidates:
            if loop_head in G.predecessors(c) and G[loop_head][c].get("condition") is False:
                return c
        #    (b) 바깥으로 나간 뒤 다시 루프 안으로 돌아오지 않는 후보를 선호
        for c in exit_candidates:
            if all(succ2 not in loop_nodes for succ2 in G.successors(c)):
                return c
        #    (c) 최후수단: 첫 후보 반환
        return next(iter(exit_candidates))

    # =================================================================
    #  During / Post Annotation 처리
    # =================================================================

    def _process_during_annotations(self, stmt, node, cur_vars):
        """
        Statement 실행 후 해당 라인의 During annotations 검증

        Args:
            stmt: 실행된 Statement 객체
            node: 현재 CFGNode
            cur_vars: 현재 변수 환경
        """
        if not self._record_enabled:
            return

        line_no = getattr(stmt, "src_line", None)
        if line_no is None:
            return

        # ═══ CFG 노드에 저장된 intent 검증 (새로운 메커니즘) ═══
        self._process_node_intents(node, cur_vars, line_no)

        # line_info에서 during_annotations 가져오기 (기존 메커니즘)
        line_info = self.an.sa.line_info.get(line_no, {})
        during_annotations = line_info.get('during_annotations', [])

        if not during_annotations:
            return

        # 각 during annotation 검증
        for annot in during_annotations:
            try:
                result = self._verify_during_annotation(annot, node, cur_vars)

                # 결과를 analysis_per_line에 기록
                if line_no not in self.an.analysis_per_line:
                    self.an.analysis_per_line[line_no] = []

                self.an.analysis_per_line[line_no].append({
                    'type': 'during',
                    'annotation_type': annot.annotation_type,
                    'result': result
                })

            except Exception as e:
                # 에러 발생 시 기록
                if line_no not in self.an.analysis_per_line:
                    self.an.analysis_per_line[line_no] = []

                self.an.analysis_per_line[line_no].append({
                    'type': 'during',
                    'annotation_type': annot.annotation_type,
                    'result': {
                        'status': 'error',
                        'message': f'During annotation processing error: {str(e)}'
                    }
                })

    def _process_node_intents(self, node, cur_vars, line_no):
        """
        CFG 노드에 저장된 intent 검증 (새로운 메커니즘)

        Args:
            node: CFGNode (intents 리스트 포함)
            cur_vars: 현재 변수 환경
            line_no: 현재 라인 번호 (코드 라인)
        """
        if not hasattr(node, 'intents') or not node.intents:
            return

        guardian = self.an.guardian_verifier

        for intent in node.intents:
            if intent.get("type") != "during":
                continue

            # standalone annotation은 자체 라인 번호 사용, inline은 코드 라인 번호 사용
            report_line = intent.get("line_no", line_no)

            clauses = intent.get("clauses", [])
            logic_ops = intent.get("logic_ops", [])

            try:
                # 각 clause 검증
                results = []
                for clause in clauses:
                    result = self._verify_during_clause_dynamic(clause, node, cur_vars, guardian, line_no)
                    results.append(result)

                # 논리 연산자로 조합
                combined_result = self._combine_logic_results(results, logic_ops)

                # 결과 출력 (annotation 라인 번호로 표시)
                status = combined_result.get("status", "unknown")
                risk = combined_result.get("risk_score", "")
                risk_str = f" [risk={risk}]" if risk != "" else ""
                if status == "violated":
                    print(f"[INTENT VIOLATED] Line {report_line}: {combined_result.get('message', '')}{risk_str}")
                elif status == "satisfied":
                    print(f"[INTENT SATISFIED] Line {report_line}: {combined_result.get('message', '')}{risk_str}")
                else:
                    print(f"[INTENT {status.upper()}] Line {report_line}: {combined_result.get('message', '')}{risk_str}")

                detail_str = self._format_violation_detail(results, clauses)
                if detail_str:
                    print(detail_str)

                # analysis_per_line에 기록 (annotation 라인 번호 기준)
                if report_line not in self.an.analysis_per_line:
                    self.an.analysis_per_line[report_line] = []

                self.an.analysis_per_line[report_line].append({
                    'type': 'during_intent',
                    'clauses': clauses,
                    'result': combined_result
                })

            except Exception as e:
                print(f"[INTENT ERROR] Line {report_line}: {str(e)}")
                if report_line not in self.an.analysis_per_line:
                    self.an.analysis_per_line[report_line] = []
                self.an.analysis_per_line[report_line].append({
                    'type': 'during_intent',
                    'result': {'status': 'error', 'message': str(e)}
                })

    def _verify_during_annotation(self, annot, node, cur_vars):
        """
        During annotation 검증 (CompoundDuringAnnotation 지원)

        Args:
            annot: DuringAnnotation 또는 CompoundDuringAnnotation 객체
            node: CFGNode
            cur_vars: 변수 환경

        Returns:
            검증 결과 딕셔너리
        """
        # CompoundDuringAnnotation 처리
        if isinstance(annot, CompoundDuringAnnotation):
            return self._verify_compound_during(annot, node, cur_vars)

        # 기존 DuringAnnotation 처리 (하위 호환성)
        guardian = self.an.guardian_verifier
        atype = annot.annotation_type

        if atype == "beforeAfter":
            return guardian.verify_during_before_after(
                var_ref=annot.var_ref,
                comp_op=annot.comp_op,
                line_no=annot.line_no,
                cfg_node=node
            )

        elif atype == "assignCurrent":
            return guardian.verify_during_assign_current(
                var_ref=annot.var_ref,
                comp_op=annot.comp_op,
                line_no=annot.line_no,
                cfg_node=node
            )

        elif atype == "returnExpression":
            return guardian.verify_during_return_expression(
                comp_op=annot.comp_op,
                value_expr=annot.value_expr,
                line_no=annot.line_no,
                cfg_node=node
            )

        elif atype == "returnVariable":
            return guardian.verify_during_return_variable(
                var_ref=annot.var_ref,
                comp_op=annot.comp_op,
                value_expr=annot.value_expr,
                line_no=annot.line_no,
                cfg_node=node
            )

        elif atype == "directComparison":
            return guardian.verify_during_direct_comparison(
                lhs_expr=annot.lhs_expr,
                comp_op=annot.comp_op,
                rhs_expr=annot.rhs_expr,
                line_no=annot.line_no,
                cfg_node=node
            )

        else:
            return {
                'status': 'error',
                'message': f'Unknown during annotation type: {atype}'
            }

    def _verify_compound_during(self, compound: CompoundDuringAnnotation, node, cur_vars):
        """
        동적 분석: CompoundDuringAnnotation 검증
        debug annotation이 주어진 경우 더 정확한 검증
        """
        guardian = self.an.guardian_verifier
        results = []

        # 각 clause 검증
        for clause in compound.clauses:
            result = self._verify_during_clause_dynamic(clause, node, cur_vars, guardian)
            results.append(result)

        # 논리 연산자로 조합
        return self._combine_logic_results(results, compound.logic_ops)

    def _verify_during_clause_dynamic(self, clause: dict, node, cur_vars, guardian, line_no=None):
        """개별 during clause 동적 검증"""
        kind = clause["kind"]
        if line_no is None:
            # fallback: 노드의 첫 번째 statement에서 라인 번호 추출
            line_no = getattr(node.statements[0], "src_line", 0) if node.statements else 0

        if kind == "beforeAfter":
            return guardian.verify_during_before_after(
                var_ref=clause["var"],
                comp_op=clause["op"],
                line_no=line_no,
                cfg_node=node
            )
        elif kind == "assignCurrent":
            return guardian.verify_during_assign_current(
                var_ref=clause["var"],
                comp_op=clause["op"],
                line_no=line_no,
                cfg_node=node
            )
        elif kind == "retExpr":
            return guardian.verify_during_return_expression(
                comp_op=clause["op"],
                value_expr=clause["rhs"],
                line_no=line_no,
                cfg_node=node
            )
        elif kind == "retIndex":
            return guardian.verify_during_return_index(
                index=clause["index"],
                comp_op=clause["op"],
                value_expr=clause["rhs"],
                line_no=line_no,
                cfg_node=node
            )
        elif kind == "retVar":
            return guardian.verify_during_return_variable(
                var_ref=clause["lhs"],
                comp_op=clause["op"],
                value_expr=clause["rhs"],
                line_no=line_no,
                cfg_node=node
            )
        elif kind == "direct":
            return guardian.verify_during_direct_comparison(
                lhs_expr=clause["lhs"],
                comp_op=clause["op"],
                rhs_expr=clause["rhs"],
                line_no=line_no,
                cfg_node=node
            )
        elif kind == "implication":
            return guardian.verify_during_implication(
                antecedent=clause["antecedent"],
                consequent=clause["consequent"],
                line_no=line_no,
                cfg_node=node
            )
        elif kind == "functionArg":
            # @During transfer.arg[0] > 27 형식
            return guardian.verify_during_function_arg(
                func_name=clause["func_name"],
                arg_index=clause["arg_index"],
                comp_op=clause["op"],
                rhs_expr=clause["rhs"],
                line_no=line_no,
                cfg_node=node
            )
        elif kind == "feasible":
            # @During require feasible / assert feasible
            return guardian.verify_during_feasible(
                target=clause["target"],
                line_no=line_no,
                cfg_node=node,
                cur_vars=cur_vars
            )
        elif kind == "changed":
            # @During changed(x, true/false)
            return guardian.verify_during_changed(
                var_ref=clause["var"],
                expect_changed=clause["expect_changed"],
                line_no=line_no,
                cfg_node=node,
                cur_vars=cur_vars
            )
        else:
            return {"status": "error", "message": f"Unknown clause kind: {kind}"}

    def _process_post_annotations(self, fcfg):
        """
        함수 종료 시 Post annotations 검증

        Args:
            fcfg: FunctionCFG 객체
        """
        if not self._record_enabled:
            return

        # ═══ Exit 노드에 저장된 post intent 검증 (새로운 메커니즘) ═══
        self._process_exit_node_intents(fcfg)

        # 함수 내 모든 post annotations 수집 (기존 메커니즘)
        post_annotations = []
        for line_no, line_info in self.an.sa.line_info.items():
            annots = line_info.get('post_annotations', [])
            post_annotations.extend(annots)

        if not post_annotations:
            return

        # 각 post annotation 검증
        for annot in post_annotations:
            try:
                result = self._verify_post_annotation(annot, fcfg)

                # 결과를 analysis_per_line에 기록
                line_no = annot.line_no
                if line_no not in self.an.analysis_per_line:
                    self.an.analysis_per_line[line_no] = []

                self.an.analysis_per_line[line_no].append({
                    'type': 'post',
                    'annotation_type': annot.annotation_type,
                    'result': result
                })

            except Exception as e:
                # 에러 발생 시 기록
                line_no = annot.line_no
                if line_no not in self.an.analysis_per_line:
                    self.an.analysis_per_line[line_no] = []

                self.an.analysis_per_line[line_no].append({
                    'type': 'post',
                    'annotation_type': annot.annotation_type,
                    'result': {
                        'status': 'error',
                        'message': f'Post annotation processing error: {str(e)}'
                    }
                })

    def _process_exit_node_intents(self, fcfg):
        """
        Exit 노드에 저장된 post intent 검증 (새로운 메커니즘)

        Args:
            fcfg: FunctionCFG 객체
        """
        if fcfg is None:
            return

        exit_node = fcfg.get_exit_node() if hasattr(fcfg, 'get_exit_node') else None
        if exit_node is None or not hasattr(exit_node, 'intents'):
            return

        if not exit_node.intents:
            return

        guardian = self.an.guardian_verifier

        for intent in exit_node.intents:
            if intent.get("type") != "post":
                continue

            clauses = intent.get("clauses", [])
            logic_ops = intent.get("logic_ops", [])
            line_no = intent.get("line_no", 0)

            try:
                # 각 clause 검증
                results = []
                for clause in clauses:
                    result = self._verify_post_clause_dynamic(clause, line_no, fcfg, guardian)
                    results.append(result)

                # 논리 연산자로 조합
                combined_result = self._combine_logic_results(results, logic_ops)

                # 결과 출력
                status = combined_result.get("status", "unknown")
                risk = combined_result.get("risk_score", "")
                risk_str = f" [risk={risk}]" if risk != "" else ""
                if status == "violated":
                    print(f"[POST INTENT VIOLATED] Line {line_no}: {combined_result.get('message', '')}{risk_str}")
                elif status == "satisfied":
                    print(f"[POST INTENT SATISFIED] Line {line_no}: {combined_result.get('message', '')}{risk_str}")
                else:
                    print(f"[POST INTENT {status.upper()}] Line {line_no}: {combined_result.get('message', '')}{risk_str}")

                detail_str = self._format_violation_detail(results, clauses)
                if detail_str:
                    print(detail_str)

                # analysis_per_line에 기록
                if line_no not in self.an.analysis_per_line:
                    self.an.analysis_per_line[line_no] = []

                self.an.analysis_per_line[line_no].append({
                    'type': 'post_intent',
                    'clauses': clauses,
                    'result': combined_result
                })

            except Exception as e:
                print(f"[POST INTENT ERROR] Line {line_no}: {str(e)}")
                if line_no not in self.an.analysis_per_line:
                    self.an.analysis_per_line[line_no] = []
                self.an.analysis_per_line[line_no].append({
                    'type': 'post_intent',
                    'result': {'status': 'error', 'message': str(e)}
                })

    def _verify_post_clause_dynamic(self, clause: dict, fcfg, guardian):
        """개별 post clause 동적 검증"""
        kind = clause["kind"]
        line_no = fcfg.start_line if hasattr(fcfg, 'start_line') else 0

        if kind == "entryExit":
            return guardian.verify_post_entry_exit(
                var_ref=clause["var"],
                comp_op=clause["op"],
                line_no=line_no,
                fn_cfg=fcfg
            )
        elif kind == "changed":
            return guardian.verify_post_changed(
                var_ref=clause["var"],
                expect_changed=clause["expect_changed"],
                line_no=line_no,
                fn_cfg=fcfg
            )
        elif kind == "retExpr":
            return guardian.verify_post_return_expression(
                comp_op=clause["op"],
                value_expr=clause["rhs"],
                line_no=line_no,
                fn_cfg=fcfg
            )
        elif kind == "retIndex":
            return guardian.verify_post_return_index(
                index=clause["index"],
                comp_op=clause["op"],
                value_expr=clause["rhs"],
                line_no=line_no,
                fn_cfg=fcfg
            )
        elif kind == "retVar":
            return guardian.verify_post_return_variable(
                var_ref=clause["lhs"],
                comp_op=clause["op"],
                value_expr=clause["rhs"],
                line_no=line_no,
                fn_cfg=fcfg
            )
        elif kind == "direct":
            return guardian.verify_post_direct_comparison(
                lhs_expr=clause["lhs"],
                comp_op=clause["op"],
                rhs_expr=clause["rhs"],
                line_no=line_no,
                fn_cfg=fcfg
            )
        elif kind == "implication":
            return guardian.verify_post_implication(
                antecedent=clause["antecedent"],
                consequent=clause["consequent"],
                line_no=line_no,
                fn_cfg=fcfg
            )
        else:
            return {"status": "error", "message": f"Unknown post clause kind: {kind}"}

    def _verify_post_annotation(self, annot, fcfg):
        """
        Post annotation 검증 (CompoundPostAnnotation 지원)

        Args:
            annot: PostAnnotation 또는 CompoundPostAnnotation 객체
            fcfg: FunctionCFG

        Returns:
            검증 결과 딕셔너리
        """
        # CompoundPostAnnotation 처리
        if isinstance(annot, CompoundPostAnnotation):
            return self._verify_compound_post(annot, fcfg)

        # 기존 PostAnnotation 처리 (하위 호환성)
        guardian = self.an.guardian_verifier
        atype = annot.annotation_type

        if atype == "entryExit":
            return guardian.verify_post_entry_exit(
                var_ref=annot.var_ref,
                comp_op=annot.comp_op,
                line_no=annot.line_no,
                fn_cfg=fcfg
            )

        elif atype == "changed":
            return guardian.verify_post_changed(
                var_ref=annot.var_ref,
                expect_changed=getattr(annot, "expect_changed", False),
                line_no=annot.line_no,
                fn_cfg=fcfg
            )

        elif atype == "returnExpression":
            return guardian.verify_post_return_expression(
                comp_op=annot.comp_op,
                value_expr=annot.value_expr,
                line_no=annot.line_no,
                fn_cfg=fcfg
            )

        elif atype == "returnVariable":
            return guardian.verify_post_return_variable(
                var_ref=annot.var_ref,
                comp_op=annot.comp_op,
                value_expr=annot.value_expr,
                line_no=annot.line_no,
                fn_cfg=fcfg
            )

        elif atype == "directComparison":
            return guardian.verify_post_direct_comparison(
                lhs_expr=annot.lhs_expr,
                comp_op=annot.comp_op,
                rhs_expr=annot.rhs_expr,
                line_no=annot.line_no,
                fn_cfg=fcfg
            )

        else:
            return {
                'status': 'error',
                'message': f'Unknown post annotation type: {atype}'
            }

    def _verify_compound_post(self, compound: CompoundPostAnnotation, fcfg):
        """
        동적 분석: CompoundPostAnnotation 검증
        debug annotation이 주어진 경우 더 정확한 검증
        """
        guardian = self.an.guardian_verifier
        results = []

        # 각 clause 검증
        for clause in compound.clauses:
            result = self._verify_post_clause_dynamic(clause, compound.line_no, fcfg, guardian)
            results.append(result)

        # 논리 연산자로 조합
        return self._combine_logic_results(results, compound.logic_ops)

    def _verify_post_clause_dynamic(self, clause: dict, line_no: int, fcfg, guardian):
        """개별 post clause 동적 검증"""
        kind = clause["kind"]

        if kind == "entryExit":
            return guardian.verify_post_entry_exit(
                var_ref=clause["var"],
                comp_op=clause["op"],
                line_no=line_no,
                fn_cfg=fcfg
            )
        elif kind == "changed":
            return guardian.verify_post_changed(
                var_ref=clause["var"],
                expect_changed=clause["expect_changed"],
                line_no=line_no,
                fn_cfg=fcfg
            )
        elif kind == "retExpr":
            return guardian.verify_post_return_expression(
                comp_op=clause["op"],
                value_expr=clause["rhs"],
                line_no=line_no,
                fn_cfg=fcfg
            )
        elif kind == "retIndex":
            return guardian.verify_post_return_index(
                index=clause["index"],
                comp_op=clause["op"],
                value_expr=clause["rhs"],
                line_no=line_no,
                fn_cfg=fcfg
            )
        elif kind == "retVar":
            return guardian.verify_post_return_variable(
                var_ref=clause["lhs"],
                comp_op=clause["op"],
                value_expr=clause["rhs"],
                line_no=line_no,
                fn_cfg=fcfg
            )
        elif kind == "direct":
            return guardian.verify_post_direct_comparison(
                lhs_expr=clause["lhs"],
                comp_op=clause["op"],
                rhs_expr=clause["rhs"],
                line_no=line_no,
                fn_cfg=fcfg
            )
        elif kind == "implication":
            return guardian.verify_post_implication(
                antecedent=clause["antecedent"],
                consequent=clause["consequent"],
                line_no=line_no,
                fn_cfg=fcfg
            )
        else:
            return {"status": "error", "message": f"Unknown clause kind: {kind}"}

    def _combine_logic_results(self, results: list[dict], logic_ops: list[str]) -> dict:
        """
        여러 clause 결과를 논리 연산자로 조합

        Args:
            results: 각 clause의 검증 결과 리스트
            logic_ops: 논리 연산자 리스트 ('&&' 또는 '||')

        Returns:
            조합된 결과 딕셔너리
        """
        if not results:
            return {"status": "error", "message": "No results to combine"}

        if len(results) == 1:
            r = results[0]
            # details 내부의 risk_score를 top-level로 전파
            if r.get("risk_score") is None and r.get("details"):
                rs = r["details"].get("risk_score")
                if rs is not None:
                    r["risk_score"] = rs
            return r

        # 초기 결과
        combined = results[0]
        combined_status = combined.get("status", "unknown")

        for i, result in enumerate(results[1:]):
            op = logic_ops[i] if i < len(logic_ops) else "&&"
            status = result.get("status", "unknown")

            if op == "&&":
                # AND: 하나라도 violated이면 violated, 하나라도 unknown이면 unknown
                if combined_status == "violated" or status == "violated":
                    combined_status = "violated"
                elif combined_status == "unknown" or status == "unknown":
                    combined_status = "unknown"
                elif combined_status == "error" or status == "error":
                    combined_status = "error"
                else:
                    combined_status = "satisfied"
            elif op == "||":
                # OR: 하나라도 satisfied이면 satisfied, 둘 다 violated이면 violated
                if combined_status == "satisfied" or status == "satisfied":
                    combined_status = "satisfied"
                elif combined_status == "error" or status == "error":
                    combined_status = "error"
                elif combined_status == "unknown" or status == "unknown":
                    combined_status = "unknown"
                else:
                    combined_status = "violated"

        # 메시지 조합
        messages = [r.get("message", "") for r in results if r.get("message")]
        combined_msg = " ; ".join(messages) if messages else ""

        # risk_score: 가장 높은 위험도를 전파 (top-level 또는 details 내부에서 추출)
        risk_scores = []
        for r in results:
            rs = r.get("risk_score")
            if rs is None:
                rs = r.get("details", {}).get("risk_score")
            if rs is not None:
                risk_scores.append(rs)
        max_risk = max(risk_scores) if risk_scores else None

        out = {"status": combined_status, "message": combined_msg}
        if max_risk is not None:
            out["risk_score"] = max_risk
        return out

    # ── 상세 출력 헬퍼 ──────────────────────────────────────────────
    @staticmethod
    def _risk_type_label(risk_type: int) -> str:
        return {1: "safe", 2: "one-side", 3: "both-side"}.get(risk_type, "unknown")

    @staticmethod
    def _risk_type_from_score(score) -> int:
        """risk_score(0-10)에서 risk type 역산"""
        if score is None:
            return 0
        score = float(score)
        if score <= 3.3:
            return 1
        elif score <= 6.6:
            return 2
        else:
            return 3

    @staticmethod
    def _is_literal_expr(expr) -> bool:
        """Expression 객체가 순수 리터럴(상수)인지 판별"""
        if expr is None:
            return False
        return (getattr(expr, "literal", None) is not None
                and getattr(expr, "operator", None) is None
                and getattr(expr, "identifier", None) is None)

    @staticmethod
    def _fmt_val(v: str) -> str:
        """'UnsignedIntegerInterval([0, 100])' → '[0, 100]' 로 간결화"""
        import re
        m = re.search(r'\[([^\]]*)\]', v)
        return f"[{m.group(1)}]" if m else v

    def _format_violation_detail(self, results: list[dict], clauses: list[dict]) -> str:
        """각 clause 결과의 상세 정보를 포맷팅하여 반환"""
        lines = []
        for i, result in enumerate(results):
            details = result.get("details", {})
            kind = result.get("kind", "")
            clause = clauses[i] if i < len(clauses) else {}
            risk_score = details.get("risk_score")
            risk_type = self._risk_type_from_score(risk_score) if risk_score is not None else None
            risk_label = self._risk_type_label(risk_type) if risk_type else None

            prefix = "  "
            if len(results) > 1:
                prefix = f"  [{i+1}] "

            fv = self._fmt_val

            if kind == "duringAssignCurrent":
                lines.append(f"{prefix}Assign  = {fv(details.get('assign_value', '?'))}")
                lines.append(f"{prefix}Current = {fv(details.get('current_value', '?'))}")
            elif kind == "duringBeforeAfter":
                lines.append(f"{prefix}Before = {fv(details.get('before', '?'))}")
                lines.append(f"{prefix}After  = {fv(details.get('after', '?'))}")
            elif kind in ("postEntryExit", "postChanged"):
                lines.append(f"{prefix}Entry = {fv(details.get('entry_value', '?'))}")
                lines.append(f"{prefix}Exit  = {fv(details.get('exit_value', '?'))}")
            elif kind in ("duringDirectCmp", "postDirectCmp"):
                lhs_val = fv(details.get("lhs", details.get("lhs_value", "?")))
                rhs_val = fv(details.get("rhs", details.get("rhs_value", "?")))
                # RHS가 리터럴이면 Analysis/Intent, 아니면 LHS/RHS
                rhs_expr = clause.get("rhs")
                if rhs_expr is not None and self._is_literal_expr(rhs_expr):
                    lines.append(f"{prefix}Analysis = {lhs_val}")
                    lines.append(f"{prefix}Intent   = {rhs_val}")
                else:
                    lines.append(f"{prefix}LHS = {lhs_val}")
                    lines.append(f"{prefix}RHS = {rhs_val}")
            elif kind in ("duringRetExpr", "postRetExpr",
                          "duringRetIndex", "postRetIndex",
                          "duringRetVar", "postRetVar"):
                ret_val = fv(details.get("return_value", details.get("return_join",
                          details.get("indexed_join", details.get("actual", "?")))))
                rhs_val = fv(details.get("expected", details.get("rhs_value", "?")))
                lines.append(f"{prefix}Analysis = {ret_val}")
                lines.append(f"{prefix}Intent   = {rhs_val}")
            elif kind in ("duringFunctionArg",):
                lines.append(f"{prefix}Analysis = {fv(details.get('arg_value', '?'))}")
                lines.append(f"{prefix}Intent   = {fv(details.get('rhs_value', '?'))}")
            elif kind in ("duringImplication", "postImplication"):
                ant = details.get("antecedent", {})
                con = details.get("consequent", {})
                ant_status = ant.get("status", "?") if isinstance(ant, dict) else str(ant)
                con_status = con.get("status", "?") if isinstance(con, dict) else str(con)
                logic = details.get("logic")
                if logic == "vacuous-true":
                    lines.append(f"{prefix}Antecedent = false (vacuous truth)")
                else:
                    lines.append(f"{prefix}Antecedent = {ant_status}")
                    lines.append(f"{prefix}Consequent = {con_status}")
                risk_label = None  # implication은 risk type 별도 미표시

            if risk_label:
                lines.append(f"{prefix}Risk: Type {risk_type} ({risk_label})")

        return "\n".join(lines) if lines else ""
