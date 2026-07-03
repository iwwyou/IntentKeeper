import { useEffect, useRef } from 'react'
import Editor from '@monaco-editor/react'
import type { editor } from 'monaco-editor'
import { registerSolidity } from '../editor/solidity'
import { useStore, keyOf } from '../state/store'
import type { AnalysisResult } from '../types/result'
import type { NavState } from './useNavigation'

interface Props {
  source: string
  nav: NavState
  result: AnalysisResult
}

// 커서 노드 라인 하이라이트 + merge backward 시 양쪽 pred 라인 하이라이트
// + violated region + breakpoint glyph. 전부 Result 위 로컬 표시(엔진 호출 없음).
export default function CodePane({ source, nav, result }: Props) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null)
  const monacoRef = useRef<any>(null)
  const decoRef = useRef<string[]>([])

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

    const decos: editor.IModelDeltaDecoration[] = []
    if (cursorLine) {
      decos.push({
        range: new monaco.Range(cursorLine, 1, cursorLine, 1),
        options: { isWholeLine: true, className: 'cursor-line', glyphMarginClassName: 'cursor-glyph' },
      })
    }
    predLines.forEach((l) =>
      decos.push({
        range: new monaco.Range(l, 1, l, 1),
        options: { isWholeLine: true, className: 'pred-line' },
      })
    )
    violatedLines.forEach((l) =>
      decos.push({
        range: new monaco.Range(l, 1, l, 1),
        options: { isWholeLine: true, className: 'violated-line' },
      })
    )
    nav.breakpoints.forEach((l) =>
      decos.push({
        range: new monaco.Range(l, 1, l, 1),
        options: { glyphMarginClassName: 'bp-glyph' },
      })
    )
    intentLines.forEach((l) =>
      decos.push({
        range: new monaco.Range(l, 1, l, 1),
        options: { glyphMarginClassName: 'intent-glyph', glyphMarginHoverMessage: { value: '@During' } },
      })
    )
    decoRef.current = ed.deltaDecorations(decoRef.current, decos)
  }, [cursorLine, predLines.join(','), violatedLines.join(','), nav.breakpoints, intentLines.join(','), result])

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
        // glyph margin 클릭 → breakpoint 토글
        ed.onMouseDown((e) => {
          if (e.target.type === monaco.editor.MouseTargetType.GUTTER_GLYPH_MARGIN) {
            const ln = e.target.position?.lineNumber
            if (ln) nav.toggleBreakpoint(ln)
          }
        })
      }}
      options={{
        readOnly: true,
        glyphMargin: true,
        minimap: { enabled: false },
        fontSize: 13,
        lineNumbers: 'on',
      }}
    />
  )
}
