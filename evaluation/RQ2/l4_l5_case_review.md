# L4/L5 Case-by-Case Deep Review

**Target**: 34 not_detectable cases (L4a 10, L4b 8, L4c 1, L4d 1, L5a 7, L5b 7)
**Purpose**: Re-examine the validity of classification and root causes for each case based on its audit report and source code, deriving insights for the paper (Introduction / RQ2 / Discussion).

---

# Paper-Ready Insights (cumulative)

The following are **cross-cutting observations** extracted from the case analyses — in a form ready for direct citation/editing in the paper body (RQ1 / RQ2 / Discussion). See the subsections for per-case detail.

## I1. Annotation grammar != Abstract interpretation engine

**Observation** (from Case 1): IntentChecker has two separate language layers, and there is a risk of conflating them in the paper body:

- **Analysis engine (abstract interpretation)**: can soundly abstract a rich set of Solidity operations including `**`, bitwise operations, loops, external view calls, etc.
- **Intent annotation grammar**: only allows variables, integer literals, intervals `[a,b]`, `+ − × / %`, and parentheses — a **strict subset** of what the engine can handle.
- **Debug annotations** (`@StateVar`, `@LocalVar`, `@IReturn`, etc.): value-supply mechanisms **for the analysis engine**. Not a means of extending the intent annotation grammar. The two layers are independent by design.

**Paper integration**:
- Add one sentence to the Figure 6 (grammar BNF) caption — make explicit that the simplicity of the annotation grammar is an intended design choice, not an engine limitation.
- RQ2 opening — declare the separation of the two axes (engine expressiveness / annotation expressiveness).
- In L4a/L5 body text, prohibit phrasing such as "IntentChecker does not support `**`" — instead state precisely "the annotation grammar does not include `**`".

## I2. L4a / L5a decision criterion — the "omniscient-developer test" (read together with I7)

**Decision criterion** (from Case 2, refined in Case 4):
> Can a developer who knows the bug exactly write an annotation that **directly expresses the correct intent** using only the grammar?
> - **Yes** → **L5a/L5b** (*behavior deficit*): annotation is expressible; deciding "which annotation to write" presupposes bug awareness.
> - **No** → **L4a** (*expressibility deficit*): even an omniscient developer cannot directly express the intent.

**Important caveat (lesson from Case 4)**: One must not conclude L5 based solely on the "existence of a grammar-expressible distinguishing annotation". Including cases where a local proxy annotation accidentally has distinguishing power renders the classification meaningless. **Intent-level expressibility** is required (→ I7).

**Paper integration**:
- Declare the refined criterion as a formal decision rule at the start of L4a/L5a sections.
- L5a body: "bug-awareness required" is a **symptom**; the cause is "the annotation space is rich enough that the choice carries meaning".

## I3. Primary blockers within L4a — three branches

**Three axes** (from Cases 1, 2, 3, 4):

- **(α) The variable relation includes a function call (Case 1, Case 3 type)**: variables that contribute to the correct relation exist in scope, but the relation itself requires the **return value of a function call** (an external interface view or an internal view) as an operand. Since intentValue allows only variables and constants, the function cannot enter the relation.
- **(β) The variable to be related is itself absent (Case 2 type)**: there is **no proxy variable anywhere in scope or in the contract** for the domain referenced by the correct RHS (e.g., underlying token decimals). The RHS consists only of "literal + external value" without any contribution from scope variables.
- **(γ) Multi-point accounting cannot be expressed as a single-point annotation (Case 4 type)**: the bug is not a single-line formula error but the **combinatorial net effect of multiple external calls**. Each call's local args are valid, but the net differs from the intent. The intent is a multi-point balance change — it cannot be captured by a single-point annotation. Often depends on external state (e.g., ERC20 balance).

**Common ground**: all three axes fail to express intent directly within a pure annotation-only workflow.

**Paper integration**:
- In the rewrite of the L4a body (line 1307), distinguish the three axes or list representative cases.
- In the Discussion, the effect of grammar extension differs by axis — (α) admits partial relief by allowing limited function references; (β) requires code modification; (γ) requires introducing a multi-point accumulator concept into the annotation language.

## I4. Permeability of the L4a / L5 boundary — auxiliary local injection

**Observation** (from Cases 2, 3): if a developer injects a **side-effect-free auxiliary local** into production code (e.g., `uint256 D0 = _computeLiquidity(...)` or `uint8 uD = IERC20(...).decimals()`), the scope landscape expands and the annotation becomes grammar-expressible. However, the decision to inject is itself a judgment that "this value is important to correctness" → presupposes bug awareness → **moves into the L5 region**.

**Implication**: the L4a / L5 boundary is fixed only under the **pure annotation-only workflow** assumption. In an "annotation-driven refactor" environment (where introducing auxiliary variables to support annotation writing is allowed), many L4a cases would be reclassified as L5.

**Paper integration**:
- In Discussion/future work, present "annotation-driven refactor" as an alternative workflow — possibly more practical than grammar extension.

## I5. The "silent sanction" risk — fail-by-confirmation mode (across L4a)

**Observation** (from Cases 3, 4): when a developer translates the natural intent of the code/natspec into an annotation, the result can be **tautologically consistent with the buggy code**. IntentChecker then re-confirms it as "correct" — a failure mode.

**Two failure modes**:
- **Mode-1 (fail-silent-by-omission)**: writing the annotation itself fails → no verdict is produced at all.
- **Mode-2 (fail-by-confirmation, silent sanction)**: the annotation is grammar-expressible and Satisfied on the buggy code → the bug passes.

**Where silent sanction arises** (per case):
- **Case 3 (29_H_05)**: the rational-polynomial expressive range of the grammar covers the CP formula family, and that formula is the buggy one. "Grammar-algebraic coincidence".
- **Case 4 (39_H_02)**: the natspec above L280 ("transfer premium minus fee from maker to sender") is synchronized with the buggy implementation, so an annotation written following the natspec validates the buggy code. **Natspec-code consistency**.

**Paper citation value**:
- Simple grammar extension does not resolve Mode-2.
- Summarizing L4a as a single message of "inexpressibility" hides the Mode-2 risk. A separate mention in Discussion is recommended.
- Annotation-driven workflow must go hand in hand with **natspec review** — the process of checking that the natural intent has not drifted to track the buggy implementation is as important as the annotation itself.

## I6. L4a boundary observation — general form vs specific form

**Observation** (from Case 2): when an L4a case's correctness condition is "a value that varies with the parameters", **fixing a specific instance** makes a constant annotation grammar-expressible. However:
- A single annotation that applies to all instances → requires referencing an external value → **L4a**.
- Hardcoding a constant per instance → expressible, but the constant = the answer knowledge → **L5a-flavored** (bug-awareness).

**Implication**: the expressiveness of "generalized intent annotation" and that of "instance-specific intent annotation" must be distinguished; annotation reusability reveals another axis of structural limitation.

## I7b. Re-examination of the L4a/L5b boundary — "Type A vs Type B" (unsettled, follow-up needed)

**Discovery path** (suggested by the user during Case 5 analysis): bisecting cases classified as L4a by "whether a proxy variable exists in scope":

- **Type A (proxy in scope; a variable close to the correct value exists, but the current code does not use it correctly)**: in theory an annotation of the form `@Post return == correct_formula_using_proxy` could be grammar-expressible → **may in fact be L5b (wrong-code)**.
- **Type B (no proxy; no scope or state variable connects to the correct value at all)**: the expression path is fundamentally blocked by the grammar → **proper L4a**.

**Application so far**:
- Case 1 (25_H_01): the `source.decimals` struct field — **Type A candidate**. Re-examination of the existing L4a classification needed.
- Cases 2, 3, 4, 5: confirmed **Type B**.

**Unsettled items**:
- If Case 1 is confirmed Type A, L4a → L5b reclassification is needed.
- A full sweep of the remaining L4a cases (7) is needed to find more Type A.
- A finer criterion may be needed between "proxy exists but the buggy code uses the wrong variable" vs "proxy exists, the buggy code uses the right variable but the operation is wrong".

**Implication (paper level)**: this **bisection cuts more cleanly** than the prior I3 α/β/γ trichotomy. Whether "intent-level expressibility is possible" can be decided mechanically by scope inspection alone. However, operating guidelines are needed for borderline cases (deeply nested struct fields, inherited state, etc.).

**Paper integration (tentative)**:
- After completing the full L4a review, present the Type A/B distribution statistics — an upper bound on how much grammar extension would resolve.
- In Discussion, branch the message: "Within L4a, Type A can be resolved by establishing a proxy-finding principle when writing annotation_plans, rather than by extending the grammar; Type B is a structural limitation."

## I8-pre. Classification priority: **L4 > L1-L3 > L5**

**Principle**: when a case spans multiple limitation axes, **applicability of the methodology** has the highest priority. Apply the inapplicability dimension first.

```
Pipeline-applicability viewpoint:
  (0) Is the intent annotation expressible? → if no, L4 (pipeline entry fails, tool silent)
  (1) Does the engine compute an abstract value? → if widening/TOP, L1-L3 (Warning emitted, signal present)
  (2) Does it produce a contrasting verdict? → if the written annotation presupposes bug awareness, L5
```

- **L4 primary**: the annotation cannot be written → no Satisfied/Warning/Violated verdict → the tool is silent on that function. **The methodology itself is inapplicable** — the most fundamental limitation.
- **L1-L3 secondary**: the annotation can be written. The engine widens/TOPs and produces a Warning. At least provides "something is wrong" signal.
- **L5 tertiary**: the pipeline operates. However, the *direction* of the written annotation must align with the correct answer to be meaningful.

**Practical implications**:
- If a case satisfies both L4 and L1-L3, **classify as L4**, with L1-L3 as a secondary note.
- That is, no need to run L1-L3 experiments for cases confirmed as L4 (e.g., the newBalances loop widening experiment in Case 6).
- Paper narrative: L4 is the main novel contribution (annotation language expressiveness limit → future direction: grammar extension). L1-L3 is a common AI-tool challenge and less distinctive.

---

## I9. The `.arg[n]` channel is lint-level; do not use it as the basis for an L5b verdict

**Discovery path** (cascading re-examination of Cases 4, 8): a `.arg[n]` intent annotation is grammar-expressible and can distinguish buggy from correct argument order. However:

- **Nature**: `.arg[n]` checks the **argument identifier choice in source code**. Its character differs from a semantic intent that checks the meaning of program **values**. It is essentially a **lint-style pattern check**.
- **Overlap with existing tools**: pattern-matching static analyzers such as Slither already cover this. Not in IntentChecker's distinctive contribution area.

**Paper classification principle**:
- Even if a bug is caught by `.arg[n]`, **do not use it as the basis for an L5b classification**.
- The L4a/L5 boundary is decided on the **semantic intent channel** (return value meaning, state-change meaning).
- That is, decide L4a/L5 based on whether `correct_expr` is expressible in `@Post returnExpression == correct_expr`, `@Post changed(stateVar, true)`, etc.

**Application examples**:
- Case 4 (39_H_02): the semantic intent (net flow) is inexpressible → **L4a**. Independent of the existence of `.arg[n]`.
- Case 8 (61_H_01): the semantic intent (the meaning of `_ratioOfPrices`) is inexpressible (the engine cannot distinguish buggy from correct due to @IReturn arg-indifference) → **L4a**.
- Case 7 (59_H_05): the semantic intent (pre-penalty maltQuantity) is inexpressible → **L4a**.

**Contrast (existing L5b examples)**:
- 52_H_15 (pool swap arg order): catchable only via `.arg[n]`. Under this principle, **its L5b status also requires re-examination** — possibly a candidate for reclassification as L4a.
- 113_H_05 (require operator): a simple comparison-operator error. Need to examine whether a non-`.arg[n]` semantic comparison is also possible.
- 35_H_11 (struct field error): similarly requires re-examination.

**Unresolved (in subsequent cases)**: existing L5b classifications may also be reclassified as L4a under this principle. Reassess systematically when reviewing the L5b section.

**Paper implications**:
- For L5b to be featured as "detectable with bug awareness", semantic-level annotations must be possible.
- Cases catchable only via `.arg[n]` should not be counted in IntentChecker's novelty.

---

## I8. Value error vs Algorithm error × Type A/B (the main matrix of the paper narrative)

**Reason for terminology**: the paper Introduction/Background uses "numeric logic error" as the umbrella term. To distinguish sub-classes without a hierarchical conflict, **"algorithm error"** is used ("logic error" is reserved for the umbrella).

```
numeric logic error (umbrella)
├── value error      : constant / operand / single-value error — one-line fix
└── algorithm error  : formula choice / flow composition / missing decomposition — structural fix
```

**Purpose**: provide a symmetric narrative of "what IntentChecker solves and what it does not". Since I1-I7 were biased toward the blocker side, restructure them as a bidirectional **solvable ↔ unsolvable** structure.

**Two axes**:
- **Value error vs Algorithm error** (axis on fix size/character):
  - Value error: a constant or operand at a specific location is wrong. Fix = one-line, one-value correction.
  - Algorithm error: formula choice, flow composition, or decomposition is wrong. Fix = algorithmic restructuring or multi-line rewrite.
  - Borderline cases exist (e.g., a one-line fix whose meaning is a flow-design correction).
- **Type A vs Type B** (axis on whether a proxy exists in scope, I7b):
  - Type A: a proxy variable exists → annotation possible from the existing scope.
  - Type B: no proxy → a value outside the scope is required.

**2×2 matrix (tentative)**:

|  | Value error | Algorithm error |
|---|---|---|
| **Type A** | `@Post == correct_value` expressible with existing scope vars → mostly **L5b (detectable)** | post-condition can be composed with existing scope vars → **L5a (missing-code detectable)** |
| **Type B** | needed value is outside scope → **L4a axis β** — future: proxy-discovery principle | algorithmic decomposition required → **L4a axis α/γ** — future: annotation-driven refactor / sequential grammar |

**Tentative mapping of the 5 cases so far**:
- Case 1 (25_H_01): Value error / Type A candidate (to be confirmed when Case 1 is re-examined).
- Case 2 (25_H_05): **Value error / Type B**.
- Case 3 (29_H_05): **Algorithm error / Type B** — single step (wrong formula choice).
- Case 4 (39_H_02): **Algorithm error / Type B** — cross-line fee flow composition.
- Case 5 (51_H_04): **Algorithm error / Type B** — multi-step decomposition missing.

**Paper narrative strategy**:
- **RQ1 (solvable)**: most of the Type A region + the grammar-expressible portion of Type B.
- **RQ2 (unsolvable)**: branched message per Type B cell:
  - Value/B: the absence of a proxy is the blocker → propose a proxy-discovery annotation methodology.
  - Algorithm/B: restructuring required → grammar extension limit + annotation-driven refactor as alternative.
- **Discussion → Future direction**: the resolution path for each cell differs qualitatively, organized along the axis.

**Note**: the matrix is not enforced as a strict partition. For borderline cases, only the **principal viewpoint** is recorded; after the full review of the 34 cases, a **summary section will aggregate per cell + select representative examples**. Currently each case §5 carries only a `**[Category]**` tag.

## I7. Formal expressibility != Intent-level expressibility (the true criterion of the L4a/L5 boundary)

**Discovery path** (during Case 4 re-examination): if I2's "omniscient-developer test" is applied as a purely formal criterion ("does a grammar-expressible distinguishing annotation exist?"), then **local proxy annotations** that happen to have distinguishing power get classified as L5 → the classification loses meaning.

**Corrected criterion**:
- **Formal expressibility**: does the grammar admit some form of distinguishing annotation (including proxies)? (weak condition)
- **Intent-level expressibility**: does the grammar admit an annotation that **directly expresses the correct intent**? (strong condition, the true criterion of the L4a/L5 boundary)

**Application to Case 4**:
- Formal: `@During .arg[2] == premiumFilled` exists → expressible.
- Intent-level: the true intent is "sender net flow = premiumFilled - fee" (external ERC20 balance) → inexpressible → **L4a**.
- The local `.arg[n]` proxy is a derived form obtained through cross-line back-derivation + external standard knowledge + natspec override; not the intent itself.

**Paper integration**:
- Rewrite the I2 decision rule on the intent-level criterion.
- In the RQ2 opening or the L4a introduction, state explicitly: "formal proxy annotations may incidentally distinguish, but the classification is decided by intent-level expressibility". Defends against reviewer challenge.
- Discussion — emphasize that the concept of intent-level expressibility is at the core of IntentChecker's design philosophy (annotation is a language for transferring intent, not a test for shadowing the implementation).

---

Quick reference for grammar constraints (**post-paper-revision baseline, includes `**`**):
- **intentValue**: variables (including member/index access), integer literals, `[a,b]`, `+ - * / % **`, parentheses.
- **Not allowed**: function calls, bitwise operations (`<<`, `>>`, `&`, `|`, `^`), user-defined calls, variables outside scope.
- **Debug annotations**: `@IReturn` only on view/pure interface calls. Independent of intent grammar (see I1).
- **Change record (for the log)**: initial drafts assumed `**` was unsupported, but it will be added in the paper revision. The G2_annotation_only tag on prior cases (1, 10) is **no longer a blocker**. However, the G1 (function call) and G3 (scope absence) axes are unchanged.

Root-cause G-categories:
- **G1** no function call in grammar
- **G2** no bitwise / exponent operations in grammar
- **G3** intermediate variable absent in code and not derivable in grammar
- **G4** no state change at all (view/pure, library, external delegation)
- **G5** buggy/correct qualitatively identical, only quantitatively different (`changed`/entry-exit cannot distinguish)
- **G6** multi-variable invariant (e.g., product preservation) not expressible in PostEntryExit
- **G7** bug awareness presupposed (the correct annotation = fix knowledge)
- **G8** depends on external contract state (outside the allowed range of `@IReturn`)
- **G9** other

---

## L4a — Inexpressible Expected Value (10 cases)

---

### Case 1 — `web3bugs_25_H_01` (current classification: **L4a**)

#### 1. Audit report citation

- **Source**: `reports/25.md` → `[H-01] CompositeMultiOracle returns wrong decimals for prices?`
- **Severity**: High. **Warden**: cmichel (C4 2021-08-yield micro)
- **Core claim (verbatim excerpt)**:

  > The `CompositeMultiOracle.peek/get` functions seem to return wrong prices. A single price is computed as:
  > ```
  > (priceOut,_) = IOracle(source.source).peek(base, quote, 10 ** source.decimals);
  > priceOut = priceIn * priceOut / (10 ** source.decimals);
  > ```
  > Assume all oracles use 18 decimals and `source.decimals` refers to the token decimals of `source.source`. Going from USDC → DAI → USDT (`path = [DAI]`) starts with price `1e18`:
  > - `_peek(USDC, DAI, 1e18)`: `priceOut = 1e18 * 1e18 / 1e6 = 1e30`
  > - `_peek(DAI, USDT, 1e30)`: `priceOut = 1e30 * 1e18 / 1e18 = 1e30`
  >
  > Final `value = 1e30 * 1e6 / 1e18 = 1e18` = 10^12 USDT. Inflates USDT by 10^12.
  >
  > The issue is that `peek` assumes the final price is in 18 decimals (`value = price * amount / 1e18`) but `_peek`/`_get` don't enforce this.

- **Recommended fix**:
  ```solidity
  priceOut = priceIn * priceOut / (10 ** IOracle(source.source).decimals());
  ```
  — make the denominator "the output precision the oracle itself reports". The sponsor (alcueca) subsequently patched it as an invariant "force every sub-oracle to have 18 decimals".

#### 2. Understanding the code's meaning

##### (2a) Contract purpose and system role

`CompositeMultiOracle` — a **price aggregator** in Yield Protocol v2. When there is no direct pair for A→B, it uses `paths[A][B] = [X₁, X₂, …]` as relay points and **multiplicatively chains** several sub-`IOracle`s to obtain a synthesized exchange rate. A **price source of truth** for Yield's vault collateral valuation, liquidation, and CR (collateralization ratio) computation.

##### (2b) Function role within the contract

Two private helpers:
- `_peek(base, quote, priceIn, updateTimeIn) → (priceOut, updateTimeOut)` (line 110-118, view)
- `_get(...)` (line 120-128, mirror of `_peek` — uses `.get` instead of `.peek`)

The public `peek`/`get` (line 74-108) traverses the path, calling these helpers at each hop. That is, they perform a **single hop of the chain** as a curried multiplier.

**Note that the terms `base`/`quote` are reused across two layers** (key to understanding this case):
- **From the public `peek(base, quote, amount)` perspective**: `base` = the source token of the conversion (A); `quote` = the destination token (B). The user-facing final "A→B".
- **From the internal `_peek(base, quote, …)` perspective**: only one hop. `base` = "the source of this hop"; `quote` = "the destination of this hop". During path traversal, **the destination of the previous hop becomes the base of the next hop** (line 84 `base_ = path[p]`). `base_` acts as a pointer advancing along the path.

##### (2c) Function intent (formula + scaling convention)

Internal exchange-rate convention: **`price` is always an 18-decimal fixed-point cumulative rate of the form "rate × 10^18"**.
- Initial value `price = 1e18` (= rate 1.0, no hops traversed).
- What each hop does: "multiply the raw rate of this hop into the cumulative value, then renormalize back to 18-dp".

Formula:
```
priceOut = priceIn    ×    raw_price_from_oracle    /   10^(output_scale)
           ^^^^^^^^        ^^^^^^^^^^^^^^^^^^^^^         ^^^^^^^^^^^^^^^^
           cumulative      this-hop rate (scale-dp)      normalization divisor
           rate (18dp)
```

**Intuition for "multiply by priceIn"**: rate composition. `USDC→USDT = USDC→DAI × DAI→USDT`. Each hop contributes its own share, and accumulation is multiplicative.

**Intuition for "align to 18 decimals"**: the oracle returns a number inflated by `10^scale`, so dividing by the same magnitude returns it to a "pure rate × 10^18". This way the scale is not progressively contaminated when multiplied by the next hop.

**Invariant (`peek` contract)**: `peek(base, quote, amount) = value` ⇒ "`amount` units of the base token are economically equivalent to `value` units of the quote token at the current rate". Both `amount` and `value` are in each token's native integer representation (1 USDC = `1e6`, 1 DAI = `1e18`).

##### (2d) Line-by-line analysis (`_peek` line 110-118)

```solidity
113  Source memory source = sources[base][quote];
114  require (source.source != address(0), "Source not found");
115  (priceOut, updateTimeOut) = IOracle(source.source).peek(base, quote, 10 ** source.decimals);
116  priceOut = priceIn * priceOut / (10 ** source.decimals);   // BUG
117  updateTimeOut = (updateTimeOut < updateTimeIn) ? updateTimeOut : updateTimeIn;
```

