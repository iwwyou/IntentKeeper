# Intent Annotation Grammar Extension — ANTLR 버전 정합성 + 회귀 검증

**목적**: intent annotation grammar(`arithExpr` 계열)에 `**`, `<<`, `>>`, `>>>` 연산자를 추가하는 작업을 완료. 이미 grammar 수정과 파서 재생성까지 했으나 ANTLR CLI/runtime 버전 미스매치로 실행 실패. 이 chat에서는 **버전 정합성 복구 → 파서 재생성 → visitor 확인 → 회귀 검증 → paper 업데이트** 전 과정을 수행.

**맥락**: IntentChecker는 Solidity용 development-time specification validation tool. RQ1에 20개 mitigated case가 있고 `evaluation/RQ1/run_all.py`가 이들을 subprocess로 돌려 VIOLATED/WARNING/SATISFIED/ERROR 집계.

---

## 현재 상태 (이전 chat에서 이미 수행)

### 수행 완료
1. `Parser/Solidity.g4` 수정 — intent arithmetic grammar에 shift(`<<`,`>>`,`>>>`)와 exponentiation(`**`) 층 추가. 기존 `arithExpr`→`arithTerm`→`arithFactor` 층 사이에 `arithAdd`, `arithExp` 층 삽입. Label은 Solidity source grammar의 `#Exponentiation`/`#ShiftOp`와 충돌 피해 `#IntentExponentiation`/`#IntentShiftOp` 사용.

   최종 구조:
   ```antlr
   arithExpr   : arithExpr ('<<'|'>>'|'>>>') arithAdd   #IntentShiftOp
               | arithAdd                                #IntentShiftRoot ;
   arithAdd    : arithAdd ('+'|'-') arithTerm            #AddSub
               | arithTerm                               #AddSubRoot ;
   arithTerm   : arithTerm ('*'|'/'|'%') arithExp        #MulDivMod
               | arithExp                                #MulDivModRoot ;
   arithExp    : arithFactor '**' arithExp               #IntentExponentiation
               | arithFactor                             #IntentExpRoot ;
   arithFactor : ... (unchanged) ;
   ```

2. `Analyzer/EnhancedSolidityVisitor.py` 수정:
   - `visitAddSub`: LHS accessor `ctx.arithExpr()` → `ctx.arithAdd()` (rule 좌변이 바뀜)
   - `visitMulDivMod`: RHS `ctx.arithFactor()` → `ctx.arithExp()`
   - `visitMulDivModRoot`: `ctx.arithFactor()` → `ctx.arithExp()`
   - 신규 추가: `visitIntentShiftOp`, `visitIntentShiftRoot`, `visitIntentExponentiation`, `visitIntentExpRoot`

3. `Parser/Solidity.g4`로부터 파서 재생성 완료 — 하지만 **여기서 문제**:
   - 재생성 CLI: `antlr4` (at `C:/Users/isjeon/AppData/Local/Programs/Python/Python310/Scripts/antlr4`) — **ANTLR Parser Generator Version 4.13.2**
   - Python runtime: `antlr4-python3-runtime==4.12.0` (pip show 결과)
   - `requirements.txt`에는 `antlr4-python3-runtime==4.13.2`로 선언되어 있으나 실제 설치는 4.12.0
   - 결과: 재생성된 parser는 4.13.2 포맷이지만 runtime은 4.12.0 → `"ANTLR runtime and generated code versions disagree: 4.12.0!=4.13.2"` 다수 발생 + 파싱 실패로 `run_all.py`에서 20 중 13 ERROR.

4. `Interpreter/Semantics/Evaluation.py`와 `Domain/Interval.py`는 이미 `**`, `<<`, `>>`, `>>>` 연산자 지원 — **무수정**으로 OK.
   - `Evaluation.py` 1753: `**` dispatch → `leftInterval.exponentiate(rightInterval)`
   - `Evaluation.py` 1756: `<<`/`>>`/`>>>` dispatch → `leftInterval.shift(...)`
   - `Domain/Interval.py`: `exponentiate`, `_lshift`, `_rshift` 구현 존재

### 사용자 방향 결정
- 사용자가 **Option B** 선택: CLI를 4.12.0으로 다운그레이드해 기존 runtime과 맞추기
- `requirements.txt`도 4.12.0으로 수정 (현실 반영)
- 재생성된 parser가 4.12.0 포맷이 되도록

