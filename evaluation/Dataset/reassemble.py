# -*- coding: utf-8 -*-
"""
IntentChecker 74 eligible 케이스(expressible 48 + inexpressible 26)의 원본을 컴파일 가능한
Foundry/Hardhat 프로젝트로 재조립한다.

입력 (evaluation/Dataset/):
  cases74.csv              case_id / contract / function / expressible ... (cases48.csv = RQ3 표 원본은 별도 보존)
  target_original/         케이스별 원본 .sol (4개는 레코드 .json → 이어붙여 원본 복원)
  Dependencies/pool/       RQ1 의존성 풀 313개 ({contest}_{Name}.sol 또는 {Name}.sol)
  Dependencies/{contracts,interfaces,libraries}/   Guardian Dependencies 트리
  Dependencies/reconstructed/   공개 저장소에 없어 사용처에서 복원한 파일 (헤더에 출처 명시)
  npm/node_modules/        공용 npm 패키지 (OZ 3.x/4.x 별칭 oz3 oz4 ozu3 ozu4, solmate, ...)
  npm/vendor/              npm 에 없는 패키지 (BoringSolidity)
구조 힌트 (읽기 전용): Dataset/Web3Bugs/*/contest_<id>_*/  flatten 파일명이 원본 디렉토리 구조
  (market_UToken.sol == market/UToken.sol) 를 담고 있다.

출력: projects/<proj>/src/<원본 경로 그대로>, foundry.toml, remappings.txt, reassemble_report.json

원칙: 소스 내용은 한 바이트도 바꾸지 않는다. 디렉토리 배치와 remapping 만으로 import 를 해결한다.
가시성 완화(private→internal 5건)는 여기서 하지 않는다 — Step 2 의 harness 단계에서 patches/ 로 분리.

사용:
  .venv/Scripts/python.exe evaluation/Dataset/reassemble.py            # 재조립만
  .venv/Scripts/python.exe evaluation/Dataset/reassemble.py --build    # + forge build 게이트
  .venv/Scripts/python.exe evaluation/Dataset/reassemble.py --only w45 --build
"""
import argparse
import collections
import csv
import json
import posixpath
import re
import shutil
import subprocess
import sys
import pathlib

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[2]          # IntentKeeper/
DS = pathlib.Path(__file__).resolve().parent                 # evaluation/Dataset/
# 구조 힌트 (읽기 전용, 선택). IntentKeeper 의 Dataset/Web3Bugs 는 README 만 있고 flatten .sol 은
# Guardian 쪽에만 있다. 없어도 동작한다 — 그때는 import 의 `../` 깊이에 맞춰 자리를 잡는다(depth-retry).
W3B_CANDIDATES = [ROOT / "Dataset" / "Web3Bugs",
                  ROOT.parent / "SolidityGuardian" / "Dataset" / "Web3Bugs"]
NPM = DS / "npm" / "node_modules"
VENDOR = DS / "npm" / "vendor"
HH_NPM = ROOT / "evaluation" / "hardhat" / "node_modules"
PROJ = DS / "projects"

IMP = re.compile(r"""^\s*import\s+(?:\{[^}]*\}\s*from\s*)?['"]([^'"]+)['"]\s*;""", re.M)
PRAGMA = re.compile(r"pragma\s+solidity\s+([^;]+);")

# npm prefix → remapping 대상. "oz"/"ozu" 는 프로젝트의 solc 세대(3.x/4.x)로 나중에 결정.
NPM_MAP = {
    "@openzeppelin/contracts-upgradeable/": "ozu",
    "@openzeppelin/contracts/": "oz",
    "@openzeppelin/upgrades/": NPM / "@openzeppelin" / "upgrades",      # OZ SDK 2.8 (w59)
    "solmate/": NPM / "solmate" / "src",
    "@sushiswap/bentobox-sdk/": DS / "Dependencies" / "reconstructed" / "bentobox-sdk",   # npm 에 .sol 없음 → 복원
    "@mochifi/library/": NPM / "@mochifi" / "library",
    "@mochifi/vmochi/": NPM / "@mochifi" / "vmochi",
    "@mochifi/cssr/": NPM / "@mochifi" / "cssr",
    "@uniswap/v2-core/": NPM / "@uniswap" / "v2-core",
    "prb-math/": NPM / "prb-math",                                      # w16 (2.4.x)
    "@boringcrypto/boring-solidity/": VENDOR / "BoringSolidity",
    "hardhat/": HH_NPM / "hardhat",
    # w110: forge 식 lib remapping 이름(`openzeppelin-contracts-upgradeable/...`) — 레이아웃은 npm 패키지와 동일
    "openzeppelin-contracts-upgradeable/": "ozu",
    # w34: v4-core@35b00f7 package.json 이 고정한 버전 (owner-manager 1.1.0, rng 1.4.0)
    "@pooltogether/owner-manager-contracts/": NPM / "@pooltogether" / "owner-manager-contracts",
    "@pooltogether/pooltogether-rng-contracts/": NPM / "@pooltogether" / "pooltogether-rng-contracts",
    # w17: code-423n4/2021-06-gro package.json 고정 버전 0.0.11
    "@chainlink/contracts/": NPM / "@chainlink" / "contracts",
}
NPM_PREFIXES = tuple(NPM_MAP)

