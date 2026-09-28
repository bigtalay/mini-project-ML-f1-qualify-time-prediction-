# Verification record

## Practice + tyres — 28 September 2026

Verified on branch `docker`, with the new model in `intelligence/tyre_model.py` and the explanatory `f1_practice_tyres.ipynb`. The older evidence below describes the historical identity-based model, not the current deployment.

| Check | Result |
|---|---|
| Python/API suite | 14 passed in the production Docker image |
| Source lap provenance | Time, compound and tyre age match the same eligible source lap; equal times choose the earliest source row |
| Missing inputs | Whole-session triple copy, age median/pool fallback, UNKNOWN compound, no-Practice rejection and invalid manual inputs checked |
| Training isolation | Instrumented fitting confirms only 2021 and then 2021 + validation are fitted; calibration/2023 are excluded |
| Model selection | Each feature-set winner equals the lowest validation RMSE; tyre winner is deployed regardless of 2023 ranking |
| Notebook | 53 cells (28 code cells) executed with tables/graphs, zero cell errors |
| FastF1 demonstration | Bahrain 2023 load succeeded using available cache; exported/re-read 1,246 raw Practice rows, 177,781 bytes; separate from committed raw |
| Offline notebook | Run All with `F1_OFFLINE=1` succeeded; live sample skipped explicitly |
| Parity | Independent notebook features and all four configurations agree with production; notebook saved/reloaded estimator and custom HTTP API agree within 1e-8 |
| Data integrity | All original normalized raw hashes unchanged; old notebook byte SHA-256 remained `B2EE56F097E03A990283F7FB25EA5AAE37454F0EF420AC1F4E9B5614C6C64019` |
| Build/startup | TypeScript check, production build and `docker compose up --build -d` succeeded; app healthy on 8501 |
| Fresh offline artifacts | A network-disabled disposable container trained from bundled snapshot into an empty directory; repeat call reused the exact bundle mtime |
| Legacy | Streamlit AppTest loaded the tyre model and executed a prediction without exceptions |
| Browser | 14 passed, covering desktop/mobile manual/history modes, time parsing, tyres, missing sessions, invalid input, source-lap links, export, URL refresh, keyboard and existing analysis flows |
| Local instructions | AGENTS.md updated and remains ignored; existing old-notebook edits and unrelated tmp/ preserved |

No dependencies were added; the existing Python and npm lockfiles remain authoritative. OpenAPI and TypeScript types were regenerated. React checks informed request cancellation, labelled native controls and clear empty/error states; browser screenshots were inspected on both viewports. The optional three-year redownload/resume path and actual Google Colab runtime were not exercised end-to-end; normal training uses the supplied immutable snapshot.

### Reproduced model results

| Configuration | Validation RMSE (s) | 2023 MAE (s) | 2023 RMSE (s) |
|---|---:|---:|---:|
| Practice baseline | 7.089 | 2.247 | 4.433 |
| Time / Linear Regression — selected | 5.752 | 2.385 | 4.915 |
| Time / Random Forest | 6.764 | 2.218 | 4.133 |
| Time + tyres / Linear Regression — deployed | 4.993 | 1.865 | 3.360 |
| Time + tyres / Random Forest | 7.943 | 1.808 | 3.693 |

Eligible row counts: training 432, validation 216, calibration 220, retrospective 2023 evaluation 431. All four configurations use identical partitions/rows. The selected time-only algorithm loses to baseline in 2023; it is not silently replaced with the better 2023 Random Forest. No team/driver/circuit/year/weather/qualifying-result columns enter X.

Calibration residual percentiles are −20.077 and +7.181 seconds. Coverage in 2023 is 99.1%, but interval width is 27.257 seconds: this is **not 99.1% prediction accuracy**. Per-event and complete/missing-session, dry/wet/unknown-tyre metrics are available in the notebook, evaluation artifact and API/UI. 2023 has previously been inspected and is explicitly labelled retrospective, not untouched.

### Local performance sample

Warm production Docker server on localhost:8501, Chromium 153.0.8010.12, Windows 11, Intel i5-13500HX (20 logical processors), 16 GiB host RAM, Docker Engine 29.1.3 Linux. No throttling. Mobile is emulation, not physical hardware. Initial image download/model preparation is excluded.

| Viewport | Table + chart ready | Maximum of 10 filtered-lap API responses |
|---|---:|---:|
| Desktop 1440 × 1000 | 358 ms | 43.5 ms |
| Mobile 390 × 844 | 353 ms | 30.6 ms |

Measurements and screenshots are regenerated under ignored `frontend/test-results/` by `npm run test:e2e`. This is a local sample, not a load-test SLA. The existing ECharts chunk still emits a non-failing >500 kB build warning.

## Historical verification — identity-based model

Local verification: 23 September 2026 (Asia/Bangkok). Runtime source: `47b6b99`.

## Functional checks

