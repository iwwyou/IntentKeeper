from Domain.Interval import *
from Domain.Type import SolType
from Domain.AddressSet import AddressSet
from Domain.BytesSet import BytesSet
import copy

class Variables:
    def __init__(self, identifier=None, value=None,
                 isConstant=False, scope=None, typeInfo=None):
        # 기본 속성
        self.identifier = identifier  # 변수명
        self.scope = scope  # 변수의 스코프 (local, state 등)
        self.isConstant = isConstant  # 상수 여부
        self.typeInfo = typeInfo # SolType

        # 값 정보
        self.value = value  # interval
        self.initial_value = copy.deepcopy(value)  # ← NEW

class StructDefinition:
    def __init__(self, struct_name):
        self.struct_name = struct_name
        self.members = []

    def add_member(self, var_name, type_obj):
        self.members.append({'member_name' : var_name, 'member_type' : type_obj})

class EnumDefinition:
    def __init__(self, enum_name):
        self.enum_name = enum_name
        self.members = []  # 멤버들의 리스트

    def add_member(self, member_name):
        if member_name not in self.members:
            self.members.append(member_name)
        else:
            raise ValueError(f"Member '{member_name}' is already defined in enum '{self.enum_name}'.")

    def get_member(self, index):
        return self.members[index]

class GlobalVariable(Variables):
    def __init__(self, identifier=None, isConstant=False, scope=None, base=None, member=None, value=None
                 , typeInfo=None):
        super().__init__(identifier, value, isConstant, scope)
        self.base = base
        self.member = member
        self.value = value
        self.typeInfo = typeInfo

        self.default_value: Interval | str | None = None  # 런타임 기본값
        self.debug_override: Interval | str | None = None  # 마지막 @GlobalVar 값
        self.usage_sites: set[str] = set()   # func_name 만!

    # helper ― override 가 있으면 그것, 없으면 value
    @property
    def current(self):
        return self.debug_override if self.debug_override is not None else self.value

