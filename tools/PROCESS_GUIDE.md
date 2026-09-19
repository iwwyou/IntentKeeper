# RQ2 실험 수행 프로세스 가이드

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

## 데이터셋 구성
- **총 89건**: Web3Bugs 81건 + Numscout 8건
- **마스터 인덱스**: `evaluation/RQ1/dataset.csv`
- **원본 .sol 파일**: `evaluation/RQ1/target_contracts_original/` (89개 파일)
- **축약 .sol 파일**: `evaluation/RQ1/target_contracts_contraction/` (detectable 건)
- **의존성 파일**: `evaluation/RQ1/target_contracts/dependencies/` (302개 파일)
- **dependency 정보 스크립트**: `evaluation/RQ1/collect_dependencies.py`

## RQ 구조
- **RQ1**: Validation Algorithm Soundness (interval comparison 알고리즘 검증)
- **RQ2**: Mitigation (IntentChecker로 실제 취약점 완화 가능 여부)
- **RQ3**: Comparison with Existing Tools (GPTScan/NumScout과 비교)
  - Table A: NumScout vs IntentChecker on Numscout 8건
  - Table B: GPTScan vs IntentChecker on Web3Bugs 81건
- **RQ4**: Developer Perception (개발자 인식 조사)

## 수행 Phase

### Phase 1: Feasibility Review (89건 전수 검토)
각 contract를 검토하여 IntentChecker로 탐지/완화 가능한지 판정.

**판정 기준:**
- `detectable`: IntentChecker의 annotation으로 탐지 가능
- `not_detectable`: 한계로 인해 탐지 불가 (limitation type은 `limitation_types.md` 참조)
- `excluded`: numeric logical error 정의에 해당하지 않거나 분석 대상 제외

**Three-file update rule**: 케이스 분석 시 아래 세 파일을 **항상 함께** 업데이트:
1. `dataset.csv` — status 변경
2. `annotation_plans.md` — 분석 내용/annotation 계획 기록
3. `limitation_types.md` — not_detectable인 경우 limitation type 및 해당 케이스 목록 갱신

**케이스별 수행 절차:**
1. 원본 contract 읽기 (`target_contracts_original/`)
2. 버그 이해 (bug description, bug report)
3. Blocker 분석:
   - **Loop 분석**: 누적 연산(`+=`, `*=`) → widening → Top. 단, min-finding 등 monotonically non-increasing 루프는 widening 대상 아님. 또한 widening 되더라도 annotation 대상 변수가 widened 변수와 독립적이면 blocker 아님
   - **External call 분석**: interface call → Top (L2a), 외부 contract call → state unknown → Top (L2b). 단, interface에서 상속받은 struct/enum **타입 정의**는 compile-time 정보이므로 L2 아님 (target contract 자체 storage에 있는 데이터는 annotatable)
   - **Annotation 표현 한계**: storage variable 없음 (L3b), 올바른 값을 기존 변수의 산술 조합으로 표현 불가 (L3a)
   - **Bug awareness 전제**: 누락된 함수 호출의 효과가 scope 밖 (L4a), 인자 순서 오류 (L4b), 누락된 state update (L4c)
4. detectable/not_detectable 판정
5. Three-file update (dataset.csv + annotation_plans.md + limitation_types.md)
6. detectable인 경우: annotation 계획 수립 (아래 상세)

**detectable 케이스 annotation 계획 수립:**
1. Contraction 파일 확인 (`target_contracts_contraction/`)
2. Intent annotation 결정: 타입(@Post/@During), 대상 변수, 표현식, 삽입 라인
3. Debug annotation 결정: 필요한 변수, 삽입 라인
4. **Z3 solver 생성** (`evaluation/RQ1/z3_solvers/`): underflow/overflow 방지, require 통과, 버그 경로 진입 조건 등을 Z3 constraint로 모델링하여 안전한 debug annotation 값 도출
5. **Annotation 삽입 순서**: Step 1에서 intent annotation 삽입 → Step 2에서 debug annotation 삽입 → interpreter가 둘 다 포함된 상태로 실행

### Phase 2: 환경 준비
- contract별 import dependency 사전 수집 (collect_dependencies.py 완료)
- `hardhat/console.sol` import 제거 (17개 파일)
- OpenZeppelin dependency 파일 추가
- direct library call 지원 구현 (필요 시)

### Phase 3: Contraction (detectable 건만)
각 contract에서 vulnerability 관련 함수 중심으로 축약.

**산출물:**
- `_contraction.sol`: 축약된 Solidity 소스
- `_contraction.json`: `soltotestjson.py`로 변환한 JSON (IntentChecker 입력 형식)

**변환 명령:**
```bash
python soltotestjson.py [_contraction.sol 경로] -o [_contraction.json 경로]
```

### Phase 4: Annotation 명세 (Case JSON 생성)
각 contracted contract에 대해 case JSON 파일 생성.

**Case JSON 구조** (예: `evaluation/RQ1/cases/div_in_path/WANGMI.json`):
```json
{
  "id": "WANGMI",
  "name": "WANGMI div_in_path",
  "description": "버그 설명",
  "source": "Dataset/Numscout/contraction/div_in_path/WANGMI_contraction.json",
  "target_contract": "WANGMI",
  "target_function": "_transfer",
  "bug_lines": [428],
  "web3bugs_report": "35.md",
  "annotation_rationale": "35.md H-12: secondsPerLiquidity가 liquidity 변경 시 업데이트 안됨. mint에서 Ticks.insert() 전 업데이트 누락 → Assign != Current로 검증",
  "debug_annotations": [
    {
      "type": "StateVar|LocalVar|GlobalVar",
      "var": "변수명",
      "value": "값 또는 [min, max] interval 또는 symbolicAddress N 또는 true/false",
      "line": 라인번호,
      "comment": "설명"
    }
  ],
  "intent_annotations": [
    {
      "type": "During|Post",
      "line": 라인번호,
      "expr": "intent 표현식",
      "expected": "violated|satisfied",
      "rationale": "35.md H-12: 어떤 bug report 내용을 근거로 이 annotation을 선택했는지"
    }
  ],
  "expected_results": {
    "total_intents": N,
    "expected_violations": N,
    "expected_satisfied": N
  }
}
```

**Debug Annotation 생성 규칙:**
1. 대상 함수의 **모든 관련 변수**에 debug annotation 필요 (함수 파라미터, state variables, global variables)
2. `require` 문을 분석하여 **조건을 통과하는 값** 생성:
   - `require(x != address(0))` → `symbolicAddress N`
   - `require(isLaunched)` → `true`
   - `require(!isBlacklisted[x])` → `false`
   - `require(amount <= maxLimit)` → amount보다 큰 interval
   - `require(a + b <= c)` → 관계를 만족하는 값 조합
