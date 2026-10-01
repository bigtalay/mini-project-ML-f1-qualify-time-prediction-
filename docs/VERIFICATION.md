# Final release verification

Verified locally on branch `docker`, 1 October 2026 (Asia/Bangkok). This document describes `final.ipynb` and the deployed practice-time + circuit model only.

## Model and source contract

- Exactly five X columns: FP1_Time, FP2_Time, FP3_Time, circuit_length_km, corner_count. Target: minimum positive Q1/Q2/Q3 in seconds.
- Train 2021 (432 rows), select/tune on all 2022 (436), refit on 2021–2022 (868), retrospectively evaluate 2023 (431). No 2023 model selection; no calibration/Prediction Interval.
- Deployed pipeline: SVR(RBF, C=100, epsilon=0.1, gamma=0.01), saved at `data/final/models/qualifying-circuit.joblib`. Web startup loads and checks this artifact; it never trains or contacts FastF1.
- 2023 model MAE/RMSE: **1.555394 / 3.254304 s**. Best-practice baseline: **2.246914 / 4.433238 s**. API reports recompute predictions from the loaded artifact, not a different model's score CSV.
- Four aggregate raw CSVs and their per-event completion markers remain unchanged. Circuit CSV is byte-identical after generation from original sources; model features/results have not changed.

## Reproducible circuit matching

Notebook 2.8.1–2.8.3 uses pinned original F1DB YAMLs, Grand Prix-name references and directory indexes. The source manifest records each URL and SHA256; matching uses year/normalized Grand Prix name, exact official-name fallback and independent local/UTC date verification.

All 66 events match: 61 by Grand Prix name + local date; 3 by official name + local date (Mexico); 1 by Grand Prix name + UTC date (Las Vegas); 1 explicitly documented source-date discrepancy (Turkey 2021). The audit retains both source names, dates, URLs and hashes. No positional round-number or manually assumed event-id/circuit mapping.

Tests regenerate a deleted circuits.csv offline; changed source round numbers do not change the mapping. Unmatched/ambiguous names, unexplained dates and corrupted cached source bytes fail explicitly.

## Executed checks

| Check | Evidence |
|---|---|
| Python / API / notebook logic | `python -m unittest discover -s tests -v`: 10 tests passed against the final code |
| Snapshot download step | All 66 events skipped with no network calls or FastF1 cache requirement |
| Data quality | Sequential removals reconcile with 79,661 raw laps and 47,754 kept pre-Q laps; overlapping flags retained |
| Leakage / preprocessing | Sprint post-Q practice excluded; partition event sets disjoint; saved scaler mean equals 2021–2022 X only |
| Inference parity | Notebook saved predictions, joblib and custom/history API agree; time parsing, missing/invalid inputs and geometry coverage checked |
| Frontend | `npm run lint`, `npm run build`: passed |
| Docker | Build/startup passed; app healthy on 8501 and Jupyter available on 8888; preparation validates the saved model |
| Browser | 14 tests passed on desktop and mobile in the production UI (19.9 s) |
| UI inspection | Actual 1440×1000 and 390×844 viewports inspected; form precedes historical tables, FP1 visible on initial viewport |
| Release layout | One project notebook, one deployed model; no obsolete runtime entry points |
| Source integrity | `git diff` reports no raw or circuit snapshot changes; loader verifies byte-level SHA256 |
| Clean clone / offline | Local clone of `457f207`, no FastF1 cache: full Notebook execution and 10 tests passed in network-disabled containers |

Clean-clone verification binds only the cloned `f1_project/` into the production image. Full Notebook execution writes its output to `/tmp/verified-final.ipynb`; raw, circuit CSV and saved SVR bytes remain unchanged. Random Forest validation scores may differ at floating-point rounding precision across threaded runs without changing the chosen model.

The browser suite exercises manual button/Enter submission, clearing stale results after edits, API parity, missing/invalid/out-of-range inputs, historical What-if/reset, source-lap links, CSV, URL refresh, retry, keyboard navigation, sprint/rain/missing-session states and horizontal overflow.

The existing ECharts bundle is approximately 581 kB and emits a non-failing chunk-size warning. FastAPI TestClient emits an upstream deprecation warning for the locked HTTP client; tests pass. Neither warning is suppressed.
The browser also requests an absent favicon (404); the application/API interactions themselves pass.

## Repeat locally

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose run --rm test
docker compose run --rm jupyter jupyter nbconvert --to notebook --execute final.ipynb --output /tmp/verified-final.ipynb --ExecutePreprocessor.timeout=600
cd frontend
npm ci
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

Full Notebook execution regenerates processed files and the saved model, leaving complete raw unchanged. The output notebook in this command is temporary, not another project notebook. GitHub Actions repeats these checks after push.

## Performance and boundaries

Browser checks assert prediction-input readiness below 3 s and ten warm lap API reads below 500 ms each. Per-run actual measurements and screenshots are stored in ignored `frontend/test-results/`; these local checks are not a public-hosting or throughput SLA.

| Viewport | Input-ready time | Maximum of 10 warm API reads |
|---|---:|---:|
| Desktop 1440 × 1000 | 216.5 ms | 14.4 ms |
| Mobile-emulated 390 × 844 | 321.9 ms | 19.4 ms |

Environment: Windows 11, Intel i5-13500HX (20 logical processors), 16 GiB RAM; Docker Engine 29.1.3 Linux; Chromium, desktop 1440×1000 and mobile-emulated 390×844. No network/CPU throttling. Image downloads/builds are excluded from readiness. Mobile is emulation, not a physical device test.

No live timing, continuous telemetry, account system, public hosting, causal claim or guaranteed future-season accuracy is included. Missing weather/fuel/setup/run-plan inputs limit forecasts under changing conditions.
