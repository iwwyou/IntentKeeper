# Logic Error Analysis for Smart Contracts

## 1. Logic Error Definition

> **"컴파일/런타임 예외 없이 트랜잭션이 성공하지만, 개발자가 의도한 수치/상태를 깨뜨리는 버그"**
>
> A bug where a transaction succeeds without compile/runtime errors but violates the developer's intended values or state.

---

## 2. Two-Level Classification System

```
Logic Error
├── Level 1: Type Classification
│   ├── Numeric (수치 관련)
│   ├── Access Control (권한 관련)
│   ├── State Management (상태 관리)
│   ├── Business Flow (비즈니스 흐름)
│   └── ID/Validation (식별자/검증)
│
└── Level 2: Transaction Scope (Numeric Only)
    ├── Single Transaction
    └── Multiple Transaction
```

---

## 3. Data Sources

### 3.1 Web3Bugs (Code4rena)
- **Source**: https://github.com/ZhangZhuoSJTU/Web3Bugs
- **Total Bugs**: 493 bugs
- **Classification System**: O (Out-of-scope), L (Simple oracles), S (High-level semantic)

### 3.2 DeFiHackLabs
- **Source**: https://github.com/SunWeb3Sec/DeFiHackLabs
- **Total Incidents**: 674 incidents
- **Classification System**: Tag-based (price-manipulation, logic-flaw, etc.)

---

## 4. Web3Bugs Category Distribution

### 4.1 Out-of-Scope (O) - 113 bugs
| Label | Count | Description |
|-------|-------|-------------|
| O1 | 28 | Privileged user exploits |
| O2 | 12 | Source code unavailable |
| O3 | 16 | Requires victim user action |
| O4 | 5 | Off-chain components |
| O5 | 26 | Trivial/deployment bugs |
| O6 | 14 | Not considered bugs by project |
| O7 | 12 | Doubtful findings |

### 4.2 Simple Oracles (L) - 79 bugs
| Label | Count | Description | Numeric? |
|-------|-------|-------------|----------|
| L1 | 19 | Reentrancy | No |
| L2 | 7 | Rounding/Precision loss | **Yes** |
| L3 | 4 | Uninitialized variables | No |
| L4 | 6 | Gas limitation | No |
| L5 | 3 | Storage collision | No |
| L6 | 2 | Arbitrary external call | No |
| L7 | 17 | Integer overflow/underflow | **Yes** |
| L8 | 15 | Low-level call reverts | No |
| LA | 4 | Cryptographic issues | No |
| LB | 2 | tx.origin usage | No |

### 4.3 High-Level Semantic (S) - 300 bugs
| Label | Count | Description | Numeric? | TX Scope |
|-------|-------|-------------|----------|----------|
| **S1-1** | 15 | AMM price oracle manipulation | **Yes** | Multiple |
| **S1-2** | 8 | Sandwich attack | **Yes** | Multiple |
| **S1-3** | 1 | Non-AMM price oracle manipulation | **Yes** | Multiple |
| S2-1 | 14 | Arbitrary ID/lack of ID validation | No | - |
| S2-2 | 5 | Shared resource without locks | No | - |
| S2-3 | 2 | ID uniqueness violation | No | - |
| S3-1 | 22 | Missing state update | Partial | Single |
| S3-2 | 4 | Incorrect state update | Partial | Single |
| S4-1 | 8 | Business-flow atomicity violation | No | Multiple |
| S5-1 | 8 | Arbitrary privileged state update | No | - |
| S5-2 | 4 | Unauthorized function timing | No | - |
| S5-3 | 13 | Privileged function access | No | - |
| **S6-1** | 8 | Incorrect calculating order | **Yes** | Single |
| **S6-2** | 4 | Unexpected return value | **Yes** | Single |
| **S6-3** | 18 | Wrong numbers in calculation | **Yes** | Single |
| **S6-4** | 56 | Other accounting errors | **Yes** | Single |
| SE-1 | 15 | Unexpected function sequence | Partial | Multiple |
| SE-2 | 13 | Unexpected environment conditions | Partial | Multiple |
| SE-3 | 4 | Unexpected repeated invocation | No | Multiple |
| SE-4 | 13 | Unexpected function arguments | Partial | Single |
| SC | 65 | Contract-specific bugs | Varies | Varies |

---

## 5. DeFiHackLabs Tag Distribution