# 순환 import 가 있는 프로젝트. solc 는 `import "X";` 로 X 가 *다시 import 한* 심볼까지 가져오지만, 순환이
# 있으면 처리 순서에 따라 전이 심볼이 빠질 수 있다(IBasket → IAuction → IFactory 에서 IFactory.Proposal 미해결).
# 원 프로젝트는 hardhat 이 저장소 전체를 한 번에 컴파일해 통과했으므로, 같은 파일 집합(contest 디렉토리의
# 나머지 소스)을 함께 넣는다. 타겟 바이트코드와는 무관하다.
INCLUDE_SIBLINGS = {"w36", "w65"}

# 저장소 루트 기준(non-relative) import 를 쓰는 프로젝트 (hardhat 의 `contracts/...` 식). 이 접두어를 src 루트로
# 보고 해석하고, 같은 접두어를 `src/` 로 remapping 한다. flatten 이름(common_FixedContracts.sol)이 접두어 아래 경로다.
ROOT_IMPORT_PREFIX = {"w17": "contracts/"}

# 타겟의 가상 경로를 수동으로 고정해야 할 때 (case_id → src 루트 기준 경로). 현재는 비어 있다 —
# 다른 파일이 타겟을 import 하는 경우는 내용 비교(alias)로 자동 처리된다 (w16 LibBalances, w35 Ticks, w77 MathLib).
TARGET_VPATH = {}


def read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def case_rows():
    return list(csv.DictReader(open(DS / "cases74.csv", encoding="utf-8")))


def orig_name(cid):
    return "numscout_SwordCrowdsale" if cid == "flyinointment_SwordCrowdsale" else cid


NUMSCOUT_ORIG = ROOT / "Dataset" / "Numscout" / "Original"       # Etherscan 검증 원문 (IntentKeeper 안)
SWORD_SIMPLE = ROOT.parent / "SolidityGuardian" / "Dataset" / "flyinointment" / "greedy_contract" / "SwordCrowdsale_simple.sol"


def replay_records(recs):
    """레코드를 에디터 삽입 순서대로 재생해 소스를 복원한다 (code 를 그냥 이어붙이면 `{`/`}` 가 깨진다)."""
    lines = []
    for r in recs:
        n = r["endLine"] - r["startLine"] + 1
        chunk = r["code"].split("\n")[:n]
        chunk += [""] * (n - len(chunk))
        lines[r["startLine"] - 1:r["startLine"] - 1] = chunk
    return "\n".join(lines) + "\n"


def load_target(row):
    """타겟 원본 소스.
    numscout: target_original/ 의 .sol/.json 은 IntentChecker 가 **축약·전개한 형태**라 solc 가 못 읽는다
      (주석 제거, 함수 탈락, 한 줄 블록 전개). Etherscan 검증 원문(Dataset/Numscout/Original)을 쓴다.
      SwordCrowdsale 은 원문이 어디에도 없어 flyinointment 의 단순화 재현본(35줄)으로 대체한다 — 논문에 명시.
    web3bugs: target_original/<case>.sol 이 code4rena 저장소 파일 그대로다."""
    cid = row["case_id"]
    if cid.startswith("web3bugs_"):
        return read(DS / "target_original" / (cid + ".sol"))
    name = row["contract"]
    cands = sorted(NUMSCOUT_ORIG.glob(f"*_{name}.sol")) if NUMSCOUT_ORIG.exists() else []
    if cands:
        return read(cands[0])
    if name == "SwordCrowdsale" and SWORD_SIMPLE.exists():
        return read(SWORD_SIMPLE)
    n = orig_name(cid)
    f = DS / "target_original" / (n + ".sol")
    if f.exists():
        return read(f)
    return replay_records(json.loads(read(DS / "target_original" / (n + ".json"))))


