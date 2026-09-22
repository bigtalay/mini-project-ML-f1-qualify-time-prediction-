"""Train and evaluate qualifying-time regression models."""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from preprocessing import prepare_data


def _metrics(y_true, prediction):
    mse = mean_squared_error(y_true, prediction)
    return {
        "MAE": mean_absolute_error(y_true, prediction),
        "MSE": mse,
        "RMSE": np.sqrt(mse),
        "R2": r2_score(y_true, prediction),
    }


def train_models(
    dataset_path: str | Path = "data/processed/f1_model_features.csv",
    artifact_dir: str | Path = "artifacts",
):
    dataset_path = Path(dataset_path)
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(dataset_path)
    prepared = prepare_data(data, test_year=2023, max_features=15)

    models = {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(
            n_estimators=400,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        ),
    }
    rows = []
    predictions = {}
    for name, model in models.items():
        model.fit(prepared.X_train, prepared.y_train)
        prediction = model.predict(prepared.X_test)
        predictions[name] = prediction
        rows.append({"Model": name, **_metrics(prepared.y_test, prediction)})

    metrics = pd.DataFrame(rows).sort_values("RMSE").reset_index(drop=True)
    best_name = str(metrics.iloc[0]["Model"])
    best_model = models[best_name]
    reference = {
        "categories": {
            column: sorted(data[column].dropna().astype(str).unique().tolist())
            for column in ("Driver", "Team", "Circuit")
        },
        "numeric_defaults": {
            column: float(pd.to_numeric(data[column], errors="coerce").median())
            for column in ("AirTemp", "TrackTemp", "Humidity", "Rainfall", "FP1_Time", "FP2_Time", "FP3_Time")
        },
        "years": sorted(pd.to_numeric(data["Year"], errors="coerce").dropna().astype(int).unique().tolist()),
    }
    bundle = {
        "model_name": best_name,
        "model": best_model,
        "preprocessing": prepared.artifacts,
        "selected_features": prepared.X_train.columns.tolist(),
        "metrics": metrics,
        "split_description": prepared.split_description,
        "reference": reference,
    }
    joblib.dump(bundle, artifact_dir / "model_bundle.joblib")
    metrics.to_csv(artifact_dir / "metrics.csv", index=False)
    prediction_frame = pd.DataFrame(
        {
            "Actual": prepared.y_test,
            **{f"Predicted_{name.replace(' ', '_')}": values for name, values in predictions.items()},
        },
        index=prepared.y_test.index,
    )
    prediction_frame.to_csv(artifact_dir / "test_predictions.csv", index_label="Row")
    print(prepared.split_description)
    print(metrics.to_string(index=False))
    print(f"Saved best model ({best_name}) to {artifact_dir / 'model_bundle.joblib'}")
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="data/processed/f1_model_features.csv")
    parser.add_argument("--artifact-dir", default="artifacts")
    args = parser.parse_args()
    train_models(args.dataset, args.artifact_dir)


if __name__ == "__main__":
    main()
