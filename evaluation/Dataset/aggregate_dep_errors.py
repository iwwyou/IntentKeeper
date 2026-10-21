# -*- coding: utf-8 -*-
"""
프로젝트 의존성 빌드(deps/<p>/build.log) 오류 집계 — 원인별 분류 + 예전 공용 트리와의 비교 (읽기 전용).

분류는 오류 메시지 패턴으로 하고, 각 오류 줄(`[ERR] L<n>`)의 실제 소스 줄을 deps/<p>/<kind>/<File>.sol 에서 붙여 근거로 남긴다.
"연쇄" 오류(앞선 함수 헤더 실패로 함수 문맥이 없어서 나는 것)는 1차 원인과 분리해 센다.

출력: deps/error_aggregate.json (기계용), 콘솔 요약
사용: .venv/Scripts/python.exe evaluation/Dataset/aggregate_dep_errors.py
"""
import collections
import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DS = pathlib.Path(__file__).resolve().parent
ROOT = DS.parents[1]
DEPS = DS / "deps"
OLD_DIRS = [ROOT / "Dependencies" / d for d in ("interfaces", "libraries", "contracts")]

# (카테고리, 정규식) — 먼저 맞는 것
CATS = [
    ("grammar_sol04", r"extraneous input 'constant'|no viable alternative at input 'function\(\)"),
    ("overload_internal_call", r"Argument count mismatch in function call to"),
    ("assert_single_arg", r"process_assert_statement\(\) missing 1 required positional argument"),
    ("address_builtin_member", r"unresolved member '\.(transfer|send|call|staticcall|delegatecall|code|codehash)'"),
    ("bytes_length_member", r"unresolved member '\.length'"),
    ("contract_cast_or_using_for", r"unresolved member '\.\w+' on (UnsignedIntegerInterval|NoneType)"),
    ("ext_return_unresolved", r"external call return type unresolved"),
    ("interval_width_join", r"Cannot join intervals of different type lengths"),
    ("try_catch", r"add_control_flow_node"),
    ("modifier_not_defined", r"Modifier '\w+' is not defined"),
    ("type_not_defined", r"is not defined as struct, enum, or type alias|not found in library"),
    ("cascade_no_function", r"No active function CFG|active FunctionCFG not found|No active FunctionCFG|Function context not found|"
                            r"may be elementary variable but may not be declared|No CFG node found"),
    ("antlr_other", r"mismatched input|extraneous input|no viable alternative"),
]


def classify(msg):
    for cat, pat in CATS:
        if re.search(pat, msg):
            return cat
    return "other"


def old_index():
    idx = collections.defaultdict(list)
    for d in OLD_DIRS:
        for p in d.rglob("*.sol"):
            t = p.read_text(encoding="utf-8", errors="ignore")
            for name in re.findall(r"^\s*(?:abstract\s+)?(?:contract|library|interface)\s+(\w+)", t, re.M):
                idx[name].append(p)
    return idx


def norm(t):
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
    return re.sub(r"\s+", "", re.sub(r"//[^\n]*", "", t))


def main():
    oidx = old_index()
    rows = []
    for pdir in sorted(p for p in DEPS.iterdir() if (p / "build.log").exists()):
        cur = None
        for line in (pdir / "build.log").read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(r"\[(\w+)\] 분석: (.+\.sol)", line)
            if m:
                cur = m.group(2)
                continue
            if not cur or not re.search(r"\[ERR\]|\[UPDATE_CODE ERR\]|\[ANTLR\]", line):
                continue
            lm = re.search(r"\bL(\d+)\b", line)
            src = next((pdir / k / cur for k in ("interfaces", "libraries", "contracts") if (pdir / k / cur).exists()), None)
            code = ""
            if src and lm:
                ls = src.read_text(encoding="utf-8").splitlines()
                n = int(lm.group(1))
                code = ls[n - 1].strip() if 0 < n <= len(ls) else ""
            msg = re.sub(r"^\s*\[(ERR|UPDATE_CODE ERR|ANTLR)\]\s*(L\d+\s*)?(ctx=\w+:\s*)?", "", line.strip())
            rows.append({"project": pdir.name, "file": cur, "line": int(lm.group(1)) if lm else None,
                         "cat": classify(line), "msg": msg[:200], "code": code[:160]})
    # 예전 트리와 비교 (파일 단위)
    files = {(r["project"], r["file"]) for r in rows}
    origin = {}
    for proj, f in files:
        name = f[:-4]
        new = next((DEPS / proj / k / f for k in ("interfaces", "libraries", "contracts") if (DEPS / proj / k / f).exists()), None)
        cands = oidx.get(name, [])
        pid = proj[1:] if proj.startswith("w") else None
        pref = [c for c in cands if c.parent.name == pid] or cands
        if not pref:
            origin[(proj, f)] = "new_file"
        else:
            origin[(proj, f)] = "same_as_old" if new and norm(new.read_text(encoding="utf-8")) == norm(
                pref[0].read_text(encoding="utf-8", errors="ignore")) else "differs_from_old"
    for r in rows:
        r["origin"] = origin[(r["project"], r["file"])]

    by_cat = collections.defaultdict(list)
    for r in rows:
        by_cat[r["cat"]].append(r)
    projects = sorted({r["project"] for r in rows})
    print(f"projects with build.log: {len(list(DEPS.glob('*/build.log')))}, with errors: {len(projects)}, error lines: {len(rows)}")
    for cat, lst in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        ps = sorted({r["project"] for r in lst})
        oc = collections.Counter(r["origin"] for r in lst)
        print(f"\n## {cat}: {len(lst)} lines / {len(ps)} projects / {len({(r['project'], r['file']) for r in lst})} files  origin={dict(oc)}")
        for msg, n in collections.Counter(re.sub(r"0x[0-9A-F]+|\d{5,}", "#", r["msg"]) for r in lst).most_common(3):
            print(f"   {n:3d}x {msg[:140]}")
        ex = lst[0]
        print(f"   e.g. {ex['project']}/{ex['file']}:L{ex['line']}  {ex['code']!r}")
    (DEPS / "error_aggregate.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
