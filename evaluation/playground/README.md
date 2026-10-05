# Hardhat / Foundry 실습 (playground)

평가 하네스를 짜기 전에 두 도구가 **실제로 무엇을 하는지** 손으로 확인하는 곳이다.
두 프로젝트 모두 같은 `Vault.sol` 을 쓴다 — 평가 케이스가 가진 귀찮은 점(setter 없는 상태변수,
internal 타겟 함수, 루프, require)을 일부러 다 넣었다.

PowerShell 기준. 경로는 `IntentKeeper\evaluation\playground` 에서 시작한다.

---

## Foundry (forge)

```powershell
cd forge
$F = "..\..\forge\bin\forge.exe"

& $F build                                   # 1. 컴파일 (out/ 에 ABI·바이트코드)
& $F test -vv                                # 2. 테스트 전부 + console.log 출력
& $F test --mt test_withdraw -vvvv           # 3. 한 테스트 + 호출 trace (누가 누구를 불렀나, storage 읽기/쓰기)
& $F inspect Vault storageLayout             # 4. 상태변수 → 슬롯 번호 (상태 주입에 필요)
& $F test --mt test_withdraw --debug         # 5. ★ 인터랙티브 디버거 (TUI). q 로 종료
```

5번이 forge 의 **스텝 디버거**다. 소스 줄 / opcode / 스택 / 메모리를 같이 보여 준다.
하단에 키 안내가 뜬다. 해볼 것: 루프 안으로 들어가 `r` 이 iteration 마다 바뀌는 걸 따라가 보기.
→ IQDebug 는 같은 루프를 **fixpoint 한 번**으로 접어서 보여준다는 점과 비교.

### 직접 바꿔볼 것

| 해볼 일 | 어디를 | 관찰 포인트 |
|---|---|---|
| 값 바꾸기 | `test_withdraw` 의 `_seed(..., 1000, 1000)` 과 `withdraw(100)` | `out` 이 왜 100 그대로인가? (`100*30/10000 = 0`) ← **정밀도 손실 버그** |
| 버그를 fuzz 로 잡기 | `testFuzz_withdraw` 의 `assertLe(out, amt)` → `assertLt(out, amt)` | fuzz 가 반례(`amt` 가 작은 값)를 찾아 준다. 몇 번째에 찾는지, 매번 같은지 |
| 소스 한 줄 고치고 다시 | `src/Vault.sol` 의 `feeBps` 를 `300` 으로 | `forge test` 가 **재컴파일 → 재배포 → 재실행** 하는 시간을 본다 (= 평가의 "증분 재측정") |
| private 만들기 | `_afterFee` 를 `private` 로 | harness 가 컴파일 안 된다 → 평가에서 private 5건에 `internal` 패치가 필요한 이유 |

---

## Hardhat

```powershell
cd hardhat
npx hardhat compile                          # 1. 컴파일 (artifacts/ 에 ABI·바이트코드)
npx hardhat run scripts/run.js               # 2. 배포 → storage 주입 → 실행 → opcode trace
npx hardhat run scripts/logged.js            # 3. console.log 를 심은 버전으로 루프 값 보기
```

- **hardhat 에는 스텝 디버거가 없다.** 값을 보는 방법은 (a) 소스에 `console.log` 를 넣고 다시 돌리기
  (`contracts/VaultLogged.sol`), (b) `debug_traceTransaction` 으로 opcode trace 받기(`run.js` ⑤) 두 가지다.
- `run.js` 는 평가 하네스가 Python 에서 할 일과 **똑같다** — 전부 JSON-RPC 호출이다
  (`hardhat_setStorageAt`, `evm_setNextBlockTimestamp`, `debug_traceTransaction`).

### 노드를 띄워서 밖에서 붙어 보기 (Python 하네스의 실제 모양)

```powershell
# 터미널 A
npx hardhat node                             # 127.0.0.1:8545 에 로컬 체인

# 터미널 B — 같은 스크립트를 외부 노드 대상으로
npx hardhat run scripts/run.js --network localhost
```
터미널 A 에 트랜잭션 로그가 찍힌다. Python 에서는 `requests.post("http://127.0.0.1:8545", json={...})` 로
똑같이 부르면 된다. Foundry 쪽은 `..\..\forge\bin\anvil.exe` 가 같은 역할(포트 8545, `anvil_setStorageAt`).

---

## 두 도구의 차이 한 장 요약

| | Foundry | Hardhat |
|---|---|---|
| 테스트 언어 | **Solidity** (`*.t.sol`) | JavaScript/TypeScript (또는 HH3 의 Solidity test) |
| 상태 주입 | cheatcode `vm.store` / `vm.deal` / `vm.warp` | JSON-RPC `hardhat_setStorageAt` / `hardhat_setBalance` / `evm_setNextBlockTimestamp` |
| internal 호출 | 상속 harness (테스트 파일 안) | 상속 harness (별도 .sol) |
| 값 보기 | `console.log`, `-vvvv` trace, **`--debug` 스텝 디버거** | `console.log`, `debug_traceTransaction` (스텝 디버거 없음) |
| 입력 구간 | **fuzz** (무작위 점 N개) | 직접 루프 |
| 속도 | 매우 빠름 (Rust, 증분 컴파일) | 느림 (Node, 매 run 마다 프로세스 기동) |
| 로컬 체인 | `anvil` | `hardhat node` |
