# IQDebug — 진행상황 (handoff)

> 최종 수정 기준 스냅샷. compact 후 이 문서로 바로 이어가기 위함.
> 관련 문서: `temp/solqdebug-extension-direction.md`(채택 방향·§8 task), `temp/direction-analysis.md`(미채택 방향),
> memory: `project-direction`, `engine-sync-and-run`.

---

## 0. 한 줄 요약

**잠정 제목 (2026-06-22 선정, 교수님 확정 전):**
> **Towards Safer Solidity Development: An Intent-Aware Quick Debugging Assistant**
>
> 선정 근거: ①`Towards Safer` = interval/intent 기반의 *상대적·점진적* 보장과 정합 — 절대 안전(program verification) 주장
> 회피로 과대주장 리스크 0. (보장은 선언된 debugging annotation·입력 가정 *안에서만* sound; 그 바깥/모델링 갭은
> 미보장.) ②`Intent-Aware` = 의도-구현 정합 검사라는 핵심 차별점 전면. ③`Quick Debugging Assistant` = SolQDebug
> 계보 edit-time 디버거 성격 명시(verifier 아님을 솔직히 신호). 대안 검토: `Efficient`(무관/가스 허위 위험)·
> `Secure`/`Reliable`(절대형이라 상대적 보장과 충돌) 회피, `Intent-Conformant`(정밀하나 "intent" 중복)·형용사 제거(밋밋)
> 차선. 평가의 "탐지율 개선"이 `Towards Safer`를 직접 뒷받침 → 제목이 바뀌어도 근거는 재활용 가능.

**IQDebug** = SolQDebug(게재) + IntentChecker(심사중) 엔진을 확장한 **intent-aware quick debugger** (박사학위 3번째 컴포넌트).
- 엔진 = interval abstract interpretation, multi-contract single-tx, intent(@During/@Post) 검증. (IntentKeeper에 동기화 완료, 20/20 VIOLATED 검증.)
- 추가 = 인터랙티브 디버거 UI(step/breakpoint/back navigation) + LLM/solver debug-value 제안 + precompute(후순위).
- 현재 단계: **증분 편집 아키텍처(B1 + T-stmt) 동작** (2026-06-22). `EngineSession.update(new_source)` =
  SyntaxValid 게이트 → record-space diff → 변경분만 적용(delete=`delete_cfg_range` SESE 수술, 조건 modify=
  in-place, simple modify=delete+add). `engine_server /analyze` 가 첫 호출 fresh·이후 증분. **프론트 무변경**.
  end-to-end analyze→update→evaluate→verify 가 fresh 빌드와 등가(temp 테스트 61개 통과). 코어 변경:
  `DynamicCFGBuilder`(delete/modify 메서드 추가), `ContractAnalyzer`(process_if/while/for modify 분기),
  `Engine.py`(freeze 게이트 + warning-combine), `engine_api`(update/closeBefore). 상세·잔여 = §5.6.
- 툴명 = IQDebug, repo/project = IntentKeeper 유지.

---

## 1. 확정된 설계 결정 (decisions log)

1. **UI = 두 화면 분리** (옵션 2): Workspace(편집+deps 등록) ↔ Debug view(함수 focused). 상단 탭 전환.
2. **분석은 백엔드 live(edit-time), 표시만 화면 전환**: 분석 트리거 = 코드편집/디버그입력/intent/deps 변경. 화면전환·step navigation은 트리거 아님(표시일 뿐).
3. **navigation은 전적으로 로컬**: 분석 1패스가 함수 전체 program-point 추상상태를 다 계산 → CFG-with-states 통째 전송 → step/back/into/out은 그 위 커서 이동(엔진 호출 0). = "quick" 정체성의 구조적 근거.
4. **step 의미 재정의** (concrete 디버거 아님, path-insensitive AI):
   - backward = 시간되감기 아니라 **provenance 추적**.
   - merge node backward = 비-⊥ predecessor **전부 하이라이트**(⊥ 분기는 dead로 표시). SC는 분기 적어 follow-all 기본.
   - loop = iteration별 step 없음. step forward 진입 시 **fixpoint로 접어 표시**, backward가 loop exit면 **fixpoint evaluation node** 조회. 본문값 = 루프 불변식 라벨.
   - step into: 외부/cross-contract(@IReturn)는 "opaque, 못 들어감" 표시 = derivable/opaque 경계 노출.
   - continue = 다음 (라인) breakpoint 또는 함수끝까지 전진. prev/next breakpoint 버튼 있음.
5. **Stack&Memory / Tx Details 제외** (바이트코드 아님). Tx 대신 @GlobalVar 구간 선언.
6. **debug 입력 = 분석-주도 슬롯, 값만 입력** (함수-스코프):
   - @StateVar(상태변수 선언 시), @LocalVar(함수 파라미터/로컬), @GlobalVar(static 화이트리스트), @IReturn(인터페이스 호출 statement 등장 시).
   - 사용자는 targetExpr/funcName/accessChain을 타이핑 안 함 → 엔진이 슬롯 제공. **값만** 입력.
   - 값 타입 = 슬롯의 valueKind 결정: interval / bool / address(symbolicAddress). array/bytes/enum은 advanced.
7. **intent = 코드 밖 패널 메타데이터 + lineRef** (코드 삽입/밀림 없음):
   - @During = 라인-스코프(코드 라인 옆) → 라인-클릭 부착 UX(미구현, (a)).
   - @Post = 함수-스코프(entry/exit).
8. **annotation "삽입 없는 적용"**: 코드는 순수 Solidity. 어노테이션은 캐논 텍스트로 직렬화 → engine_api가 *그 텍스트만 파싱*해 lineRef/함수 노드에 등록, `update_code` 삽입 단계 생략 → 라인 밀림 원천 제거.
9. **LLM vs solver 결정 보류**: suggestion은 backend-agnostic(`backend: llm|solver|hybrid`). 무엇이 나은지는 L2 실험이 결정(derivable→? opaque→? 경험적 매핑이 originality).
10. **프론트 = 로컬 웹앱**(Vite+React+TS+Monaco), VSCode 아님(DAP 임피던스·커스텀 패널 자유도·엔진 editor-event 정합). localStorage 영속.
11. **코어 수정은 승인 후에만**. 지금까지 엔진 코드 미수정(읽기만). 기존 출력 경로 보존(run_all.py 20/20 = 회귀 가드).

### 1.1 추가 확정 (2026-06-19 세션)

12. **두 레이어로 분리**:
    - **결정론 코어**(abstract interpreter, edit-time, 빠름) = `analyze`/`evaluate`/`verify`.
    - **생성 보조**(solver/LLM, async, 느림, L2 originality) = `suggest_value`/`reach`/`cover`/`suggest_intent`.
    - 보조는 코어의 *자식*이 아니라 위에 얹힌 *형제* — 코어 출력(CFG/states/path condition) + 추가입력(주석/패턴) 소비.
13. **debug는 analyze의 하위 함수가 아님** — 같은 분석을 *값으로 파라미터화한 재호출*. navigation은 엔진 0콜(프론트 로컬). 슬롯(debugSlots)은 analyze 산출물(구조적, 값 이전).
14. **3계층 = 캐시 무효화 계층(dirty 신호 = 액션 종류)**:
    - `analyze(records)` → CFG 구조 + 빈 슬롯. [코드 편집]
    - `evaluate(debug값)` → fixpoint → CFG-with-states. [값 변경] (CFG 재사용)
    - `verify(intents)` → verdict. [intent 변경] (CFG·states 재사용). **states 종속** = 없으면 lazy evaluate.
    - 체인 종속: analyze → evaluate → verify.
15. **인터랙티브 = 3콜, 실험/격리 = 1콜(`analyze_once`)**. 3콜이 dirty 신호를 공짜로 운반(1콜은 dirty 재인코딩이라 캐시 이득 상실).
16. **두 루트**: Root A 타겟 분석 세션(`EngineSession`) / Root B 의존성(`DependencyStore`). deps는 분석의 *선행 리소스*(세션 생성 전 빌드돼야 @IReturn 해소) → peer 아님, 별 루트.
17. **suggest 분해**(입력이 다름 → 표면 분리, generator 공유): `suggest_value`(opaque 슬롯) / `reach`(특정 path 도달 입력, witness) / `cover`(전 분기, 후순위) / `suggest_intent`(주석·취약점패턴 → intent 제안, 입력=원문+주석). derivable→solver / opaque→LLM 매핑이 L2.
18. **intent_anchors 출력 drop** — @During 부착 가능 라인 = `{CFGNode.src_line}`으로 프론트가 유도.
19. **입력 모델 = delta fragment**(full-slice 아님): Monaco onChange→`(startLine,endLine,code,event)` 어댑터. `slice_solidity` record 형식과 동일 경로(update_code 증분) = SolQDebug "quick" 강점 유지. paste=multi-line record.
20. **syntax gate = ANTLR(`Solidity.g4`)로 누적 전체 코드 파스** → 실패 시 `Diagnostic` 반환. **solc 게이트 보류**(런타임 무겁고 의미검사는 분석 선결조건 아님, 과거 compile-first 실패 이력). 필요 시 별도 deep-validate 액션으로 분리.
21. **출력층 `send_report_to_front`(print만, ContractAnalyzer.py:2934) 교체 허용** → `engine_api.to_analysis_result`가 구조화 Result로 대체.
    - **(2026-06-20 정정)** `send_report_to_front`는 **CFG/risk/region을 만들지 않음** — `recorder.ledger`(라인별 텍스트 record)를 콘솔에 print할 뿐. CFG/states = `FunctionCFG.graph`, verdict = Engine 해석 중 `combined_result`. → "교체"가 아니라 **신규 뷰 직렬화기** 필요. (risk/region 출처는 §2.1 참조.)

### 1.2 추가 확정 (2026-06-20 세션) — 최적화 아키텍처

