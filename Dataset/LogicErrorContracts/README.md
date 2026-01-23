# Logic Error Contracts Dataset

This dataset contains real-world vulnerable smart contracts extracted from the sc-defi-security repository (Chaliasos et al., ICSE 2024).

## Source
- Paper: "Smart Contract and DeFi Security Tools: Do They Meet the Needs of Practitioners?"
- Repository: https://github.com/StefanosChaliasos/sc-defi-security
- Original Data: Zhou et al. SoK (IEEE S&P 2023)

## Categories

| Category | Count | Description |
|----------|-------|-------------|
| Absence_of_code_logic_or_sanity_check | 37 | Missing validation logic (require/assert) |
| Arithmetic_mistakes | 5 | Calculation errors, precision issues |
| Other_coding_mistakes | 3 | General coding bugs |
| Liquidity_borrow,_purchase,_mint,_deposit | 11 | DeFi liquidity manipulation |
| Unfair_slippage_protection | 3 | Invalid slippage control |
| Unfair_liquidity_providing | 3 | LP token manipulation |
| Other_unfair_or_unsafe_DeFi_protocol_interaction | 1 | Unsafe protocol interactions |
| Other_protocol_vulnerabilities | 2 | Other protocol-level bugs |

**Total: 65 contracts**

## File Naming Convention
```
{incident_date}_{project}_{type}_{contract_name}_{address_prefix}.sol
```

Example: `20210213_CreamFinance_CSR_HomoraBankv2_0x33bf0bb8.sol`

## Single Transaction vs Multiple Transaction

For SolIntentKeeper research, focus on:

### Single Transaction (Intent Model Target)
- **Arithmetic_mistakes**: Overflow, underflow, precision loss
- **Absence_of_code_logic_or_sanity_check**: Missing require/assert (some cases)
- **Other_coding_mistakes**: General logic bugs

### Multiple Transaction (Out of Scope)
- **Liquidity_borrow,_purchase,_mint,_deposit**: Flash loan based
- **Unfair_slippage_protection**: Cross-transaction manipulation
- **Unfair_liquidity_providing**: LP manipulation across txs

## Mapping to Intent Model

| Logic Error Type | Intent Expression |
|------------------|-------------------|
| Overflow check | `@During x(Before < After)` |
| Underflow check | `@During x(Before >= After)` |
| Percentage calculation | `PercentOf(value, percent)` |
| Balance invariant | `@Post x(Entry relOp Exit)` |
| State unchanged | `@Post Unchanged(var)` |
