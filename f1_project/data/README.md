# Data lineage

This directory separates source-granularity data from derived model features.

## `raw/`

These tables are extracted from FastF1 without aggregation, imputation,
encoding, scaling, or model-based changes. FastF1 `Timedelta` values are
serialized as seconds because CSV has no timedelta type.

- `qualifying_results.csv` — one row per driver and qualifying event. Q1/Q2/Q3
  and missing values come from `Session.results`.
- `practice_laps.csv` — one row per FP1/FP2/FP3 lap. It preserves lap/sector
  times, speed traps, compound, tyre life, track status, deletion state, and
  FastF1 accuracy flags.
- `qualifying_weather.csv` — one row per qualifying weather timestamp. It
  preserves temperature, humidity, pressure, rainfall, wind direction, and
  wind speed.

Current raw counts:

| Table | Rows | Columns |
|---|---:|---:|
| Qualifying results | 1,320 | 11 |
| Practice laps | 79,661 | 25 |
| Qualifying weather | 5,777 | 11 |

## `processed/`

`f1_model_features.csv` is created by `data_preparation.py`. The preparation
stage is explicit and reproducible:

1. Remove duplicate driver/event result rows.
2. Derive `QualiTime` from the minimum available Q1/Q2/Q3 time.
3. Remove practice laps without a time/driver, deleted laps, and laps marked
   inaccurate by FastF1.
4. Aggregate the fastest valid FP1/FP2/FP3 lap per driver/event.
5. Aggregate mean qualifying weather per event.
6. Left-join the summaries to qualifying results.

The resulting 1,320 × 15 table intentionally retains missing values. Imputation,
encoding, scaling, feature selection, and train/test splitting happen later in
`preprocessing.py` and are learned from training data only.