22. **intent ↔ debug 게이트 = 소프트 + auto-fill**: intent는 항상 허용. debug 슬롯이 비면 `reach`/`suggest_value`로 값을 **auto-fill 제안**(witness 생성과 연결). 막지 않고 채움. **auto-fill = 값 변경 이벤트** → 일반 `evaluate`(P1)→`verify`(P2) 캐스케이드를 탐(= intent 제스처가 값 변경으로 번질 수 있음). debug 없는 의미상 하드 의존은 아님(전부 ⊤면 대부분 warning이라 무의미할 뿐).
23. **분석 3-페이즈 분해**: **P0 structure**(code→CFG 골격) / **P1 fixpoint**(code+debug값→per-node states: `variables`/`before_envs`/`return_vals`) / **P2 judge**(states+intents→verdict, **P1 출력의 순수함수**). 현재 엔진은 **P2가 P1에 용접**(해석 walk 중 인라인 검증, `Engine.py:1396+`) → 분리가 목표. 근거: `guardian_verifier.verify_*`는 이미 `cfg_node.before_envs`/`variables`만 읽음 → 루프 밖 사후 호출 가능.
24. **독립성 = 절차(snapshot/restore) → 구조(deepcopy-into-working)**: `baseline_fcfg`(코드만 의존, pristine)의 **복사본에 P1 해석** → restore 불필요(매 run이 자기 복사본 = 구조적 격리), **계산결과 보존**. 그 복사본이 곧 캐시·투영 대상. `FunctionCFG`/`ContractCFG`는 pkl 왕복 검증됨(deps가 .pkl) → deepcopy/pickle 택일은 측정으로.
25. **states 버전 캐시 = 진짜 3-tier 재사용**: `states_cache[values_ver]`. 값변경→해당 버전만 P1, 나머지 히트. **intent변경→P1 스킵, P2만**. (code,값) 반복→무계산. 라우터: 값 버전 동일→P2만 / 바뀜(auto-fill 포함)→P1→P2 / **변수 첫사용 인덱스 early-out**(바뀐 변수의 첫 사용이 모든 intent보다 뒤면 재계산 스킵, 건전).
26. **최적화 도달 = Stage 1 → 등가확인 → Stage 2** (목표는 순수 P0/P1/P2 분리):
    - **Stage 1**: deepcopy-into-working + 버전 캐시 + **standalone P2**(guardian를 보존 states에 사후 호출) + 뷰 직렬화기 + first-use 인덱스. 인라인 verify는 **지우지 않고 정답 오라클로 유지**. → 이 시점에 이미 verify-only(쌈) 경로 동작.
    - **등가 확인**: standalone P2 == 인라인 verify.
    - **Stage 2**: 같음 확인 후 인라인 verify 제거(핫패스 청소). = 새 기능 아님, 중복 제거.
    - **증분 fixpoint 보류**: 단일 함수 CFG엔 이득 작고 loop widening/narrowing 건전성 위험·공수 큼. 프로파일링서 P1 병목으로 측정되면 재검토.
27. **(14) 정정 — verify는 "싼 재조회"가 아니다(현행)**: 현재 엔진에서 intent는 노드에 attach되고 **해석 패스 중** 검증됨(`Engine.py:1396+`) → verdict·states가 같은 패스에서 생성되고 **restore로 함께 소거**(`DebugBatchManager.flush:48`). "states 재사용 + 판정만"의 싼 verify는 **Stage 2(P2 분리) 후에야** 성립. 그전엔 intent 변경도 재해석 동반.
28. **증분 편집 = B1(record-space diff) + T-stmt(논문 surgical delete/modify) + ANTLR SyntaxValid** (2026-06-22). 프론트는 풀소스 전송, 서버가 prev/new 레코드 diff 로 변경분만 영속 세션에 `update_code`. raw-Monaco-델타(B2)·T2 폐기. **검증: 엔진 delete/modify 가 논문 Alg.대로 미구현**(add-only 만 실전 검증) → 구현 대상. `closeBefore` 누락 버그는 B1 apply 경로(diff 스트림이 `update_code` 에 close_before 전달)에 흡수. 상세·6단계 계획·Alg↔API 매핑 = **§5.6**.

---

## 2. 엔진 확인 결과 (코드 근거, file:line)

### 2.1 program-point 상태 / CFG / loop
- per-node 상태: `CFGNode.variables`, `before_envs` (`Utils/CFG.py:47-48`). 라인↔노드: `SolidityAnalyzer.line_info[ln]["cfg_nodes"]`.
- 직렬화(interval→str): `Analyzer/RecordManager.py:292-325` (`"[lo,hi]"`, `"address(⊤)"` 등).
- **loop fixpoint 조회 핸들 = YES**: `CFGNode.fixpoint_evaluation_node`(플래그), `fixpoint_evaluation_node_vars`(`Utils/CFG.py:15,33`), `loop_exit_node`, `cond_type`. fixpoint 계산 `Interpreter/Engine.py:409`.
- **⊤ provenance 태깅 = NO**: `Domain/Interval.py`에 ⊤ 도입 출처 추적 없음. 필요시 소작업으로 추가(후순위).
- verdict: `during_annotations`/`post_annotations`(`ContractAnalyzer.py:68-69`), 검증 `Analyzer/GuardianVerificationEngine.py`, 결과 `RecordManager.ledger`.
- **(2026-06-20 확정) risk/region 출처**: 실제 검증은 `process_during`(fallback) 아니라 **해석 중** `Interpreter/Engine.py:1396+`에서 `combined_result` 생성. 매핑:
  - `VerdictItem.risk` ← `combined_result["risk_score"]` (0-10 float, `Engine.py:1418`).
  - `status` ← `"violated"/"satisfied"/"warning"` → `Violated/Satisfied/Warning` 매핑 필요.
  - `region [n,n]` = **소스 라인 스팬** `[report_line, report_line]` (값-interval 아님). `false_regions`(lower/upper violation 값구간)는 별개 도메인 → 프론트 현재 미모델(추후 확장 후보).
  - **transient**: `combined_result`는 `analysis_per_line[report_line]`에 기록되나 states와 같은 해석 패스 산물 → restore로 소거. Stage 1에서 states와 함께 freeze.

### 2.2 annotation 바인딩 (삽입 없는 적용 근거)
- 라인 밀림: `SolidityAnalyzer.update_code`(`SolidityAnalyzer.py:40-106`) → `_insert_lines`(108-170) → `ContractAnalyzer._shift_cfg_meta`(92-118).
- **구조화 등록 메서드 이미 존재**(텍스트 아님): `process_during(clauses, logic_ops)`(`ContractAnalyzer.py:1748`), `process_post`(1866). 등록 키 = `current_start_line`, 노드 부착 `_cfg_node_at(line_no)`(1734)/`_find_prev_cfg_node`. @Post는 exit_node.
- **삽입 없이 등록 패턴 이미 있음**: `_is_during_inline`(`SolidityAnalyzer.py:219`)이 inline @During이면 `_insert_lines` 스킵.
- → 결론: `update_code`를 어노테이션에 호출 안 하고 텍스트만 파싱+visit하면 밀림 없음. 침습도 낮음~중간.

### 2.3 debug annotation 문법/시그니처 (`Parser/Solidity.g4`)
- `debugInput`(g4 268-294), `debugValue`(329-338).
- @StateVar/@LocalVar: `varRef '=' debugValue`. varRef는 복합경로(`config.fee[user]`, `token.decimals`) 지원.
- @GlobalVar: simple(`block.X`/`msg.X`/`tx.X` 화이트리스트) | addressBalance(`address(this).balance`).
- @IReturn: A(`cVar.f()`) | B(`IIface(addr).f()`) + accessChain(member/index/call). func은 view/pure만.
- debugValue: `[lo,hi]` | `symbolicAddress N` | `true/false/any` | `array[...]` | `arrayAddress[...]` | `symbolicBytes/String hex` | enum.
- 등록: `process_state_var_for_debug(lhs_expr, value)`(`ContractAnalyzer.py:2756`), `process_local_var_for_debug`(2782), `process_global_var_for_debug`(2710), `process_ireturn(contract_var, func_name, access_chain, value)`(2830), `process_ireturn_cast`(2876). lhs resolve = `Interpreter/Semantics/DebugInitializer.py`. snapshot/restore = `DebugBatchManager.flush`(`Analyzer/DebugUnitAnalyzer.py:33-48`) + snapman.

### 2.4 dependency pkl 빌더 (이미 존재)
- `Dependencies/main.py`: `slice_solidity(source)`(.sol→records), `analyze_file(sol, mode)`(→ `ifc_/lib_/con_*.pkl` 저장, `{cfg, file_level_structs, type_aliases}`). 부모 해석 `_load_parent_pkls`. **순서 하드코딩**(`_con_order`) → 임의 첨부엔 자동 topo-sort 필요(미구현).
- 로드: `main.py:load_dependencies()` (pkl 읽기 + 3개 .sol 디렉토리 interface 이름 스캔).

---

## 3. 프론트 구조 (`frontend/`)

스택: Vite + React + TS + `@monaco-editor/react`. 실행: `cd frontend && npm run dev` (포트 5173, 점유 시 5174).

