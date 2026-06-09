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

    def _build_function_call(self, ctx: YulParser.YulFunctionCallContext) -> Expression:
        """yulFunctionCall → Expression IR"""
        func_name = ctx.IDENTIFIER().getText()
        args = [self._build_expression(e) for e in ctx.yulExpression()]

        # 2인자 binary op
        if func_name in self._BINARY_OPS and len(args) == 2:
            return Expression(
                left=args[0],
                operator=self._BINARY_OPS[func_name],
                right=args[1],
                context="BinaryOperationContext"
            )

        # not(x) → bitwise NOT
        if func_name == 'not' and len(args) == 1:
            return Expression(
                operator='~',
                expression=args[0],
                context="UnaryOperationContext"
            )

        # iszero(x) → x == 0
        if func_name == 'iszero' and len(args) == 1:
            return Expression(
                left=args[0],
                operator='==',
                right=Expression(literal=0, context="LiteralExpContext"),
                context="BinaryOperationContext"
            )

        # mulmod(a, b, n) → (a * b) % n
        if func_name == 'mulmod' and len(args) == 3:
            mul_expr = Expression(
                left=args[0], operator='*', right=args[1],
                context="BinaryOperationContext"
            )
            return Expression(
                left=mul_expr, operator='%', right=args[2],
                context="BinaryOperationContext"
            )

        # addmod(a, b, n) → (a + b) % n
        if func_name == 'addmod' and len(args) == 3:
            add_expr = Expression(
                left=args[0], operator='+', right=args[1],
                context="BinaryOperationContext"
            )
            return Expression(
                left=add_expr, operator='%', right=args[2],
                context="BinaryOperationContext"
            )

        # 미지원 built-in → TOP placeholder
        return Expression(identifier=f"__yul_{func_name}__", context="YulUnsupportedContext")

    def _build_literal(self, ctx: YulParser.YulLiteralContext) -> Expression:
        """yulLiteral → Expression IR"""
        if ctx.DECIMAL_NUMBER():
            val = int(ctx.DECIMAL_NUMBER().getText())
            return Expression(literal=val, context="LiteralExpContext")
        elif ctx.HEX_NUMBER():
            val = int(ctx.HEX_NUMBER().getText(), 16)
            return Expression(literal=val, context="LiteralExpContext")
        elif ctx.STRING_LITERAL():
            return Expression(literal=ctx.STRING_LITERAL().getText(), context="LiteralExpContext")
        # true/false
        text = ctx.getText()
        if text == 'true':
            return Expression(literal=1, context="LiteralExpContext")
        elif text == 'false':
            return Expression(literal=0, context="LiteralExpContext")
        return Expression(literal=0, context="LiteralExpContext")
