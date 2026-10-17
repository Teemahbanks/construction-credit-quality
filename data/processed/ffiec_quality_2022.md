# FFIEC 2022 year-end quality check

- Input: `data/ffiec_raw/2022`
- Source SHA-256: `directory input: hash original ZIP separately`
- Input scope: **five core schedules only**
- Parsed reporting institutions (RC-C): **4,756**
- Matched institution profiles: **4,756**
- Positive construction balances: **4,294**
- Positive balances with valid two-letter headquarters jurisdiction: **4,293**
- Headquarters jurisdictions among valid positive-balance institutions: **54**
- Construction balances (source thousands USD): **465,623,836**
- Unfunded commitments (source thousands USD): **not supplied (not zero)**
- Problem loans (source thousands USD): **3,165,986**
- Gross charge-offs (source thousands USD): **78,965**

## Nonmissing coverage

| Measure | Banks |
|---|---:|
| construction_loans | 4,756 |
| pd30 | 4,756 |
| pd90 | 4,756 |
| nonaccrual | 4,756 |
| gross_chargeoffs_ytd | 4,756 |
| unfunded_construction_commitments | 0 |
| total_assets | 4,756 |
| total_loans | 4,756 |
| allowance_total | 0 |
| provision_total_ytd | 0 |

**Limits:** Construction delinquency and nonaccrual are year-end stocks; charge-offs and provisions are year-to-date flows. Allowance and provision here are bank-wide. FFIEC does not report individual loan lifecycle stages. Ratios are undefined where their denominators are missing or zero.