def contest_id(row):
    m = re.match(r"web3bugs_(\d+)_", row["case_id"])
    return m.group(1) if m else None


DECL = re.compile(r"^\s*(?:abstract\s+)?(?:contract|library|interface)\s+(\w+)", re.M)


def target_file_stem(row, content):
    """타겟 파일 이름. cases48.csv 의 contract 열이 실제 선언과 다를 수 있다(w77: 표는 Exchange, 파일은
    `library MathLib`). 선언된 이름을 우선하고, 표의 이름이 선언돼 있으면 그것을 쓴다."""
    names = DECL.findall(content)
    if row["contract"] in names or not names:
        return row["contract"]
    return names[-1] if len(names) > 1 and names[-1] != "" else names[0]


def project_key(row):
    c = contest_id(row)
    return f"w{c}" if c else f"n_{row['contract']}"


# ── 소스 풀 색인 ─────────────────────────────────────────────────────────
class Pool:
    def __init__(self):
        self.pool = collections.defaultdict(list)       # basename → [paths]  (Dependencies/pool)
        self.pool_pref = {}                             # "{id}_{base}" → path
        for p in (DS / "Dependencies" / "pool").glob("*.sol"):
            m = re.match(r"^(\d+)_(.+\.sol)$", p.name)
            if m:
                self.pool_pref[p.name] = p
                self.pool[m.group(2)].append(p)
            else:
                self.pool[p.name].append(p)
        self.tree = collections.defaultdict(list)       # basename → [paths]  (contracts/interfaces/libraries)
        for sub in ("contracts", "interfaces", "libraries"):
            for p in (DS / "Dependencies" / sub).rglob("*.sol"):
                self.tree[p.name].append(p)
        self.recon = {p.name: p for p in (DS / "Dependencies" / "reconstructed").glob("*.sol")}
        # 풀에 그 contest 버전이 없어 원 저장소에서 받아온 파일 ({id}_{Name}.sol, 출처는 fetched/FETCHED.txt)
        for p in (DS / "Dependencies" / "fetched").glob("*.sol"):
            self.pool_pref.setdefault(p.name, p)
        # flatten 구조 힌트: contest id → {flat name → path}
        self.flat = collections.defaultdict(dict)
        for w3b in W3B_CANDIDATES:
            if not w3b.exists():
                continue
            for d in w3b.glob("*/contest_*"):
                m = re.match(r"contest_(\d+)_", d.name)
                if not m:
                    continue
                for p in d.glob("*.sol"):
                    self.flat[m.group(1)].setdefault(p.name, p)

    def vpath_for_contract(self, cid, contract):
        """flatten 디렉토리에서 <dir>_<Contract>.sol 을 찾아 원본 가상 경로(dir/Contract.sol)를 돌려준다."""
        for name in self.flat.get(cid, {}):
            if name == contract + ".sol":
                return name
            if name.endswith("_" + contract + ".sol"):
                return name[: -len(contract) - 5].replace("_", "/") + "/" + contract + ".sol"
        return None

    def resolve(self, cid, vpath, base, gen="4"):
        """가상 경로 vpath 의 내용을 가진 실제 파일 → (출처 태그, 경로). 못 찾으면 (None, None).
        우선순위: 그 contest 의 사본(flat / {id}_base / contracts/<id>/) → npm 벤더 경로 → 범용 풀."""
        flat = vpath.replace("/", "_")
        if cid and flat in self.flat.get(cid, {}):
            return "flat", self.flat[cid][flat]
        if cid and f"{cid}_{base}" in self.pool_pref:
            return "pool-pref", self.pool_pref[f"{cid}_{base}"]
        # 저장소 안에 npm 패키지를 벤더링한 경우 (w31: `../deps/@openzeppelin/...`) → 공용 npm 사본.
        # (w47 처럼 그 contest 전용 수정본이 풀에 있으면 위에서 먼저 잡힌다.)
        for pref, tgt in NPM_MAP.items():
            i = vpath.find(pref)
            if i >= 0:
                if tgt == "oz":
                    tgt = NPM / f"oz{gen}"
                elif tgt == "ozu":
                    tgt = NPM / f"ozu{gen}"
                p = tgt / vpath[i + len(pref):]
                if p.exists():
                    return "npm-path", p
        if base in self.pool:
            return "pool", self.pool[base][0]
        # Guardian Dependencies 트리(contracts/interfaces/libraries)는 pkl 분석용으로 **import 가 제거되거나
        # 축약된 사본**이 섞여 있다(51/LPToken.sol, IBentoBoxV1.sol). 다른 출처가 전부 없을 때만 쓰고 보고한다.
        if cid:
            for p in self.tree.get(base, []):
                if p.parent.name == cid:                 # Dependencies/contracts/<id>/<base>
                    return "tree-id", p
        if base in self.tree:
            return "tree", self.tree[base][0]
        if base in self.recon:
            return "reconstructed", self.recon[base]
        if base == "console.sol":
            return "hardhat", HH_NPM / "hardhat" / "console.sol"
        return None, None


