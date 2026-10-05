// 실행: npx hardhat run scripts/run.js
// forge 테스트와 같은 일을 "스크립트 + JSON-RPC" 로 한다. 평가 하네스가 Python 에서 할 일이 바로 이것이다.
const hre = require("hardhat");
const { ethers } = hre;

async function main() {
  const [me] = await ethers.getSigners();

  // ① 컴파일된 artifact 로 배포 (hardhat 이 run 전에 자동 compile)
  const v = await ethers.deployContract("Vault");
  await v.waitForDeployment();
  const addr = await v.getAddress();
  console.log("deployed at", addr);

  // ② 상태 주입: setter 가 없으니 storage 슬롯에 직접 쓴다 (JSON-RPC hardhat_setStorageAt)
  //    mapping(address=>uint) at slot 0 → 값 위치 = keccak256(abi.encode(key, 0))
  const coder = ethers.AbiCoder.defaultAbiCoder();
  const slotShares = ethers.keccak256(coder.encode(["address", "uint256"], [me.address, 0]));
  const u256 = (n) => ethers.toBeHex(n, 32);
  await hre.network.provider.send("hardhat_setStorageAt", [addr, slotShares, u256(1000)]);
  await hre.network.provider.send("hardhat_setStorageAt", [addr, u256(1), u256(1000)]); // totalShares
  console.log("before: shares =", (await v.shares(me.address)).toString(),
              " total =", (await v.totalShares()).toString());

  // ③ 전역 변수 조작 예: 다음 블록 timestamp 지정 (@GlobalVar block.timestamp 에 해당)
  await hre.network.provider.send("evm_setNextBlockTimestamp", [2_000_000_000]);

  // ④ 트랜잭션 실행
  const tx = await v.withdraw(100);
  const rc = await tx.wait();
  console.log("after : shares =", (await v.shares(me.address)).toString(),
              " total =", (await v.totalShares()).toString(), " gas =", rc.gasUsed.toString());

  // ⑤ 실행 추적: opcode 단위 trace. hardhat 에는 스텝 디버거가 없고, 이게 가장 낮은 수준의 관찰 수단이다.
  const trace = await hre.network.provider.send("debug_traceTransaction", [tx.hash]);
  console.log("opcode steps =", trace.structLogs.length,
              " first ops =", trace.structLogs.slice(0, 5).map((s) => s.op).join(" "));
}

main().catch((e) => { console.error(e); process.exitCode = 1; });
