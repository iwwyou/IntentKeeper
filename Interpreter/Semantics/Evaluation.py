from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:                                         # 타입 검사 전용
     from Analyzer.ContractAnalyzer import ContractAnalyzer

from Domain.Variable import Variables, ArrayVariable, StructVariable, MappingVariable, EnumVariable, EnumDefinition
from Domain.Type import SolType
from Domain.Interval import Interval, IntegerInterval, BoolInterval, UnsignedIntegerInterval
from Domain.AddressSet import AddressSet
from Domain.BytesSet import BytesSet
from Domain.IR import Expression

from Utils.Helper import VariableEnv

from decimal import Decimal, InvalidOperation
import re
import copy

class Evaluation :

    def __init__(self, analyzer: "ContractAnalyzer"):
        # ContractAnalyzer 인스턴스만 보관해 두고,
        # 나머지 컴포넌트는 필요할 때 property 로 접근합니다.
        self.an = analyzer

    # ── lazy properties ──────────────────────────────────────────────
    @property
    def up(self):
        return self.an.updater          # Update 싱글톤

    @property
    def engine(self):
        return self.an.engine          # Engine 싱글톤

    # ──────────────────── Helper functions ───────────────────────────

    def _find_enum_in_chain(self, name: str):
        """현재 contract + parent chain에서 EnumDefinition 검색. 없으면 None."""
        cfg = self.an.contract_cfgs.get(self.an.current_target_contract)
        return self._search_enum_recursive(cfg, name) if cfg else None

    @staticmethod
    def _search_enum_recursive(cfg, name):
        defs = getattr(cfg, 'enumDefs', {})
        if name in defs:
            return defs[name]
        for pcfg in getattr(cfg, 'parent_cfgs', {}).values():
            result = Evaluation._search_enum_recursive(pcfg, name)
            if result:
                return result
        return None

    def _get_interface_name_of_var(self, var_name: str, variables: dict) -> str | None:
        """
        변수(function parameter 또는 state variable)의 typeInfo에서
        interface 이름을 반환. interface 타입이 아니면 None.
        """
        # 1) 현재 함수의 variables (parameter 포함)
        if var_name in variables:
            var = variables[var_name]
            if hasattr(var, 'typeInfo') and var.typeInfo and var.typeInfo.typeCategory == "interface":
                return var.typeInfo.interfaceName

        # 2) FunctionCFG.interface_var_types (지역변수 중 interface 타입)
        fcfg = self.an.current_target_function_cfg
        if fcfg and hasattr(fcfg, 'interface_var_types') and var_name in fcfg.interface_var_types:
            return fcfg.interface_var_types[var_name]

        # 3) state variable
        current_contract = self.an.current_target_contract
        if current_contract and current_contract in self.an.contract_cfgs:
            ccf = self.an.contract_cfgs[current_contract]
            if hasattr(ccf, 'state_variables') and var_name in ccf.state_variables:
                var = ccf.state_variables[var_name]
                if hasattr(var, 'typeInfo') and var.typeInfo and var.typeInfo.typeCategory == "interface":
                    return var.typeInfo.interfaceName

        return None

    def _collect_ireturn_entries(self, registry, match_prefix):
        """registry에서 match_prefix로 시작하는 (contract_var, func_name) entries 수집.
        Returns: dict { access_chain_tuple: value }
        """
        entries = {}
        for key, val in registry.items():
            if key[:len(match_prefix)] == match_prefix:
                chain = key[len(match_prefix)]  # access_chain tuple
                entries[chain] = val
        return entries

    def _assemble_ireturn_value(self, interface_name, func_name, entries, callerObject):
        """@IReturn entries로부터 반환값 조립.
        entries: { access_chain_tuple: value }
        - () → 단일 값
        - (("member", "x"),) → struct member
        - (("index", 0),) → tuple index
        """
        import pickle, pathlib

        # 단일 반환 (access_chain이 빈 tuple)
        if () in entries and len(entries) == 1:
            return self._mapping_lookup_if_needed(entries[()], callerObject)

        # struct member 또는 index가 있는 경우 → return type 조회 후 조립
        pkl_path = pathlib.Path(f'Dependencies/objectfile/ifc_{interface_name}.pkl')
        if not pkl_path.exists():
            # fallback: 단일 값이면 반환
            if () in entries:
                return self._mapping_lookup_if_needed(entries[()], callerObject)
            return None

        with open(pkl_path, 'rb') as f:
            raw = pickle.load(f)
        ifc_cfg = raw["cfg"] if isinstance(raw, dict) and "cfg" in raw else raw
        ifc_fcfg = ifc_cfg.get_function_cfg(func_name)
        if not ifc_fcfg or not ifc_fcfg.return_types:
            return None

        rt = ifc_fcfg.return_types[0]
        struct_defs = getattr(ifc_cfg, 'structDefs', {})
        enum_defs = getattr(ifc_cfg, 'enumDefs', {})

        # top 값 생성
        top_val = VariableEnv.top_from_soltype(
            rt, struct_defs, enum_defs,
            identifier=f"{interface_name}.{func_name}_ret")
        # Variables wrapper → value 추출 (elementary)
        if isinstance(top_val, Variables) and \
           not isinstance(top_val, (StructVariable, ArrayVariable, MappingVariable, EnumVariable)):
            top_val = top_val.value

        # entries의 access chain을 따라 값 설정
        for chain, val in entries.items():
            if chain == ():
                top_val = val  # 전체 덮어쓰기
                continue
            target = top_val
            for i, step in enumerate(chain):
                is_last = (i == len(chain) - 1)
                if step[0] == "member":
                    if isinstance(target, StructVariable) and step[1] in target.members:
                        if is_last:
                            member_var = target.members[step[1]]
                            if hasattr(member_var, 'value'):
                                member_var.value = val
                        else:
                            target = target.members[step[1]]
                    else:
                        break  # member를 찾지 못함
                elif step[0] == "index":
                    if isinstance(target, ArrayVariable):
                        idx = step[1]
                        if idx < len(target.elements):
                            if is_last:
                                elem = target.elements[idx]
                                if hasattr(elem, 'value'):
                                    elem.value = val
                            else:
                                target = target.elements[idx]
                    else:
                        break
                elif step[0] == "call":
                    # chained interface call: target이 Variables이고
                    # value가 AddressSet + _cast_interface면 해당 interface 함수 반환값 설정
                    call_name = step[1]
                    addr_val = target.value if isinstance(target, Variables) else target
                    cast_ifc = getattr(addr_val, '_cast_interface', None)
                    if cast_ifc and is_last:
                        # 이 chained call의 반환값을 별도 registry에 저장하지 않고
                        # 직접 top_val 수준에서 처리 (evaluation 시 _lookup_interface_return으로 조회)
                        # → chained call은 registry에 full chain으로 저장되어 있으므로
                        #   evaluation 시점에서 처리됨
                        pass  # 값은 이미 registry에 chain 전체로 저장됨
                    elif cast_ifc and not is_last:
                        # 중간 chained call: 반환 타입으로 top 생성하여 다음 step 진행
                        ret_val = self._lookup_interface_return(cast_ifc, call_name)
                        if ret_val is not None:
                            target = ret_val
                        else:
                            break
                    else:
                        break

        return self._mapping_lookup_if_needed(top_val, callerObject)

    def _resolve_ireturn_pattern_a(self, fcfg, interface_name, contract_var, func_name, callerObject):
        """Pattern A: contractVar.funcName().<chain> 조회"""
        if not fcfg.ireturn_registry:
            return None
        entries = self._collect_ireturn_entries(
            fcfg.ireturn_registry, (contract_var, func_name))
        if not entries:
            return None
        return self._assemble_ireturn_value(interface_name, func_name, entries, callerObject)

    def _resolve_ireturn_pattern_b(self, fcfg, interface_name, addr_var, func_name, callerObject):
        """Pattern B: Interface(addr).funcName().<chain> 조회"""
        if not fcfg.ireturn_registry:
            return None
        entries = self._collect_ireturn_entries(
            fcfg.ireturn_registry, (interface_name, addr_var, func_name))
        if not entries:
            return None
        return self._assemble_ireturn_value(interface_name, func_name, entries, callerObject)

    def _lookup_interface_return(self, interface_name, func_name):
        """interface pkl에서 함수 return type 조회 (parent chain 포함) → top domain value"""
        import pickle, pathlib
        visited = set()
        queue = [interface_name]
        while queue:
            ifc_name = queue.pop(0)
            if ifc_name in visited:
                continue
            visited.add(ifc_name)
            pkl_path = pathlib.Path(f'Dependencies/objectfile/ifc_{ifc_name}.pkl')
            if not pkl_path.exists():
                continue
            with open(pkl_path, 'rb') as f:
                raw = pickle.load(f)
            ifc_cfg = raw["cfg"] if isinstance(raw, dict) and "cfg" in raw else raw
            ifc_fcfg = ifc_cfg.get_function_cfg(func_name)
            if ifc_fcfg and ifc_fcfg.return_types:
                rt = ifc_fcfg.return_types[0]
                struct_defs = getattr(ifc_cfg, 'structDefs', {})
                enum_defs = getattr(ifc_cfg, 'enumDefs', {})
                top_val = VariableEnv.top_from_soltype(
                    rt, struct_defs, enum_defs,
                    identifier=f"{ifc_name}.{func_name}_ret")
                if isinstance(top_val, Variables) and \
                   not isinstance(top_val, (StructVariable, ArrayVariable, MappingVariable, EnumVariable)):
                    return top_val.value
                return top_val
            # parent chain 추가
            for pname in getattr(ifc_cfg, 'parent_contracts', []):
                if pname not in visited:
                    queue.append(pname)
        return None

    def _mapping_lookup_if_needed(self, result, callerObject):
        """
        callerObject가 MappingVariable이면 result를 key로 mapping lookup 수행.
        index access 내 함수 호출 등에서 사용.
        """
        if not isinstance(callerObject, MappingVariable) or result is None:
            return result

        mapping_var = callerObject
        if not mapping_var.struct_defs or not mapping_var.enum_defs:
            ccf = self.an.contract_cfgs[self.an.current_target_contract]
            mapping_var.struct_defs = ccf.structDefs
            mapping_var.enum_defs = ccf.enumDefs

        # key 결정: 리턴값에서 추론
        if isinstance(result, AddressSet):
            key_val = str(result)
        elif hasattr(result, "min_value"):
            if result.min_value == result.max_value:
                key_val = str(result.min_value)
            else:
                key_val = f"func_result_{id(result)}"
        else:
            key_val = str(result)

        if key_val not in mapping_var.mapping:
            mapping_var.mapping[key_val] = mapping_var.get_or_create(key_val)
        mvar = mapping_var.mapping[key_val]
        if isinstance(mvar, (StructVariable, ArrayVariable, MappingVariable)):
            return mvar
        else:
            return mvar.value

    def find_function_in_hierarchy(self, contract_cfg, function_name: str):
        """
        Args:
            contract_cfg: 현재 컨트랙트 CFG
            function_name: 찾을 함수 이름

        Returns:
            FunctionCFG 또는 None (못 찾은 경우)
        """
        # 1. 현재 컨트랙트에서 검색
        if function_name in contract_cfg.functions:
            return contract_cfg.get_function_cfg(function_name)

        # 2. 부모 컨트랙트 체인 검색 (MRO 순서)
        parent_contracts = getattr(contract_cfg, 'parent_contracts', [])
        parent_cfgs = getattr(contract_cfg, 'parent_cfgs', {})

        for parent_name in parent_contracts:
            parent_cfg = parent_cfgs.get(parent_name)
            if parent_cfg:
                # 재귀적으로 부모 체인 검색
                result = self.find_function_in_hierarchy(parent_cfg, function_name)
                if result:
                    return result

        # 3. 못 찾음
        return None

    def find_function_in_parent_only(self, contract_cfg, function_name: str):
        """
        super 키워드용: 현재 컨트랙트는 건너뛰고 부모 체인에서만 검색한다.

        Args:
            contract_cfg: 현재 컨트랙트 CFG
            function_name: 찾을 함수 이름

        Returns:
            FunctionCFG 또는 None (못 찾은 경우)
        """
        parent_contracts = getattr(contract_cfg, 'parent_contracts', [])
        parent_cfgs = getattr(contract_cfg, 'parent_cfgs', {})

        for parent_name in parent_contracts:
            parent_cfg = parent_cfgs.get(parent_name)
            if parent_cfg:
                # 부모에서는 전체 계층 검색
                result = self.find_function_in_hierarchy(parent_cfg, function_name)
                if result:
                    return result

        return None

    def _join_struct_fields(self, struct_list):
        """
        구조체 리스트의 각 필드를 join하여 하나의 구조체 반환
        """
        if not struct_list:
            return None

        # 첫 구조체를 복사하여 결과 구조체 생성
        result = copy.deepcopy(struct_list[0])

        # 각 필드별로 모든 구조체의 값을 join
        for field_name in result.members:
            values = []
            for i, s in enumerate(struct_list):
                if field_name in s.members:
                    field_var = s.members[field_name]
                    if isinstance(field_var, (StructVariable, ArrayVariable, MappingVariable)):
                        # 복합 타입은 join 불가 - 첫 번째 것 사용
                        values.append(field_var)
                        break
                    else:
                        val = field_var.value
                        values.append(val)

            # join 수행
            if values:
                joined_val = values[0]
                for v in values[1:]:
                    if hasattr(joined_val, 'join') and hasattr(v, 'join'):
                        joined_val = joined_val.join(v)

                # 결과 저장
                if isinstance(result.members[field_name], Variables):
                    result.members[field_name].value = joined_val

        return result

    def _join_array_elements_virtually(self, array, index_range):
        """
        배열을 수정하지 않고 가상으로 요소 생성하여 join
        """
        l, r = index_range
        span = r - l

        # 샘플링할 인덱스 결정 (최대 20개)
        if span > 20:
            sample_indices = [l + i * span // 20 for i in range(21)]
        else:
            sample_indices = list(range(l, r + 1))

        joined = None
        for idx in sample_indices:
            # 기존 요소가 있으면 사용, 없으면 가상으로 생성
            if idx < len(array.elements):
                elem = array.elements[idx]
            else:
                elem = array._create_element_virtual(idx)

            # join 로직
            if isinstance(elem, StructVariable):
                # 구조체는 각 필드별로 join
                if joined is None:
                    joined = copy.deepcopy(elem)
                else:
                    # 구조체의 각 필드 join
                    for field in elem.members:
                        if field in joined.members:
                            elem_val = elem.members[field].value if hasattr(elem.members[field], 'value') else elem.members[field]
                            joined_val = joined.members[field].value if hasattr(joined.members[field], 'value') else joined.members[field]
                            if hasattr(elem_val, 'join') and hasattr(joined_val, 'join'):
                                joined.members[field].value = joined_val.join(elem_val)
            else:
                val = elem.value if hasattr(elem, 'value') else elem
                joined = val if joined is None else joined.join(val)

        return joined

    def _join_mapping_values_virtually(self, mapping, sample_keys):
        """
        매핑의 여러 키에 대해 가상으로 value 생성하여 join
        """
        joined = None
        for k in sample_keys:
            k_str = str(k)
            if k_str in mapping.mapping:
                val_obj = mapping.mapping[k_str]
            else:
                val_obj = mapping._create_value_virtual(k_str)

            # 구조체: 필드별 join
            if isinstance(val_obj, StructVariable):
                if joined is None:
                    joined = copy.deepcopy(val_obj)
                else:
                    for field in val_obj.members:
                        if field in joined.members:
                            val = val_obj.members[field].value if hasattr(val_obj.members[field], 'value') else val_obj.members[field]
                            joined_val = joined.members[field].value if hasattr(joined.members[field], 'value') else joined.members[field]
                            if hasattr(val, 'join') and hasattr(joined_val, 'join'):
                                joined.members[field].value = joined_val.join(val)
            # 기본 타입: value join
            elif isinstance(val_obj, (ArrayVariable, MappingVariable)):
                # 복합 타입은 첫 것만 사용
                if joined is None:
                    joined = val_obj
            else:
                val = val_obj.value if hasattr(val_obj, "value") else val_obj
                joined = val if joined is None else joined.join(val)

        return joined

    def evaluate_expression(self, expr: Expression, variables, callerObject=None, callerContext=None):
        if expr.context == "LiteralExpContext":
            return self.evaluate_literal_context(expr, variables, callerObject, callerContext)
        elif expr.context == "NumLiteralContext":
            # Guardian DSL의 숫자 리터럴 (arithExpr에서 사용)
            return self.evaluate_literal_context(expr, variables, callerObject, callerContext)
        elif expr.context == "IdentifierExpContext":
            return self.evaluate_identifier_context(expr, variables, callerObject, callerContext)
        elif expr.context == "VarRefBase":
            # Guardian DSL의 단순 변수 참조 (IdentifierExpContext와 동일 구조)
            return self.evaluate_identifier_context(expr, variables, callerObject, callerContext)
        elif expr.context == 'MemberAccessContext':
            return self.evaluate_member_access_context(expr, variables, callerObject, callerContext)
        elif expr.context == "VarRefMemberAccess":
            # Guardian DSL의 멤버 접근 (MemberAccessContext와 동일 구조)
            return self.evaluate_member_access_context(expr, variables, callerObject, callerContext)
        elif expr.context == "IndexAccessContext":
            return self.evaluate_index_access_context(expr, variables, callerObject, callerContext)
        elif expr.context == "VarRefIndexAccess":
            # Guardian DSL의 인덱스 접근 (IndexAccessContext와 동일 구조)
            return self.evaluate_index_access_context(expr, variables, callerObject, callerContext)
        elif expr.context == "MetaTypeContext":
            # type(uint256), type(address) 등
            return {"isType": True, "typeName": expr.typeName}
        elif expr.context == "TypeConversion":
            return self.evaluate_type_conversion_context(expr, variables, callerObject, callerContext)
        elif expr.context == "ConditionalExpContext":
            return self.evaluate_conditional_expression_context(expr, variables, callerObject, callerContext)
        elif expr.context == "InlineArrayExpression":
            return self.evaluate_inline_array_expression_context(expr, variables, callerObject, callerContext)
        elif expr.context == "TypeWrapUnwrapContext":
            return self.evaluate_type_wrap_unwrap(expr, variables, callerObject, callerContext)
        elif expr.context == "FunctionCallContext":
            return self.evaluate_function_call_context(expr, variables, callerObject, callerContext)
        elif expr.context == "FunctionCallOptionContext":
            return self.evaluate_function_call_option_context(expr, variables, callerObject, callerContext)
        elif expr.context == "PayableFunctionCallContext":
            # payable(addr) - address를 payable address로 변환
            return self.evaluate_payable_function_call_context(expr, variables, callerObject, callerContext)

        elif expr.context == "TupleExpressionContext":
            return self.evaluate_tuple_expression_context(expr, variables,
                                                          callerObject, callerContext)
        elif expr.context == 'AssignmentOpContext':
            return self.evaluate_assignment_expression(expr, variables,
                                                       callerObject, callerContext)
        elif expr.context == "LiteralSubDenomination":
            return self.evaluate_literal_with_subdenomination_context(
                expr, variables, callerObject, callerContext)
        elif expr.context == "NewExpContext":
            return self.evaluate_new_expression_context(expr, variables,
                                                        callerObject, callerContext)

        # 단항 연산자
        if expr.operator in ['-', '!', '~'] and expr.expression:
            return self.evaluate_unary_operator(expr, variables, callerObject, callerContext)

        # 이항 연산자
        if expr.left is not None and expr.right is not None:
            return self.evaluate_binary_operator(expr, variables, callerObject, callerContext)

    def evaluate_new_expression_context(self, expr: Expression,
                                        variables, callerObject=None, callerContext=None):
        """
        ▸ expr.type_name  : visitNewExp() 에서 채워 둔 SolType 인스턴스
        ▸ 반환값          : 새로 만든 ArrayVariable / MappingVariable /
                           StructVariable / Variables (elementary) /
                           심볼릭 address 등
        """

        sol_t: SolType = expr.typeName  # 타입 정보
        fresh_id = f"new_{id(expr)}"  # 유니크한 식별자

        # ── (A) 배열 ───────────────────────────────────────────────
        if sol_t.typeCategory == "array":
            # 동적 배열 크기 평가: new uint256[](size) 형태
            MAX_CONCRETE_ARRAY_LEN = 100  # 구체적으로 초기화할 최대 배열 길이
            array_length = sol_t.arrayLength
            if expr.arguments and len(expr.arguments) > 0:
                # arguments[0]에 길이 표현식이 있으면 평가
                length_result = self.evaluate_expression(expr.arguments[0], variables, callerObject, callerContext)
                # 결과가 interval이면 상한값 사용 (max_value 속성 사용)
                if hasattr(length_result, 'max_value') and length_result.max_value is not None:
                    # 배열 길이가 너무 크면 동적 배열로 처리 (무한 루프 방지)
                    if length_result.max_value > MAX_CONCRETE_ARRAY_LEN:
                        array_length = None  # 동적 배열로 처리
                    else:
                        array_length = length_result.max_value
                elif isinstance(length_result, int):
                    if length_result > MAX_CONCRETE_ARRAY_LEN:
                        array_length = None
                    else:
                        array_length = length_result
                else:
                    # 심볼릭이거나 다른 타입이면 None으로 (동적)
                    array_length = None

            arr = ArrayVariable(
                fresh_id,
                base_type=sol_t.arrayBaseType,
                array_length=array_length,
                is_dynamic=sol_t.isDynamicArray,
                scope="memory"
            )

            # ⬇ Solidity default: new array elements are zero-initialized
            if ArrayVariable._is_abstractable(sol_t.arrayBaseType):
                et = str(sol_t.arrayBaseType.elementaryTypeName)
                bits = sol_t.arrayBaseType.intTypeLength or 256
                if et.startswith("int"):
                    dummy = IntegerInterval(0, 0, bits)
                elif et == "bool":
                    dummy = BoolInterval(0, 0)
                else:
                    dummy = UnsignedIntegerInterval(0, 0, bits)
                arr.initialize_elements(dummy)
            else:
                arr.initialize_not_abstracted_type()

            return arr

        # ── (B) 매핑 ───────────────────────────────────────────────
        if sol_t.typeCategory == "mapping":
            ccf = self.an.contract_cfgs[self.an.current_target_contract]

            return MappingVariable(fresh_id,
                                   key_type=sol_t.mappingKeyType,
                                   value_type=sol_t.mappingValueType,
                                   scope="memory",
                                   struct_defs=ccf.structDefs,  # ⭐️ 전달
                                   enum_defs=ccf.enumDefs)  # ⭐️ 전달)

        # ── (C) 구조체 ─────────────────────────────────────────────
        if sol_t.typeCategory == "struct":
            return StructVariable(fresh_id, sol_t.structTypeName, scope="memory")

        # ── (D) 컨트랙트 new Foo()  → 심볼릭 address ───────────────
        if sol_t.typeCategory == "userDefined" :
            # "fresh address"를 set domain TOP 으로
            return AddressSet.top()

        # ── (E) 기본형 new uint[](...) 처럼 size 없는 array 등
        #        또는 new bytes(...) – 메모리 상 동적 할당
        if sol_t.typeCategory == "elementary":
            return f"symbolic_{fresh_id}"

        raise ValueError(f"unsupported 'new' type: {sol_t!r}")

    # ───────────────────── evaluate_literal_context ──────────────
    def evaluate_literal_context(
            self,
            expr: Expression,
            variables: dict[str, Variables],
            callerObject: Variables | ArrayVariable | MappingVariable | None = None,
            callerContext: str | None = None):

        lit = expr.literal  # 예: "123", "0x1A", "true", ...
        ety = expr.expr_type  # 'uint'·'int'·'bool'·'string'·'address' 등
        _NUM_SCI = re.compile(r"^[+-]?\d+([eE][+-]?\d+)$")  # 1e8, 2E+18 …

        def _to_scalar_int(txt: str) :
            """
            10·16·8진수(+부호) + decimal scientific notation → int 로 변환.
            """
            try:
                return int(txt, 0)  # 0x… / 0o… / plain decimal
            except ValueError:
                pass

        def _parse_maybe_int(txt: str):
            """10·16·8진수 또는 지수표기를 int 로 반환. 실패하면 None."""
            # ➊ 0x / 0o / decimal
            try:
                return int(txt, 0)
            except ValueError:
                pass

            # ➋ scientific notation
            if _NUM_SCI.match(txt):
                try:
                    return int(Decimal(txt))
                except (InvalidOperation, ValueError):
                    pass
            return None

        def _literal_is_address(txt: str) -> bool:
            """
            0x 로 시작하고 20 바이트(40 hex) 또는 0x0 처럼 짧아도 ‘주소 literal’ 로 간주
            실제 Solidity lexer 는 0x 포함 42자 고정이지만, 여기선 분석 편의상 느슨하게 허용
            """
            return txt.lower().startswith("0x") and all(c in "0123456789abcdefABCDEF" for c in txt[2:])

        # ───────── 1. 상위 객체(Array / Mapping) 인덱싱 ──────────
        if callerObject is not None:
            # 1-A) 배열 인덱스
            if isinstance(callerObject, ArrayVariable):
                if not lit.lstrip("-").isdigit():
                    raise ValueError(f"Array index must be decimal literal, got '{lit}'")
                idx = int(lit)
                if idx < 0 or idx >= len(callerObject.elements):
                    raise IndexError(f"Index {idx} out of range for array '{callerObject.identifier}'")
                return callerObject.elements[idx]  # element (Variables | …)

            # 1-B) 매핑 키 – 문자열·hex·decimal 모두 허용
            if isinstance(callerObject, MappingVariable):
                if not callerObject.struct_defs or not callerObject.enum_defs:
                    ccf = self.an.contract_cfgs[self.an.current_target_contract]
                    callerObject.struct_defs = ccf.structDefs
                    callerObject.enum_defs = ccf.enumDefs

                key = lit
                if key not in callerObject.mapping:
                    # 새 엔트리 생성
                    new_var = callerObject.get_or_create(key)
                    # CFG 에 반영
                    self.update_mapping_in_cfg(callerObject.identifier, key, new_var)
                return callerObject.mapping[key]

        # ───────── 2. 상위 없음 & 인덱스/멤버 base 해결 ──────────
        if callerContext in ("IndexAccessContext", "MemberAccessContext"):
            return lit  # key 로 그대로 사용

        # ───────── 3. 실제 값으로 해석해 반환 ──────────
        if ety == "uint":
            val = _to_scalar_int(lit)
            if val < 0:
                raise ValueError("uint literal cannot be negative")
            bits = expr.type_length or 256
            return UnsignedIntegerInterval(val, val, bits)

        if ety == "int":
            bits = expr.type_length or 256
            val = _to_scalar_int(lit)
            return IntegerInterval(val, val, bits)

        if ety == "bool":
            if lit.lower() == "true":
                return BoolInterval(1, 1)
            if lit.lower() == "false":
                return BoolInterval(0, 0)
            raise ValueError(f"Invalid bool literal '{lit}'")

        # 새로 추가 ───────── address / bytes / string ─────────
        if ety == "address":
            if not _literal_is_address(lit):
                raise ValueError(f"Malformed address literal '{lit}'")
            val_int = int(lit, 16)
            # ★ Set domain 사용: 구체적 address ID로 singleton set 생성
            return AddressSet(ids={val_int})

        # bytes32, bytes16 등 고정 크기 바이트 배열
        if ety and ety.startswith("bytes") and len(ety) > 5:  # "bytes32", "bytes16" 등
            byte_size = int(ety[5:])  # "bytes32" -> 32
            maybe_int = _parse_maybe_int(lit)
            if maybe_int is not None:
                # 숫자로 파싱 가능하면 BytesSet으로 처리
                return BytesSet(values={maybe_int}, byte_size=byte_size)
            # 16진수 문자열 시도
            if lit.startswith("0x"):
                try:
                    val_int = int(lit, 16)
                    return BytesSet(values={val_int}, byte_size=byte_size)
                except ValueError:
                    pass
            # 파싱 불가능하면 심볼릭 (TOP)
            return BytesSet.top(byte_size)

        if ety in ("string", "bytes"):
            maybe_int = _parse_maybe_int(lit)
            if maybe_int is not None:
                # ▶ 사실은 숫자!  → uint256 interval 로 취급
                return UnsignedIntegerInterval(maybe_int, maybe_int, 256)
            return lit  # 진짜 문자열이면 그대로 심볼릭

        # 기타 타입
        raise ValueError(f"Unsupported literal expr_type '{ety}'")

    def evaluate_identifier_context(self, expr: Expression, variables, callerObject=None, callerContext=None):
        ident_str = expr.identifier

        # callerObject가 있는 경우
        if callerObject is not None:
            if isinstance(callerObject, ArrayVariable):
                if ident_str not in variables:
                    raise ValueError(f"Index identifier '{ident_str}' not found.")

                idx_var_obj = variables[ident_str]
                iv = idx_var_obj.value  # Unsigned/IntegerInterval …

                # ── (A) 인덱스가 확정(singleton) ────────────────────────
                if VariableEnv.is_interval(iv) and not iv.is_bottom() and iv.min_value == iv.max_value:
                    idx = iv.min_value
                    if idx < 0:
                        raise IndexError(f"Negative index {idx} for array '{callerObject.identifier}'")

                    if idx >= len(callerObject.elements):
                        # ❗ 요소가 아직 없음 → base-type 의 TOP 값 (알 수 없는 값)
                        base_t = callerObject.typeInfo.arrayBaseType
                        if base_t.elementaryTypeName and base_t.elementaryTypeName.startswith("uint"):
                            bits = base_t.intTypeLength or 256
                            return UnsignedIntegerInterval.top(bits)
                        elif base_t.elementaryTypeName and base_t.elementaryTypeName.startswith("int"):
                            bits = base_t.intTypeLength or 256
                            return IntegerInterval.top(bits)
                        elif base_t.elementaryTypeName and base_t.elementaryTypeName == "bool":
                            return BoolInterval.top()
                        elif base_t.elementaryTypeName and base_t.elementaryTypeName == "address":
                            return AddressSet.top()
                        elif isinstance(base_t, SolType) and base_t.typeCategory == "struct":
                            # 구조체 타입: 빈 구조체 생성 후 초기화
                            empty_struct = StructVariable(
                                f"{callerObject.identifier}[{idx}]",
                                base_t.structTypeName,
                                scope=callerObject.scope
                            )
                            ccf = self.an.contract_cfgs[self.an.current_target_contract]
                            if base_t.structTypeName in ccf.structDefs:
                                empty_struct.initialize_struct(ccf.structDefs[base_t.structTypeName])
                            return empty_struct
                        else:
                            # 기타 (bytes/string 등)는 symbol
                            return f"symbolic_{callerObject.identifier}[{idx}]"

                    elem = callerObject.elements[idx]
                    # 구조체나 배열 등 복합 타입이면 객체 자체 반환, 기본 타입이면 .value 반환
                    if isinstance(elem, (StructVariable, ArrayVariable, MappingVariable)):
                        return elem
                    return elem.value if hasattr(elem, "value") else elem

                # ── (B) 불확정(bottom 또는 [l,r] 범위) ─────────────────
                #      ⇒  배열 모든 요소의 join 을 반환 (구조체 포함)
                if callerObject.elements:
                    first_elem = callerObject.elements[0]

                    # 구조체 배열: 각 필드를 join하여 필드마다 TOP으로 만든 구조체 반환
                    if isinstance(first_elem, StructVariable):
                        return self._join_struct_fields(callerObject.elements)

                    # 기본 타입: 모든 값 join
                    elif not isinstance(first_elem, (ArrayVariable, MappingVariable)):
                        # # DEBUG: Check array access with interval index
                        # print(f"[ARRAY DEBUG] Accessing {callerObject.identifier} with interval index {ident_str}={iv}, elements count={len(callerObject.elements)}")
                        joined = None
                        for i, elem in enumerate(callerObject.elements):
                            val = getattr(elem, "value", elem)
                            # print(f"[ARRAY DEBUG]   element[{i}] = {val}")
                            joined = val if joined is None else joined.join(val)
                        # print(f"[ARRAY DEBUG]   joined result = {joined}")
                        return joined

                    # 배열/매핑 중첩: 첫 요소 그대로 반환 (복잡도 제한)
                    else:
                        return first_elem

                # 배열이 비어 있으면 base-type 에 맞는 TOP 반환
                base_t = callerObject.typeInfo.arrayBaseType

                # 구조체: 빈 구조체 생성 후 초기화
                if isinstance(base_t, SolType) and base_t.typeCategory == "struct":
                    empty_struct = StructVariable(
                        f"{callerObject.identifier}[virtual]",
                        base_t.structTypeName,
                        scope=callerObject.scope
                    )
                    # struct_defs가 필요하면 ContractAnalyzer에서 가져오기
                    ccf = self.an.contract_cfgs[self.an.current_target_contract]
                    if base_t.structTypeName in ccf.structDefs:
                        empty_struct.initialize_struct(ccf.structDefs[base_t.structTypeName])
                    return empty_struct

                # 기본형: TOP interval
                if base_t.elementaryTypeName and base_t.elementaryTypeName.startswith("uint"):
                    bits = base_t.intTypeLength or 256
                    return UnsignedIntegerInterval.top(bits)
                if base_t.elementaryTypeName and base_t.elementaryTypeName.startswith("int"):
                    bits = base_t.intTypeLength or 256
                    return IntegerInterval.top(bits)
                if base_t.elementaryTypeName and base_t.elementaryTypeName == "bool":
                    return BoolInterval.top()
                if base_t.elementaryTypeName and base_t.elementaryTypeName == "address":
                    return AddressSet.top()

                # 기타
                return f"symbolic_{callerObject.identifier}[<unk>]"

            elif isinstance(callerObject, StructVariable):
                if ident_str not in callerObject.members:
                    raise ValueError(f"member identifier '{ident_str}' not found in struct variables.")

                var = callerObject.members[ident_str]

                if isinstance(var, Variables):  # int, uint, bool이면 interval address, string이면 symbol을 리턴
                    return var.value
                else:  # ArrayVariable, StructVariable
                    return var  # var 자체를 리턴 (배열, 다른 구조체일 수 있음)

            elif isinstance(callerObject, EnumDefinition):
                for enumMemberIndex in range(len(callerObject.members)):
                    if ident_str == callerObject.members[enumMemberIndex]:
                        return enumMemberIndex

            # ContractAnalyzer.evaluate_identifier_context 내부

            elif isinstance(callerObject, MappingVariable):
                if not callerObject.struct_defs or not callerObject.enum_defs:
                    ccf = self.an.contract_cfgs[self.an.current_target_contract]
                    callerObject.struct_defs = ccf.structDefs
                    callerObject.enum_defs = ccf.enumDefs

                # ── ① key 결정 ──────────────────────────────────
                if ident_str in variables:  # ident_str == 변수명
                    key_var = variables[ident_str]
                    val = getattr(key_var, "value", key_var)

                    # ★ AddressSet: singleton이면 str(val)을 key로 사용
                    if isinstance(val, AddressSet):
                        if val.is_singleton():
                            key_val = str(val)  # "AddressSet({1})"
                        else:
                            key_val = key_var.identifier  # TOP/multi → identifier
                    elif hasattr(val, "min_value"):
                        if val.min_value == val.max_value:  # 숫자·bool 싱글톤
                            key_val = str(val.min_value)
                        else:
                            # TOP 범위인 경우: 매핑에 이미 설정된 키 중 범위 내 키가 있으면 사용
                            # (디버그 annotation으로 설정된 concrete 키 우선)
                            found_key = None
                            for existing_key in callerObject.mapping.keys():
                                try:
                                    k_int = int(existing_key)
                                    if val.min_value <= k_int <= val.max_value:
                                        found_key = existing_key
                                        break
                                except (ValueError, TypeError):
                                    continue
                            key_val = found_key if found_key else key_var.identifier
                    else:
                        key_val = key_var.identifier  # string·bool 등
                else:
                    # ───── 리터럴 키 ────────────────────────────
                    try:
                        key_val = str(int(ident_str, 0))
                    except ValueError:
                        key_val = ident_str

                # ── ③ 매핑 엔트리 가져오거나 생성 ─────────────
                if key_val not in callerObject.mapping:
                    callerObject.mapping[key_val] = callerObject.get_or_create(key_val)
                mvar = callerObject.mapping[key_val]
                # ── ④ 반환 규칙 ────────────────────────────
                if isinstance(mvar, (StructVariable, ArrayVariable, MappingVariable)):
                    return mvar
                else:
                    return mvar.value
            else:
                raise ValueError(f"This '{ident_str}' may not be included in enum def '{callerObject.enum_name}'")

        # callerObject가 없고 callerContext는 있는 경우
        if callerContext is not None:
            if callerContext == "MemberAccessContext":  # base에 대한 접근
                if ident_str in variables:
                    var = variables[ident_str]
                    # interface 타입 변수: AddressSet with _cast_interface → value 반환
                    if isinstance(var, Variables) and \
                       not isinstance(var, (ArrayVariable, StructVariable, MappingVariable)) and \
                       isinstance(getattr(var, 'value', None), AddressSet) and \
                       getattr(var.value, '_cast_interface', None):
                        return var.value
                    return var  # MappingVariable, StructVariable 자체를 리턴
                elif ident_str == "this":
                    # this 키워드: 현재 컨트랙트 자체를 반환
                    return "this"
                elif ident_str == "super":
                    return "super"
                elif ident_str in ["block", "tx", "msg", "address", "code"]:
                    return ident_str  # block, tx, msg를 리턴
                elif self._find_enum_in_chain(ident_str):  # EnumDef 리턴 (parent chain 포함)
                    return self._find_enum_in_chain(ident_str)
                elif ident_str in self.an.library_cfgs:
                    return {"isLibrary": True, "libraryName": ident_str}
                else:
                    raise ValueError(f"This '{ident_str}' is may be array or struct but may not be declared")
            elif callerContext == "IndexAccessContext":  # base에 대한 접근
                if ident_str in variables:
                    return variables[ident_str]  # ArrayVariable, MappingVariable 자체를 리턴

        # callerContext, callerObject 둘다 없는 경우
        if ident_str == "this":
            return "this"
        if ident_str in variables:  # variables에 있으면
            var_obj = variables[ident_str]
            # composite 타입(Struct/Array/Mapping)은 객체 자체를 반환
            if isinstance(var_obj, (StructVariable, ArrayVariable, MappingVariable)):
                return var_obj
            return var_obj.value  # 해당 value 리턴

        # library 이름이면 qualified call marker 반환 (UFixed18Lib._from(x) 등)
        if ident_str in self.an.library_cfgs:
            return {"isLibrary": True, "libraryName": ident_str}

        raise ValueError(f"This '{ident_str}' is may be elementary variable but may not be declared")

    def evaluate_member_access_context(
            self,
            expr: Expression,
            variables: dict[str, Variables],
            callerObject: Variables | None = None,
            callerContext: str | None = None):

        baseVal = self.evaluate_expression(expr.base, variables, None,
                                           "MemberAccessContext")
        member = expr.member

        # ──────────────────────────────────────────────────────────────
        # 0. Function call context 처리 (using directive 지원)
        # ──────────────────────────────────────────────────────────────
        # callerContext가 "functionCallContext"인 경우 - a.mul(b)에서 a.mul 부분이 호출될 때
        if callerContext == "functionCallContext":
            # baseVal이 Variables, mapping, Struct, 또는 interval인 경우 라이브러리 함수 호출 처리
            base_type = None
            implicit_arg = baseVal

            # 타입 추출
            if isinstance(baseVal, Variables):
                base_type = self._get_variable_type_string(baseVal)
            elif isinstance(baseVal, (UnsignedIntegerInterval, IntegerInterval)):
                # interval인 경우: expr.base에서 원래 타입(aliasName) 복원 시도
                alias_type = self._resolve_alias_from_expr(expr.base, variables)
                if alias_type:
                    base_type = alias_type
                else:
                    bits = getattr(baseVal, 'bits', 256)
                    if isinstance(baseVal, UnsignedIntegerInterval):
                        base_type = f"uint{bits}"
                    else:
                        base_type = f"int{bits}"

            if base_type:
                # 현재 컨트랙트의 using directive 확인
                current_contract = self.an.current_target_contract
                if current_contract and current_contract in self.an.contract_cfgs:
                    contract_cfg = self.an.contract_cfgs[current_contract]

                    # 라이브러리 함수 존재 여부만 확인 (overload 해소는 function call 시점에서)
                    library_function = contract_cfg.find_library_function(base_type, member)
                    if library_function:
                        result_expr = Expression(
                            function=Expression(identifier=member),
                            operator='library_call',
                            context='LibraryFunctionCallContext'
                        )
                        # overload 해소를 위한 정보 저장 (특정 FunctionCFG가 아닌 검색 키)
                        result_expr._library_base_type = base_type
                        result_expr._library_contract_cfg = contract_cfg
                        result_expr._implicit_first_arg = implicit_arg
                        return result_expr
        
        # ──────────────────────────────────────────────────────────────
        # 0-Q. Qualified library call (UFixed18Lib._from(x) 등)
        # ──────────────────────────────────────────────────────────────
        if isinstance(baseVal, dict) and baseVal.get("isLibrary"):
            lib_name = baseVal["libraryName"]
            lib_cfg = self.an.library_cfgs.get(lib_name)
            if lib_cfg and callerContext == "functionCallContext":
                result_expr = Expression(
                    function=Expression(identifier=member),
                    operator='library_call',
                    context='LibraryFunctionCallContext'
                )
                result_expr._library_base_type = None  # qualified call은 implicit first arg 없음
                result_expr._library_contract_cfg = lib_cfg
                result_expr._implicit_first_arg = None
                result_expr._qualified_library_call = True
                return result_expr
            # function call이 아닌 경우 (상수 등)
            if lib_cfg and member in getattr(lib_cfg, 'globals', {}):
                return lib_cfg.globals[member].value
            # state_variable_node에서 상수 조회
            sv_node = getattr(lib_cfg, 'state_variable_node', None)
            if sv_node and member in getattr(sv_node, 'variables', {}):
                sv = sv_node.variables[member]
                return sv.value if hasattr(sv, 'value') else sv
            return f"symbolic({lib_name}.{member})"

        # ──────────────────────────────────────────────────────────────
        # 0-1. super 키워드 처리 (super.foo() → 부모 컨트랙트 함수 호출)
        # ──────────────────────────────────────────────────────────────
        if isinstance(baseVal, str) and baseVal == "super":
            if callerContext == "functionCallContext":
                # super.foo() 형태의 함수 호출
                current_contract = self.an.current_target_contract
                if current_contract and current_contract in self.an.contract_cfgs:
                    contract_cfg = self.an.contract_cfgs[current_contract]

                    # 부모 컨트랙트에서만 함수 검색
                    parent_function = self.find_function_in_parent_only(contract_cfg, member)
                    if parent_function:
                        # super 함수 호출 Expression 반환
                        result_expr = Expression(
                            function=Expression(identifier=member),
                            operator='super_call',
                            context='SuperFunctionCallContext'
                        )
                        result_expr._super_function_cfg = parent_function
                        return result_expr

            # super를 함수 호출 외의 컨텍스트에서 사용한 경우
            return f"super.{member}"

        # ──────────────────────────────────────────────────────────────
        # 0-2. this 키워드 처리 (this.foo(), this.balance, address(this).balance 등)
        # ──────────────────────────────────────────────────────────────
        if isinstance(baseVal, str) and baseVal == "this":
            if callerContext == "functionCallContext":
                # this.foo() 형태의 함수 호출 → 현재 컨트랙트의 함수 호출
                current_contract = self.an.current_target_contract
                if current_contract and current_contract in self.an.contract_cfgs:
                    contract_cfg = self.an.contract_cfgs[current_contract]
                    this_function = self.find_function_in_hierarchy(contract_cfg, member)
                    if this_function:
                        # this 함수 호출 Expression 반환
                        result_expr = Expression(
                            function=Expression(identifier=member),
                            operator='this_call',
                            context='ThisFunctionCallContext'
                        )
                        result_expr._this_function_cfg = this_function
                        return result_expr
                # 함수를 찾지 못함 → Top 반환
                return UnsignedIntegerInterval.top()

            # this.balance → GlobalVar에 값이 있으면 사용, 없으면 Top
            if member == "balance":
                gv_val = self._get_address_this_balance(variables)
                return gv_val if gv_val is not None else UnsignedIntegerInterval.top()

            # 기타 this 멤버 접근은 심볼릭으로 처리
            return f"this.{member}"

        # ──────────────────────────────────────────────────────────────
        # 1. Global-var (block / msg / tx)
        # ──────────────────────────────────────────────────────────────
        if isinstance(baseVal, str):
            if baseVal in {"block", "msg", "tx"}:
                # 0) 함수-env 에 이미 변수로 들어와 있나?
                full_name = f"{baseVal}.{member}"
                if isinstance(callerObject, MappingVariable):
                    if not callerObject.struct_defs or not callerObject.enum_defs:
                        ccf = self.an.contract_cfgs[self.an.current_target_contract]
                        callerObject.struct_defs = ccf.structDefs
                        callerObject.enum_defs = ccf.enumDefs
                    # global var의 실제 값으로 key 결정 (identifier 경로와 동일)
                    key_val = full_name  # fallback
                    if full_name in variables:
                        gv_val = variables[full_name].value
                        if isinstance(gv_val, AddressSet):
                            if gv_val.is_singleton():
                                key_val = str(gv_val)  # "AddressSet({101})"
                            # else: TOP → full_name 유지
                        elif hasattr(gv_val, "min_value"):
                            if gv_val.min_value == gv_val.max_value:
                                key_val = str(gv_val.min_value)
                    if key_val not in callerObject.mapping:
                        callerObject.mapping[key_val] = callerObject.get_or_create(key_val)
                    entry = callerObject.mapping[key_val]
                    if isinstance(entry, (StructVariable, ArrayVariable, MappingVariable)):
                        return entry
                    return entry.value if hasattr(entry, "value") else entry

                else:
                    if full_name in variables:  # ← added
                        return variables[full_name].value  # (Variables → 값))
                    else:
                        raise ValueError(f"There is no global variable in function")

            if baseVal.startswith("type(") and member == "max":
                inner = baseVal[5:-1].strip()  # "uint256", "int224", "address", "MyERC20", ...
                m = member  # 읽기 편하게 별도 변수로

                if inner.startswith("uint") or inner.startswith("int"):
                    signed = inner.startswith("int")
                    bits_txt = inner.lstrip("uintint")  # '' 면 기본 256
                    bits = int(bits_txt) if bits_txt else 256
                    if signed:
                        i_min = -2 ** (bits - 1)
                        i_max = 2 ** (bits - 1) - 1
                        if m == "max":
                            return IntegerInterval(i_max, i_max, bits)
                        elif m == "min":
                            return IntegerInterval(i_min, i_min, bits)
                    else:
                        u_min = 0
                        u_max = 2 ** bits - 1
                        if m == "max":
                            return UnsignedIntegerInterval(u_max, u_max, bits)
                        elif m == "min":
                            return UnsignedIntegerInterval(u_min, u_min, bits)

                    # ---- address ------------------------------------------------------
                if inner == "address":
                    if m == "max":
                        # ★ address의 max는 모든 주소 가능 → TOP
                        return AddressSet.top()
                    if m == "min":
                        # ★ address의 min은 0 주소
                        return AddressSet(ids={0})

                    # ---- bytes<M>  (고정 길이) ----------------------------------------
                if inner.startswith("bytes") and inner != "bytes":
                    # 컴파일 타임 바이트 시퀀스 최대/최소 → 심볼릭 문자열이면 충분
                    return f"{inner}.{m}"  # 예: "bytes32.max"

                    # ---- 컨트랙트 타입  (MyERC20) --------------------------------------
                    # creationCode / runtimeCode / interfaceId
                if m in {"creationCode", "runtimeCode", "interfaceId"}:
                    return f"symbolic_{inner}_{m}"  # 심볼릭 스트링

                    # ---- type(SomeType).name ------------------------------------------
                if m == "name":
                    return inner  # 그냥 타입 이름 문자열

                    # ---- 기타 미지원 멤버 ---------------------------------------------
                return f"symbolicMeta({inner}.{m})"

            # address.code / address.code.length
            if baseVal == "code":
                if member == "length":
                    # 코드 사이즈 – 예시로 고정 상수
                    return UnsignedIntegerInterval(0, 24_000, 256)
                return member  # address.code → 다음 단계에서 .length 접근

            if member == "code":  # <addr>.code
                return "code"  # 상위 계층에서 재귀적으로 처리

            # interface cast된 address에서 interface 함수 호출 (IERC20(x).balanceOf())
            cast_ifc = getattr(baseVal, '_cast_interface', None)
            import sys as _s; print(f"[CAST-CHK] member={member}, baseVal={type(baseVal).__name__}, cast_ifc={cast_ifc}, callerCtx={callerContext}", file=_s.stderr) if member in ('delayedStrategyParams','delayedProtocolParams') else None
            if cast_ifc and callerContext == "functionCallContext":
                # interface function lookup → return type 기반 top 반환
                result_expr = Expression(
                    function=Expression(identifier=member),
                    operator='interface_call',
                    context='InterfaceFunctionCallContext'
                )
                result_expr._cast_interface = cast_ifc
                result_expr._cast_address = baseVal
                return result_expr

            raise ValueError(f"member '{member}' is not a recognised global-member.")

        # ──────────────────────────────────────────────────────────────
        # 2. ArrayVariable  ( .myArray.length  /  .push() / .pop() )
        # ──────────────────────────────────────────────────────────────
        if isinstance(baseVal, ArrayVariable):
            if member == "length":
                # ★ widening으로 TOP으로 표시된 경우 (-1)
                if baseVal.typeInfo.arrayLength == -1:
                    return UnsignedIntegerInterval(0, 2 ** 256 - 1, 256)

                # 동적 배열의 경우: 실제 elements 길이를 우선 사용
                # (typeInfo.arrayLength는 초기 선언 시의 값이고, 실제 길이는 elements로 결정)
                if baseVal.typeInfo.isDynamicArray:
                    if len(baseVal.elements) > 0:
                        # elements가 있으면 그 길이 반환
                        ln = len(baseVal.elements)
                        return UnsignedIntegerInterval(ln, ln, 256)
                    else:
                        # 빈 동적 배열: TOP 반환 (알 수 없는 길이)
                        return UnsignedIntegerInterval(0, 2 ** 256 - 1, 256)

                # 정적 배열의 경우: typeInfo.arrayLength 사용
                elif baseVal.typeInfo.arrayLength is not None:
                    return UnsignedIntegerInterval(baseVal.typeInfo.arrayLength, baseVal.typeInfo.arrayLength, 256)

                # 기타: elements 길이 반환
                else:
                    ln = len(baseVal.elements)
                    return UnsignedIntegerInterval(ln, ln, 256)

            # .push() / .pop()  – 동적배열만 허용
            if callerContext == "functionCallContext":
                if not baseVal.typeInfo.isDynamicArray:
                    raise ValueError("push / pop available only on dynamic arrays")
                elemType = baseVal.typeInfo.arrayBaseType

                if expr.member == "push":
                    # ★ widening 모드에서는 실제 push를 수행하지 않고 length를 TOP으로 추상화
                    engine = getattr(self.an, 'engine', None)
                    in_widening = engine and getattr(engine, '_in_widening_mode', False)

                    if in_widening:
                        # widening 중: 배열 길이를 TOP으로 추상화
                        # arrayLength를 특수값(-1)으로 설정하여 TOP임을 표시
                        # (elements는 유지하되, length 평가 시 TOP 반환하도록)
                        baseVal.typeInfo.arrayLength = -1  # -1 = TOP을 의미하는 특수값
                        return None
                    else:
                        # 정상 실행 또는 widening 전: 실제로 push 수행
                        if not expr.arguments:  # push()  – 값 없이
                            elem = baseVal._create_new_array_element(len(baseVal.elements))
                            baseVal.elements.append(elem)
                        else:  # push(v)
                            val = self.evaluate_expression(expr.arguments[0], variables)
                            elem = baseVal._create_new_array_element(len(baseVal.elements))
                            elem.value = val
                            baseVal.elements.append(elem)
                        return None  # Solidity push 는 값 반환 X

                    # pop()
                if expr.member == "pop":
                    if not baseVal.elements:  # 빈 배열 pop  →  ⊥ 또는 revert
                        return None  # 보수적으로 ⊥ 처리하려면 Interval.bottom(...) 반환
                    popped = baseVal.elements.pop()
                    return getattr(popped, "value", popped)  # 값이 있으면 값, 없으면 객체

            if member == "length":
                # 동적 배열인데 아직 push 로 단 1-개도 추가되지 않음
                if baseVal.typeInfo.isDynamicArray and not baseVal.elements:
                    # “얼마든지 될 수 있다”  →  ⊥(bottom) 으로 전파
                    #   • 이후 비교( >, == 등) 는 항상 불확정 TOP 으로 유지
                    return UnsignedIntegerInterval(None, None, 256)

                # 그 밖의 경우 → 현재 element 수를 singleton-interval 로
                ln = len(baseVal.elements)
                return UnsignedIntegerInterval(ln, ln, 256)

        # ──────────────────────────────────────────────────────────────
        # 3. StructVariable  ( struct.field )
        # ──────────────────────────────────────────────────────────────
        if isinstance(baseVal, StructVariable):
            if member not in baseVal.members:
                raise ValueError(f"'{member}' not in struct '{baseVal.identifier}'")

            nested = baseVal.members[member]

            # ① enum (저장형 uint) -----------------------------------------
            if isinstance(nested, EnumVariable):
                return nested.value  # Enum 은 값만 필요

            # ② leaf-variable ---------------------------------------------
            if (isinstance(nested, Variables) and
                    not isinstance(nested, (ArrayVariable,
                                            StructVariable,
                                            MappingVariable))):
                return nested.value  # int / uint / bool / address …

            # ③ 배열·구조체·매핑 ------------------------------------------
            return nested  # 객체 그대로 넘김

        # ──────────────────────────────────────────────────────────────
        # 3-A. AddressSet  (address.balance, address.transfer(), address.send())
        # ──────────────────────────────────────────────────────────────
        if isinstance(baseVal, AddressSet):
            # address.balance → GlobalVar에 address(this).balance가 있으면 사용
            if member == "balance":
                gv_val = self._get_address_this_balance(variables)
                return gv_val if gv_val is not None else UnsignedIntegerInterval.top()

            # address.code → bytes Top
            if member == "code":
                return "code"  # 상위 계층에서 .length 접근 처리

            # address.codehash → bytes32 Top
            if member == "codehash":
                return BytesSet.top(32)

            # 함수 호출 컨텍스트에서의 처리
            if callerContext == "functionCallContext":
                # address.transfer(amount) → void (reverts on failure)
                if member == "transfer":
                    # transfer는 실패 시 revert하므로 리턴값 없음
                    # 단순히 None 반환 (상태 변경 없음으로 가정)
                    return None

                # address.send(amount) → bool (true=success, false=failure)
                if member == "send":
                    # send는 성공/실패를 bool로 반환
                    return BoolInterval.top()  # [0,1] 둘 다 가능

                # address.call{value:...}() 등
                if member == "call":
                    # call은 (bool success, bytes memory data) 반환
                    # 단순화: Top 반환
                    return BoolInterval.top()

                # address.delegatecall(), staticcall()
                if member in ("delegatecall", "staticcall"):
                    return BoolInterval.top()

            # interface cast된 address의 함수 호출 (IERC20(x).balanceOf())
            cast_ifc = getattr(baseVal, '_cast_interface', None)
            if cast_ifc and callerContext == "functionCallContext":
                result_expr = Expression(
                    function=Expression(identifier=member),
                    operator='interface_call',
                    context='InterfaceFunctionCallContext'
                )
                result_expr._cast_interface = cast_ifc
                result_expr._cast_address = baseVal
                return result_expr

            # 기타 address 멤버는 심볼릭 처리
            return f"address.{member}"

        # ──────────────────────────────────────────────────────────────
        # 4. EnumDefinition  (EnumType.RED)
        # ──────────────────────────────────────────────────────────────
        if isinstance(baseVal, EnumDefinition):
            try:
                idx = baseVal.members.index(member)
                return UnsignedIntegerInterval(idx, idx, 256)
            except ValueError:
                raise ValueError(f"'{member}' not a member of enum '{baseVal.enum_name}'")

        # ──────────────────────────────────────────────────────────────
        # 5. Solidity type(uint).max / min  (baseVal == dict with "isType")
        # ──────────────────────────────────────────────────────────────
        if isinstance(baseVal, dict) and baseVal.get("isType"):
            T = baseVal["typeName"]
            if member not in {"max", "min"}:
                raise ValueError(f"Unsupported type property '{member}' for {T}")

            if T.startswith("uint"):
                bits = int(T[4:]) if len(T) > 4 else 256
                if member == "max":
                    mx = 2 ** bits - 1
                    return UnsignedIntegerInterval(mx, mx, bits)
                return UnsignedIntegerInterval(0, 0, bits)  # min

            if T.startswith("int"):
                bits = int(T[3:]) if len(T) > 3 else 256
                if member == "max":
                    mx = 2 ** (bits - 1) - 1
                    return IntegerInterval(mx, mx, bits)
                mn = -2 ** (bits - 1)
                return IntegerInterval(mn, mn, bits)

            raise ValueError(f"type() with unsupported base '{T}'")

        # ──────────────────────────────────────────────────────────────
        # 6. 기타 – 심볼릭 보수적 값
        # ──────────────────────────────────────────────────────────────
        return f"symbolic({baseVal}.{member})"

    def _get_variable_type_string(self, var: Variables) -> str:
        """Variables 객체에서 타입 문자열 추출"""
        if hasattr(var, 'typeInfo') and var.typeInfo:
            type_info = var.typeInfo
            if type_info.typeCategory == "elementary":
                # type alias가 있으면 원래 이름 반환 (library function lookup용)
                if getattr(type_info, 'aliasName', None):
                    return type_info.aliasName
                return type_info.elementaryTypeName
            elif type_info.typeCategory == "array":
                return f"{self._get_type_string_from_soltype(type_info.arrayBaseType)}[]"
            elif type_info.typeCategory == "mapping":
                return "mapping"
            elif type_info.typeCategory == "struct":
                return type_info.structTypeName
            elif type_info.typeCategory == "enum":
                return type_info.enumTypeName
        
        # 기본값으로 "unknown" 반환
        return "unknown"
    
    def _get_type_string_from_soltype(self, sol_type) -> str:
        """SolType 객체에서 타입 문자열 추출"""
        if sol_type.typeCategory == "elementary":
            return sol_type.elementaryTypeName
        elif sol_type.typeCategory == "array":
            return f"{self._get_type_string_from_soltype(sol_type.arrayBaseType)}[]"
        elif sol_type.typeCategory == "struct":
            return sol_type.structTypeName
        elif sol_type.typeCategory == "enum":
            return sol_type.enumTypeName
        else:
            return "unknown"

    def evaluate_index_access_context(self, expr, variables, callerObject=None, callerContext=None):
        """
        해석 로직:
          1) base_val = evaluate_expression(expr.base, variables, ..., callerContext="IndexAccessContext")
          2) index_val = evaluate_expression(expr.index, variables, callerObject=base_val, callerContext="IndexAccessContext")
          3) base_val이 ArrayVariable이면 -> arrayVar.elements[index]
             base_val이 MappingVariable이면 -> mappingVar.mapping[indexKey]
             그 외 -> symbolic/error
        """

        # 1) base 해석
        base_val = self.evaluate_expression(expr.base, variables, None, "IndexAccessContext")

        if expr.index is not None:
            return self.evaluate_expression(expr.index, variables, base_val, "IndexAccessContext")
        else:
            raise ValueError(f"There is no index expression")

    def evaluate_literal_with_subdenomination_context(
            self, expr: Expression, variables,
            callerObject=None, callerContext=None):
        """
        · expr.literal 은 이제 604800 처럼 *이미 환산된* 10진수 문자열이다.
        · 모든 sub-denom 값은 양수이므로 uint256 TOP 안에 들어간다.
        """

        lit_txt = expr.literal  # e.g. '604800'
        try:
            abs_val = int(lit_txt, 10)
        except ValueError:
            raise ValueError(f"Invalid pre-evaluated literal '{lit_txt}'")

        # uint256 상수 Interval 로 반환
        return UnsignedIntegerInterval(abs_val, abs_val, 256)

    def evaluate_type_conversion_context(self, expr, variables, callerObject=None, callerContext=None):
        """
        expr: Expression(operator='type_conversion', type_name=..., expression=subExpr, context='TypeConversionContext')
        예:  'uint256(x)', 'int8(y)', 'bool(z)', 'address w' 등

        1) sub_val = evaluate_expression(expr.expression, variables, None, "TypeConversion")
        2) if type_name.startswith('uint'):  -> UnsignedIntegerInterval로 클램핑
           if type_name.startswith('int'):   -> IntegerInterval로 클램핑
           if type_name == 'bool':           -> 0이면 False, 나머지면 True (또는 Interval [0,1])
           if type_name == 'address':        -> int/Interval -> symbolic address, string '0x...' 등등
        3) 반환
        """

        type_name = expr.typeName  # 예: "uint256", "int8", "bool", "address"
        sub_val = self.evaluate_expression(expr.expression, variables, None, "TypeConversion")

        # 1) 우선 sub_val이 Interval(혹은 BoolInterval), str, etc. 중 어느 것인가 확인
        #    편의상, 아래에서 Interval이면 클램핑, BoolInterval이면 bool 변환 등 처리

        # a. bool, int, uint, address 등으로 나누어 처리
        if type_name.startswith("uint"):
            # 예: "uint256", "uint8" 등
            # 1) bits 추출
            bits_str = "".join(ch for ch in type_name[4:] if ch.isdigit())  # "256" or "8" 등
            bits = int(bits_str) if bits_str else 256

            # 2) sub_val이 IntegerInterval/UnsignedIntegerInterval 이라면:
            #    - 음수 부분은 0으로 clamp
            #    - 상한은 2^bits - 1로 clamp
            #    - 만약 sub_val이 BoolInterval, string, etc. => 대략 변환 로직 / symbolic
            return self.convert_to_uint(sub_val, bits)

        elif type_name.startswith("int"):
            # 예: "int8", "int256"
            bits_str = "".join(ch for ch in type_name[3:] if ch.isdigit())
            bits = int(bits_str) if bits_str else 256
            return self.convert_to_int(sub_val, bits)

        elif type_name == "bool":
            # sub_val이 Interval이면:
            #   == 0 => bool false
            #   != 0 => bool true
            # 범위 넓으면 [0,1]
            return self.convert_to_bool(sub_val)

        elif type_name == "address":
            # ★ address 타입 변환
            if isinstance(sub_val, AddressSet):
                addr_result = sub_val
            elif isinstance(sub_val, (UnsignedIntegerInterval, IntegerInterval)):
                # uint → address: singleton이면 구체적 ID, 아니면 TOP
                if sub_val.is_bottom():
                    addr_result = AddressSet.bot()
                elif sub_val.min_value == sub_val.max_value:
                    addr_result = AddressSet(ids={sub_val.min_value})
                else:
                    addr_result = AddressSet.top()
            elif isinstance(sub_val, str) and sub_val.startswith("0x"):
                addr_int = int(sub_val, 16)
                addr_result = AddressSet(ids={addr_int})
            elif isinstance(sub_val, str) and sub_val == "this":
                # ★ address(this): 현재 컨트랙트 주소 (symbolic ID 1)
                addr_result = self.an.addr_mgr.make_symbolic_address(1, "this")
            else:
                addr_result = AddressSet.top()

            # ★ callerObject가 MappingVariable이면 mapping lookup 수행
            if isinstance(callerObject, MappingVariable):
                if not callerObject.struct_defs or not callerObject.enum_defs:
                    ccf = self.an.contract_cfgs[self.an.current_target_contract]
                    callerObject.struct_defs = ccf.structDefs
                    callerObject.enum_defs = ccf.enumDefs
                key_val = str(addr_result)
                if key_val not in callerObject.mapping:
                    callerObject.mapping[key_val] = callerObject.get_or_create(key_val)
                mvar = callerObject.mapping[key_val]
                if isinstance(mvar, (StructVariable, ArrayVariable, MappingVariable)):
                    return mvar
                return mvar.value

            return addr_result

        # ★ payable(addr) 타입 변환 - address와 동일하게 처리
        elif type_name == "payable" or type_name == "address payable":
            # payable은 Ether를 받을 수 있는 address - 추상 해석에서는 address와 동일
            if isinstance(sub_val, AddressSet):
                return sub_val  # 이미 AddressSet이면 그대로
            if isinstance(sub_val, (UnsignedIntegerInterval, IntegerInterval)):
                if sub_val.is_bottom():
                    return AddressSet.bot()
                if sub_val.min_value == sub_val.max_value:
                    return AddressSet(ids={sub_val.min_value})
                return AddressSet.top()
            if isinstance(sub_val, str) and sub_val.startswith("0x"):
                addr_int = int(sub_val, 16)
                return AddressSet(ids={addr_int})
            if isinstance(sub_val, str) and sub_val == "this":
                return self.an.addr_mgr.make_symbolic_address(1, "this")
            return AddressSet.top()

        # bytes32, bytes16 등 고정 크기 바이트 배열 타입 변환
        elif type_name.startswith("bytes") and len(type_name) > 5:
            byte_size = int(type_name[5:])  # "bytes32" -> 32
            # 이미 BytesSet이면 그대로
            if isinstance(sub_val, BytesSet):
                return sub_val
            # uint/int → bytes: singleton이면 구체적 값, 아니면 TOP
            if isinstance(sub_val, (UnsignedIntegerInterval, IntegerInterval)):
                if sub_val.is_bottom():
                    return BytesSet.bot(byte_size)
                if sub_val.min_value == sub_val.max_value:
                    return BytesSet(values={sub_val.min_value}, byte_size=byte_size)
                return BytesSet.top(byte_size)
            # 16진수 문자열 → bytes
            if isinstance(sub_val, str) and sub_val.startswith("0x"):
                try:
                    val_int = int(sub_val, 16)
                    return BytesSet(values={val_int}, byte_size=byte_size)
                except ValueError:
                    pass
            return BytesSet.top(byte_size)  # 기타 → symbolic TOP

        # interface/contract type cast: IERC20(_token), IVault(addr) 등
        elif type_name in self.an.interface_names or type_name in self.an.contract_cfgs:
            if isinstance(sub_val, AddressSet):
                result = sub_val
            elif isinstance(sub_val, (UnsignedIntegerInterval, IntegerInterval)):
                result = AddressSet.top()
            else:
                result = AddressSet.top()
            result._cast_interface = type_name
            return result

        else:
            # 그 외( string, etc. ) => 필요 시 구현
            return f"symbolicTypeConversion({type_name}, {sub_val})"

    def evaluate_conditional_expression_context(self, expr, variables, callerObject=None, callerContext=None):
        """
        삼항 연산자 (condition ? true_expr : false_expr)
        expr: Expression(
          condition=...,  # condition expression
          true_expr=...,  # true-branch expression
          false_expr=..., # false-branch expression
          operator='?:',
          context='ConditionalExpContext'
        )
        """

        # 1) 조건식 해석
        cond_val = self.evaluate_expression(expr.condition, variables, None, "ConditionalCondition")
        # cond_val이 BoolInterval일 가능성이 높음
        # 다른 경우(Interval 등) => symbolic or 0≠0 ?

        if isinstance(cond_val, BoolInterval):
            # (a) cond_val이 [1,1] => 항상 true
            if cond_val.min_value == 1 and cond_val.max_value == 1:
                return self.evaluate_expression(expr.true_expr, variables, callerObject, "ConditionalExp")

            # (b) cond_val이 [0,0] => 항상 false
            if cond_val.min_value == 0 and cond_val.max_value == 0:
                return self.evaluate_expression(expr.false_expr, variables, callerObject, "ConditionalExp")

            # (c) cond_val이 [0,1] => 부분적 => 두 branch 모두 해석 후 join
            true_val = self.evaluate_expression(expr.true_expr, variables, callerObject, "ConditionalExp")
            false_val = self.evaluate_expression(expr.false_expr, variables, callerObject, "ConditionalExp")

            # 두 결과가 모두 Interval이면 => join
            # (IntegerInterval, UnsignedIntegerInterval, BoolInterval 등)
            if (hasattr(true_val, 'join') and hasattr(false_val, 'join')
                    and type(true_val) == type(false_val)):
                return true_val.join(false_val)
            else:
                # 타입이 다르거나, join 메서드 없는 경우 => symbolic
                return f"symbolicConditional({true_val}, {false_val})"

        # 2) cond_val이 BoolInterval가 아님 => symbolic
        # 예: cond_val이 IntegerInterval => 0이 아닌 값은 true?
        # 여기서는 간단히 [0,∞]? => partial => symbolic
        return f"symbolicConditionalCondition({cond_val})"

    def evaluate_inline_array_expression_context(self, expr, variables, callerObject=None, callerContext=None):
        """
        expr: Expression(
           elements = [ expr1, expr2, ... ],
           expr_type = 'array',
           context   = 'InlineArrayExpressionContext'
        )

        이 배열 표현식은 예: [1,2,3], [0x123, 0x456], [true, false], ...
        각 요소를 재귀적으로 evaluate_expression으로 해석하고, 그 결과들을 리스트로 만든다.
        """

        results = []
        for elem_expr in expr.elements:
            # 각 요소를 재귀 해석
            # callerObject, callerContext는 "inline array element"로 명시
            val = self.evaluate_expression(elem_expr, variables, None, "InlineArrayElement")
            results.append(val)

        # -- 2) 여기서 optional로, 모든 요소가 Interval인지, BoolInterval인지, etc.를 확인해
        #       "동일한 타입"인지 검사하거나, 적절히 symbolic 처리할 수도 있음.
        # 여기서는 단순히 그대로 반환

        return results

    def evaluate_assignment_expression(self, expr, variables,
                                       callerObject=None, callerContext=None):
        """
        대입식이 ‘값을 돌려주는 표현식’ 으로 사용될 때 처리.
          예)  (z = x + y)
        ①  RHS 값을 계산
        ②  LHS 변수에 반영(update_left_var)
        ③  RHS 값을 그대로 반환
        """
        r_val = self.evaluate_expression(expr.right, variables, None, None)
        # LHS 쪽 환경 업데이트
        self.up.update_left_var(expr.left, r_val, '=', variables,
                             callerObject, callerContext, None, None, False)
        return r_val  # ← ‘값을 돌려주기’ 핵심!

    def evaluate_tuple_expression_context(self, expr, variables,
                                          callerObject=None, callerContext=None):
        # 각 요소 평가
        elems = [self.evaluate_expression(e, variables, None, "TupleElem")
                 for e in expr.elements]

        # (a) 요소가 1개뿐 ⇒ 괄호식이거나 return (X) 같은 형태
        if len(elems) == 1:
            return elems[0]  # <- Interval · 값 그대로 반환

        # (b) 진짜 튜플 (a,b,...) ⇒ 리스트 유지
        return elems  # [v1, v2, ...]

    def evaluate_unary_operator(self, expr, variables,
                                callerObject=None, callerContext=None):

        operand_val = self.evaluate_expression(expr.expression, variables, None, "Unary")

        if operand_val is None:
            raise ValueError(f"Unable to evaluate operand in unary expression: {expr}")

        op = expr.operator
        if op == '-':
            return operand_val.negate()
        elif op == '!':
            return operand_val.logical_not()
        elif op == '~':
            return operand_val.bitwise_not()
        elif op == 'delete':
            # 분석 단계에서는 “완전 미정” 값으로 — 스칼라는 0-singleton,
            # Interval 이면 같은 bit-width bottom 으로.
            if hasattr(operand_val, "bottom"):
                return operand_val.bottom(getattr(operand_val, "type_length", 256))
            return 0
        return

    def evaluate_binary_operator(self, expr, variables, callerObject=None, callerContext=None):
        leftInterval = self.evaluate_expression(expr.left, variables, None, "Binary")
        rightInterval = self.evaluate_expression(expr.right, variables, None, "Binary")
        operator = expr.operator

        result = None

        def _bottom(interval) -> "Interval":
            """
            interval 과 동일한 클래스·bit-width로 ⊥(bottom) 을 만들어 준다.
            (IntegerInterval.bottom(bits) 같은 헬퍼 통일)
            """
            if isinstance(interval, IntegerInterval):
                return IntegerInterval.bottom(interval.type_length)
            if isinstance(interval, UnsignedIntegerInterval):
                return UnsignedIntegerInterval.bottom(interval.type_length)
            if isinstance(interval, BoolInterval):
                return BoolInterval.bottom()
            return Interval(None, None)  # fallback – 거의 안 옴

        left_bottom = isinstance(leftInterval, Interval) and leftInterval.is_bottom()
        right_bottom = isinstance(rightInterval, Interval) and rightInterval.is_bottom()
        if left_bottom or right_bottom:
            # || : short-circuit — 한쪽이 true 가능하면 결과도 true 가능
            if operator == '||':
                if not left_bottom and isinstance(leftInterval, BoolInterval) and leftInterval.max_value == 1:
                    return BoolInterval(0, 1)
                if not right_bottom and isinstance(rightInterval, BoolInterval) and rightInterval.max_value == 1:
                    return BoolInterval(0, 1)
                return BoolInterval.bottom()
            # && : 한쪽이 BOTTOM이면 BOTTOM
            if operator in ['==', '!=', '<', '>', '<=', '>=', '&&']:
                return BoolInterval.bottom()
            return _bottom(leftInterval if not left_bottom else rightInterval)

        if operator == '+':
            result = leftInterval.add(rightInterval)
        elif operator == '-':
            result = leftInterval.subtract(rightInterval)
        elif operator == '*':
            result = leftInterval.multiply(rightInterval)
        elif operator == '/':
            result = leftInterval.divide(rightInterval)
        elif operator == '%':
            result = leftInterval.modulo(rightInterval)
        elif operator == '**':
            result = leftInterval.exponentiate(rightInterval)
        # 시프트 연산자 처리
        elif operator in ('<<', '>>', '>>>'):
            if (isinstance(leftInterval, IntegerInterval) and
                    isinstance(rightInterval, IntegerInterval)):
                result = leftInterval.shift(rightInterval, operator)

            elif (isinstance(leftInterval, UnsignedIntegerInterval) and
                  isinstance(rightInterval, UnsignedIntegerInterval)):
                result = leftInterval.shift(rightInterval, operator)

            else:
                raise ValueError(
                    f"Shift operands must both be int/uint intervals, got "
                    f"{type(leftInterval).__name__} and {type(rightInterval).__name__}"
                )
        # 비교 연산자 처리
        elif operator in ['==', '!=', '<', '>', '<=', '>=']:
            # ★ AddressSet 비교
            if isinstance(leftInterval, AddressSet) and isinstance(rightInterval, AddressSet):
                if operator == '==':
                    result = leftInterval.equals(rightInterval)
                elif operator == '!=':
                    result = leftInterval.not_equals(rightInterval)
                else:
                    # <, >, <=, >= 는 address에 대해 정의되지 않음
                    result = BoolInterval.top()
            # ★ BytesSet 비교
            elif isinstance(leftInterval, BytesSet) and isinstance(rightInterval, BytesSet):
                if operator == '==':
                    result = leftInterval.equals(rightInterval)
                elif operator == '!=':
                    result = leftInterval.not_equals(rightInterval)
                else:
                    # <, >, <=, >= 는 bytes에 대해 정의되지 않음 (Solidity에서)
                    result = BoolInterval.top()
            # 두 피연산자가 모두 Interval 계열인지 검사
            elif not (isinstance(leftInterval, (IntegerInterval,
                                              UnsignedIntegerInterval,
                                              BoolInterval))
                    and isinstance(rightInterval, (IntegerInterval,
                                                   UnsignedIntegerInterval,
                                                   BoolInterval))):
                # Interval 아니면 "결과 불확정" 으로 취급
                result = BoolInterval.top()  # [0,1]
            else:
                result = Evaluation.compare_intervals(
                    leftInterval, rightInterval, operator)
        # 논리 연산자 처리
        elif operator in ['&&', '||']:
            # 피연산자가 BoolInterval이 아닌 경우 변환
            if not isinstance(leftInterval, BoolInterval):
                leftInterval = BoolInterval.top()
            if not isinstance(rightInterval, BoolInterval):
                rightInterval = BoolInterval.top()
            result = leftInterval.logical_op(rightInterval, operator)
        else:
            raise ValueError(f"Unsupported operator '{operator}' in expression: {expr}")

        if isinstance(callerObject, ArrayVariable) or isinstance(callerObject, MappingVariable):
            return self.evaluate_binary_operator_of_index(result, callerObject)
        else:
            return result

    def evaluate_function_call_context(self, expr, variables, callerObject=None, callerContext=None):
        # [TRACE]
        _fn = getattr(expr, 'function', None)
        _fn_ctx = getattr(_fn, 'context', None) if _fn else None
        _fn_mem = getattr(_fn, 'member', None) if _fn else None
        if expr.context == "IdentifierExpContext":
            function_name = expr.identifier
        elif _fn and _fn_ctx == "MemberAccessContext":  # dynamic array에 대한 push, pop
            # ★ @IReturn: interface call이면 registry에서 값 조회 (evaluate 전에 short-circuit)
            base_expr = expr.function.base
            member_name = expr.function.member
            if hasattr(base_expr, 'identifier'):
                contract_var = base_expr.identifier
                fcfg = self.an.current_target_function_cfg
                interface_name = self._get_interface_name_of_var(contract_var, variables)
                if fcfg and interface_name:
                    ret = self._resolve_ireturn_pattern_a(
                        fcfg, interface_name, contract_var, member_name, callerObject)
                    if ret is not None:
                        return ret

            # ★ @IReturn Pattern B: explicit cast — IERC20(want).balanceOf() 등
            if (hasattr(base_expr, 'context') and base_expr.context == 'FunctionCallContext'
                    and hasattr(base_expr, 'function') and hasattr(base_expr.function, 'identifier')):
                cast_interface = base_expr.function.identifier
                fcfg = self.an.current_target_function_cfg
                if fcfg and cast_interface in self.an.interface_names:
                    addr_var = None
                    if base_expr.arguments and len(base_expr.arguments) == 1:
                        arg = base_expr.arguments[0]
                        if hasattr(arg, 'identifier'):
                            addr_var = arg.identifier
                    if addr_var:
                        ret = self._resolve_ireturn_pattern_b(
                            fcfg, cast_interface, addr_var, member_name, callerObject)
                        if ret is not None:
                            return ret

            # member access를 평가하여 라이브러리 함수인지 확인
            function_result = self.evaluate_expression(expr.function, variables, None, "functionCallContext")
            
            # 라이브러리 함수 호출인 경우
            if (isinstance(function_result, Expression) and
                hasattr(function_result, 'context') and
                function_result.context == 'LibraryFunctionCallContext'):

                # function call 시점에서 인자 개수로 overload resolution
                implicit_arg = function_result._implicit_first_arg
                is_qualified = getattr(function_result, '_qualified_library_call', False)
                n_explicit = len(expr.arguments) if expr.arguments else 0
                n_args = (n_explicit if is_qualified else 1 + n_explicit)  # qualified: implicit arg 없음
                func_name = function_result.function.identifier
                ccfg = function_result._library_contract_cfg
                base_type = function_result._library_base_type

                # qualified call: library CFG에서 직접 함수 검색
                if is_qualified:
                    lib_fcfg = ccfg.get_function_cfg(func_name)
                    # overload: 인자 개수로 매칭
                    if lib_fcfg and len(lib_fcfg.parameters) != n_args:
                        if func_name in ccfg.functions:
                            for sig, fc in ccfg.functions[func_name].items():
                                if len(fc.parameters) == n_args:
                                    lib_fcfg = fc
                                    break
                else:
                    # n_args를 전달하여 처음부터 올바른 overload 선택
                    lib_fcfg = ccfg.find_library_function(base_type, func_name, n_args=n_args)

                return self._mapping_lookup_if_needed(
                    self.evaluate_library_function_call_context(
                        expr, variables, implicit_arg, lib_fcfg),
                    callerObject)

            # interface cast 함수 호출인 경우 (IERC20(x).balanceOf())
            if (isinstance(function_result, Expression) and
                getattr(function_result, 'context', '') == 'InterfaceFunctionCallContext'):
                cast_ifc = function_result._cast_interface
                func_name = function_result.function.identifier
                cast_addr = getattr(function_result, '_cast_address', None)

                # IReturn registry 조회 (Pattern A/B에서 못 잡힌 경우)
                fcfg = self.an.current_target_function_cfg
                if fcfg and fcfg.ireturn_registry:
                    # cast_ifc 기반으로 entries 수집 시도
                    for prefix_len in (3, 2):  # Pattern B (4-tuple prefix 3) or A (3-tuple prefix 2)
                        for key in fcfg.ireturn_registry:
                            if len(key) >= prefix_len + 1 and \
                               key[0] == cast_ifc and key[prefix_len - 1] == func_name:
                                # 매칭되는 entries 수집
                                match_prefix = key[:prefix_len]
                                entries = self._collect_ireturn_entries(
                                    fcfg.ireturn_registry, match_prefix)
                                if entries:
                                    ret = self._assemble_ireturn_value(
                                        cast_ifc, func_name, entries, callerObject)
                                    if ret is not None:
                                        return ret
                                break

                # pkl에서 interface return type 조회 → top_from_soltype으로 반환
                import pickle, pathlib
                result = self._lookup_interface_return(cast_ifc, func_name)
                if result is not None:
                    return self._mapping_lookup_if_needed(result, callerObject)

                # fallback: uint256 top
                return self._mapping_lookup_if_needed(UnsignedIntegerInterval.top(), callerObject)

            # super 함수 호출인 경우 (super.foo())
            if (isinstance(function_result, Expression) and
                hasattr(function_result, 'context') and
                function_result.context == 'SuperFunctionCallContext'):

                # super 함수 호출로 처리
                return self._mapping_lookup_if_needed(
                    self.evaluate_super_function_call_context(
                        expr, variables, function_result._super_function_cfg),
                    callerObject)

            # this 함수 호출인 경우 (this.foo())
            if (isinstance(function_result, Expression) and
                hasattr(function_result, 'context') and
                function_result.context == 'ThisFunctionCallContext'):

                # this 함수 호출로 처리 (일반 함수 호출과 동일)
                return self._mapping_lookup_if_needed(
                    self.evaluate_this_function_call_context(
                        expr, variables, function_result._this_function_cfg),
                    callerObject)

            # 일반적인 member access 결과 반환 (dynamic array push/pop 등)
            return self._mapping_lookup_if_needed(function_result, callerObject)
            
        elif expr.function.context == "NewExpContext":
            # new Type[](size) → FunctionCall(NewExp, [size]) 로 파싱된 경우
            new_expr = expr.function
            if not new_expr.arguments:
                new_expr.arguments = expr.arguments
            return self.evaluate_new_expression_context(new_expr, variables, callerObject, callerContext)

        elif expr.function.context == "FunctionCallOptionContext":
            # expr{value: ethAmount}(args) → options는 무시, 외부 호출이므로 Top 반환
            return self._mapping_lookup_if_needed(
                self.evaluate_function_call_option_context(
                    expr.function, variables, callerObject, callerContext),
                callerObject)

        elif expr.function.context == "IdentifierExpContext":
            function_name = expr.function.identifier
        else:
            raise ValueError(f"There is no function name in function call context")

        # 1-B) Solidity built-in 함수 처리
        builtin_result = self._evaluate_builtin_function(function_name, expr, variables, callerObject)
        if builtin_result is not None:
            return builtin_result

        # 2) 현재 컨트랙트 CFG 가져오기
        contract_cfg = self.an.contract_cfgs.get(self.an.current_target_contract)
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.an.current_target_contract}")

        # 2-A) 구조체 생성자인지 확인 (현재 contract + parent chain + using libraries)
        found = self._find_struct_def(contract_cfg, function_name)
        if found is not None:
            struct_def, qualified_name = found
            new_struct = StructVariable(
                identifier=f"temp_{function_name}_{id(expr)}",
                struct_type=qualified_name,
                scope="memory"
            )
            new_struct.initialize_struct(struct_def)

            # named_arguments로 필드 초기화
            named_args = expr.named_arguments if expr.named_arguments else {}
            if named_args:
                for field_name, field_expr in named_args.items():
                    if field_name in new_struct.members:
                        field_value = self.evaluate_expression(field_expr, variables, None, None)
                        field_var = new_struct.members[field_name]
                        if isinstance(field_var, Variables):
                            field_var.value = field_value
            elif expr.arguments:
                # positional arguments: StructName(val1, val2, ...)
                member_names = list(new_struct.members.keys())
                for i, arg_expr in enumerate(expr.arguments):
                    if i < len(member_names):
                        field_value = self.evaluate_expression(arg_expr, variables, None, None)
                        field_var = new_struct.members[member_names[i]]
                        if isinstance(field_var, Variables):
                            field_var.value = field_value

            return new_struct

        # 3) 함수 CFG 가져오기 (상속 계층 포함 검색)
        function_cfg = self.find_function_in_hierarchy(contract_cfg, function_name)
        if not function_cfg:
            # 함수를 찾을 수 없음 → Top 반환 (외부 함수, interface 메서드, 미정의 함수)
            # ★ 아직 분석 안 된 함수일 수 있음 → pending_callee_name에 기록
            self.an.pending_callee_name = function_name
            # 반환 타입을 알 수 없으므로 uint256 Top으로 처리
            return self._mapping_lookup_if_needed(UnsignedIntegerInterval.top(), callerObject)

        # 4) 함수 파라미터와 인자 매핑
        #    expr.arguments -> 위치 기반 인자
        #    expr.named_arguments -> 키워드 인자
        arguments = expr.arguments if expr.arguments else []
        named_arguments = expr.named_arguments if expr.named_arguments else {}

        # 파라미터 목록
        param_names = getattr(function_cfg, 'parameters', [])
        total_params = len(param_names)
        total_args = len(arguments) + len(named_arguments)

        # overload 재검색: 인자 개수 불일치 시 같은 이름의 다른 overload 탐색
        if total_params != total_args and hasattr(contract_cfg, 'functions') and function_name in contract_cfg.functions:
            for sig, fcfg_candidate in contract_cfg.functions[function_name].items():
                if len(getattr(fcfg_candidate, 'parameters', [])) == total_args:
                    function_cfg = fcfg_candidate
                    param_names = function_cfg.parameters
                    total_params = len(param_names)
                    break

        if total_params != total_args:
            raise ValueError(f"Argument count mismatch in function call to '{function_name}': "
                             f"expected {total_params}, got {total_args}.")

        # 현재 함수 컨텍스트 저장
        saved_function = self.an.current_target_function
        self.current_target_function = function_name

        # 5) 인자 해석
        #    순서 기반 인자
        for i, arg_expr in enumerate(arguments):
            param_name = param_names[i]
            arg_val = self.evaluate_expression(arg_expr, variables, None, None)

            # function_cfg 내부의 related_variables에 param_name이 있어야
            if param_name in function_cfg.related_variables:
                param_var = function_cfg.related_variables[param_name]
                # struct 인자: StructVariable이면 members도 복사
                if hasattr(param_var, 'members') and hasattr(arg_val, 'members'):
                    param_var.members = {k: copy.deepcopy(v) for k, v in arg_val.members.items()}
                    param_var.value = arg_val.value
                elif hasattr(param_var, 'members') and arg_val is None:
                    # struct 파라미터에 None이 전달됨 → members 유지 (기본 초기화 상태)
                    pass
                else:
                    param_var.value = arg_val
            else:
                raise ValueError(f"Parameter '{param_name}' not found in function '{function_name}' variables.")
        #    named 인자
        #    (예: foo(a=1,b=2)) => paramName->index 매핑이 필요할 수 있음
        #    여기서는 paramName가 function_cfg.parameters[i]와 동일한지 가정
        param_offset = len(arguments)
        for i, (key, expr_val) in enumerate(named_arguments.items()):
            if key not in param_names:
                raise ValueError(f"Unknown named parameter '{key}' in function '{function_name}'.")
            arg_val = self.evaluate_expression(expr_val, variables, None, f"CallNamedArg({function_name})")

            if key in function_cfg.related_variables:
                function_cfg.related_variables[key].value = arg_val
            else:
                raise ValueError(f"Parameter '{key}' not found in function '{function_name}' variables.")

        # 6) 실제 함수 CFG 해석
        #    caller env는 interpret_function_cfg 내에서 start_block.variables에 병합됨
        #    related_variables는 함수 정의 시점의 변수 집합이므로 수정하지 않음
        return_value = self.engine.interpret_function_cfg(function_cfg, variables)

        # 7) 함수 컨텍스트 복원
        self.an.current_target_function = saved_function

        return self._mapping_lookup_if_needed(return_value, callerObject)

    def evaluate_library_function_call_context(self, expr, variables, implicit_first_arg, library_function_cfg):
        """
        라이브러리 함수 호출 처리
        expr: 원래 FunctionCallContext Expression 객체 (arguments 포함)
        implicit_first_arg: 첫 번째 인자로 전달될 baseVal (Variables 객체)
        library_function_cfg: 라이브러리 함수의 FunctionCFG
        """
        if not library_function_cfg:
            return f"symbolic_library_call(unknown_function)"

        # 1) 인자 준비 - implicit_first_arg가 있으면 첫 번째 인자로 설정
        arguments = []
        if implicit_first_arg is not None:
            arguments.append(implicit_first_arg)
        if expr.arguments:
            arguments.extend(expr.arguments)

        # 2) 파라미터와 인자 매핑
        param_names = getattr(library_function_cfg, 'parameters', [])

        if len(param_names) > len(arguments):
            for _ in range(len(param_names) - len(arguments)):
                arguments.append("")
        elif len(param_names) < len(arguments):
            return f"symbolic_library_call_mismatch({expr.function.identifier})"

        # 3) 파라미터는 related_variables에 설정, caller_env에는 나머지만
        #    related_variables 수정은 파라미터에 한정 (다른 함수의 변수 오염 방지)
        caller_env = variables.copy()

        for i, param_name in enumerate(param_names):
            if isinstance(arguments[i], (StructVariable, ArrayVariable, MappingVariable)):
                # 복합 타입: 객체 자체를 파라미터로 설정
                library_function_cfg.related_variables[param_name] = arguments[i]
            elif isinstance(arguments[i], Variables):
                arg_val = arguments[i].value if hasattr(arguments[i], 'value') else arguments[i]
                if param_name in library_function_cfg.related_variables:
                    library_function_cfg.related_variables[param_name].value = arg_val
                else:
                    param_var = Variables(identifier=param_name, scope="local")
                    param_var.value = arg_val
                    library_function_cfg.related_variables[param_name] = param_var
            elif isinstance(arguments[i], (UnsignedIntegerInterval, IntegerInterval)):
                if param_name in library_function_cfg.related_variables:
                    library_function_cfg.related_variables[param_name].value = arguments[i]
                else:
                    param_var = Variables(identifier=param_name, scope="local")
                    param_var.value = arguments[i]
                    library_function_cfg.related_variables[param_name] = param_var
            elif isinstance(arguments[i], str):
                if param_name in library_function_cfg.related_variables:
                    library_function_cfg.related_variables[param_name].value = arguments[i]
                else:
                    param_var = Variables(identifier=param_name, scope="local")
                    param_var.value = arguments[i]
                    library_function_cfg.related_variables[param_name] = param_var
            else:
                arg_val = self.evaluate_expression(arguments[i], variables, None, None)
                # evaluate 결과가 복합 타입이면 객체 자체를 파라미터로 설정
                if isinstance(arg_val, (StructVariable, ArrayVariable, MappingVariable)):
                    library_function_cfg.related_variables[param_name] = arg_val
                elif param_name in library_function_cfg.related_variables:
                    library_function_cfg.related_variables[param_name].value = arg_val
                else:
                    param_var = Variables(identifier=param_name, scope="local")
                    param_var.value = arg_val
                    library_function_cfg.related_variables[param_name] = param_var

        # 4) 라이브러리 함수 실행
        try:
            saved_function = self.an.current_target_function
            saved_function_cfg = self.an.current_target_function_cfg

            self.an.current_target_function = library_function_cfg.function_name
            self.an.current_target_function_cfg = library_function_cfg

            # 라이브러리의 constant 변수들을 caller_env에 추가
            library_cfg = None
            for lib_name, lib_cfg in self.an.library_cfgs.items():
                if library_function_cfg in [f for _, f in lib_cfg.iter_all_functions()]:
                    library_cfg = lib_cfg
                    break

            if library_cfg and library_cfg.state_variable_node:
                for var_name, var_obj in library_cfg.state_variable_node.variables.items():
                    if var_name not in caller_env:
                        caller_env[var_name] = var_obj

            return_value = self.engine.interpret_function_cfg(library_function_cfg, caller_env)


            # 함수 컨텍스트 복원
            self.an.current_target_function = saved_function
            self.an.current_target_function_cfg = saved_function_cfg
            
            return return_value
            
        except Exception as e:
            # 오류 발생 시 symbolic 값 반환
            import traceback
            print(f"[LIBRARY CALL ERROR] {expr.function.identifier}: {str(e)}")
            traceback.print_exc()
            return f"symbolic_library_error({expr.function.identifier}: {str(e)})"

    def evaluate_super_function_call_context(self, expr, variables, super_function_cfg):
        """
        super 함수 호출 처리 (super.foo())
        부모 컨트랙트의 함수를 호출한다.

        Args:
            expr: 원래 FunctionCallContext Expression 객체 (arguments 포함)
            variables: 현재 변수 환경
            super_function_cfg: 부모 컨트랙트의 함수 FunctionCFG
        """
        if not super_function_cfg:
            return f"symbolic_super_error(function not found)"

        # 1) 함수 파라미터 정보
        param_names = getattr(super_function_cfg, 'parameters', [])

        # 2) 인자 준비
        arguments = expr.arguments if expr.arguments else []
        named_arguments = expr.named_arguments if expr.named_arguments else {}

        total_params = len(param_names)
        total_args = len(arguments) + len(named_arguments)

        if total_params != total_args:
            return f"symbolic_super_error(arg count mismatch: expected {total_params}, got {total_args})"

        # 3) 인자 값 설정
        caller_env = variables.copy()

        for i, arg_expr in enumerate(arguments):
            param_name = param_names[i]
            arg_val = self.evaluate_expression(arg_expr, variables, None, None)

            if param_name in super_function_cfg.related_variables:
                super_function_cfg.related_variables[param_name].value = arg_val
            else:
                from Domain.Variable import Variables as Var
                param_var = Var(identifier=param_name, scope="local")
                param_var.value = arg_val
                super_function_cfg.related_variables[param_name] = param_var

        # named arguments 처리
        for key, expr_val in named_arguments.items():
            if key in param_names:
                arg_val = self.evaluate_expression(expr_val, variables, None, None)
                if key in super_function_cfg.related_variables:
                    super_function_cfg.related_variables[key].value = arg_val

        # 4) caller env를 callee에 병합
        for k, v in variables.items():
            super_function_cfg.related_variables.setdefault(k, v)

        # 5) 부모 함수 CFG 실행
        try:
            saved_function = self.an.current_target_function
            saved_function_cfg = self.an.current_target_function_cfg

            self.an.current_target_function = super_function_cfg.function_name
            self.an.current_target_function_cfg = super_function_cfg

            return_value = self.engine.interpret_function_cfg(super_function_cfg, caller_env)

            self.an.current_target_function = saved_function
            self.an.current_target_function_cfg = saved_function_cfg

            return return_value

        except Exception as e:
            return f"symbolic_super_error({super_function_cfg.function_name}: {str(e)})"

    def evaluate_this_function_call_context(self, expr, variables, this_function_cfg):
        """
        this 함수 호출 처리 (this.foo())
        현재 컨트랙트의 함수를 external call로 호출한다.
        Solidity에서 this.foo()는 external call이지만, 추상 해석에서는 일반 함수 호출과 동일하게 처리.

        Args:
            expr: 원래 FunctionCallContext Expression 객체 (arguments 포함)
            variables: 현재 변수 환경
            this_function_cfg: 현재 컨트랙트의 함수 FunctionCFG
        """
        if not this_function_cfg:
            return UnsignedIntegerInterval.top()  # 함수를 찾지 못하면 Top 반환

        # 1) 함수 파라미터 정보
        param_names = getattr(this_function_cfg, 'parameters', [])

        # 2) 인자 준비
        arguments = expr.arguments if expr.arguments else []
        named_arguments = expr.named_arguments if expr.named_arguments else {}

        total_params = len(param_names)
        total_args = len(arguments) + len(named_arguments)

        if total_params != total_args:
            return f"symbolic_this_error(arg count mismatch: expected {total_params}, got {total_args})"

        # 3) 인자 값 설정
        caller_env = variables.copy()

        for i, arg_expr in enumerate(arguments):
            param_name = param_names[i]
            arg_val = self.evaluate_expression(arg_expr, variables, None, None)

            if param_name in this_function_cfg.related_variables:
                this_function_cfg.related_variables[param_name].value = arg_val
            else:
                from Domain.Variable import Variables as Var
                param_var = Var(identifier=param_name, scope="local")
                param_var.value = arg_val
                this_function_cfg.related_variables[param_name] = param_var

        # named arguments 처리
        for key, expr_val in named_arguments.items():
            if key in param_names:
                arg_val = self.evaluate_expression(expr_val, variables, None, None)
                if key in this_function_cfg.related_variables:
                    this_function_cfg.related_variables[key].value = arg_val

        # 4) caller env를 callee에 병합
        for k, v in variables.items():
            this_function_cfg.related_variables.setdefault(k, v)

        # 5) 함수 CFG 실행
        try:
            saved_function = self.an.current_target_function
            saved_function_cfg = self.an.current_target_function_cfg

            self.an.current_target_function = this_function_cfg.function_name
            self.an.current_target_function_cfg = this_function_cfg

            return_value = self.engine.interpret_function_cfg(this_function_cfg, caller_env)

            self.an.current_target_function = saved_function
            self.an.current_target_function_cfg = saved_function_cfg

            return return_value

        except Exception as e:
            return f"symbolic_this_error({this_function_cfg.function_name}: {str(e)})"

    def update_mapping_in_cfg(self, mapVarName: str, key_str: str, new_var_obj: Variables):
        """
        mapVarName: "myMapping"
        key_str: "someKey"
        new_var_obj: 새로 만든 Variables(...) for the mapping value
        여기에 state_variable_node, function_cfg 등을 업데이트
        """
        contract_cfg = self.an.contract_cfgs.get(self.an.current_target_contract)
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.an.current_target_contract}")

        # state_variable_node 갱신
        if contract_cfg.state_variable_node and mapVarName in contract_cfg.state_variable_node.variables:
            mapVar = contract_cfg.state_variable_node.variables[mapVarName]
            if isinstance(mapVar, MappingVariable):
                mapVar.mapping[key_str] = new_var_obj

        # 함수 CFG 갱신
        function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if function_cfg:
            if mapVarName in function_cfg.related_variables:
                mapVar2 = function_cfg.related_variables[mapVarName]
                if isinstance(mapVar2, MappingVariable):
                    mapVar2.mapping[key_str] = new_var_obj

    def convert_to_uint(self, sub_val, bits):
        """
        sub_val을 uintN 범위 [0 .. 2^bits−1] 로 변환/클램프
        """
        type_max = (1 << bits) - 1  # 2**bits - 1 과 동일

        # ────────────────────────────────────────────────────────
        # 1) Interval 계열 (Unsigned / Integer)
        # ────────────────────────────────────────────────────────
        if isinstance(sub_val, (UnsignedIntegerInterval, IntegerInterval)):
            if sub_val.is_bottom():  # ★ bottom 우선 검사
                return UnsignedIntegerInterval(None, None, bits)

            new_min = max(0, sub_val.min_value)
            new_max = min(type_max, sub_val.max_value)
            if new_min > new_max:  # 교집합이 공집합
                return UnsignedIntegerInterval(None, None, bits)

            return UnsignedIntegerInterval(new_min, new_max, bits)

        # ────────────────────────────────────────────────────────
        # 2) BoolInterval  (0 또는 1)
        # ────────────────────────────────────────────────────────
        if isinstance(sub_val, BoolInterval):
            return UnsignedIntegerInterval(
                sub_val.min_value, sub_val.max_value, bits
            )  # 이미 0‥1 범위

        # ────────────────────────────────────────────────────────
        # 3) 문자열(리터럴·symbolic) → symbolic 래퍼
        # ────────────────────────────────────────────────────────
        if isinstance(sub_val, str):
            return f"symbolicUint{bits}({sub_val})"

        # ────────────────────────────────────────────────────────
        # 4) 기타(정수 등) → 그대로 Interval 로 래핑
        # ────────────────────────────────────────────────────────
        try:
            v = int(sub_val)
            v = max(0, min(type_max, v))
            return UnsignedIntegerInterval(v, v, bits)
        except (ValueError, TypeError):
            return f"symbolicUint{bits}({sub_val})"

    def convert_to_int(self, sub_val, bits):
        """
        주어진 sub_val(Interval·리터럴·symbolic)을
        signed int<bits> 범위 [-2^(bits-1) .. 2^(bits-1)-1] 로 변환/클램프한다.
        """
        type_min = -(1 << (bits - 1))
        type_max = (1 << (bits - 1)) - 1

        # ────────────────────────────────────────────────────────
        # 1) Interval → Interval
        #    ⊥(bottom) 은 그대로 bottom 반환
        # ────────────────────────────────────────────────────────
        if isinstance(sub_val, (IntegerInterval, UnsignedIntegerInterval)):
            if sub_val.is_bottom():  # ★ bottom 체크
                return IntegerInterval(None, None, bits)

            new_min = max(type_min, sub_val.min_value)
            new_max = min(type_max, sub_val.max_value)
            if new_min > new_max:  # 교집합이 공집합
                return IntegerInterval(None, None, bits)
            return IntegerInterval(new_min, new_max, bits)

        # ────────────────────────────────────────────────────────
        # 2) BoolInterval → 0/1 로 압축 후 위와 동일
        # ────────────────────────────────────────────────────────
        if isinstance(sub_val, BoolInterval):
            # 0‥1 과 int<bits> 의 교집합은 그대로 0‥1
            return IntegerInterval(
                max(type_min, sub_val.min_value),
                min(type_max, sub_val.max_value),
                bits
            )

        # ────────────────────────────────────────────────────────
        # 3) 문자열(리터럴·심볼릭)  → 그대로 symbolic 래퍼
        # ────────────────────────────────────────────────────────
        if isinstance(sub_val, str):
            return f"symbolicInt{bits}({sub_val})"

        # ────────────────────────────────────────────────────────
        # 4) 기타(정수 등) → 그대로 Interval 로 래핑
        # ────────────────────────────────────────────────────────
        try:
            v = int(sub_val)
            v = max(type_min, min(type_max, v))  # 범위 클램프
            return IntegerInterval(v, v, bits)
        except (ValueError, TypeError):
            return f"symbolicInt{bits}({sub_val})"

    def evaluate_type_wrap_unwrap(self, expr, variables, callerObject=None, callerContext=None):
        """
        user-defined value type의 wrap/unwrap 처리.
        Fixed18.wrap(100) → int256 interval로 변환
        Fixed18.unwrap(a) → underlying type interval로 변환
        """
        type_name = expr.identifier       # "Fixed18", "UFixed18"
        method = expr.member               # "wrap" or "unwrap"
        args = expr.arguments or []

        if not args:
            return UnsignedIntegerInterval.top()

        # 인자 evaluate
        arg_val = self.evaluate_expression(args[0], variables, None, None)

        # underlying type 조회
        underlying = self.an.sa.resolve_type(type_name)
        if underlying is None:
            return arg_val  # fallback

        # underlying type에 맞는 interval로 변환
        if underlying.startswith("int"):
            bits = int(underlying[3:]) if len(underlying) > 3 else 256
            if VariableEnv.is_interval(arg_val):
                return IntegerInterval(arg_val.min_value, arg_val.max_value, bits)
            elif isinstance(arg_val, (int, float)):
                return IntegerInterval(int(arg_val), int(arg_val), bits)
            return IntegerInterval.top(bits)
        elif underlying.startswith("uint"):
            bits = int(underlying[4:]) if len(underlying) > 4 else 256
            if VariableEnv.is_interval(arg_val):
                return UnsignedIntegerInterval(arg_val.min_value, arg_val.max_value, bits)
            elif isinstance(arg_val, (int, float)):
                return UnsignedIntegerInterval(int(arg_val), int(arg_val), bits)
            return UnsignedIntegerInterval.top(bits)
        elif underlying == "bool":
            if isinstance(arg_val, BoolInterval):
                return arg_val
            return BoolInterval.top()

        return arg_val  # 기타 타입은 그대로

    def _resolve_alias_from_expr(self, base_expr, variables) -> str | None:
        """expr.base에서 원래 타입의 aliasName을 복원.
        1) Identifier → variables에서 조회
        2) MemberAccess on struct → struct 멤버의 typeInfo 조회
        3) 그 외 → None + error 출력"""
        if base_expr is None:
            return None

        # 1) Identifier: someVar.add(...)
        if getattr(base_expr, 'context', None) == 'IdentifierExpContext':
            ident = base_expr.identifier
            var = variables.get(ident)
            if var and hasattr(var, 'typeInfo') and var.typeInfo:
                return getattr(var.typeInfo, 'aliasName', None)
            return None

        # 2) MemberAccess: self.shortfall.add(...)
        if getattr(base_expr, 'context', None) == 'MemberAccessContext':
            member_name = base_expr.member
            # global keyword (block, msg, tx) base는 alias 없음
            base_ident = getattr(base_expr.base, 'identifier', None)
            if base_ident in ('block', 'msg', 'tx'):
                return None
            try:
                base_val = self.evaluate_expression(base_expr.base, variables, None, None)
            except (ValueError, KeyError):
                return None
            if isinstance(base_val, StructVariable) and member_name in base_val.members:
                member_var = base_val.members[member_name]
                if hasattr(member_var, 'typeInfo') and member_var.typeInfo:
                    return getattr(member_var.typeInfo, 'aliasName', None)
            return None

        # 3) TupleExpression: (expr).method() → 괄호 벗기고 재귀
        if getattr(base_expr, 'context', None) == 'TupleExpressionContext':
            inner = getattr(base_expr, 'elements', None)
            if inner and len(inner) == 1:
                return self._resolve_alias_from_expr(inner[0], variables)

        # 4) IndexAccess: balances[_to].add(...) → 평가해서 Variables typeInfo 확인
        if getattr(base_expr, 'context', None) == 'IndexAccessContext':
            try:
                val = self.evaluate_expression(base_expr, variables, None, None)
                if isinstance(val, Variables) and hasattr(val, 'typeInfo') and val.typeInfo:
                    return getattr(val.typeInfo, 'aliasName', None)
            except (ValueError, KeyError, AttributeError):
                pass
            return None

        # 5) FunctionCall: value.div(100000).mul(...) → 체이닝, base object 재귀 추적
        if getattr(base_expr, 'context', None) == 'FunctionCallContext':
            func_expr = getattr(base_expr, 'function', None) or getattr(base_expr, 'base', None)
            if func_expr and getattr(func_expr, 'context', None) == 'MemberAccessContext':
                result = self._resolve_alias_from_expr(func_expr.base, variables)
                if result:
                    return result
                # base가 library 이름인 경우: using directive에서 역추적
                lib_ident = getattr(func_expr.base, 'identifier', None)
                if lib_ident and lib_ident in self.an.library_cfgs:
                    contract_name = self.an.current_target_contract
                    ccfg = self.an.contract_cfgs.get(contract_name)
                    if ccfg:
                        for type_name, libs in ccfg.using_libraries.items():
                            for lib in libs:
                                lib_name = getattr(lib, 'library_name', None) or getattr(lib, 'contract_name', None)
                                if lib_name == lib_ident:
                                    return type_name
            return None

        # 6) 그 외: alias 없음
        return None

    def _find_struct_def(self, contract_cfg, struct_name):
        """struct 정의를 현재 contract, parent chain, using libraries에서 검색.
        Returns: (struct_def, qualified_name) 또는 None"""
        # 1) 현재 contract
        if struct_name in contract_cfg.structDefs:
            return contract_cfg.structDefs[struct_name], struct_name
        # 2) parent chain
        for parent_cfg in getattr(contract_cfg, 'parent_cfgs', {}).values():
            if struct_name in parent_cfg.structDefs:
                return parent_cfg.structDefs[struct_name], struct_name
        # 3) using libraries
        all_libs = []
        for libs in getattr(contract_cfg, 'using_libraries', {}).values():
            all_libs.extend(libs if isinstance(libs, list) else [libs])
        all_libs.extend(getattr(contract_cfg, 'using_all_libraries', []))
        for lib in all_libs:
            if struct_name in lib.structDefs:
                qualified = f"{lib.library_name}.{struct_name}"
                return lib.structDefs[struct_name], qualified
        # 4) library_cfgs 직접 검색
        for lib_name, lib_cfg in self.an.library_cfgs.items():
            if struct_name in lib_cfg.structDefs:
                qualified = f"{lib_name}.{struct_name}"
                return lib_cfg.structDefs[struct_name], qualified
        return None

    def _evaluate_builtin_function(self, function_name, expr, variables, callerObject):
        """Solidity built-in 함수 처리. 해당하면 결과 반환, 아니면 None."""
        args = expr.arguments or []

        # addmod(a, b, n) → (a + b) % n
        if function_name == "addmod" and len(args) == 3:
            a = self.evaluate_expression(args[0], variables, None, None)
            b = self.evaluate_expression(args[1], variables, None, None)
            n = self.evaluate_expression(args[2], variables, None, None)
            if VariableEnv.is_interval(a) and VariableEnv.is_interval(b) and VariableEnv.is_interval(n):
                return self._mapping_lookup_if_needed(a.add(b).modulo(n), callerObject)
            return self._mapping_lookup_if_needed(UnsignedIntegerInterval.top(), callerObject)

        # mulmod(a, b, n) → (a * b) % n
        if function_name == "mulmod" and len(args) == 3:
            a = self.evaluate_expression(args[0], variables, None, None)
            b = self.evaluate_expression(args[1], variables, None, None)
            n = self.evaluate_expression(args[2], variables, None, None)
            if VariableEnv.is_interval(a) and VariableEnv.is_interval(b) and VariableEnv.is_interval(n):
                return self._mapping_lookup_if_needed(a.multiply(b).modulo(n), callerObject)
            return self._mapping_lookup_if_needed(UnsignedIntegerInterval.top(), callerObject)

        # keccak256, sha256, ripemd160, blockhash → TOP (bytes32)
        if function_name in ("keccak256", "sha256", "ripemd160", "blockhash"):
            return self._mapping_lookup_if_needed(UnsignedIntegerInterval.top(), callerObject)

        # ecrecover → TOP (address)
        if function_name == "ecrecover":
            return self._mapping_lookup_if_needed(AddressSet.top(), callerObject)

        # gasleft → TOP (uint256)
        if function_name == "gasleft":
            return self._mapping_lookup_if_needed(UnsignedIntegerInterval.top(), callerObject)

        return None  # built-in이 아님

    def _get_address_this_balance(self, variables):
        """GlobalVar에서 address(this).balance 값을 조회. 없으면 None."""
        gv_name = "address(this).balance"
        # 1) variables(함수 env)에 있는지
        if gv_name in variables:
            v = variables[gv_name]
            return v.value if hasattr(v, "value") else v
        # 2) contract globals에 있는지
        contract_name = self.an.current_target_contract
        if contract_name and contract_name in self.an.contract_cfgs:
            cfg = self.an.contract_cfgs[contract_name]
            if gv_name in cfg.globals:
                g = cfg.globals[gv_name]
                return g.value
        return None

    def convert_to_bool(self, sub_val):
        """
        int/uint interval -> 0 => false, !=0 => true => [0,1] 형태
        """
        if isinstance(sub_val, IntegerInterval) or isinstance(sub_val, UnsignedIntegerInterval):
            if sub_val.is_bottom():
                return BoolInterval(None, None)
            # if entire range is strictly 0..0 => false
            if sub_val.min_value == 0 and sub_val.max_value == 0:
                return BoolInterval(0, 0)
            # if entire range is non-zero => true => [1,1]
            if sub_val.min_value > 0:
                return BoolInterval(1, 1)
            # if partial includes 0 and nonzero => [0,1]
            return BoolInterval(0, 1)

        elif isinstance(sub_val, BoolInterval):
            # 이미 bool => 그대로 반환 가능
            return sub_val

        elif isinstance(sub_val, str):
            # string => symbolic bool
            return BoolInterval(0, 1)

        # fallback
        return BoolInterval(0, 1)

    def evaluate_binary_operator_of_index(self, result, callerObject):
        def array_base_is_address(arr: ArrayVariable) -> bool:
            et = arr.typeInfo.arrayBaseType
            if isinstance(et, SolType):
                return et.elementaryTypeName == "address"
            return et == "address"

        if isinstance(callerObject, ArrayVariable):
            # 숫자/인터벌이 아니면 그대로 symbolic (fallback)
            if not hasattr(result, "min_value"):
                # 가상 생성 시도
                return self._join_array_elements_virtually(callerObject, (0, 0))

            # bottom → 빈 구조체 또는 TOP interval
            if result.is_bottom():
                base_t = callerObject.typeInfo.arrayBaseType
                if isinstance(base_t, SolType) and base_t.typeCategory == "struct":
                    empty_struct = StructVariable(
                        f"{callerObject.identifier}[bottom]",
                        base_t.structTypeName,
                        scope=callerObject.scope
                    )
                    ccf = self.an.contract_cfgs[self.an.current_target_contract]
                    if base_t.structTypeName in ccf.structDefs:
                        empty_struct.initialize_struct(ccf.structDefs[base_t.structTypeName])
                    return empty_struct
                elif array_base_is_address(callerObject):
                    return AddressSet.top()
                else:
                    return f"symbolicIndex({callerObject.identifier}[BOTTOM])"

            l, r = result.min_value, result.max_value

            # ─── (A) 단일 인덱스 ───────────────────────────────
            if l == r:
                try:
                    elem = callerObject.get_or_create_element(l)
                except IndexError:
                    # 범위 밖: 가상 생성
                    elem = callerObject._create_element_virtual(l)
                if isinstance(elem, (StructVariable, ArrayVariable, MappingVariable)):
                    return elem
                return elem.value if hasattr(elem, "value") else elem

            # ─── (B) 범위 [l..r]  → 가상 생성 + join  ─────────────────────
            return self._join_array_elements_virtually(callerObject, (l, r))

        # 3) callerObject가 MappingVariable인 경우
        if isinstance(callerObject, MappingVariable):
            if not callerObject.struct_defs or not callerObject.enum_defs:
                ccf = self.an.contract_cfgs[self.an.current_target_contract]
                callerObject.struct_defs = ccf.structDefs
                callerObject.enum_defs = ccf.enumDefs

            # result => 단일 키 or 범위 => map lookup
            if not hasattr(result, 'min_value') or not hasattr(result, 'max_value'):
                # 가상 키로 value 생성
                sample_keys = [0, 1, 2, 3, 4]
                return self._join_mapping_values_virtually(callerObject, sample_keys)

            if result.is_bottom():
                # bottom: 빈 value 생성
                return callerObject._create_value_virtual("bottom")

            min_idx = result.min_value
            max_idx = result.max_value

            # 단일 키
            if min_idx == max_idx:
                key_str = str(min_idx)
                if key_str in callerObject.mapping:
                    val_obj = callerObject.mapping[key_str]
                else:
                    val_obj = callerObject.get_or_create(key_str)
                    self.update_mapping_in_cfg(callerObject.identifier, key_str, val_obj)

                # 복합 타입이면 객체 반환, 기본 타입이면 value 반환
                if isinstance(val_obj, (StructVariable, ArrayVariable, MappingVariable)):
                    return val_obj
                return val_obj.value if hasattr(val_obj, "value") else val_obj

            # 범위 키: 가상 생성 + join
            else:
                span = max_idx - min_idx
                if span > 20:
                    # 샘플링
                    sample_keys = [min_idx + i * span // 20 for i in range(21)]
                else:
                    sample_keys = list(range(min_idx, max_idx + 1))

                return self._join_mapping_values_virtually(callerObject, sample_keys)
        return

    def evaluate_payable_function_call_context(self, expr, variables, callerObject=None, callerContext=None):
        """
        payable(addr) 함수 호출 처리
        - address를 payable address로 변환
        - 추상 해석에서는 address와 동일하게 AddressSet 반환
        """
        # 인자가 있으면 평가
        if expr.arguments:
            sub_val = self.evaluate_expression(expr.arguments[0], variables, None, None)

            # 이미 AddressSet이면 그대로 반환
            if isinstance(sub_val, AddressSet):
                return sub_val

            # uint/int → address 변환
            if isinstance(sub_val, (UnsignedIntegerInterval, IntegerInterval)):
                if sub_val.is_bottom():
                    return AddressSet.bot()
                if sub_val.min_value == sub_val.max_value:
                    return AddressSet(ids={sub_val.min_value})
                return AddressSet.top()

            # 0x로 시작하는 문자열 → address
            if isinstance(sub_val, str) and sub_val.startswith("0x"):
                addr_int = int(sub_val, 16)
                return AddressSet(ids={addr_int})

            # "this" → 현재 컨트랙트 주소
            if isinstance(sub_val, str) and sub_val == "this":
                return self.an.addr_mgr.make_symbolic_address(1, "this")

        # 기타 경우 → Top
        return AddressSet.top()

    def evaluate_function_call_option_context(self, expr, variables, callerObject=None, callerContext=None):
        """
        FunctionCallOptions: expr.function { option1: val1, option2: val2, ... }

        두 가지 경우:
        1) 구조체 생성자: StructName({ field1: val1, field2: val2 })
        2) 함수 호출 옵션: contract.func{value: 1 ether, gas: 5000}(args)
        """
        # Check if it's a MemberAccess with call/delegatecall/staticcall
        if expr.function and hasattr(expr.function, 'context') and expr.function.context == "MemberAccessContext":
            member = getattr(expr.function, 'member', None)
            if member in ['call', 'delegatecall', 'staticcall']:
                # This is the case: address.call{value: ...}
                # 외부 호출은 결과를 알 수 없으므로 Top 반환
                return UnsignedIntegerInterval.top()

        # expr.function이 구조체 타입 이름인지 확인
        if expr.function and expr.function.context == "IdentifierExpContext":
            struct_name = expr.function.identifier

            # 현재 컨트랙트 CFG에서 구조체 정의 가져오기
            ccf = self.an.contract_cfgs[self.an.current_target_contract]

            # 구조체인지 확인
            if struct_name in ccf.structDefs:
                # 구조체 생성자: 새 StructVariable 생성
                struct_def = ccf.structDefs[struct_name]

                new_struct = StructVariable(
                    identifier=f"temp_{struct_name}_{id(expr)}",
                    struct_type=struct_name,
                    scope="memory"
                )
                new_struct.typeInfo = SolType(typeCategory="struct", structTypeName=struct_name)

                # 구조체 초기화
                new_struct.initialize_struct(struct_def)

                # options에서 필드 값 설정
                if expr.options:
                    for field_name, field_expr in expr.options.items():
                        if field_name in new_struct.members:
                            field_value = self.evaluate_expression(field_expr, variables, None, None)
                            field_var = new_struct.members[field_name]
                            if isinstance(field_var, Variables):
                                field_var.value = field_value
                            # 중첩 구조체/배열의 경우 추가 처리 필요할 수 있음

                return new_struct

        # 함수 호출 옵션 (예: {value: 1 ether, gas: 5000})
        # 결과를 알 수 없으므로 Top 반환
        return UnsignedIntegerInterval.top()

    @staticmethod
    def calculate_default_interval(var_type):
        # 1. int 타입 처리 - 상태변수 기본값은 0
        if var_type.startswith("int"):
            length = int(var_type[3:]) if var_type != "int" else 256  # int 타입의 길이 (기본값은 256)
            return IntegerInterval(0, 0, length)  # int의 기본값 0

        # 2. uint 타입 처리 - 상태변수 기본값은 0
        elif var_type.startswith("uint"):
            length = int(var_type[4:]) if var_type != "uint" else 256  # uint 타입의 길이 (기본값은 256)
            return UnsignedIntegerInterval(0, 0, length)  # uint의 기본값 0

        # 3. bool 타입 처리 - 상태변수 기본값은 false (0)
        elif var_type == "bool":
            return BoolInterval(0, 0)  # bool의 기본값 false (0)

        # 4. address 타입 처리 - 기본값은 address(0)
        elif var_type == "address":
            return AddressSet(ids={0})  # address의 기본값 0 (singleton set)

        # 5. bytes32, bytes16 등 고정 크기 바이트 배열 - 기본값은 bytes32(0)
        elif var_type.startswith("bytes") and len(var_type) > 5:
            byte_size = int(var_type[5:])  # "bytes32" -> 32
            return BytesSet(values={0}, byte_size=byte_size)  # bytes32의 기본값 0

        # 6. 기타 처리 (필요시 확장 가능)
        else:
            raise ValueError(f"Unsupported type for default interval: {var_type}")

    @staticmethod
    def compare_intervals(left_interval, right_interval, operator):

        # 값이 하나라도 BOTTOM이면 비교 결과도 BOTTOM (unreachable)
        if (left_interval.min_value is None or left_interval.max_value is None or
                right_interval.min_value is None or right_interval.max_value is None):
            return BoolInterval.bottom()  # unreachable

        definitely_true = False
        definitely_false = False

        # ───────── 비교 연산별 판정 ────────────────────────────────
        if operator == '==':
            if left_interval.max_value < right_interval.min_value or \
                    left_interval.min_value > right_interval.max_value:
                definitely_false = True
            elif (left_interval.min_value == left_interval.max_value ==
                  right_interval.min_value == right_interval.max_value):
                definitely_true = True

        elif operator == '!=':
            if left_interval.max_value < right_interval.min_value or \
                    left_interval.min_value > right_interval.max_value:
                definitely_true = True
            elif (left_interval.min_value == left_interval.max_value ==
                  right_interval.min_value == right_interval.max_value):
                definitely_false = True

        elif operator == '<':
            if left_interval.max_value < right_interval.min_value:
                definitely_true = True
            elif left_interval.min_value >= right_interval.max_value:
                definitely_false = True

        elif operator == '>':
            if left_interval.min_value > right_interval.max_value:
                definitely_true = True
            elif left_interval.max_value <= right_interval.min_value:
                definitely_false = True

        elif operator == '<=':
            if left_interval.max_value <= right_interval.min_value:
                definitely_true = True
            elif left_interval.min_value > right_interval.max_value:
                definitely_false = True

        elif operator == '>=':
            if left_interval.min_value >= right_interval.max_value:
                definitely_true = True
            elif left_interval.max_value < right_interval.min_value:
                definitely_false = True

        else:
            raise ValueError(f"Unsupported comparison operator: {operator}")

        # ───────── BoolInterval 생성 ─────────────────────────────
        if definitely_true and not definitely_false:
            return BoolInterval(1, 1)  # [1,1]  확실히 true
        if definitely_false and not definitely_true:
            return BoolInterval(0, 0)  # [0,0]  확실히 false
        return BoolInterval(0, 1)  # [0,1]  불확정(top)