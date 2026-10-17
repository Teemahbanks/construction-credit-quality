# FFIEC 2021 year-end quality check

- Input: `data/ffiec_raw/2021`
- Source SHA-256: `directory input: hash original ZIP separately`
- Input scope: **five core schedules only**
- Parsed reporting institutions (RC-C): **4,887**
- Matched institution profiles: **4,887**
- Positive construction balances: **4,396**
- Positive balances with valid two-letter headquarters jurisdiction: **4,395**
- Headquarters jurisdictions among valid positive-balance institutions: **54**
- Construction balances (source thousands USD): **401,538,445**
- Unfunded commitments (source thousands USD): **not supplied (not zero)**
- Problem loans (source thousands USD): **3,259,596**
- Gross charge-offs (source thousands USD): **203,753**

## Nonmissing coverage

| Measure | Banks |
|---|---:|
| construction_loans | 4,887 |
| pd30 | 4,887 |
| pd90 | 4,887 |
| nonaccrual | 4,887 |
| gross_chargeoffs_ytd | 4,887 |
| unfunded_construction_commitments | 0 |
| total_assets | 4,887 |
| total_loans | 4,887 |
| allowance_total | 0 |
| provision_total_ytd | 0 |

**Limits:** Construction delinquency and nonaccrual are year-end stocks; charge-offs and provisions are year-to-date flows. Allowance and provision here are bank-wide. FFIEC does not report individual loan lifecycle stages. Ratios are undefined where their denominators are missing or zero.
