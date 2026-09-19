# RQ2 실험 수행 프로세스 가이드 v2

## 프로젝트 개요
- **프로젝트**: IntentChecker
- **목적**: Solidity 스마트 컨트랙트의 numeric logic vulnerability를 개발자 의도(intent annotation) 기반으로 탐지/완화하는 정적 분석 도구
- **분석 방법**: Abstract interpretation (interval domain) + developer-provided debug/intent annotations
- **논문**: `paper/main.tex`

## 핵심 지시사항
- **오류가 나면 바로 수정하지 말고 사용자에게 먼저 보고할 것**
- **모르는 것이 있으면 사용자에게 물어볼 것**
- **코드 수정 전 반드시 사용자에게 수정 방향을 설명하고 승인받을 것** (직접 판단하여 수정 금지)
- **방어 코드(try-except 무시, None 체크 후 pass 등) 금지** — 근본 원인을 파악하고 일반화된 방향으로 해결할 것
- **항상 위 사항들을 지킬 것**

## 실행 방법

### 개별 케이스 실행
```bash
# main.py에 JSON 경로 전달 (subprocess)
PYTHONIOENCODING=utf-8 python main.py "evaluation/RQ1/cases/web3bugs_47_H_02/web3bugs_47_H_02.json"

# Python에서 subprocess로 실행
import subprocess, sys, os
env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'
result = subprocess.run(
    [sys.executable, 'main.py', '경로/파일.json'],
    capture_output=True, timeout=120, env=env
)
out = result.stdout.decode('utf-8', errors='replace')
err = result.stderr.decode('utf-8', errors='replace')
```

### 전체 회귀 테스트
```bash
for f in evaluation/RQ1/cases/*/*.json; do
  name=$(basename "$f" .json)
  result=$(PYTHONIOENCODING=utf-8 python main.py "$f" 2>&1 | \
    grep -oE "INTENT (VIOLATION|SATISFIED|WARNING)|INTENT VIOLATED|POST INTENT VIOLATED" | head -1)
  if [ -z "$result" ]; then
    err=$(PYTHONIOENCODING=utf-8 python main.py "$f" 2>&1 | \
      grep -oE "ValueError:.*|AttributeError:.*" | head -1)
    [ -n "$err" ] && result="ERROR: ${err:0:60}" || result="NO_OUTPUT"
  fi
  echo "$name: $result"
done
```

### pkl 재생성
```bash
python Dependencies/main.py  # Dependencies 전체 재분석 + pkl 생성
```

## 데이터셋 구성
- **총 89건**: Web3Bugs 81건 + Numscout 8건
- **마스터 인덱스**: `evaluation/RQ1/dataset.csv`
- **케이스 JSON**: `evaluation/RQ1/cases/{category}/{name}.json`

## 핵심 파일 경로
| 파일 | 경로 | 설명 |
|------|------|------|
| 메인 실행 | `main.py` | JSON 입력 → 분석 + intent 검증 |
| Dependencies 분석 | `Dependencies/main.py` | .sol → pkl 사전분석 |
| pkl 저장소 | `Dependencies/objectfile/` | ifc_*.pkl, lib_*.pkl, con_*.pkl |
| Grammar | `Parser/Solidity.g4` | Intent annotation 문법 정의 |
| Engine | `Interpreter/Engine.py` | CFG 해석 + intent 검증 실행 |
| Evaluation | `Interpreter/Semantics/Evaluation.py` | 식 평가 + library dispatch |
| ContractAnalyzer | `Analyzer/ContractAnalyzer.py` | contract-level 분석 |
| SolidityAnalyzer | `Analyzer/SolidityAnalyzer.py` | 소스 관리 + file-level 처리 |
| Verifier | `Analyzer/GuardianVerificationEngine.py` | intent 검증 엔진 |
| Visitor | `Analyzer/EnhancedSolidityVisitor.py` | ANTLR parse tree → IR |
| CFG 구조 | `Utils/CFG.py` | ContractCFG, LibraryCFG, FunctionCFG |
| 논문 | `paper/main.tex` | 메인 논문 파일 |
| v1 가이드 | `evaluation/RQ1/PROCESS_GUIDE.md` | 세션 1~7 상세 기록 (아키텍처, grammar, 구현 이력) |

