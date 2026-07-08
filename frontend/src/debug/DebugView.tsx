import { useStore, keyOf } from '../state/store'
import { useNavigation } from './useNavigation'
import CodePane from './CodePane'
import DebuggerControls from './DebuggerControls'
import StateLocals from './StateLocals'
import VerdictPanel from './VerdictPanel'
import DebugInputPanel from './DebugInputPanel'
import IntentPanel from './IntentPanel'

export default function DebugView() {
  const activeContract = useStore((s) => s.activeContract)
  const activeFunction = useStore((s) => s.activeFunction)
  const results = useStore((s) => s.results)
  const functions = useStore((s) => s.functions)

  const analyzeError = useStore((s) => s.analyzeError)
  const result = results[keyOf(activeContract, activeFunction)]
  const fnMeta = functions.find((f) => f.name === activeFunction)
  const nav = useNavigation(result)

  if (!result) {
    return (
      <div className="debug" style={{ display: 'block', padding: 24, color: '#888' }}>
        분석 결과 없음 — {activeContract}.{activeFunction} (mock에 미등록이거나 분석중)
      </div>
    )
  }

  return (
    <div className="debug">
      {/* 상단 가로 툴바 = 디버거 컨트롤 */}
      <div className="dtoolbar">
        <DebuggerControls nav={nav} />
      </div>

      {analyzeError && (
        <div className="analyze-error" title={analyzeError}>
          ⚠ 분석 실패: {analyzeError}
        </div>
      )}

      {/* 좌측 = 코드 (함수만 표시 · 라인넘버는 컨트랙트-절대) */}
      <div className="dpanel code">
        <CodePane source={fnMeta?.source ?? ''} startLine={fnMeta?.startLine} nav={nav} result={result} />
      </div>

      {/* 우측 사이드바 = 세로 3분할 */}
      <div className="dright">
        <div className="dpanel intent-sec">
          <div className="dsec-title">Intent &amp; Verdict</div>
          <VerdictPanel result={result} nav={nav} />
          <IntentPanel />
        </div>
        <div className="dpanel">
          <div className="dsec-title">Debug Input</div>
          <DebugInputPanel result={result} />
        </div>
        <div className="dpanel">
          <div className="dsec-title">State &amp; Locals</div>
          <StateLocals nav={nav} result={result} />
        </div>
      </div>
    </div>
  )
}