### 5.1 Numeric-Related Tags
| Tag | Count | TX Scope |
|-----|-------|----------|
| price-manipulation | 57 | Multiple |
| precision-loss | 8 | Single |
| flashloan-price-oracle-manipulation | 7 | Multiple |
| incorrect-reward-calculation | 6 | Single |
| donate-inflation-exchangerate-rounding-error | 5 | Single |
| flashloan-price-manipulation | 5 | Multiple |
| share-price-manipulation | 2 | Multiple |
| loss-of-precision | 2 | Single |
| incorrect-calculation | 1 | Single |
| div-precision-loss | 1 | Single |
| integer-overflow | 1 | Single |
| integer-underflow | 2 | Single |

**Total Numeric**: ~97 incidents

### 5.2 Access Control Tags
| Tag | Count |
|-----|-------|
| access-control | 44 |
| lack-of-access-control | 19 |
| incorrect-access-control | 7 |

**Total Access Control**: ~70 incidents

### 5.3 Business Logic Tags
| Tag | Count |
|-----|-------|
| business-logic-flaw | 73 |
| logic-flaw | 36 |

**Total Logic Flaw**: ~109 incidents

### 5.4 Reentrancy Tags
| Tag | Count |
|-----|-------|
| reentrancy | 29 |
| read-only-reentrancy | 3 |
| cross-contract-reentrancy | 2 |
| erc777-reentrancy | 2 |
| erc667-reentrancy | 2 |

**Total Reentrancy**: ~38 incidents

---

## 6. Proposed Logic Error Categorization

### 6.1 Level 1: Type Classification

| Category | Web3Bugs Labels | DeFiHackLabs Tags | Total Est. |
|----------|-----------------|-------------------|------------|
| **Numeric** | L2, L7, S1-*, S6-* | price-manipulation, precision-loss, incorrect-calculation | ~200+ |
| **Access Control** | S5-* | access-control, lack-of-access-control | ~95+ |
| **State Management** | S3-* | logic-flaw (partial) | ~26+ |
| **Business Flow** | S4-*, SE-* | business-logic-flaw (partial) | ~53+ |
| **ID/Validation** | S2-*, SE-4 | incorrect-input-validation | ~35+ |

### 6.2 Level 2: Numeric Sub-Classification

| Sub-Category | TX Scope | Description | Examples |
|--------------|----------|-------------|----------|
| **Single TX - Expression Level** | Single | Arithmetic in single expression | div_in_path, precision loss |
| **Single TX - Function Argument** | Single | Wrong values passed to functions | indivisible_amount, wrong params |
| **Single TX - Intra-function State** | Single | State ordering within function | CoverProtocol memory/storage |
| **Multiple TX - Price Manipulation** | Multiple | AMM/oracle price manipulation | Flash loan attacks |
| **Multiple TX - Cross-TX State** | Multiple | State dependency across TXs | Front-running, sandwich |

---

## 7. Sample Bugs by Category

### 7.1 Numeric - Single Transaction

#### S6-4: Other Accounting Errors (56 bugs)
```
- "Wrong liquidation logic"
  https://code4rena.com/reports/2021-04-marginswap#h-05-wrong-liquidation-logic

- "Wrong calcAsymmetricShare calculation"
  https://code4rena.com/reports/2021-04-vader#h-07-wrong-calcasymmetricshare-calculation

- "Wrong liquidity units calculation"
  https://code4rena.com/reports/2021-04-vader#h-08-wrong-liquidity-units-calculation
```

#### S6-3: Wrong Numbers in Calculation (18 bugs)
```
- "Wrong slippage protection on Token -> Token trades"
  https://code4rena.com/reports/2021-04-vader#h-15-wrong-slippage-protection-on-token---token-trades

- "User could lose underlying tokens when redeeming from the IdleYieldSource"
  https://code4rena.com/reports/2021-06-pooltogether#h-01-user-could-lose-underlying-tokens-when-redeeming-from-the-idleyieldsource
```

#### L2: Rounding/Precision Loss (7 bugs)
```
- "IdleYieldSource doesn't use mantissa calculations"
  https://code4rena.com/reports/2021-06-pooltogether#h-05-idleyieldsource-doesnt-use-mantissa-calculations

- "customPrecisionMultipliers would be rounded to zero and break the pool"
  https://code4rena.com/reports/2021-11-bootfinance#h-07-customprecisionmultipliers-would-be-rounded-to-zero-and-break-the-pool
```

