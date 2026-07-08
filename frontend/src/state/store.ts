// 공유 앱 상태. 워크스페이스/디버그 두 화면이 같은 상태를 구독.
// 원칙: 분석 트리거(편집/입력/intent/deps 변경)만 results를 갱신.
//       화면 전환(view)·step navigation은 트리거가 아니라 "표시"일 뿐.
// 영속: files/activeFile/deps/debugInputs를 localStorage에 저장(zustand persist).

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AnalysisResult, RangeValue, DepItem, IntentItem } from '../types/result'
import { analyzeStructure, evaluate, verify } from '../engine/analyzeClient'
import workspace from '../mock/workspace.json'

export interface FunctionMeta {
  name: string
  contract: string
  startLine: number
  source: string
}

export interface FileItem {
  path: string
  content: string
}

type View = 'workspace' | 'debug'

// 분석 tier = dirty 신호. 액션 종류가 어느 tier부터 재계산할지 결정.
//   structure: 코드 편집 → CFG 재구성(+하위 evaluate/verify)
//   evaluate : 값 변경   → fixpoint만(+verify)  (CFG 구조 재사용)
//   verify   : intent 변경 → 판정만            (CFG·states 재사용)
type AnalysisTier = 'structure' | 'evaluate' | 'verify'

interface AppState {
  view: View
  files: FileItem[]
  activeFile: string
  functions: FunctionMeta[]
  deps: DepItem[]
  depContents: Record<string, string> // 첨부 .sol 원문 (나중에 pkl 빌드용)

  activeContract: string
  activeFunction: string

  debugInputs: Record<string, Record<string, RangeValue>> // funcKey → slotKey → 값
  intents: Record<string, IntentItem[]> // 함수키별 작성된 intent (패널 메타데이터 + lineRef)
  results: Record<string, AnalysisResult>
  analyzing: boolean
  analyzeError: string | null // 분석 실패(서버 500/네트워크) — 배너 표시
  valueErrors: { line: number; message: string }[] // debug 값 입력 오류(슬롯 옆 표시)
  applyTick: number // Apply(evaluate) 실행마다 +1 — nav 가 결과 노드로 커서 재배치하는 신호

  setView: (v: View) => void

  // 파일 관리
  setActiveFile: (path: string) => void
  newFile: (path: string) => void
  openFile: (path: string, content: string) => void
  deleteFile: (path: string) => void
  updateActiveContent: (content: string) => void

  // 디버그
  openDebug: (contract: string, func: string) => void
  setActiveFunction: (func: string) => void
  setDebugValue: (func: string, slotKey: string, value: RangeValue) => void
  applyDebug: (func?: string) => void // Apply 버튼/Enter → 모든 슬롯 값 한 번에 evaluate

  // intent (코드 밖 패널, lineRef로 부착 — 코드 삽입/밀림 없음)
  addIntent: (key: string, item: IntentItem) => void
  removeIntent: (key: string, index: number) => void

  // 의존성
  attachDep: (name: string, content: string) => void

  runAnalysis: (func?: string, tier?: AnalysisTier) => Promise<void>
}

const ws = workspace as {
  source: string
  contracts: string[]
  functions: FunctionMeta[]
  deps: DepItem[]
}

function keyOf(contract: string, func: string) {
  return `${contract}.${func}`
}

function funcOfKey(key: string) {
  const i = key.indexOf('.')
  return i >= 0 ? key.slice(i + 1) : key
}

function detectKind(content: string): DepItem['kind'] {
  if (/\binterface\s+\w+/.test(content)) return 'interface'
  if (/\blibrary\s+\w+/.test(content)) return 'library'
  return 'contract'
}

function activeContent(s: AppState): string {
  return s.files.find((f) => f.path === s.activeFile)?.content ?? ''
}

