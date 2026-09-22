"""Event-grouped training, separate model selection/calibration, untouched 2023 test."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_selection import SelectKBest, f_regression
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .data import DATA, ROOT, PRACTICE, Dataset, records

NUMERIC = [*PRACTICE, "Year"]
CATEGORIES = ["Driver", "circuit_id"]
ARTIFACTS = Path(os.environ.get("F1_ARTIFACTS", ROOT / "artifacts/intelligence"))
MODELS = ["Practice baseline", "Linear Regression", "Random Forest"]


def target_map(values, target):
    stats = pd.DataFrame({"category": values.astype(str), "target": target}).groupby("category").target.agg(["mean", "count"])
    mean = float(target.mean())
    return ((stats["count"] * stats["mean"] + 10 * mean) / (stats["count"] + 10)).to_dict(), mean


class Preprocessor:
    def fit_transform(self, frame):
        self.imputer = SimpleImputer(strategy="median", keep_empty_features=True)
        numeric = self.imputer.fit_transform(frame[NUMERIC])
        self.maps, self.defaults = {}, {}
        self.fold_events = []
        encoded = np.empty((len(frame), len(CATEGORIES)))
        folds = list(GroupKFold(n_splits=min(5, frame.event_id.nunique())).split(frame, groups=frame.event_id))
        for train, validation in folds:
            self.fold_events.append({"fit": sorted(frame.iloc[train].event_id.unique()),
                                     "validation": sorted(frame.iloc[validation].event_id.unique())})
        for j, column in enumerate(CATEGORIES):
            for train, validation in folds:
                mapping, default = target_map(frame.iloc[train][column], frame.iloc[train].QualiTime)
                encoded[validation, j] = frame.iloc[validation][column].astype(str).map(mapping).fillna(default)
            self.maps[column], self.defaults[column] = target_map(frame[column], frame.QualiTime)
        self.onehot = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        teams = self.onehot.fit_transform(frame[["Team"]].fillna("Unknown"))
        self.scaler = StandardScaler()
        scaled = self.scaler.fit_transform(np.column_stack([numeric, encoded]))
        matrix = np.column_stack([scaled, teams])
        self.selector = SelectKBest(f_regression, k=min(15, matrix.shape[1]))
        names = [*NUMERIC, *[f"{c}_TargetEncoded" for c in CATEGORIES], *self.onehot.get_feature_names_out(["Team"])]
        selected = self.selector.fit_transform(matrix, frame.QualiTime)
        self.selected = np.array(names)[self.selector.get_support()].tolist()
        return selected

    def transform(self, frame):
        numeric = self.imputer.transform(frame[NUMERIC])
        encoded = np.column_stack([frame[c].astype(str).map(self.maps[c]).fillna(self.defaults[c]) for c in CATEGORIES])
        scaled = self.scaler.transform(np.column_stack([numeric, encoded]))
        teams = self.onehot.transform(frame[["Team"]].fillna("Unknown"))
        return self.selector.transform(np.column_stack([scaled, teams]))


def fit_models(frame):
    processor = Preprocessor()
    matrix = processor.fit_transform(frame)
    models = {"Linear Regression": LinearRegression(),
              "Random Forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=42, n_jobs=-1)}
    for model in models.values():
        model.fit(matrix, frame.QualiTime)
    return processor, models


def predict(frame, processor, models, name):
    if name == "Practice baseline":
        return frame[PRACTICE].min(axis=1).to_numpy()
    return models[name].predict(processor.transform(frame))


def metrics(actual, predicted):
    residual = np.asarray(actual) - np.asarray(predicted)
    return {"count": len(residual), "mae": float(np.abs(residual).mean()),
            "rmse": float(np.sqrt(np.square(residual).mean()))}


def fingerprint(data=DATA):
    digest = hashlib.sha256()
    for folder, pattern in [(Path(data)/"raw", "*.csv"), (Path(data)/"reference", "*"), (ROOT/"intelligence", "*.py")]:
        for path in sorted(folder.glob(pattern)):
            if path.is_file():
                digest.update(path.name.encode())
                digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    for package in ["pandas", "numpy", "scikit-learn", "joblib"]:
        digest.update(f"{package}={importlib.metadata.version(package)}".encode())
    return digest.hexdigest()


def train(dataset: Dataset, output=ARTIFACTS):
    output = Path(output)
    frame = dataset.features.loc[dataset.features.predictable & dataset.features.QualiTime.notna()].copy()
    training = frame.loc[frame.Year.eq(2021)]
    validation = frame.loc[frame.Year.eq(2022) & frame["round"].le(11)]
    calibration = frame.loc[frame.Year.eq(2022) & frame["round"].gt(11)]
    testing = frame.loc[frame.Year.eq(2023)]
    if any(part.empty for part in [training, validation, calibration, testing]):
        raise ValueError("All four chronological partitions must contain eligible rows")
    processor, models = fit_models(training)
    selection = [{"model": name, **metrics(validation.QualiTime, predict(validation, processor, models, name))} for name in MODELS]
    chosen = min(selection, key=lambda row: row["rmse"])["model"]
    final_fit = pd.concat([training, validation]).sort_values(["Year", "round", "Driver"])
    processor, models = fit_models(final_fit)
    cal_prediction = predict(calibration, processor, models, chosen)
    residuals = calibration.QualiTime.to_numpy() - cal_prediction
    lo, hi = [float(x) for x in np.quantile(residuals, [.05, .95])]
    results, test_metrics, per_event = [], [], []
    for name in MODELS:
        prediction = predict(testing, processor, models, name)
        test_metrics.append({"model": name, **metrics(testing.QualiTime, prediction)})
        table = testing[["event_id", "Driver", "Team", "QualiTime", *PRACTICE]].copy()
        table["model"] = name
        table["prediction"] = prediction
        table["error"] = prediction - table.QualiTime
        table["lower"] = prediction + lo if name == chosen else np.nan
        table["upper"] = prediction + hi if name == chosen else np.nan
        results.append(table)
        for event_id, group in table.groupby("event_id"):
            per_event.append({"event_id": event_id, "model": name, **metrics(group.QualiTime, group.prediction)})
    predictions = pd.concat(results, ignore_index=True)
    active = predictions.loc[predictions.model.eq(chosen)]
    report = {"selected_model": chosen, "selection": selection, "test": test_metrics, "per_event": per_event,
              "interval": {"percentiles": [5, 95], "residual_lower": lo, "residual_upper": hi,
                           "calibration_count": len(calibration),
                           "test_coverage": float(active.QualiTime.between(active.lower, active.upper).mean())},
              "partitions": {name: {"rows": len(part), "events": sorted(part.event_id.unique())}
                             for name, part in [("training", training), ("selection", validation), ("calibration", calibration), ("test", testing)]},
              "selected_features": processor.selected,
              "excluded_test_rows": int(dataset.features.Year.eq(2023).sum() - len(testing)),
              "input_ranges": {c: {"min": float(final_fit[c].min()), "max": float(final_fit[c].max())} for c in PRACTICE}}
    bundle = {"processor": processor, "models": models, "selected": chosen, "report": report, "fingerprint": fingerprint(dataset.path)}
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, output / "bundle.tmp")
    (output / "bundle.tmp").replace(output / "bundle.joblib")
    predictions.to_csv(output / "predictions.csv", index=False)
    dataset.features.to_csv(output / "features.csv", index=False)
    dataset.laps[["lap_id", "source_row", "event_id", "reason", "usable", "pre_qualifying", *[c for c in dataset.laps if c.startswith("flag_")]]].to_csv(output / "lap_audit.csv", index=False)
    (output / "evaluation.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    (output / "quality.json").write_text(json.dumps(dataset.quality(), indent=2), encoding="utf-8")
    # Write the completion marker last. An interrupted run will be rebuilt at startup.
    (output / "fingerprint.txt").write_text(bundle["fingerprint"], encoding="utf-8")
    return bundle


def ensure_artifacts(dataset: Dataset, output=ARTIFACTS, force=False):
    output = Path(output)
    marker = output / "fingerprint.txt"
    required = ["bundle.joblib", "predictions.csv", "evaluation.json", "quality.json", "features.csv", "lap_audit.csv"]
    if not force and marker.exists() and marker.read_text() == fingerprint(dataset.path) and all((output / f).exists() for f in required):
        print("Dataset/model version unchanged; reuse artifacts", flush=True)
        return joblib.load(output / "bundle.joblib")
    print("Preparing data and evaluating models offline...", flush=True)
    return train(dataset, output)


def scenario(dataset, bundle, event_id, driver, overrides):
    frame = dataset.features.loc[dataset.features.event_id.eq(event_id) & dataset.features.Driver.eq(driver)].copy()
    if frame.empty:
        raise ValueError("ไม่พบนักขับในรายการนี้")
    if int(frame.iloc[0].Year) != 2023:
        raise ValueError("What-if เปิดเฉพาะชุดทดสอบปี 2023")
    if not bool(frame.iloc[0].predictable):
        raise ValueError("ไม่มี Practice ที่ใช้ได้ก่อน Qualifying จึงไม่ออกผลทำนาย")
    baseline = float(predict(frame, bundle["processor"], bundle["models"], bundle["selected"])[0])
    warnings = []
    for column, value in overrides.items():
        if column not in PRACTICE or pd.isna(frame.iloc[0][column]):
            raise ValueError("แก้ได้เฉพาะ Practice ที่มีข้อมูลก่อน Qualifying")
        if not np.isfinite(value) or value <= 0:
            raise ValueError("เวลา Practice ต้องเป็นตัวเลขบวกที่ finite")
        frame[column] = value
        limits = bundle["report"]["input_ranges"][column]
        if not limits["min"] <= value <= limits["max"]:
            warnings.append(f"{column}: อยู่นอกช่วงข้อมูลฝึก {limits['min']:.3f}–{limits['max']:.3f} วินาที")
    processor = bundle["processor"]
    for c in CATEGORIES:
        if str(frame.iloc[0][c]) not in processor.maps[c]:
            warnings.append(f"{c}: ไม่พบในชุดฝึก ใช้ค่าอ้างอิงจากชุดฝึก")
    value = float(predict(frame, processor, bundle["models"], bundle["selected"])[0])
    if not np.isfinite(value) or value <= 0:
        raise ValueError("สถานการณ์นี้ให้ผลนอกขอบเขตที่แสดงได้ กรุณาใช้ input ใกล้ข้อมูลจริง")
    interval = bundle["report"]["interval"]
    return {"prediction": value, "baseline": baseline, "delta": round(value-baseline, 9),
            "lower": value+interval["residual_lower"], "upper": value+interval["residual_upper"],
            "warnings": warnings, "inputs": records(frame[PRACTICE])[0], "model": bundle["selected"]}