def solc_generation(sources: dict) -> str:
    """프로젝트의 OZ 세대: 0.8 pragma 가 하나라도 있으면 4.x, 아니면 3.x"""
    for s in sources.values():
        m = PRAGMA.search(s)
        if m and "0.8." in m.group(1):
            return "4"
    return "3"


def no_pragma(sources: dict) -> bool:
    return all(not PRAGMA.search(s) for s in sources.values())


# ── 프로젝트 재조립 ──────────────────────────────────────────────────────
def assemble(rows, cid, pool: Pool, depth: int, gen: str, vpath_override=None):
    """타겟을 `_/`*depth 아래에 두고 import 를 재귀 해석한다. 결과와 함께 'src 루트 탈출' 여부를 돌려준다.
    vpath_override[case_id] 가 있으면 타겟을 그 경로에 둔다 (다른 파일이 타겟을 상대경로로 import 하는 경우)."""
    files = {}          # vpath → content
    origin = {}         # vpath → 출처 태그
    missing = []        # (from vpath, import string)
    conflicts = []
    npm_used = set()
    work = []
    escaped = False
    alias = {}          # case_id → 다른 파일이 타겟을 참조한 가상 경로
    prefix = "/".join(["_"] * depth)
    vpath_override = vpath_override or {}
    root_pref = ROOT_IMPORT_PREFIX.get(project_key(rows[0]))

    # 1) 타겟 배치 — alias 재시도 경로 > 수동 고정(TARGET_VPATH) > flatten 힌트 > Contract.sol. prefix 아래.
    for r in rows:
        content = load_target(r)
        if r["case_id"] in vpath_override:
            vp = vpath_override[r["case_id"]]
        elif r["case_id"] in TARGET_VPATH:
            vp = TARGET_VPATH[r["case_id"]]            # src 루트 기준 절대 가상경로 — depth prefix 를 붙이지 않는다
        else:
            stem = target_file_stem(r, content)
            vp = pool.vpath_for_contract(cid, stem) if cid else None
            if vp is None:
                vp = stem + ".sol"
            vp = posixpath.join(prefix, vp) if prefix else vp
        if vp in files and files[vp] != content:
            conflicts.append((vp, "target content differs between cases"))
        files[vp] = content
        origin[vp] = "target:" + r["case_id"]
        work.append(vp)

    # 2) import 재귀 해석
    seen = set()
    while work:
        vp = work.pop()
        if vp in seen:
            continue
        seen.add(vp)
        for imp in IMP.findall(files[vp]):
            if imp.startswith(NPM_PREFIXES):
                npm_used.add(next(p for p in NPM_PREFIXES if imp.startswith(p)))
                continue
            if root_pref and imp.startswith(root_pref):
                rel = imp[len(root_pref):]
                tgt = posixpath.join(prefix, rel) if prefix else rel
            elif not imp.startswith("."):
                missing.append((vp, imp + "  (non-relative, no remapping)"))
                continue
            else:
                tgt = posixpath.normpath(posixpath.join(posixpath.dirname(vp), imp))
            if tgt.startswith(".."):
                escaped = True
                missing.append((vp, imp + "  (escapes src root)"))
                continue
            if tgt in files:
                continue
            base = posixpath.basename(tgt)
            tag, p = pool.resolve(cid, tgt, base, gen)
            # 다른 파일이 타겟을 상대경로로 참조 (Exchange.sol → ../libraries/MathLib.sol, Types.sol →
            # ../lib/LibBalances.sol). 복사하면 같은 심볼이 두 소스 단위에 생겨 "Identifier already declared" 가
            # 나므로, 타겟을 그 경로로 옮겨 다시 푼다. 데이터셋이 타겟 파일을 컨트랙트 이름으로 바꿔 저장했을 수
            # 있어(Balances.sol vs LibBalances.sol) 파일명이 아니라 **내용**으로 판별한다.
            resolved = read(p) if p is not None else None
            same = [v for v in files if origin[v].startswith("target:")
                    and (posixpath.basename(v) == base or (resolved is not None and files[v] == resolved))]
            if same:
                alias[origin[same[0]][len("target:"):]] = tgt
                files[tgt] = files[same[0]]
                origin[tgt] = "target-alias"
                work.append(tgt)
                continue
            if p is None:
                missing.append((vp, imp))
                continue
            src_tag = f"{tag}:{p.relative_to(ROOT).as_posix()}" if p.is_relative_to(ROOT) else f"{tag}:{p.as_posix()}"
            # 같은 실제 파일이 이미 다른 가상 경로에 놓였으면 → 두 소스 단위가 같은 심볼을 선언하게 된다
            # (solc 2333 Identifier already declared). 타겟 디렉토리 추정이 틀렸다는 신호라 conflict 로 보고한다.
            dup = [v for v, o in origin.items() if o == src_tag]
            if dup:
                conflicts.append((tgt, f"same source already placed at {dup[0]} (imported from {vp})"))
            files[tgt] = resolved
            origin[tgt] = src_tag
            work.append(tgt)
    return files, origin, missing, conflicts, npm_used, escaped, alias