class ArrayVariable(Variables):
    """
    ▸ 정적/동적 배열 래퍼
    ▸ int·uint·bool 은 interval 로,
      address·string·bytes 등은 심볼/AddressManager 를 이용해 초기화
    """

    def __init__(self, identifier=None, base_type=None,
                 array_length=None,
                 value=None, isConstant=False, scope=None,
                 is_dynamic=False,
                 struct_defs=None, enum_defs=None):
        super().__init__(identifier, value, isConstant, scope)

        self.typeInfo = SolType()
        self.typeInfo.typeCategory = "array"
        self.typeInfo.arrayBaseType = base_type
        self.typeInfo.arrayLength = array_length  # None → 동적
        self.typeInfo.isDynamicArray = is_dynamic
        self.elements: list[Variables | "ArrayVariable"] = []
        self.struct_defs = struct_defs or {}
        self.enum_defs = enum_defs or {}

    # models.py ― ArrayVariable  내부
    def _create_default_value(self, eid: str):
        """
        base_type 에 맞춰 'TOP' 값을 만들어 준다.
        """
        bt = self.typeInfo.arrayBaseType  # SolType | str
        # ─ address ──────────────────────────────────
        if (isinstance(bt, SolType) and bt.elementaryTypeName == "address") \
                or bt == "address":
            return AddressSet.top()

        # ─ bool ─────────────────────────────────────
        if (isinstance(bt, SolType) and bt.elementaryTypeName == "bool") \
                or bt == "bool":
            return BoolInterval(0, 1)  # TOP of bool

        # ─ int / uint ──────────────────────────────
        if isinstance(bt, SolType) and bt.elementaryTypeName and bt.elementaryTypeName.startswith("int"):
            w = bt.intTypeLength or 256
            return IntegerInterval(-(2 ** (w - 1)), 2 ** (w - 1) - 1, w)
        if isinstance(bt, SolType) and bt.elementaryTypeName and bt.elementaryTypeName.startswith("uint"):
            w = bt.intTypeLength or 256
            return UnsignedIntegerInterval(0, 2 ** w - 1, w)

        # ─ 그 밖의 타입(bytes,string,구조체 등) ───
        return f"symbol_{eid}"  # 마지막 보루

    # -----------------------------------------------------------------
    def get_or_create_element(self, idx: int):
        """
        동적 배열이면 idx 위치까지 0‥idx 의 모든 요소를 채워 넣으며,
        정적 배열이면 범위 체크만 수행한다.
        """
        if idx < 0:
            raise IndexError("negative index")

        # 동적 배열 → 필요하면 확장
        if self.typeInfo.isDynamicArray:
            while idx >= len(self.elements):  # auto-push
                # ★ _create_new_array_element 사용 (struct, nested array 등을 올바르게 생성)
                new_elem = self._create_new_array_element(len(self.elements))
                self.elements.append(new_elem)

        # 정적 배열 → 범위 검사
        if idx >= len(self.elements):
            raise IndexError(f"index {idx} out of range ({len(self.elements)})")

        return self.elements[idx]

    def _create_new_array_element(self, idx: int):
        """
        배열 push·동적-초기화 시 1칸짜리 child 를 만든다.
        ▸ base_type 이
            · elementary / address / bool → Variables
            · struct                    → StructVariable
            · 배열                       → (중첩) ArrayVariable
            · mapping                   → MappingVariable
            · enum                      → EnumVariable
        """
        eid = f"{self.identifier}[{idx}]"
        btype = self.typeInfo.arrayBaseType  # SolType | str

        # ─ elementary / address / bool ───────────────────────────────
        if isinstance(btype, SolType) and btype.typeCategory == "elementary":
            # 주소형
            if btype.elementaryTypeName == "address":
                val = AddressSet.top()
                return Variables(eid, val, scope=self.scope, typeInfo=btype)
            # uint / int / bool → ⊤ interval
            if btype.elementaryTypeName.startswith("uint"):
                bits = int(btype.elementaryTypeName[4:] or 256)
                val = UnsignedIntegerInterval(0, 2 ** bits - 1, bits)
                return Variables(eid, val, scope=self.scope, typeInfo=btype)
            if btype.elementaryTypeName.startswith("int"):
                bits = int(btype.elementaryTypeName[3:] or 256)
                val = IntegerInterval(-(2 ** (bits - 1)), 2 ** (bits - 1) - 1, bits)
                return Variables(eid, val, scope=self.scope, typeInfo=btype)
            if btype.elementaryTypeName == "bool":
                return Variables(eid, BoolInterval(0, 1), scope=self.scope, typeInfo=btype)
            # bytes/string 등
            return Variables(eid, f"symbol_{eid}", scope=self.scope, typeInfo=btype)

        # ─ struct ───────────────────────────────────────────────────
        if isinstance(btype, SolType) and btype.typeCategory == "struct":
            sv = StructVariable(eid, btype.structTypeName, scope=self.scope)
            # ★ struct 정의가 있으면 초기화
            if btype.structTypeName in self.struct_defs:
                sv.initialize_struct(self.struct_defs[btype.structTypeName],
                                     struct_defs=self.struct_defs, enum_defs=self.enum_defs)
            return sv

        # ─ enum ─────────────────────────────────────────────────────
        if isinstance(btype, SolType) and btype.typeCategory == "enum":
            return EnumVariable(eid, btype.enumTypeName, scope=self.scope)

        # ─ mapping ──────────────────────────────────────────────────
        if isinstance(btype, SolType) and btype.typeCategory == "mapping":
            return MappingVariable(eid,
                                   btype.mappingKeyType,
                                   btype.mappingValueType,
                                   scope=self.scope,
                                   struct_defs=self.struct_defs,
                                   enum_defs=self.enum_defs)

        # ─ 중첩 배열 ────────────────────────────────────────────────
        if isinstance(btype, SolType) and btype.typeCategory == "array":
            return ArrayVariable(eid,
                                 btype.arrayBaseType,
                                 btype.arrayLength,
                                 scope=self.scope,
                                 is_dynamic=btype.isDynamicArray,
                                 struct_defs=self.struct_defs,
                                 enum_defs=self.enum_defs)

        # ─ interface ────────────────────────────────────────────────
        if isinstance(btype, SolType) and btype.typeCategory == "interface":
            ifc_name = getattr(btype, 'interfaceName', None)
            v = Variables(eid, AddressSet.top(), scope=self.scope, typeInfo=btype)
            if ifc_name:
                v.value._cast_interface = ifc_name
            return v

        # fallback
        raise ValueError(f"Unhandled array base-type for {eid!r}")

    def _create_element_virtual(self, idx: int):
        """
        배열에 실제로 추가하지 않고 가상으로 요소를 생성한다.
        범위 인덱스 join 시 사용.
        """
        return self._create_new_array_element(idx)


    # ────────────────────────── public API ──────────────────────────
    def initialize_elements(self, init_iv: Interval):
        """int / uint / bool 전용 (추상화 도메인 사용)"""
        # 동적 배열이지만 arrayLength가 설정된 경우(new uint256[](size))는 초기화 필요
        if self.typeInfo.isDynamicArray and self.typeInfo.arrayLength is None:
            return
        self._init_recursive(
            baseT=self.typeInfo.arrayBaseType,
            length=self.typeInfo.arrayLength or 0,
            build_val=lambda eid, et:
            Variables(eid, init_iv.copy() if hasattr(init_iv, "copy") else init_iv,
                      scope=self.scope, typeInfo=et)
        )

    def initialize_not_abstracted_type(self):
        """address / bytes / string 등 — address 는 fresh interval, 나머진 심볼"""
        # 동적 배열이지만 arrayLength가 설정된 경우(new address[](size))는 초기화 필요
        if self.typeInfo.isDynamicArray and self.typeInfo.arrayLength is None:
            return

        def builder(eid, et):
            # address
            if (isinstance(et, SolType) and et.elementaryTypeName == "address") or et == "address":
                top = AddressSet.top()
                return Variables(eid, top, scope=self.scope, typeInfo=et)
            # 그 외 string/bytes … → 심볼
            return Variables(eid, f"symbol_{eid}", scope=self.scope, typeInfo=et)

        self._init_recursive(
            baseT=self.typeInfo.arrayBaseType,
            length=self.typeInfo.arrayLength or 0,
            build_val=builder
        )

    def initialize_default_by_base_type(self, is_return_param: bool = False):
        """base_type을 보고 numeric/bool이면 initialize_elements(TOP 또는 0),
        아니면 initialize_not_abstracted_type()으로 위임 — make_param_variable/
        top_from_soltype/MappingVariable._make_value 세 호출부가 공유하는
        단일 진실 공급원(예전엔 세 곳이 서로 다르게 복붙돼 있어서 두 곳이
        base type 체크 없이 무조건 initialize_not_abstracted_type()을 불러
        numeric 배열 원소가 raw 문자열로 초기화되는 버그가 있었음)."""
        bt = self.typeInfo.arrayBaseType
        et = bt.elementaryTypeName if isinstance(bt, SolType) else None

        if et and et.startswith("int"):
            bits = bt.intTypeLength or 256
            val = IntegerInterval(0, 0, bits) if is_return_param else IntegerInterval.top(bits)
            self.initialize_elements(val)
        elif et and et.startswith("uint"):
            bits = bt.intTypeLength or 256
            val = UnsignedIntegerInterval(0, 0, bits) if is_return_param else UnsignedIntegerInterval.top(bits)
            self.initialize_elements(val)
        elif et == "bool":
            val = BoolInterval(0, 0) if is_return_param else BoolInterval.top()
            self.initialize_elements(val)
        else:
            self.initialize_not_abstracted_type()

    # ──────────────────────── private helper ────────────────────────
    def _init_recursive(self, *, baseT, length: int, build_val):
        """
        baseT : SolType 또는 문자열
        length: 정적 배열 길이
        build_val(eid:str, et) ➜ Variables 객체를 생성해 주는 콜백
        """
        for i in range(length):
            eid = f"{self.identifier}[{i}]"

            # ─ nested array -----------------------------------------------------------------
            if isinstance(baseT, SolType) and baseT.typeCategory == "array":
                sub_arr = ArrayVariable(
                    identifier=eid,
                    base_type=baseT.arrayBaseType,
                    array_length=baseT.arrayLength,
                    scope=self.scope
                )
                # recursion – baseT.arrayBaseType 에 따라 분기
                if self._is_abstractable(baseT.arrayBaseType):
                    base_elem = baseT.arrayBaseType
                    bits = getattr(base_elem, 'intTypeLength', 256) or 256
                    dummy = IntegerInterval.top(bits) \
                        if str(base_elem.elementaryTypeName).startswith("int") \
                        else UnsignedIntegerInterval.top(bits)
                    sub_arr.initialize_elements(dummy)
                else:
                    sub_arr.initialize_not_abstracted_type()
                self.elements.append(sub_arr)
                continue
            # ─ struct element ---------------------------------------------------------------
            # build_val(elementary 전용 콜백)은 struct를 몰라서 raw 문자열
            # (`symbol_{eid}`)로 바텀아웃시킴 — `new <StructType>[](n)`처럼
            # struct 타입 배열을 미리(정적으로) 할당할 때 걸림
            # (web3bugs_35_H_08/35_H_12에서 발견). `_create_new_array_element`
            # 의 struct 분기와 동일한 패턴으로 진짜 StructVariable을 만든다.
            if isinstance(baseT, SolType) and baseT.typeCategory == "struct":
                sv = StructVariable(eid, baseT.structTypeName, scope=self.scope)
                # qualified 네임스페이스 struct(예: "IPool.TokenAmount")는
                # struct_defs에 마지막 "." 뒤 bare 이름으로 등록돼 있음
                bare_name = baseT.structTypeName.rsplit(".", 1)[-1]
                if bare_name in self.struct_defs:
                    sv.initialize_struct(self.struct_defs[bare_name],
                                         struct_defs=self.struct_defs, enum_defs=self.enum_defs)
                self.elements.append(sv)
                continue
            # ─ leaf element -----------------------------------------------------------------
            self.elements.append(build_val(eid, baseT))

    @staticmethod
    def _is_abstractable(bt):
        """int / uint / bool 이면 True"""
        if isinstance(bt, SolType):
            et = bt.elementaryTypeName
        else:
            et = str(bt)
        # struct 등 non-elementary base type이면 elementaryTypeName이 None —
        # new <StructType>[](n) 같은 케이스에서 걸림(web3bugs_35_H_08/35_H_12).
        if et is None:
            return False
        return et.startswith("int") or et.startswith("uint") or et == "bool"

