// ★ 실엔진 교체 지점(seam). engine_server(FastAPI) → engine_api 계약과 1:1.
// 인터랙티브 = 3콜(analyze/evaluate/verify), dirty 신호는 호출 tier가 곧 전달.
//   코드 편집 → analyzeStructure (+ 하위 evaluate/verify)
//   값 변경   → evaluate (+ verify)
//   intent 변경 → verify
// navigation 은 로컬(0콜). 실험/격리용 1콜 = analyzeOnce.
// 서버 세션("contract.func")이 3콜을 묶어 states 캐시/standalone P2 활용.

import type {
  AnalysisResult,
  CFG,
  DebugSlot,
  IntentItem,
  RangeValue,
  TopVar,
  VerdictItem,
} from '../types/result'

const BASE =
  ((import.meta as unknown as { env?: { VITE_ENGINE_URL?: string } }).env?.VITE_ENGINE_URL) ??
  'http://127.0.0.1:8000'

export interface AnalyzeRequest {
  contract: string
  func: string
  source: string
  inputs: Record<string, RangeValue> // slotKey → 값
  intents?: IntentItem[]
}

export interface Diagnostic {
  line: number
  message: string
  severity: 'error' | 'warning'
}

// analyze() = CFG 구조 + 빈 슬롯 (값/상태 없음) + syntax diagnostics
export interface StructureResult {
  scope: { contract: string; function: string }
  cfg: CFG // nodes.state == {} (구조만)
  debugSlots: DebugSlot[]
  diagnostics: Diagnostic[]
}

// evaluate() = fixpoint 후 states 채워진 CFG (navigation substrate) + ⊤ 변수
export interface EvaluateResult {
  scope: { contract: string; function: string }
  cfg: CFG // nodes.state 채워짐
  top_vars: TopVar[]
  diagnostics?: Diagnostic[] // debug 값 입력 오류(잘못된 interval 등) — 슬롯 옆 표시
}

// verify() = intent 판정
export interface VerifyResult {
  verdict: VerdictItem[]
}

async function post<T>(path: string, req: AnalyzeRequest): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    throw new Error(`engine ${path} ${res.status}: ${await res.text()}`)
  }
  return (await res.json()) as T
}

/** 코드 편집 tier — CFG 구조 + debug 슬롯 + diagnostics. [코드 변경 트리거] */
export async function analyzeStructure(req: AnalyzeRequest): Promise<StructureResult | null> {
  return post<StructureResult>('/analyze', req)
}

/** 값 tier — debug 값 seed → fixpoint → CFG-with-states. [값 변경 트리거] */
export async function evaluate(req: AnalyzeRequest): Promise<EvaluateResult | null> {
  return post<EvaluateResult>('/evaluate', req)
}

/** intent tier — states 읽어 판정. [intent 변경 트리거] */
export async function verify(req: AnalyzeRequest): Promise<VerifyResult> {
  return post<VerifyResult>('/verify', req)
}

/** 실험/격리용 1콜 — 통짜 Result (engine_api.analyze_once 대응). */
export async function analyzeOnce(req: AnalyzeRequest): Promise<AnalysisResult | null> {
  return post<AnalysisResult>('/analyze_once', req)
}
