"""Turn source-granularity FastF1 tables into one modeling row per driver/event."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


FEATURE_COLUMNS = [
    "Driver",
    "Team",
    "Q1",
    "Q2",
    "Q3",
    "QualiTime",
    "AirTemp",
    "TrackTemp",
    "Humidity",
    "Rainfall",
    "FP1_Time",
    "FP2_Time",
    "FP3_Time",
    "Year",
    "Circuit",
]


def _boolean(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.astype("string").str.lower().isin({"true", "1"})


def prepare_modeling_table(
    raw_dir: str | Path = "data/raw",
    output_path: str | Path = "data/processed/f1_model_features.csv",
) -> tuple[pd.DataFrame, dict]:
    """Clean and aggregate raw tables; retain missing feature values for ML preprocessing."""
    raw_dir = Path(raw_dir)
    output_path = Path(output_path)
    results = pd.read_csv(raw_dir / "qualifying_results.csv")
    laps = pd.read_csv(raw_dir / "practice_laps.csv", low_memory=False)
    weather = pd.read_csv(raw_dir / "qualifying_weather.csv")

    result_duplicates = int(results.duplicated(["Year", "Circuit", "Driver"]).sum())
    results = results.drop_duplicates(["Year", "Circuit", "Driver"], keep="last").copy()
    for column in ("Q1", "Q2", "Q3"):
        results[column] = pd.to_numeric(results[column], errors="coerce")
    results["QualiTime"] = results[["Q1", "Q2", "Q3"]].min(axis=1)

    laps["LapTime"] = pd.to_numeric(laps["LapTime"], errors="coerce")
    invalid_lap = laps["LapTime"].isna() | laps["Driver"].isna()
    deleted_lap = _boolean(laps["Deleted"])
    inaccurate_lap = laps["IsAccurate"].notna() & ~_boolean(laps["IsAccurate"])
    usable_laps = laps.loc[~invalid_lap & ~deleted_lap & ~inaccurate_lap].copy()
    practice_best = (
        usable_laps.groupby(["Year", "Circuit", "Session", "Driver"], observed=True)["LapTime"]
        .min()
        .unstack("Session")
        .rename(columns={"FP1": "FP1_Time", "FP2": "FP2_Time", "FP3": "FP3_Time"})
        .reset_index()
    )
    for column in ("FP1_Time", "FP2_Time", "FP3_Time"):
        if column not in practice_best:
            practice_best[column] = pd.NA

    weather_numeric = ["AirTemp", "TrackTemp", "Humidity", "Rainfall"]
    for column in weather_numeric:
        weather[column] = pd.to_numeric(weather[column], errors="coerce")
    weather_summary = (
        weather.groupby(["Year", "Circuit"], observed=True)[weather_numeric]
        .mean()
        .reset_index()
    )

    modeling = results.merge(weather_summary, on=["Year", "Circuit"], how="left")
    modeling = modeling.merge(
        practice_best[["Year", "Circuit", "Driver", "FP1_Time", "FP2_Time", "FP3_Time"]],
        on=["Year", "Circuit", "Driver"],
        how="left",
    )
    modeling = modeling[FEATURE_COLUMNS].sort_values(["Year", "Circuit", "Driver"]).reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    modeling.to_csv(output_path, index=False)

    report = {
        "raw_result_rows": len(pd.read_csv(raw_dir / "qualifying_results.csv")),
        "raw_lap_rows": len(laps),
        "raw_weather_rows": len(weather),
        "duplicate_result_rows_removed": result_duplicates,
        "laps_without_time_or_driver_removed": int(invalid_lap.sum()),
        "deleted_laps_removed": int(deleted_lap.sum()),
        "inaccurate_laps_removed": int(inaccurate_lap.sum()),
        "usable_lap_rows": len(usable_laps),
        "modeling_rows": len(modeling),
        "modeling_columns": len(modeling.columns),
        "missing_values": modeling.isna().sum().to_dict(),
    }
    print(pd.Series(report).to_string())
    print(f"Prepared modeling table -> {output_path}")
    return modeling, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--output", default="data/processed/f1_model_features.csv")
    args = parser.parse_args()
    prepare_modeling_table(args.raw_dir, args.output)


if __name__ == "__main__":
    main()