- **L113**: looks up `sources[base][quote]` — `Source { address source; uint8 decimals; }`. `decimals` is snapshotted from `IOracle(source).decimals()` in `_setSource` (line 131) — **intended as the sub-oracle's output precision**.
- **L114**: revert if the source is not set.
- **L115**: asks the sub-oracle for the quote conversion of "base in units of `10^source.decimals`" → `priceOut = raw_oracle_price`. The comment "Get price for one unit" presumes `source.decimals` to be **token decimals** (cmichel's interpretation point).
- **L116 (BUG)**: `priceIn * priceOut / 10^source.decimals`. The semantic role of the denominator should be "remove the oracle's output precision", but the variable name (`source.decimals`) is ambiguous. In the actual implementation, `_setSource` stores `IOracle.decimals()` so it is numerically correct, but **the code does not express its own intent** and is therefore fragile.
- **L117**: freshness propagation (preserve the older updateTime).

##### (2e) Root meaning of the bug (with examples)

**Example A — normal operation** (`source.decimals == 18`, all rates 1.0):

| hop | `priceIn` | sub raw | calculation | `priceOut` |
|---|---|---|---|---|
| USDC→DAI | `1e18` | `1e18` | `1e18*1e18/1e18` | `1e18` OK |
| DAI→USDT | `1e18` | `1e18` | `1e18*1e18/1e18` | `1e18` OK |

Final: `value = 1e18 * 1e6 / 1e18 = 1e6` → 1 USDT. Correct.

**Example B — cmichel's interpretation (bug scenario)**: USDC source with `source.decimals = 6` (token decimals). The oracle's actual output is still 18-dp.

| hop | `priceIn` | sub call | raw | wrong division | `priceOut` |
|---|---|---|---|---|---|
| USDC→DAI | `1e18` | peek(...,10^6) | `1e18` | `1e18*1e18/1e6` | **`1e30`** WRONG |
| DAI→USDT | `1e30` | peek(...,10^18) | `1e18` | `1e30*1e18/1e18` | `1e30` |

Final: `value = 1e30 * 1e6 / 1e18 = 1e18` → from the USDT viewpoint, `1e18/1e6 = 10^12` USDT. 1 USDC is valued as a trillion USDT.

Error site: **the first hop's `/1e6`**. The number returned by the oracle in 18-dp is divided by 6-dp, injecting a factor of `10^12` into the cumulative value, which persists to the end.

**Protocol-level result**: a Yield vault uses `value` as the collateral quantity in collateral valuation → valuations are inflated or shrunk by `10^k` → unsecured loans or instant liquidation of healthy positions → bidirectional asset loss.

##### (2f) Correct fix

```solidity
priceOut = priceIn * priceOut / (10 ** IOracle(source.source).decimals());
```
The denominator becomes "the sub-oracle's currently-reported decimals", not "the stored number `source.decimals`". Mathematically correct regardless of the variable name's ambiguity.

#### 3. IntentChecker annotation attempt

**(a) State variable change?** None. `_peek` is view, and `_get` performs no storage write. No target for `Post changed`/entry-exit.

**(b) Correct return value as an arithExpr?**
```
@Post returnExpression == priceIn * priceOut_raw / (10 ^ IOracle(source.source).decimals())
```
- `10 ** x` / `10 ^ x` → **G2** (no exponentiation).
- `IOracle(source.source).decimals()` → **G1** (no function call). Even attempting to supply the view call via `@IReturn`, there is no way to use the result together with `**`.
- The sub-call's raw `priceOut` can be supplied via `@IReturn`, but the `10^decimals` division itself is blocked.
- Workaround of hardcoding `1e18` → makes the annotation pre-assert an invariant that does not exist in the code; meaning is distorted.

**(c) Bug-awareness presupposed?** Blocked at the inexpressibility step → not an L5 candidate.

**Prediction**: regardless of form, parsing/expression fails → no verdict on either buggy or correct.

#### 4. Classification validity

- Current: **L4a**. Maintain.
- Nature of the blocker: the correct denominator is `10^IOracle(...).decimals()` — depends on the **combination of exponentiation and a function call**. The new intermediate value lies outside the target function's scope (only present in `_setSource`).
- The note in `annotation_plans.md` line 360 — "interface calls are now supported, so this is not TOP" — is correct, but it tends to obscure **the true blockers G1/G2/G3** → needs reinforcement.

#### 5. Root cause

**Essence (impedance mismatch)**: IntentChecker's intent annotation is a variable-relation language expressing **first-order relations among values that actually exist on the function trace**. That is, the allowed operands are (i) function locals/parameters/storage variables, (ii) integer literals, and (iii) the return values of **calls already present in the code** labeled by `@IReturn`. By contrast, this bug's correctness condition is a relation involving `IOracle(source.source).decimals()` — **the return of a function the function does not call**. In other words, "the world the annotation can speak about" and "the world correctness requires" are disconnected. The G-categories below are all surface symptoms of this single mismatch.

- **G1 (syntactic surface)** — the annotation grammar has no slot for function calls. A direct restriction prevents writing `IOracle(...).decimals()` in intentValue.
- **G3 (semantic surface)** — even if the grammar allowed it, the `.decimals()` call site does not exist in the body of `_peek`/`_get`, so the `@IReturn` workaround is unavailable. It exists only in `_setSource`, outside the target function's trace.
- **G2 (auxiliary, annotation-only)** — the annotation grammar does not include `**`, so `10 ** x` cannot be expressed. **Note: this limitation is restricted to the annotation language** — the abstract interpretation engine supports `**`, so **the buggy runtime's `10 ** source.decimals` computation is precisely abstracted** (not TOP). Therefore G2 is a surface symptom of "cannot express the correct answer", not "cannot analyze". (A separate paper correction is needed — see `paper_corrections.md`.)
- **G4 (augmenting)** — being view/effectively-view, the post-state channel is also closed → G1/G3 are the only channels and are blocked.

**[Category (I8)]**: **Value error / Type A candidate** — `source.decimals` is a snapshot proxy. Re-examination needed (audit interpretation has branches).

#### 6. Suggested rewrite of paper sentence

Current (main.tex line 1307):
> **L4a (Inexpressible expected value, 10).** The correct expected value depends on a new intermediate computation, an external contract's state, or a function call that does not appear in the program; no intentValue expression can be constructed.

Proposed rewrite (elevated as an impedance mismatch):
> **L4a (Inexpressible expected value, 10).** The corrective specification references values that the target function's trace does not produce — most commonly, the return of a function the target does not call. Since `intentValue` is a first-order language over variables and call returns already bound in the function (`@IReturn` applies only to call sites already present in the code), no expression matches the correctness condition.

(The separate limitation that the annotation grammar does not include `**` is described separately from the main expressiveness discussion — proposed below in Case 1.)

---

### Case 2 — `web3bugs_25_H_05` (current classification: **L4a**)

#### 1. Audit report citation

- **Source**: `reports/25.md` → `[H-05] Exchange rates from Compound are assumed with 18 decimals`
- **Severity**: High. **Warden**: shw.
- **Core claim (verbatim excerpt)**:
  > `CTokenMultiOracle` assumes the exchange rates of Compound always have 18 decimals. According to the Compound documentation, the exchange rate returned from `exchangeRateCurrent`/`exchangeRateStored` is scaled by `1 * 10^(18 - 8 + Underlying Token Decimals)`. Using a wrong decimal number on the exchange rate could cause incorrect pricing on tokens. See `CTokenMultiOracle.sol#L110`.
- **Recommended fix**: "get the decimals of the underlying tokens to set the correct decimal of a Source."
- **Sponsor**: confirmed and patched (`e9c1ee5532...`).

#### 2. Understanding the code's meaning

##### (2a) Contract purpose and system role

`CTokenMultiOracle` — an **adapter oracle** that exposes the exchange rate between a Compound cToken and its underlying ERC20 in the Yield system's internal representation (18-dp). e.g., cDAI ↔ DAI, cUSDC ↔ USDC. Since `CompositeMultiOracle` (case 1) can designate this adapter as one of the sub-`IOracle`s when constructing a path, it affects **the entire collateral-valuation pipeline of cToken-based Yield vaults**.

Compound's `exchangeRate` is a raw number representing "how much underlying one cToken represents", and Compound returns it on a **scale of `10^(18 - 8 + uD)`** (where `uD` = underlying token decimals). A cToken's own decimals are fixed at 8. e.g., cDAI (uD=18) → scale `10^28`; cUSDC (uD=6) → scale `10^16`.

Yield internal convention: every oracle's output is in 18-dp (`decimals = 18` public constant, line 14).

##### (2b) Function role within the contract

- `_setSource(cTokenId, underlying, source)` (line 109-124, internal): sets bidirectional entries `sources[cTokenId][underlying]` and `sources[underlying][cTokenId]`. The latter has `inverse = true`.
- The `decimals` value stored by this function becomes the **price-scale normalization parameter** for every subsequent `_peek`/`_get` call.

L110 `uint8 decimals_ = 18;` — this single line is the bug.

##### (2c) Function intent (formula)

`_peek`/`_get` internal normalization (line 82-86):
```solidity
if (source.inverse)  price = 10 ** (source.decimals + 18) / rawPrice;   // underlying → cToken
else                 price = rawPrice * 10 ** (18 - source.decimals);   // cToken → underlying
```
Here the semantic role of `source.decimals` = **"the scale carried by rawPrice"** = `10 + uD` (= 18 - 8 + uD).

Therefore the intent of `_setSource`:
```
decimals_ = 10 + IERC20(CTokenInterface(source).underlying()).decimals()
```
e.g., cDAI → `decimals_ = 28`; cUSDC → `decimals_ = 16`.

##### (2d) Line-by-line analysis (`_setSource` line 109-124)

```solidity
109  function _setSource(bytes6 cTokenId, bytes6 underlying, address source) internal {
110      uint8 decimals_ = 18; // Does the borrowing rate have 18 decimals?   // BUG
111      require (decimals_ <= 18, "Unsupported decimals");
112      sources[cTokenId][underlying] = Source({
113          source: source,
114          decimals: decimals_,
115          inverse: false
116      });
117      sources[underlying][cTokenId] = Source({
118          source: source,
119          decimals: decimals_,
120          inverse: true
121      });
122      emit SourceSet(cTokenId, underlying, source);
123      emit SourceSet(underlying, cTokenId, source);
124      // }
```

- **L110 (BUG)**: `decimals_` is hardcoded to `18`. The comment `// Does the borrowing rate have 18 decimals?` reveals that the developer was uncertain — and ultimately committed a wrong assumption to code.
- **L111**: tautology (`18 <= 18`). If the actual underlying decimals had been queried, this guard would have had meaning.
- **L112-116**: stores the forward entry. `decimals = 18` flows into the `_peek` branch as the exponent `18 - 18 = 0` → `price = rawPrice * 10^0 = rawPrice`. If the underlying is DAI, `rawPrice` is on the `10^28` scale, but is exposed as a price asserting the 18-dp convention → **inflated by a factor of 10^10**.
- **L117-121**: stores the reverse entry (inverse). Same `decimals = 18` is stored → in the `_peek` inverse branch, `10^(18+18) / rawPrice = 10^36 / rawPrice`. If the underlying is DAI, this yields a value on the order of `10^36 / 10^28 = 10^8`, violating the 18-dp price convention.
- **L122-123**: bidirectional events.

##### (2e) Root meaning of the bug

Because `_setSource` lacks the instruction "look up underlying's decimals", the stored `source.decimals = 18` is used as a **wrong normalization exponent** in every subsequent rate computation. The formulas in `_peek`/`_get` are algebraically correct, but the input parameter `source.decimals` is wrong, producing systematic scale errors.

Protocol-level: same path as Case 1 — a Yield vault uses this oracle's result for collateral valuation → cUSDC collateral is undervalued by 10^2× and instantly liquidated, or cDAI collateral is inflated by 10^10× and used for unsecured loans. **A systematic bias** (the bug direction differs by underlying token), allowing an attacker to choose the favorable direction.

##### (2f) Correct fix

Implementing the audit recommendation:
```solidity
uint8 uD = IERC20(CTokenInterface(source).underlying()).decimals();
uint8 decimals_ = uint8(10 + uD);
require(decimals_ <= 36, "Unsupported decimals");   // prevent overflow in _peek inverse branch
```
The sponsor patched in this direction in commit `e9c1ee5532...`.

#### 3. IntentChecker annotation attempt

**(a) State variable change?** — there are writes to `sources[...][...]` (L112, L117). `changed(sources[cTokenId][underlying], true)` is satisfied by both buggy and correct (both write, only the values differ). → cannot distinguish qualitatively.

**(b) Arithmetic expression of the correct value?** — ideal annotation:
```
@Post sources[cTokenId][underlying].decimals == 10 + IERC20(CTokenInterface(source).underlying()).decimals()
```
- `IERC20(...).decimals()`, `CTokenInterface(source).underlying()` → **G1** (function calls). Both are view, so theoretically eligible for `@IReturn`, but:
  - The corresponding call sites **do not exist** in the body of `_setSource` (it does not fetch underlying or decimals).
  - `@IReturn` only supplies values for call expressions present in the code. It cannot "virtually inject" a non-existent call by annotation.
- Considering only the numbers, `10 + <token decimals>` is a plain `+`, allowed by the grammar. However, no variable for `<token decimals>` exists anywhere in the function scope or inherited scope → **G3**.
- Workaround: putting the value of `decimals_` itself in via `@LocalVar` would be **declaring the input as the buggy value `18` to be the correct answer**. Value condition is impossible.

**(c) Bug-awareness presupposed?** Does not get this far.

**Prediction**: expression fails at the annotation-writing step → no verdict on either side.

#### 4. Classification validity

- Current: **L4a**. Maintain.
- Blocker: the correct value depends on "the returns of two view calls that do not exist in the code". Furthermore, what is wrong is not a hop-wise computation result but **the value of the stored parameter itself**, which propagates to all downstream computations.
- The explanation in `annotation_plans.md` lines 2006-2012 is accurate. However, making explicit that "a new intermediate computation is required" is the combination G1+G3 would be sharper.

#### 5. Root cause

**Essence (one-liner)**: for IntentChecker to detect that `decimals_ = 18` at L110 is wrong, a grammar-expressible annotation distinguishing buggy from correct must be constructible **using only the existing variable landscape of `CTokenMultiOracle`**. But **even an omniscient developer cannot write such an annotation** — because the operands of the relation do not exist anywhere in the contract. (This is the decisive difference from L5a "missing-code": in L5a, the landscape is sufficient but the choice of "which annotation to write" presupposes bug awareness — in this case the landscape itself is insufficient.)

**Variable inventory check** — identifiers visible at L110 and possible relations to `decimals_`:

| Identifier | Type | Relation possible with `decimals_` |
|---|---|---|
| `decimals` (contract constant) | `uint8` = 18 | `decimals_ == decimals` → tautology (18 == 18). Cannot distinguish buggy/correct |
| `cTokenId`, `underlying` | `bytes6` | Type mismatch — no numeric arithmetic |
| `source` | `address` | Type mismatch |
| `sources[...][...]` | struct mapping | Empty at L110, then filled with `decimals_` itself |

→ **No variable in the contract corresponds to the operand `uD` (underlying decimals)** of the correct value `10 + uD`. To obtain the value, two external calls — `CTokenInterface(source).underlying()` followed by `IERC20(...).decimals()` — are needed, and neither is used in this function (`_setSource`).

G-surface:
- **G1** — `CTokenInterface(...).underlying()` and `IERC20(...).decimals()` cannot be written in intentValue.
- **G3** — no variable holds the returns of these calls + **the call sites themselves do not exist** → the `@IReturn` workaround is also unavailable.
- **G2 not applicable** — the required arithmetic is `10 + x`. Only operations allowed by the grammar. The sole problem is that `x` cannot be obtained.

**Side observation vs Case 1**: Case 1's `_peek` passes through the decimals numeric domain at least once via `10 ** source.decimals`. Case 2's `_setSource` does not enter the decimals domain at all — `18` is fabrication, not a trace. The runtime trace depths differ, but **on the annotation-blocking side, both converge to "the relation operands are not in the contract"**.

**L4a ↔ L5 boundary observation** — fixing a specific cToken-underlying pair makes a constant annotation (`sources[cDAI][DAI].decimals == 28`) grammar-expressible. However:
- Attaching a single annotation across all pairs requires referencing uD → uD is outside the contract → **L4a**.
- Hardcoding constants per pair is expressible, but the constant = the answer knowledge → **L5a-flavored** (bug-awareness).

This separation between "general form ↔ specific form" is a boundary phenomenon between L4a and L5 worth citing in the paper.

**[Category (I8)]**: **Value error / Type B** — at the position of the hardcoded `18`, no proxy for `uD` (the operand of the correct value `10 + uD`) exists in scope or in the contract. Proper L4a.

---

### Case 3 — `web3bugs_29_H_05` (current classification: **L4a**)

#### 1. Audit report citation

- **Source**: `reports/29.md` → `[H-05] hybrid pool uses wrong non_optimal_mint_fee`
- **Severity**: High. **Warden**: broccoli (C4 2021-09-sushitrident).
- **Core claim (verbatim excerpt)**:
  > When an LP provider deposits an imbalanced amount of tokens, a swap fee is applied. `HybridPool` uses the same `_nonOptimalMintFee` as `constantProductPool`; however, since the two pools use different AMM curves, the ideal balance is not the same.
  >
  > Stable swap pools are designed for 1B+ TVL. Any issue related to pricing/fee is serious. I consider this is a high-risk issue.
- **Recommended fix**: rewrite in the manner of Curve's `StableSwap3Pool.vy#L322-L337` — compute the ideal balance based on the difference of the invariant `D` before and after deposit.
- **Sponsor**: confirmed.

#### 2. Understanding the code's meaning

##### (2a) Contract purpose and system role

`HybridPool` — a stableswap pool template in Sushi **Trident**. For asset pairs close to 1:1 (e.g., USDC-USDT, DAI-USDC), it minimizes slippage using a Curve-style amplified invariant `D`. The Trident router/aggregator interacts with this pool, and all price/liquidity/fee computations within the pool are subordinate to the stableswap invariant.

##### (2b) Function role within the contract

`_nonOptimalMintFee(_amount0, _amount1, _reserve0, _reserve1) → (token0Fee, token1Fee)` (line 426-441, internal view).
- Caller: `mint(bytes data)` (line 99).
- Role: when an LP provider makes an **imbalanced deposit**, treat it as if an implicit swap occurred and charge the corresponding swap fee. The fee is deducted before computing the LP token reward.
- A wrong fee leads to under/over-collection of protocol revenue and to distorted value transfer between LPs.

##### (2c) Function intent (formula)

The correct intent based on stableswap theory:
- D₀ = current invariant (pre-deposit): `D₀ = computeLiquidity(_reserve0, _reserve1)`
- D₁ = post-deposit invariant: `D₁ = computeLiquidity(_reserve0 + _amount0, _reserve1 + _amount1)`
- For each token i, the **ideal balance** (under balanced growth): `idealᵢ = D₁ × _reserveᵢ / D₀`
- **Imbalance** (actual post-balance − idealᵢ): `|(_reserveᵢ + _amountᵢ) − idealᵢ|`
- Fee per token: `swapFee × imbalanceᵢ / (2 × MAX_FEE)`

That is, the definition of "ideal balance" depends on the curve:
- **Constant product** (xy=k): `idealᵢ = _amountⱼ × _reserveᵢ / _reserveⱼ` — reserve ratio.
- **Stableswap** (D-invariant): the formula above. D must be computed by Newton iteration.

##### (2d) Line-by-line analysis (line 426-441)

```solidity
431  ) internal view returns (uint256 token0Fee, uint256 token1Fee) {
432      if (_reserve0 == 0 || _reserve1 == 0) return (0, 0);
433      uint256 amount1Optimal = (_amount0 * _reserve1) / _reserve0;   // BUG — CP formula
434
435      if (amount1Optimal <= _amount1) {
436          token1Fee = (swapFee * (_amount1 - amount1Optimal)) / (2 * MAX_FEE);
437      } else {
438          uint256 amount0Optimal = (_amount1 * _reserve0) / _reserve1;   // BUG — CP formula
439          token0Fee = (swapFee * (_amount0 - amount0Optimal)) / (2 * MAX_FEE);
440      }
441  }
```

- **L432**: empty-pool handling — if either is 0, no fee. (Applies on virgin mint.)
- **L433 (BUG)**: `amount1Optimal = _amount0 × _reserve1 / _reserve0`. This is the **constant-product** pool's balanced-deposit formula. In StableSwap, the reserve ratio is not the ideal deposit ratio (the amplification A flattens the curve).
- **L435**: if the deposited `_amount1` is below CP-optimal → token1 is short → fee is charged on the token1 side.
- **L436**: `token1Fee = swapFee × (_amount1 - amount1Optimal) / (2 × MAX_FEE)`. The structure of the formula is right, but `amount1Optimal` is wrong.
- **L437-440**: opposite branch; same bug, computing `amount0Optimal` with the CP formula and then the fee.
- **L441**: end.

##### (2e) Root meaning of the bug

HybridPool runs on a stableswap curve with amplification `A`, so **the price curve is piecewise flat**. The larger `A`, the smaller the price deviation caused by small imbalances. Therefore the criterion for "how imbalanced was the LP" is **not the reserve ratio** but the **invariant-D-based ideal balance**.

Using the CP formula directly:
- In a normal stableswap environment (small price impact), **imbalance is overestimated** → a fee larger than the actually induced swap is charged. The LP loses unjustly.
- At extreme imbalance (near depeg), **underestimation** is also possible.
- From an attacker's viewpoint: an LP can reverse-engineer this formula to design deposit patterns that yield rewards (MEV).

Protocol-level: under stableswap's 1B+ TVL design assumption, even small fee distortions accumulate to large amounts, and the pool's incentive structure (the LP bears in proportion to the imbalance contribution) itself breaks.

##### (2f) Correct fix

```solidity
function _nonOptimalMintFee(...) internal view returns (uint256 token0Fee, uint256 token1Fee) {
    if (_reserve0 == 0 || _reserve1 == 0) return (0, 0);
    uint256 D0 = _computeLiquidity(_reserve0, _reserve1);
    uint256 D1 = _computeLiquidity(_reserve0 + _amount0, _reserve1 + _amount1);
    uint256 ideal0 = D1 * _reserve0 / D0;
    uint256 ideal1 = D1 * _reserve1 / D0;
    uint256 new0 = _reserve0 + _amount0;
    uint256 new1 = _reserve1 + _amount1;
    uint256 diff0 = new0 > ideal0 ? new0 - ideal0 : ideal0 - new0;
    uint256 diff1 = new1 > ideal1 ? new1 - ideal1 : ideal1 - new1;
    token0Fee = swapFee * diff0 / (2 * MAX_FEE);
    token1Fee = swapFee * diff1 / (2 * MAX_FEE);
}
```
The canonical structure of Curve StableSwap3Pool.vy L322-337. `_computeLiquidity` (line 341) is an internal view function HybridPool already defines — Newton iteration built in.

#### 3. IntentChecker annotation attempt (including a development-time perspective)

**Development-time assumption**: HybridPool's author understands the stableswap structure (they wrote `_computeLiquidity`, `_getY`, `_getYD`). What if, without bug awareness, they try to attach annotations to `_nonOptimalMintFee`?

**(a) State variable change?** — `_nonOptimalMintFee` is `internal view`, with no storage write. The `changed`/entry-exit channels are absent.

**(b) Distinguishing buggy/correct with grammar-expressible annotations on the existing landscape?**

In-scope variables: `_amount0`, `_amount1`, `_reserve0`, `_reserve1`, `swapFee`, `MAX_FEE`, `amount1Optimal` (or `amount0Optimal`), `token0Fee`, `token1Fee`. All uint256. Grammar-expressible annotations are only **polynomial-arithmetic combinations** of these.

Annotations a development-time developer would naturally try:

1. **Upper/lower bound**: `@Post token1Fee <= swapFee * _amount1 / MAX_FEE`. Grammar OK. But satisfied by both buggy and correct → cannot distinguish.
2. **Ratio-based intent**: `@Post token1Fee == swapFee * (_amount1 - _amount0 * _reserve1 / _reserve0) / (2 * MAX_FEE)` (when the developer defines "imbalance = _amount1 − CP-optimal"). Grammar OK. **But this is exactly the formula of the buggy code** → buggy is tautologically satisfied; correct is violated. Result: **IntentChecker incorrectly judges the correct code as a violation**.
3. **Correct stableswap formula**: of the form `@Post token1Fee == swapFee * (_new1 - D1 * _reserve1 / D0) / (2 * MAX_FEE)`. `D0`/`D1` are not in the function scope → **expression fails**.

→ **Key observation (mathematically rigorous)**: the grammar's expressive range = **rational-polynomial functions** of the scope variables. The correct ideal balance, however, depends on the stableswap invariant D, and D is the solution of the cubic equation `D³ − 16A·xy·D + 16A·xy·(x+y) − 4xy·D = 0` which is **not rational-polynomial** (cube roots appear under Cardano's formula). Therefore, even though `A`, `_reserve0`, `_reserve1` are all in scope, **no rational-polynomial combination of them equals D**. Not a shortage of materials, but rather **outside the closure of the allowed operations** (a structural constraint analogous to the impossibility of trisecting an angle with compass and straightedge).

In this context, the "most economically plausible" rational-polynomial specification a developer naturally tries (`_amount_j × _reserveᵢ / _reserveⱼ`) is precisely **the buggy formula itself**. Many other expressions are allowed by the grammar, but none of them is correct, and the simplest, most intuitive candidate happens to coincide with the buggy code, creating the risk of **IntentChecker actively sanctioning the bug**.

**(c) Auxiliary local injection workaround?**: the developer can extend the landscape by adding `uint256 D0 = _computeLiquidity(_reserve0, _reserve1);` at the top of the function. Then `@Post amount1Optimal == D1 * _reserve1 / D0` is grammar-expressible. However:
- This injection is a **production code change**, and the developer must know that "D is involved in fee computation" to perform it → **bug-awareness presupposed**.
- After injection, "buggy amount1Optimal = CP-based ≠ D-based ideal", so the annotation fires — i.e., **L4a moves into the L5 region via auxiliary injection**.

**Inexpressible under "pure annotation-only" paradigm** → confirmed L4a.

#### 4. Classification validity