## Intent Annotation 문법
```
// During:
//   @During var(Before relOp After)              -- DuringBeforeAfter
//   @During var(Assign relOp Current)            -- DuringAssignCurrent
//   @During func.arg[N] relOp value              -- DuringFunctionArg
//   @During lhs relOp rhs                        -- RelationalCmp (commonClause)
//   @During antecedent => consequent             -- Implication (commonClause)
//   @During changed(var, true/false)             -- VarChangedEval (commonClause)

// Post:
//   @Post var(Entry relOp Exit)                  -- PostEntryExit
//   @Post lhs relOp rhs                          -- RelationalCmp (commonClause)

// relOp: >, <, >=, <=, ==, !=
// logicOp: && (여러 clause 연결 가능)
```

## Debug Annotation 문법
```
// @Debugging BEGIN                              -- 디버그 영역 시작 (함수 본문 첫 줄에 위치)
// @GlobalVar msg.value = [0, 0]                 -- 글로벌 변수 설정
// @StateVar balances[account] = [50, 50]        -- 상태변수 설정
// @LocalVar amount = [-100, -100]               -- 지역변수 설정
// @LocalVar to = symbolicAddress 10             -- symbolic address 할당
// @IReturn engine.cssr().update() = [1e18, 1e18] -- interface 반환값 설정
// @Debugging END                                -- 디버그 영역 끝
```

**주의사항:**
- `@Debugging BEGIN`은 함수 헤더가 아닌 **함수 본문 첫 줄**에 위치해야 함 (함수 헤더에 두면 `_batch_targets`에 잘못된 fcfg가 등록됨)
- debug annotation 라인 번호는 서로 겹치지 않아야 함
- intent annotation은 debug 영역 밖, 코드 라인과 같은 startLine에 위치

---

## 세션 8 (2026-04-06) 변경사항 종합

### 1. 코드 변경 요약

#### A. ImplicationContext visitor 수정 + nonzero 평가기
| 파일 | 변경 |
|------|------|
| `EnhancedSolidityVisitor.py:987-993` | `commonClause(0/1)` → `intentValue(0/1)`, `{"kind":"nonzero","expr":...}` 래핑 |
| `GuardianVerificationEngine.py` | `_eval_nonzero()` 메서드 추가, `_eval_during_predicate`/`_eval_post_predicate`에 `"nonzero"` 분기 |

#### B. _resolve_alias_from_expr 일반화
| 파일 | 변경 |
|------|------|
| `Evaluation.py:2551-2583` | `IndexAccessContext` 지원 — 평가 후 Variables typeInfo 확인 |
| `Evaluation.py:2561-2583` | `FunctionCallContext` 지원 — 체이닝 시 base object 재귀 추적 + using_libraries 역추적 |
| `Evaluation.py:2585` | 일반 fallback 제거 (side effect 위험) |

#### C. Library qualified call 체이닝 수정
| 파일 | 변경 |
|------|------|
| `Evaluation.py:2122-2125` | `evaluate_library_function_call_context`: `implicit_first_arg=None`일 때 인자 리스트에 안 넣도록 수정 |
| `Evaluation.py:2580` | `_resolve_alias_from_expr`: `library_name` 속성 우선 사용 (`contract_name` fallback) |

#### D. pkl wrapper 포맷 변경 (SolidityAnalyzer 단위)
| 파일 | 변경 |
|------|------|
| `Dependencies/main.py` (line 375,400,430) | dump 3곳 → `{"cfg": cfg, "file_level_structs": ..., "type_aliases": ...}` |
| `Dependencies/main.py` (line 294) | `_load_parent_pkls` unwrap 추가 |
| `main.py` (line 33,48,66) | `load_dependencies()` unwrap + `sa.file_level_structs`, `sa.type_aliases` merge |
| `main.py` (line 45) | lib_ prefix에서 숫자 서브폴더 제거 (con_과 동일 처리) |
| `ContractAnalyzer.py` (line 665) | `process_using_directive` pkl fallback unwrap |
| `ContractAnalyzer.py` (line 715) | `resolve_library_struct` pkl fallback unwrap |
| `Evaluation.py` (line 115, 222) | 동적 interface pkl load unwrap |
| `CFGSerializerPickle.py` | save/load 전체 wrapper 포맷 지원 |

#### E. Modifier overload dict 수정
| 파일 | 변경 |
|------|------|
| `StaticCFGFactory.py:130-132` | `make_modifier_cfg`에서 `functions[modifier_name]`이 overload dict일 때 첫 번째 FunctionCFG 추출 |

#### F. HIT_input.json 수정
| 변경 | 내용 |
|------|------|
| `@Debugging BEGIN` 라인 | 54(함수 헤더) → 55(함수 본문) |
| 전체 debug annotation 라인 | 1씩 shift (55-62) |

