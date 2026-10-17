# FFIEC 2024 year-end quality check

- Input: `data/ffiec_raw/2024`
- Source SHA-256: `directory input: hash original ZIP separately`
- Input scope: **five core schedules only**
- Parsed reporting institutions (RC-C): **4,543**
- Matched institution profiles: **4,543**
- Positive construction balances: **4,101**
- Positive balances with valid two-letter headquarters jurisdiction: **4,100**
- Headquarters jurisdictions among valid positive-balance institutions: **54**
- Construction balances (source thousands USD): **484,427,049**
- Unfunded commitments (source thousands USD): **not supplied (not zero)**
- Problem loans (source thousands USD): **5,726,202**
- Gross charge-offs (source thousands USD): **347,599**

## Nonmissing coverage

| Measure | Banks |
|---|---:|
| construction_loans | 4,543 |
| pd30 | 4,543 |
| pd90 | 4,543 |
| nonaccrual | 4,543 |
| gross_chargeoffs_ytd | 4,543 |
| unfunded_construction_commitments | 0 |
| total_assets | 4,543 |
| total_loans | 4,543 |
| allowance_total | 0 |
| provision_total_ytd | 0 |

**Limits:** Construction delinquency and nonaccrual are year-end stocks; charge-offs and provisions are year-to-date flows. Allowance and provision here are bank-wide. FFIEC does not report individual loan lifecycle stages. Ratios are undefined where their denominators are missing or zero.