```
src/
  main.tsx, App.tsx            App: view(workspace|debug) 전환 + 상단바
  types/result.ts             ★ engine_api 출력 계약(CFG/verdict/top_vars/intents/debugSlots)
  state/store.ts              ★ zustand+persist(localStorage v2). 공유상태+트리거.
                              runAnalysis(func,tier): 액션=dirty신호 → 코드편집=structure / 값=evaluate / intent=verify.
                              tier별로 results[key] 패치 후 조립. verify는 항상 마지막 1회.
  engine/analyzeClient.ts     ★ 실엔진 seam. 3콜+analyzeOnce → engine_server(FastAPI) fetch.
                              BASE=VITE_ENGINE_URL|127.0.0.1:8000. (mock 제거 완료.)
  editor/solidity.ts          Monaco Solidity 문법(Monarch)+테마 'iqdebug-dark'
  mock/
    workspace.json            컨트랙트 소스 + 함수목록 + deps
    result.withdraw.json      Vault.withdraw mock Result (CFG+verdict+slots+intents)
  workspace/
    WorkspacePanel.tsx        좌:FileExplorer+Deps / 중:Monaco / 우:FunctionList
    FileExplorer.tsx          .sol 파일 new/open(File API)/select/delete
    DepsSidebar.tsx           .sol 첨부(File API)→building→ready(pkl 빌드는 엔진 연결 시)
    FunctionList.tsx          함수별 verdict 마커(●/⚠/○) + [Debug ▷]
  debug/
    DebugView.tsx             focused 함수 디버그 레이아웃
    CodePane.tsx              Monaco(read-only) + 커서/pred/violated/bp/intent 데코
    DebuggerControls.tsx      back/fwd/into/out/continue + prev/next bp
    StateLocals.tsx           커서 노드 추상상태 + path + merge pred 표기
    VerdictPanel.tsx          S/W/V + risk + region 클릭→점프 + ⊤vars
    DebugInputPanel.tsx       ★ 슬롯-주도(그룹별) + 값만 입력(interval/bool/address)
    IntentPanel.tsx           intent 편집(@During+line / @Post) store기반
    serialize.ts              슬롯+값→g4 캐논 텍스트 (engine_api용)
    useNavigation.ts          ★ CFG 위 로컬 navigation(step/back/into/out/continue/bp)
```

### 동작 vs mock
- **동작**: 두 화면 전환, 다중 파일(new/open/delete, localStorage 영속), deps 첨부(stub), Solidity 하이라이트, 함수 verdict 마커, **navigation 로컬(엔진 0)**, merge backward 양쪽 하이라이트, verdict→점프, breakpoint(gutter 토글/continue/prev/next), slot-주도 debug 입력(값만), ghost 제안 Tab수락, intent 편집+라인 마커.
- **mock/stub**: 분석 자체(Result 고정, `analyzeClient`가 seam), deps pkl 빌드, ghost 제안 내용, LLM chat 없음, step-into=forward stub, advanced value types(array/bytes/enum) 스텁.

---

## 4. 다음 할 일

### 완료 (2026-06-19)
- ✅ `engine_api.py` 계약 스켈레톤(타입·시그니처·docstring, 내부 `NotImplementedError`).
- ✅ 프론트 seam 3콜 배선: `analyzeClient.ts`(3콜+analyzeOnce) + `store.ts`(tier 라우팅) + `engine_api`에 `Diagnostic`/`analyze_once`.

### 즉시 후보
- **(T2) Monaco delta 어댑터**: `onChange` → `(startLine,endLine,code,event)` records (decision 19). 현재 `updateActiveContent`는 전체 content를 넘김 → delta로 교체.
- **(T1) 결정론 경로 실배선 = Stage 1**(§1.2 decision 24-26): `EngineSession.analyze/evaluate/verify`.
  - **(1) deepcopy-into-working + 후크**: `DebugBatchManager.flush` restore 직전에 해석된 `fcfg`를 복사/freeze해 `states_cache[values_ver]`에 보존. 기존 snapshot/restore는 폴백 병행. 코어 변경은 flush 경로로 한정(작은 diff).
  - **(2) 뷰 직렬화기**(코어 밖, engine_api): CFGNode role 플래그→`flags`, `variables`/`before_envs`→`state`(interval→`"[lo,hi]"`, RecordManager:292-325 재사용), edge `condition`→`true/false`, join pred→`join_from`. verdict 매핑(§2.1).
  - **(3) standalone P2**: `guardian_verifier`를 보존된 states에 사후 호출 → verify-only 경로. 인라인 verify는 오라클로 유지(등가 확인용).
  - **(4) debugSlots 도출**(파라미터/상태변수/글로벌/`ireturn_registry`(opaque)) + **변수 첫사용 인덱스**(early-out용) + ANTLR 게이트→`Diagnostic`.
  - **이후 Stage 2**: standalone P2 == 인라인 등가 확인 후 인라인 verify 제거.
- **(a) @During 라인-클릭 부착**(intent 전용): 디버그뷰 라인 클릭→커서 라인 기본값+override. (현재 라인넘버 수동입력.)

### T1 끝나야 풀리는 것
- ⊤ provenance 태깅(why-⊤ 라벨), `to_analysis_result` 출력층(send_report_to_front 대체).
- websocket 배선: `analyzeClient` seam → 실제 `engine_api` 호출(현재 mock).
- Root B 의존성 빌드(slice→analyze_file→pkl) + 자동 topo-sort(임의 .sol 첨부 순서).
- 라인 anchor(워크스페이스 편집 시 @During lineRef 따라 이동 — Monaco sticky). 현재 디버그뷰 read-only라 안정적.

### 생성 보조 (L2 originality, 후순위)
- `suggest_value`/`reach`/`cover`/`suggest_intent` 구현 + solver/LLM backend seam. derivable→solver / opaque→LLM 매핑 실험.

### 폴리시/후순위
- Solidity 함수목록 동적 파싱(현재 mock 고정), advanced value types UI, precompute&inject(P1), intent-repair.

---

## 5. `engine_api.py` (스켈레톤 작성 완료 — 내부 `NotImplementedError`)

**파일 = 프로젝트 root `engine_api.py`**. 계약(타입·시그니처)만 확정, 본문 미구현. 각 스텁 docstring에 실배선 hook이 `file:line`으로 박혀 있음.

### 5.1 Root A — `EngineSession` (결정론 코어)
- `__init__(deps)` / `close()` — SolidityAnalyzer 1개 + deps 1회 로드(load_dependencies를 인스턴스 받는 형태로 신규). DebugBatchManager로 snapshot/restore.
- `analyze(records) → Structure` — delta 누적 적용 → CFG 구조 + 빈 debugSlots + `diagnostics`. nodes.state={}. [코드 편집]
- `evaluate(debug_values) → CfgWithStates` — fixpoint → states. **restore 전 스냅샷 직렬화**(불변 사본). top_vars(provenance=None). [값 변경]
- `verify(intents) → list[VerdictItem]` — states 읽어 판정. states 없으면 lazy evaluate. [intent 변경]
- `to_analysis_result(structure, states, verdict, intents) → AnalysisResultDict` — 3산출 합성(= 프론트 `AnalysisResult`). **`send_report_to_front` 대체 출력층**.
- `analyze_once(records, debug_values, intents, deps)` — 세션 없이 1회(L2 실험). 내부서 세션 만들어 analyze→evaluate→verify→to_analysis_result.

### 5.2 생성 보조 (모듈 함수, solver/LLM, 표면 분리·generator 공유)
- `suggest_value(session, slot) → Suggestion` — opaque 슬롯 채우기.
- `reach(session, target) → dict[SlotKey, RangeValue]` — 특정 path/intent 도달 입력 합성(witness).
- `cover(session, scope) → list[dict]` — 전 분기 커버(reach 반복, 후순위).
- `suggest_intent(source, comments, patterns) → list[IntentItem]` — 주석·취약점패턴 → intent 제안.

### 5.3 Root B — `DependencyStore`
- `build(name, source) → DepInfo` (slice_solidity → analyze_file → ifc_/lib_/con_*.pkl) / `list()` / `remove(name)`. 자동 topo-sort 미구현.

### 5.4 값 모델 (frontend/src/types/result.ts와 1:1)
`Record`(code/startLine/endLine/event), `CFGNode/Edge/CFG`, `VerdictItem`, `TopVar`, `Suggestion`, `DebugSlot`, `IntentItem`, `RangeValue`(interval/bool/address/none), `Diagnostic`, 단계 산출 `Structure`/`CfgWithStates`, `Scope`, `DepSpec`/`DepInfo`.

### 5.5 실배선 = Stage 1 (★ 구현·스모크 검증 완료, 2026-06-20)

**구현 완료(`engine_api.py` + 코어 3곳, `temp/smoke_engine_api.py` 로 검증):**
- `EngineSession.analyze(records)` — slice_solidity record → `update_code`+visit 누적 → CFG 구조 직렬화 + `LocalVar` 슬롯 도출. ✅ (flags/cond_type/edge true·false/entry·exit·return·error 정확, state={}).
- `EngineSession.evaluate(debug_values)` — 값→캐논 어노테이션(삽입 없이 컨텍스트 수동설정)→`batch.flush`→**freeze**→states 직렬화. ✅ (seed 전파·dead branch ⊥ 확인: `a=[0,5]`→`b=[1,6]`, `a>10` 분기 `[None,None]`=⊥).
- `EngineSession.verify(intents)` — intent 를 노드에 attach(`_attach_intents`, 삽입 없이)→`_interpret` 재해석→inline 검증이 `analysis_per_line` 에 기록→`_extract_verdict`→`VerdictItem`. ✅ (Satisfied/Violated/Warning·risk·복합 `&&`/`||` 검증. **inline verify = Stage 1**, standalone P2 는 Stage 2). `evaluate`/`verify` 는 공통 `_interpret` 공유(현재 둘 다 재해석).
- 뷰 직렬화기 `_serialize_cfg`/`_serialize_node_state`(RecordManager._flatten_var 재사용)/`_node_flags`/`_collect_top_vars`/`_derive_debug_slots`/`_extract_verdict`/`_cfg_to_dict`.
- `to_analysis_result` + `analyze_once` ✅ — 3산출 합성 → 프론트 `AnalysisResult`(키 6개, edge `from_`→`from`). (= send_report_to_front 대체 출력층.)
- **deps 선별 로딩** `_load_dependencies_into`/`_find_dep_pkl` ✅ — DepSpec 이름으로 objectfile pkl 매칭 로드(전부 로드 시 버전 충돌 회피). fail-loud(pkl 없으면 raise). topo-sort 미구현.
- **Stage 2 standalone P2** `_verify_standalone` ✅ — 보존 states(frozen)에 `_process_node_intents`/`_process_post_annotations` 사후 호출 → **재해석 없이** verdict. intent 는 live fcfg 에 파싱 attach 후 node 이름으로 frozen 미러링. **inline 과 등가 검증 5/5 OK**(결정 26 오라클). verify 는 캐시 있으면 standalone, 없으면 inline 재해석 fallback. → **엔진의 inline verify 는 제거하지 않음**(배치 경로 보존) — 우리 경로만 standalone 사용 = Stage 2 효과 달성.

