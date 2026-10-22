# -*- coding: utf-8 -*-
"""
리팩터링 마이크로 케이스(Phase 0~) — 구문별 작은 컨트랙트를 engine_api(analyze → evaluate → verify)로 돌려
노드 상태·판정·오류를 덤프한다. REFACTOR_PLAN.md §5 의 테스트 목록을 덮는다.

각 케이스는 새 프로세스에서 돈다(재귀 등으로 인한 오염·크래시 격리).
기대값(expect)은 Solidity 의미상의 정답이다. 현 엔진이 틀리는 것도 그대로 기록한다(기준선 = 현 동작).

사용:
  .venv/Scripts/python.exe evaluation/refactor/micro_cases.py --tag p0
  .venv/Scripts/python.exe evaluation/refactor/micro_cases.py --tag p0 --only incdec
출력: evaluation/refactor/baseline/micro_<tag>.json
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PY = ROOT / ".venv" / "Scripts" / "python.exe"


def I(lo, hi=None):
    return {"t": "interval", "lo": str(lo), "hi": str(lo if hi is None else hi)}


# name: (source, contract, func, debug_values, intents[(kind, text, marker|None)], expect{var: value at marker/EXIT})
# expect 는 사람이 읽는 메모(자동 채점은 하지 않음 — 현 동작 기록이 목적).
CASES = {
    "decl_assign": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        uint256 b = a + 1;
        b = b * 2;
        return b;
    }
}""", "C", "f", {"a": I(0, 5)}, [("During", "b <= 12", "return b")], "b=[2,12]"),

    "incdec": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        uint256 b = a;
        b++;
        b--;
        --b;
        ++b;
        return b;
    }
}""", "C", "f", {"a": I(10, 20)}, [("During", "b == a", "return b")], "b=[10,20] (x-- 는 감소여야 함)"),

    "compound_assign": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        uint256 b = a;
        b += 3;
        b -= 1;
        return b;
    }
}""", "C", "f", {"a": I(10, 20)}, [], "b=[12,22]"),

    "delete_local": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        uint256 b = a;
        delete b;
        return b;
    }
}""", "C", "f", {"a": I(10, 20)}, [], "b=[0,0]"),

    "tuple_decl": ("""contract C {
    function g(uint256 a) internal pure returns (uint256, uint256) {
        return (a, a + 1);
    }
    function f(uint256 a) public pure returns (uint256) {
        (uint256 x, uint256 y) = g(a);
        return x + y;
    }
}""", "C", "f", {"a": I(1, 2)}, [], "x=[1,2] y=[2,3]"),

    "tuple_swap": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        uint256 x = a;
        uint256 y = 7;
        (x, y) = (y, x);
        return x;
    }
}""", "C", "f", {"a": I(1, 2)}, [], "x=[7,7] y=[1,2]"),

    "if_else": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        uint256 b;
        if (a > 10) {
            b = 1;
        } else {
            b = 2;
        }
        return b;
    }
}""", "C", "f", {"a": I(0, 20)}, [], "b=[1,2]"),

    "else_if": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        uint256 b;
        if (a > 10) {
            b = 1;
        } else if (a > 5) {
            b = 2;
        } else {
            b = 3;
        }
        return b;
    }
}""", "C", "f", {"a": I(0, 20)}, [], "b=[1,3]"),

    "infeasible_branch": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        uint256 b = 0;
        if (a > 100) {
            b = 1;
        }
        return b;
    }
}""", "C", "f", {"a": I(0, 20)}, [], "true 분기 ⊥, b=[0,0]"),

    "block_scope_branch": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        uint256 b = 0;
        if (a > 10) {
            uint256 x = 5;
            b = x;
        }
        return b;
    }
}""", "C", "f", {"a": I(0, 20)}, [], "join 이후 x 는 스코프 밖, b=[0,5]"),

    "shadow_bare_block": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        uint256 x = 1;
        {
            uint256 x = 2;
            a = x;
        }
        return x;
    }
}""", "C", "f", {"a": I(0, 20)}, [], "return x = [1,1] (바깥 x)"),

    "shadow_if_block": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        uint256 x = 1;
        if (a > 10) {
            uint256 x = 2;
            a = x;
        }
        return x;
    }
}""", "C", "f", {"a": I(0, 20)}, [], "return x = [1,1] (바깥 x 복원), a=[0,10]∪[2,2]"),

    "shadow_state_var": ("""contract C {
    uint256 public s;
    function f(uint256 a) public returns (uint256) {
        s = a;
        uint256 s = 7;
        return s;
    }
}""", "C", "f", {"a": I(1, 2)}, [], "반환 7, EXIT 의 상태변수 s = [1,2]"),

    "while_loop": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        uint256 i = 0;
        uint256 s = 0;
        while (i < 10) {
            s = s + 1;
            i = i + 1;
        }
        return s;
    }
}""", "C", "f", {"a": I(0, 0)}, [], "i=[10,10] 이후, s over-approx"),

    "for_loop": ("""contract C {
    function f(uint256 n) public pure returns (uint256) {
        uint256 s = 0;
        for (uint256 i = 0; i < n; i++) {
            s += 2;
        }
        return s;
    }
}""", "C", "f", {"n": I(0, 5)}, [], "loop-local i 는 루프 밖에서 스코프 밖"),

    "do_while": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        uint256 i = 0;
        do {
            i = i + 1;
        } while (i < 3);
        return i;
    }
}""", "C", "f", {"a": I(0, 0)}, [], "i=[3,3] 또는 over-approx; 현재 미지원 예상"),

    "break_continue": ("""contract C {
    function f(uint256 n) public pure returns (uint256) {
        uint256 s = 0;
        for (uint256 i = 0; i < n; i++) {
            if (i == 2) {
                continue;
            }
            if (i == 4) {
                break;
            }
            s += 1;
        }
        return s;
    }
}""", "C", "f", {"n": I(0, 10)}, [], "s over-approx"),

    "continue_nested": ("""contract C {
    function f(uint256 n) public pure returns (uint256) {
        uint256 s = 0;
        for (uint256 i = 0; i < n; i++) {
            for (uint256 j = 0; j < 2; j++) {
                s += 1;
            }
            if (i == 2) {
                continue;
            }
            s += 1;
        }
        return s;
    }
}""", "C", "f", {"n": I(0, 10)}, [], "continue 는 바깥 루프의 for_incr 로 가야 한다"),

    "break_nested": ("""contract C {
    function f(uint256 n) public pure returns (uint256) {
        uint256 s = 0;
        for (uint256 i = 0; i < n; i++) {
            for (uint256 j = 0; j < 2; j++) {
                s += 1;
            }
            if (i == 3) {
                break;
            }
        }
        return s;
    }
}""", "C", "f", {"n": I(0, 10)}, [], "break 는 바깥 루프의 for_exit 로"),

    "continue_then_inner": ("""contract C {
    function f(uint256 n) public pure returns (uint256) {
        uint256 s = 0;
        for (uint256 i = 0; i < n; i++) {
            if (i == 2) {
                continue;
            }
            for (uint256 j = 0; j < 2; j++) {
                s += 1;
            }
        }
        return s;
    }
}""", "C", "f", {"n": I(0, 10)}, [], "continue 뒤에 안쪽 루프 — 바깥 for_incr 로"),

    "while_continue": ("""contract C {
    function f(uint256 n) public pure returns (uint256) {
        uint256 i = 0;
        uint256 s = 0;
        while (i < n) {
            i += 1;
            if (i == 2) {
                continue;
            }
            s += 1;
        }
        return s;
    }
}""", "C", "f", {"n": I(0, 10)}, [], "while 의 continue → while join"),

    "int_width": ("""contract C {
    function g() internal pure returns (uint112, uint32) {
        return (7, 9);
    }
    function f(uint112 a) public pure returns (uint256) {
        uint256 b = a;
        uint256 c = b * 1606938044258990275541962092341162602522202993782792835301376;
        (uint256 r0, uint256 t) = g();
        uint256 m = r0 * 1427247692705959881058285969449495136382746624;
        uint8 d = 250;
        uint256 e = 1 + d;
        return c + m + e + t;
    }
}""", "C", "f", {"a": I(1, 3)}, [], "c=[2^200,3*2^200] m=7*2^150 (256비트에서 계산), e=[251,251]? (uint8 1+d=251, overflow 없음)"),

    "for_no_incr": ("""contract C {
    function f(uint256 n) public pure returns (uint256) {
        uint256 s = 0;
        for (uint256 i = 0; i < n;) {
            s += 1;
            i += 1;
        }
        return s;
    }
}""", "C", "f", {"n": I(0, 10)}, [], "증감식 없는 for: body → join"),

    "address_members": ("""contract C {
    uint256 public sent;
    function f(address payable to, uint256 amount) public returns (bool) {
        to.transfer(amount);
        bool ok = to.send(amount);
        (bool ok2, ) = to.call{value: amount}("");
        to.call{value: amount}("");
        sent = to.balance;
        return ok && ok2;
    }
}""", "C", "f", {"amount": I(1, 5)}, [], "transfer/send/call-options 모두 노드가 생기고 오류 없음"),

    "require_assert": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        require(a > 5, "small");
        assert(a < 100);
        return a;
    }
}""", "C", "f", {"a": I(0, 20)}, [("Post", "a > 5", None)], "a=[6,20] after require"),

    "revert_branch": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        if (a > 10) {
            revert("big");
        }
        return a;
    }
}""", "C", "f", {"a": I(0, 20)}, [], "return 시 a=[0,10]"),

    "emit_call_side_effect": ("""contract C {
    uint256 public counter;
    event E(uint256 v);
    function inc() internal returns (uint256) {
        counter = counter + 1;
        return counter;
    }
    function f(uint256 a) public returns (uint256) {
        counter = a;
        emit E(inc());
        return counter;
    }
}""", "C", "f", {"a": I(1, 1)}, [], "counter=[2,2] (emit 인자 호출 효과)"),

    "try_catch": ("""interface IFoo {
    function g(uint256 x) external view returns (uint256);
}
contract C {
    IFoo foo;
    function f(uint256 a) public view returns (uint256) {
        uint256 b;
        try foo.g(a) returns (uint256 v) {
            b = v;
        } catch {
            b = 0;
        }
        return b;
    }
}""", "C", "f", {"a": I(1, 1)}, [], "b = ⊤ ⊔ 0; 현재 미지원 예상"),

    "modifier_before": ("""contract C {
    uint256 public counter;
    modifier gt(uint256 v) {
        require(v > 10);
        _;
        counter = counter + 1;
    }
    function f(uint256 a) public gt(a) returns (uint256) {
        counter = 5;
        return a;
    }
}""", "C", "f", {"a": I(0, 20)}, [], "a=[11,20] 본문, counter=[6,6] 종료"),

    "modifier_after": ("""contract C {
    uint256 public counter;
    function f(uint256 a) public gt(a) returns (uint256) {
        counter = 5;
        return a;
    }
    modifier gt(uint256 v) {
        require(v > 10);
        _;
    }
}""", "C", "f", {"a": I(0, 20)}, [], "뒤에 정의된 modifier — 현재 함수 손실 예상"),

    "forward_internal_call": ("""contract C {
    function f(uint256 a) public pure returns (bool) {
        return !h(a);
    }
    function h(uint256 a) internal pure returns (bool) {
        return a > 10;
    }
}""", "C", "f", {"a": I(0, 5)}, [], "h=false → f=true"),

    "backward_internal_call": ("""contract C {
    function h(uint256 a) internal pure returns (bool) {
        return a > 10;
    }
    function f(uint256 a) public pure returns (bool) {
        return !h(a);
    }
}""", "C", "f", {"a": I(0, 5)}, [], "f=true"),

    "overload": ("""contract C {
    function g(uint256 a) internal pure returns (uint256) {
        return a + 1;
    }
    function g(uint256 a, uint256 b) internal pure returns (uint256) {
        return a + b;
    }
    function f(uint256 a) public pure returns (uint256) {
        uint256 x = g(a);
        uint256 y = g(a, 10);
        return x + y;
    }
}""", "C", "f", {"a": I(1, 1)}, [], "x=[2,2] y=[11,11]"),

    "library_using_for": ("""library L {
    function twice(uint256 a) internal pure returns (uint256) {
        return a * 2;
    }
}
contract C {
    using L for uint256;
    function f(uint256 a) public pure returns (uint256) {
        uint256 b = a.twice();
        return b;
    }
}""", "C", "f", {"a": I(1, 3)}, [], "b=[2,6]"),

    "inheritance_super": ("""contract B {
    uint256 public s;
    function g(uint256 a) internal virtual returns (uint256) {
        s = a;
        return a;
    }
}
contract C is B {
    function g(uint256 a) internal override returns (uint256) {
        return super.g(a) + 1;
    }
    function f(uint256 a) public returns (uint256) {
        return g(a);
    }
}""", "C", "f", {"a": I(1, 3)}, [], "s=[1,3], ret=[2,4]"),

    "state_side_effect_callee": ("""contract C {
    uint256 public total;
    function add(uint256 a) internal {
        total = total + a;
    }
    function f(uint256 a) public returns (uint256) {
        total = 0;
        add(a);
        add(a);
        return total;
    }
}""", "C", "f", {"a": I(1, 2)}, [], "total=[2,4]"),

    "memory_alias_callee": ("""contract C {
    struct P {
        uint256 v;
    }
    function bump(P memory p) internal pure {
        p.v = p.v + 1;
    }
    function f(uint256 a) public pure returns (uint256) {
        P memory p = P(a);
        bump(p);
        return p.v;
    }
}""", "C", "f", {"a": I(1, 1)}, [], "p.v=[2,2] (memory 참조 전달)"),

    "self_recursion": ("""contract C {
    function fact(uint256 n) internal pure returns (uint256) {
        if (n == 0) {
            return 1;
        }
        return n * fact(n - 1);
    }
    function f(uint256 a) public pure returns (uint256) {
        return fact(a);
    }
}""", "C", "f", {"a": I(0, 3)}, [], "D7: 재진입 시 typed ⊤; 현재 RecursionError 예상"),

    "mutual_recursion": ("""contract C {
    function even(uint256 n) internal pure returns (bool) {
        if (n == 0) {
            return true;
        }
        return odd(n - 1);
    }
    function odd(uint256 n) internal pure returns (bool) {
        if (n == 0) {
            return false;
        }
        return even(n - 1);
    }
    function f(uint256 a) public pure returns (bool) {
        return even(a);
    }
}""", "C", "f", {"a": I(0, 3)}, [], "D7; 현재 RecursionError 예상"),

    "unchecked_block": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        uint256 b = a;
        unchecked {
            b = b - 1;
        }
        return b;
    }
}""", "C", "f", {"a": I(0, 5)}, [], "unchecked: wrap → ⊤ 또는 [0..] (0-1 래핑)"),

    "yul_simple": ("""contract C {
    function f(uint256 a) public pure returns (uint256 r) {
        assembly {
            r := add(a, 1)
        }
    }
}""", "C", "f", {"a": I(1, 2)}, [], "r=[2,3]"),

    "state_initializer": ("""contract C {
    uint256 public s = 5;
    uint256 public constant K = 7;
    function f(uint256 a) public view returns (uint256) {
        return s + K + a;
    }
}""", "C", "f", {"a": I(0, 0)}, [], "s=⊤(미지정), K=[7,7]"),

    "state_declared_after": ("""contract C {
    function f(uint256 a) public returns (uint256) {
        s = a;
        return s;
    }
    uint256 public s;
}""", "C", "f", {"a": I(1, 2)}, [], "s=[1,2]"),

    "named_return": ("""contract C {
    function f(uint256 a) public pure returns (uint256 r) {
        if (a > 5) {
            r = a;
        }
    }
}""", "C", "f", {"a": I(0, 10)}, [], "r=[0,10] (기본 0 포함)"),

    "ternary": ("""contract C {
    function f(uint256 a) public pure returns (uint256) {
        uint256 b = a > 5 ? 1 : 2;
        return b;
    }
}""", "C", "f", {"a": I(0, 10)}, [], "b=[1,2]"),
}

# 실행 격리: 같은 세션에서 A → B → A
ISOLATION = ("decl_assign", {"a": I(0, 5)}, {"a": I(100, 200)})

# 실행 격리(@IReturn 누수): A 는 @IReturn 지정, B 는 미지정 → B 에서 r 은 ⊤ 이어야 한다.
ISOLATION_IRETURN_SRC = """interface IFoo {
    function g() external view returns (uint256);
}
contract C {
    IFoo foo;
    function f(uint256 a) public view returns (uint256) {
        uint256 r = foo.g();
        return r + a;
    }
}"""


def _line_of(src, marker):
    for i, ln in enumerate(src.splitlines(), 1):
        if marker in ln:
            return i
    return None


def _cfg_dump(cfg):
    return {n.name: {"line": n.src_line, "state": dict(sorted((n.state or {}).items()))} for n in cfg.nodes}


def run_one(name):
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    import contextlib, io
    buf = io.StringIO()
    out = {"name": name}
    with contextlib.redirect_stdout(buf):
        import engine_api
        from engine_api import IntentItem
        from Dependencies.main import slice_solidity
        try:
            if name == "__isolation__":
                cname, A, B = ISOLATION
                src, c, f = CASES[cname][:3]
                s = engine_api.EngineSession()
                s.analyze(slice_solidity(src), c, f)
                d1 = _cfg_dump(s.evaluate(A, c, f).cfg)
                d2 = _cfg_dump(s.evaluate(B, c, f).cfg)
                d3 = _cfg_dump(s.evaluate(A, c, f).cfg)
                out.update(first_A=d1, B=d2, second_A=d3, A_equal=(d1 == d3))
            elif name == "__isolation_ireturn__":
                s = engine_api.EngineSession()
                st = s.analyze(slice_solidity(ISOLATION_IRETURN_SRC), "C", "f")
                out["slots"] = sorted(f"{x.kind}:{x.key}" for x in st.debug_slots)
                ir = next((x.key for x in st.debug_slots if x.kind == "IReturn"), None)
                A = {"a": I(1, 1)}
                if ir:
                    A[ir] = I(7, 7)
                d1 = _cfg_dump(s.evaluate(A, "C", "f").cfg)
                d2 = _cfg_dump(s.evaluate({"a": I(1, 1)}, "C", "f").cfg)
                r1 = sorted({n["state"].get("r") for n in d1.values() if n["state"].get("r")})
                r2 = sorted({n["state"].get("r") for n in d2.values() if n["state"].get("r")})
                out.update(ireturn_key=ir, r_with=r1, r_without=r2, leaked=(r1 == r2))
            else:
                src, c, f, vals, intents, expect = CASES[name]
                out["expect"] = expect
                s = engine_api.EngineSession()
                t = time.perf_counter()
                st = s.analyze(slice_solidity(src), c, f)
                out["analyze_s"] = round(time.perf_counter() - t, 3)
                out["diagnostics"] = [f"{d.line}:{d.message}" for d in st.diagnostics]
                out["slots"] = sorted(f"{x.kind}:{x.key}" for x in st.debug_slots)
                out["structure"] = sorted(f"{n.name}@{n.src_line}" for n in st.cfg.nodes)
                t = time.perf_counter()
                ev = s.evaluate(vals, c, f)
                out["evaluate_s"] = round(time.perf_counter() - t, 3)
                out["states"] = _cfg_dump(ev.cfg)
                out["eval_diagnostics"] = [f"{d.line}:{d.message}" for d in ev.diagnostics]
                if intents:
                    items = [IntentItem(scopeKind=k, text=tx, line=(_line_of(src, m) if m else None))
                             for k, tx, m in intents]
                    out["verdicts"] = [f"{v.type}@{v.line}:{v.status}" for v in s.verify(items, c, f)]
        except BaseException as ex:                  # RecursionError 포함 — 기록만
            import traceback
            out["error"] = f"{type(ex).__name__}: {str(ex)[:300]}"
            out["trace"] = traceback.format_exc()[-1200:]
    return out


def main_cli():
    ap = argparse.ArgumentParser()
    ap.add_argument("--one")
    ap.add_argument("--only")
    ap.add_argument("--tag", default="p0")
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()
    if a.one:
        print("@@JSON@@" + json.dumps(run_one(a.one), ensure_ascii=False))
        return
    names = [a.only] if a.only else list(CASES) + ["__isolation__", "__isolation_ireturn__"]
    res = {}
    for nm in names:
        try:
            p = subprocess.run([str(PY), __file__, "--one", nm], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=a.timeout, cwd=ROOT,
                               env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            line = next((l for l in p.stdout.splitlines() if l.startswith("@@JSON@@")), None)
            d = json.loads(line[8:]) if line else {"error": "no result line", "stderr": p.stderr[-1500:]}
        except subprocess.TimeoutExpired:
            d = {"error": f"timeout {a.timeout}s"}
        res[nm] = d
        summary = d.get("error") or (f"A_equal={d.get('A_equal')}" if nm == "__isolation__" else
                                     f"leaked={d.get('leaked')} with={d.get('r_with')} without={d.get('r_without')}"
                                     if nm == "__isolation_ireturn__" else
                                     f"nodes={len(d.get('states', {}))} verdicts={d.get('verdicts', '')}")
        print(f"{nm:<26} {str(summary)[:110]}", flush=True)
    outp = HERE / "baseline" / f"micro_{a.tag}.json"
    outp.parent.mkdir(exist_ok=True)
    if a.only and outp.exists():
        old = json.loads(outp.read_text(encoding="utf-8")); old.update(res); res = old
    outp.write_text(json.dumps(res, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print("->", outp)


if __name__ == "__main__":
    main_cli()