---

### 2. 케이스별 실행 결과 (세션 8 최종)

| # | Case | 이전(세션7) | 현재(세션8) | 비고 |
|---|------|:---:|:---:|------|
| 1 | WANGMI | ✅ VIOLATED | ✅ VIOLATED | |
| 2 | Nokon | ✅ VIOLATED | ⚠️ WARNING | **regression** — LHS 구간 넓어짐 |
| 3 | SwordCrowdsale | ✅ VIOLATED | ✅ VIOLATED | |
| 4 | BoostToken_operator | ✅ VIOLATED | ✅ VIOLATED | |
| 5 | BoostToken_indivisible | ✅ VIOLATED | ❌ ERROR | **regression** — `_rOwned` not declared |
| 6 | HIT | ❌ ERROR | ✅ VIOLATED | **신규 해결** |
| 7 | 5_H_07 | ✅ VIOLATED | ✅ VIOLATED | |
| 8 | 5_H_08 | ✅ VIOLATED | ✅ VIOLATED | |
| 9 | 5_H_12 | ✅ VIOLATED | ❌ ERROR | **regression** — `iERC20` interface empty |
| 10 | 77_H_01 | ✅ VIOLATED | ✅ VIOLATED | |
| 11 | 101_H_01 | ✅ VIOLATED | ✅ VIOLATED | |
| 12 | 45_H_01 | ✅ VIOLATED | ✅ VIOLATED | |
| 13 | 47_H_02 | ✅ VIOLATED | ❌ ERROR | **regression** — `member 'div'` not recognised |
| 14 | 51_H_02 | ✅ VIOLATED | ✅ VIOLATED | |
| 15 | 56_H_02 | ✅ VIOLATED | ❌ ERROR | **regression** — NoneType getText |
| 16 | 58_H_02 | ✅ VIOLATED | ⚠️ WARNING | **regression** — 결과 변경 |
| 17 | 60_H_01 | ❌ ERROR | ✅ VIOLATED | **신규 해결** |
| 18 | 62_H_08 | ✅ VIOLATED | ✅ VIOLATED | |
| 19 | 70_H_10 | ✅ VIOLATED | ✅ VIOLATED | |
| 20 | 77_H_01 | ✅ VIOLATED | ✅ VIOLATED | |
| 21 | 78_H_02 | ✅ VIOLATED | ❌ ERROR | **regression** — `is_bottom` None |
| 22 | 42_H_01 | ❌ 미생성 | ❌ ERROR | `bytes32 constant` 선언 미지원 |

**요약: 15 VIOLATED + 2 WARNING + 5 ERROR = 22건**

---

### 3. Regression 분석 (7건)

#### WARNING (2건) — 이전 VIOLATED → 현재 WARNING

| Case | 증상 | 추정 원인 |
|------|------|----------|
| Nokon | LHS `[12.5e21, 33.3e21]` (이전 `[12.5e21, 12.5e21]`) | `_resolve_alias_from_expr` 변경으로 SafeMath dispatch 경로 변화 → 구간 넓어짐 |
| 58_H_02 | WARNING으로 변경 | 동일 원인 추정 — library dispatch 경로 변화 |

**조사 방향**: `_resolve_alias_from_expr`의 `IndexAccessContext`/`FunctionCallContext` 추가가 기존 SafeMath dispatch를 방해하는지 확인. 이전에는 alias=None → `uint256` fallback → SafeMath 매칭이었는데, 새 코드가 잘못된 alias를 반환하거나, 평가 시 side effect를 일으킬 수 있음.

#### ERROR (5건) — 이전 VIOLATED → 현재 ERROR

| Case | 에러 | 추정 원인 |
|------|------|----------|
| BoostToken_indivisible | `_rOwned` not declared | pkl 변경으로 parent contract 로드 시 변수 선언 순서/컨텍스트 변화 |
| 47_H_02 | `member 'div'` not recognised | SafeMathUpgradeable using directive 미등록 (lib_name prefix 이슈는 수정했으나 아직 미해결) |
| 56_H_02 | NoneType getText | pkl 변경과 무관한 파싱 이슈 가능성 |
| 5_H_12 | `iERC20` interface empty | interface pkl 로드 시 함수 목록 누락 |
| 78_H_02 | `is_bottom` None | exit_env 전파 관련 — pkl 변경 영향 또는 이번 세션의 다른 변경 영향 |