**검증 중 발견·수정한 코어 버그 2건:**
- **`_combine_logic_results`(Engine.py:1987~) — `warning` 누락**: `&&`/`||` 조합이 `warning` 을 분기에 안 넣어 `warning && satisfied`→`satisfied`(증발), `warning || …`→`violated`(둔갑). 단일 절은 정상, 복합만 오류. → warning 우선순위 추가(`&&`: violated>warning>…, `||`: satisfied>warning>…). IntentChecker 는 `&&`/`||` 미사용이라 RQ1 무영향(사용자 확인).
- **status 어휘 혼용**: 단일 절(`_verify_during_clause_dynamic`)=`success`/`violation`, 복합(`_combine_logic_results`)=`satisfied`/`violated`. `engine_api._VSTATUS` 가 둘 다 정규화(우리 레이어, 코어 무수정).

**★ 핵심 정정 — states-wipe 의 진짜 위치 = `Interpreter/Engine.py:769`:**
- `interpret_function_cfg_for_debug` 가 worklist 로 `blk.variables` 에 seed된 states 계산(verification·ledger 기록은 여기서) → **함수 끝에서 `_saved_node_vars` 로 baseline 복원**(`Engine.py:769-770`). `DebugBatchManager.flush` 의 restore 는 그보다 바깥.
- 따라서 freeze 는 **`Engine.py:769` 복원 직전**이어야 함(거기서만 계산된 states 가 산다). flush 시점 freeze 는 이미 baseline → 폐기.
- **코어 변경 = `Interpreter/Engine.py` 한 곳뿐**(게이트 `an._capture_debug_fcfg`, 기본 미설정 → 게재 경로 무영향): 복원 직전 `an._frozen_debug_fcfg = pickle.loads(pickle.dumps(fcfg))`. pickle 실패는 그대로 전파(fail-loud).
- `EngineSession` 은 `_capture_debug_fcfg=True` 설정, flush 후 `ca._frozen_debug_fcfg` 직렬화. (한때 둔 `DebugUnitAnalyzer.freeze_enabled`/`ContractAnalyzer._last_debug_fcfg` 는 죽은 코드라 되돌림.)

**fallback 정책 = 전부 제거, fail-loud (2026-06-20):** evaluate freeze None→`raise`, 직렬화·드라이버 에러는 try/except 없이 전파. 조용한 baseline/`str()` 대체 없음. (유저 코드 syntax 검증은 추후 ANTLR 게이트로 *의도된* diagnostics 산출 — 버그 숨기는 catch-all 과 구분.)

**프론트 배선 (2026-06-20, HTTP 서버):**
- `engine_server.py` ✅ — FastAPI(+uvicorn, 포트 8000, CORS). 세션 키 "contract.func" 영속으로 3콜 묶음: `/analyze`(fresh 세션 재빌드+캐시 리셋) / `/evaluate`(재사용→states) / `/verify`(보존 states standalone P2) / `/analyze_once` / `/health`. full source→`slice_solidity`→records. 실행 `.venv\Scripts\python.exe engine_server.py`.
- `frontend/src/engine/analyzeClient.ts` ✅ — mock 제거, 실 서버 `fetch`로 교체(`BASE`=`VITE_ENGINE_URL`|`127.0.0.1:8000`). 함수 시그니처/인터페이스 동일 → `store.ts` 무변경. `npx tsc --noEmit` 통과.
- 검증: 단순 컨트랙트(`C.f`) 3콜 end-to-end OK(analyze slots/nodes, evaluate `b=[1,6]`, verify Satisfied). `temp/test_http.py`.

**★ 알려진 버그:**
- ✅ **(해결 2026-06-22) `closeBefore` 미전달 → if/else 분석 실패**: `EngineSession._apply_code_record` 가 `update_code(s,e,code,ev)` 4-인자만 호출. `slice_solidity` 는 `} else {`/`} while`/`} catch` 에 `closeBefore=True` 를 붙이는데(main.py `simulate_inputs` 는 `update_code(s,e,code,ev,close_before)` 전달) 이게 누락 → `Vault.withdraw`(if/else) analyze 시 `DynamicCFGBuilder.build_else_statement`: "else: target join not found" 500. **수정**: `_apply_code_record` 가 record 의 `closeBefore` 를 받아 `update_code` 에 전달. (Record TypedDict 에 `closeBefore: bool` 추가.)
- ✅ **(해결 2026-06-22) StateVar/GlobalVar 슬롯 미도출**: `_derive_debug_slots` 가 LocalVar(파라미터)·
  IReturn 만 도출했음 → **StateVar**(`ccf.state_variable_node.variables`; 스칼라=interval, 매핑·구조체·배열
  =opaque) + **GlobalVar**(`ccf.globals` 중 *함수 소스에 실제 등장한 것만* — 화이트리스트 15개 전부면 노이즈)
  추가. `structure()` 가 ccf·소스텍스트 전달. 검증: Vault.withdraw → amount(Local)/balances(State,opaque)/
  total(State)/msg.sender(Global) 정확 표시.
- **@IReturn 슬롯**: 여전히 `ireturn_registry`(값 적용 후 채워짐)만 봄 → 인터페이스 *호출 지점* 구조적 도출 잔여.
- **프론트 레이아웃 개편(2026-06-22)**: intent 가 4-컬럼 맨 끝(`max-height:110px`)이라 안 보이던 문제 →
  **상단 가로 툴바(컨트롤) + 코드 좌(크게) + 우측 세로 3분할: Intent+Verdict(상단)/Debug Input(중)/State&Locals
  (하단)**. `DebugView.tsx`·`styles.css`(`.dtoolbar`/`.dright`). tsc 통과.

**잔여(우선순위 순):**
1. **`closeBefore` 수정** → `Vault.withdraw`(if/else) 등 실컨트랙트 통과. 그 후 브라우저에서 실동작 확인(`engine_server` + `npm run dev`).
2. **@IReturn 슬롯 도출**(인터페이스 호출 지점) + deps 선별로딩 연결(프론트 첨부 deps → 서버 DepSpec).
3. `[None,None]`→`⊥` 표기, verdict message 정리(`<Expression object>` repr 노이즈), node 이름 verdict 부착.
4. before_envs(라인 단위 nav), ANTLR diagnostics(누적 코드 파스), deps topo-sort.
5. 생성 보조(L2): `suggest_value`/`reach`/`cover`/`suggest_intent` + solver/LLM seam. `DependencyStore.build`(slice→pkl).
6. 동시성: 서버 세션 잠금(현재 단일 사용자 전제), delta 어댑터(T2, Monaco onChange→record).
- **뷰 직렬화기**(engine_api): CFGNode 플래그→`flags`, `variables`/`before_envs`→`state`(interval→`"[lo,hi]"`, RecordManager:292-325 부품 재사용), edge `condition`(`graph.edges[u,v]`)→`true/false`, `get_true/false_block`. `serialize_graph_structure`(CFG.py:211)·`CFGSerializer._json_safe` 부품화하되 before_envs·interval-str·flag 매핑은 신규.
- **verdict**: `Engine.py:1418` `combined_result["risk_score"]`/status/message → `VerdictItem` (§2.1 매핑).
- **debugSlots**: `FunctionCFG.parameters`/state vars/globals/`ireturn_registry`(opaque) 스캔. **변수 첫사용 인덱스**(early-out)도 P1 walk서 수집.
- **ANTLR 게이트**: 누적 전체 코드 파스 → error listener → `Diagnostic`.

**침습 범위 (2026-06-20 갱신, 코어 수정 승인됨)**:
- **수정 대상**: `DebugBatchManager.flush`(freeze 후크, Stage 1), `Interpreter/Engine.py`(인라인 verify 제거 = Stage 2), 출력층.
- **불변 유지**: `Domain/`, `Utils/CFG.py`(구조), `GuardianVerificationEngine.py`(P2 로직 그대로 사후 호출), 파서·visitor, fixpoint 핵심 로직(`Engine.py`는 P2 분리만, P1 계산 불변).
- 회귀 가드: `run_all.py` 20/20 VIOLATED 매 단계 확인.

### 5.6 증분 편집 아키텍처 (B1 + T-stmt, 2026-06-22 결정)

**배경 / 모순**: 현 `engine_server`는 매 호출 풀소스를 받아 fresh 세션으로 `slice_solidity` 전체를 add 재적용
(= 매번 통째 재구성). SolQDebug 의 핵심 주장인 *edit-time 증분 분석*을 살리지 못함.

**결정 (B1, record-space diff)**: 에디터는 풀소스를 보내고(와이어 단순), **서버가 prev/new 레코드를 diff**해
변경분만 영속 세션의 `update_code` 로 적용. Monaco 라인 좌표가 아니라 **slice-정규화된 레코드 시퀀스에서 diff**
하므로 좌표매핑·closeBefore·`}`스트립 재구현 불필요(slice 가 단일 진실원). chunk paste = "삽입 레코드 묶음"으로
검증된 add 경로를 그대로 탐 → 큰 코드일수록 B1 이 더 안전(문맥-정합 정규화). 필요시 Monaco 변경범위 힌트로
diff 를 O(변경) 한정(선택).
- 반려: **B2**(프론트가 raw Monaco 델타 전송). 물리라인↔정규화공간 불일치 + slice 의 TS 포팅(영구 동기화 부채)
  + auto-brace 로 생기는 단독 `}`(slice 가 버리는 줄) 처리 → 큰 청크에서 가장 위험. published 계약(=slice 레코드)
  에서도 더 멀어짐.