- Current: **L4a**. Maintain.
- Nature of the blocker: in the function's existing variable landscape, no grammar-expressible annotation distinguishes buggy from correct. The grammar's algebraic range exactly covers the CP formula family — i.e., a peculiar arrangement where **all "candidate correct answers" expressible by the grammar are in fact wrong (the buggy code itself)**.
- The explanation in `annotation_plans.md` lines 1419-1424 is accurate. However, the phrase "D is computed by Newton iteration" — does it convey to the reader the true cause of the limitation? Making explicit that **the analysis engine can call/abstract `_computeLiquidity`, but the annotation grammar does not allow function calls** would be clearer.

#### 5. Root cause

**Essence (I3 axis α — function call inside variable relation)**: in `_nonOptimalMintFee`'s scope, the variables contributing to the correct relation (`_reserve0`, `_reserve1`, `_amount0`, `_amount1`, `swapFee`, `MAX_FEE`, `A`, `N_A`, `A_PRECISION`) **do exist**. The problem is that the correct relation cannot be expressed as a rational-polynomial combination of these alone, and instead requires the return values of **two internal function calls**: `_computeLiquidity(_reserve0, _reserve1)` and `_computeLiquidity(_reserve0 + _amount0, _reserve1 + _amount1)`. Since the intentValue grammar only allows variables and constants, function calls cannot enter the relation.

Distinction from Case 2: in Case 2, the variable to be related is itself absent from scope (axis β). This case is the same axis as Case 1 (axis α) — not a shortage of materials, but **correctly combining the materials requires a function call across function boundaries**.

Sub-variation (within I3 axis α):
- **Case 1**: external interface view call (`IOracle(source.source).decimals()`) — potentially accessible via `@IReturn`-style binding under a grammar extension.
- **Case 3 (this case)**: **internal view function** (`_computeLiquidity`) — the current `@IReturn` is interface-only, so even with grammar extension, a separate channel must be designed.

G-surface:
- **G1** — `_computeLiquidity(...)` cannot be written in intentValue (internal function call).
- **G3** — locals holding D₀, D₁ values are absent from `_nonOptimalMintFee`'s scope. (Injection path → see I4 — moves to the L5 region.)
- **G2 not applicable** — per the user's observation, once D is obtained, repeated multiplication like `D*D*D` suffices. The absence of `**` is not the primary blocker of this case.

**Side observation — the "silent sanction" risk (from I5)**: among the rational-polynomial specifications allowed by the grammar, the "most economically plausible" choice (`_amount_j × _reserveᵢ / _reserveⱼ`) happens to be the buggy formula itself. An annotation written in good faith by the developer can tautologically validate the buggy code → **a risk case where fail-by-confirmation mode is possible even within L4a**. An additional risk layered on the general I3 axis α pattern, independent of the α classification itself.

**[Category (I8)]**: **Algorithm error / Type B** — the wrong formula family (CP) is selected. The correct stableswap formula requires the value `D`, but none of `D`/`D₀`/`D₁` is in the scope of `_nonOptimalMintFee`. A single-step algorithm error.

#### 6. Suggested rewrite of paper sentence

The current L4a sentence (line 1307) can be kept, but this case's insight is worth placing in a **separate insight paragraph** in the Discussion (see item C5):
> *When the annotation grammar's algebraic range coincides with the buggy code's formula, even a well-intentioned developer producing the most specific annotation confirms the buggy behavior. This is a failure mode of simple grammars that goes beyond "inexpressibility" — the specification language silently sanctions the wrong answer.*

---

### Case 4 — `web3bugs_39_H_02` (current classification: **L4a** → reclassification proposal: **L5b**)

#### 1. Audit report citation

- **Source**: `reports/39.md` → `[H-02] Swivel: Taker is charged fees twice in exitVaultFillingVaultInitiate`
- **Severity**: High (judge upgrade). **Warden**: itsmeSTYJ, also gpersoon (C4 2021-09-swivel).
- **Core claim (original excerpt)**:
  > Taker is charged fees twice in `exitVaultFillingVaultInitiate()`. Maker is transferring less than premiumFilled to taker and then taker is expected to pay fees i.e. taker's net balance is `premiumFilled - 2*fee`.
- **Reason for judge promotion**: "fees are being incorrectly taken from the taker and not the maker, the maker ends up with a higher balance than expected and the taker has no way to recoup these fees (assets are now lost)".
- **Recommended fix** (audit-provided code):
  ```solidity
  uToken.transferFrom(o.maker, msg.sender, premiumFilled);        // full premium
  uToken.transferFrom(msg.sender, address(this), fee);             // fee once
  ```
  That is, change `premiumFilled - fee` at L280 to `premiumFilled`.
- **Sponsor**: confirmed.

#### 2. Understanding the Code

##### (2a) Contract purpose & position in system

`Swivel` — the on-chain order matching engine of a fixed/floating yield splitting protocol. The taker fills off-chain signed orders (`Hash.Order`). Order types: 4 combinations of zcToken (fixed yield) / Vault (floating yield) × initiate / exit. On each match, Swivel collects a fee at the reciprocal ratio of the `fenominator` array (`[200, 600, 400, 200]`). Swivel itself acts as the coordinator that handles ERC20 escrow and MarketPlace contract calls.

##### (2b) Function's role within the contract

`exitVaultFillingVaultInitiate(o, a, c)` (L268–289, internal):
- Caller: dispatched by public `exit(...)` (L209–234) when `o[i].exit == true` and `o[i].vault == true`.
- Scenario: when a maker has placed an off-chain "vault(nToken) initiate" order, msg.sender **sells (exits)** their own nToken. Sender = vault holder seller, maker = vault buyer. Maker pays the premium, sender transfers nToken.
- An incorrect amount calculation causes the sender to either not receive the premium or to pay double → direct asset loss.

##### (2c) Function intent (formulas)

Intended token flows:
- `premiumFilled = a * o.premium / o.principal` — premium that maker pays to sender (proportional to the principal sold).
- `fee = premiumFilled / fenominator[3]` — protocol fee (vaultExit fee ratio).
- **Maker → Sender**: `premiumFilled` (full premium).
- **Sender → Swivel**: `fee`.
- **Sender → Maker**: `a` nToken (notional, `p2pVaultExchange`).

Sender net cash flow: `+premiumFilled - fee`.

##### (2d) Line-by-line analysis (L268–289)

```solidity
269  bytes32 hash = validOrderHash(o, c);
271  require(a <= (o.principal - filled[hash]), ...);
273  filled[hash] += a;
275  uint256 premiumFilled = (((a * 1e18) / o.principal) * o.premium) / 1e18;
276  uint256 fee = ((premiumFilled * 1e18) / fenominator[3]) / 1e18;
278  Erc20 uToken = Erc20(o.underlying);
280  uToken.transferFrom(o.maker, msg.sender, premiumFilled - fee);   // BUG
283  uToken.transferFrom(msg.sender, address(this), fee);
286  require(MarketPlace(marketPlace).p2pVaultExchange(..., msg.sender, o.maker, a), ...);
288  emit Exit(...);
```

- **L269–273**: After signature/cancellation/expiry validation, `filled[hash] += a` updates the cumulative fill amount of the order (state write).
- **L275**: Computes `premiumFilled` (overflow-safe 1e18 scaling order).
- **L276**: Computes `fee` (`fenominator[3] = 200` default → 0.5% of premium).
- **L278**: ERC20 handle.
- **L280 (BUG)**: "Maker sends sender the premium **with fee already deducted**". The developer's incorrect assumption: "Since the sender will pay the fee anyway, deducting it on the maker side allows handling in a single transfer" — overlooking L283.
- **L283**: Sender pays the fee to Swivel. The sender, who already received less by the fee amount in L280, pays the fee again here → **double burden**.
- **L286**: Delegates nToken transfer (sender → maker) to MarketPlace.

##### (2e) Fundamental meaning of the bug

**A combinational error of two transfers**. The amount calculation of each transfer is individually free of syntactic/arithmetic problems (`premiumFilled - fee`, `fee` are both valid uint256). However, **the net effect of the two transfers deviates from the intent**:
- Intent: sender net income = `+premiumFilled - fee`
- Actual: sender net income = `+(premiumFilled - fee) - fee = +premiumFilled - 2·fee`

Protocol-level: the sender loses **twice the stated fee** per order. The maker conversely pays less by the fee and gains. As the judge points out, the taker has no means to recover assets.

Characteristic of this case: the bug is **not a single-line formula error but a "intent split" failure between two external calls**. Of "the maker sends after deduction" + "the sender also pays the fee", exactly one must be removed.

##### (2f) Correct fix

As proposed by the audit. Change `premiumFilled - fee` at L280 to `premiumFilled`. Keep L283. A one-line fix.

#### 3. IntentChecker annotation attempt (development-time perspective)

**(a) State variable change?** `filled[hash] += a` is a state write but identical in both buggy and correct → cannot be distinguished by `changed`.

**(b) Express "net flow" via `@Post`?** Sender net income = entry-exit difference of external ERC20 `uToken.balanceOf(msg.sender)`. However:
- Not a state variable of the Swivel contract → cannot be referenced in Swivel scope.
- `@IReturn` is a debug annotation (for the analysis engine), not an intent input (I1).
- The `@Post` path is therefore blocked.

**(c) `@During` + `.arg[n]` path** (a channel missed by annotation_plans):

The grammar's duringClause allows `identifier.arg[n] relOp intentValue` (limitation_types.md L5b example: `pool0.swap.arg[0] == 0`). Above the L280 call:

```solidity
// @During uToken.transferFrom.arg[2] == premiumFilled
uToken.transferFrom(o.maker, msg.sender, premiumFilled - fee);   // buggy
```

- Buggy: arg[2] = `premiumFilled - fee` ≠ `premiumFilled` → **VIOLATED**.
- Correct (after fix): arg[2] = `premiumFilled` → **SATISFIED**.
- The operand `premiumFilled` is a local declared in L275, in scope. Fully grammar-permitted.

→ **A grammar-expressible distinguishing annotation exists**.

**Pitfall from a development-time perspective (silent sanction reappears)**: if the developer reflects the L280 buggy code as-is and writes the natural intent "maker sends premium-fee":
```
// @During uToken.transferFrom.arg[2] == premiumFilled - fee
```
→ buggy is tautologically satisfied, correct is violated (false positive). The **I5 silent sanction** pattern appears not only in L4a but also in the L5b category.

To write the correct annotation `arg[2] == premiumFilled`, one must understand the mechanism "the maker must send the full premium, the fee is collected separately" = fix knowledge = **bug awareness as a precondition**.

#### 4. Classification validity — **L4a retained (after attempting and withdrawing L5b reclassification)**

**Review process**: The initial analysis proposed reclassification to L5b on the grounds that `@During uToken.transferFrom.arg[2] == premiumFilled` at L280 is grammar-expressible and distinguishes buggy/correct. However, **L4a is retained** for the following reasons:

**(1) The true intent depends on external ERC20 state** — exactly matches the L4a definition:
- The essence of the bug is "the sender's **net income (net token flow)** falls short of the intent by the fee amount", an external ERC20 balance change.
- `limitation_types.md` L4a definition: "the correct value depends on external contract state, function calls, or new intermediate computation" — **exactly this case**.
- Sender net income = entry-exit difference of `uToken.balanceOf(msg.sender)` → outside Swivel scope → `@Post` path blocked.

**(2) `.arg[2] == premiumFilled` is not the intent but a proxy**:
- The natspec above L280 is `// transfer premium minus fee from maker to sender` — **describes the buggy intent verbatim**. If the developer follows the natspec when writing the annotation, they get `arg[2] == premiumFilled - fee` (matching the buggy).
- Path to derive the correct `arg[2] == premiumFilled`:
  1. ERC20 `transferFrom` semantics (external standard knowledge).
  2. **Cross-line accounting** of L280 + L283: sender net income = `+arg[2]_L280 - arg[2]_L283`.
  3. Intended net flow = `premiumFilled - fee` (protocol design knowledge).
  4. Solving the system → arg[2]_L280 = `premiumFilled`.
- That is, deriving the local proxy requires **cross-line back-solving + natspec override + external standard knowledge**. This qualitatively exceeds the bug-awareness level of typical L5b ("noticing a wrong arg/operator/field at a single location" — e.g., 52_H_15, 113_H_05).

**(3) Refining I2 "omniscient developer test" (→ I7)**:
- Formal criterion: "does a grammar-expressible annotation distinguish buggy/correct".
- However, including cases where a **local proxy annotation** incidentally has distinguishing power makes the L4a/L5 distinction meaningless.
- Refined criterion: "does a grammar-expressible annotation that **directly expresses the correct intent** exist". Case 4's intent (net flow) cannot be directly expressed due to dependence on external state → **L4a**.

**Conclusion**: **L4a retained**. The `.arg[n]` proxy has formal expressibility, but on the intent-level expressibility criterion it falls under L4a.

#### 5. Root cause

**Essence**: The bug's correctness condition depends on **external ERC20 contract state (sender balance)**. There is no channel in the annotation grammar to directly reference state outside the Swivel scope (`@Post` cannot express external state, `@IReturn` is for debugging and cannot enter intent — I1).

**A new sub-pattern within L4a — "cross-line accounting" bug**:
- The bug is not a single-line formula error but arises from **the combination of multiple external calls**.
- Each call's local args are syntactically valid but the net effect differs from intent.
- The intent of such bugs is essentially **multi-point accumulation (balance changes)** — cannot be expressed by a single-point annotation.
- Distinguished from Case 1's "function call result needed" (axis α) and Case 2's "no variable to relate" (axis β), this is the **axis γ — multi-point accounting cannot be expressed by single-point annotation** pattern.

G-surface:
- **G1 (indirect)** — referencing sender balance requires calling `uToken.balanceOf(msg.sender)`. intentValue does not allow function calls.
- **G3 (primary)** — no scope variable holds the net flow value. External balance changes are outside Swivel scope.
- **G8 (applicable)** — depends on external contract state (ERC20 balance).

**Silent sanction of the natural annotation**: if the developer follows L280's natspec ("premium minus fee from maker") verbatim, the buggy intent is annotated → buggy tautologically satisfied, correct violated. **I5 silent sanction** here arises because the natspec is synchronized with the buggy implementation. This is the typical failure mode of L4a, and the most dangerous variant — "if the annotation follows the natural intent of code/documentation, it automatically reconfirms the buggy".

**[Category (I8)]**: **Algorithm error / Type B** — the fee-distribution composition of the two transfers is wrong. The correct intent (sender net income) is an external ERC20 balance change, outside Swivel scope. Cross-line accounting algorithm error.

#### 6. Suggestions for paper text improvement

- **L4a body (line 1307)**: Keep the current sentence's enumeration of "external contract's state, function call that does not appear", but it would add value to add one line on the **"cannot capture multi-point accounting with single-point annotation"** sub-pattern. Case 4 is the representative of this pattern.
- **Discussion — intent-level expressibility (I7)**: Distinguish formal expressibility vs intent-level expressibility as separate axes. State that the real criterion of the L4a/L5 boundary is the latter.
- **Silent sanction extension (I5)**: natspec-code consistency can induce silent sanction. Suggest in the Discussion that an annotation-driven development workflow must accompany natspec review.

---

### Case 5 — `web3bugs_51_H_04` (current classification: **L4a**)

#### 1. Audit report citation

- **Source**: `reports/51.md` → `[H-04] Swaps are not split when trade crosses target price`
- **Severity**: High. **Warden**: cmichel, gzeon (C4 2021-11-bootfinance).
- **Core claim (original excerpt)**:
  > The protocol uses two amplifier values A1 and A2 for the swap, depending on the target price. The swap curve is therefore **a join of two different curves at the target price**. When doing a trade that crosses the target price, it should first perform the trade partially with A1 up to the target price, and then the rest of the trade with A2.
  >
  > However, `SwapUtils.swap / _calculateSwap` does not do this, it only uses the "new A", see `getYC` step 5:
  > ```solidity
  > if (aNew == a) { return y; }
  > else { return getY(self, ..., x, xp, aNew, d); }   // BUG
  > ```
- **Impact**: "Worse (better) average execution price. In the worst case, it could even be possible to make the entire trade with one amplifier and then sell the swap result again using the other amplifier making a profit" — **a free arbitrage attack path**.
- **Recommendation**: split the trade into two segments and apply A1, A2 respectively.
- **Sponsor**: confirmed.

#### 2. Understanding the Code

##### (2a) Contract purpose & position in system

`SwapUtils` — Boot Finance's dual-amplifier StableSwap library. It uses Curve-style invariant by default but has a piecewise curve structure that **switches the amplifier depending on the price region**:
- `xp[0] < xp[1]` → uses amplifier **A1**
- `xp[0] >= xp[1]` → uses amplifier **A2**
- The boundary (`xp[0] == xp[1]`) is the "target price". The curve bends at this point.

This structure is a design of Boot Finance to implement custom pricing behavior tailored to individual asset-pairs. When a swap **crosses the boundary** and the entire amount is computed with a single A, price distortion occurs → LP value damage + taker arbitrage.

##### (2b) Function's role within the contract

`getYC(self, tokenIndexFrom, tokenIndexTo, x, xp) → uint256 y` (L735–771, internal view):
- Caller: `_calculateSwap` (L914–933) → ultimately invoked by external `swap()` (L1098–1152).
- Role: "When the FROM token is increased to `x` (new total amount), how much TO token must remain in the pool for the invariant to hold".
- The returned `y` → swap result is computed as `dy = xp[tokenIndexTo] - y - 1`. This `dy` is transferred to msg.sender, and state `balances[tokenIndexTo]` decreases.

##### (2c) Function intent (formulas)

Normal intent under single-A assumption (StableSwap standard):
```
given A, d, x → solve for y such that invariant(xp with tokenFrom=x, tokenTo=y, A) = d
```
`getY` solves it via Newton iteration.

**Correct intent in the dual-A case** (audit proposal):
1. Does the swap cross the boundary? (when `aNew != a`).
2. Compute the amount `dx₁` up to the boundary point (`xp[0] == xp[1]`).
3. Partial swap 1: (`dx₁` portion of x, A, d) → intermediate `y₁`, intermediate state.
4. New invariant in the intermediate state `d₂ = getD(intermediate xp, aNew)`.
5. Partial swap 2: (remaining `x - dx₁`, aNew, d₂) → final `y₂`.
6. Return `y₂`.

##### (2d) Line-by-line analysis (L735–771)

```solidity
742  uint256 numTokens = self.pooledTokens.length;
753  uint256 a = determineA(self, xp);        // (1) A of current state
756  uint256 d = getD(xp, a);                 // (2) invariant under current A
759  uint256 y = getY(self, ..., x, xp, a, d);// (3) new y computed under single A
762  uint256 aNew = _xpCalc(self, ..., x, y); // (4) A of the new region based on the computed y
765  if (aNew == a) {
766      return y;                            // boundary not crossed → normal
767  } else {
768      return getY(self, ..., x, xp, aNew, d);  // BUG: full recomputation with aNew + old d
769  }
```

- **L753**: `determineA` — determines the current A by comparing `xp[0]` vs `xp[1]`.
- **L756**: Compute invariant `d` from current xp and A (Newton loop).
- **L759**: Compute y for x via `getY` (Newton loop). **Assumes A does not change** — a single-A swap.
- **L762**: With the computed y, check what the post-state A would be (`_xpCalc`).
- **L765–766**: A is unchanged → the single-A assumption was valid → return y.
- **L767–768 (BUG)**: A changed → single-A assumption invalid. But the code **recomputes the entire swap with the new A (aNew) and the old d**. This:
  - `d` is the curve invariant value of the old region. In the new-region curve (A=aNew) this invariant is meaningless.
  - Applies only the new A to the entire swap → price distortion in the segment before the boundary.
  - As the audit notes, arbitrage is possible: profit in the cycle of buying with one A and selling with the other A.

##### (2e) Fundamental meaning of the bug

The pool's price curve is a **bent piecewise curve at the target price**. Curve1 and curve2 connect continuously at that point but have different slopes. A correct swap must **compute the movement amount in each segment with the corresponding A and sum**.

The buggy version "recomputes everything with aNew when A changes" — as if assuming the curve has A=aNew over the entire range. For a trade crossing the boundary:
- The price impact of the early trade (old region) is computed by the aNew curve and is **over/underestimated** compared to the actual curve1.
- The cumulative result `y` differs from the actual curve-following result.
- Arbitrage path: buy with curve1 just before the boundary and sell with curve2 just after to make profit. The pool systematically loses.

Protocol-level: LP funds gradually drain, becoming an automatic harvest target for MEV bots.

##### (2f) Correct fix

Split as recommended by audit. Pseudocode:
```solidity
if (aNew != a) {
    uint256 dx1 = computeBoundaryX(self, tokenIndexFrom, xp, a, d);  // amount to reach boundary
    uint256 y1 = getY(self, tokenIndexFrom, tokenIndexTo, dx1, xp, a, d);
    // construct xp' as intermediate state
    uint256[] memory xpMid = ...;
    uint256 d2 = getD(xpMid, aNew);
    return getY(self, tokenIndexFrom, tokenIndexTo, x, xpMid, aNew, d2);  // remaining
}
```
Key unmaterialized elements: `computeBoundaryX` (finding the boundary point — a nonlinear equation), `xpMid` (intermediate state), `d2` (new invariant).

#### 3. IntentChecker annotation attempt (development-time perspective)

**Function-scope variables**: parameters (`tokenIndexFrom`, `tokenIndexTo`, `x`, `xp[]`), locals (`numTokens`, `a`, `d`, `y`, `aNew`), contract state (`initialA`, `futureA`, `initialA2`, `futureA2`, …).

**(a) State variable change?** `getYC` is internal view, no storage write. No `changed`/entry-exit channel. (The caller `swap` has them, but both buggy and correct decrease `balances` in the same direction — also indistinguishable as I3 β style.)

**(b) `@Post return == expr` path**:

Correct return value:
```
return == getY(...rest..., aNew, getD(xpMid, aNew))   // result of the second partial swap
```
- Both `getY(...)` and `getD(...)` are **internal function calls** → not allowed in intentValue (G1).
- `xpMid`, `d2`, `y1`, `dx1` — absent from scope (G3).
- `dx1` is the solution of the equation `xp[0] + dx1 == xp[1] - getY(...)` → itself the solution of a nonlinear equation, outside rational-polynomial.

**(c) Other annotation forms**:

| Attempt | Grammar | Buggy verdict | Correct verdict | Evaluation |
|---|---|---|---|---|
| `@Post return == y` (L759 result) | OK | VIOLATED (different value returned) | VIOLATED (split result ≠ y) | both violated, indistinguishable |
| `@Post getY.arg[5] == a` (i.e., the `a` arg of the second call must be the original `a`) | OK (.arg[n]) | VIOLATED (`aNew` passed) | — (correct uses the split approach so this constraint itself is meaningless) | not a meaningful correctness expression |
| Bound such as `@Post return >= xp[tokenIndexTo] - x` | OK | both satisfied | both satisfied | indistinguishable |

**For an omniscient developer to directly express the intent, the chain of two `getY` calls and one `getD` call must be embedded in the annotation** — outside the grammar's scope.

**I4 auxiliary local injection path**: insert `uint256 dx1 = ...; uint256 y1 = getY(...); uint256 d2 = getD(...); uint256 y2 = getY(...);` at the top of the function, then `@Post return == y2`. However:
- The insertion itself is equivalent to implementing the fix structure (split) — **bug awareness as a precondition**.
- Since the boundary-point `dx1` computation is the solution of a nonlinear equation, no closed form is injectable. An iteration routine such as binary search must be created — the depth of the production fix is large.

#### 4. Classification validity

- Current: **L4a**. ✅ Retain.
- I2 omniscient developer test: the correct intent (piecewise split) cannot be directly expressed by the grammar → L4a confirmed.
- I7 intent-level expressibility: even at the formal level, proxy annotations fail to distinguish buggy/correct → expression impossible at the formal level too.
- The analysis at `annotation_plans.md` L862–893 is accurate. In particular, the table "annotation approaches attempted and reasons for failure" well demonstrates the thoroughness of this case.

#### 5. Root cause

**Essence (Type B — proxy absent in scope)**:

Locals existing in `getYC` scope are `a`, `d`, `y`, `aNew`. These are all **values computed under the single-A assumption** — i.e., "the result of assuming x is swapped over curve 1 in its entirety". The correct intent is `y₂`, the piecewise split result, which involves:
- **Boundary point `M`** (the value satisfying `getD([M,M], a) == d`)
- **Intermediate state `xpMid`** (`[M, M]`)
- **New invariant `d₂ = getD([M,M], aNew)`**
- **Partial 1 result `y₁`**, **partial 2 result `y₂`**

None of these values **exist anywhere** in `getYC` scope or in `Swap` struct state. State variables (`initialA, futureA, balances, tokenPrecisionMultipliers, …`) only describe the current pool state and do not carry "hypothetical boundary points" or "intermediate state".

