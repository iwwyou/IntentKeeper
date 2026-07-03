// ★ navigation은 전적으로 로컬 — 이미 받은 Result(cfg) 위 커서 이동.
//   step/back/into/out/continue 어느 것도 엔진을 호출하지 않음.
//   (이게 "quick" 정체성의 구조적 근거.)

import { useMemo, useState } from 'react'
import type { AnalysisResult, CFGNode } from '../types/result'

export interface NavState {
  cursor: string // 현재 노드 id
  node: CFGNode | undefined
  highlightedPreds: string[] // merge backward 시 비-⊥ predecessor들
  breakpoints: Set<number> // 라인 기준 breakpoint
  stepForward: () => void
  stepBackward: () => void
  stepInto: () => void
  stepOut: () => void
  continueRun: () => void
  nextBreakpoint: () => void
  prevBreakpoint: () => void
  jumpToNode: (id: string) => void
  jumpToLine: (line: number) => void
  toggleBreakpoint: (line: number) => void
}

export function useNavigation(result: AnalysisResult | undefined): NavState {
  const [cursor, setCursor] = useState<string>(result?.cfg.entry ?? '')
  const [highlightedPreds, setHighlightedPreds] = useState<string[]>([])
  const [breakpoints, setBreakpoints] = useState<Set<number>>(new Set())

  const nodeById = useMemo(() => {
    const m = new Map<string, CFGNode>()
    result?.cfg.nodes.forEach((n) => m.set(n.id, n))
    return m
  }, [result])

  const succ = (id: string) =>
    (result?.cfg.edges ?? []).filter((e) => e.from === id).map((e) => e.to)
  const pred = (id: string) =>
    (result?.cfg.edges ?? [])
      .filter((e) => e.to === id && e.kind !== 'back_edge') // back_edge는 fixpoint로 흡수, navigation에서 숨김
      .map((e) => e.from)

  const isBottom = (n: CFGNode | undefined) =>
    !n || Object.values(n.state).some((v) => v.includes('⊥'))

  const go = (id: string | undefined, preds: string[] = []) => {
    if (!id) return
    setCursor(id)
    setHighlightedPreds(preds)
  }

  const node = nodeById.get(cursor)

  return {
    cursor,
    node,
    highlightedPreds,
    breakpoints,

    stepForward: () => {
      const ss = succ(cursor)
      // 분기면 첫 successor로 (mock 단순화). 실제론 사용자 선택/true 우선.
      go(ss[0], [])
    },

    stepBackward: () => {
      const ps = pred(cursor)
      // ★ merge backward: 비-⊥ predecessor 전부 하이라이트, 커서는 첫째로.
      const live = ps.filter((p) => !isBottom(nodeById.get(p)))
      go(live[0] ?? ps[0], live.length > 1 ? live : [])
    },

    stepInto: () => {
      // mock: 외부/내부 호출 노드 구분 없음 → forward로 stub.
      // 실엔진: callee CFG로 하강. @IReturn(opaque)이면 "못 들어감" 표시.
      const ss = succ(cursor)
      go(ss[0], [])
    },

    stepOut: () => {
      // mock: caller로 복귀 stub → backward 1.
      const ps = pred(cursor)
      go(ps[0], [])
    },

    continueRun: () => {
      // 다음 (라인) breakpoint 또는 exit까지 forward 전진.
      let cur = cursor
      for (let i = 0; i < 1000; i++) {
        const ss = succ(cur)
        if (ss.length === 0) break
        cur = ss[0]
        const ln = nodeById.get(cur)?.src_line
        if (ln !== undefined && breakpoints.has(ln)) break
      }
      go(cur, [])
    },

    nextBreakpoint: () => {
      const cl = node?.src_line ?? 0
      const target = [...breakpoints].sort((a, b) => a - b).find((l) => l > cl)
      if (target !== undefined) {
        const n = result?.cfg.nodes.find((x) => x.src_line === target)
        if (n) go(n.id, [])
      }
    },

    prevBreakpoint: () => {
      const cl = node?.src_line ?? Number.MAX_SAFE_INTEGER
      const target = [...breakpoints].sort((a, b) => b - a).find((l) => l < cl)
      if (target !== undefined) {
        const n = result?.cfg.nodes.find((x) => x.src_line === target)
        if (n) go(n.id, [])
      }
    },

    jumpToNode: (id) => go(id, []),

    jumpToLine: (line) => {
      const n = result?.cfg.nodes.find((x) => x.src_line === line)
      if (n) go(n.id, [])
    },

    toggleBreakpoint: (line) => {
      setBreakpoints((prev) => {
        const next = new Set(prev)
        if (next.has(line)) next.delete(line)
        else next.add(line)
        return next
      })
    },
  }
}