**검증 결과 (2026-06-22)**: **논문 Code Deletion/Modification 알고리즘이 엔진에 미구현**.
`update_code` delete 분기(`SolidityAnalyzer.py:83-98`)는 소스라인/`line_info`/`ledger` pop + `_shift_cfg_meta`
(src_line·ledger 시프트만) 뿐 — 논문의 `RemoveNodes`/`AddEdge(pred→succ)` 재연결/`succ` 재해석 **없음**.
다른 "delete"는 무관: `ContractAnalyzer.py:2736`=디버그값 롤백, `handle_delete`(1595)=Solidity `delete` 연산자,
`DynamicCFGBuilder` `remove_node`(55/309/386)=빌드 중 stub 정리. **미발각 이유**: slice 가 전부 `add` 라
main.py·engine_server 어디서도 delete/modify 를 호출 안 함 → add-only 만 실전 검증됨.

**T-stmt 채택** (statement 단위 surgical delete/modify 를 논문 Alg.대로 구현). 대안 T-func(바뀐 함수만 drop+add
재구성)는 더 안전하나 사용자가 논문 충실도/효율 위해 T-stmt 선택.

**Alg. → 엔진 API 매핑**:
- `M`(line→node) = `sa.line_info[ln]["cfg_nodes"]` + `CFGNode.src_line` + `recorder.ledger[ln]`
- `RemoveNodes`/`RemoveEdge`/`AddEdge` = `nx.DiGraph` 원시연산(`G.remove_node` 엣지자동제거 등)
- `IncrementalInterpretation(G,{succ})` = **기존** `engine.reinterpret_from(fcfg, seeds)`(Engine.py:1013)
- `ShiftIndex` = **기존** `_shift_cfg_meta`
- `SyntaxValid(C')` = **ANTLR 로 살림**(결정). delete 전 누적 `C'` 파스 검증, 실패 시 reject.
- 새로 짤 핵심 = **FindBoundary + 노드집합 제거 + pred→succ 재연결**.

**어려운 지점 (논문 Alg.은 이상화)**: 단순 statement 삭제는 그대로 OK. **블록 삭제**(if/else)는 cond+양분기+
**join** 서브그래프 수집, succ=join 의 successor. **루프 삭제**는 cond+body+back-edge+`loop_exit_node`. 중첩은
재귀 수집. SyntaxValid 가 1단계인 이유 = 문법유효 삭제라야 `M[Ls..Le]`가 제거대상과 정확히 일치.

**구현 순서 (위험 분리, 각 단계 독립 테스트)**:
1. ✅ **record-space diff 레이어** (`incremental.py`, **코어 무관·순수 Python**, 2026-06-22 완료):
   `diff_records(prev, new)` → `difflib` 로 레코드 `code` 시퀀스 정렬 → 엔진 좌표 `EditOp(event,start,end,
   code,close_before)` 스트림. equal=커서전진, insert=add, delete=delete, replace=1:1동일span→modify/그외
   delete+add. closeBefore 보존. `temp/test_diff_records.py` 16/16 통과(값변경=modify, 삽입/삭제, if/else
   closeBefore 전달, chunk 삽입/덮어쓰기, 무변경).