The existing `d`, `y` are in scope but unrelated to the correct relational expression. That is, **the proxy itself is absent** (Type B — user-suggested framing).

G-surface:
- **G3 (primary)** — necessary intermediates (M, xpMid, d₂, y₁, y₂) are all absent from scope/state.
- **Nonlinearity** (auxiliary) — `M` is the solution of the nonlinear equation `getD([M,M], a) == d`. Even if the grammar received a rational-polynomial extension, no closed form is constructible (the same transcendental barrier as Case 3's D).
- **Multi-step sequential dependency** (structure) — chain M → y₁ → xpMid → d₂ → y₂. Each step depends on the previous step's result. Since the grammar is a language describing "single relations", it has no expression structure for the chain itself.

**Relation to Cases 1, 2, 3 (Type A/B basis)**:
- Cases 2, 3, 5: Type B (no proxy) — no variable in scope is connected to the correct value.
- Case 1: Type A possibility (struct field `source.decimals` is a snapshot proxy) — separate L4a/L5b boundary re-examination needed (in the future).
- Therefore, despite Case 5's surface complexity (multi-step, nonlinear), the **essential blocker is the same "absence of proxy" as Cases 2 and 3**. The complexity merely explains the degree to which this absence is hard to resolve.

**[Category (I8)]**: **Algorithm error / Type B** — missing split decomposition. Correct requires all of the boundary point (M), intermediate state, d₂, y₁, y₂. None are in scope/state. Multi-step sequential algorithm error — the most complex axis among I8 matrix Type B.

#### 6. Suggestions for paper text improvement

- **L4a body (line 1307)**: Case 5 is an extreme example of the "multi-step algorithmic intent" sub-pattern. Cite as the "boundary point + partial swap chain" example in the I3 axis γ explanation of `paper_corrections.md`.
- **Discussion future work**: Limitations of the proposal to introduce "sequential computation" into the annotation grammar — cases like Case 5 where the number of steps is input-dependent require the grammar to effectively approach an imperative language to be effective. Simplicity tradeoff.
- **Arbitrage path explanation**: This case is one where the audit report explicitly presents the attack path of "buying with one amplifier and selling with the other amplifier" — the **most clear example of economically exploitable severity** among L4a cases. Worth citing in the Introduction motivation as evidence that "undetected bugs lead directly to economic loss".

---

### Case 6 — `web3bugs_51_H_06` (current classification: **L4a**)

#### 1. Audit report citation

- **Source**: `reports/51.md` → `[H-06] Ideal balance is not calculated correctly when providing imbalanced liquidity`
- **Severity**: High. **Warden**: jonah1005 (C4 2021-11-bootfinance).
- **Core claim (original excerpt)**:
  > In Saddle Finance, the optimal balance should be the same ratio as in the Pool. For example, if there's 10000 USD and 10000 DAI, the user should get the optimal LP if they provide liquidity with ratio = 1.
  >
  > However, if the `customSwap` pool is created with a target price = 2, **the user would get 2 times more LP if they deposit DAI**. The current implementation does not calculate ideal balance correctly. If the target price is set to be 10, the ideal balance deviates by 10. The fee deviates a lot.
- **POC (audit-provided)**: In a DAI/LINK pool with `target_price = 4`, an imbalanced deposit causes LP tokens to be **issued about 4× in excess**. That is, 4× profit on the same deposit — a pump attack path.
- **Recommended fix (audit)**: re-examine `self.balances` usage logic; compute `d0`/`d1` with consistent A.
- **Sponsor**: confirmed.

#### 2. Understanding the Code

##### (2a) Contract purpose & position in system

Same `SwapUtils` (the same contract as Case 5). Dual-A custom StableSwap. `addLiquidity` is the public path called when the LP provider deposits tokens. Inaccurate fee computation directly leads to **distortion of LP token issuance → LP value transfer attacks**.

##### (2b) Function's role within the contract

`addLiquidity(self, amounts[], minToMint) → toMint` (L1163–1270, external):
- LP deposits tokens into the pool → LP tokens are issued.
- An imbalanced deposit (depositing in a ratio different from the pool's) includes an **implicit swap** → swap fees are charged in proportion to imbalance, then LP tokens corresponding to the net deposit are issued.
- The accuracy of the fee is the foundation of **value fairness across all LPs**.

##### (2c) Function intent (formulas)

Standard StableSwap addLiquidity formulas:
1. `d0 = getD(oldBalances, A)` — pre-deposit invariant.
2. `newBalances[i] = oldBalances[i] + amounts[i]`.
3. `d1 = getD(newBalances, A)` — post-deposit invariant.
4. For each i:
   - `idealBalance[i] = d1 × oldBalances[i] / d0` — "what newBalance should be if balance was fairly maintained".
   - `fee[i] = feePerToken × |idealBalance[i] − newBalances[i]|` — fee proportional to imbalance.
5. `d2 = getD(feeAdjustedBalances, A)` reflecting the fee.
6. `toMint = (d2 − d0) × totalSupply / d0`.

**Key assumption**: `d0`, `d1`, `d2` must all be computed on **the same curve (same A)** for the ratio to be meaningful. The D of a different curve has different scale/units.

##### (2d) Line-by-line analysis (part of addLiquidity, L1178–1241)

```solidity
1178  if (self.lpToken.totalSupply() != 0) {
1179      v.d0 = getD(self);                                    // (1) based on current balances; internal determineA picks A
1180  }
1188  uint256[] memory newBalances = self.balances;
1190  for (...) { newBalances[i] = self.balances[i].add(amounts[i]); }    // (2) new balances
1216  v.preciseA = determineA(self, _xp(self, newBalances));    // (3) A based on new balances (A switching possible)
1222  v.d1 = getD(_xp(self, newBalances), v.preciseA);          // (4) compute d1 with NEW A
1223  require(v.d1 > v.d0, "D should increase");
1227  if (self.lpToken.totalSupply() != 0) {
1230      for (uint256 i = 0; i < self.pooledTokens.length; i++) {
1231          uint256 idealBalance = v.d1.mul(self.balances[i]).div(v.d0);  // BUG
1232          fees[i] = feePerToken
1233              .mul(idealBalance.difference(newBalances[i]))
1234              .div(FEE_DENOMINATOR);
1235          self.balances[i] = newBalances[i].sub(
1236              fees[i].mul(self.adminFee).div(FEE_DENOMINATOR)
1237          );
1238          newBalances[i] = newBalances[i].sub(fees[i]);
1239      }
1240      v.d2 = getD(_xp(self, newBalances), determineA(self, _xp(self, newBalances)));
1241  }
```

- **L1178–1179**: For non-initial LP cases, compute d0. Inside `getD(self)` is `determineA(self, _xp(self))` → **determines A from old balances** (call it A_old). Then calls `getD(xp_old, A_old)`.
- **L1188–1190**: Construct newBalances.
- **L1216 (Important)**: `v.preciseA = determineA(self, _xp(self, newBalances))` — **determines A from new balances** (call it A_new). If the deposit is large enough to invert the pool ratio, `A_old ≠ A_new`.
- **L1222**: `v.d1 = getD(xp_new, A_new)` — **computes d1 on the A_new curve**.
- **L1231 (BUG)**: `idealBalance = d1 × balances[i] / d0`. Here `d0` is on the A_old curve and `d1` is on the A_new curve. The two curves' D values have different units/scales → **the ratio is meaningless**. The result `idealBalance` is distorted.
- **L1232–1234**: Fee computation based on the distorted `idealBalance` → fee distortion.
- **L1235–1238**: Update `self.balances[i]` with the distorted fee → state distortion.
- **L1240**: `d2` again calls `determineA` anew — possible mixing.
- Eventually `toMint = (d2 - d0) × totalSupply / d0` (L1251) also mixes the D of three different A's → LP issuance distortion.

##### (2e) Fundamental meaning of the bug

In a dual-A design, the **scale/value of invariant `D` differs by A**. The "balance_i × d1 / d0" ratio in the `idealBalance` formula means proportional scaling **between two states on the same curve** — across different curves it has no physical meaning, like "computing the kg/lb ratio".

The audit's POC: at `target_price=4`, an imbalanced deposit triggers A switching → distorts the formula → LP tokens are **issued 4× in excess**. The attacker:
1. Pushes the pool near the target price.
2. Performs an imbalanced deposit that triggers A switching.
3. Acquires the over-issued LP tokens.
4. After the pool normalizes, withdraws — captures LP value transfer.

**Protocol-level**: dilution of existing LP holders' shares (value drain). The higher the target price (when the attacker deploys a malicious pool), the proportionally greater the damage.

##### (2f) Correct fix

Per audit recommendation: compute `d0`/`d1` with **consistent A**. Example:
```solidity
v.preciseA = determineA(self, _xp(self, newBalances));    // pick A_new
v.d0 = getD(_xp(self), v.preciseA);                        // recompute d0 with A_new (consistent)
v.d1 = getD(_xp(self, newBalances), v.preciseA);
```
Or use A_old for both. The key is **unification with the same A**.

#### 3. IntentChecker annotation attempt (development-time perspective)

**Function-scope variables** (at addLiquidity time):
- `amounts[]`, `fees[]`, `newBalances[]` (local arrays).
- `v.d0`, `v.d1`, `v.d2`, `v.preciseA` (AddLiquidityInfo struct locals).
- `feePerToken`, `idealBalance`, `toMint` (locals, partial scope).
- State via `self`: `balances[]`, `pooledTokens[]`, `lpToken`, `initialA`, `futureA`, `initialA2`, `futureA2`, ... .

**(a) State variable change?** There is a change to `self.balances[]`. However, both buggy and correct increase in the same direction → cannot be distinguished by `changed`/entry-exit (I3 γ flavor: same direction, only magnitude differs — bordering on L4c but deeper).

**(b) Attempt `@Post ... == correct_expr` with existing scope**:

The correct `idealBalance` is:
```
idealBalance_correct = d1_consistent × balances[i] / d0_consistent
```
where `d0_consistent = getD(oldBalances, A_consistent)`.

Here:
- `v.d0` (L1179) is computed with `A_old` → inconsistent.
- `v.d1` (L1222) is computed with `v.preciseA` (`A_new`).
- **d0 recomputed with A_new** (= correct d0) is not in scope.
- **d1 recomputed with A_old** (alternative fix) is also not in scope.

Ultimately, expressing the correct idealBalance requires the result of a `getD(...)` call as a new argument → same structure as Case 5. Additionally, no variable carries the result of this call (absent in scope).

**(c) `.arg[n]` channel attempt**: form `@During getD.arg[1] == some_A` at the L1222 `getD` call? `v.preciseA` is the argument used; even when trying to express what the "correct A" is, that itself is `v.preciseA` (new A). The correct fix requires recomputing `v.d0`, not correcting the argument of `v.d1`. So `.arg[n]` does not solve it.

**(d) Indirect state-variable constraint**:
- A meta-constraint like `@Post v.d0 computed_with_A == v.preciseA` is not in the grammar.
- `@Post self.balances[i] (entry relOp exit)` checks only direction — as seen above, indistinguishable.

All paths fail to express within the grammar. **Type B confirmed**.

#### 4. Classification validity

- Current: **L4a**. ✅ Retain.
- I2 omniscient developer test: the correct idealBalance formula depends on the result of recalling `getD(...)`. Grammar disallows.
- I7 intent-level: even formal proxy annotations fail to distinguish buggy/correct — cannot be circumvented even with `.arg[n]`.
- The existing explanation at `annotation_plans.md` L904–962 is accurate. The "no function calls in annotations + Newton-loop iteration function" explanation captures the core.

#### 5. Root cause

**Essence (Type B — consistent-A D absent in scope)**:

In `addLiquidity` scope, D-related values exist but all are based on **mixed A**:
- `v.d0` — old balances + A_old (buggy)
- `v.d1` — new balances + A_new
- `v.d2` — fee-adjusted balances + yet another A (re-call of determineA)

The **consistent-A-based d0** that correct idealBalance requires (i.e., `getD(oldBalances, A_new)` or its symmetric counterpart) is absent anywhere in scope. State variables (initialA, futureA, …) are only raw A parameters and do not carry D values.

Twin structure with Case 5:
- Case 5 (`getYC`): the split result `y₂` is absent from scope.
- Case 6 (`addLiquidity`): the consistent-A `d0_correct` is absent from scope.
- Both are twin bugs in different functions of the **same dual-A library**, arising from the same cause (failure to maintain A consistency).

G-surface:
- **G3 (primary)** — consistent-A D values are absent from scope/state.
- **G1 (secondary)** — even if a D value proxy existed, `getD(...)` cannot be called from intentValue, blocking the alternative path.
- **Multi-A dependency** — the requirement of "computing D twice with the same A", peculiar to dual-A systems, is a constraint hard to describe in the grammar (meta-level: concepts like "computational homogeneity" do not exist in the grammar).

**Subtle difference from Case 5**:
- Case 5: the result value itself (`y₂`) is the final product of a multi-step chain.
- Case 6: the chain is a single step, but the **argument consistency of the same call** is the issue. "Re-call d0 with A_consistent" — fixed with just one additional call, but the result of that call is not in scope.
- Therefore Case 6 is **relatively mild among algorithm errors**. If the grammar allowed referencing "the result of recalling an existing call with new arguments", it could be resolved — a case that benefits more from grammar extension than Case 5.

**Silent sanction observation**:
- If the developer transcribes the L1231 formula as-is into an annotation: `@Post idealBalance == v.d1 * self.balances[i] / v.d0` — buggy is tautologically satisfied, correct is violated since it uses a different d0. Typical **fail-by-confirmation** (I5 Mode-2). Same pattern as Case 3 reappearing.

**[Category (I8)]**: **Algorithm error / Type B** — `d0` recomputation under consistent-A required. Single-step algorithm error (not multi-step like Case 5). Resolvable if the grammar introduces "argument consistency of calls" constraints or allows re-invocation result references.

---

### Case 7 — `web3bugs_59_H_05` (current classification mismatch: limitation_types.md = **L4a**, annotation_plans.md = L5b → objective verdict: **L4a**)

#### 1. Audit report citation

- **Source**: `reports/59.md` → `[H-05] AuctionEschapeHatch.sol#exitEarly updates state of the auction wrongly`
- **Severity**: High. **Warden**: 0x0x0x (C4 2021-11-malt).
- **Core claim (original excerpt)**:
  > When the user exits an auction with profit, to apply the profit penalty **less maltQuantity is liquidated** compared to how much malt token the liquidated amount corresponds to. The problem is `auction.amendAccountParticipation()` simply subtracts the malt quantity **with penalty** and full `amount` from users auction stats. This causes a major problem:
  >
  > `uint256 maltQuantity = userMaltPurchased.mul(amount).div(userCommitment);`
  >
  > The ratio of `userMaltPurchased / userCommitment` gets higher after each profit taking (since penalty is applied to subtracted maltQuantity from userMaltPurchased), by doing so **a user can earn more than it should**.
- **Judge**: "warden has identified an exploit that allows early withdrawers to gain more rewards than expected... flow in the accounting logic". High severity confirmed.
- **Sponsor**: 0xScotch confirmed.
- **Recommended fix**: not concrete. "Make sure which values are used for what and update values which doesn't create problems like this."

#### 2. Understanding the Code

##### (2a) Contract purpose & position in system

`AuctionEscapeHatch` — an escape hatch in Malt's (algorithmic stablecoin) auction-based stabilization mechanism that enables **early liquidation of auction positions already participated in**. On liquidation, a **profit penalty** is applied to suppress full profit realization (encouraging sticky participation).

##### (2b) Function's role within the contract

`exitEarly(auctionId, amount, minOut)` (L65–92, external):
- User liquidates `amount` of auction commitment early.
- Internal: compute penalty-adjusted maltQuantity → mint → sell as collateral on DEX → transfer to user.
- **Key dependency**: calls the auction contract's `amendAccountParticipation` to **subtract the user's participation state in the auction** (presumably subtracts amount from userCommitment and maltQuantity from userMaltPurchased).
- Repeatedly callable — state must shrink exactly proportionally to avoid cumulative arbitrage.

##### (2c) Function intent (formulas)

Intended invariant:
- Pre-exit: `userMaltPurchased / userCommitment = ratio_initial`.
- Exit `amount`: subtract malt/commitment proportionally → **ratio invariant**.
- Pro-rata pre-penalty `maltQuantity`: `userMaltPurchased × amount / userCommitment`.
- Liquidated (post-penalty): `desiredReturn × pegPrice / currentPrice` — only partial profit realization.
- **State subtraction must use the pre-penalty value**. Liquidation (mint) must use the post-penalty value.

##### (2d) Line-by-line analysis (exitEarly L65–92)

```solidity
66   uint256 maltQuantity = _calculateMaltRequiredForExit(_auctionId, amount);
     // → returns post-penalty value (overwritten internally at L209)
69   malt.mint(address(dexHandler), maltQuantity);     // (A) for mint — post-penalty correct
70   uint256 amountOut = dexHandler.sellMalt();
72   require(amountOut > minOut, "EarlyExit: Insufficient output");
74   AuctionExits storage auctionExits = auctionEarlyExits[_auctionId];
76   auctionExits.exitedEarly = auctionExits.exitedEarly + amount;
77   auctionExits.earlyExitReturn = auctionExits.earlyExitReturn + amountOut;
78   auctionExits.maltUsed = auctionExits.maltUsed + maltQuantity;   // own accounting
...
83   auction.amendAccountParticipation(                // (B) for state subtraction — BUG
84     msg.sender,
85     _auctionId,
86     amount,            // commitment subtraction amount
87     maltQuantity       // BUG: post-penalty value passed. Should be pre-penalty.
88   );
90   collateralToken.safeTransfer(msg.sender, amountOut);
91   emit EarlyExit(msg.sender, amount, amountOut);
```

- **L66**: Calls `_calculateMaltRequiredForExit`. Internally computes pre-penalty (L195), then if profitable overwrites to post-penalty (L209). Final return is post-penalty.
- **L69 (OK)**: liquidation — mints malt at the post-penalty amount. Correct usage.
- **L83–88 (BUG)**: the same `maltQuantity` (post-penalty) is passed for auction state subtraction. As a result, inside amendAccountParticipation, `userMaltPurchased -= post-penalty_maltQuantity` (subtracted less by the penalty amount) + `userCommitment -= amount` (as-is).
- **Result**: the user's remaining `userMaltPurchased/userCommitment` ratio increases. The next exitEarly is computed at a higher malt/commitment ratio → over-payment. Repeatable → attack path.

##### (2e) Fundamental meaning of the bug

The return value of `_calculateMaltRequiredForExit` is used in **dual purposes**, but the two purposes require different values:
- **Mint (liquidation)**: the actual mint amount must be reduced by the penalty → post-penalty.
- **State accounting**: must preserve the user's remaining participation ratio → pre-penalty.

The code does not separate them (collapsed into a single variable). State must be subtracted with pre-penalty for the ratio invariant to hold; using post-penalty causes the ratio to inflate each time.

Protocol-level: Repeated exitEarly calls extract increasingly more malt per commitment → **excess profit realization** before the position is fully exhausted + additional profit on the residual commitment via `claimArbitrage`. System fund drain.

##### (2f) Correct fix

Two possibilities:
1. Have `_calculateMaltRequiredForExit` **return both values**:
   ```solidity
   (uint256 postPenalty, uint256 prePenalty) = _calculateMaltRequiredForExit(...);
   malt.mint(address(dexHandler), postPenalty);
   ...
   auction.amendAccountParticipation(msg.sender, _auctionId, amount, prePenalty);
   ```
2. Compute pre-penalty directly in `exitEarly` (redundant but explicit):
   ```solidity
   // separately query user state to compute pre-penalty
   (,, uint256 userMaltPurchased) = auction.getAuctionParticipationForAccount(msg.sender, _auctionId);
   (uint256 userCommitment,,) = auction.getAuctionParticipationForAccount(msg.sender, _auctionId);
   uint256 prePenalty = userMaltPurchased * amount / userCommitment;
   ```

Both entail **introducing new local variables + changing the existing return-value structure**.

#### 3. IntentChecker annotation attempt (development-time perspective)

**Function-scope variables** (exitEarly):
- Params: `_auctionId`, `amount`, `minOut`.
- Locals: `maltQuantity` (post-penalty), `amountOut`, `auctionExits` pointer.
- State: `auction`, `dexHandler`, `malt`, `maxEarlyExitBps`, `cooloffPeriod`, `auctionEarlyExits` (own tracking).

**(a) State variable change?** There is an update to `auctionExits.*` — but this is AuctionEscapeHatch's own tracking, not the bug's target (auction state). The bug occurs in the external auction's state (cross-contract). The `changed` channel is identical for both buggy and correct.

**(b) Attempt `@During amendAccountParticipation.arg[3] == expected`**:
- Correct expected value = pre-penalty maltQuantity = `userMaltPurchased × amount / userCommitment`.
- `userMaltPurchased`, `userCommitment` are **external state of the auction contract** — not in exitEarly scope.
- To obtain them, the result of `auction.getAuctionParticipationForAccount(...)` is required. This call only happens inside `_calculateMaltRequiredForExit` — not in the exitEarly body.
- Function calls are not allowed in intentValue (G1). Even with @IReturn, since the call site is inside `_calculateMaltRequiredForExit`, binding it to an exitEarly annotation is hard.
- **Expression fails**.

**(c) `@During amendAccountParticipation.arg[3] == maltQuantity` (naive)**:
- Uses the in-scope `maltQuantity` local → tautologically satisfied in buggy. Violated in correct since the value is different.
- **Silent sanction** (I5 Mode-2) — if the developer writes "just pass maltQuantity", the buggy is reconfirmed.

**(d) Auxiliary injection path (I4)**:
- Insert `(uint256 _userCommitment, , uint256 _userMaltPurchased) = auction.getAuctionParticipationForAccount(msg.sender, _auctionId);` at the top of exitEarly.
- Then `@During ... arg[3] == _userMaltPurchased * amount / _userCommitment` becomes writable.
- Bug awareness as a precondition — judging "pre-penalty / post-penalty separation needed" is at the level of the fix itself.

#### 4. Classification validity — **L4a confirmed**

**Resolving the cross-document inconsistency**: `limitation_types.md` (L4a) is correct and `annotation_plans.md` (L5b) is wrong. Reasoning:

- I2 omniscient developer test: with only existing variables in exitEarly scope, **no grammar-expressible distinguishing annotation exists**.
- `userMaltPurchased`/`userCommitment` are external auction-contract state, with no binding inside exitEarly whatsoever.
- The L5b basis in `annotation_plans.md` ("wrong argument passed → bug awareness needed") corresponds only to *knowing the arg is wrong*, while *whether the correct value can be expressed in the grammar* is a separate matter — expression is impossible, hence L4a.

**Document update needed**: Modify `annotation_plans.md` L2398–2402 to an L4a explanation. (To be reflected after confirmation.)

#### 5. Root cause

**Essence (Type B — pre-penalty maltQuantity absent in scope)**:

The exitEarly function has only the return `maltQuantity` (post-penalty) of `_calculateMaltRequiredForExit`, `amount` (param), and its own state. The pre-penalty maltQuantity needed for the bug fix, and its constituent materials `userMaltPurchased`/`userCommitment`, are **state of another contract** with no binding of any form into the exitEarly body. The correct value cannot be expressed by an arithmetic combination of existing scope variables.

Furthermore, the causal structure of the bug is **dual-use collapse of the return value** — `_calculateMaltRequiredForExit` returns a single `maltQuantity`, which is used for both the mint purpose (post-penalty) and the state-subtraction purpose (pre-penalty). These two purposes split on whether the penalty is applied, but **the function returns only the penalty-applied version**. Pre-penalty exists at the intermediate stage (L195) and disappears with the L209 overwrite — a transient value in local scope.

**Similarity to Case 4 (39_H_02)**:
- Both pass **wrong arguments** to external state-modifying calls.
- Both have correct values that depend on external contract state (ERC20 balance / auction participation).
- Both are combinational errors that arise from "using a single variable for dual purposes" (Case 4: sender net-income collapse, Case 7: maltQuantity collapse).
- **Twin pattern** — "dual-use value without decomposition".

G-surface:
- **G3 (primary)** — pre-penalty maltQuantity value absent from exitEarly scope.
- **G1** — to obtain the necessary value, `auction.getAuctionParticipationForAccount(...)` is not in exitEarly + intent grammar disallows function calls.
- **G8** — depends on external contract state.

**Silent sanction (I5)**:
- If the developer transcribes the L83–88 code as-is into an annotation (`@During ... arg[3] == maltQuantity`), buggy passes tautologically.
- Same pattern as Cases 3, 4, 6: a natural local-reference-based annotation reconfirms the buggy.

**Aux injection possibility (I4)**:
- Possible, but the judgment of pre-penalty separation itself is the core of the fix — bug awareness as a precondition.

**[Category (I8)]**: **Algorithm error / Type B** — dual-use collapse of a single value as algorithmic error. The fix requires value separation (decomposition). Twin structure with Case 4. L4a orthodox, axis α (need for external view-call results + reference to variables outside scope).

---

### Case 8 — `web3bugs_61_H_01` (current classification: **L4a** → reclassification proposal: **L5b**)

#### 1. Audit report citation

- **Source**: `reports/61.md` → `[H-01] In CreditLine#_borrowTokensToLiquidate, oracle is used wrong way`
- **Severity**: High. **Warden**: 0x0x0x (C4 2021-12-sublime).
- **Core claim (original excerpt)**:
  > Current implementation:
  > `(uint256 _ratioOfPrices, uint256 _decimals) = IPriceOracle(priceOracle).getLatestPrice(_borrowAsset, _collateralAsset);`
  >
  > But it should not consult `borrowToken / collateralToken`, rather it should consult the **inverse**. As a consequence, in `liquidate` the liquidator/lender can lose/gain funds as a result of this miscalculation.
- **Recommended fix**: `getLatestPrice(_collateralAsset, _borrowAsset)` — swap the two argument positions.
- **Sponsor**: ritik99 confirmed.

#### 2. Understanding the Code

##### (2a) Contract purpose & position in system

`CreditLine` — Sublime's **P2P lending protocol** core contract. The lender provides a credit limit and the borrower deposits collateral to borrow. On liquidation, collateral is converted into borrow token for liquidation processing.

##### (2b) Function's role within the contract

`_borrowTokensToLiquidate(_borrowAsset, _collateralAsset, _totalCollateralTokens) → uint256` (L1045–1056, internal view):
- Caller: `liquidate` (L996, autoLiquidation branch), public `borrowTokensToLiquidate` (view wrapper).
- Role: computes "how many borrow tokens the liquidator needs to liquidate this much collateral". After deducting the reward fraction, converts using the oracle ratio.

##### (2c) Function intent (formulas)

Intended:
```
_borrowTokens = _totalCollateralTokens
              × (1 - liquidatorRewardFraction)
              × (collateral/borrow price ratio)
```
i.e., "n collateral × (collateral unit price / borrow unit price) = borrow-equivalent quantity for n collateral". Oracle's `getLatestPrice(A, B)` convention = `A_price / B_price` (in most cases).

##### (2d) Line-by-line analysis (L1045–1056)

```solidity
1045  function _borrowTokensToLiquidate(
1046      address _borrowAsset,
1047      address _collateralAsset,
1048      uint256 _totalCollateralTokens
1049  ) internal view returns (uint256) {
1050      (uint256 _ratioOfPrices, uint256 _decimals) = IPriceOracle(priceOracle).getLatestPrice(
1051          _borrowAsset, _collateralAsset);          // BUG — arg order swapped
1052      uint256 _borrowTokens = (
1053          _totalCollateralTokens
1054              .mul(uint256(10**30).sub(liquidatorRewardFraction))
1055              .div(10**30)
1056              .mul(_ratioOfPrices)
1057              .div(10**_decimals)
1058      );
1059      return _borrowTokens;
1060  }
```

- **L1050–1051 (BUG)**: `getLatestPrice(_borrowAsset, _collateralAsset)` — receives the borrow/collateral ratio. Correct call requires collateral/borrow.
- **L1052–1058**: `_borrowTokens = collateral_amount × (1 - reward) × _ratioOfPrices / 10^decimals`. The formula structure is OK, but `_ratioOfPrices` is inverted.

**Result**:
- For example, if collateral price is $100 and borrow price is $1 → correct ratio = 100, buggy ratio = 0.01.
- For 10 collateral, the correct borrow-eq = 10 × 100 = 1000.
- Buggy = 10 × 0.01 = 0.1.
- A 10^4 difference. The liquidator can seize collateral nearly for free (acquiring 1000 worth of collateral for just 0.1 borrow tokens).

##### (2e) Root meaning of the bug

Violation of the oracle call convention. **Pattern inconsistency** with other call sites in the same contract:
- L442 (`calculateBorrowableAmount`): `getLatestPrice(_collateralAsset, _borrowAsset)` — uses **correct order**.
- L869 (`calculateCurrentCollateralRatio`): `getLatestPrice(_collateralAsset, _borrowAsset)` — **correct**.
- L931 (`withdrawableCollateral`): `getLatestPrice(_collateralAsset, _borrowAsset)` — **correct**.
- L1050 (`_borrowTokensToLiquidate`): **BUGGY — only this one is swapped**.

That is, **only one of four call sites in the same contract is wrong**. Simple typo / copy-paste error level. A bug caught by **call convention consistency** checking rather than protocol design knowledge.

##### (2f) Correct fix

Single-line modification: swap `_borrowAsset, _collateralAsset` → `_collateralAsset, _borrowAsset`.

#### 3. IntentChecker annotation attempt (developer-time perspective)

**Function scope variables**: `_borrowAsset`, `_collateralAsset` (params), `_ratioOfPrices`, `_decimals`, `_borrowTokens` (locals), contract state (`priceOracle`, `liquidatorRewardFraction`).

**(a) State change?** `_borrowTokensToLiquidate` is internal view — no storage write.

**(b) Attempt at `@Post returnExpression == correct_formula`**:
- Correct formula requires `_ratioOfPrices_correct = getLatestPrice(_collateralAsset, _borrowAsset).ratio`.
- The `_ratioOfPrices` local is the **buggy value** — the correct value is not in scope.
- `@Post return == ... * correct_ratio / ...` cannot express correct_ratio (G1: function calls disallowed, Type B for ratio).
- Through this path alone, it looks like L4a.

**(c) `@During .arg[n]` channel** (decisive observation):

Attempt at annotation of the form `getLatestPrice.arg[0] == _collateralAsset`:

```solidity
// @During IPriceOracle(priceOracle).getLatestPrice.arg[0] == _collateralAsset
(uint256 _ratioOfPrices, uint256 _decimals) = IPriceOracle(priceOracle).getLatestPrice(
    _borrowAsset, _collateralAsset);   // buggy
```

- **Buggy**: arg[0] = `_borrowAsset` ≠ `_collateralAsset` → **VIOLATED**.
- **Correct (after fix)**: arg[0] = `_collateralAsset` → **SATISFIED**.
- `_collateralAsset` is in scope as a function parameter. Grammar fully allows it.

→ **A distinguishing annotation exists in grammar-expressible form**. **Exactly the same pattern** as the L5b example `pool0.swap.arg[0] == 0` (52_H_15) in `limitation_types.md`: catching argument order errors via `.arg[n]`.

**Developer's annotation-writing labor**:
- Observing the pattern of `_collateralAsset` first at three other sites (L442, L869, L931) in the same contract → infer convention.
- Assert the same convention at L1050 via annotation.
- Writing this annotation requires **no deep domain knowledge**, only observing pattern consistency within the contract.
- However, the decision itself "that this should be asserted" presupposes bug awareness — since the convention is not auto-enforced.

#### 4. Classification validity — **L4a retained** (L5b proposal withdrawn)

**Review and withdrawal of the L5b proposal**:

In the initial analysis, the `@During IPriceOracle.getLatestPrice.arg[0] == _collateralAsset` annotation is grammar-expressible and distinguishes buggy/correct, so L5b was proposed. However, applying **principle I9 (L5b judgment is based on the semantic intent channel)** leads to withdrawal:

- The `.arg[n]` channel is a **lint-style pattern check** (checking argument identifier choice at the source code level). It is not in IntentChecker's distinctive contribution area, and is weak as a basis for L5b in the paper.
- Semantic intent channel = verifying the meaning of the `_ratioOfPrices` return value (the `collateral_price / borrow_price` ratio). Here:
  - `@IReturn` supplies **a single arg-indifferent concrete return value** to `IPriceOracle.getLatestPrice`.
  - From the engine's perspective, both buggy `getLatestPrice(_borrow, _collateral)` and correct `getLatestPrice(_collateral, _borrow)` **receive the same `_ratioOfPrices` value**.
  - Downstream `_borrowTokens` computation is identical → no `@Post returnExpression == ...` expression can distinguish buggy/correct.
- → **Inexpressible in the semantic intent channel** → **L4a confirmed**.

**Basis for L4a (`inexpressible-expected-value`)**:
- The correct `_ratioOfPrices` value = `collateral_price / borrow_price` (oracle semantics).
- This value is the numeric meaning of the oracle return and cannot be expressed as an arithmetic combination of in-scope variables.
- The `@IReturn`-supplied value is constructively indistinguishable from the value received by buggy code (arg-indifference).
- Therefore, no proxy used by an intent annotation can express the true correct meaning.

**L4a vs L4b choice**:
- L4b is the structural limitation "no-target-storage — no attach point" (typical of view functions).
- In this case, the return-based `@Post returnExpression == expr` channel itself is open. The problem is that the correct value cannot be written in the `expr` slot — an **inexpressibility** problem.
- → L4a is correct. The view-function nature is secondary.

#### 5. Root cause

**Essence (Type B — `_ratioOfPrices` semantic meaning is inexpressible)**:

The `_borrowTokensToLiquidate` scope contains `_ratioOfPrices` (the oracle-returned local), but this is **a concrete value supplied via @IReturn**. Its **numeric meaning (collateral/borrow vs borrow/collateral)** is not stored anywhere in scope. Asserting the correct meaning would require checking "whether the convention of the value returned by the oracle is correct," but this convention is in **the external oracle API specification**, outside scope.

From the analysis engine's perspective, buggy and correct are **indistinguishable**:
- @IReturn supplies the same value arg-indifferently → engine computation is identical.
- No matter what expression is written in a semantic intent annotation, buggy/correct receive the same verdict.

G-surface:
- **G1** — no way to reference the **semantic return value** of `IPriceOracle.getLatestPrice(...)` in intent.
- **G3** — source values such as `collateral_price`, `borrow_price` are not in scope (`@IReturn` returns only the ratio).
- **G8** — depends on external oracle state.
- **@IReturn arg-indifference** (engine-specific limitation): does not distinguish between calls to the same function with different argument orders. A concrete manifestation of I1's "separation of debug annotation vs intent annotation" principle.

**Similarity to Cases 2 and 7 (Value/Type B axis)**:
- Case 2 (25_H_05): hardcoded `18` instead of the required `10 + uD` — depends on external underlying decimals.
- Case 7 (59_H_05): post-penalty `maltQuantity` instead of the required pre-penalty — depends on external auction state + loss of transient value in scope.
- **Case 8 (this case)**: buggy meaning of `_ratioOfPrices` instead of the required correct meaning — depends on external oracle API convention.

All three cases share the **"value error / Type B"** cell. All depend on external state/convention.

**Caught by `.arg[n]` but lint-level (I9)**:
- The `.arg[n]` channel is an area where syntactic lint tools (Slither, etc.) can also catch via pattern matching.
- Not included in IntentChecker novelty claims.
- A simple arg-order error is acknowledged as an area covered by modern static analysis tools.

**[Category (I8)]**: **Value error / Type B** — the semantic meaning of the correct oracle ratio is not expressible as an arithmetic combination of scope variables/constants. `@IReturn` arg-indifference also blocks the workaround through the debug annotation channel. Same cell as Cases 2 and 7.

#### 6. Suggested paper wording improvements

- **Refrain from mentioning the `.arg[n]` channel**: Framing Case 8 as L5b in the paper would downgrade it to L5b-syntactic — the territory of existing lint tools. The L4a (semantic intent inexpressibility) framing strengthens the paper's contribution.
- **Observation of @IReturn arg-indifference**: A structural limitation of debug annotation — does not distinguish between argument variations of the same function. This is a concrete manifestation of I1 (annotation vs engine separation) and worth mentioning as **a separate limitation axis**.
- **Implicit re-examination of existing L5b classifications**: Under principle I9, it is necessary to examine whether 52_H_15, 113_H_05, 35_H_11 can also be caught in the semantic channel. Systematic re-evaluation when entering the L5b section.
- **`annotation_plans.md` revision needed**: The L4a basis at L1830–1836 is fundamentally correct, but emphasize `@IReturn` arg-indifference as primary. Exclude the `.arg[n]` workaround as lint.

---

### Case 9 — `web3bugs_61_H_02` (classification mismatch: limitation_types.md = **L4a**, annotation_plans.md = L5a → objective verdict: **L4a**)

#### 1. Audit report citation

- **Source**: `reports/61.md` → `[H-02] Wrong returns of SavingsAccountUtil.depositFromSavingsAccount() can cause fund loss`
- **Severity**: High. **Warden**: WatchPug (C4 2021-12-sublime).
- **Core claim (excerpt)**:
  > `savingsAccountTransfer()` does not return the result of `_savingsAccount.transfer()`, but returned `_amount` instead, which means that `SavingsAccountUtil.depositFromSavingsAccount()` may not return the actual shares (when pps is not 1).
- **POC**:
  > Given the price per share of yearn USDC vault is `1.2`:
  > 1. Alice deposited 12,000 USDC to yearn strategy, received 10,000 share tokens.
  > 2. Alice created a pool, added all 12,000 USDC from savings account as collateral. The recorded `CollateralAdded` got the wrong number: **12000** (should be **10000**).
  > 3. `cancelPool()` fails (recorded shares > actual). **Alice loses all 12,000 USDC**. Liquidation also fails → lender fund loss.
- **Recommended fix**:
  ```solidity
  function savingsAccountTransfer(...) internal returns (uint256) {
      if (_from == address(this)) return _savingsAccount.transfer(...);
      else return _savingsAccount.transferFrom(...);
  }
  ```
  i.e., remove `return _amount;` at L79 and directly return the interface call result.

#### 2. Code semantics understanding

##### (2a) Contract purpose & system position

`SavingsAccountUtil` — Sublime's wrapper library between the **savings account (yield-bearing settlement account)** and pools/credit lines. Mediates handling in **shares** units corresponding to token transfers.

Savings account: deposited into a yield strategy such as Yearn, where price-per-share (pps) may not be 1. Even if a user deposits 12,000 USDC, in shares it becomes 10,000 (when pps=1.2). Downstream accounting must be done **in shares** to be accurate.

##### (2b) Function's role within the contract

`savingsAccountTransfer(_savingsAccount, _from, _to, _amount, _token, _strategy) → uint256` (L66–80, internal library):
- Caller: `depositFromSavingsAccount` (L11–26) → deposit/withdraw flows of Pool and CreditLine.
- Role: execute shares transfer between savings accounts + **return the actual shares transferred**.
- The return value is stored as upstream's `_sharesReceived` and used in critical accounting such as `poolVariables.baseLiquidityShares`.

##### (2c) Function intent (formula)

Intended:
- Call `_savingsAccount.transfer(...)` which moves shares and returns actual share count.
- Return that share count to caller.
- Caller records shares for future withdraw/liquidation.

Intent essence: "**maintain accuracy in shares units**". Token amount ≠ shares when pps ≠ 1.

##### (2d) Line-by-line analysis (L66–80)

```solidity
66  function savingsAccountTransfer(
67      ISavingsAccount _savingsAccount,
68      address _from,
69      address _to,
70      uint256 _amount,
71      address _token,
72      address _strategy
73  ) internal returns (uint256) {
74      if (_from == address(this)) {
75          _savingsAccount.transfer(_amount, _token, _strategy, _to);   // BUG — return ignored
76      } else {
77          _savingsAccount.transferFrom(_amount, _token, _strategy, _from, _to);   // BUG — return ignored
78      }
79      return _amount;   // BUG — returns token amount instead of shares
80  }
```

- **L74–75**: when `_from == address(this)`, calls `_savingsAccount.transfer(...)`. This function is **state-modifying** (changes balances) and returns shares. However, **the return value is ignored** here.
- **L76–77**: the other branch calls `transferFrom`. Return value is also ignored.
- **L79 (BUG)**: returns `_amount` as-is. `_amount` is in token units (USDC, etc.). When pps ≠ 1, it mismatches actual shares.

Result: caller records `_sharesReceived = 12,000` (when actual shares are 10,000). Subsequent `cancelPool()`/`liquidate()` attempts to withdraw 12,000 shares → only 10,000 shares actually exist, so it fails → permanent fund lock.

##### (2e) Root meaning of the bug

**Return value scope mismatch**. The interface call (`transfer`/`transferFrom`) is state-modifying and provides a useful return value (shares). However, the buggy code **does not capture** this return (does not store it in a local) and instead returns an unrelated parameter (`_amount`).

Essentially "**failure to wire return value**" — the result of the external call should be conveyed to the caller, but is lost in the intermediate wrapper. One level of indirection misses the opportunity for accounting unit (token amount vs shares) conversion.

Protocol level: accounting that confuses token amount and shares → pool liquidity tracking is broken. As in Alice's POC, full fund lock is possible. Lender fund loss.

##### (2f) Correct fix

Exactly as the audit recommends. `return _savingsAccount.transfer(...)` — **directly wire the interface call's return into the return**. Or:
```solidity
uint256 _sharesReceived = _savingsAccount.transfer(_amount, _token, _strategy, _to);
return _sharesReceived;
```
Either way, **introduce a new local or use the interface call directly in the return expression**.

#### 3. IntentChecker annotation attempt (developer-time perspective)

**Function scope variables**: parameters only (`_savingsAccount`, `_from`, `_to`, `_amount`, `_token`, `_strategy`). **No local variables**. Library function with no state.

**(a) State change?** No state writes in the library body. Storage channel closed.

**(b) Attempt at `@Post returnExpression == correct_shares`**:
- Correct value = the return of `_savingsAccount.transfer(...)`.
- This value is not in scope (not stored in a local — that is precisely the bug).
- Suppliable via `@IReturn`? → **`transfer` is a state-modifying interface call**. `@IReturn` is **view/pure only** → not applicable.
- Function calls disallowed in the grammar. `@Post returnExpression == _savingsAccount.transfer(...)` is inexpressible (G1).
- Result: no path to reference the correct value.

**(c) `@Post returnExpression == _amount` (naive)**:
- Grammar OK. Buggy: `_amount == _amount` tautology. Satisfied.
- Correct: returns shares → `shares == _amount` → if pps ≠ 1, VIOLATED.
- This is **a false positive on correct**. That is, if a developer naturally writes the annotation "return == _amount", it certifies buggy and violates correct. **I5 silent sanction reappears**.

**(d) `.arg[n]` channel**: bug not catchable by checking transfer/transferFrom args — args are identical between buggy/correct.

**(e) Auxiliary local injection (I4)**:
- Insert `uint256 _sharesReceived = _savingsAccount.transfer(...);`.
- Then `@Post returnExpression == _sharesReceived` becomes writable.
- However, **this injection itself is the fix**. Same structure as the audit-recommended fix → presupposes bug awareness.

#### 4. Classification validity — **L4a confirmed** (annotation_plans.md L5a withdrawn)

**Self-contradiction in annotation_plans.md L5a claim**:
- "Correct fix: missing return capture assignment (L5a)"
- "Function calls not allowed in annotation grammar → `returnExpression == _savingsAccount.transfer(...)` is inexpressible"

The two sentences are incompatible. L5a should be "post-condition **expressible**, only bug awareness lacking", but the second sentence above admits inexpressibility. → **L5a conditions not met**.

**Basis for L4a (inexpressible-expected-value) confirmed**:
- Correct shares value absent in scope (local not stored = the bug itself).
- `@IReturn` path blocked (state-modifying interface).
- Function calls disallowed in grammar.
- Conclusion: **even an omniscient developer cannot write a correct annotation with the existing scope** → L4a confirmed.

**L4a vs L4b**:
- Library function (no storage) → L4b candidate.
- However, return-based `@Post` is in principle open. The problem is **correct inexpressibility** (value).
- **L4a primary** (inexpressibility), L4b secondary (structural no-state is a sub-factor).

**limitation_types.md (L4a) confirmed**, annotation_plans.md needs revision.

#### 5. Root cause

**Essence (Type B — semantic return value of state-modifying interface call not stored in scope)**:

`savingsAccountTransfer` scope is parameters only. The **shares return of the interface call (`transfer`/`transferFrom`) has no binding in scope** — the bug is precisely this missing binding. The meaning of this value (shares) is defined in the oracle/external spec and cannot be obtained by any arithmetic combination within scope.

The debug annotation path is also blocked:
- **`@IReturn` is view/pure only**, not applicable to state-modifying `transfer()`.
- This is a **concrete constraint manifestation** of I1 (separation of annotation layer vs engine layer): the range of values the debug annotation can supply to the engine is cut off at state-modifying interfaces.

G-surface:
- **G1** — `transfer(...)` cannot be referenced in intent (no function-call grammar).
- **G3** — shares value not stored as a local, hence absent from scope.
- **G8** — depends on external contract state (pps, shares balance).
- **@IReturn limitation** (auxiliary) — cannot supply debug values to state-modifying interfaces.

**Twin nature with Case 7 (59_H_05)**:
- Case 7: dual-use value collapse — the return of `_calculateMaltRequiredForExit` is used for two purposes, but only one of them is correct.
- Case 9 (this case): ignores the interface call return and returns a parameter instead — **return value substitution error**.
- Both are **bugs related to "return value wiring"**. Case 7 is collapse, Case 9 is drop.
- Both have a structure where a "wrapper/helper function" passes a wrong value downstream.

**Strong silent sanction (I5)**: the natural annotation `returnExpression == _amount` tautologically passes for buggy and is violated for correct. **fail-by-confirmation** — if the developer transcribes the code text as intent, the bug is certified.

**Aux injection (I4)**: injection = fix itself. Like Case 5, "injection is the fix".

**[Category (I8)]**: **Value error / Type B** — return value is wrong (interface call result substituted by parameter). Fix is one line (`return _savingsAccount.transfer(...)`). Correct value absent in scope + `@IReturn` blocked. Same cell as Cases 2, 7, 8.

#### 6. Suggested paper wording improvements

- **`@IReturn`'s view/pure restriction needs a separate G-category**: As a structural constraint of the debug annotation system, the inability to supply returns of state-modifying interface calls is an **independent cause** of L4a occurrence. Likely to recur in Case 9 and future cases.
- **`annotation_plans.md` L2336–2341 revision needed**: correct L5a→L4a. The premise of L5a "post-condition expressible" is false, so L5a does not logically hold.
- **Emphasize silent sanction**: the natural `return == _amount` annotation that certifies buggy — fail-by-confirmation — is worth citing in the paper as a representative example of **"developer writes intent matching code text, not protocol spec"**.
- **Case 7 + Case 9 twins**: return-value-handling errors of wrapper functions (collapse vs drop) — can be grouped as the **"wrapper layer return misrouting" sub-pattern** within L4a. Present sub-pattern statistics after completing all 34 cases.

---

### Case 10 — `web3bugs_61_H_04` (current classification: **L4a**)

#### 1. Audit report citation

- **Source**: `reports/61.md` → `[H-04] Yearn token <> shares conversion decimal issue`
- **Severity**: High. **Warden**: cmichel (C4 2021-12-sublime).
- **Core claim (excerpt)**:
  > The yearn strategy `YearnYield` converts shares to tokens by `pricePerFullShare * shares / 1e18`. But Yearn's `getPricePerFullShare` seems to be in `vault.decimals()` precision, i.e., it should convert as `pricePerFullShare * shares / (10 ** vault.decimals())`. The vault decimals are the same as the underlying token decimals.
- **Impact**: "The token and shares conversions do not work correctly for underlying tokens that do not have 18 decimals. Too much or too little might be paid out leading to a loss for either the protocol or user."
- **Recommended fix**: "Divide by `10**vault.decimals()` instead of `1e18`."
- **Sponsor**: ritik99 confirmed.

#### 2. Code semantics understanding

##### (2a) Contract purpose & system position

`YearnYield` — Sublime's Yearn V2 vault adapter strategy. `SavingsAccount` locks deposited assets into the Yearn vault. Provides `lockTokens` / `unlockTokens` / `getTokensForShares` / `getSharesForTokens` API.

The Yearn vault's `getPricePerFullShare()` = "how many units of underlying token does 1 share correspond to" returned in **the vault's decimals precision**. Yearn spec: `vault.decimals == underlying_token.decimals` (USDC vault → 6, DAI vault → 18).

##### (2b) Function's role within the contract

`getTokensForShares(shares, asset) → amount` (L178–181, public view):
- Caller: used in many places such as SavingsAccount, CreditLine for shares ↔ token amount conversion.
- Role: compute "how many units of underlying token are equivalent to this many shares".
- An incorrect conversion impairs the accuracy of asset movements such as withdraw/liquidation.

##### (2c) Function intent (formula)

```
amount = pricePerFullShare × shares / 10^(vault.decimals)
```
Here `pricePerFullShare` is the pps expressed in the vault's decimals scale.

USDC vault (decimals=6) example:
- pps = `1.05 * 1e6` = `1050000` (1 share = 1.05 USDC).
- shares = `1000`.
- correct amount = `1050000 * 1000 / 1e6 = 1050`. (1000 shares = 1050 USDC units = 0.00105 USDC in human, but uint representation is 1050 * 1e6-scaled... wait I need to recheck scales).

Actually Yearn's convention: shares are in vault's own decimals (same as underlying). So:
- 1000 shares (uint) = 1000 * 10^(-6) = 0.001 vault share tokens in human.
- pps = 1.05 (in decimals, represented as `1050000` = 1.05 * 1e6).
- correct amount = `1050000 * 1000 / 1e6 = 1050` → 0.00105 USDC (uint 1050).

Buggy divides by 1e18: `1050000 * 1000 / 1e18 ≈ 0` (underflow). Returns nearly 0 → critical system error.

For 18-dec tokens (DAI), it happens to be correct (buggy and correct yield identical results). Severe error for 6-dec/8-dec tokens.

##### (2d) Line-by-line analysis (L178–181)

```solidity
178  function getTokensForShares(uint256 shares, address asset) public view override returns (uint256 amount) {
179      if (shares == 0) return 0;
180      amount = IyVault(liquidityToken[asset]).getPricePerFullShare().mul(shares).div(1e18);   // BUG
181  }
```

- **L179**: fast return.
- **L180 (BUG)**: 
  - `IyVault(liquidityToken[asset])`: obtain vault address.
  - `.getPricePerFullShare()`: vault's pps, in **vault.decimals precision**.
  - `.mul(shares).div(1e18)`: divides by 1e18 (incorrect).
  - Correct should be `.div(10 ** vaultDecimals)` — dividing by vault decimals removes pps's scaling → rate is restored to a "1.0-based real number".

**Systematic scaling error**: a `10^(18-vaultDecimals)`-fold error for all non-18-dec underlying assets. USDC (6-dec) = 10^12-fold distortion. WBTC (8-dec) = 10^10-fold.

##### (2e) Root meaning of the bug

Cross-protocol convention assumption error. Yearn V1 used 18-dec precision, but V2 changed to **vault.decimals precision**. The developer wrote code assuming the V1 convention (`1e18` denominator). For non-18-dec tokens, shares↔token conversions are systematically distorted across the protocol.

Protocol level: 
- During withdraw, actual repayment amount is near 0 or infinite → permanent loss of user/lender funds.
- During liquidation, collateral valuation is distorted → unfair liquidation or inability to defend.

##### (2f) Correct fix

Audit recommendation:
```solidity
amount = IyVault(liquidityToken[asset]).getPricePerFullShare()
    .mul(shares)
    .div(10 ** IyVault(liquidityToken[asset]).decimals());   // vault.decimals()
```
Or equivalently, use the underlying token's decimals.

#### 3. IntentChecker annotation attempt (developer-time perspective)

**Function scope variables**: `shares`, `asset` (params). `amount` (return). State: `liquidityToken` mapping.

**(a) Attempt at `@Post amount == pps_value * shares / (10 ** vaultDecimals)`**:

Components of the correct annotation:
- `pps_value`: return of `IyVault(liquidityToken[asset]).getPricePerFullShare()`. No local in scope.
- `vaultDecimals`: return of `IyVault(liquidityToken[asset]).decimals()`. **The buggy code itself does not contain this call**.
- `10 ** vaultDecimals`: the `**` operator is **absent from annotation grammar** (G2 annotation-only — engine supports it).

Three blockers overlap:
- Access to `pps_value`: the getPricePerFullShare return can be supplied via `@IReturn` (view). However, since function calls are disallowed in intent expressions, `@Post amount == <IyVault(..).getPricePerFullShare()> * shares / ...` itself is inexpressible. `@IReturn` is a debug supply, not a means of intent expression (I1).
- Access to `vaultDecimals`: the corresponding call is absent in the buggy code → no call site to attach `@IReturn`. Cannot write the call directly in intent either.
- `10 ** x`: `**` absent from grammar.

**(b) Attempt at natural annotation `@Post amount == pps * shares / 1e18`**:

Grammar allows it, but it is the buggy code formula as-is → **tautologically satisfied** in buggy, violated in correct (non-18-dec tokens). **Quintessential I5 silent sanction**. If the developer naturally writes `1e18`, the bug is certified.

**(c) Aux injection (I4) — when `**` is in grammar**:
- Developer injects two locals:
  ```solidity
  uint256 pps = IyVault(liquidityToken[asset]).getPricePerFullShare();
  uint8 vaultDecimals = IyVault(liquidityToken[asset]).decimals();
  amount = pps.mul(shares).div(10 ** vaultDecimals);   // fix
  ```
- Annotation: `@Post amount == pps * shares / (10 ** vaultDecimals)` — grammar OK (assuming `**` support).
- **Detectable**. However, the injection decision = the fix itself = presupposes bug awareness → **transit into L5 territory (I4)**.

**That is, under current grammar (with `**`), the L4a → L5 transit path is viable**. In a pure annotation-only workflow, it remains L4a (function calls disallowed in intent + return value not stored in local).

**(d) Concrete value access**:
- Pinned to a specific vault instance: USDC vault → vaultDecimals = 6 → divisor = `1000000` literal.
- Annotation: `@Post amount == pps * shares / 1000000` — valid only in USDC scenario.
- Cannot generalize across all vaults → I6 general vs specific boundary.

#### 4. Classification validity — **L4a confirmed** (twin of Case 1)

- I2 omniscient developer test: cannot express the general-form correct annotation (G1+G2+G3 triple block).
- The analysis at `annotation_plans.md` L2026–2032 is accurate. As stated, "same pattern as 25_H_01".

#### 5. Root cause

**Essence (Value / Type B — structural twin of Case 1)**:

The correct division denominator `10 ** vault.decimals()`:
- **Absent from scope**: no variable holds the `vaultDecimals` value (the `.decimals()` call itself is absent in the buggy code).
- **No call site**: no place to attach `@IReturn` either → the strictest form of G3 (similar to Case 25_H_05).
- **Grammar block**: even if the vaultDecimals value is injected, `10 ** x` is inexpressible (G2 annotation-only).

**Subtle difference from Case 1 (25_H_01)**:
- Case 1: `source.decimals` struct field exists as snapshot proxy (Type A_candidate).
- Case 10: no such proxy at all for vault.decimals (**pure Type B form**).
- Case 10 is **a clean version of Case 1 that completely removes the Type A possibility**.

**Similarity to Case 2 (25_H_05)**:
- Case 2: `uD` (underlying decimals) absent, requires `CTokenInterface(source).underlying()` + `IERC20(...).decimals()` chain.
- Case 10: `vaultDecimals` absent, requires single call `IyVault(liquidityToken[asset]).decimals()`.
- Both must place **external view call results into `10 + x` or `10 ** x` operations**.
- Difference: Case 2 only needs `+` (grammar OK), Case 10 needs `**` (grammar block).

G-surface (assuming `**` in grammar):
- **G1** — cannot reference `IyVault(...).decimals()`, `getPricePerFullShare()` in intent.
- **G3** — `vaultDecimals` value absent in scope + `.decimals()` call site absent. `getPricePerFullShare()` return also not stored in local.

**Strong silent sanction (I5)**: the natural annotation `amount == pps * shares / 1e18` is the buggy archetype. Fail-by-confirmation in a workflow where the developer transcribes code text as intent.

**Aux injection-routed L5 transit viable (I4)**: assuming `**` grammar support, after injecting `pps`, `vaultDecimals`, annotation becomes possible. Pure annotation-only stays at L4a.

**I6 general vs specific**: when pinned to a specific vault instance such as USDC, the constant `1000000` annotation is grammar-expressible but does not generalize across all vaults → L5b-flavored. General annotation is L4a.

**[Category (I8)]**: **Value error / Type B** — scaling divisor is in the same cell as Cases 2, 61_H_01, 61_H_02. In particular, **decimals-based scaling** sub-family with Cases 2, 25_H_01.

#### 6. Suggested paper wording improvements

- **"Decimals-based scaling L4a family"**: Cases 1 (25_H_01), 2 (25_H_05), 10 (61_H_04) share — **scaling errors of the form `10^x` recur in L4a**. Can be presented as a sub-pattern in the paper. Resolving it requires either allowing `**` or `pow(10, x)` in the grammar, or introducing separate syntax to express convention-based scaling as an annotation.
- **Explicitly note inability to use `@IReturn`**: many L4a cases cannot be circumvented because of the design boundary of `@IReturn` (view/pure only + arg-indifferent + unused in intent). This is worth mentioning in the Discussion as **a design trade-off of the debug annotation system**.
- **Cases 1, 2, 10 "scaling trio"**: present as the L4a representative example of the paper, grouping these three — concretizing the static analysis limits of decimals handling.

---

### L4a Subsection Summary (10 cases reviewed)

**All 10 L4a cases reviewed** out of 34 cases. See `l4_l5_classification.csv` and `l4_l5_classification.py stats()` for statistics. Cross-cutting observations are accumulated in I1–I9 insights above and `paper_corrections.md` C1–C6. Next step: enter the **L4b section (8 cases)**.

---

## L4b — No Target Storage (8 cases)

L4b definition: the buggy function does not modify any storage variable of the target contract, hence no attach point for state-based intent annotations. Main types: view/pure functions, wrappers without state-modification, library helpers.

---

### Case 11 — `web3bugs_17_H_02` (classification mismatch: limitation_types.md = **L4b**, annotation_plans.md = L5a → objective verdict: **L4b**)

#### 1. Audit report citation

- **Source**: `reports/17.md` → `[H-02] Buoy3Pool.safetyCheck is not precise and has some assumptions`
- **Severity**: High (judge upgrade). **Wardens**: cmichel, shw (C4 2021-06-gro).
- **Core claim (excerpt)**:
  > 1. Only checks if the `a/b` and `a/c` ratios are within `BASIS_POINTS`. By transitivity, `b/c` is only within `2 * BASIS_POINTS` if `a/b` and `a/c` are in range. For a more precise check whether both USDC and USDT are within range, `b/c` must be checked as well.
  > 2. If `a/b` is within range, this does not imply that `b/a` is within range.
  > 3. The NatSpec for the function states that it checks Curve and an external oracle, but no external oracle calls are checked.
- **Reason for judge upgrade**: "A possibility of stopping deposits or withdrawals deserves high risk."
- **Sponsor**: kristian-gro confirmed, b/c check added in release version.
- **Recommended fix**: add `b/c` ratio check.

#### 2. Code semantics understanding

##### (2a) Contract purpose & system position

`Buoy3Pool` — Gro protocol's **price sanity checker**. Provides pricing-related computations on top of Curve 3Pool (DAI, USDC, USDT). Core role: detect whether the price has depegged in the Curve pool due to flash loan attacks etc. → block deposit/withdraw upon detection.

`safetyCheck` is the **first gate of every interaction function** — if not passed, the transaction reverts.

##### (2b) Function's role within the contract

`safetyCheck() external view returns (bool)` (L87–96):
- Caller: Gro's vault/controller calls before deposit/withdraw/rebalance.
- Role: check whether the Curve pool's internal (a, b, c) price ratios **deviate from the recently cached lastRatio within BASIS_POINTS (20bp)**. Returns true if passed, false if exceeded.
- Wrongful pass → allows deposit/withdraw under stablecoin depeg conditions → user funds may be stolen.

##### (2c) Function intent (per NatSpec)

NatSpec excerpt:
> "establishes a set of ratios (a/a, a/b, a/c), (b/b, b/a, b/c), (c/c, c/a, c/b). The following set should provide the necessary coverage checks: (a/b, a/c)"

NatSpec argues "(a/b, a/c) check alone is sufficient", but this is the root cause of this bug — **the transitivity logic is wrong**. Even if `|a/b - last_a/b| ≤ ε` ∧ `|a/c - last_a/c| ≤ ε`, only `|b/c - last_b/c| ≤ 2ε` is guaranteed. Therefore, b/c variation within `ε` (BASIS_POINTS) is not detected.

Also, NatSpec mentions "Curve + external oracle comparison" but **this function has no oracle call** (only `_updateRatios` does).

##### (2d) Line-by-line analysis (L87–96)

```solidity
87  function safetyCheck() external view override returns (bool) {
88      for (uint256 i = 1; i < N_COINS; i++) {       // iterates only i = 1, 2 (N_COINS=3)
89          uint256 _ratio = curvePool.get_dy(int128(0), int128(i), getDecimal(0));
90          _ratio = abs(int256(_ratio - lastRatio[i]));
91          if (_ratio.mul(PERCENTAGE_DECIMAL_FACTOR).div(CURVE_RATIO_DECIMALS_FACTOR) > BASIS_POINTS) {
92              return false;
93          }
94      }
95      return true;
96  }
```

- **L88**: `i = 1..2` — checks only the ratio from token 0 (DAI) to token 1 (USDC) and token 2 (USDT). **Token 1 ↔ token 2 (b/c) is not in the loop**.
- **L89**: Curve `get_dy(from=0, to=i, amount_in=1 unit of 0)` → how much USDC/USDT comes out from swapping 1 unit of DAI. That is, a/b, a/c.
- **L90**: absolute difference from `lastRatio[i]`. `lastRatio` is the oracle-sanitized Curve value from `_updateRatios`.
- **L91**: returns **false** if difference exceeds BASIS_POINTS (20bp).
- **L95**: returns true if both pass.

**Missing**:
- Core omission: check **`(from=1, to=2)` i.e., b/c** in the i combination.
- No external oracle comparison (mentioned in NatSpec).

##### (2e) Root meaning of the bug

**Erroneous transitivity inference**. The developer assumed "a/b OK && a/c OK → b/c also OK", but mathematically only the 2-BP range is guaranteed:
- `|a/b - last_a/b| ≤ 20bp`
- `|a/c - last_a/c| ≤ 20bp`
- ⇒ `|b/c - last_b/c| ≤ 40bp` (worst case). That is, in reality b/c can depeg up to twice BASIS_POINTS.

Attack scenario:
- Use flash loan to distort only the USDC/USDT ratio of the Curve 3Pool by 30bp (a/b, a/c each move by 15bp → both pass under 20bp).
- safetyCheck returns true → attacker executes deposit/withdraw.
- Curve calculates LP token at distorted prices → attacker profits, remaining LPs lose.

##### (2f) Correct fix

```solidity
function safetyCheck() external view override returns (bool) {
    // a/b, a/c (existing)
    for (uint256 i = 1; i < N_COINS; i++) {
        uint256 _ratio = curvePool.get_dy(int128(0), int128(i), getDecimal(0));
        _ratio = abs(int256(_ratio - lastRatio[i]));
        if (_ratio.mul(PERCENTAGE_DECIMAL_FACTOR).div(CURVE_RATIO_DECIMALS_FACTOR) > BASIS_POINTS) {
            return false;
        }
    }
    // add b/c
    uint256 bc_ratio = curvePool.get_dy(int128(1), int128(2), getDecimal(1));
    uint256 bc_diff = abs(int256(bc_ratio - lastRatio_bc));   // lastRatio_bc also needs caching
    if (bc_diff.mul(PERCENTAGE_DECIMAL_FACTOR).div(CURVE_RATIO_DECIMALS_FACTOR) > BASIS_POINTS) {
        return false;
    }
    return true;
}
```

#### 3. IntentChecker annotation attempt (developer-time perspective)

**Function scope variables**: no parameters. State: `lastRatio[1]`, `lastRatio[2]`, `BASIS_POINTS`.

**(a) State change?** `view` function → no state writes → post-state channel closed.

**(b) Return-based @Post**:
- `@Post returnExpression == false` when "b/c out of range"?
- Expressing "b/c out of range" requires the result of `curvePool.get_dy(1, 2, ...)` + `lastRatio_bc` (not in state).
- Both values absent in scope/state. G3.
- Cannot write `curvePool.get_dy()` itself in intent (G1, function calls disallowed).

**(c) Natural annotation (silent sanction)**:
- If the developer transcribes the code logic as-is: `@Post returnExpression == !(any i=1,2 has _ratio[i] > BASIS_POINTS)`.
- Tautology in buggy, different condition in correct (with b/c) → developer's natural intent is buggy as-is. **Quintessential I5 silent sanction**.
- Additionally: **NatSpec provides the wrong transitivity explanation** → further misleads the annotation author (double natspec-driven silent sanction).

**(d) Aux injection (I4)**:
- Can insert `uint256 bc_ratio = curvePool.get_dy(int128(1), int128(2), getDecimal(1));`.
- However, the cache for `lastRatio[b/c]` is **not in state**. The `mapping(uint256 => uint256) lastRatio` only stores indices 1, 2 — the state itself for b/c comparison is absent in the data model.
- This absence requires contract state extension (add `uint256 lastRatioBc` state var). Production code requires large modifications + initialization logic + simultaneous `_updateRatios` revision.
- **Injection requires data-model extension as well** → L5 transit also difficult (**Y_hard**).

#### 4. Classification validity — **L4b confirmed**

**Review of existing classification**:
- `limitation_types.md` (L4b): view function so state attach impossible.
- `annotation_plans.md` (L5a): missing-code.

**Objective verdict**:
- L4b criterion: view function with no state modifier → no attach point for state-based @Post. Holds.
- L5a criterion: post-condition must be expressible, but return-based expression is also impossible due to scope absence. **L5a conditions not met**.
- → **L4b confirmed**, L5a in annotation_plans.md is wrong.

**Resolving L4a vs L4b overlap**:
- A case where both L4b (no-target-storage) and L4a (inexpressible-expected-value) apply.
- This case has **function type view → state channel absent** (L4b) + **return-based expression also impossible due to scope absence** (L4a).
- Existing taxonomy convention: prefer L4b for view functions (`limitation_types.md` L161, explicit). Retained.

#### 5. Root cause

**Essence (L4b — view function + return inexpressibility)**:

`safetyCheck` is a view that does not modify state. Two main channels of intent annotation:
- State-based `@Post changed(...)`: no target since view.
- Return-based `@Post returnExpression == ...`: correct expression requires out-of-scope values (b/c ratio from Curve + lastRatio_bc from state-that-doesn't-exist).

Both channels blocked. **"There is no place to attach the annotation, or even if attached, the value cannot be written"** — the spiritual meaning of the L4b definition.

**I8 axis re-classification (new axis)**:
- **Bug category**: **Algorithm error** — missing check (b/c ratio verification algorithm omission). Not a single-value error but **omission of verification logic structure**.
- **Proxy type**: **Type B** — both b/c ratio and its cached value absent in scope/state.
- **Annotation channel**: state channel closed (view) + return channel blocked (scope absent).

G-surface:
- **G1** — `curvePool.get_dy(1, 2, ...)` cannot be referenced in intent.
- **G3** — state itself for `lastRatio_bc` absent in data model (omitted in cache slot design).
- **G4** — view function so state write channel closed.

**Double silent sanction**: (a) developer's natural annotation transcribes buggy logic as-is → fail-by-confirmation, (b) **NatSpec provides the wrong explanation "(a/b, a/c) check alone is sufficient"** misleading the annotation author. **Natspec-driven silent sanction** is a strong example of I5.

**Aux injection (I4) difficulty (Y_hard)**: injection of b/c value is possible, but lastRatio_bc state addition + initialization + _updateRatios revision are simultaneously needed. Beyond simple local injection, **data model extension** is required → L5 transit is also a major operation.

**Comparison with Cases 10 and 5**:
- Case 10: injection possible if just `**` grammar is added.
- Case 5: requires multi-step algorithmic injection but no data model change.
- Case 11 (this case): **requires data model extension itself** — the deepest level of fix.

**[Category (I8)]**: **Algorithm error / Type B** — missing verification logic + related state data model absence. View function so state-based workaround also impossible. Algorithm/B cell with Cases 3 and 5.

#### 6. Suggested paper wording improvements

- **L4b body (line 1315)**: currently centered on "view function → no @Post attach target". Case 11 is **a pattern where view + return expression are both blocked**. Explicitly include "view functions where return-based expression is also inexpressible" in the L4b definition.
- **Silent sanction + NatSpec**: the natspec-driven silent sanction pattern raised in Case 4 reappears in Case 11. If the NatSpec contains a wrong explanation, it misleads the annotation author. Emphasize in Discussion as **"NatSpec audit is a necessary prerequisite for the annotation workflow"**.
- **Cases requiring data model extension**: the I4 difficulty of Case 11 ("Y_hard") shows the limit of aux injection — beyond simple variable injection, requires storage slot addition. Cite in paper future work when discussing "the scope of annotation-driven contract refactoring".

---

### Case 12 — `web3bugs_52_H_15` (current classification: **L4b**, but limitation_types.md is internally self-inconsistent)

#### 1. Audit report citation

- **Source**: `reports/52.md` → `[H-15] VaderRouter._swap performs wrong swap`
- **Severity**: High. **Warden**: cmichel (C4 2021-11-vader).
- **Core claim (excerpt)**:
  > The 3-path hop in `VaderRouter._swap` is supposed to first swap **foreign** assets to native assets, and then the received native assets to different foreign assets again. `pool.swap(nativeAmountIn, foreignAmountIn)` accepts the foreign amount as the **second** argument. The code however mixes these positional arguments up:
  > ```solidity
  > return pool1.swap(0, pool0.swap(amountIn, 0, address(pool1)), to);   // BUG
  > // should be:
  > return pool1.swap(pool0.swap(0, amountIn, address(pool1)), 0, to);
  > ```
- **Impact**: "All 3-path swaps through the VaderRouter fail in the pool check when `require(nativeAmountIn = amountIn <= nativeBalance - nativeReserve = 0)` is checked."
- **Recommended fix**: `pool1.swap(pool0.swap(0, amountIn, address(pool1)), 0, to);` swap argument order.
- **Sponsor**: SamSteinGG confirmed.

#### 2. Code semantics understanding

##### (2a) Contract purpose & system position

`VaderRouter` — Vader Protocol's DEX router. A router designed to be Uniswap V2 API-compatible, a wrapper for swap/liquidity management of Vader pools (native ↔ foreign asset exchange). Holds only `factory`, `reserve` addresses as state, no own accounting state (pure router).

##### (2b) Function's role within the contract

`_swap(amountIn, path, to) → amountOut` (L302-351, private):
- Caller: `swapExactTokensForTokens`, `swapTokensForExactTokens` (public entry).
- Role: depending on path length 2 (single-hop) or 3 (multi-hop), call pool.swap.
- For 3-path, **foreign A → native → foreign B** — foreign→native at pool0, then native→foreign at pool1 with the received native.
- VaderRouter itself has no state writes — all asset movement is delegated to pool and ERC20 external calls.

##### (2c) Function intent (formula)

3-path swap logic:
- pool0: `foreign A` in → `native` out. `pool0.swap(nativeAmountIn=0, foreignAmountIn=amountIn, to=pool1)` → returns nativeAmountOut.
- pool1: `native` in → `foreign B` out. `pool1.swap(nativeAmountIn=nativeAmountOut, foreignAmountIn=0, to=recipient)` → returns foreignAmountOut.
- Key convention: `pool.swap(nativeAmountIn, foreignAmountIn, to)` — **first arg native, second arg foreign**.

##### (2d) Line-by-line analysis (L302-351, 3-path branch)

```solidity
309      if (path.length == 3) {
310-315      require(
                 path[0] != path[1] &&
                     path[1] == factory.nativeAsset() &&
                     path[2] != path[1],
                 "VaderRouter::_swap: Incorrect Path"
             );
317          IVaderPool pool0 = factory.getPool(path[0], path[1]);   // foreign A ↔ native
318          IVaderPool pool1 = factory.getPool(path[1], path[2]);   // native ↔ foreign B
320-324      IERC20(path[0]).safeTransferFrom(msg.sender, address(pool0), amountIn);
326          return pool1.swap(0, pool0.swap(amountIn, 0, address(pool1)), to);   // BUG
```

- **L317-318**: Acquire two pools. pool0 = (foreign A, native), pool1 = (native, foreign B).
- **L320-324**: Transfer foreign A amountIn from sender → pool0 (pre-deposit for the swap).
- **L326 (BUG)**:
  - **Inner `pool0.swap(amountIn, 0, address(pool1))`**: arg[0] = amountIn (native slot), arg[1] = 0 (foreign slot). I.e., it attempts a **native→foreign swap** — the wrong direction.
  - pool0 only received foreign A as deposit, so the native reserve did not increase. The check `require(nativeAmountIn = amountIn <= nativeBalance - nativeReserve = 0)` reverts.
  - **Correct**: `pool0.swap(0, amountIn, address(pool1))` — swap foreign A for native.
  - Outer `pool1.swap(0, ..., to)`: arg[0] = 0, arg[1] = the nested call result (assuming it had not reverted, this would be a native value placed in the foreign slot). The direction is also wrong.
  - **Correct**: `pool1.swap(pool0_native_out, 0, to)` — swap the native received from pool0 into foreign B at pool1.

**Execution outcome**: Every 3-path swap **reverts at pool0**. The feature is completely unusable.

##### (2e) Underlying meaning of the bug

**Confusion between the Uniswap V2 API convention and the Vader pool API convention**. Uniswap V2's `swap(amount0Out, amount1Out, to, data)` takes **output** amounts as arguments. Vader's `pool.swap(nativeAmountIn, foreignAmountIn, to)` takes **input** amounts, with separate slots per asset.

Most likely the developer thought in Uniswap V2 style and mistakenly "set the input direction to 0" (in reality `pool.swap` takes input but they treated it as if it were output).

Protocol-level: the 3-path swap feature is fully broken → the cross-pool swap path of the DEX is blocked. Direct loss of funds is prevented by the revert, but **functionality is paralyzed and UX is broken**. (The actual severity is treated as "functional loss" → High.)

##### (2f) Correct fix

The audit recommendation is exactly the one-line swap at L326:
```solidity
return pool1.swap(pool0.swap(0, amountIn, address(pool1)), 0, to);
```

#### 3. IntentChecker annotation attempt (development-time perspective)

**Function-scope variables**: `amountIn`, `path` (params), `pool0`, `pool1` (local). `to` (param). State: `factory` (immutable), `reserve`.

**(a) State change?** VaderRouter._swap performs no state writes (everything is an external call). The direct state channel of `_swap` is **blocked**.

**(b) Return-based @Post**:
- `@Post returnExpression == correct_amountOut_formula`: amountOut is the result of the pool's swap formula (constant-product based). It depends on the external pool's state (reserves). Inexpressible.

**(c) `.arg[n]` channel (lint-level, excluded by principle I9)**:
- `@During pool0.swap.arg[0] == 0` — asserts that arg[0] (the nativeAmountIn) must be 0. Buggy: `amountIn ≠ 0` → VIOLATED. Correct: `0 == 0` → SATISFIED.
- `.arg[1] == amountIn` can additionally be added.
- This is the annotation that the existing `limitation_types.md` cited as an L5b example.
- **Principle I9**: this is lint-style. Not used as a basis for L5b classification.

**(d) Semantic intent via require feasibility**:
- Use the grammar's `require feasible` / `assert feasible` clauses.
- `@During` on the internal `require` of `pool0.swap` — but pool0 is an external contract. Internal requires are not accessible.
- Only the requires inside VaderRouter._swap (L310-315) can be annotated, but those check the path shape, not the swap direction.

**(e) Revert detection**:
- Buggy always reverts → that itself is a bug sign. Correct returns.
- `@Post returnExpression` is itself an unreachable state (in the buggy version). The engine could express this as "this path is infeasible".
- However, this is a side effect of the analysis engine, not the IntentChecker intent annotation feature. **From the perspective of intent annotation, there is no explicit means of expression**.

**(f) Aux injection (I4)**:
- Adding new state or injecting external values has no real meaning in this case — the bug is in argument order, not in the values themselves.
- N/A.

#### 4. Classification rationale — **L4b confirmed** (distinguished from Case 8 and Case 4)

**Review of the existing classification (self-inconsistency in limitation_types.md)**:
- L4b list (L33): includes 52_H_15.
- L5b examples section (L229-237): presents 52_H_15 as a representative L5b example.
- → Internal contradiction in the document.

**Objective verdict**:
- VaderRouter._swap is a **router/wrapper function with no state writes**.
- Semantic intent (correct amountOut) is inexpressible (depends on external pool state).
- The `.arg[n]` channel is excluded from L5b classification by I9.
- → **L4b** (no-target-storage: router/wrapper category).

**Comparison with Case 8 and Case 4**:
| | Case 4 (39_H_02) | Case 8 (61_H_01) | Case 12 (this case) |
|---|---|---|---|
| Function type | non-view (has state writes) | internal view | private wrapper (no state writes) |
| Bug form | arg[2] value error (cross-line fee flow) | arg order swap (oracle) | arg order swap (pool) |
| Can `.arg[n]` actually express it? | Yes (proxy) | Yes (intent itself) | Yes (arg order) |
| Acceptable as L5b under I9? | No (proxy) | No (lint) | No (lint) |
| Semantic channel feasible? | No (external ERC20 balance) | No (@IReturn arg-indifference) | No (external pool state) |
| Classification | L4a (cross-line intent) | L4a (inexpressible) | **L4b (wrapper, no state)** |

All three cases share the common pattern of "an arg-related bug whose semantic intent is inexpressible". The criterion that splits classification between L4a and L4b is the **function type** (presence/absence of state writes).

#### 5. Root cause

**Essence (L4b — router/wrapper function + arg direction error)**:

VaderRouter._swap is a pure router — it has no state of its own. The correct intent concerns the **direction of state change of external pools**: pool0's foreign reserve increases and native reserve decreases; pool1's native reserve increases and foreign reserve decreases. This directionality lives in the state of external pool contracts → outside VaderRouter's scope.

The two channels of intent annotation:
- State-based @Post: VaderRouter has no state of its own. Channel blocked.
- Return-based @Post: computing the correct value of amountOut requires the external pools' reserves plus the swap formula. Inexpressible.
- Arg-based @During: argument-order constraints can be expressed via `.arg[n]`. However, by principle I9 this is lint-level and excluded from L5b classification.

**I8 axis re-classification (new axis)**:
- **Bug category**: **Value error** — wrong choice of argument identifier (order swap). One-line fix.
- **Proxy type**: **Type B** — the correct amountOut or pool state changes are out of scope.
- **Annotation channel**: state channel blocked (router nature) + return channel blocked (depends on external state) + arg channel (lint).

G-surfaces:
- **G1** — return values of `pool0.swap(...)`, `pool1.swap(...)` cannot be referenced inside the intent.
- **G3** — the correct amountOut and pool reserves are out of VaderRouter's scope.
- **G4** — being a router/wrapper, the state-write channel is closed.
- **G8** — depends on external pool state.

**Silent sanction (I5)**: Translating the code straight into an annotation (`arg[0] == amountIn, arg[1] == 0`) yields a buggy tautology → fail-by-confirmation. Both the `.arg[n]` form and a generic natural intent run into silent-sanction risk.

**Aux injection (I4) N/A**: Since the issue is argument order and not value, it is not the kind of problem that injection resolves.

**[Category (I8)]**: **Value error / Type B** — argument-order error in a router/wrapper function. Same cell as Case 8 (value/B), but **L4b due to the function-type difference**. Cross-cutting pattern: "arg-level value error whose semantic intent depends on external state".

#### 6. Suggested improvements to the paper text

- **Correct the L4b list**: resolve the self-inconsistency in `limitation_types.md` where 52_H_15 appears in both the L4b list and the L5b examples — **standardize on L4b** and remove 52_H_15 from the L5b examples section (or annotate it as "originally listed as L5b, reclassified to L4b under the I9 principle").
- **Make the L4a vs L4b criterion explicit**: include the comparison table for Cases 4, 8, and 12 in the paper. "Common: semantic intent inexpressible; what splits them is the function type (presence/absence of state writes)".
- **The router/wrapper L4b archetype**: in functions with no state of their own, every semantic intent depends on external state → L4b is the default. Several Vader-related cases (52_H_15, 52_H_16, 70_H_08) fall in this cell.

---

## L4c — Magnitude-only Difference (1 case)

L4c definition: A state variable changes in the same direction in both buggy and correct versions, with the only difference being the magnitude of the change. `changed()` / `Entry op Exit` annotations are equally satisfied in both versions. The primary blocker is that PostEntryExit does not support arithmetic expressions (`Entry - Exit == expected_magnitude`).

---

### Case 13 — `web3bugs_35_H_10` (current classification: **L4c**, sole case)

#### 1. Audit report citation

- **Source**: `reports/35.md` → `[H-10] ConcentratedLiquidityPool.burn() Wrong implementation`
- **Severity**: High. **Warden**: WatchPug (C4 2021-09-sushitrident-2).
- **Core claim (verbatim excerpt)**:
  > The reserves should be updated once LP tokens are burned to match the actual total bento shares hold by the pool. However, the current implementation only updated reserves with the fees subtracted. Makes the `reserve0` and `reserve1` smaller than the current `balance0` and `balance1`.
- **Impact**: "many essential features of the contract will malfunction, includes `swap()` and `mint()`" (subsequent requires fail under the reserve > balance condition).
- **Recommended fix**:
  ```solidity
  // Change L263-266
  unchecked {
      reserve0 -= uint128(amount0);   // was amount0fees
      reserve1 -= uint128(amount1);   // was amount1fees
  }
  ```
- **Sponsor**: sarangparikh22 confirmed.

#### 2. Understanding the code semantics

##### (2a) Contract purpose

`ConcentratedLiquidityPool` — Sushi Trident's **Uniswap V3-style concentrated liquidity pool**. Tick-based range liquidity + fee accounting. `reserve0`/`reserve1` are internal trackers of the bento shares the pool holds.

##### (2b) Function role

`burn(bytes data)` (L231–272, public):
- The LP provider burns a position to withdraw liquidity.
- The withdrawn amount = **principal (proportional to liquidity) + fee**, two parts.
- The reserve decrease must **reflect both parts** to stay in sync with the balance.

##### (2d) Line-by-line core (L245–266)

```solidity
245  (uint256 amount0, uint256 amount1) = _getAmountsForLiquidity(...);   // principal portion
252  (uint256 amount0fees, uint256 amount1fees) = _updatePosition(...);    // fee portion
254  unchecked {
255      amount0 += amount0fees;                                            // total = principal + fees
256      amount1 += amount1fees;
257  }
...
263  unchecked {
264      reserve0 -= uint128(amount0fees);    // BUG: missing principal portion
265      reserve1 -= uint128(amount1fees);    // BUG
266  }
268  _transferBothTokens(recipient, amount0, amount1, unwrapBento);       // actual transfer uses amount0 (total)
```

- L255–256: `amount0` is updated to **principal + fees combined**.
- L268: **the entire `amount0` is transferred**.
- L264 (BUG): `reserve0` decreases **only by `amount0fees`**.
- Result: `balance0` decreased by `amount0` while `reserve0` only decreased by `amount0fees` → the **reserve0 > balance0** state persists.
- Subsequent `mint()` checks `require(reserve0 <= balance0)` and reverts → pool functionality is paralyzed.

##### (2e) Underlying meaning of the bug

The goal is to maintain the internal invariant of reserve tracking (`reserve ≤ balance`). When `burn` transfers tokens to the sender, the reserve must decrease by the same amount. Subtracting only the fee portion is an accounting error that **ignores the principal movement**.

#### 3. IntentChecker annotation attempt

**Function scope**: `amount0`, `amount1`, `amount0fees`, `amount1fees` — **all exist as local variables**.

**(a) `@Post reserve0 (entry relOp exit)` channel**:
- `entry > exit` (decreasing direction): satisfied by both buggy and correct — both decrease reserve0.
- `entry == exit`: violated by both.
- Direction alone **cannot distinguish** the two. The grammar's entry/exit comparison **only allows qualitative form (relOp: =, ≠, <, >)**, not magnitude comparison.

**(b) `@Post changed(reserve0, true)` channel**:
- Both buggy and correct are satisfied — both change.

**(c) Magnitude expression attempt**:
- A form like `@Post reserve0_entry - reserve0_exit == amount0` is required.
- There is no syntax for placing `reserve0_entry` inside an arithExpr. `reserve0 (entry relOp exit)` is a special form.
- In `commonClause`'s `intentValue relOp intentValue`, `reserve0` only refers to its exit value.
- No path to reference the entry value → **inexpressible**.

**(d) Aux injection (I4)**:
- Insert `uint128 reserve0_before = reserve0;` at the top of the function.
- Annotation: `@Post reserve0_before == reserve0 + amount0` — grammar OK.
- Buggy: `reserve0_before == reserve0 + amount0fees ≠ reserve0 + amount0` → VIOLATED.
- Correct: `reserve0_before == reserve0 + amount0` → SATISFIED.
- **Detectable with injection**. However, the very decision to inject the snapshot already implies awareness that "the reserve decrement should equal amount0" → transit toward L5.

#### 4. Classification rationale — **L4c confirmed**

**Essence of L4c**: The grammar's postClause `intentValue (entry relOp exit)` **only permits qualitative comparison** (direction/equality). There is no syntactic means to express magnitude (the exact difference). Case 13 is the archetype where buggy/correct change the same state variable in the same direction and differ only in magnitude.

The `limitation_types.md` description of L4c is accurate. As **the sole L4c case, generalization is not yet possible**.

#### 5. Root cause

**Essence (L4c — qualitative restriction of postClause grammar)**:

The PostEntryExit form `intentValue (entry relOp exit)` does not include arithmetic. That is, "reserve0 decreased by amount0" (`before - after == amount0`) is inexpressible. **A grammar-level limitation**.

**I8 new-axis re-classification**:
- **Bug category**: **Value error** — wrong identifier choice (should have been `amount0` instead of `amount0fees`). One-line fix.
- **Proxy type**: **Type A** — the correct identifier `amount0` **exists in scope**.
- I.e., Case 13 is **Value / Type A**. Following Case 1 (A_candidate), this is the **second confirmed Type A case**.

**Resemblance to Case 8 (61_H_01)**: both are wrong-identifier-choice errors (wrong identifier in scope).
- Case 8: `.arg[n]` channel possible, semantic channel blocked (@IReturn arg-indifference) → **L4a**.
- Case 13: no `.arg[n]` channel (state subtraction takes the form `x -= y`, not a call); the `changed`/`entry-exit` channels are qualitative only → **L4c**.
- Both are excluded from lint-level L5b under I9 → fixed at L4.

**Important observation — character of L4c**:
- L4c is **the cell that drops to L4 because, although the scope is Type A (proxy exists), the grammar postClause cannot express magnitude**.
- It is **completely different in character** from L4a (Type B: proxy absent).
- In the new I8 axis matrix, L4c occupies a single cell as **Value / Type A / grammar-limit**. Distinct from L4a's Value/B cell.

**Aux injection (I4) path**: A simple snapshot of the local `reserve0_before`. The easiest I4 injection (a single state copy). Y (easy).

**[Category (I8)]**: **Value error / Type A (grammar-limit)** — the sole L4c case. The qualitative restriction of postClause grammar is the primary blocker. The proxy (`amount0`) is in scope, but the grammar cannot express the state-transition magnitude.

#### 6. Suggested improvements to the paper text

- **L4c body (line 1319)** can be retained. However, **make explicit that the essence of L4c is a "grammar-level restriction", not absence of scope**. Mention the possibility of L5 transit via aux injection.
- **Grammar-extension candidate**: allowing arithmetic such as `intentValue (entry - exit == expr)` would dissolve L4c (without snapshot injection). Paper insight: this is **the only L4 category that can be dissolved by a simple grammar extension**.
- **Placement in I8 matrix**: after completing all 34 cases, separate L4c in the matrix into the **Value/A / grammar-limit** cell. Emphasize the structural difference from L4a (Value/B).

---

## L4d — Invariant Masked (1 case)

L4d definition: Other code in the same function already changes the target variable, so `changed()`/PostEntryExit are satisfied in both buggy and correct versions. A **multi-variable arithmetic relationship** such as a product invariant is required, but PostEntryExit does not support arithmetic expressions.

---

### Case 14 — `web3bugs_36_H_02` (current classification: **L4d**, sole case)

#### 1. Audit report citation

- **Source**: `reports/36.md` → `[H-02] Basket.sol#auctionBurn() A failed auction will freeze part of the funds`
- **Severity**: High (judge confirmed). **Warden**: WatchPug (C4 2021-09-defiprotocol).
- **Core claim (verbatim excerpt)**:
  > Given the `auctionBurn()` function will `_burn()` the auction bond without updating the `ibRatio`. Once the bond of a failed auction is burned, the proportional underlying tokens won't be able to be withdrawn, in other words, being frozen in the contract.
- **POC**: ibRatio=1e18, totalSupply=400, burn 1 token → buggy ibRatio remains 1e18, totalSupply=399. When a user burns 1 token, they can withdraw 1 BTC + 1 ETH, but relative to the original assets **1 BTC + 1 ETH is permanently locked**.
- **Recommended fix**:
  ```solidity
  function auctionBurn(uint256 amount) onlyAuction external override {
      handleFees();
      uint256 startSupply = totalSupply();
      _burn(msg.sender, amount);
      uint256 newIbRatio = ibRatio * startSupply / (startSupply - amount);
      ibRatio = newIbRatio;
      emit NewIBRatio(newIbRatio);
      emit Burned(msg.sender, amount);
  }
  ```
- **Judge**: "funds can be irrevocably lost, this is a high severity finding".

#### 2. Understanding the code semantics

##### (2a) Contract purpose

`Basket` — DefiProtocol's **index basket token** (ETF-style). Users mint/burn the basket token while underlying tokens (BTC, ETH, etc.) are deposited/withdrawn proportionally. `ibRatio` is an **accounting multiplier** that maintains the basket-token ↔ underlying ratio. Invariant: `ibRatio × totalSupply` is proportional to the pool's total underlying value.

##### (2b) Function role

`auctionBurn(amount) onlyAuction external` (L102–108):
- Called by the auction contract to burn a **failed auction bond**.
- Decreases totalSupply via `_burn`.
- For the remaining users to receive the same proportional underlying withdrawal, **ibRatio must increase inversely with the totalSupply decrease** (preserving the invariant).
- The audit fix: `newIbRatio = ibRatio * startSupply / (startSupply - amount)` — the exact invariant-preserving formula.

##### (2d) Line-by-line (L102–108)

```solidity
102  function auctionBurn(uint256 amount) onlyAuction external override {
103      handleFees();         // (A) updates ibRatio in a particular branch
105      _burn(msg.sender, amount);   // decreases totalSupply
107      emit Burned(msg.sender, amount);
108  }
```

- **L103 (`handleFees`)**: only updates ibRatio when `lastFee != 0 && time passed` (`ibRatio = ibRatio * startSupply / totalSupply()`). Its purpose is to charge fees. If `lastFee == 0`, it is a no-op (setter only).
- **L105 (`_burn`)**: decreases totalSupply.
- **MISSING BUG**: after totalSupply decreases, **there is no ibRatio update to preserve the invariant**.

##### (2e) Underlying meaning of the bug

**Multi-variable product invariant violation**. Before `auctionBurn`: `ibRatio_entry × totalSupply_entry = K`. After `auctionBurn` (under the fix): `ibRatio_exit × totalSupply_exit = K` is preserved. In the buggy version only totalSupply decreases while ibRatio is unchanged → the product decreases → the proportional share of the underlying tokens becomes "non-recoverable" (frozen).

In the POC: 1 BTC + 1 ETH is permanently locked. Proportional freeze of funds is a High severity issue.

#### 3. IntentChecker annotation attempt

**Function scope**:
- Param: `amount`.
- State: `ibRatio`, `totalSupply` (ERC20 inherited), `lastFee`, etc.

**(a) `@Post changed(ibRatio, true)` channel** — the core L4d issue:
- `handleFees` **already updates ibRatio in some branches**. Therefore:
  - Scenario-A (`lastFee != 0` + time passed): handleFees changes ibRatio → both buggy and correct satisfy `changed`. **Indistinguishable**.
  - Scenario-B (`lastFee == 0`): handleFees does not change ibRatio → buggy unchanged, correct changed. Distinguishable.
- I.e., **detectability splits according to debug annotation scenario** (the I6 boundary between general vs specific).

**(b) `@Post ibRatio (entry == exit)` (asserting invariance)**:
- Buggy Scenario-A: ibRatio is already changed by handleFees → VIOLATED.
- Buggy Scenario-B: ibRatio unchanged → SATISFIED.
- Correct: always changes (manual update) → VIOLATED.
- Distinguishable (in reverse direction) in Scenario-B. In Scenario-A both are VIOLATED → indistinguishable.

**(c) Product invariant (the real intent)**:
- Correct: `@Post ibRatio * totalSupply (entry == exit)` — **product preservation**.
- The grammar's `intentValue (entry relOp exit)` is **qualitative only**. It does not allow arithmetic expressions (product).
- Trying `commonClause`'s `intentValue relOp intentValue` to assert `ibRatio * totalSupply == <entry value>`: there is no way to express the entry value (same as Case 13).
- **Inexpressible** (the primary essence of L4d).

**(d) Aux injection (I4)**:
- Inject `uint256 K_before = ibRatio * totalSupply();` → product-invariant check becomes feasible. There is the `totalSupply()` function-call issue (resolvable if the inherited ERC20 `_totalSupply` state is accessible — Issue 8 territory).
- **Y_medium** level.

#### 4. Classification rationale — **L4d confirmed**

The `limitation_types.md` description of L4d is accurate. handleFees may already change ibRatio, masking `changed`, while the real invariant (product preservation) is inexpressible due to the absence of PostEntryExit arithmetic.

#### 5. Root cause

**Essence (L4d — multi-variable arithmetic invariant inexpressible)**:

Correct intent = `ibRatio × totalSupply == ibRatio_entry × totalSupply_entry` (product preservation). This form does not exist in the postClause grammar.

**Comparison with Case 13 (L4c)**:
- L4c: single-variable magnitude (`reserve0 entry - exit == amount0`).
- L4d: multi-variable product (`ibRatio × totalSupply` invariant).
- Both reduce to **the limited arithmetic expressivity of PostEntryExit grammar**.

I.e., **L4c and L4d are essentially two manifestations of the same grammar-limit**:
- L4c: `diff == const`.
- L4d: `product == const`.
- The essential blocker is the same (absence of arithmetic PostEntryExit).

**I8 new-axis re-classification**:
- **Bug category**: **Algorithm error** — missing invariant-preservation logic (= missing state update). Multi-line fix (startSupply + newIbRatio computation + ibRatio update + emit).
- **Proxy type**: **Type A** — all relevant variables (`ibRatio`, `totalSupply`, `amount`) exist in scope/state.
- **Algorithm / Type A (grammar-limit)** — same "Type A / grammar-limit" axis as Case 13 (Value/A), differing in bug category.

G-surfaces:
- **G6 (specific to L4d)** — multi-variable PostEntryExit arithmetic is inexpressible.
- **Type A side**: no G1/G3 (variables are all in scope).

**Silent sanction (I5)**:
- `@Post changed(ibRatio, true)` is satisfied by buggy in Scenario-A → silent sanction.
- Distinguishable only in Scenario-B → fortunate scenario (the I6 specific form).

**Common to Cases 13 + 14 — "Proposal to merge L4c/L4d"**:
For both, the PostEntryExit grammar-limit is the primary issue. Only the bug category differs:
- L4c (Case 13): Value / Type A / magnitude-grammar-limit.
- L4d (Case 14): Algorithm / Type A / product-grammar-limit.
- In the new axis matrix these two cases are **two sub-patterns of the same grammar-limit cell**. Proposal for the paper: merge L4c and L4d into a **"PostEntryExit arithmetic gap"**.

**[Category (I8)]**: **Algorithm error / Type A (grammar-limit)** — multi-variable invariant preservation. Shares structure with L4c.

#### 6. Suggested improvements to the paper text

- **L4c + L4d merger**: under the new axis these two cases occupy **the same grammar-limit cell**. Consider unifying them in the paper as a single "PostEntryExit arithmetic absence" item.
- **Grammar-extension candidate**: both Case 13 and Case 14 are dissolved by allowing `intentValue (entry arithOp exit)`. Concrete proposals: `reserve0 (entry - exit == amount0)` (L4c), `ibRatio * totalSupply (entry == exit)` (L4d).
- **Invariant DSL future direction**: Multi-variable protocol invariants are a DeFi cornerstone, yet the current grammar does not support them. This serves as the basis for proposing an **invariant annotation DSL** in future work.

---

## L4b batch (Cases 15–20) — 6-case compact batch

**Batch approach**: per-case key information + new 4-axis tagging. Common patterns are consolidated in the L4b subsection summary. File size is controlled.

---

### Case 15 — `web3bugs_52_H_16` (L4b, twin of Case 12)

- **Audit**: `[H-16] VaderRouter.calculateOutGivenIn calculates wrong swap` (cmichel, confirmed).
- **Bug** (L488–495): in the 3-path swap, the pool order is reversed. Inner `calculateSwap` uses `pool1` reserves and outer uses `pool0` reserves — the correct order is **inner=pool0 (foreign→native), outer=pool1 (native→foreign)**.
- **Fix**: swap the reserve arguments at the pool0/pool1 positions.
- **Function type**: `calculateOutGivenIn` external view — no state writes.
- **Annotation attempt**: (a) `@Post returnExpression == correct_amountOut` is needed — a combination of the VaderMath.calculateSwap chain + pool0/pool1 reserves. The grammar disallows function calls → inexpressible. (b) The `.arg[n]` order check is feasible but **excluded from L5b by I9 (lint-level)**.
- **Classification**: annotation_plans.md = L5b → after applying I9 principle, **L4b** (view + dependence on external reserves/formula).
- **[Category (I8)]**: **Value error / Type B** — the view-version twin of Case 12 (52_H_15). Pool routing semantics is outside VaderRouter scope.

---

### Case 16 — `web3bugs_58_H_04` (L4b)

- **Audit**: `[H-04] AaveVault stale tvl` (Aave's rebasing aToken). annotation_plans.md L5a.
- **Bug** (L47, related to _push/_pull): `tvl()` returns the cached `_tvls`. In `_push()`, `updateTvls()` is called **after** the deposit → LPIssuer **computes shares based on the old tvl** → excessive shares are issued before Aave interest is reflected.
- **Fix**: add `updateTvls()` at the start of `_push()` (correct the operation ordering).
- **Function type**: `tvl` view, `_push`/`_pull` state-modifying wrappers.
- **Annotation attempt**:
  - `@Post` on `_tvls` change: both buggy and correct are satisfied (both invoke updateTvls).
  - The "update tvl before deposit" ordering invariant: not supported by the grammar.
  - A snapshot like `@During bal_before == bal_after_before_deposit` — requires aux injection.
- **Classification**: L4b (view tvl; _push wrapper → has state attachment but cannot distinguish since the issue is ordering).
- **[Category (I8)]**: **Algorithm error / Type B** — the ordering issue exceeds the scope of a single annotation. Similar to Case 11 (17_H_02) (view + missing check/call).

---

### Case 17 — `web3bugs_62_H_01` (L4b)

- **Audit**: `[H-01] Stream.recoverTokens leaks flashloan fee`. Sponsor (brockelmore) confirmed.
- **Bug** (L654): `excess = balanceOf(this) - (depositTokenAmount - redeemedDepositTokens)` — `depositTokenFlashloanFeeAmount` is missing.
- **Fix**: `excess = balanceOf(this) - (depositTokenAmount - redeemedDepositTokens) - depositTokenFlashloanFeeAmount` (one term added).
- **Function type**: external, only safeTransfer — the Stream contract itself has no state writes (close to a wrapper).
- **Annotation attempt**:
  - The operand `depositTokenFlashloanFeeAmount` of the correct formula is a **state var in scope**.
  - `balanceOf(this)` is an external interface view — the call site exists but **is not stored locally** (inline chain).
  - `@During excess (assign == balanceOf_result - (...) - depositTokenFlashloanFeeAmount)` — `balanceOf_result` has no local.
  - Aux injection: insertion of `uint256 bal = balanceOf(...);` makes annotation possible.
- **annotation_plans.md L5a** → proposed re-classification to **L4b** under I9 + the wrapper nature (no state writes + balanceOf inline chain).
- **[Category (I8)]**: **Algorithm error / Type B** — missing formula term + balanceOf result not stored locally. Similar to Case 9 (61_H_02) (wrapper return handling).

---

### Case 18 — `web3bugs_70_H_08` (L4b)

- **Audit**: `[H-08] USDV/VADER rate conversion missing 1e18 scaling`. Judge resolved.
- **Bug** (L98, L102):
  - Line 98: `amount = amount / usdvPrice` — usdvPrice is at 1e18 scale, so the result is undersized by 1e18.
  - Line 102: `amount = amount * vaderPrice` — oversized by 1e18.
  - Correct: `amount * 1e18 / usdvPrice`, `amount * vaderPrice / 1e18`.
- **Function type**: external, vader.safeTransfer then emit. VaderReserve state is unchanged (transfer only). Wrapper.
- **Annotation attempt**:
  - `usdvPrice`, `vaderPrice` — return values from interface view calls, **stored locally** (L96, L100).
  - Correct annotation: `@During amount (assign == original_amount * 1e18 / usdvPrice)` in branch 1.
  - Issue: `amount` is **the parameter overwritten in place** → the original value is lost.
  - Aux injection: `uint256 original = amount;` must be inserted at the top.
- **annotation_plans.md L5a** → proposed re-classification to **L4b** due to wrapper + parameter overwrite.
- **[Category (I8)]**: **Value error / Type B** — missing scaling factor; with the parameter overwritten the original value is out of scope. Wrapper-version of the "scaling trio" of Cases 1, 2, 10.

---

### Case 19 — `web3bugs_83_H_02` (L4b)

- **Audit**: `[H-02] MasterChef deposit fee permanently locked`.
- **Bug** (L170–172, inside the deposit branch): `depositFee` is computed and subtracted from user.amount, but **there is no code increasing feeRecipient.amount** → tokens equivalent to the fee are permanently locked.
- **Fix**: add the corresponding feeRecipient state update.
- **Function type**: external, has user state changes (user.amount, user.rewardDebt).
- **Annotation attempt**:
  - The user-side state (user.amount) is correctly `_amount - depositFee` in both buggy/correct → `changed(user.amount, true)` is satisfied by both.
  - The fee-recipient-side state is **entirely missing from the code** — there is no fee-recipient account slot in the data model.
  - The "missing state variable" pattern of Case 11 (Buoy3Pool.safetyCheck).
- **annotation_plans.md L4b unchanged** — within the "target storage variable" idea, the "target" is the fee recipient, which is not in scope.
- **[Category (I8)]**: **Algorithm error / Type B** — missing state update + the target state variable itself is absent. Similar to Case 11 (data model absence).

---

### Case 20 — `web3bugs_110_H_01` (L4b, recurring twin pattern)

- **Audit**: `[H-01] StakedCitadel.balance missing strategy portion`. Sponsor confirmed.
- **Bug** (L293–294): `balance()` returns only `token.balanceOf(address(this))`, missing `IStrategy(strategy).balanceOf()`. Although the comment specifies "vault + strategy balance", the implementation covers only the vault.
- **Fix**: `return token.balanceOf(address(this)) + IStrategy(strategy).balanceOf();`
- **Function type**: public view.
- **Annotation attempt**:
  - The correct return requires a call to `IStrategy(strategy).balanceOf()`.
  - `strategy` is a state var (in scope), but the `.balanceOf()` call itself is **not in the code** → no `@IReturn` attachment point (same structure as Case 2, 25_H_05).
  - `@Post returnExpression == token.balanceOf(this) + strategy.balanceOf()` — both calls are inexpressible inside the intent (G1).
- **Classification**: annotation_plans.md L5a → proposed re-classification to **L4b** due to I9 + view + absent function call.
- **[Category (I8)]**: **Algorithm error / Type B** — missing interface call + absent call site. Same family as Cases 11 and 16 (view + missing call).

---

### L4b Subsection Summary (Cases 11-12, 15-20 — 8 cases total)

**Common patterns**:
1. **Function type**: view (11, 15, 16 tvl, 20) / wrapper without state (12, 17, 18) / state-modifying but with target state absent (19).
2. **Intent channel blocked**:
   - State-based @Post infeasible (view), or lacks distinguishing power (wrapper/missing-target).
   - Return-based @Post also cannot express the semantics (G1, G3).
3. **Proxy type**: all **Type B**. The L4b definition ("no-target-storage") is essentially a function-type-based special case of Type B.
4. **Bug category**: 2 Value (15, 18), 6 Algorithm (11, 12, 16, 17, 19, 20). Algorithm dominates — many missing-call/update/term patterns.
5. **Silent sanction frequency**: applies in most cases — translating the code straight into an annotation reproduces the buggy behavior.
6. **Aux injection**: feasible (17, 18) vs infeasible (data-model extension required: 11, 19). **A spectrum of difficulty**.

**Twin observations**:
- (11, 16, 20): view function + missing call/update/check.
- (12, 15): VaderRouter _swap vs calculateOutGivenIn — same-contract twins (state-modifying vs view).
- (17, 18, 1, 2, 10): scaling/missing-formula-term family.

**Re-classification review results**:
- annotation_plans.md mislabels many L4b cases as L5a/L5b. Considering principle I9 + function type, **L4b is correct**.
- Re-classification: 15 (L5b→L4b), 17 (L5a→L4b proposed), 18 (L5a→L4b proposed), 20 (L5a→L4b proposed).

**I8 matrix distribution (L4b 8 cases)**:
- Algorithm/B: 6 (11, 12, 16, 17, 19, 20).
- Value/B: 2 (15, 18).
- Type A · A_candidate · non-B: 0.

→ **L4b is confirmed as a Type-B-only cell**.

---

## L5a — Missing Code (7 cases, compact batch: Cases 21–27)

**L5a definition**: Code that should exist (state update, function call, etc.) is missing. The post-condition can be expressed using existing state variables (basic Type A). Bug awareness is presupposed.

**Proposed L5-only axis**: **Bug awareness source**:
- **(consistency)**: derivable through comparison with sibling functions/branches (pattern-level).
- **(domain)**: requires protocol domain knowledge (semantic-level).

---

### Case 21 — `web3bugs_35_H_12` (L5a)

- **Contract/Function**: ConcentratedLiquidityPool / mint (L176, L184 original).
- **Bug**: After modifying `liquidity`, the update of `secondsPerLiquidity` is missing. `swap()` performs `secondsPerLiquidity += uint160((diff << 128) / liquidity)` for the same change — the consistency was missed.
- **Annotation**: `@Post changed(secondsPerLiquidity, true)` — buggy unchanged, correct changed → distinguishable.
- **Bug awareness**: **consistency** (derivable from sibling comparison with swap).
- **Additional blocker**: parameters delivered via `abi.decode` (L3 unsupported-construct) — restricts the supply of debug annotations.
- **[Category]**: **Value / Type A / consistency** (L5a).

---

### Case 22 — `web3bugs_52_H_23` (L5a)

- **Contract/Function**: VaderPoolV2 / mintSynth (L161).
- **Bug**: `_update(foreignAsset, reserveNative + nativeDeposit, reserveForeign, ...)` — the subtraction of `amountSynth` from `reserveForeign` is missing. Excessive synth issuance.
- **Annotation**: `@Post changed(reserveForeign, true)` — buggy unchanged (arg = current value), correct changed → distinguishable. Or `@Post reserveForeign (entry > exit)`.
- **Bug awareness**: **domain** (requires the accounting rule that foreign reserve must reflect synth issuance).
- **[Category]**: **Value / Type A / domain** (L5a).

---

### Case 23 — `web3bugs_62_H_03` (L5a, symptom in recoverTokens, root in claimReward)

- **Contract/Function**: Stream / claimReward (L575 transfer).
- **Bug**: When transferring reward tokens, the `rewardTokenAmount -= rewardAmt` update is missing. `recoverTokens` then references the stale value, producing wrong excess computation.
- **Annotation (at the root-cause site)**: `@Post changed(rewardTokenAmount, true)` or `@Post rewardTokenAmount (entry > exit)` on `claimReward`.
- **Bug awareness**: **consistency** (the general accounting pattern of token transfer ↔ tracking-variable update).
- **Additional blocker (at the symptom site)**: `balanceOf()` external — auxiliary L2a.
- **[Category]**: **Value / Type A / consistency** (L5a).

---

### Case 24 — `web3bugs_62_H_10` (L5a, symptom in recoverTokens, root in creatorClaimSoldTokens)

- **Contract/Function**: Stream / creatorClaimSoldTokens (L597 transfer).
- **Bug**: When transferring deposit tokens, the `redeemedDepositTokens` update (or `depositTokenAmount = 0`) is missing. Twin pattern of 62_H_03.
- **Annotation**: `@Post changed(redeemedDepositTokens, true)` on `creatorClaimSoldTokens`.
- **Bug awareness**: **consistency** (the same token-transfer-tracking pattern).
- **[Category]**: **Value / Type A / consistency** (L5a). Twin of Case 23.

---

### Case 25 — `web3bugs_65_H_01` (L5a)

- **Contract/Function**: Basket / handleFees (L136–137).
- **Bug**: In the `startSupply == 0` branch, the `lastFee = block.timestamp` update is missing. The other two branches (`lastFee == 0`, normal `else`) do update it. Consequently, fees are charged even for periods when supply was zero.
- **Annotation**: `@Post changed(lastFee, true)` — must change in every branch.
- **Bug awareness**: **consistency** (cross-branch consistency — verifying that one branch is missing what the others do).
- **[Category]**: **Value / Type A / consistency** (L5a).

---

### Case 26 — `web3bugs_83_H_01` (L5a)

- **Contract/Function**: MasterChef / add (L89).
- **Bug**: `massUpdatePools()` is not called before incrementing `totalAllocPoint`. The `accConcurPerShare` of existing pools then retroactively reflects the new `totalAllocPoint`, diluting existing stakers' rewards.
- **Annotation**: `@Post poolInfo[1].accConcurPerShare (entry != exit)` — for existing pools, accConcurPerShare must be updated.
- **Bug awareness**: **consistency** (`set`/`update` functions elsewhere call massUpdatePools first — derivable by comparison) + **domain** (understanding reward accrual).
- **[Category]**: **Algorithm / Type A / consistency+domain** (L5a).

---

### Case 27 — `web3bugs_192_H_01` (L5a)

- **Contract/Function**: Lock / extendLock (L90, L91).
- **Bug**: When receiving tokens via `transferFrom`, the `totalLocked[_asset] += _amount` is missing. The subsequent `release()`'s `totalLocked[asset] -= lockAmount` underflows → funds permanently locked.
- **Annotation**: `@Post totalLocked[_asset] (entry < exit)` or `@Post changed(totalLocked[_asset], true)`.
- **Bug awareness**: **consistency** (the `lock()` function correctly performs `totalLocked += _amount` — `extendLock` misses it. Sibling comparison).
- **[Category]**: **Value / Type A / consistency** (L5a).

---

### L5a Subsection Summary (7 cases)

**Common patterns**:
1. **All Type A** (a natural consequence of the L5 definition) — the relevant state vars are in scope.
2. **Annotation form**: nearly all use `changed(x, true)` or `x (entry relOp exit)` — checking the direction or occurrence of state change is sufficient.
3. **Bug awareness source distribution**:
   - **consistency: 6** (35_H_12, 62_H_03, 62_H_10, 65_H_01, 83_H_01, 192_H_01).
   - **domain: 1** (52_H_23).
   - → L5a is **mostly derivable by pattern-check**.
4. **Bug category distribution**:
   - **Value (missing state update): 6**: 35_H_12, 52_H_23, 62_H_03, 62_H_10, 65_H_01, 192_H_01.
   - **Algorithm (missing function call): 1**: 83_H_01.

**Twin observations**:
- (62_H_03, 62_H_10): Stream's token-transfer-vs-tracking twins.
- (35_H_12, 83_H_01, 192_H_01): family of sibling-function consistency omissions.
- (65_H_01): branch consistency (within a single function).

**Paper insight**:
- L5a "detectability" depends on **whether the developer notices the consistency pattern**, not on annotation expressivity.
- This suggests that **IntentChecker's annotation-writing workflow is powerful when combined with sibling/branch consistency review principles**. Basis for a "consistency-driven annotation writing" workflow proposal in the paper Discussion.
- **The domain case (52_H_23) is separate** — domain expert review is essential. Hard to resolve through annotation alone.

**I8 + L5-axis distribution (7 cases)**:
- Value/A/consistency: 5 (35_H_12, 62_H_03, 62_H_10, 65_H_01, 192_H_01).
- Value/A/domain: 1 (52_H_23).
- Algorithm/A/consistency+domain: 1 (83_H_01).

→ **L5a concentrates in the Value/A/consistency cell** — can be presented in the paper as the "easiest detection region".

---

## L5b — Wrong Code (7 cases, compact batch: Cases 28–34)

**L5b definition**: Code exists but uses a wrong identifier, operator, struct field, ordering, etc. Annotation expression is feasible (Type A); writing an accurate intent presupposes bug awareness.

---

### Case 28 — `web3bugs_31_H_01` (L5b)

- **Contract/Function**: MyStrategy / manualRebalance (L469, 471, 477).
- **Bug**: Dimensional mismatch. `currentLockRatio = balanceInLock * 1e18 / totalCVXBalance` (a ratio) vs `newLockRatio = totalCVXBalance * toLock / MAX_BPS` (an absolute amount) → ratio and amount are compared with `<=`.
- **Fix (audit)**: `currentLockRatio = balanceInLock` (unify as amount).
- **Annotation**: `@During currentLockRatio (assign == balanceInLock)` — grammar OK; `balanceInLock` in scope.
- **Bug awareness**: **domain** (back-derived from analysis of the downstream `cvxToLock = newLockRatio.sub(currentLockRatio)`).
- **[Category]**: **Value / Type A / domain** (L5b).

---

### Case 29 — `web3bugs_35_H_11` (L5b)

- **Contract/Function**: Ticks / cross (L40, L49).
- **Bug**: In the `zeroForOne` branch the wrong struct field is updated — should update `ticks[next].feeGrowthOutside0` but uses field 1 (the opposite branch is symmetrically reversed).
- **Annotation**: `@Post changed(ticks[nextTickToCross].feeGrowthOutside1, true)` (when zeroForOne) — assert that only the correct field is modified.
- **Bug awareness**: **domain** (the semantic mapping `zeroForOne → token1 fee → feeGrowthOutside1`).
- **[Category]**: **Value / Type A / domain** (L5b).

---

### Case 30 — `web3bugs_70_H_09` (L5b)

- **Contract/Function**: USDV / mint, burn (L76 mint, L109 burn).
- **Bug**: `uAmount = vPrice * vAmount / 1e18` (mint), `vAmount = uPrice * uAmount / 1e18` (burn) — the formula direction is wrong relative to the oracle return semantics (USD/Vader vs Vader/USD).
- **Fix**: `uAmount = vAmount * 1e18 / vPrice` (or `vPrice * vAmount / 1e18` — depending on the oracle spec).
- **Annotation**: `@Post uAmount == vAmount * 1e18 / vPrice` — grammar OK.
- **Bug awareness**: **domain** (requires understanding of the oracle API spec).
- **[Category]**: **Value / Type A / domain** (L5b).

---

### Case 31 — `web3bugs_79_H_02` (L5b)

- **Contract/Function**: LaunchEvent / createPair (L398).
- **Bug**: `tokenAllocated = (wavaxReserve * 10**token.decimals()) / floorPrice` — `floorPrice` is at 1e18 scale, so the correct computation is `wavaxReserve * 1e18 / floorPrice`. Severe error for non-18-decimals tokens (WBTC=8).
- **Annotation**: `@Post tokenAllocated == wavaxReserve * 1e18 / floorPrice`.
- **Bug awareness**: **domain** (the natspec "scaled to 1e18" provides a partial hint — not pure domain, but understanding scaling semantics is required).
- **[Category]**: **Value / Type A / domain** (L5b).

---

### Case 32 — `web3bugs_101_H_02` (L5b)

- **Contract/Function**: LenderPool / terminate (L389, L400).
- **Bug**: `_actualNotBorrowedInShares` is computed via a token/share mixed calculation and then passed to `withdrawShares`. Since terminate = full-shares withdrawal, using `_sharesHeld` directly is correct.
- **Fix**: simplify to `_sharesHeld`.
- **Annotation**: `@Post withdrawShares == _sharesHeld` — `_sharesHeld` in scope.
- **Bug awareness**: **domain** (understanding the terminate semantics = "withdraw all shares").
- **[Category]**: **Value / Type A / domain** (L5b).

---

### Case 33 — `web3bugs_112_H_01` (L5b, **operation ordering**)

- **Contract/Function**: StakerVault / transfer (L112, 113, 117, 118).
- **Bug**: `balances[sender] -= amount` / `balances[receiver] += amount` (L31–32) execute **before** `userCheckpoint()` (L37, L39). The checkpoint computes rewards based on the already-modified balance → over-claim path.
- **Fix**: reorder to checkpoint → balance (the `transferFrom` function has the correct order).
- **Annotation**: `@During changed(balances[msg.sender], false)` immediately before the checkpoint call — buggy already mutated the balance → VIOLATED. Correct unchanged → SATISFIED.
- **Bug awareness**: **consistency** (`transferFrom` has the correct order — sibling comparison).
- **[Category]**: **Algorithm / Type A / consistency** (L5b — ordering is algorithmic in nature).

---

### Case 34 — `web3bugs_113_H_05` (L5b)

- **Contract/Function**: NFTPairWithOracle / _lend (L316).
- **Bug**: `require(params.ltvBPS >= accepted.ltvBPS, ...)` — from the lender's perspective lower LTV is preferred, so `<=` is correct.
- **Annotation**: `@During params.ltvBPS <= accepted.ltvBPS` — complementary to the require.
- **Bug awareness**: **domain** (understanding which direction benefits the lender).
- **Additional blocker**: `ltvBPS` is not used in subsequent amount computation (only the require check) → no impact on the state channel (auxiliary L2a).
- **[Category]**: **Value / Type A / domain** (L5b).

---

### L5b Subsection Summary (7 cases)

**Common patterns**:
1. **All Type A** (per the L5 definition).
2. **Diverse annotation forms**: `@During x (assign == y)` (value correction), `@Post changed(struct.field, true)` (field correction), `@Post expr == formula` (formula correction), `@During changed(x, false)` (ordering correction).
3. **Bug awareness source distribution**:
   - **domain: 6** (31, 35_H_11, 70_H_09, 79_H_02, 101_H_02, 113_H_05).
   - **consistency: 1** (112_H_01).
   - → L5b is **domain-knowledge dominant**. In contrast to L5a (consistency-dominant).
4. **Bug category distribution**:
   - **Value: 6**: 31, 35_H_11, 70_H_09, 79_H_02, 101_H_02, 113_H_05.
   - **Algorithm: 1**: 112_H_01 (ordering).

**L5a vs L5b contrast** (paper insight candidate):
| | L5a (missing-code) | L5b (wrong-code) |
|---|---|---|
| Bug awareness | **consistency dominant** (6/7) | **domain dominant** (6/7) |
| Detection difficulty | possible via sibling/branch comparison review | requires protocol semantic knowledge |
| IntentChecker contribution | **high** (assists pattern discovery) | **limited** (in the hands of domain experts) |

**I8 + L5-axis distribution (L5b 7 cases)**:
- Value/A/domain: 5 (31, 35_H_11, 70_H_09, 79_H_02, 113_H_05).
- Value/A/domain (101_H_02, a parameter-simplification case in the same vein): 1.
- Algorithm/A/consistency: 1 (112_H_01 ordering).

→ **L5b concentrates in the Value/A/domain cell** — the area requiring "annotation-writing-experienced domain experts".

---

### L5 complete — Cross-L5 Synthesis (14 cases)

**L5a + L5b contrast insight**:

```
L5a (missing-code)  → consistency-dominant → IntentChecker's strength area
  (sibling/branch comparison lets the annotation writer catch "something is missing")

L5b (wrong-code)    → domain-dominant     → IntentChecker's limited area
  (a wrong identifier/operator/ordering cannot be caught without semantic knowledge)
```

**Full I8 matrix (L4+L5 14 cases, L5 7+7=14 added):**
- Value/A/consistency: 5 (all L5a).
- Value/A/domain: 6 (1 L5a + 5 L5b).
- Value/A/mixed: 0.
- Value/A/grammar-limit: 1 (Case 13, L4c).
- Value/A_candidate: 1 (Case 1, L4a re-examination pending).
- Value/B: 7 (all L4).
- Algorithm/A/consistency: 2 (112_H_01 L5b, 83_H_01 L5a-mixed).
- Algorithm/A/domain: 0.
- Algorithm/A/grammar-limit: 1 (Case 14, L4d).
- Algorithm/B: 10 (all L4).

**Paper-ready dichotomy**:
- Type A / Value / consistency → **easiest detection**, pattern-check workflow effective.
- Type A / Value / domain → **domain expert required**, annotation as a supporting tool.
- Type A / grammar-limit (L4c, L4d) → **resolvable via grammar extension** (arithmetic PostEntryExit).
- Type B → **fundamental limitation under the current grammar + workflow**. Requires grammar extension + auxiliary injection workflow.

---
