// ★ navigation은 전적으로 로컬 — 이미 받은 Result(cfg) 위 커서 이동.
//   step/back/into/out/continue 어느 것도 엔진을 호출하지 않음.
//   (이게 "quick" 정체성의 구조적 근거.)

import { useEffect, useMemo, useRef, useState } from 'react'
import { useStore } from '../state/store'
import type { AnalysisResult, CFGNode, NodeFlag } from '../types/result'

// ★ breakpoint 를 걸 수 없는 "구조적" 노드 = 조인(merge)/루프탈출/do-while φ/함수exit.
//   이들은 forward-pred(=non-back-edge 선행)가 2개 이상(또는 종결)이라 "이 줄 실행 직전" 상태가
//   merge 대상이라 모호하다. 이 노드들만 타겟에서 빼면, 남는 착지 노드는 전부 forward-pred=1 보장
//   → 선행 out-state 가 곧 pre-state (StateLocals 참조). 엔진 in-state 노출 불필요(프론트-only).
const FORBIDDEN_TARGET_FLAGS: NodeFlag[] = ['merge', 'loop_exit', 'fixpoint_evaluation', 'exit']
export const isForbiddenTarget = (n: CFGNode | undefined): boolean =>
  !!n && n.flags.some((f) => FORBIDDEN_TARGET_FLAGS.includes(f))

// 해당 절대라인에 breakpoint 를 걸 수 있나: 그 라인에 착지 가능한(비-금지) 노드가 하나라도 있으면 OK.
//   (노드가 아예 없는 라인은 run-to-bp 에서 어차피 안 걸리므로 무해 → 허용)
export const canBreakpointOnLine = (result: AnalysisResult, absLine: number): boolean => {
  const on = result.cfg.nodes.filter((n) => n.src_line === absLine)
  return on.length === 0 || on.some((n) => !isForbiddenTarget(n))
}

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

  // ★ 엔진 _run_worklist 의 분기 선택과 1:1 이식. 후속이 "죽었나"를 엔진과 동일 기준으로 판정:
  //   - error_exit(=require/assert 실패 sink): 엔진 _is_sink 가 전파 skip → state 빈 {} 로 남음.
  //     프론트는 빈-state 휴리스틱 대신 id 로 직접 식별(cfg.error_exit). (return_exit 은 제외 — 정상 도달)
  //   - ⊥ 포함(infeasible if/else 분기): 엔진 _is_bottom_env("하나라도 BOTTOM") 와 동일.
  const engineDead = (id: string | undefined): boolean => {
    if (!id) return true
    if (id === result?.cfg.error_exit) return true // _is_sink (error_exit 만)
    const n = nodeById.get(id)
    return !n || Object.values(n.state).some((v) => v.includes('⊥')) // _is_bottom_env
  }
  // forward: 살아있는(비-dead) 후속 우선. 전부 dead 면 원래 첫째로 폴백(구조 보존).
  const forwardPick = (from: string): string | undefined => {
    const ss = succ(from)
    const live = ss.filter((id) => !engineDead(id))
    return live[0] ?? ss[0]
  }

  const go = (id: string | undefined, preds: string[] = []) => {
    if (!id) return
    setCursor(id)
    setHighlightedPreds(preds)
  }

  const node = nodeById.get(cursor)

  // ★ Apply(evaluate) 실행마다 커서를 "run" 결과 위치로 재배치 (decision #32):
  //   breakpoint 있으면 entry→첫 breakpoint 에서 정지, 없으면 EXIT(최종상태).
  //   → State&Locals 가 변수별 결과값을 즉시 표시. (applyTick 신호에만 반응)
  const applyTick = useStore((s) => s.applyTick)
  const resultRef = useRef(result)
  resultRef.current = result
  const bpRef = useRef(breakpoints)
  bpRef.current = breakpoints

  useEffect(() => {
    if (applyTick === 0) return // 초기 로드(evaluate 전) 에는 이동 안 함
    const r = resultRef.current
    if (!r) return
    const nmap = new Map(r.cfg.nodes.map((n) => [n.id, n]))
    const succOf = (id: string) =>
      r.cfg.edges.filter((e) => e.from === id && e.kind !== 'back_edge').map((e) => e.to)
    // stepForward 의 engineDead 와 동일 기준(error_exit sink + ⊥). 여기선 effect 로컬(ref) 이라 재정의.
    const dead = (id: string) => {
      if (id === r.cfg.error_exit) return true
      const n = nmap.get(id)
      return !n || Object.values(n.state).some((v) => v.includes('⊥'))
    }
    const bps = bpRef.current

    let target = r.cfg.exit
    if (bps.size > 0) {
      const visited = new Set<string>()
      let c: string | undefined = r.cfg.entry
      for (let i = 0; i < 10000 && c && !visited.has(c); i++) {
        visited.add(c)
        const ss = succOf(c)
        if (ss.length === 0) break
        // 도달 가능한(비-dead) successor 우선 → 죽은 분기(error_exit·⊥)로 새지 않음
        c = ss.find((id) => !dead(id)) ?? ss[0]
        const cn = nmap.get(c)
        const ln = cn?.src_line
        // 구조적 노드(merge/loop_exit/φ/exit)에는 안 멈춤 — 설정단에서 막지만 방어적으로 재확인.
        if (ln !== undefined && ln >= 0 && bps.has(ln) && !isForbiddenTarget(cn)) {
          target = c
          break
        }
      }
      // breakpoint 미도달 → EXIT 로 (target 은 이미 exit)
    }
    setCursor(target)
    setHighlightedPreds([])
  }, [applyTick])

  return {
    cursor,
    node,
    highlightedPreds,
    breakpoints,

    stepForward: () => {
      // 엔진과 동일하게 죽은 분기(error_exit·⊥) 건너뛰고 살아있는 후속으로.
      go(forwardPick(cursor), [])
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
      go(forwardPick(cursor), [])
    },

    stepOut: () => {
      // mock: caller로 복귀 stub → backward 1.
      const ps = pred(cursor)
      go(ps[0], [])
    },

    continueRun: () => {
      // 다음 (라인) breakpoint 또는 exit까지 forward 전진 (죽은 분기 skip).
      let cur = cursor
      for (let i = 0; i < 1000; i++) {
        const nxt = forwardPick(cur)
        if (nxt === undefined || nxt === cur) break
        cur = nxt
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