**조사 방향**:
1. pkl wrapper unwrap이 누락된 곳이 더 있는지 전체 `pickle.load` 재확인 (완료 — 추가 발견 없음)
2. `_resolve_alias_from_expr` 변경을 일시 되돌려서 regression 유발 원인 격리
3. 각 케이스별 디버깅

---

### 3.5 Input JSON 작성 시 흔한 실수 패턴 (세션 1~8 누적)

과거 세션에서 반복적으로 발견된 input JSON 관련 이슈를 유형별로 정리.
새 케이스 생성 시, 또는 regression 디버깅 시 **코드 수정 전에 input부터 점검**할 것.

#### A. `@Debugging BEGIN` 위치
| 증상 | 원인 | 해결 |
|------|------|------|
| `_batch_targets`에 잘못된 fcfg 등록 | BEGIN이 함수 **헤더** 라인에 위치 | 함수 **본문 첫 줄** startLine으로 이동 |
| 예: HIT — line 54(헤더) → 55(본문) | | |

#### B. Mapping key 불일치 (symbolic address)
| 증상 | 원인 | 해결 |
|------|------|------|
| annotation 값이 함수 내부에서 참조 안 됨 | annotation key와 callee parameter name이 다름 | `symbolicAddress N`으로 두 key를 같은 주소로 연결 |
| 예: `_balances[to]` vs `_balances[account]` | | `@LocalVar to = symbolicAddress 10` 추가 |
| 예: `balances[1]` vs `balances[address(this)]` | mapping key가 리터럴 `1`이면 `address(this)` 평가값(`AddressSet({1})`)과 불일치 | `balances[address(this)]`로 수정 — TypeConversion evaluator가 동일 key 생성 |
| 예: Nokon — `balances[1]` → `balances[address(this)]` | | |

#### C. startLine 겹침 / 순서
| 증상 | 원인 | 해결 |
|------|------|------|
| debug annotation 덮어씀 / 누락 | 여러 annotation의 startLine이 동일 | **각 annotation은 고유 startLine 필수** (batch_mgr가 dict key로 사용) |
| `@Debugging END`가 작동 안 함 | END startLine이 BEGIN과 동일 | END를 마지막 annotation + 1 라인으로 설정 |
| 예: 세션6에서 19개 JSON `@Debugging END` 일괄 수정 | | |

#### D. `@Debugging BEGIN`/`END` 누락
| 증상 | 원인 | 해결 |
|------|------|------|
| intent를 annotation 개수만큼 반복 체크 | BEGIN/END 없이 flush | 반드시 BEGIN~END로 감쌀 것 |

#### E. symbolicAddress 미설정
| 증상 | 원인 | 해결 |
|------|------|------|
| mapping key가 문자열(`"to"`)로 저장 → 다른 함수의 key(`"account"`)와 불일치 | address 파라미터에 symbolicAddress 미설정 | `@LocalVar to = symbolicAddress N` 추가 |
| 예: 78_H_02 — `to = symbolicAddress 10` | | |
| `require(x != address(0))` 통과 안 됨 | address가 default(0) | `symbolicAddress N` (N≥1)으로 설정 |

#### F. Contraction .sol에 annotation 삽입
| 증상 | 원인 | 해결 |
|------|------|------|
| soltotestjson이 라인 갭 생성 → CFG 빌드 실패 | .sol에 annotation 섞임 | annotation은 **JSON에서만** 추가, .sol은 순수 코드만 |

#### G. JSON 레코드 순서 위반
| 증상 | 원인 | 해결 |
|------|------|------|
| intent 미인식 / debug 값 미적용 | 순서 틀림 | 반드시: Code → Intent → BEGIN → Debug → END |

#### H. Contraction single-line if 미분리
| 증상 | 원인 | 해결 |
|------|------|------|
| 한 record에 if + body가 합쳐짐 → CFG 구조 오류 | `if (...) return x;` 형태가 분리 안 됨 | `if (...) {\n    return x;\n}` 형태로 contraction .sol 수정 후 soltotestjson 재생성 |
| 예: BoostToken_indivisible L93 `if (...) return (_rTotal, _tTotal);` | | |