| Check | Result |
|---|---|
| Python/API suite | 9 passed through the Docker test service |
| Event coverage | All 66 event overview responses validated |
| Data integrity | All three normalized raw SHA-256 checksums unchanged |
| Cleaning audit | Sequential removal totals reconcile with source and kept counts |
| Prediction timing | British GP 2021 post-qualifying FP2 excluded; every aggregate matches eligible source laps |
| ML isolation | Selection/calibration/test event sets disjoint; encoding folds keep complete events apart |
| Scenario checks | Historical 2023 inputs, reset, unknown category fallback, invalid/absent practice inputs |
| CSV export | Filtered lap IDs/counts match the API and comparison calculations |
| Browser suite | 12 passed: 6 flows on desktop and mobile layouts |
| Notebook | All cells executed in Docker with nbconvert; output written to a temporary notebook |
| Offline preparation | Fresh `docker run --rm --network none ... python -m intelligence.prepare` succeeded |
| Artifact reuse | Unchanged versions reuse the bundle without changing its modification time |
| Legacy view | Streamlit AppTest loaded the app and executed its prediction action without exceptions |
| HTTP | App health, Jupyter and legacy endpoints returned 200 |
| Frontend | TypeScript check and production build passed; OpenAPI types generated |
| Fresh clone | Runtime commit cloned to a temporary folder without ignored files; `docker compose -p f1-clean-check up --build -d` created a new artifact volume and a healthy app; all 12 browser tests also passed against this instance |

The browser suite covers event selection, comparison, actual-lap inspection through the table, filter persistence after reload, CSV download, what-if validation/reset, sprint/rain/missing-data states, failed-request retry, keyboard selection and horizontal overflow. Desktop/mobile screenshots were inspected; visual inspection also led to limiting the ranking pane height and distinguishing teammates by symbols/dashed lines.

## Performance

Measured with a warm application server, new Playwright browser contexts, localhost networking and no CPU/network throttling. Readiness waits for the initial lap table and chart canvas, not just an HTTP 200. Each API column below is the maximum of 10 full response measurements for the filtered lap endpoint.

| Browser viewport | Page ready | Slowest sampled API response |
|---|---:|---:|
| Desktop 1440 × 1000 | 537 ms | 26.4 ms |
| Mobile layout 390 × 844 | 402 ms | 19.5 ms |

Environment: Windows host, Intel Core i5-13500HX (20 logical processors), Docker Linux x86_64 with 20 CPUs / approximately 7.6 GiB RAM, Chromium 153.0.8010.12. Mobile is a viewport/touch emulation on the same host, not a physical phone benchmark. Docker image downloads/build time and initial model preparation are excluded from page readiness.

Reproduce with `npm run test:e2e` in `frontend/`. Per-run JSON measurements and screenshots are written to ignored `frontend/test-results/`; CI uploads that directory. These are local observations, not a throughput or public-hosting SLA.

## Model evidence and limitations

The selected Random Forest has 2023 RMSE 6.763 seconds versus 4.433 for the practice baseline. Selection was performed on 2022 rounds 1–11, not on the 2023 test. This underperformance is displayed in the UI. The historical residual interval covers 82.4% of evaluated 2023 targets, not a guaranteed 90%.

No live telemetry, fuel/setup inference, causal effect claims, authentication or public deployment is included in this release. Session cutoff uses FastF1's reported SessionInfo boundaries. All source and API limitations are also explained in the Data & Method page and notebook.
# Final Notebook web integration — 2026-09-28

- Active backend loads `data/final/models/qualifying.joblib` (SVR, C=100, epsilon=0.5) without fitting. Existing Weekend/Compare use the final raw/audit snapshot. Raw checksums verified on startup.
- `python -m unittest tests.test_final_web -q`: passed in Docker. Checked all 66 event overview/lap/prediction endpoints; saved 2023 predictions match artifact; custom/scenario predictions for Belgian GP match; invalid inputs return 422; export/evaluation/quality respond successfully.
- `npm run schema`, `npm run lint`, `npm run build`, Compose configuration and `docker compose up --build -d app`: passed. Existing large chart bundle warning remains.
- Playwright Chromium: history inputs, manual FP1=1:30.000/SOFT/3 → 1:28.887; missing FP2/FP3 provenance shown. Invalid time `abc` shows validation message (expected HTTP 422). Checked 390×844 mobile and 1440×1000 desktop. Screenshots in `output/playwright/final-model-*.png`.
- Model report recomputed from loaded artifact: 431 rows, MAE 2.372987 / RMSE 4.957968 seconds; baseline MAE 2.246914 / RMSE 4.433238. No calibration interval exists for this notebook; API returns null and UI does not reuse old intervals.
- Prior verification entries below describe earlier model versions, not the active notebook model.
# Practice + circuit model — 2026-09-28

- Replaced tyre features with exactly FP1_Time, FP2_Time, FP3_Time, circuit_length_km, corner_count in final.ipynb and the web. F1DB snapshot covers all 66 events with historical layout IDs, pinned source URLs and CC BY 4.0 attribution.
- Notebook Run All passed with existing snapshots; no FastF1 download needed. Raw files and per-event completion checksums unchanged (git diff and notebook hash assertion).
- Four-model training/tuning uses 2021 training and 2022 validation only; selected SVR(C=100, epsilon=0.1, gamma=0.01). Refit 2021–2022. Retrospective 2023: 431 rows, MAE 1.555394, RMSE 3.254304 seconds. Baseline: MAE 2.246914, RMSE 4.433238. 2023 is not an untouched holdout.
- New artifact: models/qualifying-circuit.joblib, version practice-circuit-v1. Old qualifying.joblib is historical only. API checks raw/circuit hashes and rejects tyre input and unknown event IDs.
- Python notebook/snapshot/API checks: 4 passed. Notebook saved predictions, artifact and custom API match; Barcelona/Singapore layout changes covered. Schema generation, lint, production build and Docker startup passed.
- Existing Playwright E2E suite updated for circuit inputs: 14 passed across desktop/mobile, including input validation, source laps, exports, URL state, and timing thresholds. CLI screenshots inspected at 390×844 and 1440×1000 under output/playwright/circuit-model-*.png. Existing favicon 404 and chart bundle-size warning remain unrelated limitations.
