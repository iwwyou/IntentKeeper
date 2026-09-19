"""
Collect dependency information (import paths, pragma versions) for all 81
Web3Bugs target contracts in evaluation/RQ1/target_contracts/.

For each web3bugs_*.sol file this script extracts:
  - All import paths (both plain and destructured `import { X } from "path"`)
  - The pragma solidity version string

Data structures produced:
  DEPENDENCIES    : dict[str, list[str]]   contract_id -> [import_path, ...]
  PRAGMA_VERSIONS : dict[str, str]         contract_id -> solidity_version

When executed directly the script prints comprehensive summary statistics:
  - Total contracts / unique import paths
  - Imports grouped by category (@openzeppelin, @uniswap, hardhat, etc.)
  - Contracts that use hardhat/console.sol (flagged for removal)
  - Pragma version distribution
"""

import os
import re
from collections import defaultdict

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_DIR = os.path.join(BASE_DIR, "target_contracts")

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
# Matches both:
#   import "path";
#   import { X, Y } from "path";
#   import { X, Y } from 'path';
# The path may use single or double quotes.
IMPORT_RE = re.compile(
    r"""import\s+          # keyword
        (?:\{[^}]*\}\s+from\s+)?   # optional destructured symbols
        ["']([^"']+)["']           # quoted import path (capture group 1)
    """,
    re.VERBOSE | re.MULTILINE,
)

