"""engine_api — IQDebug 프론트(↔ frontend/src/engine/analyzeClient.ts)용 분석 API.

설계 원칙(PROGRESS.md / 설계 논의 확정):
  * 코어(Interpreter/Engine.py fixpoint, Domain/, Utils/CFG.py, GuardianVerificationEngine,
    파서·visitor)는 **불변**. 이 모듈은 입력(annotation 적용)·출력(Result 직렬화) 레이어만 신설.
  * 기존 출력층 ContractAnalyzer.send_report_to_front(print만)은 이 모듈의 export가 대체.

두 레이어로 가른다:

  [결정론 코어]  abstract interpreter, edit-time, 빠름.  EngineSession 안.
    analyze(records)        → Structure        (CFG 구조 + 빈 debug 슬롯)   ── 코드 편집 트리거
    evaluate(debug_values)  → CfgWithStates     (fixpoint → states)          ── 값 변경 트리거
    verify(intents)         → list[VerdictItem] (states 읽어 판정)           ── intent 변경 트리거
        체인 종속: analyze → evaluate → verify.  verify는 states 없으면 lazy evaluate.

  [생성 보조]  solver/LLM, async, 코어 출력 + 추가입력(주석/패턴) 소비.  L2 originality.
    suggest_value(session, slot)              → Suggestion   (opaque 슬롯 채우기)
    reach(session, target)                    → dict         (특정 path 도달 입력 = target 있는 생성)
    cover(session, scope)                     → list[dict]   (전 분기 커버; reach 반복, 후순위)
    suggest_intent(source, comments, patterns)→ list[IntentItem] (주석·취약점패턴 기반 intent 제안)
        → suggest_value/reach/cover 는 표면만 분리, 내부 generator(solver/LLM seam)는 공유.

snapshot/restore 제약(중요):
  현재 debug 분석은 DebugBatchManager.flush 가 restore 로 값을 초기화 → 매 디버깅이 독립적.
  따라서 evaluate 는 **restore 가 값을 지우기 전에** CFG-with-states 를 Result(불변 스냅샷 사본)로
  직렬화해 반환한다. 초기화 로직은 그대로 두고, 엔진 객체는 다음 run 을 위해 리셋된 채 남는다.

이 파일은 계약(타입·시그니처) 우선 스켈레톤이다. 본문은 NotImplementedError.
실배선 시 참고 위치는 각 스텁 docstring에 file:line 으로 명시.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Optional, TypedDict, Union

# ─────────────────────────────────────────────────────────────────────────────
# 입력 record (slice_solidity 산출 형태와 동일: Dependencies/main.py:53)
# ─────────────────────────────────────────────────────────────────────────────


class _RecordBase(TypedDict):
    code: str
    startLine: int
    endLine: int
    event: str  # "add" | "update" | "delete"


class Record(_RecordBase, total=False):
    """순수 코드 한 조각. 어노테이션 라인은 포함하지 않는다.

    closeBefore: slice_solidity 가 `} else {`/`} while`/`} catch` 에 붙이는 플래그. update_code 의
      close_before 인자로 전달돼야 else/do-while/catch 가 직전 블록의 join 을 찾는다(누락 시 빌드 실패)."""
    closeBefore: bool


# ─────────────────────────────────────────────────────────────────────────────
# 값 모델 (frontend/src/types/result.ts 와 1:1 계약)
# ─────────────────────────────────────────────────────────────────────────────

NodeFlag = Literal[
    "condition", "branch_then", "branch_else", "merge",
    "fixpoint_evaluation", "loop_exit", "loop_body", "exit",
]
EdgeKind = Literal["normal", "true", "false", "back_edge"]
VerdictStatus = Literal["Satisfied", "Warning", "Violated"]
DebugKind = Literal["StateVar", "LocalVar", "GlobalVar", "IReturn"]
ValueKind = Literal["interval", "bool", "address", "array", "bytes", "enum"]
Backend = Literal["llm", "solver", "hybrid"]


# RangeValue — 사용자가 채우는 debug 값. debugValue 캐논(Solidity.g4 329-338)으로 직렬화됨.
class IntervalValue(TypedDict):
    t: Literal["interval"]
    lo: str
    hi: str


class BoolValue(TypedDict):
    t: Literal["bool"]
    v: Literal["true", "false", "any"]


class AddressValue(TypedDict):
    t: Literal["address"]
    id: int  # symbolicAddress N


class NoneValue(TypedDict):
    t: Literal["none"]


RangeValue = Union[IntervalValue, BoolValue, AddressValue, NoneValue]
SlotKey = str  # "balance" | "a" | "msg.sender" | "token.balanceOf()"


@dataclass
class CFGNode:
    id: str
    src_line: int
    flags: list[NodeFlag] = field(default_factory=list)
    cond_type: Optional[str] = None  # if | else_if | require | while | for | do_while
    # 변수명 → 직렬화된 추상값 ("[lo,hi]" | "address(⊤)" | "top" | ...). 구조 단계엔 빈 dict.
    state: dict[str, str] = field(default_factory=dict)
    # merge 노드면 join 기여 predecessor id들 (backward 양쪽 하이라이트용)
    join_from: Optional[list[str]] = None


@dataclass
class CFGEdge:
    from_: str
    to: str
    kind: EdgeKind = "normal"


@dataclass
class CFG:
    entry: str
    exit: str
    nodes: list[CFGNode] = field(default_factory=list)
    edges: list[CFGEdge] = field(default_factory=list)
    return_exit: Optional[str] = None
    error_exit: Optional[str] = None


@dataclass
class VerdictItem:
    line: int
    node: str
    type: str
    status: VerdictStatus
    risk: float  # 0..10
    region: tuple[int, int]
    message: str


@dataclass
class TopVar:
    var: str
    kind: str
    node: str
    src_line: int
    scope: str
    provenance: Optional[str] = None  # ⊤ 출처 태깅 (현재 엔진엔 없음 → None)


@dataclass
class Suggestion:
    value: RangeValue
    backend: Backend
    confidence: float


@dataclass
class DebugSlot:
    """분석이 노출하는 디버깅 대상 변수. 사용자는 값만 채운다."""
    kind: DebugKind
    key: SlotKey
    label: str
    valueKind: ValueKind
    opaque: bool = False           # @IReturn/외부 등 도출 불가
    line: Optional[int] = None     # debug는 대체로 함수-스코프 → 보통 None
    suggestion: Optional[Suggestion] = None
    # interval 슬롯의 타입 정보 → 빈 경계(unbounded) 를 타입 min/max 로 치환할 때 사용(Fix B).
    signed: Optional[bool] = None  # int* → True, uint* → False, 비수치 → None
    bits: Optional[int] = None     # 정수 비트폭(uint256 → 256)


@dataclass
class IntentItem:
    scopeKind: Literal["During", "Post"]
    text: str
    line: Optional[int] = None  # @During = 라인-스코프, @Post = 함수-스코프(None)


@dataclass
class Scope:
    contract: str
    function: str


@dataclass
class Diagnostic:
    """누적 코드 syntax gate 결과. analyze 가 delta 적용 후 *합쳐진 전체 코드*를
    ANTLR(Parser/Solidity.g4) 파스해 실패하면 채워진다. (solc 컴파일 게이트는 보류:
    런타임 무겁고 의미검사는 분석 선결조건 아님 — 필요 시 별도 deep-validate 액션으로 분리.)"""
    line: int
    message: str
    severity: Literal["error", "warning"] = "error"


# ─────────────────────────────────────────────────────────────────────────────
# 단계별 산출물
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Structure:
    """analyze() 산출 — CFG 구조 + 빈 debug 슬롯. 값/상태 없음.
    diagnostics 가 비어있지 않으면 누적 코드가 syntax-invalid → 이전 valid 구조 유지하고 표시만."""
    scope: Scope
    cfg: CFG                         # nodes.state == {} (구조만)
    debug_slots: list[DebugSlot] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)


@dataclass
class CfgWithStates:
    """evaluate() 산출 — fixpoint 후 states 채워진 CFG + ⊤ 변수.
    restore 전에 직렬화된 불변 스냅샷 사본."""
    scope: Scope
    cfg: CFG                         # nodes.state 채워짐 = navigation substrate
    top_vars: list[TopVar] = field(default_factory=list)
    # debug 값 입력 오류(잘못된 interval 등). 비어있지 않으면 프론트가 슬롯 옆에 표시(Fix A).
    diagnostics: list[Diagnostic] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# 의존성 명세 (Root B 입력)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DepSpec:
    name: str
    kind: Literal["interface", "library", "contract"]
    source: Optional[str] = None  # 최초 빌드용 원문 (.sol). 이미 빌드됐으면 None.


@dataclass
class DepInfo:
    name: str
    kind: Literal["interface", "library", "contract"]
    status: Literal["ready", "building", "error"]


# ─────────────────────────────────────────────────────────────────────────────
# 뷰 직렬화기 (엔진 FunctionCFG → 프론트 CFG). 코어 밖, 순수 함수.
#   상태 직렬화는 RecordManager._flatten_var/_serialize_val(이미 검증된 interval→str) 재사용.
# ─────────────────────────────────────────────────────────────────────────────


def _node_flags(n) -> list[NodeFlag]:
    """엔진 CFGNode 의 role 플래그 → 프론트 NodeFlag 목록."""
    flags: list[NodeFlag] = []
    if getattr(n, "condition_node", False):
        flags.append("condition")
    if getattr(n, "branch_node", False):
        flags.append("branch_then" if getattr(n, "is_true_branch", False) else "branch_else")
    if getattr(n, "join_point_node", False):
        flags.append("merge")
    if getattr(n, "fixpoint_evaluation_node", False):
        flags.append("fixpoint_evaluation")
    if getattr(n, "loop_exit_node", False):
        flags.append("loop_exit")
    if getattr(n, "is_loop_body", False):
        flags.append("loop_body")
    if (getattr(n, "function_exit_node", False)
            or getattr(n, "return_exit_node", False)
            or getattr(n, "error_exit_node", False)):
        flags.append("exit")
    return flags


def _serialize_node_state(n, recorder) -> dict[str, str]:
    """CFGNode.variables(name→Variables) → {name: "[lo,hi]"/"address(⊤)"/...}.
    RecordManager._flatten_var 는 인스턴스 상태에 의존하지 않는 순수 평탄화라 재사용 가능."""
    flat: dict[str, str] = {}
    for name, var in getattr(n, "variables", {}).items():
        recorder._flatten_var(var, name, flat)  # fail-loud: 직렬화 구멍은 그대로 터뜨림
    # ⊥(bottom = 도달 불가 분기) 가독화: "[None,None]" → "⊥"
    return {k: ("⊥" if v == "[None,None]" else v) for k, v in flat.items()}


def _serialize_cfg(fcfg, recorder, with_states: bool) -> CFG:
    """엔진 FunctionCFG(graph=networkx DiGraph, 노드=CFGNode) → 프론트 CFG.
    with_states=False 면 state={} (analyze 구조 단계). True 면 추상상태 채움(evaluate)."""
    nodes: list[CFGNode] = []
    for n in fcfg.graph.nodes():
        join_from = None
        if getattr(n, "join_point_node", False):
            join_from = [p.name for p in fcfg.graph.predecessors(n)]
        nodes.append(CFGNode(
            id=n.name,
            src_line=n.src_line if getattr(n, "src_line", None) is not None else -1,
            flags=_node_flags(n),
            cond_type=getattr(n, "condition_node_type", None),
            state=_serialize_node_state(n, recorder) if with_states else {},
            join_from=join_from,
        ))
    edges: list[CFGEdge] = []
    for u, v, data in fcfg.graph.edges(data=True):
        cond = data.get("condition", None)
        kind: EdgeKind = "true" if cond is True else "false" if cond is False else "normal"
        # TODO(back_edge): loop back-edge 라벨링 — fixpoint 노드 입력엣지 판별 후속.
        edges.append(CFGEdge(from_=u.name, to=v.name, kind=kind))
    ret = getattr(fcfg, "return_exit", None)
    err = getattr(fcfg, "error_exit", None)
    return CFG(
        entry=fcfg.entry_node.name,
        exit=fcfg.exit_node.name,
        nodes=nodes,
        edges=edges,
        return_exit=ret.name if ret is not None else None,
        error_exit=err.name if err is not None else None,
    )


_KIND_KW = {"StateVar": "@StateVar", "LocalVar": "@LocalVar",
            "GlobalVar": "@GlobalVar", "IReturn": "@IReturn"}


def _value_text(v: RangeValue) -> Optional[str]:
    """RangeValue → debugValue 캐논 텍스트(Solidity.g4 329-338). none → None(스킵)."""
    t = v.get("t")
    if t == "interval":
        return f'[{v["lo"]},{v["hi"]}]'
    if t == "bool":
        return v["v"]  # true | false | any
    if t == "address":
        return f'symbolicAddress {v["id"]}'
    return None


def _debug_value_text(v: RangeValue, slot: Optional["DebugSlot"]):
    """RangeValue → (캐논 텍스트|None, 에러|None). interval 빈 경계는 슬롯 타입 min/max 로 치환(Fix B).
      * 양쪽 빈칸 = 미입력 → (None, None) 스킵(무제약=⊤).
      * 한쪽만 빈칸 = 그 방향 무제약 → 타입 경계(uint256 [0,2²⁵⁶-1] / int256 [-2²⁵⁵,2²⁵⁵-1]).
      * 숫자 파싱 실패·lo>hi = (None, 에러메시지) → 상위에서 Diagnostic 로 표면화(Fix A)."""
    t = v.get("t")
    if t == "interval":
        lo, hi = str(v.get("lo", "")).strip(), str(v.get("hi", "")).strip()
        if lo == "" and hi == "":
            return None, None  # 미입력 슬롯 → seed 안 함
        signed = bool(getattr(slot, "signed", False)) if slot else False
        bits = int(getattr(slot, "bits", 256) or 256) if slot else 256
        if lo == "":
            lo = str(-(1 << (bits - 1)) if signed else 0)
        if hi == "":
            hi = str((1 << (bits - 1)) - 1 if signed else (1 << bits) - 1)
        try:
            loi, hii = int(lo, 0), int(hi, 0)
        except (ValueError, TypeError):
            return None, f"잘못된 interval 값 (lo='{v.get('lo')}', hi='{v.get('hi')}')"
        if loi > hii:
            return None, f"하한이 상한보다 큼 (lo={loi} > hi={hii})"
        return f"[{loi},{hii}]", None
    if t == "bool":
        return v.get("v", "any"), None
    if t == "address":
        return f'symbolicAddress {v.get("id", 0)}', None
    return None, None


def _collect_top_vars(fcfg, scope: str) -> list[TopVar]:
    """⊤(top) 으로 평가된 변수 수집(provenance 는 현재 엔진에 없어 None).
    1차: AddressSet/BytesSet.is_top. (interval-top 판별은 후속.)"""
    out: list[TopVar] = []
    seen: set[str] = set()
    for n in fcfg.graph.nodes():
        for name, var in getattr(n, "variables", {}).items():
            val = getattr(var, "value", None)
            # AddressSet/BytesSet.is_top 는 bool 속성. interval 의 is_top 은 메서드라
            #   strict True 비교로 오탐 방지(interval-top 판별은 후속).
            if getattr(val, "is_top", None) is True and name not in seen:
                seen.add(name)
                out.append(TopVar(var=name, kind=type(val).__name__, node=n.name,
                                  src_line=n.src_line if getattr(n, "src_line", None) is not None else -1,
                                  scope=scope, provenance=None))
    return out


# 엔진이 두 어휘를 혼용: 단일 절(_verify_during_clause_dynamic)=success/violation,
#   복합 절(_combine_logic_results)=satisfied/violated. 둘 다 정규화.
_VSTATUS: dict[str, VerdictStatus] = {
    "satisfied": "Satisfied", "success": "Satisfied",
    "violated": "Violated", "violation": "Violated",
    "warning": "Warning",
}


def _extract_verdict(ca) -> list[VerdictItem]:
    """analysis_per_line(intent 검증 기록)을 프론트 VerdictItem 으로 변환.
    엔트리 type ∈ {during_intent, post_intent, during, post}, result=combined_result."""
    out: list[VerdictItem] = []
    apl = getattr(ca, "analysis_per_line", {}) or {}
    for line_no, entries in apl.items():
        for e in entries:
            etype = e.get("type", "")
            if etype not in ("during_intent", "post_intent", "during", "post"):
                continue
            r = e.get("result", {}) or {}
            status = _VSTATUS.get(r.get("status"), "Warning")  # error/pending/unknown → Warning
            risk = r.get("risk_score")
            if risk is None and isinstance(r.get("details"), dict):
                risk = r["details"].get("risk_score")
            kind = "post" if "post" in etype else "during"
            out.append(VerdictItem(
                line=line_no, node="", type=kind, status=status,
                risk=float(risk or 0.0), region=(line_no, line_no),
                message=r.get("message", ""),
            ))
    return out


def _cfg_to_dict(cfg: CFG) -> dict:
    """CFG dataclass → 프론트 JSON dict. CFGEdge.from_ → "from" 으로 키 교정."""
    d = asdict(cfg)
    d["edges"] = [{"from": e["from_"], "to": e["to"], "kind": e["kind"]} for e in d["edges"]]
    return d


import re as _re

_GLOBAL_ADDR = {"msg.sender", "tx.origin", "block.coinbase"}


def _bits_from(type_name: str) -> Optional[int]:
    """'uint128' → 128, 'int' → None(호출부 기본 256)."""
    digits = "".join(c for c in type_name if c.isdigit())
    return int(digits) if digits else None


def _valuekind_of(typeInfo, class_name: str = "", name: str = ""):
    """변수 타입 → (valueKind, opaque, signed, bits). msg.sender=address, bool=bool,
    (u)int=interval(+signed/bits), 매핑·구조체·배열·enum·bytes=opaque(advanced)."""
    if class_name in ("MappingVariable", "StructVariable", "ArrayVariable"):
        return "array", True, None, None
    if class_name == "EnumVariable":
        return "enum", True, None, None
    cat = getattr(typeInfo, "typeCategory", None)
    et = getattr(typeInfo, "elementaryTypeName", None)
    tbits = getattr(typeInfo, "intTypeLength", None)
    if cat in ("mapping", "array", "struct"):
        return "array", True, None, None
    if cat == "enum":
        return "enum", True, None, None
    if et:
        e = et.lower()
        if e.startswith("address"):
            return "address", False, None, None
        if e == "bool":
            return "bool", False, None, None
        if e.startswith("uint"):
            return "interval", False, False, (tbits or _bits_from(e) or 256)
        if e.startswith("int"):
            return "interval", False, True, (tbits or _bits_from(e) or 256)
        if e.startswith("bytes") or e == "string":
            return "bytes", True, None, None  # advanced (값 입력 후순위)
    # typeInfo 없는 글로벌 등 → 이름 기반 폴백
    if name in _GLOBAL_ADDR:
        return "address", False, None, None
    return "interval", False, False, 256  # 기본 수치(uint256)


def _referenced(name: str, text: str) -> bool:
    """변수명이 함수 소스에 단어 경계로 등장하는지(부분문자열 오탐 방지)."""
    if not name or not text:
        return False
    return _re.search(r"\b" + _re.escape(name) + r"\b", text) is not None


# ── 통합 접근-경로 스캐너 (decision #34): compound(mapping/struct/array) + @IReturn 슬롯 도출 ──
#   슬롯 = ROOT + accessor* , key = _ap_label(maximal_expr). node.statements AST 를 정적 순회(재평가 X).
#   evaluator 가 아닌 이유: 재귀 bottom-up 이라 maximal 경로 경계를 모름 + fixpoint 로 여러 번·값 있을 때만 실행.
def _ap_member_base(e):
    b = getattr(e, "base", None)
    return b if b is not None else getattr(e, "expression", None)

def _ap_is_index(e):  return getattr(e, "base", None) is not None and getattr(e, "index", None) is not None
def _ap_is_member(e): return getattr(e, "member", None) is not None and _ap_member_base(e) is not None
def _ap_is_call(e):   return getattr(e, "function", None) is not None
def _ap_is_ident(e):  return getattr(e, "identifier", None) is not None
def _ap_is_access(e): return _ap_is_index(e) or _ap_is_member(e) or _ap_is_call(e)

def _ap_label(e) -> str:
    """접근-경로 → 어노테이션 키 문자열. 메서드 호출 인자는 드롭(`f()`), 캐스트 인자는 유지(`I(a)`)."""
    from Domain.IR import Expression
    if not isinstance(e, Expression):
        return str(e)
    if _ap_is_index(e):
        return f"{_ap_label(e.base)}[{_ap_label(e.index)}]"
    if _ap_is_member(e):
        return f"{_ap_label(_ap_member_base(e))}.{e.member}"
    if _ap_is_call(e):
        fn = e.function
        if _ap_is_member(fn):                       # 메서드 호출 → 인자 드롭 (token.balanceOf())
            return f"{_ap_label(fn)}()"
        args = ",".join(_ap_label(a) for a in (getattr(e, "arguments", None) or []))
        return f"{_ap_label(fn)}({args})"           # 캐스트 등 → 인자 유지 (IERC20(baseToken))
    if _ap_is_ident(e):
        return str(e.identifier)
    if getattr(e, "literal", None) is not None:
        return str(e.literal)
    if getattr(e, "typeName", None) is not None and getattr(e, "expression", None) is not None:
        return f"{e.typeName}({_ap_label(e.expression)})"
    return str(e)

def _ap_spine(e):
    """maximal 접근식 → (root_expr, accessors root→leaf). accessor=('index',None)/('member',name)/('call',None)."""
    accs = []
    cur = e
    while True:
        if _ap_is_index(cur):    accs.append(("index", None)); cur = cur.base
        elif _ap_is_member(cur): accs.append(("member", cur.member)); cur = _ap_member_base(cur)
        elif _ap_is_call(cur):   accs.append(("call", None)); cur = cur.function
        else: break
    accs.reverse()
    return cur, accs

def _ap_side_exprs(e):
    """spine 상의 index 키·call 인자(별도 하위식) 수집 — 중첩 경로 스캔용."""
    out, cur = [], e
    while True:
        if _ap_is_index(cur):
            if cur.index is not None: out.append(cur.index)
            cur = cur.base
        elif _ap_is_member(cur):
            cur = _ap_member_base(cur)
        elif _ap_is_call(cur):
            for a in (getattr(cur, "arguments", None) or []):
                if a is not None: out.append(a)
            cur = cur.function
        else: break
    return out

def _ap_children(e):
    from Domain.IR import Expression
    for a in ("left", "right", "base", "index", "function", "expression",
              "condition", "true_expr", "false_expr", "start_index", "end_index"):
        v = getattr(e, a, None)
        if isinstance(v, Expression): yield v
    for a in ("arguments", "elements"):
        for x in (getattr(e, a, None) or []):
            if isinstance(x, Expression): yield x

def _ap_node_exprs(n):
    for stm in getattr(n, "statements", []) or []:
        for a in ("init_expr", "left", "right", "operand", "function_expr", "return_expr"):
            v = getattr(stm, a, None)
            if v is not None: yield v
        for a in (getattr(stm, "arguments", None) or []):
            if a is not None: yield a
    ce = getattr(n, "condition_expr", None)
    if ce is not None: yield ce


def _derive_debug_slots(fcfg, ccf=None, func_src: str = "", func_name: str = "",
                        interface_names=None) -> list[DebugSlot]:
    """구조적 debug 슬롯 도출(값 이전). *이 함수와 관련된* 변수만, 타입별 valueKind로.
      LocalVar = 함수 파라미터 / StateVar = 이 함수가 참조하는 상태변수(func_src 매치)
      GlobalVar = 이 함수가 쓰는 글로벌 / IReturn = 인터페이스 호출.
    compound(mapping/struct/array 접근 경로)·IReturn 은 통합 접근-경로 스캐너(_ap_*, decision #34)로
    node.statements AST 에서 도출: 슬롯 key = 경로 문자열(`_balances[u]`·`accountBorrows[k].principal`·
    `token.balanceOf()`), valueKind = leaf 타입. compound 로 잡힌 상태변수는 opaque 통짜 슬롯 대신 경로 슬롯으로.
    valueKind = 변수 typeInfo(SolType) 기반; signed/bits 는 Fix B 경계 치환용."""
    from Domain.IR import Expression
    from Domain.Variable import MappingVariable, StructVariable, ArrayVariable
    interface_names = interface_names or set()
    slots: list[DebugSlot] = []

    svn = getattr(ccf, "state_variable_node", None) if ccf is not None else None
    statevars = (getattr(svn, "variables", {}) if svn is not None else {}) or {}
    def _is_ifc_type(ti):
        return getattr(ti, "typeCategory", None) == "interface" or bool(getattr(ti, "interfaceName", None))
    interface_var_names = {nm for nm, var in statevars.items()
                           if _is_ifc_type(getattr(var, "typeInfo", None))}

    # ── 접근-경로 스캔 ─────────────────────────────────────────────
    compound: dict[str, tuple] = {}        # label -> (valueKind, opaque, signed, bits)
    compound_roots: set[str] = set()
    ireturn_labels: set[str] = set()

    def classify(root):
        if _ap_is_ident(root):
            nm = root.identifier
            if nm in interface_names or nm in interface_var_names: return "IReturn"
            if nm in statevars: return "StateVar"
            return None
        tn = getattr(root, "typeName", None)
        if tn and tn in interface_names: return "IReturn"
        return None

    def leaf_vk(root, accs):
        cur = statevars.get(root.identifier) if _ap_is_ident(root) else None
        for kind, key in accs:
            if cur is None: break
            if kind == "member":
                cur = cur.members.get(key) if isinstance(cur, StructVariable) else None
            elif kind == "index":
                if isinstance(cur, MappingVariable):
                    cur = cur._create_value_virtual("0")
                elif isinstance(cur, ArrayVariable):
                    try: cur = cur._create_new_array_element(0)
                    except Exception: cur = None
                else: cur = None
            else:
                cur = None
        if cur is None:
            return "interval", False, False, 256  # 해소 실패 → 기본 수치
        return _valuekind_of(getattr(cur, "typeInfo", None), type(cur).__name__)

    def scan(e):
        if not isinstance(e, Expression): return
        if _ap_is_access(e):
            root, accs = _ap_spine(e)
            cls = classify(root)
            if cls is not None:
                label = _ap_label(e)
                if cls == "IReturn":
                    ireturn_labels.add(label)
                elif accs:  # compound = accessor 가 있을 때만(단순 스칼라 상태변수 제외)
                    compound_roots.add(root.identifier)
                    compound.setdefault(label, leaf_vk(root, accs))
                for side in _ap_side_exprs(e):
                    scan(side)
                return
        for c in _ap_children(e):
            scan(c)

    for n in fcfg.graph.nodes():
        for e in _ap_node_exprs(n):
            scan(e)

    # 1) 파라미터 (LocalVar, 스칼라)
    for p in getattr(fcfg, "parameters", []) or []:
        slots.append(DebugSlot(kind="LocalVar", key=p, label=p,
                               valueKind="interval", signed=False, bits=256))

    # 2) 상태변수 — compound root 는 경로 슬롯이, 인터페이스 핸들은 IReturn 이 대체하므로 스킵, 나머지는 스칼라
    for name, var in statevars.items():
        if name in compound_roots or name in interface_var_names:
            continue
        if func_src and not _referenced(name, func_src):
            continue
        vk, opaque, signed, bits = _valuekind_of(getattr(var, "typeInfo", None),
                                                 type(var).__name__, name)
        slots.append(DebugSlot(kind="StateVar", key=name, label=name, valueKind=vk,
                               opaque=opaque, signed=signed, bits=bits))

    # 3) compound 경로 슬롯 (StateVar)
    for label, (vk, opaque, signed, bits) in compound.items():
        slots.append(DebugSlot(kind="StateVar", key=label, label=label, valueKind=vk,
                               opaque=bool(opaque), signed=signed, bits=bits))

    # 4) 글로벌
    globs = (getattr(ccf, "globals", {}) if ccf is not None else {}) or {}
    for g, gvar in (globs.items() if hasattr(globs, "items") else ((x, None) for x in globs)):
        sites = getattr(gvar, "usage_sites", None)
        used = (func_name in sites) if sites else _referenced(g, func_src)
        if not used:
            continue
        vk, opaque, signed, bits = _valuekind_of(getattr(gvar, "typeInfo", None),
                                                 type(gvar).__name__, g)
        slots.append(DebugSlot(kind="GlobalVar", key=g, label=g, valueKind=vk,
                               opaque=opaque, signed=signed, bits=bits))

    # 5) @IReturn — 코드 스캔(신규) ∪ registry(@IReturn 어노테이션 값) — label dedup
    for key in getattr(fcfg, "ireturn_registry", {}) or {}:
        ireturn_labels.add(".".join(str(x) for x in key if x))
    for label in ireturn_labels:
        slots.append(DebugSlot(kind="IReturn", key=label, label=label,
                               valueKind="interval", opaque=True))
    return slots


# ─────────────────────────────────────────────────────────────────────────────
# 의존성 로딩 — DepSpec 이름으로 objectfile pkl 선별 로드(전부 로드 시 버전 충돌).
#   topo-sort(임의 첨부 순서)는 미구현(PROGRESS §2.4) — 1차는 명시 deps 만.
# ─────────────────────────────────────────────────────────────────────────────


def _find_dep_pkl(name: str):
    import pathlib
    base = pathlib.Path(__file__).parent
    for d in (base / "Dependencies" / "objectfile", base / "Libraries" / "objectfile"):
        if not d.exists():
            continue
        exact = d / f"{name}.pkl"
        if exact.exists():
            return exact
        for pkl in sorted(d.glob(f"*_{name}.pkl")):  # ifc_N_/lib_N_/con_N_ 접두사 형태
            return pkl
    return None


def _load_dependencies_into(sa, ca, deps: list[DepSpec]) -> None:
    """명시된 deps 를 objectfile pkl 에서 로드 → ca.contract_cfgs/library_cfgs/interface_names.
    fail-loud: pkl 없으면 FileNotFoundError(조용한 스킵 없음)."""
    import pickle
    for spec in deps:
        pkl = _find_dep_pkl(spec.name)
        if pkl is None:
            raise FileNotFoundError(f"dependency pkl not found for '{spec.name}' "
                                    f"(objectfile 에 빌드됐는지 확인)")
        with open(pkl, "rb") as f:
            raw = pickle.load(f)
        if isinstance(raw, dict) and "cfg" in raw:
            cfg = raw["cfg"]
            sa.file_level_structs.update(raw.get("file_level_structs", {}))
            sa.type_aliases.update(raw.get("type_aliases", {}))
        else:
            cfg = raw
        stem = pkl.stem
        if stem.startswith("ifc_") or spec.kind == "interface":
            ca.interface_names.add(spec.name)
            ca.contract_cfgs[spec.name] = cfg
        elif stem.startswith("lib_") or spec.kind == "library":
            ca.library_cfgs[spec.name] = cfg
            ca.contract_cfgs[spec.name] = cfg
        else:
            ca.contract_cfgs[spec.name] = cfg


def _is_condition_header(code: str) -> bool:
    """body 를 가진 조건 헤더(if/while/for/else-if) — modify 시 in-place(body 보존) 대상.
    require/assert(body 없음)·단순 statement 는 delete+add 로 처리하므로 제외."""
    t = code.strip()
    return ("{" in t) and t.startswith(
        ("if ", "if(", "while ", "while(", "for ", "for(", "else if", "} else if"))


def _is_risky_op(op) -> bool:
    """surgical 미지원(silent corruption 위험) 편집 → full-rebuild 안전망 대상.
    try-catch / do-while(통삭제 전제) + 분기 안 break/continue 삭제."""
    t = op.code.strip()
    if op.kind in ("break", "continue", "catch"):
        return True
    return t.startswith(("do ", "do{", "try ", "try{", "} catch", "catch"))


def _values_key(debug_values: dict[str, RangeValue]) -> str:
    """debug 값 묶음 → states 캐시 키. evaluate 가 심고 verify 가 찾는다(같은 값 = 같은 states)."""
    return repr(sorted((k, tuple(sorted(v.items()))) for k, v in debug_values.items()))


# ─────────────────────────────────────────────────────────────────────────────
# Root A — 타겟 분석 세션 (결정론 코어)
# ─────────────────────────────────────────────────────────────────────────────


class EngineSession:
    """타겟 1개에 대한 분석 세션.

    내부: SolidityAnalyzer 1개 보유(Analyzer/SolidityAnalyzer.py:13) +
          deps 1회 로드(main.load_dependencies 를 인스턴스 받는 형태로 신규 작성).
          debug 적용은 DebugBatchManager(Analyzer/DebugUnitAnalyzer.py:33) snapshot/restore 로 감쌈.
    """

    def __init__(self, deps: Optional[list[DepSpec]] = None) -> None:
        from Analyzer.SolidityAnalyzer import SolidityAnalyzer
        from Analyzer.DebugUnitAnalyzer import DebugBatchManager

        self._sa = SolidityAnalyzer()
        self._ca = self._sa.contract_analyzer
        self._batch = DebugBatchManager(self._ca, self._ca.snapman)
        # states 보존: interpret_function_cfg_for_debug 내부 restore(Engine.py) 직전에
        #   Engine 이 계산된 states fcfg 를 freeze 하도록 게이트 on.
        self._ca._capture_debug_fcfg = True

        self._scope: Optional[Scope] = None
        self._slots: dict[str, DebugSlot] = {}  # key → slot (evaluate 가 kind 조회)
        self._last_debug_values: dict[str, RangeValue] = {}  # 마지막 적용 debug 값(verify 재해석용)
        self._last_value_errors: list[Diagnostic] = []       # 마지막 debug 값 입력 오류(Fix A)
        self._last_intent_errors: list[Diagnostic] = []      # 마지막 intent 파싱/처리 오류(Fix B, crash 대신)
        self._intents: list[IntentItem] = []                 # 현재 등록된 intent
        # values_version → freeze 된 fcfg (Stage1 states 캐시). 키는 debug 값 직렬화 해시.
        self._states_cache: dict[str, object] = {}
        self._prev_records: list[dict] = []  # B1 증분 diff 기준 (마지막 적용 records)
        self._deps = deps or []
        # deps 선별 로드(@IReturn/cross-contract 해소). 없으면 단순 케이스로 동작.
        if self._deps:
            _load_dependencies_into(self._sa, self._ca, self._deps)

    def close(self) -> None:
        """세션 리소스 해제. (현재는 참조 해제만.)"""
        self._states_cache.clear()
        self._scope = None

    # ── 내부 드라이버 (simulate_inputs 의 코드-라인 경로, 콘솔 print 제거) ──────────

    def _apply_code_record(self, code: str, s: int, e: int, ev: str,
                           close_before: bool = False) -> None:
        from Utils.Helper import ParserHelpers
        from Utils.YulHelper import YulParserHelpers
        from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
        from Analyzer.EnhancedYulVisitor import EnhancedYulVisitor

        # 프론트 event("update") → 엔진("modify") 매핑
        ev = "modify" if ev == "update" else ev
        self._sa.update_code(s, e, code, ev, close_before)

        if not code.strip():
            return
        ctx = self._ca.get_current_context_type()
        if ctx == "assembly":
            tree = YulParserHelpers.generate_parse_tree(code)
            EnhancedYulVisitor(self._ca).visit(tree)
        else:
            tree = ParserHelpers.generate_parse_tree(code, ctx, True)
            EnhancedSolidityVisitor(self._ca).visit(tree)

    def _resolve_fcfg(self, contract: Optional[str], func: Optional[str]):
        """타겟 FunctionCFG 회수. contract/func 미지정 시 단일 후보를 추정."""
        cfgs = self._ca.contract_cfgs
        if contract is None:
            # 의존성으로 로드된 ifc_/lib_/con_ 제외하고, 입력으로 빌드된 컨트랙트 우선.
            candidates = [c for c in cfgs if c not in getattr(self._ca, "interface_names", set())]
            contract = candidates[-1] if candidates else (next(iter(cfgs), None))
        ccf = cfgs.get(contract)
        if ccf is None:
            return contract, func, None
        if func is None:
            names = [n for n, _ in ccf.iter_all_functions()] if hasattr(ccf, "iter_all_functions") else list(getattr(ccf, "functions", {}))
            func = names[-1] if names else None
        fcfg = ccf.get_function_cfg(func) if func else None
        return contract, func, fcfg

    def _set_context(self, fcfg, contract: str, func: str) -> None:
        """타겟 함수 컨텍스트 수동 설정 (어노테이션을 소스에 삽입하지 않음 = 라인 밀림 없음)."""
        self._ca.current_target_contract = contract
        self._ca.current_target_function = func
        self._ca.current_target_function_param_types = getattr(fcfg, "parameter_types", None)
        self._ca.current_target_function_cfg = fcfg
        self._ca.current_edit_event = "add"
        body_lines = [n.src_line for n in fcfg.graph.nodes() if getattr(n, "src_line", None)]
        line = max(body_lines) if body_lines else 1
        self._ca.current_start_line = line
        self._sa.current_start_line = line

    def _attach_intents(self, fcfg, intents: list[IntentItem]) -> None:
        """intent 를 live CFG 노드에 등록(파싱→process_during/process_post). 매번 fresh.
        @During = 라인의 노드, @Post = exit 노드. 소스 삽입 없음(컨텍스트 수동)."""
        from Utils.Helper import ParserHelpers
        from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor

        # 기존 intent 비우기 (노드 + exit)
        for n in fcfg.graph.nodes():
            if hasattr(n, "intents"):
                n.intents = []
        # Fix B: intent 하나의 파싱/처리 실패가 전체 요청을 500 으로 죽이지 않게 per-intent 격리.
        #   (debug 값 경로 _queue_debug_values 와 대칭 — 실패는 diagnostic 으로 수집·skip.)
        errors: list[Diagnostic] = []
        for it in intents:
            kw = "@During" if it.scopeKind == "During" else "@Post"
            if it.line is not None:
                self._ca.current_start_line = it.line
            code = f"{kw} {it.text}"
            try:
                tree = ParserHelpers.generate_parse_tree(code, "intentUnit")
                EnhancedSolidityVisitor(self._ca).visit(tree)
            except Exception as e:  # 파싱실패(문법위반)·처리실패 모두 흡수
                errors.append(Diagnostic(line=(it.line or 0),
                                         message=f"intent 무시됨 ({kw} {it.text}): {e}"))
        self._last_intent_errors = errors

    def _queue_debug_values(self, debug_values: dict[str, RangeValue]) -> int:
        """debug 값 → 캐논 어노테이션 라인 → batch. 적용 개수 반환.
        빈 경계는 슬롯 타입으로 치환(Fix B), 파싱 실패는 _last_value_errors 에 수집(Fix A, crash 대신)."""
        self._batch.reset()
        applied = 0
        errors: list[Diagnostic] = []
        for key, val in (debug_values or {}).items():
            slot = self._slots.get(key)
            text, err = _debug_value_text(val, slot)
            if err is not None:
                errors.append(Diagnostic(line=(slot.line if slot and slot.line else 0),
                                         message=f"{key}: {err}", severity="error"))
                continue
            if text is None:
                continue
            kw = _KIND_KW.get(slot.kind if slot else "LocalVar", "@LocalVar")
            self._batch.add(f"{kw} {key} = {text}")
            applied += 1
        self._last_value_errors = errors
        return applied

    def _interpret(self):
        """현재 _last_debug_values + _intents 로 1회 해석(P1) → freeze 된 states fcfg 반환.
        intent 는 노드에 attach 돼 해석 중 inline 검증 → analysis_per_line 에 verdict 기록.
        debug 값이 하나도 없으면 (None, None) — states/verdict 없음(프론트는 auto-fill 유도)."""
        sc = self._scope or Scope(contract="", function="")
        contract, func, fcfg = self._resolve_fcfg(sc.contract or None, sc.function or None)
        if fcfg is None:
            return None, None
        self._scope = Scope(contract=contract or "", function=func or "")
        self._set_context(fcfg, contract, func)
        self._attach_intents(fcfg, self._intents)

        applied = self._queue_debug_values(self._last_debug_values)
        if applied == 0:
            return fcfg, None  # 값 없음 → 해석 안 함

        self._ca._frozen_debug_fcfg = None
        self._batch.flush()  # interpret(P1): states 계산 + inline intent 검증 → (restore 직전 freeze)
        frozen = getattr(self._ca, "_frozen_debug_fcfg", None)
        if frozen is None:
            # fail-loud: freeze 안 됐으면 states 없음 → baseline 으로 덮지 않고 에러.
            raise RuntimeError(
                "interpret: 계산된 states freeze 실패(_frozen_debug_fcfg=None). "
                "_capture_debug_fcfg 게이트 확인.")
        return fcfg, frozen

    # ── 결정론 코어 ──────────────────────────────────────────────────────────

    def analyze(self, records: list[Record],
                contract: Optional[str] = None, func: Optional[str] = None) -> Structure:
        """편집 delta records 를 누적 적용 → CFG 구조 + 빈 debug 슬롯. 값/상태 없음. [코드 편집 트리거]

        입력 모델 (delta fragment, full-slice 아님):
          * records = 최신 편집 delta (Monaco onChange → (startLine,endLine,code,event) 어댑터 산출).
            키 입력 = 작은 fragment, paste = multi-line record 여러 개. 세션이 누적 코드를 보유.
          * 통일 경로: slice_solidity(Dependencies/main.py:53) record 형식과 동일 → update_code 증분 적용.
            = SolQDebug 증분("quick") 강점 유지. full-slice-per-change 는 그 강점을 버리므로 안 함.

        syntax gate (누적 전체 기준):
          * delta 적용 후 *합쳐진 전체 코드*를 ANTLR(Parser/Solidity.g4) 파스. 실패 시
            Structure.diagnostics 채우고 이전 valid 구조 유지(표시만). solc 게이트는 보류(Diagnostic 참고).

        실배선:
          * records 를 update_code(SolidityAnalyzer.py:40) 경로로 적용해 visitor 가 CFG 구성.
          * CFG 구조 추출: line_info[ln]["cfg_nodes"], CFGNode flags/cond_type/edges(Utils/CFG.py).
          * debug_slots 도출(값 이전, 구조적):
              StateVar = 상태변수 선언, LocalVar = 함수 파라미터/로컬,
              GlobalVar = static 화이트리스트, IReturn = 인터페이스 호출 statement 등장.
          * 이 단계 nodes.state 는 빈 dict (값은 evaluate 가 채움).
        주의: 어노테이션 라인은 records 에 없음. 슬롯 line 부착점은 CFGNode.src_line 으로 프론트가 유도.
        """
        # fail-loud: 드라이버 에러는 그대로 전파. 유저 코드 syntax 검증은 별도(추후 ANTLR
        #   게이트가 누적 코드 파스 실패를 diagnostics 로 산출 — 버그 숨기는 catch-all 아님).
        diagnostics: list[Diagnostic] = []
        for rec in records:
            self._apply_code_record(rec["code"], rec["startLine"], rec["endLine"], rec["event"],
                                    rec.get("closeBefore", False))
        self._prev_records = list(records)  # B1 증분 diff 기준
        # 코드 변경 → 이전 states 캐시 전부 무효화 (analyze→evaluate→verify 체인 종속).
        self._states_cache.clear()
        return self.structure(contract, func, diagnostics)

    def structure(self, contract: Optional[str] = None, func: Optional[str] = None,
                  diagnostics: Optional[list] = None) -> Structure:
        """현재 세션 상태(fcfg)를 Structure 로 직렬화. analyze/update 후 공용."""
        contract, func, fcfg = self._resolve_fcfg(contract, func)
        self._scope = Scope(contract=contract or "", function=func or "")
        diags = diagnostics or []
        if fcfg is None:
            return Structure(scope=self._scope, cfg=CFG(entry="ENTRY", exit="EXIT"),
                             debug_slots=[], diagnostics=diags)
        cfg = _serialize_cfg(fcfg, self._ca.recorder, with_states=False)
        ccf = self._ca.contract_cfgs.get(contract) if contract else None
        # 이 함수의 소스 텍스트만 슬라이스(상태변수/글로벌 사용 판정용) — 함수 CFG 라인 스팬 기준.
        body_lines = [n.src_line for n in fcfg.graph.nodes() if getattr(n, "src_line", None)]
        lo_ln, hi_ln = (min(body_lines), max(body_lines)) if body_lines else (0, 1 << 30)
        func_src = "\n".join(r.get("code", "") for r in self._prev_records
                             if lo_ln <= r.get("startLine", -1) <= hi_ln)
        slots = _derive_debug_slots(fcfg, ccf, func_src, func or "",
                                    interface_names=getattr(self._ca, "interface_names", None))
        self._slots = {s.key: s for s in slots}
        return Structure(scope=self._scope, cfg=cfg, debug_slots=slots, diagnostics=diags)

    # ── B1 증분 편집 (§5.6 5단계) ───────────────────────────────────────────
    def update(self, new_source: str,
               contract: Optional[str] = None, func: Optional[str] = None) -> dict:
        """새 풀소스로 증분 갱신. SyntaxValid 게이트 → record-space diff → 변경분만 적용.

        적용 순서 = modify(무이동) → delete(아래부터) → add(위부터) 로 라인 좌표 정합 유지.
        invalid 면 {"ok": False, diagnostics} 반환하고 상태 유지(잘못된 부분삭제 CFG 손상 차단).
        """
        from incremental import diff_records, syntax_valid
        from Dependencies.main import slice_solidity

        ok, diags = syntax_valid(new_source)
        if not ok:
            return {"ok": False, "diagnostics": diags}

        new_records = slice_solidity(new_source)
        ops = diff_records(self._prev_records, new_records)
        mods = [o for o in ops if o.event == "modify"]
        dels = sorted((o for o in ops if o.event == "delete"), key=lambda o: o.start, reverse=True)
        adds = sorted((o for o in ops if o.event == "add"), key=lambda o: o.start)

        # 안전망(§5.6): surgical 미지원 구조(try/do-while/catch/break/continue)가 끼면 silent corruption
        #   위험 → 검증된 full-rebuild 로. 그 외는 surgical 시도하되 예외 시 rebuild 폴백.
        if any(_is_risky_op(o) for o in (dels + mods)):
            self._full_rebuild(new_records)
        else:
            try:
                for o in mods:
                    self._apply_modify(o)
                for o in dels:
                    self._apply_delete(o.start, o.end, o.kind)
                for o in adds:
                    self._apply_code_record(o.code, o.start, o.end, "add", o.close_before)
                self._prev_records = list(new_records)
            except Exception:
                self._full_rebuild(new_records)  # surgical 실패 → 안전 폴백

        self._states_cache.clear()
        return {"ok": True, "diagnostics": []}

    def _full_rebuild(self, records: list) -> None:
        """안전망: 분석기를 새로 만들어 records 전체 재적용(검증된 add-only 경로). 증분 실패 시 폴백."""
        from Analyzer.SolidityAnalyzer import SolidityAnalyzer
        from Analyzer.DebugUnitAnalyzer import DebugBatchManager
        self._sa = SolidityAnalyzer()
        self._ca = self._sa.contract_analyzer
        self._batch = DebugBatchManager(self._ca, self._ca.snapman)
        self._ca._capture_debug_fcfg = True
        if self._deps:
            _load_dependencies_into(self._sa, self._ca, self._deps)
        for rec in records:
            self._apply_code_record(rec["code"], rec["startLine"], rec["endLine"], rec["event"],
                                    rec.get("closeBefore", False))
        self._prev_records = list(records)

    def _apply_delete(self, start: int, end: int, kind: str) -> None:
        """CFG surgery(delete_cfg_range, line_info 사용) → 소스 라인 장부(update_code delete) 순.

        ★ 수술 대상 fcfg 는 반드시 현재 타겟 스코프로 지정. 생략하면 _resolve_fcfg 폴백이
          "컨트랙트의 마지막 함수"를 집어 **엉뚱한 CFG 를 수술**한다 → 타겟 함수엔 지운 문장
          노드가 그대로 남고(유령 노드) 소스 장부만 줄어 소스/CFG 가 어긋난다.
        """
        sc = self._scope or Scope(contract="", function="")
        _, _, fcfg = self._resolve_fcfg(sc.contract or None, sc.function or None)
        if fcfg is not None:
            self._ca.builder.delete_cfg_range(fcfg=fcfg, start_line=start, kind=kind,
                                              reinterpret=False)
        self._sa.update_code(start, end, "", "delete")

    def _apply_modify(self, op) -> None:
        """조건 헤더 변경 = in-place(body 보존); 단순 statement = delete+add."""
        if _is_condition_header(op.code):
            # update_code(modify)+visitor → process_* modify 분기에서 condition_expr in-place swap
            self._apply_code_record(op.code, op.start, op.end, "modify", op.close_before)
        else:
            self._apply_delete(op.start, op.end, op.kind)
            self._apply_code_record(op.code, op.start, op.end, "add", op.close_before)

    def evaluate(self, debug_values: dict[SlotKey, RangeValue],
                 contract: Optional[str] = None, func: Optional[str] = None) -> CfgWithStates:
        """debug 값 seed → fixpoint → CFG-with-states. [값 변경 트리거]

        실배선:
          * debug_values 를 캐논 텍스트로 직렬화(serialize.ts 형식) 후
            process_*_for_debug(ContractAnalyzer.py:2710~2876)로 등록.
          * snapshot → Engine.fixpoint(Interpreter/Engine.py:409) → states 가 CFGNode 에 채워짐.
          * ★ DebugBatchManager.flush(restore) 로 값 초기화되기 **직전**에
            CFGNode.variables/before_envs(Utils/CFG.py:47-48)를
            RecordManager 직렬화(Analyzer/RecordManager.py:292-325)로 떠서 CfgWithStates 로 복사.
          * 반환은 불변 스냅샷. 엔진 객체는 리셋된 채 다음 run 대기.
          * top_vars: ⊤(top) 으로 평가된 변수 수집(provenance 는 현재 None).
        """
        if contract or func:
            sc = self._scope or Scope(contract="", function="")
            self._scope = Scope(contract=contract or sc.contract, function=func or sc.function)
        self._last_debug_values = debug_values

        fcfg, frozen = self._interpret()
        # 값 입력 오류(Fix A) + intent 파싱 오류(Fix B) — 모든 반환 경로에 부착
        diags = list(self._last_value_errors) + list(self._last_intent_errors)
        if fcfg is None:
            return CfgWithStates(scope=self._scope or Scope("", ""),
                                 cfg=CFG(entry="ENTRY", exit="EXIT"), diagnostics=diags)
        if frozen is None:
            # 값 없음(또는 전부 미입력/오류) → 구조만. 프론트는 슬롯 입력/오류표시.
            cfg = _serialize_cfg(fcfg, self._ca.recorder, with_states=False)
            return CfgWithStates(scope=self._scope, cfg=cfg, top_vars=[], diagnostics=diags)

        self._states_cache[_values_key(debug_values)] = frozen

        cfg = _serialize_cfg(frozen, self._ca.recorder, with_states=True)
        top_vars = _collect_top_vars(frozen, scope=self._scope.function)
        return CfgWithStates(scope=self._scope, cfg=cfg, top_vars=top_vars, diagnostics=diags)

    def verify(self, intents: list[IntentItem],
               contract: Optional[str] = None, func: Optional[str] = None,
               debug_values: Optional[dict[str, RangeValue]] = None) -> list[VerdictItem]:
        """intent 판정 → verdict. [intent 변경 트리거]

        Stage 1(inline verify): intent 를 노드에 등록 후 debug 값으로 재해석 →
          해석 중 inline 검증이 analysis_per_line 에 verdict 기록 → 그걸 VerdictItem 으로 변환.
          (Stage 2 에서 보존 states 에 guardian 사후 호출하는 standalone P2 로 재해석 제거 예정.)

        소프트 게이트(결정 22): debug 값이 없으면 verdict 없음([]) — 프론트가 auto-fill 유도.

        ★ 세션은 "소스의 캐시"일 뿐 클라이언트 상태의 주인이 아니다: debug 값은 항상 호출자가
          싣고 온 것(debug_values)을 쓴다. 서버 기억(_last_debug_values)에 기대면, 값을 persist
          하지 않는 프론트(세션성, decision #32)가 재접속했을 때 **이전 생애의 유령 값**으로
          verdict 가 나와 위 소프트 게이트가 무력화된다.
        """
        if contract or func:
            sc = self._scope or Scope(contract="", function="")
            self._scope = Scope(contract=contract or sc.contract, function=func or sc.function)
        if debug_values is not None:
            self._last_debug_values = debug_values
        self._intents = intents or []

        if not self._last_debug_values:
            return []  # debug 컨텍스트 없음 → auto-fill 유도

        # Stage 2 standalone P2: 이번 값으로 계산된 보존 states 가 있으면 재해석 없이 사후 검증.
        #   (직전 evaluate 의 키가 아니라 "이번 요청 값"의 키로 조회 — Apply 흐름에선 동일 키라 적중.)
        frozen = self._states_cache.get(_values_key(self._last_debug_values))
        if frozen is not None:
            return self._verify_standalone(frozen, self._intents)

        # fallback(Stage 1 inline): states 캐시 없으면 전체 재해석.
        self._ca.analysis_per_line.clear()
        _, frozen = self._interpret()
        if frozen is None:
            return []
        return _extract_verdict(self._ca)

    def _verify_standalone(self, frozen_fcfg, intents: list[IntentItem]) -> list[VerdictItem]:
        """Stage 2: 보존 states(frozen_fcfg)에 guardian 사후 호출 → **재해석 없이** verdict.
        intent 파싱은 live fcfg 에 attach(파서 재사용) 후 node 이름으로 frozen 에 미러링.
        frozen states 는 읽기만(불변) → 캐시 재사용 유효."""
        sc = self._scope or Scope(contract="", function="")
        _, _, live_fcfg = self._resolve_fcfg(sc.contract or None, sc.function or None)
        if live_fcfg is None:
            return []
        self._set_context(live_fcfg, sc.contract, sc.function)
        self._attach_intents(live_fcfg, intents)

        # live node.intents → frozen node.intents (이름 매칭). exit 노드(post) 포함.
        live_by_name = {n.name: list(getattr(n, "intents", []) or [])
                        for n in live_fcfg.graph.nodes()}
        for fn in frozen_fcfg.graph.nodes():
            fn.intents = list(live_by_name.get(fn.name, []))

        engine = self._ca.engine
        prev = getattr(self._ca, "current_target_function_cfg", None)
        self._ca.current_target_function_cfg = frozen_fcfg
        engine._record_enabled = True
        self._ca.analysis_per_line.clear()
        try:
            for node in frozen_fcfg.graph.nodes():
                if getattr(node, "intents", None):
                    engine._process_node_intents(node, node.variables, node.src_line)
            engine._process_post_annotations(frozen_fcfg)
        finally:
            self._ca.current_target_function_cfg = prev
        return _extract_verdict(self._ca)


# ─────────────────────────────────────────────────────────────────────────────
# 결합 export — send_report_to_front(print) 대체. 프론트 AnalysisResult 계약으로 직렬화.
# ─────────────────────────────────────────────────────────────────────────────


class AnalysisResultDict(TypedDict):
    """frontend/src/types/result.ts AnalysisResult 와 동일. analyzeClient 가 그대로 소비."""
    scope: dict
    cfg: dict
    verdict: list[dict]
    top_vars: list[dict]
    intents: list[dict]
    debugSlots: list[dict]


def to_analysis_result(
    structure: Structure,
    states: CfgWithStates,
    verdict: list[VerdictItem],
    intents: list[IntentItem],
) -> AnalysisResultDict:
    """3단계 산출 + intent 를 프론트 1개 객체로 합성(states.cfg 를 navigation substrate 로 사용).

    ContractAnalyzer.send_report_to_front(print만, ContractAnalyzer.py:2934)를 대체하는 출력층.
    """
    # states 가 있으면 그 cfg(=navigation substrate, states 채워짐), 없으면 구조 cfg.
    cfg = states.cfg if (states and states.cfg.nodes) else structure.cfg
    scope = (states.scope if states else None) or structure.scope
    top_vars = states.top_vars if states else []
    return {
        "scope": asdict(scope),
        "cfg": _cfg_to_dict(cfg),
        "verdict": [asdict(v) for v in verdict],
        "top_vars": [asdict(t) for t in top_vars],
        "intents": [asdict(i) for i in intents],
        "debugSlots": [asdict(s) for s in structure.debug_slots],
    }


def analyze_once(
    records: list[Record],
    debug_values: Optional[dict[SlotKey, RangeValue]] = None,
    intents: Optional[list[IntentItem]] = None,
    deps: Optional[list[DepSpec]] = None,
) -> AnalysisResultDict:
    """세션 없이 fresh 1회 통짜 분석(L2 실험·격리 실행용). [인터랙티브는 3콜, 실험은 이 1콜]

    내부: EngineSession(deps) 만들어 analyze → evaluate → verify → to_analysis_result 후 close.
    인터랙티브 캐시 계층(dirty 신호)이 필요 없는 배치/격리 시나리오 전용.
    """
    sess = EngineSession(deps)
    try:
        structure = sess.analyze(records)
        states = sess.evaluate(debug_values or {})
        verdict = sess.verify(intents or [])
        return to_analysis_result(structure, states, verdict, intents or [])
    finally:
        sess.close()


# ─────────────────────────────────────────────────────────────────────────────
# 생성 보조 (solver/LLM) — 표면 분리, 내부 generator 공유. async/느림. L2 originality.
# ─────────────────────────────────────────────────────────────────────────────


def suggest_value(session: EngineSession, slot: DebugSlot) -> Suggestion:
    """opaque 슬롯(@IReturn 등)에 그럴듯한 값 제안. target 없는 단일-슬롯 생성.

    derivable → solver, opaque(외부값) → LLM. 무엇이 나은지는 L2 실험이 결정(backend-agnostic).
    """
    raise NotImplementedError("suggest_value")


def reach(session: EngineSession, target: Union[str, IntentItem]) -> dict[SlotKey, RangeValue]:
    """특정 path(노드 id) 또는 intent 가 걸린 path 를 live(비-⊥)로 만드는 debug 값 합성.

    = target 있는 값 생성(witness). path condition 만족 = solver 주도(derivable),
      외부값 결부 시 LLM 보조. suggest_value 와 generator 공유, 목표만 다름.
    """
    raise NotImplementedError("reach")


def cover(session: EngineSession, scope: Optional[Scope] = None) -> list[dict[SlotKey, RangeValue]]:
    """전 분기를 커버하는 debug 입력 집합 생성. reach 를 분기마다 반복. [후순위]"""
    raise NotImplementedError("cover")


def suggest_intent(
    source: str,
    comments: Optional[str] = None,
    patterns: Optional[list[str]] = None,
) -> list[IntentItem]:
    """변수 관계 + 자연어 주석 + 알려진 numeric-logic-error 취약점 패턴 → intent 후보 제안.

    입력이 코드 records 가 아니라 **원문 소스(주석 포함)** + 패턴 DB 라서 코어와 분리된 별 surface.
    LLM 주도.
    """
    raise NotImplementedError("suggest_intent")


# ─────────────────────────────────────────────────────────────────────────────
# Root B — Dependency 관리 (생애주기: 첨부 1회 빌드 → pkl 캐시 영속)
# ─────────────────────────────────────────────────────────────────────────────


class DependencyStore:
    """첨부 .sol 의존성을 slice → analyze_file → pkl 로 빌드/캐시.

    실배선: Dependencies/main.py slice_solidity(:53), analyze_file(→ ifc_/lib_/con_*.pkl).
            임의 첨부 순서 해석엔 자동 topo-sort 필요(현재 _con_order 하드코딩, 미구현).
    """

    def build(self, name: str, source: str) -> DepInfo:
        """.sol 원문 → slice → analyze_file → ifc_/lib_/con_*.pkl 저장. building → ready."""
        raise NotImplementedError("DependencyStore.build")

    def list(self) -> list[DepInfo]:
        """빌드된 의존성 목록."""
        raise NotImplementedError("DependencyStore.list")

    def remove(self, name: str) -> None:
        """의존성 pkl 제거."""
        raise NotImplementedError("DependencyStore.remove")
