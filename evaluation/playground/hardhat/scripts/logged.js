// 실행: npx hardhat run scripts/logged.js
// console.log 를 심은 버전을 돌려 루프 iteration 값을 본다.
const hre = require("hardhat");
const { ethers } = hre;

async function main() {
  const [me] = await ethers.getSigners();
  const v = await ethers.deployContract("VaultLogged");
  const addr = await v.getAddress();
  const coder = ethers.AbiCoder.defaultAbiCoder();
  const u256 = (n) => ethers.toBeHex(n, 32);
  const slot = ethers.keccak256(coder.encode(["address", "uint256"], [me.address, 0]));
  await hre.network.provider.send("hardhat_setStorageAt", [addr, slot, u256(1000)]);
  await hre.network.provider.send("hardhat_setStorageAt", [addr, u256(1), u256(1000)]);

  for (const amt of [100, 10000 /* revert 시 */]) {
    console.log(`withdraw(${amt})`);
    try {
      await (await v.withdraw(amt)).wait();
    } catch (e) {
      console.log("  reverted:", e.shortMessage ?? e.message);
    }
  }
}

main().catch((e) => { console.error(e); process.exitCode = 1; });
