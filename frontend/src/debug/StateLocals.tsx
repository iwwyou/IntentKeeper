import type { AnalysisResult } from '../types/result'
import type { NavState } from './useNavigation'

// 커서 노드의 추상상태 + 도달 경로. 커서 이동 시 갱신(엔진 호출 없음).
export default function StateLocals({ nav, result }: { nav: NavState; result: AnalysisResult }) {
  const node = nav.node
  const flags = node?.flags ?? []

  // entry→cursor 단순 경로 (mock: 첫 predecessor 따라 역추적)
  const path: number[] = []
  if (node) {
    let cur: string | undefined = node.id
    const seen = new Set<string>()
    while (cur && !seen.has(cur)) {
      seen.add(cur)
      const n = result.cfg.nodes.find((x) => x.id === cur)
      if (n) path.unshift(n.src_line)
      const e = result.cfg.edges.find((x) => x.to === cur && x.kind !== 'back_edge')
      cur = e?.from
    }
  }

  const valClass = (v: string) =>
    v.includes('⊤') || v === 'top' ? 'v top' : v.includes('-') ? 'v neg' : 'v'

  return (
    <div style={{ marginTop: 14 }}>
      <div className="panel-title">
        State &amp; Locals
        {node && <span style={{ color: '#666', marginLeft: 8 }}>@ L{node.src_line} ({node.id})</span>}
      </div>
      {flags.length > 0 && (
        <div style={{ fontSize: 11, color: '#c586c0', marginBottom: 6 }}>
          {flags.join(', ')}
          {flags.includes('fixpoint_evaluation') && ' — loop invariant (모든 iteration 성립)'}
        </div>
      )}
      {node && Object.keys(node.state).length === 0 && (
        <div style={{ color: '#666' }}>(빈 상태)</div>
      )}
      {node &&
        Object.entries(node.state).map(([k, v]) => (
          <div className="kv" key={k}>
            <span>{k}</span>
            <span className={valClass(v)}>{v}</span>
          </div>
        ))}

      <div className="path">path: {path.map((l) => `L${l}`).join(' → ')}</div>
      {nav.highlightedPreds.length > 1 && (
        <div className="preds">
          merge backward: {nav.highlightedPreds.join(', ')} 양쪽 비-⊥ → 모두 하이라이트
        </div>
      )}
    </div>
  )
}
