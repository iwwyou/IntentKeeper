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
from Domain.Interval import IntegerInterval, UnsignedIntegerInterval
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
            # ── 1) “현재 함수” CFG -------------------------------
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

            if status == "unknown" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | false-candidates L={fr['left']} R={fr['right']}"
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

            if status == "unknown" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | false-candidates L={fr['left']} R={fr['right']}"
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

            # ① “해당‧또는 가장 가까운 이전” return-값 가져오기 -------------
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

            if status == "unknown" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | false-candidates L={fr['left']} R={fr['right']}"
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

            if status == "unknown" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | false-candidates L={fr['left']} R={fr['right']}"
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
                    **cmp  # satisfied / violated / uncertain / confidence
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

            # A unknown
            return {
                "status": "unknown",
                "kind": "duringImplication",
                "line": line_no,
                "details": {"antecedent": a_res, "consequent": None},
                "message": "A ⇒ B unknown (A is uncertain)."
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

            if status == "unknown" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | false-candidates L={fr['left']} R={fr['right']}"
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
            entry_env = getattr(fn_cfg, "entry_env", fn_cfg.related_variables)
            entry_val = self._materialize(self.evaluate_guardian_expression(var_ref, entry_env, None, None))

            exit_val = self._eval_on_exit_value(var_ref, fn_cfg, normal_only=True)

            cmp = self._compare_values(entry_val, comp_op, exit_val)
            status = self._status_from_cmp(cmp)
            if status == "unknown" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | false-candidates L={fr['left']} R={fr['right']}"
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
            if status == "unknown" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | false-candidates L={fr['left']} R={fr['right']}"
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
            if status == "unknown" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | false-candidates L={fr['left']} R={fr['right']}"
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
            if status == "unknown" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | false-candidates L={fr['left']} R={fr['right']}"
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
            if status == "unknown" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | false-candidates L={fr['left']} R={fr['right']}"
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

    def verify_post_unchanged(self, *, var_ref, line_no: int, fn_cfg):
        try:
            entry_env = getattr(fn_cfg, "entry_env", fn_cfg.related_variables)
            entry_val = self._materialize(self.evaluate_guardian_expression(var_ref, entry_env, None, None))

            exit_val = self._eval_on_exit_value(var_ref, fn_cfg, normal_only=True)

            cmp = self._compare_values(entry_val, '==', exit_val)
            status = self._status_from_cmp(cmp)
            if status == "unknown" and "false_regions" in cmp:
                fr = cmp["false_regions"]
                msg_tail = f" | false-candidates L={fr['left']} R={fr['right']}"
            else:
                msg_tail = ""
            return {
                "status": status,
                "kind": "postUnchanged",
                "line": line_no,
                "details": {
                    "variable": self._pretty_expr(var_ref),
                    "entry_value": str(entry_val),
                    "exit_value": str(exit_val),
                    **cmp
                },
                "message": f'Unchanged({self._pretty_expr(var_ref)}) → {cmp["message"]}{msg_tail}',
            }
        except Exception as e:
            return self._err("postUnchanged", f"internal error: {e}", line_no)

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
                "status": "unknown",
                "kind": "postImplication",
                "line": line_no,
                "details": {"antecedent": a_res, "consequent": None},
                "message": "A ⇒ B unknown (A is uncertain)."
            }

        except Exception as e:
            return self._err("postImplication", f"internal error: {e}", line_no)

    # ----------------------------------------------------------------
    # helper: uniform ok / error payloads
    # ----------------------------------------------------------------
    def _err(self, kind: str, msg: str, ln: int) -> dict[str, Any]:
        return {"status": "error", "kind": kind, "line": ln, "message": msg}

    def _pretty_expr(self, expr: Expression) -> str:
        """very small utility – turn Expression into a readable string"""
        return getattr(expr, "identifier", "") or str(expr)

    # ----------------------------------------------------------------
    # Interval-aware comparison with probability
    # ----------------------------------------------------------------
    def _compare_intervals_prob(self, left_iv, right_iv, op: str) -> dict:
        """
        두 Interval 사이의 관계를
          - 'satisfied' : 반드시 성립
          - 'violated'  : 절대 성립 불가
          - 'uncertain' : 일부 구간만 성립
        로 판정하고, uncertain 인 경우에는
          confidence ∈ (0,1)  ≒  '성립할 확률' 값을 계산한다.
        """

        # ③ op 별 true-zone, false-zone 계산 --------------------------
        def _overlap(a1, a2, b1, b2):
            """두 구간 [a1,a2], [b1,b2] 의 겹치는 길이"""
            return max(0, min(a2, b2) - max(a1, b1))

        # ① min/max 가 None → 정보 부족 → 완전 불확정
        if (left_iv.min_value is None or left_iv.max_value is None or
                right_iv.min_value is None or right_iv.max_value is None):
            return {"state": "uncertain", "confidence": 0.5}

        # ② Interval 폭
        lw, rw = left_iv.max_value - left_iv.min_value, right_iv.max_value - right_iv.min_value

        # ─── 포함(in) / 비포함(not in) ────────────────────────────
        if op in {"in", "not in"}:
            # left ⊆ right ?   (구간 포함 여부)
            left_inside = (left_iv.min_value >= right_iv.min_value and
                           left_iv.max_value <= right_iv.max_value)
            if left_inside:
                return {"state": "satisfied" if op == "in" else "violated",
                        "confidence": 1.0}
            # 완전히 분리 → ‘in’ 은 false 확정,  ‘not in’ 은 true 확정
            separated = (left_iv.max_value < right_iv.min_value or
                         left_iv.min_value > right_iv.max_value)
            if separated:
                return {"state": "violated" if op == "in" else "satisfied",
                        "confidence": 1.0}
            # 부분-겹침 → 불확정, 겹치는 비율을 신뢰도로
            overlap = max(0, min(left_iv.max_value, right_iv.max_value) -
                          max(left_iv.min_value, right_iv.min_value))
            conf = 1 - overlap / lw if op == "not in" else overlap / lw
            return {"state": "uncertain", "confidence": round(conf, 3)}

        if op == '>':
            true_len = max(0, left_iv.max_value - max(left_iv.min_value, right_iv.max_value))
            false_len = max(0, min(left_iv.max_value, right_iv.min_value) - left_iv.min_value)
            total = lw
        elif op == '<':
            true_len = max(0, min(left_iv.max_value, right_iv.min_value) - left_iv.min_value)
            false_len = max(0, right_iv.max_value - max(right_iv.min_value, left_iv.max_value))
            total = lw
        elif op == '>=':
            true_len = max(0, left_iv.max_value - right_iv.min_value + 1)
            false_len = max(0, right_iv.max_value - left_iv.max_value - 1)
            total = lw + 1  # 보수적인 처리
        elif op == '<=':
            true_len = max(0, right_iv.max_value - left_iv.min_value + 1)
            false_len = max(0, left_iv.min_value - right_iv.min_value - 1)
            total = lw + 1
        elif op == '==':
            # 겹치는 길이를 “true”, 나머지를 “false”
            true_len = _overlap(left_iv.min_value, left_iv.max_value,
                                right_iv.min_value, right_iv.max_value)
            false_len = lw - true_len
            total = lw
        elif op == '!=':
            true_len = lw - _overlap(left_iv.min_value, left_iv.max_value,
                                     right_iv.min_value, right_iv.max_value)
            false_len = lw - true_len
            total = lw
        else:
            raise ValueError(f"unsupported op {op}")

        # ④ 결과 state / confidence ----------------------------------
        if false_len == 0:
            return {"state": "satisfied", "confidence": 1.0}
        if true_len == 0:
            return {"state": "violated", "confidence": 0.0}

        conf = true_len / total if total else 0.5
        info = {"state": "uncertain", "confidence": round(conf, 3)}

        # ✨ 추가: unknown이면 false-support 구간을 계산해서 달아준다
        try:
            info["false_regions"] = self._false_regions_for_op(left_iv, right_iv, op)
        except Exception:
            info["false_regions"] = {"left": [], "right": [], "notes": "failed to compute"}

        return info

    def _compare_values(self, left, op: str, right) -> dict:
        # ───────── Interval ↔ Interval (기존) ─────────
        if hasattr(left, "min_value") and hasattr(right, "min_value"):
            info = self._compare_intervals_prob(left, right, op)
            out = {
                "satisfied": info["state"] == "satisfied",
                "violated": info["state"] == "violated",
                "uncertain": info["state"] == "uncertain",
                "confidence": info["confidence"],
                "message": f"{info['state']} (conf={info['confidence']})"
            }
            if "false_regions" in info:
                out["false_regions"] = info["false_regions"]
            return out

        # ───────── 스칼라 ↔ Interval (주로 in / not in) ─────────
        if not hasattr(left, "min_value") and hasattr(right, "min_value"):
            if op in {"in", "not in"}:
                if right.min_value is None or right.max_value is None:
                    return {"satisfied": False, "violated": True,
                            "uncertain": True, "confidence": 0.0,
                            "message": "interval unknown"}
                inside = right.min_value <= left <= right.max_value
                satisfied = inside if op == "in" else not inside
                return {
                    "satisfied": satisfied,
                    "violated": not satisfied,
                    "uncertain": False,
                    "confidence": 1.0,
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
                "uncertain": False,
                "confidence": 1.0,
                "message": f"{left} {op} {right} = {satisfied}"
            }
        except Exception as e:
            return {"satisfied": False, "violated": True,
                    "uncertain": True, "confidence": 0.0,
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
            # 본문이 비거나 pred가 없으면 entry/fallback 사용
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
        return self._err("duringPredicate", f"unknown DURING predicate kind: {k}", line_no)

    # POST predicate evaluator
    def _eval_post_predicate(self, pred: dict, *, line_no: int, fn_cfg) -> dict:
        k = pred["kind"]
        if k == "entryExit":
            return self.verify_post_entry_exit(var_ref=pred["var"], comp_op=pred["op"], line_no=line_no, fn_cfg=fn_cfg)
        if k == "unchanged":
            return self.verify_post_unchanged(var_ref=pred["var"], line_no=line_no, fn_cfg=fn_cfg)
        if k == "retExpr":
            return self.verify_post_return_expression(comp_op=pred["op"], value_expr=pred["rhs"], line_no=line_no,
                                                      fn_cfg=fn_cfg)
        if k == "retVar":
            return self.verify_post_return_variable(var_ref=pred["lhs"], comp_op=pred["op"], value_expr=pred["rhs"],
                                                    line_no=line_no, fn_cfg=fn_cfg)
        if k == "direct":
            return self.verify_post_direct_comparison(lhs_expr=pred["lhs"], comp_op=pred["op"], rhs_expr=pred["rhs"],
                                                      line_no=line_no, fn_cfg=fn_cfg)
        return self._err("postPredicate", f"unknown POST predicate kind: {k}", line_no)

    def _tri_state(self, res: dict) -> str:
        """
        result → 'satisfied' / 'violated' / 'uncertain'
        (기존 verify_*들의 details에 들어있는 cmp 필드 기반)
        """
        d = res.get("details", {})
        if d.get("satisfied"):
            return "satisfied"
        if d.get("violated"):
            return "violated"
        if d.get("uncertain"):
            return "uncertain"
        # fallback: status
        st = res.get("status")
        if st == "success":    return "satisfied"
        if st == "violation":  return "violated"
        return "uncertain"

    def _status_from_state(self, st: str) -> str:
        return "success" if st == "satisfied" else ("violation" if st == "violated" else "unknown")

    # GuardianVerificationEngine 내부에 추가

    def _status_from_cmp(self, cmp: dict) -> str:
        if cmp.get("satisfied"): return "success"
        if cmp.get("violated"):  return "violation"
        if cmp.get("uncertain"): return "unknown"
        return "unknown"

    def _prob_true_from_cmp(self, cmp: dict) -> float:
        # 이 엔진에서 confidence는 "참일 확률" 의미로 일관 사용
        if cmp.get("satisfied"): return 1.0
        if cmp.get("violated"):  return 0.0
        return float(cmp.get("confidence", 0.5))

    def _prob_true_from_result(self, res: dict) -> float:
        # verify_* 결과에서 details에 펼쳐 넣은 cmp를 그대로 사용
        d = res.get("details", {})
        if d.get("satisfied"): return 1.0
        if d.get("violated"):  return 0.0
        if "confidence" in d:  return float(d["confidence"])
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
        unknown일 때 '거짓이 될 수 있는' 후보 구간을 보수적으로 리턴.
        반환 예:
          { "left":  [[l1,l2], ...],
            "right": [[r1,r2], ...],
            "notes": "inclusive integer intervals" }
        """
        if (getattr(L, "min_value", None) is None or getattr(L, "max_value", None) is None or
                getattr(R, "min_value", None) is None or getattr(R, "max_value", None) is None):
            return {"left": [], "right": [], "notes": "unknown bounds"}

        a = [int(L.min_value), int(L.max_value)]
        b = [int(R.min_value), int(R.max_value)]
        left, right = [], []

        if op == '>':
            # 거짓(A<=B) 가능: A in [a_min, min(a_max, b_max)], B in [max(b_min, a_min), b_max]
            lf = self._mk_interval(a[0], min(a[1], b[1]))
            rf = self._mk_interval(max(b[0], a[0]), b[1])
            left = [lf] if lf else []
            right = [rf] if rf else []

        elif op == '<':
            # 거짓(A>=B) 가능
            lf = self._mk_interval(max(a[0], b[0]), a[1])
            rf = self._mk_interval(b[0], min(b[1], a[1]))
            left, right = ([lf] if lf else [], [rf] if rf else [])

        elif op == '>=':
            # 거짓(A<B) 가능: 정수 의미로 b_max-1, a_min+1 보정
            lf = self._mk_interval(a[0], min(a[1], b[1] - 1))
            rf = self._mk_interval(max(b[0], a[0] + 1), b[1])
            left, right = ([lf] if lf else [], [rf] if rf else [])

        elif op == '<=':
            # 거짓(A>B) 가능
            lf = self._mk_interval(max(a[0], b[0] + 1), a[1])
            rf = self._mk_interval(b[0], min(b[1], a[1] - 1))
            left, right = ([lf] if lf else [], [rf] if rf else [])

        elif op == '==':
            # 거짓은 '겹침 밖' 영역. left_false = A \ (A∩B), right_false = B \ (A∩B)
            inter = self._intersect(a, b)
            left = self._minus(a, inter) if inter else [a]
            right = self._minus(b, inter) if inter else [b]

        elif op == '!=':
            # 거짓은 '같을 수 있는' 영역. 즉 겹치는 부분이 false-support
            inter = self._intersect(a, b)
            left = [inter] if inter else []
            right = [inter] if inter else []

        elif op == 'in':
            # 거짓은 left의 '오버플로' 부분 (left \ right)
            inter = self._intersect(a, b)
            left = self._minus(a, inter) if inter else [a]
            right = []  # 오른쪽은 정보성 낮아 비움

        elif op == 'not in':
            # 거짓은 left⊆right 가 될 가능성. 보수적으로 left∩right를 “위험 후보”로 보고 리턴
            inter = self._intersect(a, b)
            left = [inter] if inter else []
            right = [inter] if inter else []

        else:
            left, right = [], []

        # None 정리
        left = [x for x in left if x]
        right = [x for x in right if x]
        return {"left": left, "right": right, "notes": "inclusive integer intervals"}