2. **엔진 Code Deletion** (`DynamicCFGBuilder.delete_cfg_range`, 2026-06-22):
   - **통일 SESE 알고리즘**: `node0=M[Ls]` → (entry,exit) 식별(루프=`find_loop_join`/`loop_exit`,
     if=node0/`_nearest_join`, 그외=단일노드) → `region = descendants(entry) ∩ ancestors(exit) ∪
     {entry,exit}` → 공유 sink 필터해 pred→succ 재연결 → region 제거 → `reinterpret_from(succ)`.
     **skeleton(t_blk/f_blk/while_join/body)·중첩·back-edge 자동 포함**(M 의존 X). join 은 구조로 탐색
     (M[Le]≠join, `}`줄에 등록되므로). 근거: `temp/inspect_cfg.py` 로 if/while ground-truth 확인.
   - ✅ **2a(simple)·2b(if/while) 완료**: `temp/test_delete_cfg.py` 7/7 — 삭제+evaluate == reduced
     소스 fresh 빌드(b fingerprint·node수 등가), reinterpret=True 무예외.
   - ✅ **2c-else 완료** (`_delete_else_clause`, kind="else"): else 줄 line_info=[if_join, else_block]
     이라 generic 이 join 을 지우는 문제 → 전용 처리. **false-분기 body 만 제거하고 빈 else_block→join 유지**
     (cond/join 보존, plain if 化). `temp/test_delete_else.py` 3/3(else 삭제 == plain if fresh, nodes·b 등가).
   - ✅ **2c-else-if 완료** (`_delete_else_if_clause`, kind="else if"): else-if cond+true-body+local_join
     제거 → false-child 를 위 cond 의 false 로 reparent, else 꼬리를 outer join 으로(체인 일반화).
     `temp/test_delete_2c.py` — else-if 삭제 == if/else fresh(nodes·b 등가).
   - ✅ **2c-lone-early-exit 완료** (`_delete_early_exit`, kind="return"/"revert"): true 분기는 sink 로 가
     join 미도달 → `_continuation_via_other_branch`(다른 분기 타고 첫 join/loop_exit) 로 fall-through 복원,
     `_walk_up_to_cond` 로 enclosing cond 탐색. lone-return 삭제 == 빈 then fresh(등가).
   - ☐ **2c 잔여(통삭제 전제)**: try-catch·do-while 은 **통째 삭제만** 지원(try-only/do-only 는 SyntaxValid
     거부 or 비의도) → step 5 배선에서 generic SESE + 미처리 시 함수 rebuild safety-net. break/continue 희소.
   - ★ **선행 blocker 수정**: `closeBefore` 미전달 버그(§5.5 known-bug #1) 해결 — `_apply_code_record`/
     `analyze` 가 `rec.get("closeBefore")` → `update_code(close_before)` 전달, `Record` 에 옵셔널 필드 추가.
     이게 없으면 else/do-while/catch 가 "else: target join not found" 로 빌드 실패(2c 의 전제).
3. ✅ **엔진 Code Modification** (2026-06-22): 두 결 — **단순 statement 값 변경**=delete+add(검증된 경로),
   **조건 헤더(if/while/for) 변경**=in-place(body 보존 필수, delete+add 불가). in-place = `DynamicCFGBuilder.
   modify_condition_expr`(cond 노드 condition_expr 만 교체) + `process_if/while/for_statement` 에 modify 분기
   (`current_edit_event=="modify"` → 새 빌드 대신 swap, return). `_is_condition_header` 로 라우팅. 검증:
   조건 modify == fresh(if `temp/test_update_block.py`, while 등가 확인).
4. ✅ **ANTLR SyntaxValid 게이트** (`incremental.syntax_valid`, 2026-06-22): 새 풀소스를 `sourceUnit`(EOF)
   로 파스 → 오류 수집. invalid 면 edit 거부(이전 valid CFG 유지) → **orphan-else/do-while·brace 불일치가
   CFG 수술에 도달 못 하게 원천 차단**(안전 전제). `temp/test_syntax_valid.py` 6/6(plain/if-else/do-while
   허용, orphan else/brace/orphan do-while 거부). **순서 정정**: 안전 전제라 2c·modify 보다 먼저 구현함.
   (적용 경로 배선은 5단계.)
5. ✅ **B1 배선** (`EngineSession.update`, `engine_server`, 2026-06-22): 영속 세션 + `update(new_source)`
   = SyntaxValid 게이트 → `diff_records` → 적용 순서 **modify(무이동)→delete(아래부터)→add(위부터)** 로 라인
   좌표 정합 유지(좌표=레코드 실제 startLine, delete=prev/add=new 공간). delete=`delete_cfg_range`(CFG)+
   `update_code(delete)`(소스 장부). `structure()` 추출(analyze/update 공용). `engine_server /analyze` 가
   첫 호출=fresh, 이후=증분 `update`. 검증: `temp/test_update*.py`·`test_session_flow.py` 통과 — 단순
   add/delete/value-modify, if-block add/delete, 조건 modify, **end-to-end analyze→update→evaluate→verify**
   전부 fresh 빌드와 등가, invalid 거부.
6. ✅ **프론트** (무변경): 프론트는 풀소스만 전송(`store.ts` `source: activeContent`) → 서버가 diff →
   **프론트 코드 변경 없이 B1 증분 적용**. (diagnostics squiggle·range 힌트는 선택 폴리시.)

**✅ rebuild safety-net (2026-06-22)**: `update()` 가 surgical 미지원 구조(try-catch/do-while/catch/
break/continue = `_is_risky_op`)면 `_full_rebuild`(새 분석기+records 전체 add-only 재적용)로, 그 외는
surgical 시도하되 **예외 시 rebuild 폴백** → **모든 valid 편집이 항상 정확**(corruption 불가). `temp/
test_safety_net.py` 6/6(do-while add/delete, break 삭제 == fresh). ② try/do-while/break/continue 해결.

**잔여(증분)**: ① reinterpret=True 증분 재해석(현재 evaluate full 재해석 — 정확하나 증분 이득 미실현;
**decision #26 보류와 일치** — 단일함수 fixpoint 이득 작고 widening 건전성 위험) ④ 다중-영역 동시편집
(현재 단일/연속 영역 검증; 비연속 다중편집은 미검증).

**✅ 출력 cleanup (2026-06-22)**: `Domain/IR.py Expression.__str__` 추가(재귀 렌더) → verdict 메시지가
`b > <Expression object at 0x..>` → `b > 0`(의미론 불변, display만). `_serialize_node_state` 가
`[None,None]`(bottom) → `⊥` 가독화(우리 레이어).

### 5.7 현재 상태 / 다음 후보 (handoff, 2026-06-22)

**동작하는 것 (테스트 67개 통과)**: B1 증분 편집 end-to-end.
- 편집: statement add/delete/value-modify, if-block add/delete, 조건 modify(in-place), if/else·else-if·
  lone-return 삭제 — 전부 fresh 빌드와 노드·states 등가. SyntaxValid 게이트로 invalid 거부.
- 안전망: try-catch/do-while/break/continue/미처리 → full-rebuild 폴백 → 모든 valid 편집 정확.
- 슬롯: Local(파라미터)/State(스칼라 interval·매핑 opaque)/Global(사용된 것만). verdict 텍스트·⊥ 정리.
- 서버: `/analyze` 첫 호출 fresh·이후 증분. 프론트 무변경(풀소스 전송). 레이아웃 = 상단 툴바+코드 좌+
  우측 세로3분할(Intent상단/Input/State).

**코어 변경 총괄(최소 침습)**: `DynamicCFGBuilder`(delete_cfg_range+else/else-if/early-exit/
modify_condition_expr 메서드 추가, 기존 불변) · `ContractAnalyzer`(process_if/while/for 에 modify 분기 3개) ·
`Engine.py`(freeze 게이트 + warning-combine, 기존) · `Domain/IR.py`(Expression.__str__ display) ·
`engine_api`(update/structure/_full_rebuild/슬롯/closeBefore) · `incremental.py`(diff/syntax_valid/kind, 신규).

**의도적 보류 (이유)**:
- **@IReturn 슬롯**: 키가 인터페이스 호출 패턴(`cVar.f()`/`Iface(addr).f()`)에서 *인터프리트 중* 형성
  (Evaluation.py) → analyze 시점 빈 상태. 구조적 도출 = 호출 AST 스캔+타입해석 신규 필요 → **DeFi 시나리오
  실구동 시** 착수(투기적 인프라 회피).
- **증분 reinterpret(reinterpret=True)**: decision #26 보류와 일치 — 단일함수 fixpoint 이득 작고 widening
  건전성 위험. 현재 evaluate full 재해석이 정확.
- **매핑 StateVar 값 시딩**(balances[addr]): 프론트+백 access-chain 계약 확장 필요(표시는 됨, seed 별도).
- **다중(비연속)-영역 동시편집**: 단일/연속 영역만 검증.

**다음 후보**: ① 브라우저 실동작 확인(서버 재시작 `.venv\Scripts\python.exe engine_server.py` + `npm run
dev`) ② @IReturn 호출 AST 스캔 ③ 매핑 시딩 access-chain ④ diagnostics→Monaco squiggle.

**테스트 파일**(`temp/`): test_diff_records / test_syntax_valid / test_delete_cfg / test_delete_else /
test_delete_2c / test_update / test_update_block / test_session_flow / test_safety_net. inspect_cfg{,2,3}.py 는
구조 관찰용.

### 5.8 디버그 입력 UX 세션 (2026-07-03) — 슬롯 정합·값 입력·시딩 버그

브라우저 실동작 확인 중 디버그 입력 경로에서 다수 버그 발견. 백엔드는 대체로 정상, **슬롯 도출·값 표시·다중
시딩·라인 좌표**에서 문제. 아래 ✅=수정완료(검증), 🔧=원인규명·수정방안 확정(미적용), ☐=미해결.

**✅ 수정 완료 (HTTP 검증):**
1. **① 슬롯 함수-스코프 필터** (`engine_api._derive_debug_slots`/`structure`): 이전엔 함수와 무관한 상태변수
   *전부* + 컨트랙트 어디서든 쓰인 글로벌이 떴음. → **StateVar = 이 함수가 참조하는 것만**(함수 소스 슬라이스
   `[min,max] src_line` 단어매치), **GlobalVar = `GlobalVariable.usage_sites`(func 추적) 기반**. `func_src`
   비면 필터 스킵(안전). 검증: deposit → `amt`(Local)/`balance`(State)만, fee/token/owner 제외.
2. **② valueKind 변수 타입 반영** (`_valuekind_of`, SolType 기반): 이전엔 전부 `interval` 하드코딩 → msg.sender
   가 interval 로 떴음. → `typeInfo(SolType)` 로 address/bool/interval/opaque 판별. **DebugInputPanel 이 이미
   valueKind 별 위젯 분기**(address→symbolicAddress 칸, bool→드롭다운)라 ②만 고치면 자동 정렬. 슬롯에
   `signed`/`bits` 필드 추가(Fix B 용).
3. **Fix B — 무제약(unbounded) interval 입력** (`_debug_value_text`): 빈 경계 = 그 방향 무제약, 백엔드가
   슬롯 타입 min/max 로 치환(`[5,]`=≥5=`[5,2²⁵⁶-1]`, uint 정확). 양쪽 빈칸=미입력 스킵(⊤). → 반쯤 친 값의
   500 crash 원천 소멸. (g4 문법 무변경 — 프론트 빈칸 허용 + 백엔드 치환.)
4. **Fix A — 잘못된 값 = crash 대신 구조화 에러**: `int('')` 등 → 500 대신 `Diagnostic` 수집
   (`_last_value_errors` → `CfgWithStates.diagnostics` → 서버 `/evaluate` 반환). 프론트 `runAnalysis`
   **try/finally 로 `analyzing` 항상 해제**(과거 500 시 멈춤 버그) + `analyzeError` 배너 + `valueErrors`
   슬롯 위 표시.
5. **★ debugInputs 키 불일치 (진짜 "값 입력 안됨" 원인)**: 쓰기(`setDebugValue`)·엔진전송(`runAnalysis`)은
   맨 func명("deposit"), 표시(`DebugInputPanel`)·시드는 `keyOf`("Vault.deposit") → 타이핑 값이 딴 키에
   저장돼 입력칸에 안 뜸. → **전부 `keyOf(contract,func)` 로 통일**(시드 형식이 정본).

   코어 무수정. 변경 파일: `engine_api.py`(슬롯 도출·값 치환·에러) · `engine_server.py`(/evaluate diagnostics) ·
   `frontend`(store try/finally·키통일·에러state, DebugInputPanel valueErrors·힌트, DebugView 배너,
   styles.css). tsc 통과.

**✅ 추가 수정완료 (2026-07-03 이어서):**
6. **★ 다중 슬롯 시딩 충돌 (핵심 버그) — 해결·검증**: balance=[10,20]+amt=[100,200] → 기대 [110,220]인데
   **[100,200]** 이던 문제(balance 시드 유실). 규명: `DebugBatchManager._lines` 가 **startLine 키 `dict`**
   인데 `_queue_debug_values` 가 모든 디렉티브를 `add_line(...,0,0)` → **전부 key 0 충돌, 마지막만 생존**.
   원인 = 옛 모델(annotation 을 코드에 삽입 → 라인 밀림)의 라인키 잔재; 삽입-없는 모델(decision #8)에선 무의미.
   - **적용(decision #29)**: `_lines` `dict[int]` → **`list[str]`**(순서 보존, 라인키 제거, DebugUnitAnalyzer.py
     재작성). `add(code)` 신설 + `add_line(code,s=0,e=0)` 하위호환 alias(append). `modify_line`/`delete_line`
     제거. **snapshot/restore 유지**(flush `finally: restore_from_snap` = evaluate 독립성). engine_api
     `_queue_debug_values` → `self._batch.add(...)`. `main.py` 디버그주석 분기도 add 누적으로 정리(modify/delete
     라인선택 폐기, 회귀 무관 — 사용자 허용).
   - **검증(HTTP)**: Vault.deposit, balance=[10,20]+amt=[100,200] → `Assign_5`·`EXIT` 노드에서
     `balance=[110,220]`, `amt=[100,200]`, diagnostics 없음. 충돌 소멸 확정.

**✅ 추가 수정완료 (7번 — 라인 좌표계, 2026-07-06):**
7. **★ #3 라인 좌표계 불일치 (표시 안 됨의 핵심) — 해결**: 엔진 `CFGNode.src_line` 은 **컨트랙트-절대 라인**
   (`balance=balance+amt` = 25)인데 CodePane 이 **함수-로컬 소스**(`fnMeta.source`, 그 문장=라인 2)를 표시 →
   데코/네비/State&Locals/intent glyph 전부 어긋나 값이 계산돼도 안 보임.
   - **결정 (a) 채택**: 프론트를 **절대라인 = 전체 컨트랙트 소스 표시**로 통일. 데코/네비/breakpoint/intent 가
     이미 절대 src_line 을 쓰므로 **소스만 전체로 교체하면 오프셋 코드 없이 자동 정합**((b) 매핑층 불필요).
   - **적용**: `DebugView.tsx` = CodePane 에 `fullSource`(활성파일 전체) + `focusLine`(함수 startLine) 전달.
     `CodePane.tsx` = `focusLine` prop → 마운트/함수전환 시 `revealLineInCenter` 스크롤.
     `mock/result.withdraw.json` = 시딩 intent `line 9`(구 로컬) → **21**(절대). tsc 통과.
   - **검증**: 엔진이 전체 mock 소스로 `Assign_25 src_line=25 balance=[110,220]` emit 확인 → Monaco 25번 줄
     (=`balance=balance+amt;`)에 정확 정합. **육안(브라우저) 확인은 미완**(Monaco 헤드리스 불가).
   - 잔재: `result.withdraw.json` 의 cfg/verdict 는 구 로컬좌표(src_line 1~10)지만 **표시 미사용**(store 는
     `intents` 만 읽음) → 방치. 오프라인 mock 표시 되살리면 전체 변환 필요.

**✅ 추가 구현완료 (10번 — Apply 버튼, 2026-07-06):**
10. **디버그 입력 "적용" 버튼 + 결과 표시** (decision #32) — 구현:
    - `store.ts`: `setDebugValue` 에서 자동 evaluate 제거(값 변경=상태만). `applyDebug(func)` 액션 신설
      (runAnalysis evaluate). `applyTick` 카운터 추가 → evaluate 실제 실행 시에만 +1(intent-only verify 는
      커서 안 옮김).
    - `DebugInputPanel.tsx`: `▶ 적용 (Enter)` 버튼(`analyzing` 시 비활성·"적용 중…"), 패널 `onKeyDown` Enter →
      apply. `styles.css` `.apply-btn`.
    - `useNavigation.ts`: `applyTick` 변화 시 커서 재배치 = **run-to-breakpoint** (entry→비-⊥ successor 따라
      전진, 첫 breakpoint 라인에서 정지; 없으면 **EXIT** 최종상태). → State&Locals 가 변수별 결과 즉시 표시.
    - `StateLocals.tsx`: 전역(block./msg./tx.) `<details>` 접기(기본 접힘)로 실변수 결과 강조. path 음수라인 필터.
    - tsc 통과. **브라우저 육안 확인 미완**.

**✅ 추가 수정완료 (자동계산 제거 + 함수-only 뷰, 2026-07-06 이어서):**
11. **자동 계산 버그 제거 (구조/값 분리)**: 브라우저에서 "디버그 진입만 해도 값이 자동 입력·계산됨" 보고.
    - 원인 (A) 값 자동입력 = mock seed(`Vault.withdraw` a/token) + zustand persist 가 `debugInputs` 를
      localStorage 저장 → 이전 세션 값 복원. (B) 자동계산 = tier 로직 `needEvaluate = needStructure || …` 라
      **structure(편집·디버그진입)가 evaluate 까지 발사**. Apply 버튼 무색.
    - 수정: `store.ts` `needEvaluate = tier==='evaluate'` (structure 는 CFG 만), `needVerify = evaluate||verify`
      로 verify 게이트. **openDebug/setActiveFunction = 캐시 있으면 재빌드 안 함(fetch), 없을 때만 1회 빌드**
      (사용자 방향: "workspace 편집 때 CFG 만들고 debug 는 가져오기" — updateActiveContent 가 이미 편집 시
      structure 빌드 중. per-func 세션이라 미방문 함수 첫 진입만 증분 빌드). mock 값 seed 제거 → 빈 칸 시작.
      persist 에서 `debugInputs` 제외 + version 3 migrate 로 잔재 클리어(what-if 값 세션성).
12. **함수-only 뷰 + 컨트랙트-절대 라인넘버 (#7 재조정)**: 전체 컨트랙트 대신 **해당 함수만** 표시하되 gutter
    라인넘버는 절대. `CodePane` = `startLine` prop, `offset=startLine-1`, `toLocal(abs)=abs-offset`,
    Monaco `lineNumbers:(n)=>n+offset`, 데코/breakpoint/intent 를 절대↔내부 변환(함수범위 밖 스킵). breakpoint
    클릭은 내부→절대 저장. `DebugView` = `fnMeta.source`+`startLine` 전달. 검증(수식): deposit offset=23,
    src_line25→내부2줄 정합. **(a)에서 없앴던 오프셋을 헬퍼 2개로 중앙화** — 손댈 곳 CodePane 1파일로 한정.
13. **breakpoint pre-state 표시 (실행 후 값 보이던 버그 · 단일선행)**: 브라우저에서 `balance=balance+amt;`
    에 breakpoint 찍으면 **실행 후**(`[110,220]`)가 보임. 원인 = 엔진 `CFGNode.state` 는 **out-state**(실행 후)
    라 커서 노드 state 를 그대로 표시하면 pre-state 가 아님. **사용자 통찰**: 새 in-state 필드 불필요 — "이 줄
    실행 직전" = **선행(predecessor) 노드의 out-state**. 구현(`StateLocals.tsx`): 커서 노드의 (단일)선행
    out-state 를 표시. 선행이 ENTRY(빈 상태)면 = **함수 첫 문장** → 노드 out-state 에서 시드된 진입값만 override
    하는 폴백(미시드/전역은 불변이라 out=in). EXIT 은 최종상태 그대로. note 라벨("이 줄 실행 전"/"진입 상태"/
    "최종 상태") 표시. tsc 통과.

**☐ 미해결:**
8·9. **compound 슬롯 + @IReturn 슬롯 = 통합 "접근-경로 스캐너" ✅ 구현·e2e 검증 완료** (decision #34):
    `engine_api._derive_debug_slots` 에 통합 스캐너(`_ap_*`) 추가 — node.statements AST 정적 순회로
    compound(mapping/struct/array) 경로 + 인터페이스 호출(IReturn)을 도출. compound root 상태변수는 opaque
    통짜 슬롯 대신 경로 슬롯으로 대체, 인터페이스 핸들 변수는 IReturn 이 대체(스칼라 방출 스킵).
    **e2e(.venv 실측)**: `_balances[u]`(mapping→interval) / `accountBorrows[u].principal`(mapping→struct→member
    →interval, **leaf 해소 성공**) / `token.balanceOf()`(IReturn, 인자 드롭·opaque). 스칼라 `total`·파라미터 유지.
    **잔여**: ① compound **값 evaluate** 경로의 엔진 버그 2개(아래 #34 b1/b2) ② IReturn leaf 가 address 반환일 때
    valueKind 세분(현재 interval 기본) ③ LocalVar-compound(로컬이 mapping/struct, RQ1 부재) 미처리 ④ 브라우저 육안.
14. **breakpoint pre-state — 조인(다중 선행) 지점 (decision #33) — 해결(A: 프론트-only), try/catch 잔여**:
    위 13 은 단일 선행만 정확했고, 조인 지점 표시가 문제였다. **엔진 구조 확인으로 프론트-only 해결 확정**:
    - **엔진 사실(확인)**: `ContractAnalyzer.process_if_statement` 이 **join 을 즉시 생성**(`if_join`,
      `join_point_node=True`) 후 body 채워지면 `engine.reinterpret_from(join)` → join out-state = **sound merge**.
      else-if/else 는 같은 join 재사용. join 의 `src_line = end_line`(= `}` 라인). 루프는
      `build_while/for_statement` 이 `loop_exit_node`(src_line=end_line) 생성, do-while 은 `fixpoint_evaluation_node`(φ).
      루프 멤버십 = `is_loop_body`(부모→자식 전파). **이 모두 프론트로 직렬화됨**(`engine_api._node_flags`:
      flag `merge`/`loop_exit`/`fixpoint_evaluation`/`loop_body`/`exit` + `cond_type` + `src_line`).
    - **정리(theorem)**: 이 CFG 에서 forward-pred(≥2)인 노드는 오직 ① join(`merge`) ② loop_exit(cond-false+모든 `break`)
      ③ do-while φ 뿐(루프 헤더는 back-edge 제외 시 단일). 따라서 **이 flag 노드만 breakpoint 타겟에서 빼면**
      남는 착지 노드는 전부 forward-pred=1 → 위 13 의 "선행 out-state = pre-state" 로직이 이미 정답.
    - **구현(프론트-only, 코어 무변경, tsc OK)**:
      · `useNavigation.ts`: `isForbiddenTarget`(flag merge/loop_exit/fixpoint_evaluation/exit) + `canBreakpointOnLine`
        (그 라인에 비-금지 노드 하나라도 있으면 허용). run-to-bp walk 정지조건에 `!isForbiddenTarget` 안전망.
      · `CodePane.tsx`: `}`/구조적 라인 gutter 클릭 시 breakpoint 설정 무시(+onMount 클로저 stale 방지 ref).
      · `StateLocals.tsx`: `loop_body` 노드는 pre-state 가 **fixpoint 불변식**이므로 note 에 "· 루프 불변식(모든
        iteration)" 부기. (루프 안은 **금지 안 함** — 디버깅 가치 큼, 라벨로 의미만 명확화.)
    - **잔여 ☐ try/catch**: `try_join` 은 `merge` 라 자동 포함(타겟 금지)되나, **catch 블록 진입(catch_entry/
      catch_end)의 "예외 발생 직전" pre-state** 의미는 미검증(선행 단일 여부·정상/예외 경로 구분). 별도 과제.
    - **미검증**: 브라우저 육안(특히 while/for 루프 함수 = 실엔진 필요, mock 엔 루프 없음).

**이번 세션 설계 결정 (decisions log 확장):**
- **(29) DebugBatch = 번들 모델** (라인키·BEGIN/END 폐기, snapshot/restore 유지). 위 6 참조.
- **(30) compound 접근 = 코드 스캔 자동 도출** (decision #6 "값만 입력" 준수, @IReturn 과 동일 인프라):
  함수 표현식 IR 순회 → base 가 mapping/struct/array 인 index/member 접근 체인 수집 → **등장한 distinct
  경로마다 슬롯**(key=경로문자열 `balances[msg.sender]`·`accountBorrows[k].principal`, valueKind=leaf 타입).
  사용자는 값만 채움. 근거 = **RQ1 실어노테이션이 이 형태**(`SolidityGuardian/evaluation/RQ1/cases`):
  `@StateVar balances[msg.sender]`, `_allowances[1][101]`(중첩), `accountBorrows[101].principal`(매핑[키].멤버),
  `_ctx.a.x`(중첩구조체), `self.balances[account]`(구조체.매핑). 엔진이 이미 파싱·해석(RQ1 20/20). 난점:
  ①키가 변수면(`balances[to]`) 그 변수도 seed돼야 resolve → **로컬 seed 먼저 emit** ②leaf 타입 = 체인 따라
  해석 ③함수에 안 나타나는 엔트리(불변식용)는 자동도출 불가 → 필요시 수동추가 escape hatch(후순위).
  ★일부 케이스(루프 `arr[i]` 등 구체 인덱스)는 사용자·solver 몫.
- **(31) L2 값 제안 = 엔진 오라클 + LLM/solver 제안자** (decision #9/#12/#17 구체화). 하위분해: (1)코드에 있는
  경로/키 = **도출** / (2)구체 인덱스·미등장 엔트리 = **사용자·solver** / (3a)분기도달·intent 위반 witness =
  **solver**(`reach`) / (3b)opaque·현실적 값(decimals·토큰크기·외부리턴) = **LLM**(`suggest_value`). 구조 =
  LLM 후보 → 엔진 evaluate/verify 검증 → 채택(LLM 오류를 엔진이 가드). **RQ1 어노테이션 프롬프트 활용**: 포맷
  few-shot·magnitude 주입엔 유용하나 **누수 경계**(RQ1=평가셋 → few-shot 전용, 성능평가는 held-out) +
  objective 명시("bug witness" vs "plausible"). **후순위** — 결정론 코어(6→8→7) 먼저.

- **(32) 디버그 입력 = Apply 버튼 트리거 + 결과 State&Locals 노출** (신규, 위 10): per-keystroke evaluate 는
  interval 여러 글자 입력 중 매 글자 발사 → 낭비·partial 값 transient 에러. 디버거 멘탈모델("여러 변수 what-if
  세팅 → 한 번 실행")에 맞춰 **명시 Apply 버튼(+Enter)** 로 전환. 백엔드는 이미 `debugInputs` 통째 전송이라
  번들 무변경. **적용 = "run"**: breakpoint 있으면 그 지점까지, 없으면 EXIT(최종상태)로 커서 자동 이동 →
  State&Locals 가 변수별 값을 즉시 표시(7번 좌표계 수정으로 이제 의미 있음). 대안(debounce/onBlur)보다
  예측가능. ★"안 뜸"의 해결책은 7번이고 버튼은 UX 개선임을 구분.

- **(33) breakpoint 표시상태 = 선행 out-state(= pre-state) — 확정(A: 프론트-only)** (위 13·14): CFGNode.state
  는 out-state 라 커서 노드 그대로 표시하면 "실행 후". "이 줄 실행 직전" = **선행 노드 out-state**(별도 in-state
  필드 불필요 — 사용자 통찰). 단일선행·ENTRY(시드 override)·EXIT(최종) 구현완료. **조인(다중선행) 문제는 옵션
  (a)/(b) 대신 "타겟 제한"으로 회피 확정**: 엔진이 join 을 명시 노드(`merge`)로 즉시 만들고 sound merge 하며,
  join/loop_exit/φ/exit flag 가 프론트로 직렬화되므로 — **이 구조적 노드에는 breakpoint 를 못 걸게** 하면 남는
  타겟은 전부 forward-pred=1 → 선행 out-state 로 정확. 엔진 in-state 노출/프론트 merge 둘 다 불필요. 루프 본문은
  금지 대신 "루프 불변식" 라벨. 구현 = `useNavigation`(isForbiddenTarget/canBreakpointOnLine)+`CodePane`(클릭 차단)
  +`StateLocals`(loop_body 라벨). **잔여**: try/catch catch-블록 pre-state 미검증. 위 14 참조.

- **(34) compound + @IReturn = 통합 정적 "접근-경로 스캐너" ✅ 구현완료** (decision #30 확장, item 8·9 병합; 전제·결과 e2e 검증):
  둘은 **동형 문제** — 슬롯 = **ROOT + accessor\*** , 키 = `str(maximal_path_expr)`. accessor(공통) = index/member/call.
  ROOT 만 분기: compound 상태/로컬변수(mapping/struct/array typeInfo) → StateVar/LocalVar / 인터페이스 호출
  `v.f()`·캐스트 `I(a).f()`(interface 타입·`interface_names`) → IReturn(opaque).
  **어디서 하나 = evaluator 아님, `_derive_debug_slots`(engine_api, 비코어)가 `node.statements` AST 를 훑음**:
    - evaluator 는 bottom-up 재귀라 **maximal 경로 경계("재귀의 끝")를 모름** → 중간 인터페이스 핸들이 가짜
      슬롯으로 샘. 또 fixpoint 로 여러 번·값 있을 때만 돌고 재평가 유발. statement 레벨 순회는 `stmt.left/right/
      init_expr` = 애초에 maximal 표현식에서 base 따라 root 로 하강 → 경계 공짜·1회·구문+타입만. (사용자 통찰)
  **전제 검증(e2e, `.venv` 실측)**:
    ① `Expression.__str__` 이 경로를 정규 직렬화 — `accountBorrows[msg.sender].principal`,
      `engine.mochiProfile().calculateFeeIndex()`, `IERC20(baseToken).balanceOf()` 등 6/6 정확.
    ② analyze 후 `node.statements` 에 expr AST **보존됨**(`VarDecl.init_expr=Expression:'_balances[u]'`,
      `Assign.left/right`) → 정적 스캔 실현가능. (사용자가 의심한 "evaluation 후 폐기"는 아님.)
    ③ 현 도출 갭 실증: `_balances` 매핑을 opaque 슬롯 1개로만 냄(필요한 `_balances[u]` 못 줌).
  **키-변수 의존성**: `[u]`·`[msg.sender]` 등 변수 키는 그 자체가 스칼라 슬롯(param/global/local)로 이미 도출 →
    Apply 배치에서 함께 seed → **emit 순서 무관**(#30 의 "먼저 emit" 제약 불필요). 완전 심볼릭 인덱스(`arr[i]`)는
    #30 대로 사용자·solver 몫 — 스캐너 정책(심볼릭 키째 emit vs skip) 구현 시 결정.
  **위치**: 이 프로젝트만 변경, **SolidityGuardian 반영 안 함**(사용자 지시). evaluator 코어 훅 대체 → 코어 무변경.
  **★ 도중 발견 별개 엔진 갭 2개**(슬롯 도출 무관, compound **값 evaluate** 시 물림):
    (b1) nested-literal-key 쓰기 `_allowances[1][101]=p` → "Literal '101' cannot appear standalone on LHS"
      (안쪽 `[101]` 처리 때 부모 매핑을 caller_object 로 안 넘김; Update.py:386).
    (b2) nested-literal-key 읽기 `q=_allowances[1][101]` → `Evaluation.update_mapping_in_cfg` 가 없는 속성
      `self.current_target_function` 참조 → AttributeError.
    **성격 재평가(사용자 지적, 후순위 격하)**: 두 케이스 다 **벌거벗은 이중 정수 리터럴 키** — 실 RQ1 입력엔
    안 나오는 인위적 코너(실 키는 `msg.sender`·변수·타입 있는 표현식). int/address 모호성도 실은
    매핑 **선언된 키 타입**(`ref_var.typeInfo`)으로 해소되므로 "리터럴 금지"가 아니라 **중첩 전파 구멍**.
    단일 리터럴 키(`_balances[1]`)는 정상. → 실입력 무관, 우선순위 낮음.

- **(35) forward 네비게이션 "dead-branch" 버그 수정 ✅**(프론트-only, 엔진 무결 확인):
  **증상**: withdraw 에 `a=bal=token.balanceOf()=[10,10]` 넣고 require(`a<=bal`)에서 forward → **error_exit 로 샘**.
  **진단(`.venv` repro 실측)**: 엔진은 **정상** — IReturn 값이 로컬 `bal` 에 정상 바인딩(`bal=[10,10]`),
    require true 후속 채워짐, ERROR state 는 빈 `{}`(미도달), 최종 `balance=[0,0]` 정확. 문제는 프론트 네비:
    `stepForward` 가 `succ()[0]` 만 집음 → require 엣지 순서가 `false→ERROR` 먼저라 죽은 sink 로 감.
    게다가 `isBottom` 이 `⊥`만 봐서 **빈-state ERROR(⊥ 아님)를 못 걸렀음**.
  **수정 = 엔진 `_run_worklist` 알고리즘 1:1 이식**(사용자 지시): `engineDead(id)` =
    `id===cfg.error_exit`(엔진 `_is_sink`, error_exit **만** — return_exit 은 정상도달이라 제외)
    **OR** state 에 `⊥`(엔진 `_is_bottom_env` "하나라도 BOTTOM"). 빈-state 휴리스틱 대신 **id 로 sink 직접 식별**
    (직렬화가 세 exit 를 `'exit'` 플래그로 뭉개지만 `cfg.error_exit/return_exit/exit` id 는 분리 보존).
    `forwardPick` = 살아있는 후속 우선(전부 죽으면 `ss[0]` 폴백). `stepForward/stepInto/continueRun` +
    자동배치 effect(run-to-bp, 같은 잠재버그) 일괄 적용. tsc 통과.
  **잔여 정책**: 양쪽 다 live 인 조건(require 통과·실패 둘 다 가능)에선 여전히 엣지 순서 first-live —
    명시적 "true 우선" tie-break 는 엔진 의미가 아닌 UX 결정이라 **미적용**(요청대로).
  **부수**: mock `result.withdraw.json` 의 유령 intent(`before: bal>=a`·`changed(balance)`, 잘못된 문법) 제거.
    단 이 파일은 import 안 되는 죽은 mock — 실 유령 intent 출처는 **localStorage persist(`intents`)** 일 수 있음
    (store `partialize` 가 저장, `migrate` 가 v3 서 debugInputs 만 지우고 intents 는 안 지움). 필요시 version bump.

**다음 우선순위:** ~~6 리스트-batch~~ ✅ · ~~7 라인 좌표계~~ ✅ · ~~10 Apply 버튼~~ ✅ ·
~~8·9 compound+IReturn 스캐너~~ ✅(decision #34) · ~~13·14 pre-state~~ ✅(#33) · ~~forward dead-branch~~ ✅(#35) →
① **브라우저 재확인**(6·7·10·8·9·#35 육안 — 값 입력→적용→변수별 결과·경로 슬롯·require forward 경로) →
② L2(decision #31) → ③ try/catch pre-state(#33 잔여). (#34 b1/b2 는 인위적 코너라 후순위 격하)

**세션 노트**: 서버 세션은 메모리에 `contract.func` 키로 영속 → **테스트 컨트랙트가 프론트 세션 오염** 가능
(재시작으로 클리어). 콘솔 한글 mojibake 는 cp949 출력 문제일 뿐 JSON 은 UTF-8 정상.

---

## 6. 실행/환경 메모

- 엔진 실행: **반드시 `.venv\Scripts\python.exe`** (글로벌 Python310 networkx 2.5.1 깨짐). 검증: `.venv\Scripts\python.exe evaluation\RQ1\run_all.py` → 20/20 VIOLATED.
- `load_dependencies`는 3개 디렉토리 interface 스캔 필요(`evaluation/RQ1/target_contracts_contraction`, `.../target_contracts_original/dependencies`, `Dataset/Numscout/contraction`).
- 프론트: `cd frontend && npm install` (1회), `npm run dev`. 타입체크 `npx tsc --noEmit`.
- 작업 규칙(CLAUDE.md): 객관적·비판적 검토 / 제안 도구(코어 수정 전 승인) / 모호하면 질의.
