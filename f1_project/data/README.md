# Data lineage / 2021–2023.v1

## Source tables

| File | Rows | Granularity |
|---|---:|---|
| raw/qualifying_results.csv | 1,320 | Driver / qualifying event |
| raw/practice_laps.csv | 79,661 | Individual FP1/FP2/FP3 lap |
| raw/qualifying_weather.csv | 5,777 | Qualifying weather timestamp |

These are selected FastF1 columns, not the complete original timing feeds. FastF1 itself parses, merges and sometimes generates records; the export retains `FastF1Generated` and quality flags. Timedeltas are serialized in seconds, columns are renamed where documented in `data_collection.py`, and Year/Circuit identify the event. No imputation or aggregation is performed in these source CSVs.

The original `Circuit` column contains a Grand Prix name. `reference/events.csv` maps Year + event name to `event_id` (year/round) and the separate FastF1 circuit key/name. `reference/sessions.csv` records UTC StartDate/EndDate reported by FastF1 SessionInfo, provenance path and source. These are source-reported session boundaries, not independently measured completion times.

`reference/manifest.json` stores the dataset version and SHA-256 hashes after normalizing CRLF to LF. Startup refuses a checksum mismatch. Raw files are never rewritten by analysis, training, exports, Notebook Run All or application startup.

## Sequential cleaning and cutoff

`intelligence.data.clean_laps` preserves `source_row` (CSV line, header is line 1) and `lap_id`. The first matching rule becomes `reason`; all independent flags are retained for auditing.

| Step | Removed at this step | Remaining |
|---|---:|---:|
| Source | — | 79,661 |
| Exact duplicate | 0 | 79,661 |
| Missing lap time / driver | 14,734 | 64,927 |
| Non-positive time | 0 | 64,927 |
| Deleted | 0 | 64,927 |
| Inaccurate | 13,914 | 51,013 |
| FastF1-generated | 0 additional | 51,013 |
| Not verified to end before qualifying | 2,685 | 48,328 |

There are 28,648 inaccurate flags and 16 generated flags in total, but those overlap with earlier removals. Do not sum the flag counts. Unknown accuracy/deletion flags are preserved as unknown source values; they are not fabricated as source assertions.

The 51,013 usable laps are available for historical analysis. Only the 48,328 pre-qualifying laps can contribute to predictive features. Example: British GP 2021 FP2 occurred after qualifying and must not be used to predict it.

## Prepared features

`intelligence.data.Dataset` creates one row per driver/event, minimum valid positive Q1/Q2/Q3 as target and the fastest usable pre-qualifying lap in each Practice. Missing values remain missing. Qualifying weather is available for retrospective display only.

`processed/f1_model_features.csv` is the human-readable snapshot exported by `python data_preparation.py`. It includes source/metadata columns for auditing, but the model explicitly selects only FP1/FP2/FP3 times, Year, Driver, circuit_id and Team. The app derives features from raw/reference tables instead of trusting a stale processed snapshot.

The feature table contains 1,320 rows; 16 have no valid target, 5 have no usable pre-qualifying practice. These counts may overlap. Eligibility requires both a valid target and at least one practice time. Missing targets are never imputed.

Imputation, grouped target encoding, scaling and feature selection are learned only inside each training partition; see `intelligence/ml.py`. Artifacts (including lap audit, metrics, predictions and model) are generated outside Git under `artifacts/intelligence/`, or in the Docker artifacts volume.

## Maintenance

Normal usage needs no network. To deliberately recollect, run `data_collection.py` with a separate output directory, then `python -m intelligence.metadata --cache <cache-dir> --data <data-dir>` against that dataset. Review source counts and metadata before replacing committed data, update the dataset version/manifest, regenerate processed data and retrain. The metadata collector uses FastF1 3.8.3's SessionInfo adapter, so dependency upgrades require verifying that interface.
