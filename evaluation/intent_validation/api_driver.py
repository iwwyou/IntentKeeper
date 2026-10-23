# -*- coding: utf-8 -*-
"""평가 드라이버 — **도구와 같은 경로**(engine_api: analyze → evaluate → verify)로 케이스를 돌린다 (2026-10-22, 사용자 결정).

예전 드라이버(run_cases.run_one / baseline_cases.run_one)는 케이스 JSON 의 옛 어노테이션 줄(`// @Post …`, `// @StateVar …`)을
소스 줄처럼 재생했다. 그 경로는 프론트(디버거)가 쓰는 경로와 달랐고, 줄 기반 @Post 부착이 **마지막으로 처리한 함수**에 붙는
결함으로 12 케이스의 @Post 판정이 빠져 있었다. 이제 케이스를 도구 입력으로 바꿔 넣는다:

  · 소스      = evaluation/Dataset/target_contraction_auto/<case>.sol (cases_rebuilt 의 코드 record 와 같은 원문)
  · 대상 함수 = cases74.csv 의 contract / function
  · 디버그 값 = 케이스의 `@StateVar/@LocalVar(@Param)/@GlobalVar/@IReturn 키 = 값` → engine_api 슬롯 키 → RangeValue.
                엔진이 도출한 슬롯에 없는 키는 **slot_missing** 으로 보고하고 넣지 않는다(프론트 사용자도 입력할 수 없는 값).
  · intent    = `@During` → IntentItem(During, 줄 = 케이스 record 의 줄 = 앵커 문장 줄), `@Post` → IntentItem(Post)
                (rebuild_cases: @During 은 원문 줄 번호의 앵커 문장에 인라인으로 붙어 있다)

의존성 = 프로젝트 단위 deps(evaluation/Dataset/deps/<p>), 타깃이 스스로 선언하는 이름은 제외(run_cases.declared_names 와 같은 규칙).
"""
import csv
import json
import pathlib
import re
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DS = ROOT / "evaluation" / "Dataset"
AUTO = DS / "target_contraction_auto"
REBUILT = HERE / "cases_rebuilt"

_ANN = re.compile(r"^\s*(?://\s*)?@(\w+)\s*(.*)$", re.S)
_DEBUG_KIND = {"StateVar": "StateVar", "LocalVar": "Param", "Param": "Param", "GlobalVar": "GlobalVar",
               "IReturn": "IReturn"}


def case_row(cid: str) -> dict:
    return next(r for r in csv.DictReader(open(DS / "cases74.csv", encoding="utf-8")) if r["case_id"] == cid)


def declared_names(src: str) -> list[str]:
    text = re.sub(r"//[^\n]*", "", src)
    return sorted(set(re.findall(r"^\s*(?:abstract\s+)?(?:contract|library|interface)\s+(\w+)", text, re.M)))


def parse_value(text: str) -> dict:
    """케이스 값 텍스트 → RangeValue(engine_api / frontend 계약)."""
    t = text.strip()
    m = re.fullmatch(r"\[\s*(-?\d+)\s*,\s*(-?\d+)\s*\]", t)
    if m:
        return {"t": "interval", "lo": m.group(1), "hi": m.group(2)}
    if t in ("true", "false", "any"):
        return {"t": "bool", "v": t}
    m = re.fullmatch(r"symbolicAddress\s+(\d+)", t)
    if m:
        return {"t": "address", "id": int(m.group(1))}
    raise ValueError(f"지원하지 않는 디버그 값 형식: {t!r}")


def case_inputs(cid: str):
    """→ (source, debug: [(kind, key, RangeValue)], intents: [(scopeKind, text, line)])"""
    source = (AUTO / f"{cid}.sol").read_text(encoding="utf-8")
    recs = json.loads((REBUILT / f"{cid}.json").read_text(encoding="utf-8"))
    debug, intents = [], []
    for r in recs:
        m = _ANN.match(r["code"])
        if not m:
            continue
        kind, rest = m.group(1), m.group(2).strip()
        if kind == "Debugging":
            continue
        if kind in ("During", "Post"):
            intents.append((kind, rest, r["startLine"]))
        elif kind in _DEBUG_KIND:
            key, _, val = rest.partition("=")
            debug.append((_DEBUG_KIND[kind], key.strip(), parse_value(val)))
        else:
            raise ValueError(f"알 수 없는 어노테이션 @{kind}")
    return source, debug, intents


def run_case(cid: str, deps_root: pathlib.Path) -> dict:
    """한 케이스를 engine_api 로. 반환: results / verdict 입력 / slot_missing / runs(노드 상태 덤프) / error / elapsed_s"""
    sys.path.insert(0, str(ROOT))
    import engine_api
    row = case_row(cid)
    contract, func = row["contract"], row["function"]
    out = {"results": [], "runs": [], "slot_missing": [], "error": None}
    t0 = time.perf_counter()
    try:
        source, debug, intents = case_inputs(cid)
        sess = engine_api.EngineSession(str(deps_root), tuple(declared_names(source)))
        st = sess.analyze_source(source, contract=contract, func=func)
        if st.diagnostics:
            raise RuntimeError("analyze diagnostics: " + "; ".join(f"L{d.line}: {d.message}" for d in st.diagnostics))
        values = {}
        out["kind_mismatch"] = []
        for kind, key, val in debug:
            # 슬롯 키 그대로이거나, 경로 슬롯의 인덱스 자리만 구체값으로 바꾼 키(`_pairs[0].token0` ↔ `_pairs[i].token0`)
            #   — 프론트 사용자와 같은 규칙(EngineSession.match_slot, 2026-10-23)
            s = sess.match_slot(key)
            if s is None or (s.key == key and s.requiresIndex):
                out["slot_missing"].append(f"@{kind} {key}")
                continue
            # 케이스의 종류 표기(@StateVar/@LocalVar …)는 IntentChecker 시절 것 — 슬롯은 키로 식별하고 종류는 엔진 것을 쓴다
            #   (예: 라이브러리 함수의 storage 파라미터 `self.x` 는 케이스에선 @StateVar, 엔진 슬롯은 Param).
            if s.kind != kind:
                out["kind_mismatch"].append(f"@{kind} {key} → slot {s.kind}")
            values[key] = val
        items = [engine_api.IntentItem(scopeKind=k, text=t, line=(ln if k == "During" else None))
                 for k, t, ln in intents]
        ev = sess.evaluate(values, contract=contract, func=func)
        vr = sess.verify(items, contract=contract, func=func, debug_values=values)
        diags = list(getattr(ev, "diagnostics", []) or [])
        if diags:
            out["diagnostics"] = [f"L{d.line}: {d.message}" for d in diags]
        out["results"] = [{"line": v.line, "type": v.type, "status": v.status, "risk": v.risk,
                           "message": str(v.message)[:200]} for v in vr]
        names = {n.id: n.name for n in ev.cfg.nodes}
        succ: dict = {}
        for e in ev.cfg.edges:
            succ.setdefault(e.from_, []).append(names.get(e.to, e.to))
        out["runs"] = [{"function": func,
                        "nodes": {n.name: {"succ": sorted(succ.get(n.id, [])), "stmts": [], "state": n.state,
                                           "in_state": n.in_state}
                                  for n in ev.cfg.nodes}}]
    except Exception as ex:                                  # 결과로 보고만 한다 — 폴백 없음
        import traceback
        out["error"] = f"{type(ex).__name__}: {ex}\n" + traceback.format_exc()[-1500:]
    out["elapsed_s"] = round(time.perf_counter() - t0, 3)
    return out
