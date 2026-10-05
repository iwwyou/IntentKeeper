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
  // ★ N4. **활성 프레임**의 CFG 를 본다 — callee 프레임에서 타겟 CFG 를 뒤지면 노드를
  //   못 찾아 pre-state/path 가 전부 비어버린다.
  const cfg = nav.activeCfg

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

  // ★ N2+N3. 보여줄 루프 fold 가 있나.
  //   - `nav.foldedLoopHead`: 직전 step forward 가 접고 넘어온 루프 (커서는 루프 **이후**)
  //   - 커서가 루프 헤더 자체: 다음 step 이 접을 루프 (`self`)
  //   두 경우 다 헤더 노드의 `loop_delta` 를 읽는다. 구조 단계(analyze)엔 delta 가 없다.
  const loopHeadNode =
    (nav.foldedLoopHead ? cfg.nodes.find((n) => n.id === nav.foldedLoopHead) : undefined) ??
    (node && flags.includes('condition') &&
      ['while', 'for', 'do_while'].includes(node.cond_type ?? '')
      ? node
      : undefined)
  const loopFold = loopHeadNode
    ? { node: loopHeadNode, delta: loopHeadNode.loop_delta, self: !nav.foldedLoopHead }
    : undefined

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
      {/* ★ N1. forward 분기도 backward 와 대칭으로 "동시에" 보여준다 — 경로를 고르게 하지 않는다. */}
      {nav.highlightedSuccs.length > 1 && (
        <div className="preds">
          branch forward: {nav.highlightedSuccs.join(', ')} 전부 feasible → 모두 하이라이트
          (abstract state 는 여러 경로를 동시에 표현한다)
        </div>
      )}

      {/* ★ N2+N3. 루프를 접고 넘어왔으면, 그 루프가 "한 일" = 수렴 후 바뀐 변수만 보여준다.
          iteration 을 밟게 하지 않는 대신 이 delta 가 루프의 효과를 대표한다(decision #4). */}
      {loopFold && (
        <div className="loop-fold">
          <div className="loop-fold-title">
            루프 L{loopFold.node.src_line} ({loopFold.node.cond_type}) 를 접었습니다
            {loopFold.self ? ' — 다음 step 은 루프 이후로' : ''}
          </div>
          {loopFold.delta === undefined ? (
            <div className="loop-fold-none">(아직 값이 없음 — Apply 후 표시)</div>
          ) : Object.keys(loopFold.delta).length === 0 ? (
            <div className="loop-fold-none">수렴 후 바뀐 변수 없음 (루프가 0회 또는 무효과)</div>
          ) : (
            <>
              <div className="loop-fold-sub">고정점 수렴 후 값이 바뀐 변수 (모든 iteration 성립)</div>
              {Object.entries(loopFold.delta).map(([k, v]) => (
                <div className="kv" key={k}>
                  <span>{k}</span>
                  <span className={valClass(v)}>{v}</span>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}
