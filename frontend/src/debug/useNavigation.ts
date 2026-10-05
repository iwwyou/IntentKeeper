// ★ navigation은 전적으로 로컬 — 이미 받은 Result(cfg) 위 커서 이동.
//   step/back/into/out/continue 어느 것도 엔진을 호출하지 않음.
//   (이게 "quick" 정체성의 구조적 근거.)

import { useEffect, useMemo, useRef, useState } from 'react'
import { useStore } from '../state/store'
import type { AnalysisResult, CFG, CFGNode, NodeFlag } from '../types/result'

// ★ N4. 호출 스택 한 칸. `cfgKey === null` 이 타겟 함수 프레임이다.
//   callee 프레임은 `result.callees[cfgKey]` 의 CFG 위에서 움직인다.
//   부모 프레임의 `node` 는 **호출 지점에 그대로 남겨 둔다** → Step Out 은 pop 만 하면 된다.
export interface Frame {
  cfgKey: string | null
  node: string
  label: string                 // "Pool.withdraw" / "Math.mulDiv"
  contract?: string | null
  name?: string | null
  startLine?: number | null     // callee 소스 범위 (같은 파일이면 store.functions 로도 찾는다)
  endLine?: number | null
}

// 안전장치. 재귀 처리(감지·표시)는 **보류**이고(백로그 ⑨), 이건 "UI 가 끝없이 내려가지
// 않게" 하는 상한일 뿐이다. 루프 중첩과 달리 호출은 재귀면 무한히 깊어질 수 있다.
export const MAX_CALL_DEPTH = 16

// ★ breakpoint 를 걸 수 없는 "구조적" 노드 = 조인(merge)/루프탈출/do-while φ/함수exit.
//   이들은 forward-pred(=non-back-edge 선행)가 2개 이상(또는 종결)이라 "이 줄 실행 직전" 상태가
//   merge 대상이라 모호하다. 이 노드들만 타겟에서 빼면, 남는 착지 노드는 전부 forward-pred=1 보장
//   → 선행 out-state 가 곧 pre-state (StateLocals 참조). 엔진 in-state 노출 불필요(프론트-only).
const FORBIDDEN_TARGET_FLAGS: NodeFlag[] = ['merge', 'loop_exit', 'fixpoint_evaluation', 'exit']
export const isForbiddenTarget = (n: CFGNode | undefined): boolean =>
  !!n && n.flags.some((f) => FORBIDDEN_TARGET_FLAGS.includes(f))

// 해당 절대라인에 breakpoint 를 걸 수 있나: 그 라인에 착지 가능한(비-금지) 노드가 하나라도 있으면 OK.
//   (노드가 아예 없는 라인은 run-to-bp 에서 어차피 안 걸리므로 무해 → 허용)
export const canBreakpointOnLine = (cfg: CFG, absLine: number): boolean => {
  const on = cfg.nodes.filter((n) => n.src_line === absLine)
  return on.length === 0 || on.some((n) => !isForbiddenTarget(n))
}

// ★ N5. 그 라인이 **도달 불가**인가 — 그 라인의 모든 노드 env 가 ⊥ 를 포함.
//   엔진이 `_serialize_node_state` 에서 `"[None,None]" → "⊥"` 로 바꿔주므로 프론트에서 바로 읽힌다
//   (`engine_api.py`). breakpoint 를 **막지는 않는다** — 걸 수는 있게 두고 "여기는 도달 불가라
//   Continue 가 멈추지 않는다" 를 눈에 보이게 표시하는 게 목적이다(막아버리면 왜 안 되는지가 안 보인다).
//   노드가 없는 라인은 '도달 불가' 가 아니라 '분석 대상 아님' 이므로 false.
export const isLineUnreachable = (cfg: CFG, absLine: number): boolean => {
  const on = cfg.nodes.filter((n) => n.src_line === absLine)
  if (on.length === 0) return false
  return on.every((n) => Object.values(n.state).some((v) => v.includes('⊥')))
}

