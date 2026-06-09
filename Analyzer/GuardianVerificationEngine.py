"""
GuardianVerificationEngine.py

Handles verification of @During and @Post intent annotations.
Provides temporal state checking capabilities for SolQDebug.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from Analyzer.ContractAnalyzer import ContractAnalyzer

from Domain.IR import Expression
from Domain.Interval import IntegerInterval, UnsignedIntegerInterval, BoolInterval
from Utils.Helper import VariableEnv
from Utils.CFG import CFGNode

class GuardianVerificationEngine:
    def __init__(self, analyzer: "ContractAnalyzer"):
        self.analyzer = analyzer

    # ═══════════════════════════════════════════════════════════════════
    #  Guardian DSL Expression Evaluation
    #  (VarRef*, InlineInterval, PercentOf, Ceil, Floor, Address literals)
    # ═══════════════════════════════════════════════════════════════════

    def evaluate_guardian_expression(self, expr: Expression, variables: dict,
                                     callerObject=None, callerContext=None):
        """
        Guardian DSL expression 평가 (주석 전용 구문)

        Guardian-specific contexts:
        - VarRefBase, VarRefMemberAccess, VarRefIndexAccess: 변수 참조
        - ReturnElemRef: return tuple 원소 접근
        - InlineInterval: [lo, hi] 구간 리터럴
        - PercentOfFuncContext: PercentOf(x, n)
        - CeilFuncContext: ceil(x, n)
        - FloorFuncContext: floor(x, n)
        - AddrLiteralExprContext, SymAddrLiteralExprContext: address 리터럴

        일반 Solidity expression은 evaluator에 위임
        """
        ctx = expr.context

        # ─── Guardian-specific contexts ───────────────────────────
        if ctx == "ReturnElemRef":
            return self._evaluate_return_elem_ref(expr, variables, callerObject, callerContext)

        elif ctx == "InlineInterval":
            return self._evaluate_inline_interval(expr)

        elif ctx == "PercentOfFuncContext":
            return self._evaluate_percent_of(expr, variables, callerObject, callerContext)

        elif ctx == "CeilFuncContext":
            return self._evaluate_ceil(expr, variables, callerObject, callerContext)

        elif ctx == "FloorFuncContext":
            return self._evaluate_floor(expr, variables, callerObject, callerContext)

        elif ctx in {"AddrLiteralExprContext", "SymAddrLiteralExprContext"}:
            return self._evaluate_address_literal(expr)

        # ─── VarRef contexts → evaluator에 위임 ───────────────────
        # NormalVarRef, IntentMemberAccess, IntentIndexAccess는
        # 일반 IdentifierExpContext, MemberAccessContext, IndexAccessExpContext와
        # 동일하게 처리되므로 evaluator에 위임
        elif ctx in {"NormalVarRef", "IntentMemberAccess", "IntentIndexAccess"}:
            return self.analyzer.evaluator.evaluate_expression(
                expr, variables, callerObject, callerContext
            )

        # ─── 일반 Solidity expression → evaluator 위임 ───────────
        else:
            return self.analyzer.evaluator.evaluate_expression(
                expr, variables, callerObject, callerContext
            )

    # ─── Guardian DSL 평가 헬퍼들 ─────────────────────────────────────

    def _evaluate_return_elem_ref(self, expr: Expression, variables: dict,
                                  callerObject=None, callerContext=None):
        """
        ReturnElemRef: return[N]

        expr.base  = Expression(identifier='return', ...)
        expr.index = Expression(literal='N', ...)
        """
        # (1) 'return' 변수 가져오기 (Recorder/CFG가 variables에 넣어둠)
        ret_var = variables.get("return")
        if ret_var is None:
            raise ValueError("return tuple not available in current context")

        # (2) 인덱스 계산
        idx_val = self.evaluate_guardian_expression(
            expr.index, variables, callerObject, callerContext
        )
        idx = int(idx_val.min_value) if hasattr(idx_val, "min_value") else int(idx_val)

        # (3) 튜플 원소 반환
        return ret_var.value[idx]

    def _evaluate_inline_interval(self, expr: Expression):
        """
        InlineInterval: [lo, hi]

        expr.elements[0] = Expression(literal='lo', ...)
        expr.elements[1] = Expression(literal='hi', ...)
        """
        lo = int(expr.elements[0].literal, 0)
        hi = int(expr.elements[1].literal, 0)
        cls = IntegerInterval if lo < 0 else UnsignedIntegerInterval
        bits = 256  # 필요하면 가변
        return cls(lo, hi, bits)

    def _evaluate_percent_of(self, expr: Expression, variables: dict,
                            callerObject=None, callerContext=None):
        """
        PercentOf(x, n): x의 n%

        expr.arguments[0] = valueExpr (기준 값)
        expr.arguments[1] = numberLiteral (퍼센트)
        """
        base_iv = self.evaluate_guardian_expression(
            expr.arguments[0], variables, callerObject, callerContext
        )
        pct = int(expr.arguments[1].literal, 0)
        return base_iv.percent_of(pct)

    def _evaluate_ceil(self, expr: Expression, variables: dict,
                      callerObject=None, callerContext=None):
        """
        ceil(x, n): x를 n 단위로 올림

        expr.arguments[0] = arithExpr (기준 값)
        expr.arguments[1] = numberLiteral (단위)
        """
        base_iv = self.evaluate_guardian_expression(
            expr.arguments[0], variables, callerObject, callerContext
        )
        unit = int(expr.arguments[1].literal, 0)
        return base_iv.ceil_to_unit(unit)

    def _evaluate_floor(self, expr: Expression, variables: dict,
                       callerObject=None, callerContext=None):
        """
        floor(x, n): x를 n 단위로 내림

        expr.arguments[0] = arithExpr (기준 값)
        expr.arguments[1] = numberLiteral (단위)
        """
        base_iv = self.evaluate_guardian_expression(
            expr.arguments[0], variables, callerObject, callerContext
        )
        unit = int(expr.arguments[1].literal, 0)
        return base_iv.floor_to_unit(unit)

    def _evaluate_address_literal(self, expr: Expression):
        """
        address N / symbolicAddress N

        expr.literal = 숫자 문자열
        """
        val = int(expr.literal, 0)
        return UnsignedIntegerInterval(val, val, 160)

    # ═══════════════════════════════════════════════════════════════════
    #  DURING / POST Verification Methods
    # ═══════════════════════════════════════════════════════════════════

    def verify_during_before_after(
        self, *, var_ref: Expression, comp_op: str,
        line_no: int, cfg_node: CFGNode
    ) -> dict[str, Any]:

        try:
            # 1. before / after variable environments -----------------
            before_env = cfg_node.before_envs.get(line_no)
            if before_env is None:
                return self._err(
                    "duringBeforeAfter",
                    f"no before-env captured for line {line_no}", line_no
                )

            after_env  = cfg_node.variables

            # 2. evaluate var_ref in the two envs ---------------------
            before_val = self.evaluate_guardian_expression(var_ref, before_env, None, None)
            after_val  = self.evaluate_guardian_expression(var_ref, after_env,  None, None)

            # 3. compare ---------------------------------------------
            cmp = self._compare_values(before_val, comp_op, after_val)
            status = self._status_from_cmp(cmp)
            return {
                "status": status,
                "kind": "duringBeforeAfter",
                "line": line_no,
                "details": {
                    "variable": self._pretty_expr(var_ref),
                    "before": str(before_val),
                    "after": str(after_val),
                    "operator": comp_op,
                    **cmp,
                    "prob_true": self._prob_true_from_cmp(cmp),
                    "prob_false": round(1.0 - self._prob_true_from_cmp(cmp), 3),
                },
                "message": f'{self._pretty_expr(var_ref)}(Before {comp_op} After) → {cmp["message"]}',
            }

        except Exception as e:
            return self._err("duringBeforeAfter", f"internal error: {e}", line_no)

    def verify_during_assign_current(self, *, var_ref, comp_op,
                                     line_no, cfg_node):

        fcfg = self.analyzer.current_target_function_cfg

        # 1)  Assign 값  ― assign_env 를 통째로 변수-환경으로 사용
        assign_val = self.evaluate_guardian_expression(
            var_ref, fcfg.assign_env, None, None)

        if assign_val is None:
            return self._err("duringAssignCurrent",
                             "no initial assignment for variable", line_no)

        # 2)  Current 값
        current_val = self.evaluate_guardian_expression(
            var_ref, cfg_node.variables, None, None)

        # 3)  비교
        cmp = self._compare_values(assign_val, comp_op, current_val)
        status = self._status_from_cmp(cmp)

        return {
            "status": status,
            "kind": "duringAssignCurrent",
            "line": line_no,
            "details": {
                "variable": self._expr_to_str(var_ref),
                "assign_value": str(assign_val),
                "current_value": str(current_val),
                "operator": comp_op,
                **cmp
            },
            "message": f'{self._expr_to_str(var_ref)}(Assign {comp_op} Current) '
                       f'→ {cmp["message"]}',
        }

    def verify_during_return_expression(
        self, *, comp_op: str, value_expr: Expression,
        line_no: int, cfg_node: CFGNode
    ) -> dict[str, Any]:

        try:
            # ── 1) "현재 함수" CFG -------------------------------
            fcfg = self.analyzer.current_target_function_cfg
            if fcfg is None:
                return self._err("duringRetExpr",
                                  "no active FunctionCFG", line_no)

            # ── 2) return 값 확보 -------------------------------
            # builder 가 EXIT.return_vals[ln] 에 저장해 둔다.
            ret_vals = fcfg.get_exit_node().return_vals
            if line_no not in ret_vals:
                return self._err("duringRetExpr",
                                  f"no return at line {line_no}", line_no)
            ret_val = ret_vals[line_no]

            # ── 3) valueExpr 평가 -------------------------------
            rhs_val = self.evaluate_guardian_expression(
                value_expr, cfg_node.variables, None, None)

            # ── 4) 비교 ----------------------------------------
            cmp = self._compare_values(ret_val, comp_op, rhs_val)
            status = self._status_from_cmp(cmp)

            if status == "warning" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | violation lower={fr.get('lower_violation')} upper={fr.get('upper_violation')} overlap={fr.get('overlap_zone')}"
            else:
                msg_tail = ""

            return {
                "status":  status,
                "kind":    "duringRetExpr",
                "line":    line_no,
                "details": {
                    "return_value": str(ret_val),
                    "expected":     str(rhs_val),
                    "operator":     comp_op,
                    **cmp
                },
                "message": (f"returnExpression {comp_op} {self._pretty_expr(value_expr)} "
                            f"→ {cmp['message']}{msg_tail}")
            }

        except Exception as e:
            return self._err("duringRetExpr", f"internal error: {e}", line_no)

    # ────────────────────────────────────────────────────────────────
    #  DURING : return[idx] 비교
    # ----------------------------------------------------------------
    def verify_during_return_index(
        self, *, index: int, comp_op: str, value_expr: Expression,
        line_no: int, cfg_node: CFGNode
    ) -> dict[str, Any]:
        """
        @During return[idx] op value 검증
        tuple 반환값의 특정 인덱스 원소를 value와 비교
        """
        try:
            # ── 1) "현재 함수" CFG -------------------------------
            fcfg = self.analyzer.current_target_function_cfg
            if fcfg is None:
                return self._err("duringRetIndex",
                                  "no active FunctionCFG", line_no)

            # ── 2) return 값 확보 -------------------------------
            ret_vals = fcfg.get_exit_node().return_vals
            if line_no not in ret_vals:
                return self._err("duringRetIndex",
                                  f"no return at line {line_no}", line_no)
            ret_val = ret_vals[line_no]

            # ── 3) tuple 인덱스 접근 ----------------------------
            if isinstance(ret_val, tuple):
                if index < 0 or index >= len(ret_val):
                    return self._err("duringRetIndex",
                                      f"index {index} out of range for tuple of length {len(ret_val)}", line_no)
                indexed_val = ret_val[index]
            else:
                # 단일 반환값인 경우 인덱스 0만 허용
                if index != 0:
                    return self._err("duringRetIndex",
                                      f"return value is not a tuple, index {index} invalid", line_no)
                indexed_val = ret_val

            # ── 4) valueExpr 평가 -------------------------------
            rhs_val = self.evaluate_guardian_expression(
                value_expr, cfg_node.variables, None, None)

            # ── 5) 비교 ----------------------------------------
            cmp = self._compare_values(indexed_val, comp_op, rhs_val)
            status = self._status_from_cmp(cmp)

            if status == "warning" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | violation lower={fr.get('lower_violation')} upper={fr.get('upper_violation')} overlap={fr.get('overlap_zone')}"
            else:
                msg_tail = ""

            return {
                "status":  status,
                "kind":    "duringRetIndex",
                "line":    line_no,
                "details": {
                    "return_index": index,
                    "indexed_value": str(indexed_val),
                    "expected":     str(rhs_val),
                    "operator":     comp_op,
                    **cmp
                },
                "message": (f"return[{index}] {comp_op} {self._pretty_expr(value_expr)} "
                            f"→ {cmp['message']}{msg_tail}")
            }

        except Exception as e:
            return self._err("duringRetIndex", f"internal error: {e}", line_no)

    # ────────────────────────────────────────────────────────────────
    #  DURING : return var  비교
    # ----------------------------------------------------------------
    def verify_during_return_variable(
            self, *, var_ref, comp_op, value_expr, line_no, cfg_node
    ) -> dict[str, Any]:

        try:
            fcfg = self.analyzer.current_target_function_cfg
            exit_n = fcfg.get_exit_node()

            # ① "해당‧또는 가장 가까운 이전" return-값 가져오기 -------------
            if line_no in exit_n.return_vals:
                ret_val = exit_n.return_vals[line_no]
            else:  # 앞쪽에서 찾기
                prevs = [ln for ln in exit_n.return_vals if ln < line_no]
                if not prevs:
                    return self._err("duringRetVar",
                                     "no return value available", line_no)
                ln_sel = max(prevs)  # 가장 가까운 것
                ret_val = exit_n.return_vals[ln_sel]

            # ② LHS 값 추출  -------------------------------------------------
            if var_ref.context == "ReturnElemRef":
                idx = int(var_ref.index.literal, 0)
                if not isinstance(ret_val, (list, tuple)):
                    return self._err("duringRetVar",
                                     "function does not return a tuple", line_no)
                if idx >= len(ret_val):
                    return self._err("duringRetVar",
                                     f"tuple index {idx} out of range", line_no)
                lhs_val = ret_val[idx]

            else:  # 보통의 varRef (이름 있는 return 변수 등)
                lhs_val = self.evaluate_guardian_expression(
                    var_ref, cfg_node.variables, None, None
                )

            # ③ RHS 값 계산  -------------------------------------------------
            rhs_val = self.evaluate_guardian_expression(
                value_expr, cfg_node.variables, None, None
            )

            # ④ 비교  --------------------------------------------------------
            cmp = self._compare_values(lhs_val, comp_op, rhs_val)
            status = self._status_from_cmp(cmp)

            if status == "warning" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | violation lower={fr.get('lower_violation')} upper={fr.get('upper_violation')} overlap={fr.get('overlap_zone')}"
            else:
                msg_tail = ""

            return {
                "status": status,
                "kind": "duringRetVar",
                "line": line_no,
                "details": {
                    "variable": self._pretty_expr(var_ref),
                    "actual": str(lhs_val),
                    "expected": str(rhs_val),
                    "operator": comp_op,
                    **cmp
                },
                "message": f'return {self._pretty_expr(var_ref)} {comp_op} '
                           f'{rhs_val}  →  {cmp["message"]} {msg_tail}'
            }

        except Exception as e:
            return self._err("duringRetVar", f"internal error: {e}", line_no)

    # ────────────────────────────────────────────────────────────────
    #  DURING :  valueExpr  op  valueExpr
    # ----------------------------------------------------------------
    def verify_during_direct_comparison(
            self, *, lhs_expr, comp_op, rhs_expr, line_no, cfg_node
    ) -> dict[str, Any]:

        try:
            vars_env = cfg_node.variables  # 현재 변수 Env

            # ① 두 피연산식 계산 -------------------------------------------------
            lhs_val = self.evaluate_guardian_expression(lhs_expr, vars_env, None, None)
            rhs_val = self.evaluate_guardian_expression(rhs_expr, vars_env, None, None)

            # ② 비교 ------------------------------------------------------------
            cmp = self._compare_values(lhs_val, comp_op, rhs_val)
            status = self._status_from_cmp(cmp)

            if status == "warning" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | violation lower={fr.get('lower_violation')} upper={fr.get('upper_violation')} overlap={fr.get('overlap_zone')}"
            else:
                msg_tail = ""

            # ③ 결과 dict -------------------------------------------------------
            return {
                "status": status,
                "kind": "duringDirectCmp",
                "line": line_no,
                "details": {
                    "lhs": str(lhs_val),
                    "rhs": str(rhs_val),
                    "operator": comp_op,
                    **cmp  # satisfied / violated / warning / prob_true
                },
                "message": f'{self._pretty_expr(lhs_expr)} {comp_op} '
                           f'{self._pretty_expr(rhs_expr)}  →  {cmp["message"]} {msg_tail}'
            }

        except Exception as e:
            return self._err("duringDirectCmp",
                             f"internal error: {e}", line_no)

    def verify_during_implication(self, *, antecedent: dict, consequent: dict, line_no: int, cfg_node: CFGNode) -> dict:
        try:
            a_res = self._eval_during_predicate(antecedent, line_no=line_no, cfg_node=cfg_node)
            a_state = self._tri_state(a_res)

            if a_state == "violated":  # A=false  → vacuously true
                status = "success"
                return {
                    "status": status,
                    "kind": "duringImplication",
                    "line": line_no,
                    "details": {"antecedent": a_res, "consequent": None, "logic": "vacuous-true"},
                    "message": "A ⇒ B holds vacuously (A is false)."
                }

            if a_state == "satisfied":  # A=true   → B로 결정
                b_res = self._eval_during_predicate(consequent, line_no=line_no, cfg_node=cfg_node)
                b_state = self._tri_state(b_res)
                status = self._status_from_state(b_state)
                return {
                    "status": status,
                    "kind": "duringImplication",
                    "line": line_no,
                    "details": {"antecedent": a_res, "consequent": b_res},
                    "message": f"A ⇒ B with A=true → B is {b_state}."
                }

            # A warning
            return {
                "status": "warning",
                "kind": "duringImplication",
                "line": line_no,
                "details": {"antecedent": a_res, "consequent": None},
                "message": "A ⇒ B warning (A is warning)."
            }

        except Exception as e:
            return self._err("duringImplication", f"internal error: {e}", line_no)

    # ────────────────────────────────────────────────────────────────
    #  DURING : funcName.arg[index] op value
    # ----------------------------------------------------------------
    def verify_during_function_arg(
            self, *, func_name: str, arg_index: int, comp_op: str,
            rhs_expr, line_no: int, cfg_node
    ) -> dict[str, Any]:
        """
        @During transfer.arg[0] > 0 검증
        해당 라인의 함수 호출에서 arg_index번째 인자의 값을 rhs와 비교
        """
        try:
            # ① statements에서 함수 호출 찾기
            target_call_expr = None
            for stmt in cfg_node.statements:
                if stmt.statement_type == 'functionCall':
                    found = self._find_function_call_in_expr(stmt.function_expr, func_name)
                    if found:
                        target_call_expr = found
                        break

            if target_call_expr is None:
                return self._err("duringFunctionArg",
                    f"함수 '{func_name}' 호출을 찾을 수 없음", line_no)

            # ② 인자 추출
            arguments = target_call_expr.arguments or []
            if arg_index >= len(arguments):
                return self._err("duringFunctionArg",
                    f"arg[{arg_index}] 범위 초과 (인자 개수: {len(arguments)})", line_no)

            arg_expr = arguments[arg_index]

            # ③ 인자 값 evaluate
            vars_env = cfg_node.variables
            arg_val = self.analyzer.evaluator.evaluate_expression(arg_expr, vars_env, None, None)

            # ④ RHS evaluate 및 비교
            rhs_val = self.evaluate_guardian_expression(rhs_expr, vars_env, None, None)
            cmp = self._compare_values(arg_val, comp_op, rhs_val)
            status = self._status_from_cmp(cmp)

            if status == "warning" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | violation lower={fr.get('lower_violation')} upper={fr.get('upper_violation')} overlap={fr.get('overlap_zone')}"
            else:
                msg_tail = ""

            return {
                "status": status,
                "kind": "duringFunctionArg",
                "line": line_no,
                "details": {
                    "func_name": func_name,
                    "arg_index": arg_index,
                    "arg_value": str(arg_val),
                    "rhs_value": str(rhs_val),
                    "operator": comp_op,
                    **cmp
                },
                "message": f"{func_name}.arg[{arg_index}] {comp_op} {self._pretty_expr(rhs_expr)} → {cmp['message']}{msg_tail}"
            }

        except Exception as e:
            return self._err("duringFunctionArg", f"internal error: {e}", line_no)

    def _find_function_call_in_expr(self, expr, target_name: str):
        """
        Expression 트리에서 target_name 함수 호출을 재귀적으로 찾음
        반환: 해당 함수 호출 Expression (arguments 포함) 또는 None
        """
        if expr is None:
            return None

        # Case 1: FunctionCallContext - 함수 호출
        if getattr(expr, 'context', None) == 'FunctionCallContext':
            func = expr.function
            if func:
                # MemberAccess: base.transfer()
                if getattr(func, 'context', None) == 'MemberAccessContext' and func.member == target_name:
                    return expr
                # Direct call: transfer()
                if getattr(func, 'context', None) == 'IdentifierExpContext' and func.identifier == target_name:
                    return expr

            # 인자들에서 재귀 검색 (체인 호출: a.mul(x).div(y)에서 mul 찾기)
            if expr.arguments:
                for arg in expr.arguments:
                    found = self._find_function_call_in_expr(arg, target_name)
                    if found:
                        return found

            # function 표현식에서도 재귀 (base에서 검색)
            if func:
                found = self._find_function_call_in_expr(func, target_name)
                if found:
                    return found

        # Case 2: MemberAccessContext - base에서 검색
        if getattr(expr, 'context', None) == 'MemberAccessContext' and expr.base:
            return self._find_function_call_in_expr(expr.base, target_name)

        # Case 3: 이항 연산자
        if getattr(expr, 'left', None):
            found = self._find_function_call_in_expr(expr.left, target_name)
            if found:
                return found
        if getattr(expr, 'right', None):
            found = self._find_function_call_in_expr(expr.right, target_name)
            if found:
                return found

        return None


    # === POST =======================================================

    # GuardianVerificationEngine.py
    # ────────────────────────────────────────────────────────────────
    #  POST :  varRef( Entry <op> Exit )
    # ----------------------------------------------------------------
    def verify_post_entry_exit(self, *, var_ref, comp_op: str, line_no: int, fn_cfg) -> dict[str, Any]:
        try:
            entry_env = fn_cfg.related_variables  # debug annotation 패치가 반영된 값 사용

            entry_val = self._materialize(self.evaluate_guardian_expression(var_ref, entry_env, None, None))
            exit_val = self._eval_on_exit_value(var_ref, fn_cfg, normal_only=True)

            cmp = self._compare_values(entry_val, comp_op, exit_val)
            status = self._status_from_cmp(cmp)
            if status == "warning" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | violation lower={fr.get('lower_violation')} upper={fr.get('upper_violation')} overlap={fr.get('overlap_zone')}"
            else:
                msg_tail = ""

            return {
                "status": status,
                "kind": "postEntryExit",
                "line": line_no,
                "details": {
                    "variable": self._pretty_expr(var_ref),
                    "entry_value": str(entry_val),
                    "exit_value": str(exit_val),
                    "operator": comp_op,
                    **cmp
                },
                "message": f'{self._pretty_expr(var_ref)}(Entry {comp_op} Exit) → {cmp["message"]}{msg_tail}',
            }
        except Exception as e:
            return self._err("postEntryExit", f"internal error: {e}", line_no)

    def verify_post_return_expression(self, *, comp_op: str, value_expr, line_no: int, fn_cfg):
        try:
            exit_node = self._get_post_exit_node(fn_cfg)
            ret_vals = list(exit_node.return_vals.values())

            if not ret_vals:
                return_val = None  # void
            else:
                # 값 조인은 list/tuple 가능성 있으니 얇은 어댑터 사용
                acc = ret_vals[0]
                for v in ret_vals[1:]:
                    acc = self._join_values(acc, v)
                return_val = self._materialize(acc)

            rhs_val = self._eval_on_exit_value(value_expr, fn_cfg, normal_only=True)

            cmp = self._compare_values(return_val, comp_op, rhs_val)
            status = self._status_from_cmp(cmp)
            if status == "warning" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | violation lower={fr.get('lower_violation')} upper={fr.get('upper_violation')} overlap={fr.get('overlap_zone')}"
            else:
                msg_tail = ""
            return {
                "status": status,
                "kind": "postRetExpr",
                "line": line_no,
                "details": {
                    "return_join": str(return_val),
                    "rhs_value": str(rhs_val),
                    "operator": comp_op,
                    **cmp
                },
                "message": f'returnExpression {comp_op} {self._pretty_expr(value_expr)} → {cmp["message"]}{msg_tail}',
            }
        except Exception as e:
            return self._err("postRetExpr", f"internal error: {e}", line_no)

    def verify_post_return_index(self, *, index: int, comp_op: str, value_expr, line_no: int, fn_cfg):
        """
        @Post return[idx] op value 검증
        함수 종료 시 tuple 반환값의 특정 인덱스 원소를 value와 비교
        """
        try:
            exit_node = self._get_post_exit_node(fn_cfg)
            ret_vals = list(exit_node.return_vals.values())

            if not ret_vals:
                return self._err("postRetIndex", "no return values", line_no)

            # 모든 return 값에서 인덱스 접근 후 조인
            indexed_vals = []
            for rv in ret_vals:
                if isinstance(rv, tuple):
                    if index < 0 or index >= len(rv):
                        return self._err("postRetIndex",
                                          f"index {index} out of range for tuple of length {len(rv)}", line_no)
                    indexed_vals.append(rv[index])
                else:
                    # 단일 반환값인 경우 인덱스 0만 허용
                    if index != 0:
                        return self._err("postRetIndex",
                                          f"return value is not a tuple, index {index} invalid", line_no)
                    indexed_vals.append(rv)

            # 값 조인
            acc = indexed_vals[0]
            for v in indexed_vals[1:]:
                acc = self._join_values(acc, v)
            indexed_val = self._materialize(acc)

            rhs_val = self._eval_on_exit_value(value_expr, fn_cfg, normal_only=True)

            cmp = self._compare_values(indexed_val, comp_op, rhs_val)
            status = self._status_from_cmp(cmp)
            if status == "warning" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | violation lower={fr.get('lower_violation')} upper={fr.get('upper_violation')} overlap={fr.get('overlap_zone')}"
            else:
                msg_tail = ""
            return {
                "status": status,
                "kind": "postRetIndex",
                "line": line_no,
                "details": {
                    "return_index": index,
                    "indexed_join": str(indexed_val),
                    "rhs_value": str(rhs_val),
                    "operator": comp_op,
                    **cmp
                },
                "message": f'return[{index}] {comp_op} {self._pretty_expr(value_expr)} → {cmp["message"]}{msg_tail}',
            }
        except Exception as e:
            return self._err("postRetIndex", f"internal error: {e}", line_no)

    def verify_post_return_variable(self, *, var_ref, comp_op: str, value_expr, line_no: int, fn_cfg):
        try:
            exit_node = self._get_post_exit_node(fn_cfg)
            comp_vals = []
            for rv in exit_node.return_vals.values():
                comp_vals.append(self._pick_from_return(rv, var_ref))

            if not comp_vals:
                ret_comp = None
            else:
                acc = comp_vals[0]
                for v in comp_vals[1:]:
                    acc = self._join_values(acc, v)
                ret_comp = self._materialize(acc)

            rhs_val = self._eval_on_exit_value(value_expr, fn_cfg, normal_only=True)

            cmp = self._compare_values(ret_comp, comp_op, rhs_val)
            status = self._status_from_cmp(cmp)
            if status == "warning" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | violation lower={fr.get('lower_violation')} upper={fr.get('upper_violation')} overlap={fr.get('overlap_zone')}"
            else:
                msg_tail = ""
            return {
                "status": status,
                "kind": "postRetVar",
                "line": line_no,
                "details": {
                    "variable": self._pretty_expr(var_ref),
                    "return_value": str(ret_comp),
                    "rhs_value": str(rhs_val),
                    "operator": comp_op,
                    **cmp
                },
                "message": f'return {self._pretty_expr(var_ref)} {comp_op} {self._pretty_expr(value_expr)} → {cmp["message"]}{msg_tail}',
            }
        except Exception as e:
            return self._err("postRetVar", f"internal error: {e}", line_no)

    def verify_post_direct_comparison(self, *, lhs_expr, comp_op: str, rhs_expr, line_no: int, fn_cfg):
        try:
            lhs_val = self._eval_on_exit_value(lhs_expr, fn_cfg, normal_only=True)
            rhs_val = self._eval_on_exit_value(rhs_expr, fn_cfg, normal_only=True)

            cmp = self._compare_values(lhs_val, comp_op, rhs_val)
            status = self._status_from_cmp(cmp)
            if status == "warning" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | violation lower={fr.get('lower_violation')} upper={fr.get('upper_violation')} overlap={fr.get('overlap_zone')}"
            else:
                msg_tail = ""
            return {
                "status": status,
                "kind": "postDirectCmp",
                "line": line_no,
                "details": {
                    "lhs_value": str(lhs_val),
                    "rhs_value": str(rhs_val),
                    "operator": comp_op,
                    **cmp
                },
                "message": f'{self._pretty_expr(lhs_expr)} {comp_op} {self._pretty_expr(rhs_expr)} → {cmp["message"]}{msg_tail}',
            }
        except Exception as e:
            return self._err("postDirectCmp", f"internal error: {e}", line_no)

    def verify_post_changed(self, *, var_ref, expect_changed: bool, line_no: int, fn_cfg):
        """
        @Post changed(x, true/false) 검증.
        Entry 값과 Exit 값을 비교하여 변경 여부 판정.
        expect_changed=True: 변경되었어야 함 (Entry != Exit → satisfied)
        expect_changed=False: 변경 안 되었어야 함 (Entry == Exit → satisfied)
        """
        try:
            entry_env = getattr(fn_cfg, "entry_env", fn_cfg.related_variables)
            entry_val = self._materialize(self.evaluate_guardian_expression(var_ref, entry_env, None, None))
            exit_val = self._eval_on_exit_value(var_ref, fn_cfg, normal_only=True)

            # Entry != Exit 판정
            cmp_neq = self._compare_values(entry_val, '!=', exit_val)
            cmp_eq = self._compare_values(entry_val, '==', exit_val)

            if expect_changed:
                # changed(x, true): Entry != Exit → satisfied
                cmp = cmp_neq
                label = "changed"
            else:
                # changed(x, false): Entry == Exit → satisfied
                cmp = cmp_eq
                label = "unchanged"

            status = self._status_from_cmp(cmp)
            if status == "warning" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | violation lower={fr.get('lower_violation')} upper={fr.get('upper_violation')} overlap={fr.get('overlap_zone')}"
            else:
                msg_tail = ""
            return {
                "status": status,
                "kind": "postChanged",
                "line": line_no,
                "details": {
                    "variable": self._pretty_expr(var_ref),
                    "entry_value": str(entry_val),
                    "exit_value": str(exit_val),
                    "expect_changed": expect_changed,
                    **cmp
                },
                "message": f'changed({self._pretty_expr(var_ref)}, {str(expect_changed).lower()}) → {label}: {cmp["message"]}{msg_tail}',
            }
        except Exception as e:
            return self._err("postChanged", f"internal error: {e}", line_no)

    def verify_during_changed(self, *, var_ref, expect_changed: bool, line_no: int, cfg_node, cur_vars=None):
        """
        @During changed(x, true/false) 검증.
        Entry 값(함수 진입 시)과 현재 값(이 program point)을 비교.
        expect_changed=True: 변경되었어야 함 (Entry != Current → satisfied)
        expect_changed=False: 변경 안 되었어야 함 (Entry == Current → satisfied)
        """
        try:
            fcfg = self.analyzer.current_target_function_cfg
            if fcfg is None:
                return self._err("duringChanged", "No active FunctionCFG", line_no)

            # Entry 값 (함수 진입 시 환경)
            entry_env = getattr(fcfg, "entry_env", fcfg.related_variables)
            entry_val = self._materialize(self.evaluate_guardian_expression(var_ref, entry_env, None, None))

            # Current 값 (현재 program point의 환경, cur_vars 우선)
            cur_env = cur_vars if cur_vars is not None else cfg_node.variables
            cur_val = self._materialize(self.evaluate_guardian_expression(var_ref, cur_env, None, None))

            if expect_changed:
                cmp = self._compare_values(entry_val, '!=', cur_val)
                label = "changed"
            else:
                cmp = self._compare_values(entry_val, '==', cur_val)
                label = "unchanged"

            status = self._status_from_cmp(cmp)
            return {
                "status": status,
                "kind": "duringChanged",
                "line": line_no,
                "details": {
                    "variable": self._pretty_expr(var_ref),
                    "entry_value": str(entry_val),
                    "current_value": str(cur_val),
                    "expect_changed": expect_changed,
                    **cmp
                },
                "message": f'changed({self._pretty_expr(var_ref)}, {str(expect_changed).lower()}) → {label}: {cmp["message"]}',
            }
        except Exception as e:
            return self._err("duringChanged", f"internal error: {e}", line_no)

    def verify_post_implication(self, *, antecedent: dict, consequent: dict, line_no: int, fn_cfg) -> dict:
        try:
            a_res = self._eval_post_predicate(antecedent, line_no=line_no, fn_cfg=fn_cfg)
            a_state = self._tri_state(a_res)

            if a_state == "violated":
                return {
                    "status": "success",
                    "kind": "postImplication",
                    "line": line_no,
                    "details": {"antecedent": a_res, "consequent": None, "logic": "vacuous-true"},
                    "message": "A ⇒ B holds vacuously (A is false)."
                }

            if a_state == "satisfied":
                b_res = self._eval_post_predicate(consequent, line_no=line_no, fn_cfg=fn_cfg)
                b_state = self._tri_state(b_res)
                status = self._status_from_state(b_state)
                return {
                    "status": status,
                    "kind": "postImplication",
                    "line": line_no,
                    "details": {"antecedent": a_res, "consequent": b_res},
                    "message": f"A ⇒ B with A=true → B is {b_state}."
                }

            return {
                "status": "warning",
                "kind": "postImplication",
                "line": line_no,
                "details": {"antecedent": a_res, "consequent": None},
                "message": "A ⇒ B warning (A is warning)."
            }

        except Exception as e:
            return self._err("postImplication", f"internal error: {e}", line_no)

    # ----------------------------------------------------------------
    # helper: uniform ok / error payloads
    # ----------------------------------------------------------------
    # ───────── require/assert feasible ─────────────────────────
    def verify_during_feasible(
            self, *, target: str, line_no: int, cfg_node, cur_vars
    ) -> dict[str, Any]:
        """
        @During require feasible / assert feasible 검증.
        다음 라인의 require/assert 조건식을 evaluate하여
        항상 false([0,0])이면 violated (절대 통과 불가).
        """
        try:
            # ① 현재 노드 또는 successor에서 require/assert condition 노드 찾기
            condition_expr = None
            fcfg = self.analyzer.current_target_function_cfg

            if fcfg is None:
                return self._err("duringFeasible",
                    "No active FunctionCFG", line_no)

            # CFG에서 require/assert condition 노드 탐색
            for node in fcfg.graph.nodes:
                if (getattr(node, "condition_node", False) and
                    getattr(node, "condition_node_type", "") == target and
                    getattr(node, "src_line", None) is not None and
                    node.src_line >= line_no):
                    condition_expr = getattr(node, "condition_expr", None)
                    break

            if condition_expr is None:
                return self._err("duringFeasible",
                    f"'{target}' statement를 찾을 수 없음 (line {line_no} 이후)", line_no)

            # ② 조건식 evaluate → BoolInterval
            cond_val = self.analyzer.evaluator.evaluate_expression(
                condition_expr, cur_vars, None, None)

            # BoolInterval이 아닌 경우 변환 시도
            if not isinstance(cond_val, BoolInterval):
                if VariableEnv.is_interval(cond_val):
                    cond_val = VariableEnv.convert_int_to_bool_interval(cond_val)
                else:
                    return self._err("duringFeasible",
                        f"조건식 평가 결과가 boolean이 아님: {cond_val}", line_no)

            # ③ feasibility 판정
            if cond_val.max_value == 0:
                # [0,0] → 항상 false → 절대 통과 불가 → violated
                status = "violated"
                message = f"{target} condition is always false — never passable"
            elif cond_val.min_value == 1:
                # [1,1] → 항상 true → 항상 통과 → satisfied
                status = "satisfied"
                message = f"{target} condition is always true"
            else:
                # [0,1] → 통과 가능 → satisfied
                status = "satisfied"
                message = f"{target} condition is feasible (can be true or false)"

            return {
                "status": status,
                "kind": "duringFeasible",
                "line": line_no,
                "details": {
                    "target": target,
                    "condition_value": str(cond_val),
                },
                "message": message,
            }

        except Exception as e:
            return self._err("duringFeasible", f"internal error: {e}", line_no)

    def _err(self, kind: str, msg: str, ln: int) -> dict[str, Any]:
        return {"status": "error", "kind": kind, "line": ln, "message": msg}

    def _pretty_expr(self, expr: Expression) -> str:
        """very small utility – turn Expression into a readable string"""
        return getattr(expr, "identifier", "") or str(expr)

    # ----------------------------------------------------------------
    # Risk type / Risk score 계산
    # ----------------------------------------------------------------
    def _compute_risk_type(self, state: str, false_regions: dict, op: str) -> int:
        """
        위험도 타입 판별:
          1 = satisfied (위반 경로 없음, spec 느슨할 수 있음)
          2 = 한쪽 방향만 위반
          3 = 양쪽 방향 위반 (in operator 등)
        violated 상태는 violation_ratio=1.0 과 결합하여 최대 점수가 됨.
        """
        if state == "satisfied":
            return 1
        if state == "violated":
            # violated는 타입 자체는 false_regions로 판별
            # violated이면서 양방향이면 3, 아니면 2
            pass

        # warning 또는 violated: false_regions 기반 판별
        lower = false_regions.get("lower_violation") if false_regions else None
        upper = false_regions.get("upper_violation") if false_regions else None

        has_lower = lower is not None
        has_upper = upper is not None

        # == / != 는 interval 기반 분석과 본질적으로 궁합이 안 맞으므로
        # warning이면 타입 3 (높은 위험도) 부여
        if op in {"==", "!="}:
            return 3 if state != "satisfied" else 1

        if has_lower and has_upper:
            return 3
        elif has_lower or has_upper:
            return 2
        else:
            # false_regions 계산 실패 등 → overlap_zone만 있으면 타입 2
            overlap = false_regions.get("overlap_zone") if false_regions else None
            return 2 if overlap is not None else 1

    def _compute_risk_score(self, state: str, prob_true: float,
                            false_regions: dict, op: str) -> float:
        """
        0-10 스케일 위험도 점수 계산.
          satisfied → 0.0 (고정)
          violated  → 10.0 (고정)
          warning:
            타입 1 (한쪽 경미)  → 0.1 ~ 3.3
            타입 2 (한쪽 위반)  → 3.4 ~ 6.6
            타입 3 (양쪽 위반)  → 6.7 ~ 9.9
        """
        if state == "satisfied":
            return 0.0
        if state == "violated":
            return 10.0

        # warning 전용: risk_type으로 구간 결정
        risk_type = self._compute_risk_type(state, false_regions, op)
        violation_ratio = 1.0 - prob_true  # 위반 비율

        # 타입별 구간
        if risk_type == 1:
            base, span = 0.1, 3.2   # 0.1 ~ 3.3
        elif risk_type == 2:
            base, span = 3.4, 3.2   # 3.4 ~ 6.6
        else:
            base, span = 6.7, 3.2   # 6.7 ~ 9.9

        score = base + violation_ratio * span
        return round(min(9.9, max(0.1, score)), 1)

    # ----------------------------------------------------------------
    # Interval-aware comparison with probability
    # ----------------------------------------------------------------
    def _compare_intervals_prob(self, left_iv, right_iv, op: str) -> dict:
        """
        두 Interval 사이의 관계를
          - 'satisfied' : 반드시 성립
          - 'violated'  : 절대 성립 불가
          - 'warning'   : 일부 구간만 성립
        로 판정하고, warning 인 경우에는
          prob_true ∈ (0,1)  ≒  '성립할 확률' 값을 계산한다.
        """

        def _enrich(info):
            """모든 반환 경로에 risk_type, risk_score를 추가"""
            fr = info.get("false_regions", {})
            info["risk_type"] = self._compute_risk_type(info["state"], fr, op)
            info["risk_score"] = self._compute_risk_score(
                info["state"], info["prob_true"], fr, op)
            return info

        # ① min/max 가 None → 정보 부족 → 완전 불확정
        if (left_iv.min_value is None or left_iv.max_value is None or
                right_iv.min_value is None or right_iv.max_value is None):
            return _enrich({"state": "warning", "prob_true": 0.5})

        # ② Interval 폭
        lw, rw = left_iv.max_value - left_iv.min_value, right_iv.max_value - right_iv.min_value

        # ── 정수 구간 카운팅 (모든 연산자 공통) ──
        int_total = lw + 1  # L 구간의 정수 개수

        # ─── 포함(in) / 비포함(not in) ────────────────────────────
        if op in {"in", "not in"}:
            # left ⊆ right ?   (구간 포함 여부)
            left_inside = (left_iv.min_value >= right_iv.min_value and
                           left_iv.max_value <= right_iv.max_value)
            if left_inside:
                return _enrich({"state": "satisfied" if op == "in" else "violated",
                                "prob_true": 1.0 if op == "in" else 0.0})
            # 완전히 분리 → 'in' 은 false 확정,  'not in' 은 true 확정
            separated = (left_iv.max_value < right_iv.min_value or
                         left_iv.min_value > right_iv.max_value)
            if separated:
                return _enrich({"state": "violated" if op == "in" else "satisfied",
                                "prob_true": 0.0 if op == "in" else 1.0})
            # 부분-겹침 → 정수 카운팅으로 겹치는 비율 계산
            overlap_count = max(0, min(left_iv.max_value, right_iv.max_value)
                                - max(left_iv.min_value, right_iv.min_value) + 1)
            conf = (1 - overlap_count / int_total) if op == "not in" else (overlap_count / int_total)
            info = {"state": "warning", "prob_true": round(conf, 3)}
            try:
                info["false_regions"] = self._false_regions_for_op(left_iv, right_iv, op)
            except Exception:
                info["false_regions"] = {"lower_violation": None, "upper_violation": None,
                                         "overlap_zone": None, "notes": "failed to compute"}
            return _enrich(info)

        if op == '>':
            # L > R: L.min > R.max → satisfied, L.max <= R.min → violated
            if left_iv.min_value > right_iv.max_value:
                return _enrich({"state": "satisfied", "prob_true": 1.0})
            if left_iv.max_value <= right_iv.min_value:
                return _enrich({"state": "violated", "prob_true": 0.0})
            # 확실히 true: L > R.max  →  L ∈ {R.max+1 .. L.max}
            true_len = max(0, left_iv.max_value - right_iv.max_value)
            # 확실히 false: L ≤ R.min  →  L ∈ {L.min .. R.min}
            false_len = max(0, right_iv.min_value - left_iv.min_value + 1)
            total = int_total
        elif op == '<':
            # L < R: L.max < R.min → satisfied, L.min >= R.max → violated
            if left_iv.max_value < right_iv.min_value:
                return _enrich({"state": "satisfied", "prob_true": 1.0})
            if left_iv.min_value >= right_iv.max_value:
                return _enrich({"state": "violated", "prob_true": 0.0})
            # 확실히 true: L < R.min  →  L ∈ {L.min .. R.min-1}
            true_len = max(0, right_iv.min_value - left_iv.min_value)
            # 확실히 false: L ≥ R.max  →  L ∈ {R.max .. L.max}
            false_len = max(0, left_iv.max_value - right_iv.max_value + 1)
            total = int_total
        elif op == '>=':
            # L >= R: L.min >= R.max → satisfied, L.max < R.min → violated
            if left_iv.min_value >= right_iv.max_value:
                return _enrich({"state": "satisfied", "prob_true": 1.0})
            if left_iv.max_value < right_iv.min_value:
                return _enrich({"state": "violated", "prob_true": 0.0})
            true_len = max(0, left_iv.max_value - right_iv.max_value + 1)
            false_len = max(0, right_iv.min_value - left_iv.min_value)
            total = int_total
        elif op == '<=':
            # L <= R: L.max <= R.min → satisfied, L.min > R.max → violated
            if left_iv.max_value <= right_iv.min_value:
                return _enrich({"state": "satisfied", "prob_true": 1.0})
            if left_iv.min_value > right_iv.max_value:
                return _enrich({"state": "violated", "prob_true": 0.0})
            true_len = max(0, right_iv.min_value - left_iv.min_value + 1)
            false_len = max(0, left_iv.max_value - right_iv.max_value)
            total = int_total
        elif op == '==':
            # disjoint → violated, both singletons & equal → satisfied
            if left_iv.max_value < right_iv.min_value or left_iv.min_value > right_iv.max_value:
                return _enrich({"state": "violated", "prob_true": 0.0})
            if lw == 0 and rw == 0 and left_iv.min_value == right_iv.min_value:
                return _enrich({"state": "satisfied", "prob_true": 1.0})
            # 겹치는 정수 개수를 "true", 나머지를 "false"
            overlap_count = max(0, min(left_iv.max_value, right_iv.max_value)
                                - max(left_iv.min_value, right_iv.min_value) + 1)
            true_len = overlap_count
            false_len = int_total - true_len
            total = int_total
        elif op == '!=':
            # disjoint → satisfied, both singletons & equal → violated
            if left_iv.max_value < right_iv.min_value or left_iv.min_value > right_iv.max_value:
                return _enrich({"state": "satisfied", "prob_true": 1.0})
            if lw == 0 and rw == 0 and left_iv.min_value == right_iv.min_value:
                return _enrich({"state": "violated", "prob_true": 0.0})
            overlap_count = max(0, min(left_iv.max_value, right_iv.max_value)
                                - max(left_iv.min_value, right_iv.min_value) + 1)
            true_len = int_total - overlap_count
            false_len = overlap_count
            total = int_total
        else:
            raise ValueError(f"unsupported op {op}")

        # ④ 결과 state / prob_true ----------------------------------
        uncertain = int_total - true_len - false_len
        if false_len == 0 and uncertain == 0 and not (op in ('==', '!=') and rw > 0):
            return _enrich({"state": "satisfied", "prob_true": 1.0})
        if true_len == 0 and uncertain == 0 and not (op in ('==', '!=') and rw > 0):
            return _enrich({"state": "violated", "prob_true": 0.0})

        # 불확정 구간의 기대 true 개수 (R이 범위일 때, 균등분포 가정)
        unc_true = 0
        if uncertain > 0 and rw > 0 and op in {'>', '<', '>=', '<='}:
            r_count = rw + 1  # R 정수 개수
            if op in ('>', '<='):
                unc_lo = max(left_iv.min_value, right_iv.min_value + 1)
                unc_hi = min(left_iv.max_value, right_iv.max_value)
            else:  # >= 또는 <
                unc_lo = max(left_iv.min_value, right_iv.min_value)
                unc_hi = min(left_iv.max_value, right_iv.max_value - 1)
            n = max(0, unc_hi - unc_lo + 1)
            if n > 0:
                if op == '>':
                    a = unc_lo - right_iv.min_value
                    b = unc_hi - right_iv.min_value
                elif op == '>=':
                    a = unc_lo - right_iv.min_value + 1
                    b = unc_hi - right_iv.min_value + 1
                elif op == '<':
                    a = right_iv.max_value - unc_hi
                    b = right_iv.max_value - unc_lo
                else:  # <=
                    a = right_iv.max_value - unc_hi + 1
                    b = right_iv.max_value - unc_lo + 1
                unc_true = (a + b) * n / 2 / r_count

        if op == '==':
            # overlap 값은 "확실히 true"가 아니라 1/(rw+1) 확률로 true
            conf = true_len / (total * (rw + 1))
        elif op == '!=':
            # overlap 값은 "확실히 false"가 아니라 1/(rw+1) 확률로 false
            conf = 1 - false_len / (total * (rw + 1))
        else:
            conf = (true_len + unc_true) / total
        info = {"state": "warning", "prob_true": round(conf, 3)}

        try:
            info["false_regions"] = self._false_regions_for_op(left_iv, right_iv, op)
        except Exception:
            info["false_regions"] = {"lower_violation": None, "upper_violation": None,
                                     "overlap_zone": None, "notes": "failed to compute"}

        return _enrich(info)

    def _compare_values(self, left, op: str, right) -> dict:
        # ───────── Interval ↔ Interval (기존) ─────────
        if hasattr(left, "min_value") and hasattr(right, "min_value"):
            info = self._compare_intervals_prob(left, right, op)
            out = {
                "satisfied": info["state"] == "satisfied",
                "violated": info["state"] == "violated",
                "warning": info["state"] == "warning",
                "prob_true": info["prob_true"],
                "risk_score": info.get("risk_score", 0.0),
                "risk_type": info.get("risk_type", 1),
                "message": f"{info['state']} (risk={info.get('risk_score', 0.0)})"
            }
            if "false_regions" in info:
                out["false_regions"] = info["false_regions"]
            return out

        # ───────── 스칼라 ↔ Interval (주로 in / not in) ─────────
        if not hasattr(left, "min_value") and hasattr(right, "min_value"):
            if op in {"in", "not in"}:
                if right.min_value is None or right.max_value is None:
                    return {"satisfied": False, "violated": True,
                            "warning": True, "prob_true": 0.0,
                            "risk_score": 10.0, "risk_type": 2,
                            "message": "interval unknown"}
                inside = right.min_value <= left <= right.max_value
                satisfied = inside if op == "in" else not inside
                return {
                    "satisfied": satisfied,
                    "violated": not satisfied,
                    "warning": False,
                    "prob_true": 1.0,
                    "risk_score": 0.0 if satisfied else 10.0,
                    "risk_type": 1 if satisfied else 2,
                    "message": f"{left} {op} [{right.min_value},{right.max_value}] = {satisfied}"
                }

        # ───────── 스칼라 ↔ 스칼라 (기존 + in/not in 방어) ─────────
        try:
            tbl = {
                '<': lambda a, b: a < b,
                '>': lambda a, b: a > b,
                '<=': lambda a, b: a <= b,
                '>=': lambda a, b: a >= b,
                '==': lambda a, b: a == b,
                '!=': lambda a, b: a != b,
            }
            if op in tbl:
                satisfied = tbl[op](left, right)
            elif op == "in":
                satisfied = left == right  # 스칼라끼리 in 은 동일성으로 취급
            elif op == "not in":
                satisfied = left != right
            else:
                raise ValueError(f"unsupported op {op}")

            return {
                "satisfied": satisfied,
                "violated": not satisfied,
                "warning": False,
                "prob_true": 1.0,
                "risk_score": 0.0 if satisfied else 10.0,
                "risk_type": 1 if satisfied else 2,
                "message": f"{left} {op} {right} = {satisfied}"
            }
        except Exception as e:
            return {"satisfied": False, "violated": True,
                    "warning": True, "prob_true": 0.0,
                    "risk_score": 10.0, "risk_type": 2,
                    "message": f"comparison error: {e}"}

    def _expr_to_str(self, e):  # 간단 문자열 직렬화 helper
        if getattr(e, "identifier", None):
            return e.identifier
        if getattr(e, "member", None):
            return f"{self._expr_to_str(e.base)}.{e.member}"
        if getattr(e, "index", None):
            idx = getattr(e.index, "literal", "?")
            return f"{self._expr_to_str(e.base)}[{idx}]"
        return str(e)

    def _pick_from_return(self, ret_v, var_ref):
        """
        ret_v :  한 줄의 return 값 (Interval, list, tuple …)
        var_ref.context:
            • "ReturnTupleBase"        → 전체 반환
            • "ReturnElemRef"          → return[i]
        """
        # 전체 tuple 그대로
        if var_ref.context == "ReturnTupleBase":
            return ret_v

        # return[ idx ]  ── element 추출
        if var_ref.context == "ReturnElemRef":
            idx = int(var_ref.index.literal, 0)
            if isinstance(ret_v, (list, tuple)) and idx < len(ret_v):
                return ret_v[idx]
            return None
        # 기타 경우는 evaluator 로 해결하도록 위임
        return ret_v

    def _join_values(self, a, b):
        """
        Helper의 _merge_values를 최대한 재사용.
        단, list/tuple/dict 은 Helper가 모르므로 여기서만 얇게 감싸서 원소별 join.
        """
        if a is None: return b
        if b is None: return a

        # list/tuple → 원소별 재귀
        if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            if len(a) != len(b):
                return "⊤"
            return type(a)(self._join_values(x, y) for x, y in zip(a, b))

        # dict → key union 후 값별 재귀
        if isinstance(a, dict) and isinstance(b, dict):
            keys = set(a) | set(b)
            return {k: self._join_values(a.get(k), b.get(k)) for k in keys}

        # 나머지는 Helper에게 위임(Interval/Variables/Struct/Array/Mapping 등)
        try:
            return VariableEnv._merge_values(a, b, "join")
        except Exception:
            # 서로 다른 Interval형 조합 등에서 join이 예외를 던질 수 있음 → 보수적 ⊤
            return "⊤"

    def _materialize(self, v):
        """
        Variables/Struct/Array/Mapping → 값 뷰로 평탄화
        Interval/스칼라 → 그대로
        """
        if v is None:
            return None
        if hasattr(v, "elements") and isinstance(getattr(v, "elements"), list):  # ArrayVariable
            return [self._materialize(getattr(e, "value", e)) for e in v.elements]
        if hasattr(v, "members") and isinstance(getattr(v, "members"), dict):  # StructVariable
            return {k: self._materialize(getattr(m, "value", m)) for k, m in v.members.items()}
        if hasattr(v, "mapping") and isinstance(getattr(v, "mapping"), dict):  # MappingVariable
            return {k: self._materialize(getattr(m, "value", m)) for k, m in v.mapping.items()}
        if hasattr(v, "value") and not (hasattr(v, "elements") or hasattr(v, "members") or hasattr(v, "mapping")):
            return self._materialize(v.value)
        if isinstance(v, (list, tuple)):
            return type(v)(self._materialize(x) for x in v)
        return v

    # GuardianVerificationEngine.py  ─ GuardianVerificationEngine 클래스 내부

    def _get_post_exit_node(self, fn_cfg):
        """
        Post 검증용 exit 노드 선택:
        - return이 있는 함수 → return_exit_node
        - return이 없는 함수 → exit_node
        """
        return_exit = fn_cfg.get_return_exit_node()
        if return_exit.return_vals:
            return return_exit
        else:
            return fn_cfg.get_exit_node()

    def _preds(self, fn_cfg, *, normal_only: bool = True):
        """
        EXIT의 predecessor 중 정상 경로만 뽑아옴.
        (빌더에서 revert/require/assert(false) 엣지에 edge['abnormal']=True 를 붙였다고 가정)
        """
        G = fn_cfg.graph
        exit_n = fn_cfg.get_exit_node()
        out = []
        for p in G.predecessors(exit_n):
            ed = G.get_edge_data(p, exit_n, default={})
            if normal_only and ed.get("abnormal"):
                continue
            out.append(p)
        return out

    def _exit_env(self, fn_cfg, *, normal_only: bool = True) -> dict:
        """
        EXIT 직전의 '변수 환경'을 Helper의 join으로 하나로 만든다.
        ⇒ 이후 expr은 이 env로 한 번만 평가하면 됨.
        """
        preds = self._preds(fn_cfg, normal_only=normal_only)
        if not preds:
            return VariableEnv.copy_variables(getattr(fn_cfg, "related_variables", {}))

        env = VariableEnv.copy_variables(preds[0].variables)
        for p in preds[1:]:
            env = VariableEnv.join_variables_simple(env, p.variables)
        return env

    def _eval_on_exit_value(self, expr, fn_cfg, *, normal_only: bool = True):
        """
        pred별로 평가해서 값을 join 하지 말고,
        pred들의 env를 Helper join으로 합친 다음 expr을 '한 번'만 평가.
        """
        exit_env = self._exit_env(fn_cfg, normal_only=normal_only)
        val = self.evaluate_guardian_expression(expr, exit_env, None, None)
        return self._materialize(val)

    # DURING predicate evaluator
    def _eval_during_predicate(self, pred: dict, *, line_no: int, cfg_node: CFGNode) -> dict:
        k = pred["kind"]
        if k == "beforeAfter":
            return self.verify_during_before_after(var_ref=pred["var"], comp_op=pred["op"], line_no=line_no,
                                                   cfg_node=cfg_node)
        if k == "assignCurrent":
            return self.verify_during_assign_current(var_ref=pred["var"], comp_op=pred["op"], line_no=line_no,
                                                     cfg_node=cfg_node)
        if k == "retExpr":
            return self.verify_during_return_expression(comp_op=pred["op"], value_expr=pred["rhs"], line_no=line_no,
                                                        cfg_node=cfg_node)
        if k == "retVar":
            return self.verify_during_return_variable(var_ref=pred["lhs"], comp_op=pred["op"], value_expr=pred["rhs"],
                                                      line_no=line_no, cfg_node=cfg_node)
        if k == "direct":
            return self.verify_during_direct_comparison(lhs_expr=pred["lhs"], comp_op=pred["op"], rhs_expr=pred["rhs"],
                                                        line_no=line_no, cfg_node=cfg_node)
        if k == "nonzero":
            return self._eval_nonzero(pred["expr"], cfg_node.variables, line_no)
        return self._err("duringPredicate", f"unknown DURING predicate kind: {k}", line_no)

    # POST predicate evaluator
    def _eval_post_predicate(self, pred: dict, *, line_no: int, fn_cfg) -> dict:
        k = pred["kind"]
        if k == "entryExit":
            return self.verify_post_entry_exit(var_ref=pred["var"], comp_op=pred["op"], line_no=line_no, fn_cfg=fn_cfg)
        if k == "changed":
            return self.verify_post_changed(var_ref=pred["var"], expect_changed=pred["expect_changed"], line_no=line_no, fn_cfg=fn_cfg)
        if k == "retExpr":
            return self.verify_post_return_expression(comp_op=pred["op"], value_expr=pred["rhs"], line_no=line_no,
                                                      fn_cfg=fn_cfg)
        if k == "retVar":
            return self.verify_post_return_variable(var_ref=pred["lhs"], comp_op=pred["op"], value_expr=pred["rhs"],
                                                    line_no=line_no, fn_cfg=fn_cfg)
        if k == "direct":
            return self.verify_post_direct_comparison(lhs_expr=pred["lhs"], comp_op=pred["op"], rhs_expr=pred["rhs"],
                                                      line_no=line_no, fn_cfg=fn_cfg)
        if k == "nonzero":
            exit_env = self._exit_env(fn_cfg)
            return self._eval_nonzero(pred["expr"], exit_env, line_no)
        return self._err("postPredicate", f"unknown POST predicate kind: {k}", line_no)

    def _eval_nonzero(self, expr, vars_env, line_no: int) -> dict:
        """intentValue를 평가하여 nonzero 여부 판정."""
        val = self.evaluate_guardian_expression(expr, vars_env, None, None)
        val = self._materialize(val)

        if hasattr(val, "min_value") and hasattr(val, "max_value"):
            lo, hi = val.min_value, val.max_value
            if lo > 0 or hi < 0:
                satisfied, violated = True, False
            elif lo == 0 and hi == 0:
                satisfied, violated = False, True
            else:
                satisfied, violated = False, False
        elif isinstance(val, bool):
            satisfied, violated = val, not val
        else:
            satisfied, violated = False, False

        if satisfied:
            status = "success"
        elif violated:
            status = "failure"
        else:
            status = "warning"

        return {
            "status": status,
            "kind": "nonzero",
            "line": line_no,
            "details": {"satisfied": satisfied, "violated": violated, "value": str(val)},
            "message": f"{self._pretty_expr(expr)} is {'nonzero' if satisfied else 'zero' if violated else 'possibly zero'} ({val})"
        }

    def _tri_state(self, res: dict) -> str:
        """
        result → 'satisfied' / 'violated' / 'warning'
        (기존 verify_*들의 details에 들어있는 cmp 필드 기반)
        """
        d = res.get("details", {})
        if d.get("satisfied"):
            return "satisfied"
        if d.get("violated"):
            return "violated"
        if d.get("warning"):
            return "warning"
        # fallback: status
        st = res.get("status")
        if st == "success":    return "satisfied"
        if st == "violation":  return "violated"
        return "warning"

    def _status_from_state(self, st: str) -> str:
        return "success" if st == "satisfied" else ("violation" if st == "violated" else "warning")

    # GuardianVerificationEngine 내부에 추가

    def _status_from_cmp(self, cmp: dict) -> str:
        if cmp.get("satisfied"): return "success"
        if cmp.get("violated"):  return "violation"
        if cmp.get("warning"):   return "warning"
        return "warning"

    def _prob_true_from_cmp(self, cmp: dict) -> float:
        # prob_true = 조건이 참일 확률 (0~1)
        if cmp.get("satisfied"): return 1.0
        if cmp.get("violated"):  return 0.0
        return float(cmp.get("prob_true", 0.5))

    def _prob_true_from_result(self, res: dict) -> float:
        # verify_* 결과에서 details에 펼쳐 넣은 cmp를 그대로 사용
        d = res.get("details", {})
        if d.get("satisfied"): return 1.0
        if d.get("violated"):  return 0.0
        if "prob_true" in d:  return float(d["prob_true"])
        # 비교 에러/정보부족 등
        return 0.5

    # GuardianVerificationEngine 내부에 추가

    def _mk_interval(self, lo, hi):
        """정수 구간 [lo,hi] (inclusive). lo>hi면 None."""
        if lo is None or hi is None:
            return None
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return None
        return [lo, hi]

    def _intersect(self, a, b):
        """a,b = [lo,hi]. 교집합 반환 또는 None."""
        if a is None or b is None:
            return None
        return self._mk_interval(max(a[0], b[0]), min(a[1], b[1]))

    def _minus(self, a, b):
        """정수 구간 차집합: a\b → 구간 리스트"""
        if a is None:
            return []
        inter = self._intersect(a, b)
        if inter is None:
            return [a]
        out = []
        if a[0] < inter[0]:
            out.append([a[0], inter[0] - 1])
        if inter[1] < a[1]:
            out.append([inter[1] + 1, a[1]])
        return out

    def _false_regions_for_op(self, L, R, op: str) -> dict:
        """
        L,R: Interval-like (min_value, max_value).
        warning일 때 '거짓이 될 수 있는' 후보 구간을 방향별로 분리해서 리턴.
        반환 예:
          { "lower_violation": [lo, hi] or None,   # intent 하한 아래로 벗어난 구간
            "upper_violation": [lo, hi] or None,   # intent 상한 위로 벗어난 구간
            "overlap_zone":    [lo, hi] or None,   # 겹치는 불확정 구간
            "notes": "inclusive integer intervals" }
        """
        empty = {"lower_violation": None, "upper_violation": None,
                 "overlap_zone": None, "notes": "unknown bounds"}

        if (getattr(L, "min_value", None) is None or getattr(L, "max_value", None) is None or
                getattr(R, "min_value", None) is None or getattr(R, "max_value", None) is None):
            return empty

        a = [int(L.min_value), int(L.max_value)]
        b = [int(R.min_value), int(R.max_value)]
        lower = None   # actual이 intent 하한 아래로 벗어남
        upper = None   # actual이 intent 상한 위로 벗어남
        overlap = None # 겹치는 불확정 구간

        if op == '>':
            # L > R 가 거짓인 구간: L이 R 이하인 부분
            # lower: L의 하단이 R.min 이하 → 확실히 거짓
            # overlap: L과 R이 겹치는 구간 → 불확정
            if a[0] <= b[0]:
                lower = self._mk_interval(a[0], min(a[1], b[0]))
            overlap = self._mk_interval(max(a[0], b[0] + 1), min(a[1], b[1]))

        elif op == '<':
            # L < R 가 거짓인 구간: L이 R 이상인 부분
            # upper: L의 상단이 R.max 이상 → 확실히 거짓
            # overlap: L과 R이 겹치는 구간 → 불확정
            if a[1] >= b[1]:
                upper = self._mk_interval(max(a[0], b[1]), a[1])
            overlap = self._mk_interval(max(a[0], b[0]), min(a[1], b[1] - 1))

        elif op == '>=':
            # L >= R 가 거짓인 구간: L < R 인 부분
            if a[0] < b[0]:
                lower = self._mk_interval(a[0], min(a[1], b[0] - 1))
            overlap = self._mk_interval(max(a[0], b[0]), min(a[1], b[1]))

        elif op == '<=':
            # L <= R 가 거짓인 구간: L > R 인 부분
            if a[1] > b[1]:
                upper = self._mk_interval(max(a[0], b[1] + 1), a[1])
            overlap = self._mk_interval(max(a[0], b[0]), min(a[1], b[1]))

        elif op == '==':
            # 거짓은 '겹침 밖' 영역
            inter = self._intersect(a, b)
            if inter:
                if a[0] < inter[0]:
                    lower = self._mk_interval(a[0], inter[0] - 1)
                if a[1] > inter[1]:
                    upper = self._mk_interval(inter[1] + 1, a[1])
                overlap = inter  # 겹치는 구간 (같을 수 있는 유일한 구간)
            else:
                # 완전 분리 → 전체가 violation
                if a[1] < b[0]:
                    lower = a
                else:
                    upper = a

        elif op == '!=':
            # 거짓은 '같을 수 있는' 영역 = 겹치는 부분
            inter = self._intersect(a, b)
            overlap = inter  # 겹치는 구간이 false-support

        elif op == 'in':
            # L ⊆ R 가 거짓인 구간: L이 R 밖으로 벗어나는 부분
            if a[0] < b[0]:
                lower = self._mk_interval(a[0], min(a[1], b[0] - 1))
            if a[1] > b[1]:
                upper = self._mk_interval(max(a[0], b[1] + 1), a[1])

        elif op == 'not in':
            # L ⊄ R 가 거짓인 구간: L이 R 안에 들어가는 부분
            inter = self._intersect(a, b)
            overlap = inter  # R 안에 들어가는 부분이 위험

        return {"lower_violation": lower, "upper_violation": upper,
                "overlap_zone": overlap, "notes": "inclusive integer intervals"}