PRAGMA_RE = re.compile(
    r"pragma\s+solidity\s+([^;]+);",
    re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Import category classification
# ---------------------------------------------------------------------------
CATEGORY_RULES = [
    # (label, match function)
    ("@openzeppelin",           lambda p: p.startswith("@openzeppelin/")),
    ("@openzeppelin (deps/)",   lambda p: "@openzeppelin/" in p and not p.startswith("@openzeppelin/")),
    ("openzeppelin-contracts-upgradeable",
                                lambda p: p.startswith("openzeppelin-contracts-upgradeable/")),
    ("@boringcrypto",           lambda p: p.startswith("@boringcrypto/")),
    ("@sushiswap",              lambda p: p.startswith("@sushiswap/")),
    ("@pooltogether",           lambda p: p.startswith("@pooltogether/")),
    ("@mochifi",                lambda p: p.startswith("@mochifi/")),
    ("@uniswap",                lambda p: p.startswith("@uniswap/")),
    ("hardhat/console.sol",     lambda p: p == "hardhat/console.sol" or p == "./hardhat/console.sol"),
    ("solmate",                 lambda p: p.startswith("solmate/")),
    ("prb-math",                lambda p: p.startswith("prb-math/")),
    ("contracts/ (project-level)", lambda p: p.startswith("contracts/")),
    ("local/relative",          lambda p: p.startswith("./") or p.startswith("../")),
]


def classify_import(path: str) -> str:
    """Return a human-readable category for an import path."""
    for label, matcher in CATEGORY_RULES:
        if matcher(path):
            return label
    # Fallback: anything else that starts with a package-like name
    return "other"


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def extract_imports(filepath: str) -> list[str]:
    """Return the list of raw import path strings found in *filepath*."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except Exception:
        return []
    return IMPORT_RE.findall(content)


def extract_pragma(filepath: str) -> str | None:
    """Return the pragma solidity version string, or None."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except Exception:
        return None
    m = PRAGMA_RE.search(content)
    return m.group(1).strip() if m else None


# ---------------------------------------------------------------------------
# Build the two main dictionaries
# ---------------------------------------------------------------------------
def _contract_id_from_filename(filename: str) -> str:
    """'web3bugs_35_H_12.sol' -> 'web3bugs_35_H_12'"""
    return os.path.splitext(filename)[0]


def build_data() -> tuple[dict[str, list[str]], dict[str, str | None]]:
    """
    Scan all web3bugs_*.sol files in TARGET_DIR and return
    (DEPENDENCIES, PRAGMA_VERSIONS).
    """
    deps: dict[str, list[str]] = {}
    pragmas: dict[str, str | None] = {}

    sol_files = sorted(
        f for f in os.listdir(TARGET_DIR)
        if f.startswith("web3bugs_") and f.endswith(".sol")
    )

    for fname in sol_files:
        cid = _contract_id_from_filename(fname)
        fpath = os.path.join(TARGET_DIR, fname)
        deps[cid] = extract_imports(fpath)
        pragmas[cid] = extract_pragma(fpath)

    return deps, pragmas


# Build at import time so other modules can do:
#   from collect_dependencies import DEPENDENCIES, PRAGMA_VERSIONS
DEPENDENCIES, PRAGMA_VERSIONS = build_data()

# ---------------------------------------------------------------------------
# Pretty-printing helpers
# ---------------------------------------------------------------------------
_SEPARATOR = "=" * 78


def _print_header(title: str) -> None:
    print()
    print(_SEPARATOR)
    print(f"  {title}")
    print(_SEPARATOR)


def print_summary() -> None:
    """Print comprehensive statistics about extracted dependency data."""

    # ------------------------------------------------------------------
    # 1. Basic counts
    # ------------------------------------------------------------------
    _print_header("DEPENDENCY EXTRACTION SUMMARY")
    total_contracts = len(DEPENDENCIES)
    all_import_paths = [p for paths in DEPENDENCIES.values() for p in paths]
    unique_imports = sorted(set(all_import_paths))

    print(f"\n  Total web3bugs contracts scanned : {total_contracts}")
    print(f"  Total import statements          : {len(all_import_paths)}")
    print(f"  Unique import paths              : {len(unique_imports)}")

    # ------------------------------------------------------------------
    # 2. Categorise every import occurrence
    # ------------------------------------------------------------------
    cat_to_paths: dict[str, set[str]] = defaultdict(set)
    cat_to_contracts: dict[str, set[str]] = defaultdict(set)

    for cid, paths in DEPENDENCIES.items():
        for p in paths:
            cat = classify_import(p)
            cat_to_paths[cat].add(p)
            cat_to_contracts[cat].add(cid)

    _print_header("IMPORTS BY CATEGORY")
    # Sort categories by number of unique paths (descending)
    for cat in sorted(cat_to_paths, key=lambda c: -len(cat_to_paths[c])):
        paths = sorted(cat_to_paths[cat])
        n_contracts = len(cat_to_contracts[cat])
        print(f"\n  [{cat}]  ({len(paths)} unique paths, used by {n_contracts} contracts)")
        for p in paths:
            print(f"    - {p}")

    # ------------------------------------------------------------------
    # 3. Flag hardhat/console.sol usage
    # ------------------------------------------------------------------
    _print_header("HARDHAT/CONSOLE.SOL USAGE  (needs removal)")
    console_contracts = sorted(
        cid for cid, paths in DEPENDENCIES.items()
        if any(
            p == "hardhat/console.sol" or p == "./hardhat/console.sol"
            for p in paths
        )
    )
    if console_contracts:
        print(f"\n  {len(console_contracts)} contracts import hardhat/console.sol:\n")
        for cid in console_contracts:
            print(f"    - {cid}")
    else:
        print("\n  No contracts import hardhat/console.sol.")

    # ------------------------------------------------------------------
    # 4. Pragma version distribution
    # ------------------------------------------------------------------
    _print_header("PRAGMA SOLIDITY VERSION DISTRIBUTION")
    version_counts: dict[str, list[str]] = defaultdict(list)
    no_pragma: list[str] = []
    for cid, ver in sorted(PRAGMA_VERSIONS.items()):
        if ver:
            version_counts[ver].append(cid)
        else:
            no_pragma.append(cid)

    for ver in sorted(version_counts, key=lambda v: (-len(version_counts[v]), v)):
        cids = version_counts[ver]
        print(f"\n  {ver:25s}  ({len(cids)} contracts)")
        for cid in sorted(cids):
            print(f"    - {cid}")

    if no_pragma:
        print(f"\n  <no pragma>  ({len(no_pragma)} contracts)")
        for cid in no_pragma:
            print(f"    - {cid}")

    # ------------------------------------------------------------------
    # 5. Contracts with no imports at all
    # ------------------------------------------------------------------
    no_imports = sorted(cid for cid, paths in DEPENDENCIES.items() if not paths)
    if no_imports:
        _print_header("CONTRACTS WITH NO IMPORTS")
        for cid in no_imports:
            print(f"    - {cid}")

    # ------------------------------------------------------------------
    # 6. Per-contract detail table
    # ------------------------------------------------------------------
    _print_header("PER-CONTRACT DETAIL")
    for cid in sorted(DEPENDENCIES):
        paths = DEPENDENCIES[cid]
        pragma = PRAGMA_VERSIONS.get(cid, "N/A")
        print(f"\n  {cid}  (pragma solidity {pragma})")
        if paths:
            for p in paths:
                cat = classify_import(p)
                flag = "  ** HARDHAT **" if cat == "hardhat/console.sol" else ""
                print(f"    import \"{p}\"  [{cat}]{flag}")
        else:
            print("    (no imports)")

    # ------------------------------------------------------------------
    # 7. Compact category counts summary
    # ------------------------------------------------------------------
    _print_header("CATEGORY SUMMARY (compact)")
    print(f"\n  {'Category':<45s} {'Unique paths':>14s} {'Contracts':>11s}")
    print(f"  {'-'*45} {'-'*14} {'-'*11}")
    for cat in sorted(cat_to_paths, key=lambda c: -len(cat_to_paths[c])):
        print(
            f"  {cat:<45s} {len(cat_to_paths[cat]):>14d} {len(cat_to_contracts[cat]):>11d}"
        )
    total_unique = len(unique_imports)
    print(f"  {'TOTAL':<45s} {total_unique:>14d} {total_contracts:>11d}")

    print(f"\n{_SEPARATOR}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print_summary()
