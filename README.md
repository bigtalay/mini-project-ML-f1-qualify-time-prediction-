# F1 Qualifying Time Prediction

End-to-end machine-learning project that uses [FastF1](https://github.com/theOehrly/Fast-F1)
session data to predict a driver's fastest qualifying lap. It includes a
presentation notebook, reproducible data pipeline, two regression baselines,
held-out season evaluation, Streamlit UI, and Docker runtime.

## Dataset stages

The data is separated by processing stage so the notebook shows exactly what
is changed.

### 1. Source-granularity raw data (`f1_project/data/raw/`)

- `qualifying_results.csv`: 1,320 driver/event result rows with Q1/Q2/Q3.
- `practice_laps.csv`: 79,661 individual FP1/FP2/FP3 lap rows, including
  sectors, speeds, tyres, deletion flags, and accuracy flags.
- `qualifying_weather.csv`: 5,777 individual weather timestamp rows.

No aggregation, imputation, encoding, or feature selection happens here.
FastF1 timedeltas are serialized as seconds so they can be stored in CSV.

### 2. Prepared features (`f1_project/data/processed/`)

`f1_model_features.csv` is built by `data_preparation.py`. This stage removes
unusable practice laps, derives `QualiTime`, finds each driver's fastest valid
practice lap, averages qualifying weather per event, and joins the three raw
tables. Missing values are preserved for the ML preprocessing stage.

FastF1's `f1_cache/` is not the dataset and is not committed. It stores large
API responses and lap timing data so collection can resume without downloading
completed sessions again.

## Quick start with Docker

Requirements: Docker Desktop, or Docker Engine with Compose.

Build, prepare the committed raw data, and train:

```powershell
docker compose build
docker compose run --rm --entrypoint python pipeline data_preparation.py
docker compose run --rm --entrypoint python pipeline modeling.py
docker compose up -d
```

- JupyterLab: <http://localhost:8888>
- Prediction app: <http://localhost:8501>

Stop both services:

```powershell
docker compose down
```

To download the source data again and retrain everything:

```powershell
docker compose run --rm pipeline
```

FastF1 enforces a per-process request limit. If collection reports that the
limit was reached, run the same command again. Every completed event is saved
to its season CSV and skipped on the next run.

## ML workflow

1. Extract separate raw qualifying-result, practice-lap, and weather tables.
2. Remove unusable practice laps and aggregate raw data into modeling features.
3. Remove exact duplicates and invalid/missing target rows.
4. Split chronologically: 2021-2022 train, 2023 test.
5. Median-impute numeric practice/weather features using train values only.
6. Apply out-of-fold smoothed target encoding to Driver and Circuit.
7. One-hot encode Team and safely ignore unseen inference categories.
8. Standard-scale numeric and target-encoded features.
9. Select the 15 strongest training features with `f_regression`.
10. Train Linear Regression and Random Forest Regressor.
11. Compare MAE, MSE, RMSE, and R² on the untouched 2023 season.
12. Save the best model and preprocessing objects for Streamlit inference.

With the committed dataset, the latest verified run selected Linear Regression
with MAE 3.226 seconds, RMSE 5.200 seconds, and R² 0.784 on 2023. Results are
recreated by the modeling command rather than committing binary model files.