class MappingVariable(Variables):
    def __init__(
        self,
        identifier: str | None = None,
        key_type: SolType | None = None,
        value_type: SolType | None = None,
        *,
        scope: str | None = None,
        struct_defs: dict[str, StructDefinition] | None = None,
        enum_defs: dict[str, EnumDefinition] | None = None,          # ⭐️ enum 목록 전달
    ):
        super().__init__(identifier, value=None, isConstant=False, scope=scope)

        self.typeInfo = SolType()
        self.typeInfo.typeCategory     = "mapping"
        self.typeInfo.mappingKeyType   = key_type
        self.typeInfo.mappingValueType = value_type

        self.mapping: dict[str, Variables] = {}
        self.struct_defs = struct_defs or {}
        self.enum_defs   = enum_defs   or {}

    # ────────────────────────────────────────────────
    # 값-생성 전용 private 헬퍼
    # ────────────────────────────────────────────────
    def _make_value(self, sub_id: str, sol_t: SolType) :
        """
        mappingValueType(SolType) 을 보고 알맞은 객체를 만들어 준다.
        숫자/불린 ⇒ ⊥ interval, 주소 ⇒ TOP interval, 복합 타입 ⇒ 재귀 생성
        """
        # 1) 배열 --------------------------------------------------------
        if sol_t.typeCategory == "array":
            arr = ArrayVariable(
                identifier   = sub_id,
                base_type    = sol_t.arrayBaseType,
                array_length = sol_t.arrayLength,
                is_dynamic   = sol_t.isDynamicArray,
                scope        = self.scope,
                struct_defs  = self.struct_defs,  # ★ struct 정의 전달
                enum_defs    = self.enum_defs,    # ★ enum 정의 전달
            )
            arr.initialize_default_by_base_type()   # 내부까지 재귀 초기화, base type 체크 포함
            return arr

        # 2) 매핑 --------------------------------------------------------
        if sol_t.typeCategory == "mapping":
            return MappingVariable(
                identifier=sub_id,
                key_type=sol_t.mappingKeyType,
                value_type=sol_t.mappingValueType,
                scope=self.scope,
                struct_defs=self.struct_defs,
                enum_defs=self.enum_defs,  # ⭐️ 재귀 전파
            )

        # 3) 구조체 ------------------------------------------------------
        if sol_t.typeCategory == "struct":
            sv = StructVariable(identifier=sub_id,
                                struct_type=sol_t.structTypeName,
                                scope=self.scope)

            if sol_t.structTypeName in self.struct_defs:  # ⭐️ 멤버 초기화
                sv.initialize_struct(self.struct_defs[sol_t.structTypeName],
                                     struct_defs=self.struct_defs, enum_defs=self.enum_defs)

            return sv

        if sol_t.typeCategory == "enum":
            ev = EnumVariable(identifier=sub_id,
                              enum_type=sol_t.enumTypeName,
                              scope=self.scope)

            # enum 정의가 있으면 멤버 테이블 세팅
            if sol_t.enumTypeName in self.enum_defs:
                defn = self.enum_defs[sol_t.enumTypeName]  # EnumDefinition
                ev.members = {m: i for i, m in enumerate(defn.members)}
                ev.valueIndex = 0
                ev.value = defn.members[0]            # ← 첫 멤버명 저장

            return ev

        # 4) interface -------------------------------------------------
        if sol_t.typeCategory == "interface":
            ifc_name = getattr(sol_t, 'interfaceName', None)
            v = Variables(identifier=sub_id, scope=self.scope)
            v.typeInfo = sol_t
            v.value = AddressSet.top()
            if ifc_name:
                v.value._cast_interface = ifc_name
            return v

        # 5) elementary -------------------------------------------------
        v = Variables(identifier=sub_id, scope=self.scope)
        v.typeInfo = sol_t
        et = sol_t.elementaryTypeName

        if et.startswith("int"):
            bits = sol_t.intTypeLength or 256
            v.value = IntegerInterval.top(bits)           # ⊤ interval
        elif et.startswith("uint"):
            bits = sol_t.intTypeLength or 256
            v.value = UnsignedIntegerInterval.top(bits)   # 0 ~ 2ᵇⁱᵗˢ-1
        elif et == "bool":
            v.value = BoolInterval.top()
        elif et == "address":
            v.value = AddressSet.top()   # TOP 주소
        elif et.startswith("bytes") and len(et) > 5:  # bytes32, bytes16 등
            byte_size = int(et[5:])  # "bytes32" -> 32
            v.value = BytesSet.top(byte_size)  # TOP bytes
        else:                               # string / bytes 등
            v.value = f"symbol_{sub_id}"
        return v

    # ────────────────────────────────────────────────
    # public API : get_or_create(key_val)  (기존 get_mapping 대체)
    # ────────────────────────────────────────────────
    def get_or_create(self, key_val) -> Variables:
        """
        키가 없으면 value_type 에 맞춰 **자동 생성** 후 반환
        """
        key_val = str(key_val)
        if key_val not in self.mapping:
            sub_id = f"{self.identifier}[{key_val}]"
            new_var = self._make_value(sub_id, self.typeInfo.mappingValueType)
            self.mapping[key_val] = new_var
        return self.mapping[key_val]

    def _create_value_virtual(self, key_val):
        """
        매핑에 실제로 추가하지 않고 가상으로 value를 생성한다.
        범위 키 join 시 사용.
        """
        sub_id = f"{self.identifier}[{key_val}]"
        return self._make_value(sub_id, self.typeInfo.mappingValueType)

    def get_default_interval_for_type(self, sol_type):
        # 예시 구현: elementary int/uint/bool만 처리
        if sol_type.typeCategory == 'elementary':
            etype = sol_type.elementaryTypeName
            if etype.startswith("int"):
                return IntegerInterval(float('-inf'), float('inf'), sol_type.intTypeLength)
            elif etype.startswith("uint"):
                return UnsignedIntegerInterval(0, float('inf'), sol_type.intTypeLength)
            elif etype == "bool":
                return BoolInterval(False, True)
        # 기타 타입일 경우 None
        return None


