import type { NavState } from './useNavigation'

// 전부 로컬 navigation — 엔진 호출 0.
export default function DebuggerControls({ nav }: { nav: NavState }) {
  return (
    <div>
      <div className="panel-title">Debugger</div>
      <div className="ctrl-row">
        <button onClick={nav.stepBackward} title="step backward (provenance)">⟲ back</button>
        <button onClick={nav.stepForward} title="step forward">⟳ fwd</button>
        <button onClick={nav.stepInto} title="step into">↘ into</button>
        <button onClick={nav.stepOut} title="step out">↗ out</button>
        <button onClick={nav.continueRun} title="continue to next breakpoint">▷ continue</button>
      </div>
      <div className="ctrl-row">
        <button onClick={nav.prevBreakpoint} title="previous breakpoint">|◀ prev bp</button>
        <button onClick={nav.nextBreakpoint} title="next breakpoint">next bp ▶|</button>
      </div>
      <div style={{ fontSize: 11, color: '#666' }}>
        gutter 클릭 = breakpoint · back은 시간되감기 아니라 provenance 추적
      </div>
    </div>
  )
}
