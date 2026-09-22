# Implementation record

The work continues on `docker`. The temporary `feature/weekend-intelligence` branch/worktree was removed at the owner's request after its complete tree had been preserved on `docker`.

## 1. Preserve source data and session reference

`7df09d4` separates the former aggregated “raw” dataset into three source-granularity CSVs, preserves the notebook preparation baseline, and adds offline event/session metadata plus normalized SHA-256 source checksums. No source lap or weather measurement was invented.

## 2. Make analysis and evaluation auditable

`a24183d` introduces a shared Python data/ML engine. Sequential removal counts reconcile; independent flags retain overlaps. It separates event identity from circuit identity, excludes practice after qualifying, and partitions model training, selection, calibration and test. Unit tests cover source immutability, sprint timing, grouped encoding and artifact reuse.

## 3. Expose the engine through a typed API

`eec8173` adds the FastAPI contract, pagination, filtered CSV export, per-event metrics and guarded scenarios. API tests cover every event, missing sessions, invalid inputs and CSV/analysis consistency. Python dependency versions are locked.

## 4. Replace the prediction form with the analysis workspace (`09e7f4e`)

The React frontend adds Weekend, Compare, Prediction and Data & Method. Shared URL state, actual-lap inspection, session/compound filters, consistent export, keyboard controls and responsive layouts are wired to the real API. Graphs distinguish teammates using symbols and line styles. OpenAPI generates TypeScript types.

## 5. Unify the notebook, runtime and compatibility commands (`47b6b99`)

The notebook and former Python entry points now use the same engine. Production frontend assets and the API share one Docker image and origin. A preparation service creates versioned artifacts offline in a persistent volume before the app starts. Jupyter and the legacy Streamlit view are optional profiles. The previous default that redownloaded data during the ordinary pipeline is removed.

## 6. Verify and document the release

Browser tests exercise desktop/mobile flows, error recovery, CSV downloads, persistence, input validation and performance. CI repeats backend tests, notebook execution and browser checks. README documents fresh-clone startup, model limitations and maintenance. `VERIFICATION.md` records measured results and their environment.

## Why the model results changed

The former report used qualifying weather, allowed practice sessions after qualifying, and selected a model with test scores. The current results use only pre-qualifying inputs and select a model on the 2022 validation split. The older and newer reported errors are therefore not directly comparable.

Random Forest wins selection but loses to the practice baseline in the untouched 2023 test. This is retained and displayed instead of switching the model using test data. This release is a usable historical analysis tool, not a claim of production-grade forecasting accuracy for future seasons.
