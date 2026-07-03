import type { AnalysisResult } from '../types/result'
import type { NavState } from './useNavigation'

export default function VerdictPanel({ result, nav }: { result: AnalysisResult; nav: NavState }) {
  return (
    <div>
      <div className="panel-title">Verdict</div>
      {result.verdict.length === 0 && <div style={{ color: '#6ac46a' }}>● Satisfied</div>}
      {result.verdict.map((v, i) => (
        <div
          key={i}
          className={`verdict-item ${v.status}`}
          onClick={() => nav.jumpToNode(v.node)}
          title="클릭 → 위반 지점으로 점프"
        >
          <span className="risk">{v.risk}/10</span>
          <div>
            <b>{v.status}</b> · {v.type} · L{v.line}
          </div>
          <div className="msg">{v.message}</div>
        </div>
      ))}
      {result.top_vars.length > 0 && (
        <div style={{ marginTop: 8, fontSize: 12 }}>
          <span style={{ color: '#888' }}>⊤ vars: </span>
          {result.top_vars.map((t) => (
            <span key={t.var} className="v top" style={{ marginRight: 8 }}>
              {t.var}
              {t.provenance ? ` (${t.provenance})` : ' (출처 미태깅)'}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