# utils.py  (발췌) ─ StructVariable  전체

class StructVariable(Variables):
    """
    구조체 변수를 나타내는 래퍼.
    ─ members : { fieldName(str) : Variables / ArrayVariable / MappingVariable … }
    """

    def __init__(
        self,
        identifier: str | None = None,
        struct_type: str | None = None,
        value=None,
        isConstant: bool = False,
        scope: str | None = None,
    ):
        super().__init__(identifier, value, isConstant, scope)

        self.typeInfo = SolType()
        self.typeInfo.typeCategory   = "struct"
        self.typeInfo.structTypeName = struct_type       # 구조체 이름
        self.members: dict[str, Variables] = {}          # field → variable ­obj

    def copy_from(self, other: 'StructVariable'):
        for k, member in other.members.items():
            self.members[k] = member  # 얕은 참조·필요시 deepcopy

    # ────────────────────────────────────────────────────────────
    # 초기화
    # ------------------------------------------------------------------
    def initialize_struct(
            self,
            struct_def: StructDefinition,
            *,  # ⬅️  키워드-전용
            struct_defs: dict[str, StructDefinition] | None = None,
            enum_defs: dict[str, "EnumDefinition"] | None = None
    ):
        """
        struct_def.members :
            [{ "member_name": str, "member_type": SolType }, ... ]

        멤버 하나하나의 top-value 생성은 VariableEnv.top_from_soltype에 위임한다
        (array/mapping/struct/interface/enum/elementary 전 타입 지원 - 이 함수가
        독자적으로 타입 분기를 다시 구현하면, 한쪽만 갱신되고 다른 쪽은 안 되는
        문제가 생긴다: enum 지원이 top_from_soltype에는 있었지만 여기엔 없어서
        enum 타입 struct 멤버(e.g. `Side side;`)를 만나면
        `sol_t.elementaryTypeName`이 None인 채로 `.startswith()`가 호출되어
        크래시하는 버그가 실제로 있었다 - Perpetuals.Order.side 케이스).
        """
        # 순환 import 회피를 위해 지역 import (Utils.Helper가 Domain.Variable을
        # import하므로 모듈 최상단에서 import하면 순환 참조가 됨)
        from Utils.Helper import VariableEnv

        if struct_defs is None:
            struct_defs = {struct_def.struct_name: struct_def}  # fallback
        if enum_defs is None:
            enum_defs = {}

        for mem in struct_def.members:
            m_name: str = mem["member_name"]
            m_type: SolType = mem["member_type"]
            var_id = f"{self.identifier}.{m_name}"

            member_var = VariableEnv.top_from_soltype(
                m_type, struct_defs=struct_defs, enum_defs=enum_defs, identifier=var_id
            )
            member_var.scope = self.scope  # top_from_soltype은 scope를 모르므로 여기서 채움
            self.members[m_name] = member_var

    # 디버깅용 표현
    def __repr__(self):
        mem_str = ", ".join(f"{k}:{v.value}" for k, v in self.members.items())
        return f"StructVariable({self.identifier}){{{mem_str}}}"

class EnumVariable(Variables):
    def __init__(self, identifier=None, enum_type=None, value=None, isConstant=False, scope=None):
        super().__init__(identifier, value, isConstant, scope)
        self.typeInfo = SolType()
        self.typeInfo.typeCategory = 'enum'
        self.typeInfo.enumTypeName = enum_type  # 열거형 이름
        self.members = {}  # 멤버 변수들: 멤버명 -> 정수 값 (열거형의 각 멤버는 정수 값에 매핑됨)
        self.value = None  # 현재 설정된 멤버의 이름
        self.valueIndex = None

    def set_member_value(self, member_name):
        """
        열거형 변수의 값을 특정 멤버로 설정합니다.
        :param member_name: 열거형 멤버 이름
        """
        if member_name in self.members:
            self.current_value = member_name
            self.value = self.members[member_name]  # 멤버의 정수 값을 변수의 값으로 설정
        else:
            raise ValueError(f"Member '{member_name}' not found in enum '{self.typeInfo.enumTypeName}'.")

    def get_member_value(self):
        """
        열거형 변수의 현재 값을 반환합니다.
        :return: 현재 설정된 멤버의 이름
        """
        return self.current_value
