"""engine_server — engine_api 를 프론트(frontend/src/engine/analyzeClient.ts)에 노출하는 HTTP 서버.

3콜(analyze/evaluate/verify)을 세션 영속으로 묶는다(= dirty 신호 + 캐시 활용):
  * /analyze   — 코드 변경: 세션 재빌드(full source → slice → CFG 구조). 캐시 리셋.
  * /evaluate  — 값 변경  : 같은 세션 재사용 → fixpoint states (frozen 캐시).
  * /verify    — intent 변경: 같은 세션의 보존 states 에 standalone P2.
세션 키 = "contract.func". (단일 사용자 dev 도구 전제 — 동시성 잠금 없음.)

실행: .venv\Scripts\python.exe engine_server.py   (uvicorn, 포트 8000)
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from dataclasses import asdict

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from Dependencies.main import slice_solidity
import engine_api
from engine_api import EngineSession, IntentItem, to_analysis_result, _cfg_to_dict

app = FastAPI(title="IQDebug engine_api")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev: Vite(5173) 등 로컬 origin 허용
    allow_methods=["*"],
    allow_headers=["*"],
)

# 세션 키("contract.func") → EngineSession. analyze 가 재빌드, evaluate/verify 가 재사용.
_sessions: dict[str, EngineSession] = {}


class Req(BaseModel):
    contract: str
    func: str
    source: str = ""
    inputs: dict = {}     # slotKey → RangeValue
    intents: list = []    # [{scopeKind, text, line?}]


def _key(r: Req) -> str:
    return f"{r.contract}.{r.func}"


def _to_intents(items: list) -> list[IntentItem]:
    return [IntentItem(scopeKind=i["scopeKind"], text=i["text"], line=i.get("line"))
            for i in items]


def _build(r: Req):
    """새 세션 생성 + full source → slice → analyze 1회. (session, Structure) 반환.
    (analyze 를 같은 세션에 두 번 호출하면 records 이중 적용으로 손상 → 항상 fresh.)"""
    sess = EngineSession()
    _sessions[_key(r)] = sess
    st = sess.analyze(slice_solidity(r.source), contract=r.contract, func=r.func)
    return sess, st


def _session(r: Req) -> EngineSession:
    """기존 세션 재사용. 없으면(서버 재시작 등) source 로 lazy 빌드."""
    sess = _sessions.get(_key(r))
    if sess is None:
        sess, _ = _build(r)
    return sess


@app.get("/health")
def health() -> dict:
    return {"ok": True, "sessions": list(_sessions.keys())}


@app.post("/analyze")
def analyze(r: Req) -> dict:
    # B1: 첫 분석은 fresh 빌드, 이후 코드 변경은 같은 세션에 증분 update(SyntaxValid 게이트+diff apply).
    key = _key(r)
    sess = _sessions.get(key)
    if sess is None:
        sess, st = _build(r)
        diags = [asdict(d) for d in st.diagnostics]
    else:
        res = sess.update(r.source)         # invalid 면 상태 유지 + diagnostics 반환
        st = sess.structure()               # 갱신(또는 거부 시 직전) 구조 재직렬화
        diags = res["diagnostics"]          # [{line, column, message, severity}]
    return {
        "scope": asdict(st.scope),
        "cfg": _cfg_to_dict(st.cfg),
        "debugSlots": [asdict(s) for s in st.debug_slots],
        "diagnostics": diags,
    }


@app.post("/evaluate")
def evaluate(r: Req) -> dict:
    ev = _session(r).evaluate(r.inputs, contract=r.contract, func=r.func)
    return {
        "scope": asdict(ev.scope),
        "cfg": _cfg_to_dict(ev.cfg),
        "top_vars": [asdict(t) for t in ev.top_vars],
        "diagnostics": [asdict(d) for d in ev.diagnostics],
    }


@app.post("/verify")
def verify(r: Req) -> dict:
    verdict = _session(r).verify(_to_intents(r.intents), contract=r.contract, func=r.func)
    return {"verdict": [asdict(v) for v in verdict]}


@app.post("/analyze_once")
def analyze_once(r: Req) -> dict:
    return engine_api.analyze_once(
        slice_solidity(r.source), r.inputs, _to_intents(r.intents))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