def build_project(pkey, rows, pool: Pool, report):
    pdir = PROJ / pkey
    if pdir.exists():
        shutil.rmtree(pdir)
    src = pdir / "src"
    src.mkdir(parents=True)
    cid = contest_id(rows[0])
    gen = solc_generation({r["case_id"]: load_target(r) for r in rows})

    # depth-retry: `../` 가 src 루트를 벗어나면 타겟을 한 단계 더 깊이 두고 다시 푼다 (최대 4단).
    # alias-retry: 타겟이 다른 경로로 참조되면 그 경로를 타겟 위치로 삼아 다시 푼다 (최대 2회).
    override = {}
    for _ in range(3):
        for depth in range(0, 5):
            files, origin, missing, conflicts, npm_used, escaped, alias = assemble(rows, cid, pool, depth, gen, override)
            if not escaped:
                break
        new = {k: v for k, v in alias.items() if override.get(k) != v}
        if not new:
            break
        override.update(new)
    # alias 로 옮긴 뒤에도 남은 target-alias 사본은 제거 (타겟 본체가 그 경로에 있다)
    for vp in [v for v, o in origin.items() if o == "target-alias"]:
        if any(origin.get(ov) and origin[ov].startswith("target:") for ov in override.values() if ov == vp):
            continue
        del files[vp]
        del origin[vp]

    # 순환 import 프로젝트: contest 디렉토리의 나머지 소스를 flatten 이름을 풀어 같은 트리에 넣는다
    if pkey in INCLUDE_SIBLINGS and cid in pool.flat:
        prefix = "/".join(["_"] * depth)
        for flat_name, p in pool.flat[cid].items():
            vp = flat_name[:-4].replace("_", "/") + ".sol"
            vp = posixpath.join(prefix, vp) if prefix else vp
            if vp not in files:
                files[vp] = read(p)
                origin[vp] = f"sibling:{p.as_posix()}"

    # 3) 기록
    for vp, content in files.items():
        out = src / vp
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")

    remaps = []
    for pref in sorted(npm_used):
        tgt = NPM_MAP[pref]
        if tgt == "oz":
            tgt = NPM / f"oz{gen}"
        elif tgt == "ozu":
            tgt = NPM / f"ozu{gen}"
        rel = posixpath.relpath(tgt.as_posix(), pdir.as_posix())
        remaps.append(f"{pref}={rel}/")
    if pkey in ROOT_IMPORT_PREFIX:
        root = posixpath.join("src", "/".join(["_"] * depth)) if depth else "src"
        remaps.append(f"{ROOT_IMPORT_PREFIX[pkey]}={root}/")
    (pdir / "remappings.txt").write_text("\n".join(remaps) + ("\n" if remaps else ""), encoding="utf-8")

    toml = [
        "[profile.default]",
        'src = "src"',
        'out = "out"',
        "libs = []",
        "cache = true",
        "optimizer = false",
        'allow_paths = ["../../npm", "../../../hardhat"]',
    ]
    if no_pragma(files):
        toml.append('solc_version = "0.4.26"')           # numscout_HIT: pragma 없는 0.4 코드
    else:
        toml.append("auto_detect_solc = true")
    (pdir / "foundry.toml").write_text("\n".join(toml) + "\n", encoding="utf-8")

    report[pkey] = {
        "cases": [r["case_id"] for r in rows],
        "contest": cid,
        "files": len(files),
        "depth": depth,
        "vpath_override": override,
        "oz_generation": gen,
        "npm": sorted(npm_used),
        "missing": missing,
        "conflicts": conflicts,
        "origin_counts": dict(collections.Counter(o.split(":")[0] for o in origin.values())),
    }