export const useStore = create<AppState>()(
  persist(
    (set, get) => ({
      view: 'workspace',
      files: [{ path: 'Vault.sol', content: ws.source }],
      activeFile: 'Vault.sol',
      functions: ws.functions,
      deps: ws.deps,
      depContents: {},

      activeContract: ws.contracts[0] ?? 'Vault',
      activeFunction: ws.functions[0]?.name ?? 'withdraw',

      // 디버그 값은 빈 칸으로 시작(자동입력 X) — 사용자가 채우고 Apply(decision #32).
      debugInputs: {},
      // intent 도 빈 상태로 시작 — mock intent 를 시드하면 실엔진 verify 로 유령 @During 이 새서
      // crash(파싱실패)를 유발했음(debugInputs 누수와 동형). 사용자가 패널에서 추가할 때만 전송.
      intents: {},
      results: {},
      analyzing: false,
      analyzeError: null,
      valueErrors: [],
      applyTick: 0,

      setView: (v) => set({ view: v }),

      setActiveFile: (path) => set({ activeFile: path }),

      newFile: (path) => {
        if (!path || get().files.some((f) => f.path === path)) return
        set({ files: [...get().files, { path, content: '' }], activeFile: path })
      },

      openFile: (path, content) => {
        const exists = get().files.some((f) => f.path === path)
        const files = exists
          ? get().files.map((f) => (f.path === path ? { ...f, content } : f))
          : [...get().files, { path, content }]
        set({ files, activeFile: path })
        void get().runAnalysis(undefined, 'structure')
      },

      deleteFile: (path) => {
        const files = get().files.filter((f) => f.path !== path)
        const activeFile =
          get().activeFile === path ? files[0]?.path ?? '' : get().activeFile
        set({ files, activeFile })
      },

      updateActiveContent: (content) => {
        const af = get().activeFile
        set({ files: get().files.map((f) => (f.path === af ? { ...f, content } : f)) })
        // edit-time: 편집 → 코드 변경 = structure tier (디바운스는 호출측)
        void get().runAnalysis(undefined, 'structure')
      },

      openDebug: (contract, func) => {
        set({ view: 'debug', activeContract: contract, activeFunction: func })
        // 디버그는 워크스페이스 편집 때 만들어진 CFG 를 가져다 씀(fetch) — 캐시 없을 때만 1회 빌드.
        if (!get().results[keyOf(contract, func)]) void get().runAnalysis(func, 'structure')
      },

      setActiveFunction: (func) => {
        set({ activeFunction: func })
        if (!get().results[keyOf(get().activeContract, func)]) void get().runAnalysis(func, 'structure')
      },

      setDebugValue: (func, slotKey, value) => {
        // 키는 keyOf(contract, func) 로 통일 — 표시(DebugInputPanel)·시드와 동일 키.
        // ★ 값 변경은 상태만 갱신하고 evaluate 는 발사하지 않음(per-keystroke 낭비 제거).
        //   실제 실행은 applyDebug(Apply 버튼/Enter)에서 한 번에. (decision #32)
        const fk = keyOf(get().activeContract, func)
        const cur = get().debugInputs[fk] ?? {}
        set({ debugInputs: { ...get().debugInputs, [fk]: { ...cur, [slotKey]: value } } })
      },

      applyDebug: (func) => {
        // 모든 슬롯 값 통째로 evaluate(백엔드는 이미 debugInputs 전체 전송 → 번들 무변경).
        void get().runAnalysis(func ?? get().activeFunction, 'evaluate')
      },

      addIntent: (key, item) => {
        const cur = get().intents[key] ?? []
        set({ intents: { ...get().intents, [key]: [...cur, item] } })
        void get().runAnalysis(funcOfKey(key), 'verify') // intent 변경 = verify만
      },

      removeIntent: (key, index) => {
        const cur = get().intents[key] ?? []
        set({ intents: { ...get().intents, [key]: cur.filter((_, i) => i !== index) } })
        void get().runAnalysis(funcOfKey(key), 'verify')
      },

      attachDep: (name, content) => {
        if (get().deps.some((d) => d.name === name)) return
        set({
          deps: [...get().deps, { name, kind: detectKind(content), status: 'building' }],
          depContents: { ...get().depContents, [name]: content },
        })
        // stub: 실엔진이면 slice_solidity → analyze_file → pkl 저장. 지금은 building→ready.
        setTimeout(() => {
          set({
            deps: get().deps.map((d) => (d.name === name ? { ...d, status: 'ready' } : d)),
          })
        }, 1200)
      },

      // tier 체인: structure → evaluate → verify. dirty 신호(tier)에 따라 진입 지점만 다름.
      // 캐시 없으면(첫 분석) tier 무관하게 structure부터. verify는 항상 마지막에 한 번.
      runAnalysis: async (func, tier = 'structure') => {
        const s = get()
        const fn = func ?? s.activeFunction
        const contract = s.activeContract
        if (!fn) return
        const key = keyOf(contract, fn)
        const intents = get().intents[key] ?? []
        const req = {
          contract,
          func: fn,
          source: activeContent(s),
          inputs: s.debugInputs[key] ?? {}, // key = keyOf(contract, fn) — 표시/시드와 동일 키
          intents,
        }

        const cur = get().results[key]
        const needStructure = tier === 'structure' || !cur
        // ★ evaluate 는 structure 와 분리(decision #32): 코드편집·디버그진입(structure)은 CFG 구조만,
        //   값 계산은 Apply(evaluate)에서만. (진입만으로 자동 계산되던 버그 제거)
        const needEvaluate = tier === 'evaluate'
        const needVerify = needEvaluate || tier === 'verify' // states 의미있을 때만 verdict 갱신

        // 새 분석 시작 → 이전 오류 클리어. finally 로 analyzing 항상 해제(멈춤 방지).
        set({ analyzing: true, analyzeError: null })

        let scope = cur?.scope ?? { contract, function: fn }
        let cfg = cur?.cfg
        let debugSlots = cur?.debugSlots ?? []
        let topVars = cur?.top_vars ?? []
        let valueErrors: { line: number; message: string }[] = []

        try {
          if (needStructure) {
            const st = await analyzeStructure(req)
            if (!st) return
            scope = st.scope
            cfg = st.cfg
            debugSlots = st.debugSlots
            // TODO: st.diagnostics → 편집기 squiggle (지금 mock은 빈 배열)
          }
          if (needEvaluate) {
            const ev = await evaluate(req)
            if (ev) {
              scope = ev.scope
              cfg = ev.cfg // states 채워진 CFG = navigation substrate
              topVars = ev.top_vars
              valueErrors = (ev.diagnostics ?? []).map((d) => ({ line: d.line, message: d.message }))
            }
          }
          // verify 는 states 가 의미있을 때만(Apply=evaluate 또는 intent 변경). structure-only 진입엔 스킵.
          let verdict = cur?.verdict ?? []
          if (needVerify) {
            const vf = await verify(req)
            verdict = vf.verdict
          }

          if (!cfg) return
          const result: AnalysisResult = {
            scope,
            cfg,
            verdict,
            top_vars: topVars,
            intents,
            debugSlots,
          }
          set({ results: { ...get().results, [key]: result }, valueErrors })
          // evaluate 가 실제로 돈 경우에만 nav 재배치 신호(intent-only verify 는 커서 안 옮김).
          if (needEvaluate) set({ applyTick: get().applyTick + 1 })
        } catch (e) {
          // 서버 500/네트워크 실패 → 배너로 표시(과거엔 여기서 analyzing 이 안 풀려 멈춤).
          set({ analyzeError: e instanceof Error ? e.message : String(e) })
        } finally {
          set({ analyzing: false })
        }
      },
    }),
    {
      name: 'iqdebug-workspace',
      version: 3, // v3: debugInputs 는 세션성(persist 제외) — what-if 값 자동복원 안 함
      migrate: (persisted: unknown, version: number) => {
        const p = persisted as Record<string, unknown> | null
        if (p && version < 2) {
          // 구버전 debugInputs(배열)·intents 폐기 → 초기 seed 사용
          delete p.debugInputs
          delete p.intents
        }
        if (p && version < 3) {
          // debugInputs 세션성 전환 → 잔재 클리어(자동입력 방지)
          delete p.debugInputs
        }
        return p
      },
      partialize: (s) => ({
        files: s.files,
        activeFile: s.activeFile,
        deps: s.deps,
        depContents: s.depContents,
        intents: s.intents,
        // debugInputs 제외: 새로고침 시 빈 칸으로 시작(세션성).
      }),
    }
  )
)

export { keyOf }
