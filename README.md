# Construction and Land-Development Credit Quality in U.S. Banks

Reproducible research package for the white paper *Construction and Land-Development Credit Quality in U.S. Banks: Public-Data Evidence and a Project-Lifecycle Research Design* (Fatima Abiodun Bankole, October 2026).

The paper uses public bank data to document how construction and land-development credit quality moved in 2021-2025 (FFIEC Call Reports) and 2012-2025 (FDIC BankFind), tests whether simple bank-level models can beat a persistence benchmark, and specifies a testable project-lifecycle research design.

## What is in this repository

- `prepare_ffiec_bank_year.py`, `summarize_ffiec_panel.py`, `prepare_ffiec_macro_context.py`: build the FFIEC bank-year panel and macro context.
- `prepare_fdic_historical.py`, `prepare_fdic_macro.py`: build the FDIC 2012-2025 panel from the official API responses.
- `analyze_ffiec_credit_risk.py`, `analyze_ffiec_followon.py`, `analyze_ffiec_rolling.py`, `analyze_ffiec_subcategory_panel.py`: FFIEC fixed-effects models, sensitivity checks, and rolling holdouts.
- `analyze_fdic_historical.py`, `analyze_fdic_subcategories.py`: FDIC fixed-effects models and eight rolling holdouts (2018-2025).
- `crosscheck_fdic_ffiec.py`: bank-by-bank reconciliation of the two sources.
- `plot_ffiec_followon.py`, `plot_fdic_historical.py`: figures.
- `verify_extended_analysis.py`: source-hash and output integrity checks.
- `lifecycle_framework.py`: an uncalibrated interface for the PD x LGD x EAD arithmetic. It contains no fitted parameters and is not a validated model.
- `reproduce_all.py`: runs every step above in order and then the unit tests.
- `tests/`: unit tests.
- `data/`: source manifests (with SHA-256 hashes), cached FDIC API responses, and derived results.

## How to run

1. Install Python 3.12 or later.
2. Install the requirements: `pip install -r requirements.txt`
3. Download the raw FFIEC files (see below) into `data/ffiec_raw/<year>/`.
4. Run: `python reproduce_all.py`

The runner first checks every source file against the SHA-256 hash in `data/ffiec_source_manifest.csv` and stops if a file is missing or changed. It then rebuilds the panels, estimates the models, creates the figures, runs the integrity checks and unit tests, and writes step logs to `logs/`.

## Where to get the raw data

- **FFIEC Call Reports:** the "Single Period" bulk download from the FFIEC Central Data Repository, https://cdr.ffiec.gov/public/pws/downloadbulkdata.aspx. Download the December 2021, 2022, 2023, 2024 and 2025 packages and unzip them into `data/ffiec_raw/<year>/`. File names and hashes are listed in `data/ffiec_source_manifest.csv`.
- **FDIC BankFind:** original API responses for each year-end are saved in `data/fdic_historical_raw/` with hashes in the manifest. They can be re-pulled from https://api.fdic.gov/banks/docs.
- **Macro series:** the Federal Reserve, BLS, Census/HUD and FHFA series are obtained through FRED (https://fred.stlouisfed.org); the retrieved files and hashes are stored in the data folder.

## Scope and limits

- Public data only. No private bank, employer, or borrower records are included.
- Domestic-office (RCON) fields are used for construction balances and credit-quality amounts.
- The statistical results are exploratory associations, not causal estimates, and public filings do not identify project stages. The paper explains these limits in full.
- Historical series downloaded today can differ from what was available at the time, so the holdout results are not real-time forecasts.

## How to cite

See `CITATION.cff`. Please cite the archived release (DOI on Zenodo) and the paper.

## License

MIT License. See `LICENSE`. The views expressed are the author's own.