#### I. Dependencies/main.py pkl 생성 시 분석 순서
| 증상 | 원인 | 해결 |
|------|------|------|
| 부모 pkl의 `using_libraries`가 비어있음 → 자식에서 `.div()`, `.mul()` 등 library 함수 미인식 | `contracts/` 서브폴더 내 library(.sol)가 contract보다 늦게 분석되거나, "contract" 모드에서 분석된 library가 `_global_library_cfgs`에 누적 안 됨 | **같은 서브폴더 내 분석 순서**: library → parent contract → child contract 순으로 분석. library 결과를 `_global_library_cfgs`에 누적해야 using directive가 해석됨 |
| 예: `contracts/47/` — SafeMathUpgradeable(library)이 ERC20Upgradeable(contract)보다 알파벳상 뒤라서 using 등록 실패 → `con_47_ERC20Upgradeable.pkl`의 `using_libraries = {}` | | Dependencies/main.py 수정 필요 |

---

### 세션 9 (2026-04-07) 변경사항

#### 해결된 regression (7건 중 6건)
| Case | 원인 | 해결 방법 |
|------|------|----------|
| Nokon | mapping key `balances[1]` → `balances[address(this)]` 불일치 | input JSON 수정 (패턴 B) |
| BoostToken_indivisible | single-line if 미분리 + BEGIN/LocalVar startLine 겹침 | contraction .sol 수정 + JSON 재생성 (패턴 H, C) |
| 47_H_02 | ERC20Upgradeable pkl의 `using_libraries` 비어있음 | Dependencies/main.py Phase 3 분석 순서 수정 (library → parent → child) + pkl 재생성 |
| 78_H_02 | 동일 원인 (pkl 분석 순서) | pkl 재생성으로 해결 |
| 58_H_02 | `_lpPriceHighWaterMarks[0]`≠`[1]` → loop join 구간 확대 | annotation 값 동일하게 수정 (1e18) |
| 56_H_02 | `entry`/`exit` 소문자 → grammar는 `Entry`/`Exit` + `totalCredit` → `_self.totalCredit` | input JSON 수정 |

#### 미해결 (1건)
| Case | 증상 | 분석 결과 |
|------|------|----------|
| 101_H_01 | WARNING (이전 VIOLATED) | 2가지 문제 중첩: **(1)** overload resolution이 `base_type` 무시하고 전체 library 검색 → 수정 완료 (`find_library_function`에 `n_args` 전달) **(2)** debug interpretation에서 intent 재체크 미실행 — static analysis 시점에서만 체크됨 (원인 미확인) |

#### 101_H_01 디버깅 상세

**문제 1: Library overload resolution (수정 완료)**
- `find_library_function(base_type, func_name)` → 첫 번째 overload 반환 (3-param)
- 인자 수 불일치 → fallback에서 **모든 type의 모든 library** 검색 → 엉뚱한 함수 매칭
- **수정**: `find_library_function`에 `n_args` 파라미터 추가, fallback 제거 → `base_type` 스코프 내에서 직접 overload 해소
- 파일: `Utils/CFG.py` (ContractCFG, LibraryCFG 양쪽), `Evaluation.py:1886`

**문제 2: Debug interpretation에서 intent 재체크 미실행 (미해결)**
- Intent가 `VarDecl_45` 노드에 등록됨
- Static analysis에서 L45 처리 시 intent 체크 → WARNING (TOP 값)
- Debug interpretation (ANALYSIS 섹션)에서 intent 재체크가 안 됨
- `interpret_function_cfg_for_debug` → `_process_node_intents` 경로 확인 필요
- 또한 debug에서도 `_totalLiquidityWithdrawable`가 TOP — SafeMath.sub 반환값이 debug context에서도 TOP

**문제 2 추가 조사 필요사항:**
- `_process_node_intents`가 debug interpretation에서 호출되는지
- debug context에서 SafeMath.sub 인자가 TOP인 이유 (caller_env에서 `_borrowedTokens` 전달 확인)
- 이전 세션에서 101_H_01이 VIOLATED였을 때의 차이점

#### 42_H_01 → not_detectable 변경
- `engine.cssr().update()`가 non-view interface function → IReturn 불가 → return TOP
- TOP이 `price` 변수로 전파 → `maxMinted` = TOP → `_amount` widening → intent WARNING
- dataset.csv: `annotated` → `not_detectable,interface-call-return-top`

#### 5_H_12 해결: iERC20 pkl Windows 대소문자 충돌
- `ifc_iERC20.pkl`과 `ifc_IERC20.pkl`이 Windows에서 동일 파일
- **해결**: `Dependencies/interfaces/5/iERC20.sol` 서브폴더 → `ifc_5_iERC20.pkl` 생성
- `main.py load_dependencies()`: ifc_ prefix에서 숫자 서브폴더 제거 로직 추가