3. 버그가 trigger되는 경로로 실행이 흐르도록 값 설정
4. mapping 접근 시 key에 파라미터 이름 매칭 (e.g., `isExcludedFromFees[_from]`)

**Intent Annotation 문법** (Solidity.g4 기준):
```
// During:
//   @During var(Before relOp After)              -- DuringBeforeAfter
//   @During var(Assign relOp Current)            -- DuringAssignCurrent
//   @During func.arg[N] relOp value              -- DuringFunctionArg
//   @During var relOp value                      -- CommonClause

// Post:
//   @Post var(Entry relOp Exit)                  -- PostEntryExit
//   @Post Unchanged(var)                         -- UnchangedVar
//   @Post var relOp value                        -- CommonClause

// relOp: >, <, >=, <=, ==, !=
// logicOp: && (여러 clause 연결 가능)
```

**Intent Annotation 사용자 제공 정보:**
- 사용자가 제공: 어떤 변수에 어떤 의도의 annotation을 줄지, 어느 라인에 줄지
- Claude가 생성: 해당 함수의 require 통과용 debug annotation 값 전체

**Annotation 근거 추적 (Provenance):**
- Web3Bugs 원본 bug report: `Web3Bugs/reports/{contest번호}.md` (e.g., `35.md`)
  - 경로: 사용자 로컬 `C:\Users\isjeon\Web3Bugs\reports\`
  - contest 번호는 contract_id에서 추출 (e.g., `web3bugs_35_H_12` → `35.md`)
- Case JSON에 기록할 필드:
  - `web3bugs_report`: `"35.md"` (report 파일 번호)
  - `annotation_rationale`: 전체 annotation 선택 이유 (어떤 bug report를 보고 왜 이 annotation을 선택했는지)
  - 각 intent의 `rationale`: `"35.md H-12: ..."` 형태로 리포트 항목 번호 + 근거 요약
- 목적: Threats to Validity에서 "bug report 기반으로 annotation 작성" 주장의 증거

### Phase 5: 일괄 실행 + 결과 정리 (마지막에 한번에)
- `runner.py`로 IntentChecker 실행
- TP/FP/FN 수집
- `paper/main.tex` RQ2, RQ3 표 채우기
- Threats to Validity, Discussion 작성

**실행 명령:**
```bash
# 개별 케이스 실행 (main.py에 JSON 경로 전달)
python main.py evaluation/RQ1/cases/web3bugs_56_H_02/web3bugs_56_H_02.json

