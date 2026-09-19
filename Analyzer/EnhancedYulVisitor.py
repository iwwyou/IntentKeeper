# Analyzer/EnhancedYulVisitor.py
"""
Yul (inline assembly) visitor.
Yul parse tree를 Expression IR로 변환하여 ContractAnalyzer에 전달.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Analyzer.ContractAnalyzer import ContractAnalyzer

from Parser.YulParser import YulParser
from Parser.YulVisitor import YulVisitor
from Domain.IR import Expression


class EnhancedYulVisitor(YulVisitor):
    # ★ 컨텍스트 이름에 Yul 표식을 단다(`Yul...OperationContext`).
    #   Evaluation 의 디스패치는 좌/우 존재 여부로만 라우팅하고 이 이름을 조건으로
    #   쓰는 곳이 없으므로(전수 확인) 이름만 바꿔도 평가 경로는 그대로다.
    #   대신 evaluate_binary_operator 가 "이 연산이 Yul 문맥인지" 를 알 수 있게 되어,
    #   **Yul 은 타입이 없다**(모든 값이 256-bit word)는 사실을 반영할 수 있다.
    #   Solidity 소스 경로의 타입 검사는 그대로 유지된다 — `int256 & uint256` 은
    #   애초에 컴파일되지 않는 코드이고, 그 검사가 16진 리터럴 버그(F4)를 잡았다.

    # Yul built-in → Solidity 연산자 매핑 (2인자)
    _BINARY_OPS = {
        'add': '+', 'sub': '-', 'mul': '*', 'div': '/',
        'sdiv': '/', 'mod': '%', 'smod': '%', 'exp': '**',
        'lt': '<', 'gt': '>', 'slt': '<', 'sgt': '>',
        'eq': '==',
        'and': '&', 'or': '|', 'xor': '^',
        'shl': '<<', 'shr': '>>',
        'sar': '>>',
    }

    # Yul 비교 연산. ★ Yul 에는 bool 타입이 없다 — lt/gt/slt/sgt/eq/iszero 는
    #   **1 또는 0 인 256-bit word** 를 반환하고 그대로 산술·시프트에 쓰인다.
    #   예: `let f := shl(7, gt(r, C))` = 조건이 참이면 128, 거짓이면 0 (흔한 관용구).
    #   예전엔 'gt'→'>' 로만 매핑해 BoolInterval 이 나왔고, `shl(7, <Bool>)` 이
    #   Shift dispatch 에서 거부돼 `let f` 선언 자체가 실패 → 뒤따르는
    #   `or(msb, f)` / `shr(f, r)` 가 "'f' may not be declared" 로 연쇄 실패했다
    #   (TickMath 41건 중 40건이 이 3줄 묶음 × 8회 반복).
    #   ※ and/or/xor 는 Yul 에서 **비트 연산**이므로 여기 넣지 않는다.
    _CMP_OPS = {'lt', 'gt', 'slt', 'sgt', 'eq'}

    def __init__(self, contract_analyzer: "ContractAnalyzer"):
        self.contract_analyzer = contract_analyzer

    # ── Statement visitors ──────────────────────────────────

    def visitYulUnit(self, ctx: YulParser.YulUnitContext):
        for stmt in ctx.yulStatement():
            self.visitYulStatement(stmt)
        return None

    def visitYulStatement(self, ctx: YulParser.YulStatementContext):
        return self.visitChildren(ctx)

    def visitYulBlock(self, ctx: YulParser.YulBlockContext):
        for stmt in ctx.yulStatement():
            self.visitYulStatement(stmt)
        return None

    def visitYulVariableDeclaration(self, ctx: YulParser.YulVariableDeclarationContext):
        """let mm := mulmod(a, b, not(0)) → 새 uint256 변수 선언"""
        identifiers = ctx.IDENTIFIER()
        if not identifiers:
            return None
        var_name = identifiers[0].getText()

        # := 이후 expression (없을 수도 있음: let x;)
        yul_expr = ctx.yulExpression()
        yul_func = ctx.yulFunctionCall()

        if yul_expr:
            rhs = self._build_expression(yul_expr)
        elif yul_func:
            rhs = self._build_function_call(yul_func)
        else:
            rhs = None

        self.contract_analyzer.process_yul_variable_declaration(var_name, rhs)
        return None

    def visitYulAssignment(self, ctx: YulParser.YulAssignmentContext):
        """prod0 := mul(a, b) → 기존 변수에 대입"""
        identifiers = ctx.IDENTIFIER()
        if not identifiers:
            return None

        rhs_expr = ctx.yulExpression()
        rhs_func = ctx.yulFunctionCall()

        if rhs_expr:
            rhs = self._build_expression(rhs_expr)
        elif rhs_func:
            rhs = self._build_function_call(rhs_func)
        else:
            return None

        # 단일 대입 (첫 번째 identifier)
        var_name = identifiers[0].getText()
        lhs = Expression(identifier=var_name, context="IdentifierExpContext")
        self.contract_analyzer.process_yul_assignment(lhs, rhs)
        return None

    def visitYulExpressionStatement(self, ctx: YulParser.YulExpressionStatementContext):
        # standalone function call (side effect only, e.g., log0(...))
        return None

    def visitYulIfStatement(self, ctx: YulParser.YulIfStatementContext):
        # 현재 미지원 (control flow)
        return None

    def visitYulForStatement(self, ctx: YulParser.YulForStatementContext):
        return None

    def visitYulSwitchStatement(self, ctx: YulParser.YulSwitchStatementContext):
        return None

    def visitYulFunctionDefinition(self, ctx: YulParser.YulFunctionDefinitionContext):
        return None

    # ── Expression IR builders ──────────────────────────────

    def _build_expression(self, ctx: YulParser.YulExpressionContext) -> Expression:
        """yulExpression → Expression IR"""
        if ctx.yulFunctionCall():
            return self._build_function_call(ctx.yulFunctionCall())
        elif ctx.IDENTIFIER():
            name = ctx.IDENTIFIER().getText()
            return Expression(identifier=name, context="IdentifierExpContext")
        elif ctx.yulLiteral():
            return self._build_literal(ctx.yulLiteral())
        return Expression(literal=0, context="LiteralExpContext")

    @staticmethod
    def _word(literal: str) -> Expression:
        """0/1 같은 uint256 word 리터럴. (문자열 규약 — _build_literal 주석 참조)"""
        return Expression(literal=literal, expr_type='uint', type_length=256,
                          context="LiteralExpContext")

    def _as_word(self, cond: Expression) -> Expression:
        """비교식(BoolInterval) → 0/1 uint word.

        `cond ? 1 : 0` 삼항으로 감싼다. evaluate_conditional_expression_context 가
        BoolInterval [1,1]/[0,0] 이면 해당 분기로 **정확히 접고**, [0,1] 이면 두 분기를
        join 해 [0,1] 을 준다 — ⊤ 로 뭉개지 않으므로 정밀도 손실이 없다.

        ※ Yul 경로에만 적용한다. Solidity 에선 bool 이 산술에 쓰일 수 없으므로
          Evaluation 쪽에서 BoolInterval 을 승격하면 진짜 타입 오류를 덮게 된다.
        """
        return Expression(condition=cond,
                          true_expr=self._word('1'), false_expr=self._word('0'),
                          operator='?:', context="ConditionalExpContext")

    def _build_function_call(self, ctx: YulParser.YulFunctionCallContext) -> Expression:
        """yulFunctionCall → Expression IR"""
        func_name = ctx.IDENTIFIER().getText()
        args = [self._build_expression(e) for e in ctx.yulExpression()]

        # 2인자 binary op
        if func_name in self._BINARY_OPS and len(args) == 2:
            e = Expression(
                left=args[0],
                operator=self._BINARY_OPS[func_name],
                right=args[1],
                context="YulBinaryOperationContext"
            )
            # 비교 계열은 Yul 에서 0/1 word 다 (_CMP_OPS 주석 참조)
            return self._as_word(e) if func_name in self._CMP_OPS else e

        # not(x) → bitwise NOT
        if func_name == 'not' and len(args) == 1:
            return Expression(
                operator='~',
                expression=args[0],
                context="YulUnaryOperationContext"
            )

        # iszero(x) → (x == 0) ? 1 : 0  — 결과도 0/1 word 다
        #   (우변 리터럴도 int 가 아닌 문자열 + expr_type 규약을 따라야 한다)
        if func_name == 'iszero' and len(args) == 1:
            return self._as_word(Expression(
                left=args[0],
                operator='==',
                right=self._word('0'),
                context="YulBinaryOperationContext"
            ))

        # mulmod(a, b, n) → (a * b) % n
        if func_name == 'mulmod' and len(args) == 3:
            mul_expr = Expression(
                left=args[0], operator='*', right=args[1],
                context="YulBinaryOperationContext"
            )
            return Expression(
                left=mul_expr, operator='%', right=args[2],
                context="YulBinaryOperationContext"
            )

        # addmod(a, b, n) → (a + b) % n
        if func_name == 'addmod' and len(args) == 3:
            add_expr = Expression(
                left=args[0], operator='+', right=args[1],
                context="YulBinaryOperationContext"
            )
            return Expression(
                left=add_expr, operator='%', right=args[2],
                context="YulBinaryOperationContext"
            )

        # 미지원 built-in → TOP placeholder
        return Expression(identifier=f"__yul_{func_name}__", context="YulUnsupportedContext")

    def _build_literal(self, ctx: YulParser.YulLiteralContext) -> Expression:
        """yulLiteral → Expression IR

        ★ expr_type 을 반드시 채운다. 예전엔 5개 반환 경로 전부 비워 둬서
          `Evaluation.evaluate_literal_context` 가 모든 분기를 빠져나가
          `Unsupported literal expr_type 'None'` 으로 죽었다(51건: TickMath 36,
          PRBMathCommon 7, PRBMathSD59x18 5, FullMath 2, UnsafeMath 1).

        ★ literal 은 반드시 **문자열**로 넣는다. 예전엔 `int(...)` 로 변환해 넣었는데,
          evaluate_literal_context 는 `int(txt, 0)` 로 파싱하므로 int 를 주면
          `TypeError: int() can't convert non-string with explicit base` 가 나고
          그 함수의 `except ValueError` 로는 잡히지 않는다. Solidity 쪽
          `visitLiteralExp` 도 `ctx.getText()` 문자열을 넣는다 — 같은 규약을 따른다.

        ★ 타입은 'uint'/256. Yul 은 타입 없는 256-bit word 언어다.
          (이 리포 소스에 slt/sdiv/smod/sar/signextend 는 0건, sgt 만 7건)
        """
        if ctx.DECIMAL_NUMBER():
            return Expression(literal=ctx.DECIMAL_NUMBER().getText(),
                              expr_type='uint', type_length=256,
                              context="LiteralExpContext")
        if ctx.HEX_NUMBER():
            # '0x..' 원문 그대로 — evaluate_literal_context 의 int(txt, 0) 이 해석한다.
            return Expression(literal=ctx.HEX_NUMBER().getText(),
                              expr_type='uint', type_length=256,
                              context="LiteralExpContext")
        if ctx.STRING_LITERAL():
            return Expression(literal=ctx.STRING_LITERAL().getText(),
                              expr_type='string', context="LiteralExpContext")
        text = ctx.getText()
        if text in ('true', 'false'):
            # Yul 에 bool 타입은 없다 — true/false 는 1/0 word 다.
            return Expression(literal='1' if text == 'true' else '0',
                              expr_type='uint', type_length=256,
                              context="LiteralExpContext")
        # 알 수 없는 리터럴을 조용히 0 으로 만들던 폴백 제거 — 그건 오분석의 원천이다.
        raise ValueError(f"Unknown yulLiteral: {text!r}")