#### 코드 변경 요약
| 파일 | 변경 |
|------|------|
| `Utils/CFG.py` | `find_library_function`에 `n_args` 파라미터 추가 (ContractCFG + LibraryCFG) |
| `Evaluation.py:1886` | overload fallback 제거 → `find_library_function(base_type, func_name, n_args=n_args)` 직접 호출 |
| `Dependencies/main.py` | Phase 1 `glob`→`rglob`, interface 서브폴더 prefix 지원, Phase 3 수동 분석 순서, 에러 출력 |
| `main.py` | ifc_ prefix 숫자 제거, `[TIMING]` 출력 추가 |
| `evaluation/RQ1/run_all.py` | 신규 — 전체 케이스 실행 + CSV 출력 스크립트 |
| `evaluation/RQ1/runner.py` | 삭제 (구버전) |
| `dataset.csv` | 42_H_01: annotated → not_detectable |

#### Input JSON 수정
| 파일 | 변경 |
|------|------|
| `Nokon_input.json` | `balances[1]` → `balances[address(this)]` |
| `BoostToken_input.json` (indivisible) | contraction single-line if 분리 + JSON 재생성 + annotation 라인 정정 |
| `web3bugs_56_H_02.json` | `entry/exit` → `Entry/Exit`, `totalCredit` → `_self.totalCredit` |
| `web3bugs_58_H_02.json` | `_lpPriceHighWaterMarks` 값 통일 (1e18) |
| `web3bugs_101_H_01.json` | annotation startLine 겹침 해소 (BEGIN=43, 나머지 44~49) |

---

### 4. 다음 세션 작업 우선순위

#### P0: 101_H_01 해결 → ✅ 완료 (session 10)
1. ~~debug interpretation에서 intent 재체크가 안 되는 원인 확인~~
2. ~~SafeMath.sub가 debug context에서 TOP 반환하는 원인 확인~~

#### P1: 회귀 테스트 → ✅ 완료 (20/20 VIOLATED)
- `run_all.py` 실행하여 20개 전체 VIOLATED 확인 — 87.05s total, avg 4.35s

---

## Session 10 (2026-04-08): 101_H_01 근본 원인 해결 — `using` directive 상속 우선순위

### 핵심 결과
**20/20 VIOLATED 달성.** 9세션에서 "debug context에서 SafeMath.sub가 TOP 반환"으로 보였던 문제가 실제로는 **`using` directive 상속 순서**가 원인이었음.

### 10.1 진단 경로

#### 사용자 관찰
- debug annotation 처리 후 `_borrowedTokens.sub(...)` 분석 시 call stack:
  `_interpret_var_decl → evaluate_expression → evaluate_function_call_context → evaluate_library_function_call_context → interpret_function_cfg → _run_worklist`
- **worklist 첫 노드가 `return` 문**이었음 (`src_line=157`)
- SafeMath.sub이 왜 그런 CFG 구조를 갖는지 의문

#### 중간 탐색: networkx 버전 충돌 (적색 청어지만 기록)
진짜 원인은 아니지만 **독립적으로 해결되어야 할 별개 이슈** 발견:

| 환경 | networkx 버전 |
|------|--------------|
| Global Python 3.10 | **2.5.1** (`falcon-analyzer`가 downgrade) |
| IntentChecker `.venv` | **3.4.2** |

- `Dependencies/objectfile/` pkl들은 venv의 3.4.2로 생성됨
- global python으로 로드 시 `'DiGraph' object has no attribute '_adj'` in `NodeView.__setstate__` 실패
- `main.py load_dependencies()`의 `except Exception: pass`가 조용히 삼킴
- 결과: SafeMath, SafeMathUpgradeable 등 11개 lib + 23개 contract pkl이 silently 로딩 실패

**수칙**: main.py/run_all.py는 반드시 **`.venv/Scripts/python.exe`** 로 실행. bare `python` 금지.

**원인**: 사용자가 numscout/gptscan을 설치하면서 개별 venv로 격리했지만, `falcon-analyzer`가 global site-packages에 들어가 networkx를 downgrade.

이 문제는 20/20 결과에는 영향 없음 (venv로 돌리면 pkl 모두 정상 로드). 하지만 **향후 global python 실수 사용 시 silent 실패 위험**이 있음.

#### 진짜 원인: `using` directive 상속 순서
`Evaluation.py:1888` 직전에 임시 trace 추가:
```python
print(f"[TEMP] ccfg.using_libraries[{base_type}]={lib_names}")
```