---

## 이 chat에서 할 일

### Step 1. ANTLR 버전 정합성 복구

**환경 정보**:
- OS: Windows 11, shell is bash (use `/` paths, `python` command)
- Java 17 설치됨 (`java -version`: 17.0.12)
- 기존 antlr4-tools 0.2 설치됨 (jar 위치 불명 — `find`로 찾아야 함)
- 기존 `antlr4` CLI: Windows PE binary at Python310 Scripts — 4.13.2 버전

**접근 A (권장 추정)**: antlr-4.12.0-complete.jar 직접 사용
- https://www.antlr.org/download/antlr-4.12.0-complete.jar 다운로드 (또는 이미 다른 위치에 있는지 `find`)
- `java -jar antlr-4.12.0-complete.jar -Dlanguage=Python3 -visitor Parser/Solidity.g4 -o Parser/` 형태로 재생성
- 단, output path 주의: `.g4` 파일 위치와 동일 디렉토리에 생성해야 기존 `SolidityLexer.py`, `SolidityParser.py`, `SolidityVisitor.py`, `SolidityListener.py`를 덮어씀

**접근 B**: `pip install "antlr4-tools==<version_that_bundles_4.12.0>"` 시도 — 단 antlr4-tools의 버전↔ANTLR 버전 mapping이 불확실. PyPI에서 확인 필요.

**접근 C**: `pip install --upgrade antlr4-python3-runtime==4.13.2`로 runtime을 올리는 방향 — 단 이건 사용자가 **거부한 옵션 A**. 다시 이걸로 돌리지 말 것.

### Step 2. 재생성 후 검증

1. `Parser/SolidityParser.py`, `Parser/SolidityVisitor.py` 재생성 확인
2. 생성된 파일의 상단 주석에서 ANTLR 버전 확인 (`# Generated from Solidity.g4 by ANTLR 4.12.0`)
3. 기존 visitor 수정(`EnhancedSolidityVisitor.py`)이 그대로 유효한지 확인:
   - `IntentShiftOpContext`, `IntentShiftRootContext`, `IntentExponentiationContext`, `IntentExpRootContext` 클래스가 `SolidityParser.py`에 존재하는지 grep
   - `AddSubContext.arithAdd()`, `MulDivModContext.arithExp()` accessor가 존재하는지 확인

### Step 3. `requirements.txt` 업데이트

현재:
```
antlr4-python3-runtime==4.13.2
```
→
```
antlr4-python3-runtime==4.12.0
```

주석도 업데이트: "must match the ANTLR version that generated Parser/SolidityLexer.py and Parser/SolidityParser.py" 부분은 유지하되 `4.13.2`→`4.12.0`.

### Step 4. 회귀 검증

```bash
python evaluation/RQ1/run_all.py
```

**기대값**: 20/20 VIOLATED (0 ERROR, 0 WARNING, 0 SATISFIED)

`evaluation/RQ1/rq2_results.csv`가 덮어써짐. 결과 확인:
- `result` 컬럼이 모두 `VIOLATED`인지
- `violation_count` ≥ 1인지
- `error` 컬럼이 모두 빈 문자열인지

ERROR 발생 시 해당 케이스를 개별 실행해 traceback 확인:
```bash
python main.py evaluation/RQ1/cases/<category>/<case>_input.json 2>&1 | tail -50
```

### Step 5. Paper Fig. 3 grammar 업데이트

파일: `paper/main.tex`, 줄 608-611
```latex
intentValue & $\rightarrow$ & arithExpr & \\[2pt]
arithExpr   & $\rightarrow$ & arithExpr (+ $|$ -) arithTerm $|$ arithTerm & \\
arithTerm   & $\rightarrow$ & arithTerm (* $|$ / $|$ \%) arithFactor $|$ arithFactor & \\
arithFactor & $\rightarrow$ & number $|$ [ number , number ] $|$ varRef $|$ ( arithExpr ) & \\[2pt]
```

→ 이것을 새 grammar 구조로 교체:
```latex
intentValue & $\rightarrow$ & arithExpr & \\[2pt]
arithExpr   & $\rightarrow$ & arithExpr ($<<$ $|$ $>>$ $|$ $>>>$) arithAdd $|$ arithAdd & \\
arithAdd    & $\rightarrow$ & arithAdd (+ $|$ -) arithTerm $|$ arithTerm & \\
arithTerm   & $\rightarrow$ & arithTerm (* $|$ / $|$ \%) arithExp $|$ arithExp & \\
arithExp    & $\rightarrow$ & arithFactor ** arithExp $|$ arithFactor & \\
arithFactor & $\rightarrow$ & number $|$ [ number , number ] $|$ varRef $|$ ( arithExpr ) & \\[2pt]
```

