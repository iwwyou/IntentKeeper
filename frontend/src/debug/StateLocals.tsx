import { useStore, keyOf } from '../state/store'
import type { AnalysisResult, RangeValue } from '../types/result'
import type { NavState } from './useNavigation'

// 커서 노드의 추상상태 + 도달 경로. 커서 이동 시 갱신(엔진 호출 없음).
// ★ 표시 상태 = "이 줄 실행 직전"(pre-state) = 선행(predecessor) 노드의 out-state.
//   엔진 CFGNode.state 는 out-state(실행 후)라 그대로 쓰면 breakpoint 에서 실행-후 값이 보임(버그).
//   선행 out-state 를 쓰면 별도 in-state 필드 없이 pre-state 가 된다.
//   - 단일 선행: 그 out-state
//   - 선행이 ENTRY(빈 상태): 시드 진입상태 폴백(debugInputs + 불변 전역)
//   - 다중 선행(조인): TODO(2) — 우선 노드 자신 out-state (merge 미구현, PROGRESS §5.8 참조)
function fmtRange(v: RangeValue): string {
  return v.t === 'interval'
    ? `[${v.lo},${v.hi}]`
    : v.t === 'bool'
    ? v.v
    : v.t === 'address'
    ? `address(${v.id})`
    : '-'
}

const isGlobal = (k: string) =>
  k.startsWith('block.') || k.startsWith('msg.') || k.startsWith('tx.')

export default function StateLocals({ nav, result }: { nav: NavState; result: AnalysisResult }) {
  const node = nav.node
  const flags = node?.flags ?? []
  const cfg = result.cfg

  const activeContract = useStore((s) => s.activeContract)
  const activeFunction = useStore((s) => s.activeFunction)
  const debugInputs = useStore((s) => s.debugInputs)

  // entry→cursor 단순 경로 (mock: 첫 predecessor 따라 역추적)
  const path: number[] = []
  if (node) {
    let cur: string | undefined = node.id
    const seen = new Set<string>()
    while (cur && !seen.has(cur)) {
      seen.add(cur)
      const n = cfg.nodes.find((x) => x.id === cur)
      if (n) path.unshift(n.src_line)
      const e = cfg.edges.find((x) => x.to === cur && x.kind !== 'back_edge')
      cur = e?.from
    }
  }

  // pre-state 계산: 선행 out-state (또는 ENTRY 시드 폴백 / 조인 fallback)
  const preds = node
    ? cfg.edges
        .filter((e) => e.to === node.id && e.kind !== 'back_edge')
        .map((e) => cfg.nodes.find((n) => n.id === e.from))
        .filter((n): n is NonNullable<typeof n> => !!n)
    : []

  let displayState: Record<string, string> = node?.state ?? {}
  let stateNote = ''
  if (node) {
    if (node.id === cfg.exit) {
      // 함수 끝 = 최종(실행 후) 상태 그대로.
      displayState = preds.length === 1 ? preds[0].state : node.state
      stateNote = '최종 상태'
    } else if (preds.length === 1) {
      const p = preds[0]
      const pEmpty = p.id === cfg.entry || Object.keys(p.state).length === 0
      if (pEmpty) {
        // ENTRY 폴백: 노드 out-state 에서 시작해 "시드된 진입값"만 override.
        //   (미시드 변수·전역은 실행 전후 불변이라 out-state 값이 곧 진입값 → 그대로 유지)
        const seeded: Record<string, string> = {}
        const inputs = debugInputs[keyOf(activeContract, activeFunction)] ?? {}
        for (const [k, v] of Object.entries(inputs)) seeded[k] = fmtRange(v)
        displayState = { ...node.state, ...seeded }
        stateNote = '진입 상태 (이 줄 실행 전)'
      } else {
        displayState = p.state
        stateNote = '이 줄 실행 전'
      }
    } else if (preds.length > 1) {
      // 설정단에서 구조적 노드(merge/loop_exit/φ) breakpoint 를 막으므로 여기 도달은 사실상 없음.
      // 방어적 fallback: 노드 자신 out-state + 라벨.
      displayState = node.state
      stateNote = '조인 — 실행 후 (merge 미구현)'
    }
    // 루프 본문 statement: pre-state 는 fixpoint 결과라 "특정 iteration"이 아니라 불변식(모든 iteration).
    if (stateNote && flags.includes('loop_body')) {
      stateNote += ' · 루프 불변식(모든 iteration)'
    }
  }

  const valClass = (v: string) =>
    v.includes('⊤') || v === 'top' ? 'v top' : v.includes('-') ? 'v neg' : 'v'

  const entries = Object.entries(displayState)
  const realEntries = entries.filter(([k]) => !isGlobal(k))
  const globalEntries = entries.filter(([k]) => isGlobal(k))

  return (
    <div style={{ marginTop: 14 }}>
      <div className="panel-title">
        State &amp; Locals
        {node && <span style={{ color: '#666', marginLeft: 8 }}>@ L{node.src_line} ({node.id})</span>}
      </div>
      {stateNote && <div className="state-note">{stateNote}</div>}
      {flags.length > 0 && (
        <div style={{ fontSize: 11, color: '#c586c0', marginBottom: 6 }}>
          {flags.join(', ')}
          {flags.includes('fixpoint_evaluation') && ' — loop invariant (모든 iteration 성립)'}
        </div>
      )}
      {node && entries.length === 0 && <div style={{ color: '#666' }}>(빈 상태)</div>}
      {node && entries.length > 0 && realEntries.length === 0 && (
        <div style={{ color: '#666' }}>(로컬/상태 변수 없음 — 전역만)</div>
      )}
      {realEntries.map(([k, v]) => (
        <div className="kv" key={k}>
          <span>{k}</span>
          <span className={valClass(v)}>{v}</span>
        </div>
      ))}

      {globalEntries.length > 0 && (
        <details className="globals">
          <summary>전역 변수 (block/msg/tx) · {globalEntries.length}</summary>
          {globalEntries.map(([k, v]) => (
            <div className="kv" key={k}>
              <span>{k}</span>
              <span className={valClass(v)}>{v}</span>
            </div>
          ))}
        </details>
      )}

      <div className="path">
        path: {path.filter((l) => l >= 0).map((l) => `L${l}`).join(' → ')}
      </div>
      {nav.highlightedPreds.length > 1 && (
        <div className="preds">
          merge backward: {nav.highlightedPreds.join(', ')} 양쪽 비-⊥ → 모두 하이라이트
        </div>
      )}
    </div>
  )
}
