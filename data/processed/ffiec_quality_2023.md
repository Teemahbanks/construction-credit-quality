# FFIEC 2023 year-end quality check

- Input: `data/ffiec_raw/2023`
- Source SHA-256: `directory input: hash original ZIP separately`
- Input scope: **five core schedules only**
- Parsed reporting institutions (RC-C): **4,641**
- Matched institution profiles: **4,641**
- Positive construction balances: **4,184**
- Positive balances with valid two-letter headquarters jurisdiction: **4,183**
- Headquarters jurisdictions among valid positive-balance institutions: **54**
- Construction balances (source thousands USD): **500,409,076**
- Unfunded commitments (source thousands USD): **not supplied (not zero)**
- Problem loans (source thousands USD): **4,240,212**
- Gross charge-offs (source thousands USD): **277,778**

## Nonmissing coverage

| Measure | Banks |
|---|---:|
| construction_loans | 4,641 |
| pd30 | 4,641 |
| pd90 | 4,641 |
| nonaccrual | 4,641 |
| gross_chargeoffs_ytd | 4,641 |
| unfunded_construction_commitments | 0 |
| total_assets | 4,641 |
| total_loans | 4,641 |
| allowance_total | 0 |
| provision_total_ytd | 0 |

**Limits:** Construction delinquency and nonaccrual are year-end stocks; charge-offs and provisions are year-to-date flows. Allowance and provision here are bank-wide. FFIEC does not report individual loan lifecycle stages. Ratios are undefined where their denominators are missing or zero.