실행 결과:
```
LenderPool.using_libraries[uint256] = ['SafeMathUpgradeable', 'SafeMath']
```

contraction에는 `using SafeMath for uint256;` 하나뿐인데 **`SafeMathUpgradeable`이 먼저** 등록되어 있었음.

### 10.2 근본 원인

#### 상속 전파 경로
`Analyzer/ContractAnalyzer.py:_inherit_using_libraries` (line 546):
```python
def _inherit_using_libraries(self, cfg):
    for parent_cfg in cfg.parent_cfgs.values():
        for target_type, libs in parent_cfg.using_libraries.items():
            for lib in (libs if isinstance(libs, list) else [libs]):
                cfg.add_using_library(lib, target_type)
```

LenderPool의 부모 `ERC1155Upgradeable` (`Dependencies/contracts/ERC1155Upgradeable.sol:4`):
```solidity
library SafeMathUpgradeable { ... }  // 파일 외부에 정의
contract ERC1155Upgradeable {
    using SafeMathUpgradeable for uint256;  // ← 여기
    ...
}
```

**파싱 순서**:
1. `contract LenderPool is ERC1155Upgradeable, ...` 파싱 → `make_contract_cfg` → `_inherit_using_libraries` → **부모의 `SafeMathUpgradeable`이 먼저 리스트에 append**
2. `using SafeMath for uint256;` 파싱 → `process_using_directive` → **SafeMath가 뒤에 append**
3. 결과: `using_libraries['uint256'] = [SafeMathUpgradeable, SafeMath]`

#### 왜 CFG 첫 노드가 return이었나
`Dependencies/contracts/47/SafeMathUpgradeable.sol:18-20`:
```solidity
function sub(uint256 a, uint256 b) internal pure returns (uint256) {
    return sub(a, b, "SafeMath: subtraction overflow");  // ← 본체가 return 한 줄
}
```

이 2-arg `sub`는 본체가 **`return sub(a, b, errorMsg)` 한 줄짜리 wrapper**. 그래서:
- CFG: entry → `return(3-arg sub)` → exit
- worklist 첫 노드가 정말로 return 문 (bug 아님, wrapper 함수의 자연스러운 CFG)
- 내부에서 3-arg overload 해소가 제대로 안 되거나 중첩된 library call에서 TOP이 발생 → 그대로 return
- `_totalLiquidityWithdrawable = [0, MAX]` (TOP) → `_principalWithdrawable` = TOP → intent WARNING

#### Solidity 의미론 검토
Solidity spec상 **contract-level `using` directive는 상속되지 않습니다**. file-level directive만 같은 파일 내 모든 contract에 적용. `_inherit_using_libraries`는 엄밀히 말하면 잘못된 설계지만, 기존 19개 케이스가 의존하고 있을 수 있어 **전면 제거는 위험**.

### 10.3 수정

#### 최소 변경 원칙: 자식의 명시적 선언에 우선권 부여
자식 contract가 **스스로 선언한** `using` directive는 부모로부터 상속된 것보다 **앞에** 배치.

**`Utils/CFG.py`** — `ContractCFG.add_using_library`, `LibraryCFG.add_using_library`:
```python
def add_using_library(self, library_cfg, target_type=None, prepend: bool = False):
    if target_type is None:
        if library_cfg not in self.using_all_libraries:
            if prepend:
                self.using_all_libraries.insert(0, library_cfg)
            else:
                self.using_all_libraries.append(library_cfg)
    else:
        if target_type not in self.using_libraries:
            self.using_libraries[target_type] = []
        if library_cfg not in self.using_libraries[target_type]:
            if prepend:
                self.using_libraries[target_type].insert(0, library_cfg)
            else:
                self.using_libraries[target_type].append(library_cfg)
```

중복 방지(`not in` 체크)도 함께 추가 — 기존 ContractCFG는 중복 체크 있었지만 LibraryCFG는 없었음.

**`Analyzer/ContractAnalyzer.py:675`** — `process_using_directive`:
```python
# 자식 contract가 명시적으로 선언한 using은 부모로부터 상속된 것보다 우선되어야 하므로
# 리스트 앞쪽(우선순위 높음)에 삽입
contract_cfg.add_using_library(library_cfg, target_type, prepend=True)
```

`_inherit_using_libraries`는 그대로 (기본 append). 자식의 명시적 선언은 prepend로 앞에 들어가므로, 자식이 선언한 것이 **항상 우선**.

### 10.4 결과

