import { useEffect, useRef } from 'react'
import Editor from '@monaco-editor/react'
import type { editor } from 'monaco-editor'
import { registerSolidity } from '../editor/solidity'
import { useStore, keyOf } from '../state/store'
import type { AnalysisResult } from '../types/result'
import type { NavState } from './useNavigation'
import { canBreakpointOnLine } from './useNavigation'

interface Props {
  source: string // 함수-로컬 소스 (에디터 내부 라인 1 = 함수 첫 줄)
  nav: NavState
  result: AnalysisResult
  startLine?: number // 함수의 컨트랙트-절대 시작 라인 → gutter/좌표 오프셋
}

// 함수만 표시하되 라인넘버는 컨트랙트-절대(#2). 엔진 src_line/verdict/intent 는 모두 절대라서
// 에디터 내부 로컬라인(1..N)과 offset=(startLine-1) 로 변환한다:
//   내부 = 절대 - offset,  gutter 표시 = 내부 + offset = 절대.
export default function CodePane({ source, nav, result, startLine }: Props) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null)
  const monacoRef = useRef<any>(null)
  const decoRef = useRef<string[]>([])

  const offset = (startLine ?? 1) - 1
  const toLocal = (abs: number) => abs - offset

  // onMount 콜백은 1회만 실행 → 클로저가 초기 result/offset/nav 를 캡처(함수 전환 시 stale).
  // ref 로 항상 최신값을 참조해 breakpoint 판정/토글이 어긋나지 않게 한다.
  const resultRef = useRef(result)
  resultRef.current = result
  const offsetRef = useRef(offset)
  offsetRef.current = offset
  const navRef = useRef(nav)
  navRef.current = nav

  const activeContract = useStore((s) => s.activeContract)
  const activeFunction = useStore((s) => s.activeFunction)
  const intents = useStore((s) => s.intents)
  const intentLines = (intents[keyOf(activeContract, activeFunction)] ?? [])
    .map((it) => it.line)
    .filter((l): l is number => l !== undefined)

  const cursorLine = nav.node?.src_line
  const predLines = nav.highlightedPreds
    .map((id) => result.cfg.nodes.find((n) => n.id === id)?.src_line)
    .filter((l): l is number => l !== undefined)
  const violatedLines = result.verdict
    .filter((v) => v.status === 'Violated')
    .flatMap((v) => [v.region[0], v.region[1]])

  useEffect(() => {
    const ed = editorRef.current
    const monaco = monacoRef.current
    if (!ed || !monaco) return
    const lineCount = ed.getModel()?.getLineCount() ?? 0

    const decos: editor.IModelDeltaDecoration[] = []
    // 절대라인 → 내부라인 변환 + 함수 범위(1..lineCount) 밖은 스킵.
    const push = (abs: number, options: editor.IModelDecorationOptions) => {
      const l = toLocal(abs)
      if (l < 1 || l > lineCount) return
      decos.push({ range: new monaco.Range(l, 1, l, 1), options })
    }

    if (cursorLine && cursorLine >= 0) {
      push(cursorLine, { isWholeLine: true, className: 'cursor-line', glyphMarginClassName: 'cursor-glyph' })
    }
    predLines.forEach((l) => push(l, { isWholeLine: true, className: 'pred-line' }))
    violatedLines.forEach((l) => push(l, { isWholeLine: true, className: 'violated-line' }))
    nav.breakpoints.forEach((l) => push(l, { glyphMarginClassName: 'bp-glyph' }))
    intentLines.forEach((l) =>
      push(l, { glyphMarginClassName: 'intent-glyph', glyphMarginHoverMessage: { value: '@During' } })
    )
    decoRef.current = ed.deltaDecorations(decoRef.current, decos)
  }, [cursorLine, predLines.join(','), violatedLines.join(','), nav.breakpoints, intentLines.join(','), result, offset])

  return (
    <Editor
      height="100%"
      language="solidity"
      theme="iqdebug-dark"
      beforeMount={registerSolidity}
      value={source}
      onMount={(ed, monaco) => {
        editorRef.current = ed
        monacoRef.current = monaco
        // glyph margin 클릭 → breakpoint 토글 (내부라인 → 절대라인으로 저장)
        //   단, 구조적 라인(}=merge/loop_exit/φ/exit)에는 걸 수 없음 → 무시(pre-state 모호 회피).
        ed.onMouseDown((e) => {
          if (e.target.type === monaco.editor.MouseTargetType.GUTTER_GLYPH_MARGIN) {
            const ln = e.target.position?.lineNumber
            if (!ln) return
            const abs = ln + offsetRef.current
            if (canBreakpointOnLine(resultRef.current, abs)) navRef.current.toggleBreakpoint(abs)
          }
        })
      }}
      options={{
        readOnly: true,
        glyphMargin: true,
        minimap: { enabled: false },
        fontSize: 13,
        // gutter 는 컨트랙트-절대 라인 표시 (내부 n + offset)
        lineNumbers: (n: number) => String(n + offset),
      }}
    />
  )
}