#### L7: Integer Overflow/Underflow (17 bugs)
```
- "Missing overflow check in flashLoan"
  https://code4rena.com/reports/2021-05-nftx#h-01-missing-overflow-check-in-flashloan

- "implicit underflows"
  https://code4rena.com/reports/2021-06-gro#h-01-implicit-underflows
```

### 7.2 Numeric - Multiple Transaction

#### S1-1: AMM Price Oracle Manipulation (15 bugs)
```
- "Price feed can be manipulated"
  https://code4rena.com/reports/2021-04-marginswap#h-03-price-feed-can-be-manipulated

- "Synth realise is vulnerable to flash loan attacks"
  https://code4rena.com/reports/2021-07-spartan#h-05-synth-realise-is-vulnerable-to-flash-loan-attacks
```

#### S1-2: Sandwich Attack (8 bugs)
```
- "Missing slippage checks"
  https://code4rena.com/reports/2021-07-spartan#h-07-missing-slippage-checks

- "treasury is vulnerable to sandwich attack"
  https://code4rena.com/reports/2021-10-mochi#h-09-treasury-is-vulnerable-to-sandwich-attack
```

### 7.3 Access Control (S5-*)

```
- "Anyone can list anchors / curate tokens" (S5-3)
  https://code4rena.com/reports/2021-04-vader#h-10-anyone-can-list-anchors--curate-tokens

- "Anyone can affect deposits of any user and turn the owner of the token" (S5-1)
  https://code4rena.com/reports/2021-06-realitycards#h-04-anyone-can-affect-deposits-of-any-user-and-turn-the-owner-of-the-token
```

### 7.4 State Management (S3-*)

```
- "account.holdsToken is never set" (S3-1 - Missing state update)
  https://code4rena.com/reports/2021-04-marginswap#h-07-accountholdstoken-is-never-set

- "Logic error in burnFlashGovernanceAsset can cause locked assets to be stolen" (S3-2)
  https://code4rena.com/reports/2022-01-behodler#h-04-logic-error-in-burnflashgovernanceasset-can-cause-locked-assets-to-be-stolen
```

---

## 8. Mapping to SolidityGuardian Implementation

### 8.1 Currently Implemented
| Pattern | Example | Implementation |
|---------|---------|----------------|
| Expression-level numeric | `fees.mul(x).div(y)` | Interpreter/Semantics |
| Function argument checking | `transfer(amount.div(4))` | `DuringFunctionArg` in solidity.g4 |

### 8.2 Needs Implementation
| Pattern | Example | Required Work |
|---------|---------|---------------|
| Intra-function state tracking | CoverProtocol memory/storage order | Track state changes across internal function calls |
| Cross-TX state dependency | Flash loan price manipulation | Out of scope for single-TX analysis |

---

## 9. Summary Statistics

### Total In-Scope Bugs for Logic Error Study

| Source | Category | Count |
|--------|----------|-------|
| Web3Bugs | Numeric (L2+L7+S1+S6) | 119 |
| Web3Bugs | Access Control (S5) | 25 |
| Web3Bugs | State Management (S3) | 26 |
| Web3Bugs | Business Flow (S4+SE) | 53 |
| Web3Bugs | SC (needs review) | 65 |
| DeFiHackLabs | Numeric | ~97 |
| DeFiHackLabs | Access Control | ~70 |
| DeFiHackLabs | Logic Flaw | ~109 |

### Numeric Logic Error Breakdown

| TX Scope | Sub-type | Est. Count |
|----------|----------|------------|
| Single | Expression-level (div, mul, precision) | ~50 |
| Single | Function argument errors | ~30 |
| Single | Intra-function state | ~20 |
| Multiple | Price oracle manipulation | ~80 |
| Multiple | Sandwich/Front-running | ~20 |

---

## 10. References

- Web3Bugs Classification Standard: https://github.com/ZhangZhuoSJTU/Web3Bugs/blob/main/docs/standard.md
- DeFiHackLabs: https://github.com/SunWeb3Sec/DeFiHackLabs
- NumScout Paper: "Unveiling Numerical Defects in Smart Contracts Using LLM-Pruning Symbolic Execution"
- LogicRepair Paper: "An Empirical Study on Automated Repair of Smart Contract Logic Vulnerabilities Based on LLMs"