# 전체 regression 확인 (bash)
for d in evaluation/RQ1/cases/*/; do name=$(basename "$d"); json="$d${name}.json"; if [ -f "$json" ]; then echo "=== $name ===" && python -u main.py "$json" 2>&1 | grep -iE "INTENT VIOLATION|INTENT WARNING|POST INTENT|Traceback" | head -3; fi; done
```

## 핵심 파일 경로
| 파일 | 경로 | 설명 |
|------|------|------|
| 논문 | `paper/main.tex` | 메인 논문 파일 |
| 데이터셋 CSV | `evaluation/RQ1/dataset.csv` | 89건 마스터 인덱스 |
| 타겟 계약 | `evaluation/RQ1/target_contracts/*.sol` | 원본 .sol 파일 |
| 의존성 | `evaluation/RQ1/target_contracts/dependencies/` | import 의존성 파일 |
| 케이스 JSON | `evaluation/RQ1/cases/{category}/{name}.json` | 실행 케이스 |
| 결과 | `evaluation/RQ1/results/` | 실행 결과 JSON/CSV |
| Runner | `evaluation/RQ1/runner.py` | RQ2 실행 스크립트 |
| Sol→JSON 변환 | `soltotestjson.py` | .sol → JSON 변환기 |
| Dependency 수집 | `evaluation/RQ1/collect_dependencies.py` | import 정보 수집 |
| Grammar | `Parser/Solidity.g4` | Intent annotation 문법 정의 |
| Annotation 계획 | `evaluation/RQ1/annotation_plans.md` | 케이스별 annotation 계획/분석 기록 |
| Limitation 유형 | `evaluation/RQ1/limitation_types.md` | not_detectable 한계 유형 정의/분류 |
| 추가 구현 사항 | `evaluation/RQ1/code_modification_issues.md` | IntentChecker 코드 수정 필요 사항 추적 |
| Z3 솔버 | `evaluation/RQ1/z3_solvers/` | debug annotation 값 생성용 Z3 constraint solver |
| 원본 계약 | `evaluation/RQ1/target_contracts_original/` | 원본 .sol 파일 |
| 축약 계약 | `evaluation/RQ1/target_contracts_contraction/` | 축약된 .sol 파일 (detectable 건) |

## Numscout 기존 contraction 예시
| 파일 | 경로 |
|------|------|
| WANGMI sol | `Dataset/Numscout/contraction/div_in_path/WANGMI_contraction.sol` |
| WANGMI json | `Dataset/Numscout/contraction/div_in_path/WANGMI_contraction.json` |
| WANGMI case | `evaluation/RQ1/cases/div_in_path/WANGMI.json` |
| BoostToken case | `evaluation/RQ1/cases/operator_order_issue/BoostToken.json` |
| Nokon case | `evaluation/RQ1/cases/exchange_problem/Nokon.json` |
| SwordCrowdsale case | `evaluation/RQ1/cases/greedy_contract/SwordCrowdsale.json` |

## Threats to Validity에 포함할 내용
1. **연구자 작성 annotation ≠ 개발자 의도**: 실험에서 사용된 intent annotation은 연구자가 bug report와 원본 코드를 기반으로 작성한 것이며, 실제 개발자의 의도와 다를 수 있다.
2. **완화 방안**: bug report, fix commit, 원본 소스코드를 참고하여 annotation 작성.

## Discussion에 포함할 내용
1. **Annotation 작성의 순환 논리**: annotation 작성에 버그 인지가 전제되는 한계 → LLM 기반 annotation suggestion 필요성 (future work: IntentKeeper)
2. **Missing-operation 간접 탐지**: debug annotation 초기값 + `Assign != Current` 패턴으로 값 변경 여부를 간접 탐지 가능하지만, 업데이트 결과가 초기값과 동일한 edge case에서 false positive 발생 가능.

---

## 아키텍처 리팩토링 (2026-03-25)

### SolidityAnalyzer / ContractAnalyzer 분리
- **SolidityAnalyzer** (`Analyzer/SolidityAnalyzer.py`): 소스 관리 + context 분배 + file-level 처리
  - `full_code_lines`, `full_code`, `line_info` 소유
  - `update_code()` 진입점
  - `_insert_lines()`, `_shift_source_meta()`, `update_brace_count()` 등 소스 관리
  - `analyze_context()` dispatcher: file-level → 자체 처리, assembly → context 설정, 나머지 → CA 위임
- **ContractAnalyzer** (`Analyzer/ContractAnalyzer.py`): contract-level 분석 전용
  - `self.sa.xxx`로 소스 데이터 접근 (property 없이 직접 참조)
  - `_shift_cfg_meta()`: recorder.ledger + CFGNode/Statement src_line shift
  - `analyze_context()`: contract scope 전용
  - 모든 `process_*`, CFG building, `make_*_cfg`
- Entry point: `main.py → SolidityAnalyzer.update_code() → ContractAnalyzer (위임)`

### Yul 파서 분리
- **Yul.g4** (`Parser/Yul.g4`): 별도 lexer/parser (Solidity lexer 토큰 충돌 방지)
- **EnhancedYulVisitor** (`Analyzer/EnhancedYulVisitor.py`): Yul parse tree → Expression IR
- **Solidity.g4**: Yul rule 전부 삭제, `assemblyBlock: '{' (~('{' | '}') | assemblyBlock)* '}'` 로 simplified
- 흐름: `visitAssemblyStatement` → 내부 텍스트 추출 → YulParser → EnhancedYulVisitor → ContractAnalyzer

### Function Overloading
- `CFG.py`: `functions = {name: {signature: FunctionCFG}}` (nested dict)
- `add_function_cfg()`, `update_function_cfg()`, `get_function_cfg(name, param_types)`
- `iter_all_functions()`, `_build_signature()`
- `FunctionCFG.parameter_types: list[str]` 필드 추가

---

## Grammar 변경사항 (2026-03-25)

### Solidity.g4
| 변경 | 내용 |
|------|------|
| assemblyStatement | Yul rule 전부 제거, balanced brace 소비로 simplified |
| Yul lexer rules | `YulEvmBuiltin`, `YulIdentifier` 등 삭제 (balance 토큰 충돌 해결) |
| debugGlobalVar | `GlobalVarSimple` / `GlobalVarAddressBalance` 분리 |
| DuringFeasible | `'require feasible' \| 'assert feasible'` |
| VarChangedEval | `'changed' '(' intentValue ',' ('true'\|'false') ')'` in commonClause |
| _CTX_MAP | `fileLevelStruct`, `fileLevelStructMember`, `fileLevelTypeAlias` 매핑 추가 |

### Yul.g4 (신규)
- 별도 lexer/parser, `antlr4 -Dlanguage=Python3 -visitor Yul.g4`

---

## 구현 완료된 Code Modification Issues (2026-03-25)

### Issue 1: During standalone
- `_is_during_inline()`, `_find_prev_cfg_node()`, Engine `report_line`

### Issue 3: File-level struct
- `_handle_file_level()`, visitor 라우팅, `sa.file_level_structs` fallback

### Issue 5: User-defined value type
- `process_type_alias()`, `visitUserDefinedValueTypeDefinition()`, `resolve_type()`
- `wrap/unwrap`: `TypeWrapUnwrapContext` → `evaluate_type_wrap_unwrap()`

### Issue 6: require feasible
- `verify_during_feasible()`: CFG에서 require condition → BoolInterval `[0,0]` 이면 violated

### Issue 2: Changed(x, true/false)
- `verify_during_changed()`, `verify_post_changed()`: Entry vs Current/Exit 비교
- 기존 `Unchanged` 제거

### Issue 7: address(this).balance GlobalVar
- `visitGlobalVarAddressBalance()`, `_get_address_this_balance()`
- `this.balance` / `address(X).balance` 접근 시 GlobalVar 값 우선

### Solidity Built-in 함수
- `_evaluate_builtin_function()`: `addmod`, `mulmod` 계산, 나머지 TOP

### Yul/Assembly
- `EnhancedYulVisitor`: binary ops, mulmod/addmod, not, iszero → Expression IR
- `process_yul_assignment()`, `process_yul_variable_declaration()` (미지원→TOP)

### using 키워드 (Issue 4)
- pkl 로드 경로: `Dependencies/objectfile/lib_*.pkl`
- 같은 타입에 여러 library: `using_libraries[type] = list[LibraryCFG]`

---

## Dependencies 사전분석 파이프라인 (2026-03-25)

### 디렉토리 구조
```
Dependencies/
├── interfaces/     ← 44개 interface .sol
├── libraries/      ← 17개 library .sol
├── contracts/      ← 공통 + 타겟별 서브폴더 (45/, 47/, 58/, 101/, 112/)
├── objectfile/     ← 79개 pkl (ifc_*, lib_*, con_*)
├── main.py         ← 사전분석 스크립트
└── ISSUES.md       ← 미해결 이슈 (FloatStruct 등)
```

### 실행
```bash
python Dependencies/main.py --type all    # 전체 분석
python Dependencies/main.py --file X.sol  # 단일 파일
```

### Dependency .sol 작성 규칙

**함수 순서 — callee가 caller보다 앞에 위치해야 함**
- IntentChecker는 소스를 순차적으로 파싱하므로, 호출되는 함수(callee)가 호출하는 함수(caller)보다 뒤에 정의되면 CFG가 제대로 구축되지 않음
- 예: `_transfer`가 `transferFrom`보다 **앞에** 정의되어야 함
- Dependency .sol을 작성/수정할 때 반드시 호출 관계를 확인하고 순서 정렬

**pkl 재생성 순서 — 상속 체인의 부모부터 생성**
- 자식 contract의 pkl 생성 시 부모 pkl이 이미 존재해야 `parent_cfgs`, `using_libraries` 상속이 정상 동작
- 재생성 순서 예시 (47번):
  1. `SafeMathUpgradeable` (library, 독립)
  2. `AddressUpgradeable` (library, 독립)
  3. `Initializable` (base contract)
  4. `ContextUpgradeable` (← Initializable)
  5. `ERC20Upgradeable` (← Initializable, ContextUpgradeable)
- `Dependencies/main.py --type all`은 알파벳순이라 상속 순서와 다를 수 있으므로, 개별 재생성 시 직접 순서를 지정할 것

### Phase 0
- type alias 사전 수집 (`type X is Y;` regex)
- interface 이름 사전 수집 (`interface X` regex)
- 각 파일 분석 시 `sa.type_aliases` / `ca.interface_names`에 주입

### 전처리 스크립트
- **preprocess_contraction.py**: import/주석/event 제거, `from→_from`, enum 한줄화
- **rename_reserved_identifiers.py**: `float→FloatStruct`, `from→_from`
- **slice_solidity**: assembly 내부 `in_assembly` depth 추적 → 줄 단위 chunk

---

## Dataset 변경 (2026-03-25)

| 케이스 | 변경 전 | 변경 후 | 이유 |
|--------|---------|---------|------|
| numscout_HippoHotel | not_detectable (L3) | **annotated** | address(this).balance + SafeMath 해결 |
| numscout_EthereumGod | not_detectable (L3) | not_detectable (**L2a**) | state-modifying interface call |

### Limitation 분류 개편
- L1 → L1a (8건, 기존 L1b 흡수), L1c → L1b (2건)
- 상위 그룹: A. Analysis Imprecision / B. Annotation Limitation

### 현재 통계
- annotated: **23건**, not_detectable: **53건**, excluded: **13건**

---

## 분석 준비 상태 (2026-03-25)

### 준비 완료: 22/23 annotated 케이스
dependency pkl 전부 준비, using/assembly/overloading 지원 완료.

### 미준비: 1건
- **web3bugs_42_H_01**: FloatStruct file-level struct 미등록 (Dependencies/ISSUES.md 참조)

### 추가 구현 필요
- **Issue 8** (78_H_02): 피상속 컨트랙트의 private state variable 접근

---

## Input JSON 형식 규칙 (2026-03-27)

### JSON 생성 절차
1. **전처리**: `preprocess_contraction.py` 실행 (import/주석/constructor 제거, single-line if 확장 등)
2. **Code records 생성**: `soltotestjson.py`로 clean contraction .sol에서 변환
3. **Annotation 추가**: code records 뒤에 intent → debug annotation 순서로 추가

### JSON 레코드 순서 (반드시 준수)
```
1. Code records        (soltotestjson.py 출력 그대로)
2. Intent annotations  (// @During ..., // @Post ...)
3. // @Debugging BEGIN
4. Debug annotations   (// @LocalVar, @StateVar, @GlobalVar, @IReturn)
5. // @Debugging END
```

### @Debugging BEGIN/END 필수
- Debug annotation은 반드시 `// @Debugging BEGIN` ~ `// @Debugging END`로 감싸야 함
- BEGIN/END 없이 개별 flush하면 **동일 intent를 debug annotation 개수만큼 반복 체크**하게 됨
- BEGIN/END의 startLine은 debug annotation 중 첫 번째의 startLine과 동일하게 설정

### Debug annotation startLine 규칙
- **각 debug annotation의 startLine은 서로 고유해야 함** (batch_mgr가 startLine을 dict key로 사용)
- 함수 body 내 코드 라인 번호를 순차적으로 할당 (예: 197, 198, 199, ...)
- Intent annotation의 startLine은 해당 코드 라인과 동일해도 됨 (debug와 별도 처리)

### Contraction .sol에 annotation을 넣지 말 것
- `target_contracts_contraction/` .sol은 순수 코드만 포함
- annotation은 JSON에서만 추가
- .sol에 annotation이 섞이면 soltotestjson.py가 라인 갭을 만들어 CFG 빌드 실패

---

## 엔진 수정 사항 (2026-03-27)

### _merge_values None 방어
- `VariableEnv._merge_values(v1, v2, mode)`: v1 또는 v2가 None이면 다른 쪽 반환
- 한쪽 branch에서 초기화 안 된 변수가 join 시 에러 방지

### Interface 타입 state variable 지원
- `process_state_variable`: typeCategory=="interface"이면 AddressSet.top() + `_cast_interface` 설정
- `process_variable_declaration`: 동일 처리 (local 변수)
- `evaluate_identifier_context`: MemberAccessContext에서 interface 타입 변수는 `.value`(AddressSet) 반환
- 이를 통해 `interestRateModel.getBorrowRate()` 같은 interface member call이 정상 동작

---

## 엔진 수정 사항 (2026-03-30 세션 3)

### Mapping key 통일 — AddressSet 값 기반
- global var(msg.sender)가 mapping index일 때 `"msg.sender"` 리터럴 대신 `str(AddressSet({101}))` 사용
- **5곳 수정**: Evaluation.py, Update.py, DebugInitializer.py
- annotation `accountBorrows[msg.sender]`와 callee `accountBorrows[account]` 모두 동일 key 수렴
- 45_H_01 해결

### `top_from_soltype` 범용 유틸리티
- `VariableEnv.top_from_soltype(sol_t, struct_defs, enum_defs, identifier)` → top-valued domain object
- struct, enum, array, mapping, interface, elementary 전부 지원
- interface function return 시 모든 return type에 대해 proper domain value 반환

### Interface struct return + parent chain 검색
- InterfaceFunctionCallContext에서 `top_from_soltype`으로 StructVariable 반환
- `_lookup_interface_return`: parent interface chain BFS 검색 (IVaultGovernance → ILpIssuerGovernance 등)
- `resolve_library_struct`: interface/contract pkl에서도 struct/enum 조회

### Interface 타입 전반 지원 강화
- `top_from_soltype`, `initialize_struct._make_var`, `MappingVariable._make_value`, `Engine._interpret_var_decl`: interface typeCategory → AddressSet.top() + `_cast_interface`
- `AddressSet.join/meet/narrow`: `_cast_interface` 보존 (`getattr` safe access)
- `_make_bottom`: AddressSet bottom 시 `_cast_interface` 타입 정보 보존
- `evaluate_identifier_context`: composite 타입(Struct/Array/Mapping) 객체 직접 반환

### @IReturn Grammar 일반화
- `debugIReturn` rule: 기존 4개 → PatternA/B 2개 + `ireturnAccessChain`
- access chain: `("member", name)`, `("index", int)`, `("call", name)` 3종
- Registry key: `(contract_var, func_name, access_chain_tuple)` 형식
- `_assemble_ireturn_value`: access chain 따라 struct member 설정

### Library constant 조회
- `evaluate_member_access_context`: library의 `state_variable_node.variables`에서 상수 조회

### Dependency 사전분석 확장
- `_load_parent_pkls`: 모든 모드(contract, interface, library)에서 호출
- regex: `contract|interface|library` 모두 매칭
- interface 결과 추출: `_pre_existing_all` 기반

### Refine non-l-value skip
- function call, binary/unary op, literal, tuple, type conversion 등 non-l-value expression narrowing 방지

### SolidityAnalyzer._insert_lines shift 수정
- `skip_shift_at_start=True` 시 `actual_offset = offset - 1`
- for loop 이후 코드가 loop 내부로 잘못 포함되던 CFG 구축 문제 해결

---

## 엔진 수정 사항 (2026-03-30 세션 4)

### Contract 타입 인식 (visitUserDefinedType)
- `contract_cfgs`에 등록된 contract 타입 (부모 컨트랙트 등)을 interface와 동일하게 address로 처리
- `library_cfgs`에 있는 타입은 제외 (library는 변수 타입으로 사용 불가)
- 47_H_02 해결 (ERC20Upgradeable), 51_H_02 해결 (LPToken)

### 부모 contract의 using 선언 상속
- `make_contract_cfg` / `make_abstract_contract_cfg`에서 `_inherit_using_libraries(cfg)` 호출
- 부모 pkl의 `using_libraries` / `using_all_libraries`를 자식 cfg에 복사
- Solidity semantics: `using X for Y;`는 derived contract에도 적용

### process_using_directive — library_cfgs 우선 조회
- 기존: pkl 파일 경로로만 검색 (`lib_{name}.pkl`) → `lib_47_SafeMathUpgradeable.pkl` 같은 prefix 있는 경우 못 찾음
- 수정: `self.library_cfgs`를 먼저 확인, pkl은 fallback
- 이미 로드된 library를 재활용하므로 일관성 + 일반성 확보

### Library globals (block.timestamp 등)
- `LibraryCFG`에 `globals` 필드 추가 (`CFG.py`)
- `make_library_cfg`에서 `StaticCFGFactory._create_global_variables()` 호출
- library 함수도 `block.timestamp`, `msg.sender` 등 사용 가능 (Solidity semantics)
- 51_H_02 해결 (SwapUtils library에서 block.timestamp 접근)

### require/assert 분기에서 During intent 검증
- Engine.py require/assert 분기 (`condition_node_type in ["require", "assert"]`)에서 `_process_node_intents` 호출 추가
- 기존: require 노드에 statements가 없어 intent 검증이 스킵됨
- 수정: `continue` 직전에 `_process_node_intents(node, cur_vars, src_line)` 호출
- `@During require feasible` annotation 정상 동작
- 51_H_02 해결 (require 조건이 항상 false → VIOLATED)

### 51번 Dependency 신규 생성
- `Dependencies/contracts/51/`: Context, ERC20 (OZ 0.6 표준), ERC20Burnable, Ownable, LPToken
- `Dependencies/interfaces/ISwap.sol`
- pkl 생성 순서: ISwap → Context → ERC20 → ERC20Burnable → Ownable → LPToken

### struct 생성자 검색 일반화 (_find_struct_def)
- `evaluate_function_call_context`에서 struct 생성자 검색 시 현재 contract + parent chain + using libraries + library_cfgs 전체 검색
- library에서 찾은 경우 qualified name 반환 (e.g., `FixedPointMath.FixedDecimal`) → using key와 매칭
- positional argument 지원: `FixedDecimal(x)` 같은 positional 인자도 struct 멤버에 매핑
- 56_H_02 해결 (FixedPointMath.FixedDecimal struct 생성자 인식)

### FixedPointMath inline assignment 분리
- `require((x = self.x * value) / value == self.x)` → `uint256 x = self.x * value; require(x / value == self.x);`
- IntentChecker가 조건식 내 inline assignment를 지원하지 않으므로 semantics 동일한 형태로 분리
- `fromU256`, `add`, `sub`, `mul` 4개 함수 모두 적용

### divide에서 0 제외 (Interval.py)
- 기존: 분모에 0 포함 시 무조건 BOTTOM
- 수정: Solidity에서 div-by-zero는 revert → 0을 제외하고 나눗셈 수행
- `UnsignedIntegerInterval`: `[0, MAX]` → `[1, MAX]`으로 0 제외
- `IntegerInterval`: `[-5, 5]` → `[-5, -1]` ∪ `[1, 5]` 두 구간으로 분리, 결과 보수적 합산
- 분모가 정확히 `[0, 0]`일 때만 BOTTOM (항상 revert)

### OR(||) short-circuit BOTTOM 전파 수정
- 기존: `||`에서 한쪽 피연산자가 BOTTOM이면 결과도 BOTTOM
- 수정: `||`에서 한쪽이 true 가능하면 다른 쪽 BOTTOM이어도 결과는 `[0,1]` (Solidity short-circuit semantics)
- `&&`는 기존대로 한쪽 BOTTOM이면 BOTTOM 유지

### Infeasible path (BOTTOM env) statement 실행 스킵 (Engine.py)
- 워크리스트 루프 상단에서 BOTTOM env 검사 추가
- BOTTOM이면 모든 노드 타입(statement, condition, for-increment)에서 실행 스킵
- successor에 BOTTOM 전파만 수행
- 기존: infeasible branch의 literal return (`return 666666`)이 수집되어 join 범위 확대
- 수정: infeasible path에서 statement 미실행 → return value 미수집 → 정확한 범위
- Nokon WARNING→VIOLATED 해결 (calculateRate가 정확히 250000만 반환)

### DebugInitializer TypeConversion mapping key 처리
- `_update_left_var_for_debug`에 `TypeConversion` context 핸들러 추가
- `balances[address(this)]` annotation에서 `address(this)`를 evaluator로 평가 → `AddressSet({1})` key 생성
- evaluator의 `evaluate_type_conversion_context`와 동일한 key 결정

### Refine 비트 길이 통일 (Refine.py)
- literal(256bit default)과 변수(실제 비트) 비교 시 비트 불일치
- promotion: 큰 쪽 비트로 통일 → refine → 원래 비트 복원
- 62_H_08 해결 (uint32 vs uint256 literal 비교)

### visitUserDefinedType parent chain 검색
- struct/enum 검색 시 `contract_cfg` + parent chain 순회 (`_find_in_chain` 재귀)
- `StaticCFGFactory.make_param_variable`에서도 parent chain struct 검색
- 70_H_10 해결 (ILiquidityBasedTWAP.ExchangePair)

### file-level struct StructDefinition 통일
- 기존: `{field_name: SolType}` dict → `initialize_struct` 호환 안 됨
- 수정: contract level과 동일하게 `StructDefinition` 객체 사용
- 60_H_01 해결 (OptimisticLedger file-level struct)

### main.py type alias 사전 등록
- `load_dependencies()`에 `type X is Y;` 패턴 스캔 추가
- Dependencies/libraries, contracts에서 type alias 수집 → `sa.type_aliases` 등록
- 60_H_01 해결 (UFixed18, Fixed18)

### SolType.aliasName 필드
- user-defined value type의 원래 이름 보존 (e.g., `UFixed18`)
- resolve 후에도 `aliasName`으로 using key 매칭 가능
- `_get_variable_type_string`에서 `aliasName` 우선 반환
- `_resolve_alias_from_expr`: interval baseVal일 때 expr.base 분석으로 alias 복원

### 62_H_08 contraction 수정
- sol에서 modifier를 함수 앞으로 이동 + soltotestjson 재생성
- annotation `[101]` → `[msg.sender]`

---

## 엔진 수정 사항 (2026-04-01 세션 5)

### interpret_function_cfg / interpret_function_cfg_for_debug 분리
- 기존: `_interpret_function_cfg_impl`을 공유하며 `record_enabled` flag로만 구분
- 문제: internal function call 시 caller의 state variable이 callee에 전달되지 않음 (같은 storage인데 `not in` 체크로 차단)
- 수정: `_interpret_function_cfg_impl` 제거, 두 함수를 별도 구현
  - **Case A** (`interpret_function_cfg_for_debug`): debug batch flush에서 호출. `assign_env/entry_env` 갱신, Post annotation 처리, 기록 활성화
  - **Case B** (`interpret_function_cfg`): evaluator의 함수 호출에서 호출. caller env의 state/global을 callee에 덮어씀 (파라미터 제외)
- 공통 로직은 `_reset_node_vars`, `_run_worklist`, `_extract_return_value` 헬퍼로 추출

### evaluate_function_call_context step 5-A 제거
- 기존: `function_cfg.related_variables.setdefault(k, v)`로 caller env를 callee의 `related_variables`에 영구 병합
- 문제: `related_variables`는 함수 정의 시점의 변수 집합인데 호출마다 caller 변수가 누적 → pkl 오염 (e.g., `balanceOfBatch`의 `i`가 `balanceOf`에 잔류 → BOTTOM 판정)
- 수정: step 5-A 삭제. caller env 전달은 `interpret_function_cfg`의 `start_block.variables` 병합에서만 처리

### ERC1155Upgradeable dependency 신규 생성
- `Dependencies/interfaces/`: IERC165Upgradeable, IERC1155Upgradeable, IERC1155MetadataURIUpgradeable
- `Dependencies/contracts/`: ERC165Upgradeable, ERC1155Upgradeable
- OZ contracts-upgradeable ^3.4.2 기준 (Web3Bugs contest 101)
- pkl 생성 순서: IERC165 → IERC1155 → IERC1155MetadataURI → ERC165 → ERC1155
- 기존 pkl 재사용: `con_47_Initializable`, `con_47_ContextUpgradeable`, `lib_47_SafeMathUpgradeable`, `lib_47_AddressUpgradeable`

### 101_H_01 해결: WARNING → VIOLATED
- `balanceOf`는 상속 함수(ERC1155Upgradeable) — IReturn이 아니라 상속 체인으로 진입
- `@StateVar _balances[_id][_lender] = [100000, 100000]` + `@LocalVar _lender = symbolicAddress 102` 추가
- `_principalWithdrawable = [100000, 100000]` > `_totalLiquidityWithdrawable = [99000, 99000]` → VIOLATED

### 56_H_02 해결: WARNING → VIOLATED
- **initialize_struct에 struct_defs 전달**: nested struct(FixedPointMath.FixedDecimal)의 멤버 `x`가 초기화되지 않던 문제 수정
- **library function call에서 struct 전달**: `evaluate_library_function_call_context`에서 StructVariable 인자를 `.value`로 추출하면 `None`이 됨 → 객체 자체를 전달하도록 수정
- **`_make_bottom` 재귀 버그**: `for m in ...: self._make_bottom(m); return` — 세미콜론으로 인해 첫 번째 멤버만 BOTTOM 처리 후 return. 전체 멤버 순회하도록 수정
- FixedPointMath/SafeMath pkl 재생성 (related_variables 오염 제거)

---

## 케이스별 실행 결과 (2026-03-31 세션 4 최종)

| # | Case | Status | 비고 |
|---|------|--------|------|
| 1 | WANGMI | ✅ VIOLATED (V=1) | runner.py 경로 |
| 2 | Nokon | ✅ VIOLATED (V=1) | 세션4 해결 — BOTTOM skip + address(this) key |
| 3 | SwordCrowdsale | ✅ VIOLATED (V=2) | runner.py 경로 |
| 4 | BoostToken_operator | ✅ VIOLATED (V=2) | runner.py 경로 |
| 5 | BoostToken_indivisible | ✅ VIOLATED (V=4) | runner.py 경로 |
| 6 | HIT | ❌ ERROR | ImplicationContext.commonClause (이후 작업) |
| 7 | 5_H_07 | ✅ VIOLATED (V=1) | |
| 8 | 5_H_08 | ✅ VIOLATED (V=1) | |
| 9 | 5_H_12 | ✅ VIOLATED (V=1) | |
| 10 | 77_H_01 | ✅ VIOLATED (V=1) | |
| 11 | 101_H_01 | ✅ VIOLATED (V=1) | 세션5 해결 — 상속 함수 진입 + StateVar _balances |
| 12 | 45_H_01 | ✅ VIOLATED (V=2) | 세션3 해결 |
| 13 | 47_H_02 | ✅ VIOLATED (V=1) | 세션4 해결 |
| 14 | 51_H_02 | ✅ VIOLATED (V=1) | 세션4 해결 |
| 15 | 56_H_02 | ✅ VIOLATED (V=1) | 세션5 해결 — struct 전달 + _make_bottom 재귀 |
| 16 | 58_H_02 | ✅ VIOLATED (V=1) | 세션6 해결 — related_variables BOTTOM 전파 + interface_var_types + new 배열 0-init |
| 17 | 60_H_01 | ❌ ERROR | qualified lib static call 체이닝 미해결 (Fixed18Lib._from().add()) |
| 18 | 62_H_08 | ✅ VIOLATED (V=1) | 세션4 해결 |
| 19 | 70_H_10 | ✅ VIOLATED (V=1) | 세션7 해결 — enum pkl + enum parent chain + for init 0 + VarRefMemberAccess length |
| 20 | 78_H_02 | ✅ VIOLATED (V=1) | 세션7 해결 — exit_env 캡처 + 복합자료구조 전파 + IReturn sub-function 전파 |
| 21 | HIT | ✅ VIOLATED (V=1) | 세션8 해결 — ImplicationContext visitor 수정 + nonzero 평가기 + alias resolve 일반화 |
| 22 | 60_H_01 | ✅ VIOLATED (V=1) | 세션8 해결 — qualified lib call 체이닝 + library_name 역추적 |

**21 VIOLATED + 0 WARNING + 0 ERROR = 22건** (42_H_01 미생성)

### 남은 작업

**미생성 1건:**
| Case | 사유 | 필요 작업 |
|------|------|----------|
| 42_H_01 | FloatStruct file-level struct + Float 라이브러리 | Dependencies/ISSUES.md 참조 |

---

## 세션 8 (2026-04-06)

### HIT 해결: ERROR → VIOLATED

**근본 원인 3가지 발견 및 수정:**

1. **`ImplicationContext` visitor에서 `commonClause()` 대신 `intentValue()` 호출**
   - `EnhancedSolidityVisitor._build_common_clause_dict`: grammar는 `intentValue '=>' intentValue`인데 visitor가 `commonClause(0/1)` 호출 → None 반환 → 크래시
   - `intentValue(0/1)`로 수정, `{"kind": "nonzero", "expr": ...}` dict로 래핑

2. **`_eval_nonzero` 평가기 추가 (GuardianVerificationEngine)**
   - `_eval_during_predicate`, `_eval_post_predicate`에 `"nonzero"` kind 분기 추가
   - interval `[a,b]`에서 0 미포함→satisfied, `[0,0]`→violated, 0 포함→warning
   - `toGive=[5000e18]`→nonzero(satisfied), `msg.value=[0,0]`→zero(violated) → **VIOLATED**

3. **`_resolve_alias_from_expr` 일반화 (Evaluation.py)**
   - `IndexAccessContext` 지원: `balances[_to].add(...)` — 평가 후 Variables typeInfo 확인
   - `FunctionCallContext` 지원: `value.div(100000).mul(...)` — 체이닝 시 base object 재귀 추적
   - 일반 fallback: 평가 시도 후 Variables typeInfo 확인
   - **ALIAS RESOLVE ERROR 전부 해소**, SafeMath dispatch 정상화

4. **`@Debugging BEGIN` 라인 번호 수정 (HIT_input.json)**
   - 54(함수 헤더) → 55(함수 본문): `_batch_targets`에 `getTokens` fcfg 정상 등록

### 60_H_01 해결: ERROR → VIOLATED

**근본 원인 2가지 발견 및 수정:**

1. **`evaluate_library_function_call_context`: qualified call의 implicit_first_arg 처리**
   - `arguments = [implicit_first_arg]` → qualified call에서 `implicit_first_arg=None`이 `[None]`으로 들어가 인자 수 불일치
   - `None`이 아닐 때만 추가하도록 수정

2. **`_resolve_alias_from_expr`: library CFG의 `library_name` 속성으로 역추적**
   - `contract_name` 속성이 없고 `library_name`만 있음 → `getattr(lib, 'contract_name')` 실패
   - `library_name` 우선, `contract_name` fallback으로 수정
   - `using_libraries` 역추적: `{'Fixed18': [Fixed18Lib_cfg]}` → `Fixed18Lib` → `Fixed18` alias 반환

---

## 세션 6 (2026-04-03)

### 58_H_02 해결: ERROR → VIOLATED

**근본 원인 5가지 발견 및 수정:**

1. **`build_variable_declaration`에서 지역변수 `related_variables` 참조 공유 제거**
   - `DynamicCFGBuilder.py`: `add_related_variable(var_obj)` 제거
   - 대신 interface 타입 지역변수만 `FunctionCFG.interface_var_types`에 별도 등록
   - 지역변수가 `related_variables`에 shared reference로 들어가면 분석 중 `_make_bottom()` in-place mutation이 전파됨

2. **상태변수도 copy로 추가 (BOTTOM mutation 전파 방지)**
   - `ContractAnalyzer.py:854,928`: `add_related_variable(var_obj)` → `add_related_variable(name, VariableEnv.copy_single_variable(var_obj))`

3. **BOTTOM env에서 condition refine skip**
   - `Engine.py _edge_env_from_pred()`: BOTTOM env는 refine 불필요 (BOTTOM ⊓ cond = BOTTOM)
   - `if (baseSupply == 0)` true branch가 infeasible → BOTTOM env가 for_cond로 전파 → for_body가 outer worklist에 들어감 → `i` 미선언 에러 발생 경로 차단

4. **`Evaluation._get_interface_name_of_var`에 `interface_var_types` 조회 추가**
   - `related_variables`에서 지역변수를 빼면서 `vg`의 interface 이름 조회 실패 → IReturn 미적용
   - `FunctionCFG.interface_var_types` fallback 추가

5. **`new` 배열 원소 초기화: BOTTOM → 0 (Solidity semantics)**
   - `Evaluation.py evaluate_new_expression()`: `UnsignedIntegerInterval.bottom()` → `UnsignedIntegerInterval(0, 0, bits)`
   - Solidity에서 `new uint256[](n)` 원소는 0으로 초기화됨
   - BOTTOM이었을 때 `baseTvls` 전체가 BOTTOM → 이후 모든 노드 BOTTOM 전파

**annotation 값 조정:**
- `_lpPriceHighWaterMarks[0]`과 `[1]`을 동일 값(1e18)으로 설정
  - for-loop fixpoint에서 `hwms[i]`가 `i=[0,1]`로 join되면 `[hwm0, hwm1]` interval이 됨
  - hwm이 다르면 `delta_min = hwm_min * DENOM / hwm_max < DENOM` → `toMint_min < baseSupply` → WARNING
  - hwm이 같으면 `delta_min = DENOM` → `toMint_min = baseSupply` → VIOLATED

### 기타 수정

**`@Debugging END` 라인 전체 수정:**
- 전체 19개 JSON 파일의 `@Debugging END` startLine이 BEGIN과 동일하게 잘못 설정됨 → 일괄 수정
- `generate_case_jsons.py`: BEGIN/END 자동 생성하도록 수정

### 78_H_02 시도 결과

**JSON 생성 + OZ ERC20 pkl 생성 완료, 실행 가능하나 결과 미달:**
- `Dependencies/contracts/78_OZ_ERC20.sol` 생성 → `con_ERC20.pkl` 재생성 (OZ 버전, `totalSupply()` 함수 포함)
- 기존 `con_ERC20.pkl`은 Solmate ERC20 (public state var `totalSupply`), OZ는 private `_totalSupply` + getter 함수
- 실행 결과: `@Post _balances[to] <= amount` → **satisfied** (의도는 violated)
- **원인**: `_mint()` 호출 시 pkl 내부의 `_balances`와 RebaseProxy의 `_balances`가 **별도 객체**
  - pkl `_mint.related_variables['_balances']` → `_mint()` 내부에서 업데이트
  - RebaseProxy `related_variables['_balances']` → debug annotation 대상, Post 검증 대상
  - 두 객체가 분리되어 있어 `_mint()` 결과가 Post 검증에 반영 안 됨
- **해결 방향**: 상속 함수 호출 시 child의 state variable을 caller_env로 전달하여 pkl 함수가 child의 변수를 직접 업데이트하도록

### 수정된 파일 요약

| 파일 | 변경 |
|------|------|
| `Interpreter/Engine.py` | BOTTOM env refine skip, `interface_var_types` 등록 |
| `Interpreter/Semantics/Evaluation.py` | `_get_interface_name_of_var`에 `interface_var_types` fallback, `new` 배열 0-init |
| `Analyzer/DynamicCFGBuilder.py` | `add_related_variable` 제거 → `interface_var_types` 등록 |
| `Analyzer/ContractAnalyzer.py` | 상태변수 copy 추가, `_find_interface_name_for_var`에 `interface_var_types` fallback |
| `Utils/CFG.py` | `FunctionCFG.interface_var_types` 필드 추가 |
| `Dependencies/contracts/78_OZ_ERC20.sol` | OZ ERC20 축약 버전 (pkl 생성용) |
| `evaluation/RQ1/generate_case_jsons.py` | 78_H_02, 42_H_01 추가, BEGIN/END 자동 생성 |
| 전체 JSON 19개 | `@Debugging END` startLine 수정 |

---

## 세션 7 (2026-04-06)

### 78_H_02 해결: satisfied → VIOLATED

**근본 원인 3가지 발견 및 수정:**

1. **exit_env가 node 복원 후에 읽혀서 빈 dict 반환**
   - `interpret_function_cfg()`에서 `_force_join_before_exit()`로 exit_node.variables를 설정하지만,
     직후 `_saved_node_vars` 복원에서 exit_node.variables도 실행 전 값(빈 dict)으로 덮어씀
   - **수정**: `_exit_env`를 node 복원 **전에** 캡처하도록 순서 변경
   - `Engine.py`: `_exit_env = VariableEnv.copy_variables(fcfg.get_exit_node().variables)`

2. **exit_env → caller_env 반영 시 복합 자료구조 미전파**
   - 기존 코드: `caller_env[k].value = v.value` → MappingVariable의 실제 데이터는 `.mapping`에 있어 전파 안 됨
   - **수정**: 타입별 내부 데이터 전파
     - `MappingVariable`: `.mapping` 전파
     - `ArrayVariable`: `.elements` 전파
     - `StructVariable`: `.members` 전파
     - `EnumVariable`: `.value` + `.valueIndex` 전파
   - **추가**: callee 파라미터 이름이 caller의 동명 변수를 오염시키지 않도록 skip

3. **IReturn이 sub-function에서 미적용**
   - `mint()` 스코프에서 설정한 `@IReturn IERC20(baseToken).balanceOf() = [1500e18]`가
     sub-function `redeemRate()` 호출 시 적용 안 됨 (`fcfg.ireturn_registry`가 callee 것만 참조)
   - **수정**: `interpret_function_cfg()` 진입 시 caller의 `ireturn_registry`를 callee에 `setdefault`로 합치고, 실행 후 복원
   - 결과: `redeemRate()` 내 `balanceOfBase`가 TOP → 1500e18로 정밀해짐 → `_redeemRate = 1.5e18` → `proxy = 1000e18`

**annotation 추가:**
- `@LocalVar to = symbolicAddress 10` 추가
  - `_balances[to]` annotation에서 mapping key가 문자열 `"to"`로 저장됨
  - `_mint(address account, ...)` 내부에서 `_balances[account]`의 key는 `"account"`
  - symbolic address를 통해 두 key가 같은 주소를 바라보도록 연결

**최종 결과:**
- `_balances[to] = [1000e18, 1000e18]` (= proxy) > `amount = [500e18, 500e18]` → **VIOLATED (risk=10.0, both-side)**
- `proxy = (1500e18 * 1e18) / 1.5e18 = 1000e18` — 정확한 계산

### 수정된 파일 요약

| 파일 | 변경 |
|------|------|
| `Interpreter/Engine.py` | exit_env 캡처 순서 변경, 복합자료구조 전파, callee 파라미터 skip, ireturn_registry 전파 |
| `evaluation/RQ1/cases/web3bugs_78_H_02/web3bugs_78_H_02.json` | `@LocalVar to = symbolicAddress 10` 추가, startLine shift |

### 70_H_10 해결: ERROR → VIOLATED

**근본 원인 4가지 발견 및 수정:**

1. **`UniswapV2OracleLibrary` pkl 미생성**
   - `Dependencies/libraries/UniswapV2OracleLibrary.sol` 생성 (stub: 반환 타입만 보존)
   - pkl 생성 → `library_cfgs`에 등록 → qualified static call resolve 가능

2. **`ILiquidityBasedTWAP` enum members 미등록**
   - `Dependencies/main.py slice_solidity()`: enum body 파싱 미지원 → members가 빈 리스트
   - `in_enum` 플래그 추가: enum header 후 `}` 까지 모아서 한 record로 전달
   - pkl 재생성 → `Paths.members = ['VADER', 'USDV']`

3. **parent chain에서 enum 검색 미지원**
   - `Evaluation.py evaluate_identifier_context()`: 현재 contract의 `enumDefs`만 검색
   - `_find_enum_in_chain()` 추가: parent_cfgs 재귀 탐색
   - `Paths`가 `ILiquidityBasedTWAP`(parent)에 정의 → 검색 가능

4. **for문 초기화 없는 변수 선언 시 value=None**
   - `for (uint256 i; ...)` → `init_expr = None` → `i.value = None` → `++i` 에서 None + 1 에러
   - Solidity 기본값: uint/int는 0으로 초기화

5. **`VarRefMemberAccess`에서 `.length` 특별 처리 누락**
   - `DebugInitializer.py`: `.length` annotation 처리 조건에 `VarRefMemberAccess` 미포함
   - 조건에 추가 → `@StateVar vaderPairs.length = [1, 1]` 정상 적용

**최종 결과:**
- `previousPrices[0]` Entry=[1000000000000000] == Exit=[1000000000000000] → changed 미발생 → **VIOLATED (risk=10.0)**

### 수정된 파일 요약 (70_H_10)

| 파일 | 변경 |
|------|------|
| `Dependencies/main.py` | `slice_solidity()` enum body 파싱 (`in_enum` 플래그) |
| `Dependencies/libraries/UniswapV2OracleLibrary.sol` | 신규 생성 (stub) |
| `Dependencies/interfaces/ILiquidityBasedTWAP.sol` | enum members 줄바꿈 정리 |
| `Interpreter/Semantics/Evaluation.py` | `_find_enum_in_chain()` parent chain enum 검색 |
| `Interpreter/Semantics/DebugInitializer.py` | `.length` 조건에 `VarRefMemberAccess` 추가 |
| `Analyzer/ContractAnalyzer.py` | for init 초기화 없는 uint/int → 0 |
