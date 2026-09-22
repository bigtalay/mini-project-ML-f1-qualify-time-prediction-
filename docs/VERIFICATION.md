# Verification record

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