주의: `**`는 LaTeX에서 `$\mathbin{**}$` 또는 단순히 `**`로 써도 렌더링됨. 다른 rule label들(예: §5.3 RQ2 본문에서 L4d 관련 "grammar expressibility" 언급)은 건드리지 말 것 — RQ2 데이터는 여전히 유효(L4는 별도 expressibility 이슈, 이번 추가로 풀리는 케이스 없음).

§6.3 Limitations에서 "Unsupported Solidity constructs" 같은 문단에 지수/시프트 언급이 있다면 재확인해 업데이트 필요.

---

## 검증 대상 파일 (핵심)

| 파일 | 역할 | 변경 상태 |
|------|-----|---------|
| `Parser/Solidity.g4` | Grammar source | **수정 완료** (이전 chat) |
| `Parser/SolidityParser.py` | Generated parser | **4.13.2로 재생성됨 (문제 상태)** — 4.12.0으로 재재생성 필요 |
| `Parser/SolidityVisitor.py` | Generated visitor base | 동일 |
| `Parser/SolidityLexer.py` | Generated lexer | 동일 |
| `Parser/SolidityListener.py` | Generated listener | 동일 |
| `Analyzer/EnhancedSolidityVisitor.py` | Custom visitor | **수정 완료** (1217-1290 근처) |
| `Domain/Interval.py` | Interval abstract ops | 무수정 (이미 지원) |
| `Interpreter/Semantics/Evaluation.py` | Operator dispatch | 무수정 (이미 지원) |
| `requirements.txt` | pin version | **업데이트 필요** (4.13.2 → 4.12.0) |
| `paper/main.tex` | Grammar figure | **업데이트 필요** (Fig. 3, 줄 608-611) |

---

## 결정 근거 요약 (이전 chat에서)

- **Q**: intent grammar에 `**`, `<<`, `>>`, `>>>`를 추가하면 Evaluation/Interval도 손대야 하나?
- **A**: Evaluation.py 1753/1756 및 Interval.py의 `exponentiate`/`_lshift`/`_rshift`가 이미 Solidity source 쪽 파싱을 위해 구현되어 있음. Intent expression은 `AddSubContext`/`MulDivModContext` 식으로 태그되지만 `Evaluation.evaluate_expression` 438은 context-기반 dispatch에서 못 잡히면 491-497 fall-through로 `operator` 기반 `evaluate_binary_operator` 호출 → 새 연산자도 그대로 작동. 그러니 **grammar + visitor 수정**만으로 충분.

- **Q**: `&`, `|`, `^`, `~` (bitwise)도 추가?
- **A**: 사용자 결정으로 **제외**. 이건 Evaluation.py의 binary dispatch에도 없고 Interval.py의 abstract op도 없어 full-stack 구현 필요. 이번 scope 밖.

---

## 산출물 체크리스트

- [ ] ANTLR 4.12.0으로 파서 재생성 완료 (파일 헤더로 확인)
- [ ] `requirements.txt`를 4.12.0으로 업데이트
- [ ] `python evaluation/RQ1/run_all.py` 실행 → 20/20 VIOLATED 확인
- [ ] `evaluation/RQ1/rq2_results.csv` 확인 (result 컬럼 전부 VIOLATED)
- [ ] `paper/main.tex` Fig. 3 grammar 업데이트
- [ ] `paper/main.tex`의 §6.3 등 다른 곳에 지수/시프트 연산자 관련 언급 있는지 grep으로 확인 후 정합성 점검

## 출력 지침

- 단계별로 결과 확인 후 진행
- 명령 실행 시 절대경로 선호 (`C:/Users/isjeon/PycharmProjects/pythonProject/SolidityGuardian/...`)
- Working directory는 프로젝트 루트 (`SolidityGuardian/`) 유지
- 파싱 에러 등 발견 시 즉시 보고, 임의로 defensive code 추가하지 말 것
- 사용자가 `no`라고 답하면 그 방향으로 진행하지 말 것