export interface NavState {
  cursor: string // 현재 노드 id
  node: CFGNode | undefined
  highlightedPreds: string[] // merge backward 시 비-⊥ predecessor들
  // ★ N1. branch forward 시 feasible successor들 — backward 와 **대칭**.
  //   커서는 첫째로 가고 나머지는 하이라이트한다. 사용자에게 경로를 **고르게 하지 않는다**:
  //   abstract state 는 여러 경로를 동시에 표현하므로, 하나를 고르게 하면 concrete debugger 의
  //   path 선택으로 되돌아간다. 화면도 "동시에" 보여주는 쪽이 일관적이다.
  highlightedSuccs: string[]
  // ★ N2. 직전 step forward 가 루프를 **접고** 넘어왔다면 그 루프 헤더 노드 id.
  //   UI 는 이걸로 헤더의 `loop_delta`(N3) 를 "루프가 한 것" 으로 보여준다.
  foldedLoopHead: string | undefined
  // ★ N4. 호출 스택. 마지막이 **현재 프레임**이고 `cursor`/`node` 는 그 프레임 기준이다.
  //   길이 1 = 타겟 함수. 이게 곧 UI 의 Call Stack 패널 내용이다.
  stack: Frame[]
  /** 현재 프레임의 CFG — succ/pred/state 가 모두 이것 위에서 움직인다. */
  activeCfg: CFG
  /** 현재 프레임의 breakpoint 라인. **프레임(=파일)별로 분리** — 라인 번호 충돌 방지. */
  breakpoints: Set<number>
  stepForward: () => void
  stepBackward: () => void
  stepInto: () => void
  stepOut: () => void
  continueRun: () => void
  nextBreakpoint: () => void
  prevBreakpoint: () => void
  /** Call Stack 패널에서 프레임을 눌러 그 깊이까지 되돌아가기 (0 = 타겟). */
  popToFrame: (index: number) => void
  jumpToNode: (id: string) => void
  jumpToLine: (line: number) => void
  toggleBreakpoint: (line: number) => void
}

const EMPTY_CFG: CFG = { entry: '', exit: '', nodes: [], edges: [] }

