// engine_api 출력 스키마 (mock·실엔진 공통 계약)
// 이 타입들의 합집합 = engine_api `analyze()`가 반환해야 하는 것.

export type NodeFlag =
  | 'condition'
  | 'branch_then'
  | 'branch_else'
  | 'merge'
  | 'fixpoint_evaluation' // loop fixpoint 노드
  | 'loop_exit'
  | 'loop_body'
  | 'exit'

export type EdgeKind = 'normal' | 'true' | 'false' | 'back_edge'

export interface CFGNode {
  id: string
  src_line: number
  flags: NodeFlag[]
  cond_type?: string // if | else_if | require | while | for | do_while
  /** 변수명 → 직렬화된 추상값 ("[lo,hi]" | "address(⊤)" | "top" | ...) */
  state: Record<string, string>
  /** merge 노드면 join에 기여한 predecessor 노드 id들 (backward 양쪽 하이라이트용) */
  join_from?: string[]
}

export interface CFGEdge {
  from: string
  to: string
  kind: EdgeKind
}

export interface CFG {
  entry: string
  exit: string
  return_exit?: string
  error_exit?: string
  nodes: CFGNode[]
  edges: CFGEdge[]
}

export type Verdict = 'Satisfied' | 'Warning' | 'Violated'

// 위반 영역. **출력공간**(비교되는 값의 구간)이지 입력 파라미터 구간이 아니다 —
// 입력공간 역전파/분할은 decision #40 (B) 몫. warning·단일 절(during)일 때만 존재.
// 경계는 2^256 까지 가능 → 문자열(엔진 IntervalValue 와 동일 규약).
export interface FalseRegions {
  lowerViolation: [string, string] | null // intent 하한 아래로 벗어난 구간
  upperViolation: [string, string] | null // intent 상한 위로 벗어난 구간
  overlapZone: [string, string] | null // 겹치는 불확정 구간
}

export interface VerdictItem {
  line: number
  node: string
  type: string
  status: Verdict
  risk: number // 0..10
  region: [number, number]
  message: string
  falseRegions?: FalseRegions | null // 없으면 undefined/null
}

export interface TopVar {
  var: string
  kind: string
  node: string
  src_line: number
  scope: string
  provenance: string | null // ⊤ 출처 태깅 (현재 엔진엔 없음 → null)
}

export type DebugKind = 'StateVar' | 'LocalVar' | 'GlobalVar' | 'IReturn'

// 값 입력 종류 — 슬롯의 타입이 결정 (numeric→interval, bool→bool, address→symbolicAddress)
export type ValueKind = 'interval' | 'bool' | 'address' | 'array' | 'bytes' | 'enum'

// 사용자가 입력하는 값 (debugValue 캐논으로 직렬화됨)
export type RangeValue =
  | { t: 'interval'; lo: string; hi: string }
  | { t: 'bool'; v: 'true' | 'false' | 'any' }
  | { t: 'address'; id: number } // symbolicAddress N
  | { t: 'none' }

export interface Suggestion {
  value: RangeValue
  backend: 'llm' | 'solver' | 'hybrid' // 2번 결정 보류 → 추상화
  confidence: number
}

// ★ 분석이 주는 "debuggable slot" — 사용자는 값만 채움.
//   엔진이 상태변수/파라미터/글로벌/인터페이스호출을 알고 슬롯 생성.
export interface DebugSlot {
  kind: DebugKind
  key: string // 캐논 타겟: "balance" | "a" | "msg.sender" | "token.balanceOf()"
  label: string // 표시용
  valueKind: ValueKind
  opaque?: boolean // @IReturn/외부 등 도출 불가
  line?: number // debug는 대체로 함수-스코프 → 보통 생략
  suggestion?: Suggestion // ghost 제안 (LLM/solver)
}

export type DepStatus = 'ready' | 'building' | 'error'

export interface DepItem {
  name: string
  kind: 'interface' | 'library' | 'contract'
  status: DepStatus
}

export interface IntentItem {
  scopeKind: 'During' | 'Post'
  line?: number
  text: string
}

export interface AnalysisResult {
  scope: { contract: string; function: string }
  cfg: CFG
  verdict: VerdictItem[]
  top_vars: TopVar[]
  intents: IntentItem[]
  /** 분석이 노출하는 debuggable slots (사용자는 값만 채움) */
  debugSlots: DebugSlot[]
}