# auto-detect 는 pragma 범위를 만족하는 **최신** solc 를 고른다. 2021~22년 코드는 그 뒤에 엄격해진 검사
# (SPDX 식별자 유효성, NatSpec @custom 태그 등)에 걸릴 수 있어, 실패하면 그 시대의 버전을 순서대로 핀해 본다.
SOLC_FALLBACK = {"4": ["0.8.4", "0.8.7", "0.8.9", "0.8.10", "0.8.13"], "3": ["0.6.12", "0.7.6", "0.7.4"]}


def _run_forge(forge_exe, pdir, use=None):
    cmd = [str(forge_exe), "build", "--root", str(pdir)] + (["--use", use] if use else [])
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    text = proc.stdout + proc.stderr
    errs = [l.strip() for l in text.splitlines() if re.match(r"^\s*(Error|error\[|.*Error:)", l)]
    return proc.returncode == 0, errs[:3], text


def forge_build(pkey, forge_exe, gen):
    pdir = PROJ / pkey
    log = []
    ok, errs, text = _run_forge(forge_exe, pdir)
    log.append("### auto-detect\n" + text)
    used = "auto"
    if not ok:
        for v in SOLC_FALLBACK[gen]:
            ok2, errs2, text2 = _run_forge(forge_exe, pdir, v)
            log.append(f"### --use {v}\n" + text2)
            if ok2:
                ok, errs, used = True, [], v
                break
    (pdir / "build.log").write_text("\n".join(log), encoding="utf-8")
    return ok, errs, used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="재조립 후 forge build 게이트까지 실행")
    ap.add_argument("--only", help="프로젝트 키 하나만 (예 w45)")
    a = ap.parse_args()

    by_proj = collections.defaultdict(list)
    for r in case_rows():
        by_proj[project_key(r)].append(r)
    pool = Pool()
    report = {}
    PROJ.mkdir(exist_ok=True)
    for pkey, prows in sorted(by_proj.items()):
        if a.only and pkey != a.only:
            continue
        build_project(pkey, prows, pool, report)
        rep = report[pkey]
        flag = ""
        if rep["missing"]:
            flag = f"  MISSING {len(rep['missing'])}: " + "; ".join(f"{v}→{i}" for v, i in rep["missing"][:3])
        if rep["conflicts"]:
            flag += f"  CONFLICT {len(rep['conflicts'])}: " + "; ".join(f"{v}: {m}" for v, m in rep["conflicts"][:2])
        npm_s = ",".join(p.rstrip("/") for p in rep["npm"]) or "-"
        print(f"{pkey:<20} cases={len(prows)} files={rep['files']:3d} oz={rep['oz_generation']} npm={npm_s}{flag}")

    if a.build:
        forge = ROOT / "evaluation" / "forge" / "bin" / "forge.exe"
        print("\n=== forge build 게이트 ===")
        ok_cases = 0
        for pkey in sorted(report):
            ok, errs, used = forge_build(pkey, forge, report[pkey]["oz_generation"])
            report[pkey]["build_ok"] = ok
            report[pkey]["build_errors"] = errs
            report[pkey]["solc"] = used
            n = len(report[pkey]["cases"])
            ok_cases += n if ok else 0
            tag = f"OK   solc={used}" if ok else "FAIL"
            print(f"{pkey:<20} {tag:<16} ({n} cases)" + ("" if ok else "  " + " | ".join(errs)))
        total = sum(len(v["cases"]) for v in report.values())
        print(f"\n컴파일 통과 케이스: {ok_cases}/{total}")

    # --only 는 그 프로젝트 항목만 갱신한다 (보고서 전체를 한 프로젝트로 덮어쓰지 않는다)
    rpath = DS / "reassemble_report.json"
    if a.only and rpath.exists():
        merged = json.loads(rpath.read_text(encoding="utf-8"))
        merged.update(report)
        report = merged
    rpath.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