export function useNavigation(result: AnalysisResult | undefined): NavState {
  const rootLabel = result
    ? `${result.scope.contract}.${result.scope.function}`
    : '(target)'
  const rootFrame = (): Frame[] => [
    { cfgKey: null, node: result?.cfg.entry ?? '', label: rootLabel },
  ]
  const [stack, setStack] = useState<Frame[]>(rootFrame)
  const [highlightedPreds, setHighlightedPreds] = useState<string[]>([])
  const [highlightedSuccs, setHighlightedSuccs] = useState<string[]>([])
  const [foldedLoopHead, setFoldedLoopHead] = useState<string | undefined>(undefined)
  // ★ 프레임(cfgKey)별 breakpoint. 하나의 Set 으로 두면 callee 가 **다른 파일**일 때
  //   라인 번호가 겹쳐 엉뚱한 곳에서 멈춘다. 키 '' = 타겟 프레임.
  const [bpByFrame, setBpByFrame] = useState<Record<string, Set<number>>>({})

  const top = stack[stack.length - 1]
  const cursor = top?.node ?? ''
  const activeCfg: CFG =
    (top?.cfgKey ? result?.callees?.[top.cfgKey] : result?.cfg) ?? result?.cfg ?? EMPTY_CFG
  const breakpoints = bpByFrame[top?.cfgKey ?? ''] ?? new Set<number>()

  const nodeById = useMemo(() => {
    const m = new Map<string, CFGNode>()
    activeCfg.nodes.forEach((n) => m.set(n.id, n))
    return m
  }, [activeCfg])

  // ★ N2. forward 도 back_edge 를 거른다 — 예전엔 `succ` 만 필터가 없어서 forward 가
  //   back edge 를 타고 루프를 **다시 돌았다**. 값은 fixpoint 라 안 바뀌는데 커서가
  //   iteration 을 도는 것처럼 보여, decision #4 가 금지한 "iteration 별 stepping" 착각을
  //   그대로 만들어 냈다. `pred` 와 applyTick 의 `succOf` 는 이미 걸렀으므로 **한 파일 안
  //   불일치**이기도 했다.
  //   ⚠ 거르기만 하면 루프 꼬리(본문 마지막 문장)에 forward 후속이 **하나도 없어** 커서가
  //     갇힌다. 그래서 아래 `exitEnclosingLoop` / `foldLoop` 가 반드시 함께 간다.
  const succ = (id: string) =>
    activeCfg.edges.filter((e) => e.from === id && e.kind !== 'back_edge').map((e) => e.to)
  const pred = (id: string) =>
    activeCfg.edges
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
    if (id === activeCfg.error_exit) return true // _is_sink (error_exit 만)
    const n = nodeById.get(id)
    return !n || Object.values(n.state).some((v) => v.includes('⊥')) // _is_bottom_env
  }
  // forward: 살아있는(비-dead) 후속만. **전부 dead 면 undefined** — 예전엔 `live[0] ?? ss[0]`
  // 로 폴백해 "이후 모든 경로가 도달 불가" 인데도 그냥 이동했다(= "dead branch 는 navigation
  // 후보에서 제외된다" 가 엄밀히는 거짓이었다). N1 과 함께 정정.
  const forwardLive = (from: string): string[] => succ(from).filter((id) => !engineDead(id))
  const forwardPick = (from: string): string | undefined => forwardLive(from)[0]

  // ───────────────────────── N2. 루프 fold ─────────────────────────
  // 루프 구조는 **직렬화된 flags/edges 만으로** 복원한다(엔진 재질의 없음):
  //   join(fixpoint_evaluation) → head(condition, cond_type=while|for|do_while)
  //        head ─true→  body …                    (꼬리는 back_edge 로 join 으로 돌아감)
  //        head ─false→ loop_exit(닫는 `}`) → 루프 이후 첫 statement
  const flagged = (id: string | undefined, f: NodeFlag) => {
    const n = id ? nodeById.get(id) : undefined
    return !!n && n.flags.includes(f)
  }
  const isLoopBoundary = (id: string | undefined) =>
    flagged(id, 'fixpoint_evaluation') || isLoopHead(id)
  function isLoopHead(id: string | undefined): boolean {
    const n = id ? nodeById.get(id) : undefined
    return !!n && n.flags.includes('condition')
      && ['while', 'for', 'do_while'].includes(n.cond_type ?? '')
  }
  const falseSucc = (id: string): string | undefined =>
    activeCfg.edges.find((e) => e.from === id && e.kind === 'false')?.to

  /** 루프 경계(join 또는 head)에서 루프 전체를 접고 **루프 이후 첫 statement** 를 돌려준다.
   *
   * ★ 착지점을 닫는 `}`(= `loop_exit`)로 하지 않는 이유: 그 노드는
   *   `FORBIDDEN_TARGET_FLAGS` 에 있다(forward-pred 2개 이상 → pre-state 가 merge 대상이라
   *   "이 줄 실행 직전" 이 모호). 예외를 만들면 그 설계 전제를 다시 봐야 한다.
   * ★ 접힌 효과는 `head.loop_delta`(N3) 로 보여준다 — iteration 을 밟게 하지 않는다.
   */
  const foldLoop = (boundaryId: string): { landing?: string; head?: string } => {
    const head = flagged(boundaryId, 'fixpoint_evaluation')
      ? succ(boundaryId).find((id) => isLoopHead(id))
      : boundaryId
    if (!head) return {}
    const ex = falseSucc(head)
    if (!ex) return { head }
    // loop_exit 의 첫 live 후속 = 루프 이후 첫 statement. 없으면 loop_exit 자체(함수 끝).
    return { landing: forwardPick(ex) ?? ex, head }
  }

  /** 루프 **꼬리**(본문 마지막 문장: forward 후속 없음 + back_edge 있음)에서 루프를 빠져나간다.
   *  back_edge 가 가리키는 join 이 곧 그 루프의 경계이므로, 거기서 접으면 된다.
   *  중첩 루프의 내부 꼬리면 내부 루프의 join → 내부 루프 다음으로 나간다(바깥 루프에 남는다). */
  const exitEnclosingLoop = (id: string): { landing?: string; head?: string } => {
    const join = activeCfg.edges.find((e) => e.from === id && e.kind === 'back_edge')?.to
    return join ? foldLoop(join) : {}
  }

  const go = (
    id: string | undefined,
    preds: string[] = [],
    succs: string[] = [],
    folded?: string,
  ) => {
    if (!id) return
    // ★ N4. 이동은 **현재 프레임 안에서만** 일어난다. 부모 프레임의 node 는 호출 지점에
    //   그대로 남아 있어야 Step Out 이 pop 만으로 제자리로 돌아온다.
    setStack((prev) => {
      if (prev.length === 0) return prev
      const next = prev.slice()
      next[next.length - 1] = { ...next[next.length - 1], node: id }
      return next
    })
    setHighlightedPreds(preds)
    setHighlightedSuccs(succs)
    setFoldedLoopHead(folded)
  }

  /** run / next-bp 공용 전진. stepForward 와 달리 루프 본문을 **접지 않고 통과**한다 —
   *  본문 안 breakpoint 를 놓치면 안 되기 때문이다(concrete debugger 에서 Step Over 는
   *  호출을 건너뛰지만 Continue 는 그 안의 breakpoint 에 멈추는 것과 같은 관계).
   *  루프 상태는 fixpoint 하나라 호출자의 `visited` 가 본문을 **한 번만** 지나게 보장한다.
   *  꼬리(forward 후속 없음)에 닿으면 감싸는 루프를 빠져나간다. */
  const runAdvance = (from: string): string | undefined =>
    forwardPick(from) ?? exitEnclosingLoop(from).landing

  const node = nodeById.get(cursor)

  // ★ Apply(evaluate) 실행마다 커서를 "run" 결과 위치로 재배치 (decision #32):
  //   breakpoint 있으면 entry→첫 breakpoint 에서 정지, 없으면 EXIT(최종상태).
  //   → State&Locals 가 변수별 결과값을 즉시 표시. (applyTick 신호에만 반응)
  const applyTick = useStore((s) => s.applyTick)
  const resultRef = useRef(result)
  resultRef.current = result
  // applyTick 의 run-to-breakpoint 는 **타겟 프레임** 기준이다(리셋 후 프레임이 1개).
  const bpRef = useRef<Set<number>>(new Set())
  bpRef.current = bpByFrame[''] ?? new Set<number>()

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
    // ★ N4. Apply 하면 호출 스택도 **타겟 프레임 하나로 리셋**한다 — callee 스냅샷이
    //   새 debug 값으로 전부 갱신되므로 옛 프레임을 들고 있으면 안 된다.
    setStack([{ cfgKey: null, node: target, label: rootLabel }])
    setHighlightedPreds([])
    setHighlightedSuccs([])
    setFoldedLoopHead(undefined)
  }, [applyTick])

  // ★ N6. breakpoint 로의 이동을 **CFG 순회**로 수행한다.
  //   예전엔 next/prev bp 가 `[...breakpoints].sort()` 로 **소스 라인 번호**만 보고
  //   CFG 간선을 전혀 참조하지 않았다 — `if` 의 then 분기 breakpoint 가 else 분기 것보다
  //   라인이 앞이면 도달 순서와 무관하게 먼저 갔고, 도달 불가한 breakpoint 로도 점프했다.
  //   Continue 는 CFG traversal 인데 next/prev 만 달라 **의미론이 갈라져** 있었다.
  //   dir='fwd' 는 forwardPick, dir='back' 은 pred(back_edge 제외)를 따른다.
  const walkToBreakpoint = (dir: 'fwd' | 'back'): string | undefined => {
    let cur = cursor
    const visited = new Set<string>([cur])
    for (let i = 0; i < 1000; i++) {
      const nxt =
        dir === 'fwd'
          ? runAdvance(cur)
          : pred(cur).filter((p) => !isBottom(nodeById.get(p)))[0] ?? pred(cur)[0]
      if (nxt === undefined || visited.has(nxt)) return undefined
      visited.add(nxt)
      cur = nxt
      const n = nodeById.get(cur)
      const ln = n?.src_line
      // 구조적 노드(merge/loop_exit/φ/exit)에는 멈추지 않는다 — pre-state 가 merge 대상이라 모호.
      if (ln !== undefined && breakpoints.has(ln) && !isForbiddenTarget(n)) return cur
    }
    return undefined
  }

  return {
    cursor,
    node,
    highlightedPreds,
    highlightedSuccs,
    foldedLoopHead,
    stack,
    activeCfg,
    breakpoints,

    stepForward: () => {
      // ★ N2. 커서가 루프 헤더에 있으면 본문으로 들어가지 않고 그 루프를 **접는다**.
      if (isLoopHead(cursor)) {
        const { landing, head } = foldLoop(cursor)
        if (landing) go(landing, [], [], head)
        return
      }
      // ★ N1. feasible successor 전부 하이라이트, 커서는 첫째로 (backward 와 대칭).
      //   전부 dead 면 **이동하지 않는다** — "이후 모든 경로가 도달 불가".
      const live = forwardLive(cursor)
      // ★ N2. 루프 꼬리(본문 마지막 문장) = forward 후속 없음 → 감싸는 루프를 빠져나간다.
      //   back_edge 를 거르는 대가로 생기는 "커서 갇힘" 을 여기서 해소한다.
      if (live.length === 0) {
        const { landing, head } = exitEnclosingLoop(cursor)
        if (landing) go(landing, [], [], head)
        return
      }
      // ★ N2. 루프 경계(join)로 들어가려는 중 → 루프 전체를 접고 루프 이후로 착지.
      if (live.length === 1 && isLoopBoundary(live[0])) {
        const { landing, head } = foldLoop(live[0])
        if (landing) {
          go(landing, [], [], head)
          return
        }
      }
      go(live[0], [], live.length > 1 ? live : [])
    },

    stepBackward: () => {
      const ps = pred(cursor)
      // ★ merge backward: 비-⊥ predecessor 전부 하이라이트, 커서는 첫째로.
      const live = ps.filter((p) => !isBottom(nodeById.get(p)))
      go(live[0] ?? ps[0], live.length > 1 ? live : [], [])
    },

    // ★ N4. callee CFG 로 **하강**(push). 커서는 그대로 두고 프레임만 쌓는다.
    //   opaque 뿐이거나 호출이 없으면 **이동하지 않는다** — 사유는 UI 가 `node.callees` 의
    //   `reason` 으로 띄운다(엔진이 "왜 못 들어가는지" 를 문장으로 실어 보낸다).
    //   여러 개 들어갈 수 있으면 첫째로 내려가고 나머지는 UI 가 목록으로 보여준다
    //   (N1 과 같은 원칙 — 사용자에게 **고르게 하지 않는다**).
    stepInto: () => {
      const refs = (node?.callees ?? []).filter(
        (r) => r.enterable && r.key && result?.callees?.[r.key],
      )
      if (refs.length === 0) return
      if (stack.length >= MAX_CALL_DEPTH) return   // 안전 상한 (재귀 처리는 보류)
      const r = refs[0]
      const cfg = result!.callees![r.key]
      // callee 착지점 = entry 의 첫 forward 후속 (타겟 프레임 시작과 같은 규칙)
      const start =
        cfg.edges.filter((e) => e.from === cfg.entry && e.kind !== 'back_edge').map((e) => e.to)[0] ??
        cfg.entry
      setStack((prev) => [
        ...prev,
        {
          cfgKey: r.key,
          node: start,
          label: r.label,
          contract: r.contract,
          name: r.name,
          startLine: r.start_line,
          endLine: r.end_line,
        },
      ])
      setHighlightedPreds([])
      setHighlightedSuccs([])
      setFoldedLoopHead(undefined)
    },

    // ★ N4. caller 로 **복귀**(pop). 부모 프레임의 node 가 호출 지점에 남아 있으므로
    //   pop 만으로 제자리다. 타겟 프레임이면 나갈 곳이 없어 이동하지 않는다.
    stepOut: () => {
      if (stack.length <= 1) return
      setStack((prev) => prev.slice(0, -1))
      setHighlightedPreds([])
      setHighlightedSuccs([])
      setFoldedLoopHead(undefined)
    },

    continueRun: () => {
      // 다음 (라인) breakpoint 또는 exit까지 forward 전진 (죽은 분기 skip).
      let cur = cursor
      const visited = new Set<string>([cur])
      for (let i = 0; i < 1000; i++) {
        const nxt = runAdvance(cur)
        if (nxt === undefined || visited.has(nxt)) break
        visited.add(nxt)
        cur = nxt
        const n = nodeById.get(cur)
        const ln = n?.src_line
        // ★ N7. 구조적 노드(merge/loop_exit/φ/exit)에는 멈추지 않는다.
        //   applyTick 의 run-to-breakpoint 경로는 이미 검사하는데 여기만 빠져 있어
        //   **같은 파일 안에서 불일치**였다. 그 노드들은 pre-state 가 merge 대상이라
        //   State&Locals 표시가 모호해진다.
        if (ln !== undefined && breakpoints.has(ln) && !isForbiddenTarget(n)) break
      }
      go(cur, [], [])
    },

    // ★ N6. Continue 와 달리 **breakpoint 가 없으면 이동하지 않는다**(exit 로 가지 않는다).
    //   Continue = "다음 breakpoint 또는 끝까지", next/prev bp = "breakpoint 사이 이동".
    nextBreakpoint: () => go(walkToBreakpoint('fwd'), [], []),
    prevBreakpoint: () => go(walkToBreakpoint('back'), [], []),

    popToFrame: (index) => {
      if (index < 0 || index >= stack.length - 1) return
      setStack((prev) => prev.slice(0, index + 1))
      setHighlightedPreds([])
      setHighlightedSuccs([])
      setFoldedLoopHead(undefined)
    },

    jumpToNode: (id) => go(id, [], []),

    jumpToLine: (line) => {
      const n = activeCfg.nodes.find((x) => x.src_line === line)
      if (n) go(n.id, [], [])
    },

    // ★ N4. breakpoint 는 **프레임(cfgKey)별**이다 — callee 가 다른 파일이면 라인 번호가
    //   겹쳐 엉뚱한 곳에서 멈춘다. 키 '' = 타겟 프레임.
    toggleBreakpoint: (line) => {
      const k = top?.cfgKey ?? ''
      setBpByFrame((prev) => {
        const cur = new Set(prev[k] ?? [])
        if (cur.has(line)) cur.delete(line)
        else cur.add(line)
        return { ...prev, [k]: cur }
      })
    },
  }
}