```
[20/20] web3bugs_101_H_01 ... VIOLATED (1.3177s)
==================================================
Results: 20 VIOLATED / 20 cases
Time:    total=87.05s  avg=4.35s  min=0.49s  max=15.76s
```

101_H_01 분석 결과:
```
L 50 | _borrowedTokens            = [99000, 99000]    # debug 값
L 51 | _totalLiquidityWithdrawable = [99000, 99000]   # = 99000 - 0
L 52 | _principalWithdrawable      = [100000, 100000] # 99000*100000/99000
L 53 | return _principalWithdrawable

[INTENT VIOLATION] Line 45: _principalWithdrawable <= _totalLiquidityWithdrawable
  LHS = [100000, 100000]
  RHS = [99000, 99000]
  Risk: Type 3 (both-side)  risk=10.0
```

100000 > 99000이므로 violation — 버그가 정확히 탐지됨. 총 분석 시간도 9세션 117s → 10세션 87s로 단축 (SafeMathUpgradeable wrapper 우회).

### 10.5 Input JSON mistake patterns v2 — 항목 J 추가

#### J. `using` directive 상속에 의한 overload 충돌
- **증상**: static analysis에서 동일 타입(`uint256` 등)에 대한 library 함수 호출이 기대와 다른 CFG로 해석됨. 결과가 TOP에 가깝게 나오거나 interval이 넓게 발산.
- **원인**: 자식 contract가 parent contract의 `using X for T` directive를 상속 + 리스트 순서상 parent 쪽이 먼저 등록. 특히 parent가 wrapper 함수(`return func(a,b,msg)`)만 가진 버전일 때 CFG 첫 노드가 return이 되어 어색해 보임.
- **해결**: 본 세션에서 `process_using_directive`가 `prepend=True`로 자식의 명시적 선언을 앞에 배치하도록 수정. **코드 수정으로 구조적으로 해결됨** — 향후 input JSON에서는 신경 쓸 필요 없음.
- **진단법**: 의심 시 `Evaluation.py:1888` 근처에 `print(ccfg.using_libraries)` 임시 trace 추가.

### 10.6 코드 변경 요약

| 파일 | 변경 |
|------|------|
| `Utils/CFG.py` | `ContractCFG.add_using_library` / `LibraryCFG.add_using_library`에 `prepend` 파라미터 추가, 중복 방지 |
| `Analyzer/ContractAnalyzer.py:675` | `process_using_directive`가 `prepend=True`로 호출 |

### 10.7 환경 주의사항 (신규 규칙)

**프로젝트 venv python 사용 필수**:
```bash
# 옳음
.venv/Scripts/python.exe evaluation/RQ1/run_all.py
.venv/Scripts/python.exe main.py <case>.json

# 위험 — global python 3.10은 networkx 2.5.1 (falcon-analyzer가 downgrade)
python evaluation/RQ1/run_all.py
```

`main.py load_dependencies()`의 `except Exception: pass`가 pkl 로딩 실패를 silently 삼키므로, 잘못된 python으로 돌리면 library CFG가 통째로 빠진 채 분석이 돌아감. 에러 은폐를 제거할지 여부는 추후 논의.

---

### 5. 아키텍처 변경 기록: pkl wrapper 포맷

#### 이전 포맷
```python
pickle.dump(cfg, f)  # LibraryCFG/ContractCFG/InterfaceCFG 직접
```

#### 새 포맷
```python
pickle.dump({
    "cfg": cfg,
    "file_level_structs": dict(sa.file_level_structs),
    "type_aliases": dict(sa.type_aliases)
}, f)
```

#### Backward compatibility
```python
raw = pickle.load(f)
if isinstance(raw, dict) and "cfg" in raw:
    cfg = raw["cfg"]
    file_level_structs = raw.get("file_level_structs", {})
    type_aliases = raw.get("type_aliases", {})
else:
    cfg = raw  # 구 포맷
```

#### pkl 로드하는 모든 위치 (총 7곳)
| 파일 | 라인 | 용도 | unwrap |
|------|------|------|:---:|
| `main.py` | 33, 48, 66 | `load_dependencies()` ifc/lib/con | ✅ |
| `Evaluation.py` | 115, 222 | interface return type 동적 조회 | ✅ |
| `ContractAnalyzer.py` | 665 | `process_using_directive` pkl fallback | ✅ |
| `ContractAnalyzer.py` | 715 | `resolve_library_struct` pkl fallback | ✅ |

#### 재생성 필요
```bash
python Dependencies/main.py  # 전체 pkl 재생성
```
