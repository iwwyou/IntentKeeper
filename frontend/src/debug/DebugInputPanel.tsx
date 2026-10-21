import { useStore, keyOf } from '../state/store'
import type { AnalysisResult, DebugKind, DebugSlot, RangeValue } from '../types/result'
import { emptyValue, slotToAnnotation } from './serialize'

// ★ 슬롯-주도: 분석이 슬롯(상태변수/파라미터/글로벌/IReturn)을 주고, 사용자는 값만 채움.
//   StateVar=상태변수 선언 시, Param=함수 파라미터, GlobalVar=static 화이트리스트,
//   IReturn=인터페이스 호출 statement 등장 시 자동 생성. (전부 함수-스코프)
export default function DebugInputPanel({ result }: { result: AnalysisResult }) {
  const activeContract = useStore((s) => s.activeContract)
  const activeFunction = useStore((s) => s.activeFunction)
  const debugInputs = useStore((s) => s.debugInputs)
  const setDebugValue = useStore((s) => s.setDebugValue)
  const applyDebug = useStore((s) => s.applyDebug)
  const analyzing = useStore((s) => s.analyzing)

  const valueErrors = useStore((s) => s.valueErrors)

  const apply = () => applyDebug(activeFunction)

  const fkey = keyOf(activeContract, activeFunction)
  const values = debugInputs[fkey] ?? {}

  const groups: DebugKind[] = ['StateVar', 'Param', 'GlobalVar', 'IReturn']
  const bySlot = (k: DebugKind) => result.debugSlots.filter((s) => s.kind === k)

  const valueOf = (slot: DebugSlot): RangeValue => values[slot.key] ?? emptyValue(slot)

  return (
    <div
      style={{ marginTop: 14 }}
      onKeyDown={(e) => {
        // 어느 입력 필드에서든 Enter → 전체 값 한 번에 적용(run).
        if (e.key === 'Enter') {
          e.preventDefault()
          apply()
        }
      }}
    >
      <div className="panel-title">Debug Input (슬롯 자동 · 값만 입력)</div>

      {valueErrors.length > 0 && (
        <div className="value-errors">
          {valueErrors.map((e, i) => (
            <div key={i} className="value-error">⚠ {e.message}</div>
          ))}
        </div>
      )}

      {groups.map((g) => {
        const slots = bySlot(g)
        if (slots.length === 0) return null
        const rows = slots.map((slot) => (
          <SlotRow
            key={slot.key}
            slot={slot}
            value={valueOf(slot)}
            onChange={(v) => setDebugValue(activeFunction, slot.key, v)}
          />
        ))
        // 전역(block/msg/tx)은 자주 안 건드리므로 접이식(기본 접힘) — State/Locals 전역 fold 와 일관.
        if (g === 'GlobalVar') {
          return (
            <details key={g} className="globals dbg-globals">
              <summary>@GlobalVar (block/msg/tx) · {slots.length}</summary>
              {rows}
            </details>
          )
        }
        return (
          <div key={g} className="dbg-group">
            <div className="dbg-group-title">@{g}</div>
            {rows}
          </div>
        )
      })}

      <button className="apply-btn" onClick={apply} disabled={analyzing}>
        {analyzing ? '적용 중…' : '▶ 적용 (Enter)'}
      </button>

      {analyzing && (
        <div className="analyzing-bar" role="status" aria-live="polite">
          <div className="analyzing-track">
            <div className="analyzing-fill" />
          </div>
          <span className="analyzing-label">백엔드 분석 중…</span>
        </div>
      )}

      <div style={{ fontSize: 11, color: '#666', marginTop: 6 }}>
        값 타입은 슬롯이 결정 (numeric→interval, bool→bool, address→symbolicAddress).
        interval 은 <b>한쪽을 비우면 무제약</b>(예: <code>[5, ]</code> = ≥5, <code>[ , 10]</code> = ≤10).
        <br />값 입력 후 <b>적용</b>을 눌러야 실행됩니다. breakpoint 있으면 그 지점까지, 없으면 함수 끝(EXIT)에서 정지.
      </div>
    </div>
  )
}

function SlotRow({
  slot,
  value,
  onChange,
}: {
  slot: DebugSlot
  value: RangeValue
  onChange: (v: RangeValue) => void
}) {
  const sugg = slot.suggestion
  return (
    <div>
      <div className="input-row">
        <span className="var" title={slot.label}>
          {slot.label}
        </span>
        <ValueInput slot={slot} value={value} onChange={onChange} />
        {slot.opaque && <span className="badge opaque">opaque</span>}
      </div>
      {sugg && (
        <div className="ghost">
          ⇠ {preview(sugg.value)} ({sugg.backend}, {Math.round(sugg.confidence * 100)}%)
          <span className="accept" onClick={() => onChange(sugg.value)}>
            [Tab 수락]
          </span>
        </div>
      )}
    </div>
  )
}

function ValueInput({
  slot,
  value,
  onChange,
}: {
  slot: DebugSlot
  value: RangeValue
  onChange: (v: RangeValue) => void
}) {
  if (slot.valueKind === 'interval') {
    const v = value.t === 'interval' ? value : { t: 'interval' as const, lo: '', hi: '' }
    return (
      <span className="interval-in">
        [
        <input
          className="num"
          value={v.lo}
          placeholder="lo"
          onChange={(e) => onChange({ t: 'interval', lo: e.target.value, hi: v.hi })}
        />
        ,
        <input
          className="num"
          value={v.hi}
          placeholder="hi"
          onChange={(e) => onChange({ t: 'interval', lo: v.lo, hi: e.target.value })}
        />
        ]
      </span>
    )
  }
  if (slot.valueKind === 'bool') {
    const v = value.t === 'bool' ? value.v : 'any'
    return (
      <select value={v} onChange={(e) => onChange({ t: 'bool', v: e.target.value as 'true' | 'false' | 'any' })}>
        <option value="true">true</option>
        <option value="false">false</option>
        <option value="any">any</option>
      </select>
    )
  }
  if (slot.valueKind === 'address') {
    const id = value.t === 'address' ? value.id : 0
    return (
      <span className="interval-in">
        symbolicAddress
        <input
          className="num"
          value={String(id)}
          onChange={(e) => onChange({ t: 'address', id: Number(e.target.value) || 0 })}
        />
      </span>
    )
  }
  // array/bytes/enum 은 advanced (후순위)
  return <span style={{ color: '#666', fontSize: 11 }}>({slot.valueKind} — advanced)</span>
}

function preview(v: RangeValue): string {
  return v.t === 'interval' ? `[${v.lo},${v.hi}]` : v.t === 'bool' ? v.v : v.t === 'address' ? `addr ${v.id}` : '-'
}

// (참고) 직렬화 확인용 — 실엔진 연결 시 사용
export { slotToAnnotation }
