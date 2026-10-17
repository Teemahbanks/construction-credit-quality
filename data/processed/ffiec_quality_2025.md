# FFIEC 2025 year-end quality check

- Input: `data/ffiec_raw/2025`
- Source SHA-256: `directory input: hash original ZIP separately`
- Input scope: **five core schedules only**
- Parsed reporting institutions (RC-C): **4,394**
- Matched institution profiles: **4,394**
- Positive construction balances: **3,969**
- Positive balances with valid two-letter headquarters jurisdiction: **3,968**
- Headquarters jurisdictions among valid positive-balance institutions: **54**
- Construction balances (source thousands USD): **456,067,907**
- Unfunded commitments (source thousands USD): **not supplied (not zero)**
- Problem loans (source thousands USD): **6,103,112**
- Gross charge-offs (source thousands USD): **461,829**

## Nonmissing coverage

| Measure | Banks |
|---|---:|
| construction_loans | 4,394 |
| pd30 | 4,394 |
| pd90 | 4,394 |
| nonaccrual | 4,394 |
| gross_chargeoffs_ytd | 4,394 |
| unfunded_construction_commitments | 0 |
| total_assets | 4,394 |
| total_loans | 4,394 |
| allowance_total | 0 |
| provision_total_ytd | 0 |

**Limits:** Construction delinquency and nonaccrual are year-end stocks; charge-offs and provisions are year-to-date flows. Allowance and provision here are bank-wide. FFIEC does not report individual loan lifecycle stages. Ratios are undefined where their denominators are missing or zero.
