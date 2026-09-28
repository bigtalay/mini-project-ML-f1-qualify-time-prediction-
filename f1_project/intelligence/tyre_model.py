"""Two explicit feature experiments. Identities are join/report keys, never X."""
from pathlib import Path
import json
import re

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .data import ROOT, records
from .ml import fingerprint, metrics

ARTIFACTS = ROOT / "artifacts/practice-tyres-v1"
SESSIONS = ["FP1", "FP2", "FP3"]
TIMES = [f"{s}_Time" for s in SESSIONS]
AGES = [f"{s}_TyreLife" for s in SESSIONS]
COMPOUNDS = [f"{s}_Compound" for s in SESSIONS]
KINDS = ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET", "UNKNOWN"]
FEATURES = {"Time": TIMES, "Time + tyres": [f"{s}_{c}" for s in SESSIONS for c in ["Time", "Compound", "TyreLife"]]}


def build_features(dataset):
    valid = dataset.laps.loc[dataset.laps.usable & dataset.laps.pre_qualifying]
    best = valid.sort_values(["LapTime", "source_row"], kind="stable").drop_duplicates(["event_id", "Driver", "Session"])
    frame = dataset.results.loc[~dataset.results.duplicate].copy()
    for session in SESSIONS:
        columns = {"LapTime": "Time", "Compound": "Compound", "TyreLife": "TyreLife", "source_row": "source_row", "lap_id": "lap_id"}
        part = best.loc[best.Session.eq(session), ["event_id", "Driver", *columns]]
        part = part.rename(columns={c: f"{session}_{suffix}" for c, suffix in columns.items()})
        frame = frame.merge(part, on=["event_id", "Driver"], how="left", validate="one_to_one")
    frame["predictable"] = frame[TIMES].notna().any(axis=1)
    frame["session_group"] = np.where(frame[TIMES].notna().all(axis=1), "complete", "missing")
    wet = frame[COMPOUNDS].isin(["INTERMEDIATE", "WET"]).any(axis=1)
    unknown = frame[COMPOUNDS].where(frame[TIMES].notna().to_numpy()).apply(lambda c: c.notna() & ~c.isin(KINDS[:-1])).any(axis=1)
    missing_tyre = (frame[COMPOUNDS].isna().to_numpy() & frame[TIMES].notna().to_numpy()).any(axis=1)
    frame["tyre_group"] = np.where(wet, "wet", np.where(unknown | missing_tyre, "unknown", "dry"))
    return frame


def fill_sessions(frame):
    """Copy the entire fastest available triple; do not invent an available session."""
    filled = frame.copy()
    filled[COMPOUNDS] = filled[COMPOUNDS].astype(object)
    filled[AGES] = filled[AGES].apply(pd.to_numeric, errors="coerce").astype(float)
    source_values = filled.copy()
    if filled[TIMES].isna().all(axis=1).any():
        raise ValueError("ไม่มี Practice ที่ใช้ได้ก่อน Qualifying จึงไม่ออกคำทำนาย")
    fastest = filled[TIMES].idxmin(axis=1).str.replace("_Time", "", regex=False)
    for session in SESSIONS:
        absent = filled[f"{session}_Time"].isna()
        filled[f"{session}_filled_from"] = session
        for source in SESSIONS:
            mask = absent & fastest.eq(source)
            for suffix in ["Time", "Compound", "TyreLife"]:
                filled.loc[mask, f"{session}_{suffix}"] = source_values.loc[mask, f"{source}_{suffix}"]
            filled.loc[mask, f"{session}_filled_from"] = source
        c = f"{session}_Compound"
        filled[c] = filled[c].where(filled[c].isin(KINDS), "UNKNOWN")
        c = f"{session}_TyreLife"
        age = pd.to_numeric(filled[c], errors="coerce")
        filled[c] = age.where(np.isfinite(age) & age.ge(0))
    return filled


def fit_processor(frame, feature_set):
    filled = fill_sessions(frame)
    # Pooled fallback uses real, selected training laps, not copied sessions.
    ages = frame[AGES].apply(pd.to_numeric, errors="coerce")
    ages = ages.where(np.isfinite(ages) & ages.ge(0))
    pooled = ages.stack().median()
    if feature_set == "Time + tyres" and pd.isna(pooled):
        raise ValueError("ไม่มีอายุยางที่ใช้ได้ในชุดฝึกเพื่อคำนวณ median")
    medians = filled[AGES].median().fillna(pooled)
    numeric = TIMES if feature_set == "Time" else TIMES + AGES
    values = filled[numeric].fillna(medians)
    scaler = StandardScaler().fit(values)
    encoder = None
    if feature_set == "Time + tyres":
        encoder = OneHotEncoder(categories=[KINDS] * 3, handle_unknown="ignore", sparse_output=False).fit(filled[COMPOUNDS])
    return {"numeric": numeric, "medians": medians, "scaler": scaler, "encoder": encoder, "feature_set": feature_set}


def transform(frame, processor):
    filled = fill_sessions(frame)
    numeric = processor["scaler"].transform(filled[processor["numeric"]].fillna(processor["medians"]))
    if processor["encoder"] is None:
        return numeric
    return np.column_stack([numeric, processor["encoder"].transform(filled[COMPOUNDS])])


def fit_models(frame, feature_set):
    processor = fit_processor(frame, feature_set)
    matrix = transform(frame, processor)
    models = {"Linear Regression": LinearRegression(), "Random Forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=42, n_jobs=-1)}
    for model in models.values():
        model.fit(matrix, frame.QualiTime)
    return processor, models


def train(dataset, output=ARTIFACTS):
    features = build_features(dataset)
    frame = features.loc[features.predictable & features.QualiTime.notna()]
    training = frame.loc[frame.Year.eq(2021)]
    validation = frame.loc[frame.Year.eq(2022) & frame["round"].le(11)]
    calibration = frame.loc[frame.Year.eq(2022) & frame["round"].gt(11)]
    testing = frame.loc[frame.Year.eq(2023)]
    if any(p.empty for p in [training, validation, calibration, testing]):
        raise ValueError("All chronological partitions must have eligible rows")
    final_fit = pd.concat([training, validation]).sort_values(["Year", "round", "Driver"])
    selection = [{"model": "Practice baseline", **metrics(validation.QualiTime, validation[TIMES].min(axis=1))}]
    experiments, winners = {}, {}
    for feature_set in FEATURES:
        processor, models = fit_models(training, feature_set)
        scores = [{"model": f"{feature_set} / {name}", **metrics(validation.QualiTime, model.predict(transform(validation, processor)))} for name, model in models.items()]
        selection.extend(scores)
        winner = min(scores, key=lambda r: r["rmse"])["model"].split(" / ")[1]
        processor, models = fit_models(final_fit, feature_set)
        experiments[feature_set] = {"processor": processor, "models": models, "winner": winner}
        winners[feature_set] = f"{feature_set} / {winner}"
    chosen = winners["Time + tyres"]
    active = experiments["Time + tyres"]
    cal = active["models"][active["winner"]].predict(transform(calibration, active["processor"]))
    lo, hi = map(float, np.quantile(calibration.QualiTime.to_numpy() - cal, [.05, .95]))
    predictions = {"Practice baseline": testing[TIMES].min(axis=1).to_numpy()}
    for feature_set, experiment in experiments.items():
        for name, model in experiment["models"].items():
            predictions[f"{feature_set} / {name}"] = model.predict(transform(testing, experiment["processor"]))
    scores, per_event, groups, tables = [], [], [], []
    for name, predicted in predictions.items():
        table = testing.copy()
        table["model"], table["prediction"] = name, predicted
        table["error"] = predicted - table.QualiTime
        table["lower"], table["upper"] = (predicted + lo, predicted + hi) if name == chosen else (np.nan, np.nan)
        tables.append(table)
        scores.append({"model": name, **metrics(table.QualiTime, predicted)})
        for event_id, group in table.groupby("event_id"):
            per_event.append({"event_id": event_id, "model": name, **metrics(group.QualiTime, group.prediction)})
        for column in ["session_group", "tyre_group"]:
            for value, group in table.groupby(column):
                groups.append({"group": f"{column}: {value}", "model": name, **metrics(group.QualiTime, group.prediction)})
    filled = fill_sessions(final_fit)
    filled[AGES] = filled[AGES].fillna(active["processor"]["medians"])
    report = {"selected_model": chosen, "selection": selection, "test": scores, "per_event": per_event, "groups": groups,
              "winners": winners, "raw_features": FEATURES["Time + tyres"], "selected_features": TIMES + AGES + list(active["processor"]["encoder"].get_feature_names_out(COMPOUNDS)),
              "interval": {"percentiles": [5, 95], "residual_lower": lo, "residual_upper": hi, "calibration_count": len(calibration), "test_coverage": float(np.mean((testing.QualiTime >= predictions[chosen] + lo) & (testing.QualiTime <= predictions[chosen] + hi)))},
              "partitions": {name: {"rows": len(part), "events": sorted(part.event_id.unique())} for name, part in [("training", training), ("selection", validation), ("calibration", calibration), ("test", testing)]},
              "excluded_test_rows": int(features.Year.eq(2023).sum() - len(testing)),
              "input_ranges": {c: {"min": float(filled[c].min()), "max": float(filled[c].max())} for c in TIMES + AGES}}
    bundle = {"experiments": experiments, "selected": chosen, "report": report, "fingerprint": fingerprint(dataset.path)}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, output / "bundle.tmp")
    (output / "bundle.tmp").replace(output / "bundle.joblib")
    pd.concat(tables).to_csv(output / "predictions.csv", index=False)
    features.to_csv(output / "features.csv", index=False)
    dataset.laps.to_csv(output / "lap_audit.csv", index=False)
    (output / "evaluation.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    (output / "fingerprint.txt").write_text(bundle["fingerprint"], encoding="utf-8")
    return bundle


def ensure_artifacts(dataset, output=ARTIFACTS, force=False):
    output = Path(output)
    marker = output / "fingerprint.txt"
    required = ["bundle.joblib", "predictions.csv", "features.csv", "lap_audit.csv", "evaluation.json"]
    if not force and marker.exists() and marker.read_text() == fingerprint(dataset.path) and all((output / f).exists() for f in required):
        return joblib.load(output / "bundle.joblib")
    return train(dataset, output)


def parse_time(value):
    if isinstance(value, bool):
        raise ValueError("เวลา Practice ต้องเป็นวินาทีหรือ m:ss.sss")
    if isinstance(value, str) and ":" in value:
        if not re.fullmatch(r"\d+:[0-5]\d(?:\.\d+)?", value.strip()):
            raise ValueError("รูปแบบเวลาต้องเป็น m:ss.sss")
        minutes, seconds = value.strip().split(":")
        value = 60 * int(minutes) + float(seconds)
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValueError("เวลา Practice ต้องเป็นตัวเลขบวก")
    if not np.isfinite(value) or value <= 0:
        raise ValueError("เวลา Practice ต้องมากกว่า 0 วินาทีและเป็น finite")
    return value


def custom_predict(bundle, sessions):
    if set(sessions) - set(SESSIONS):
        raise ValueError("รองรับเฉพาะ FP1, FP2, FP3")
    row = {}
    for s in SESSIONS:
        session = sessions.get(s)
        if session is None:
            row.update({f"{s}_{c}": np.nan for c in ["Time", "Compound", "TyreLife"]})
            continue
        age = session.get("tyre_life")
        if age is not None and (isinstance(age, bool) or not isinstance(age, (int, float)) or not np.isfinite(age) or age < 0):
            raise ValueError("อายุยางต้องเป็นจำนวนรอบที่ไม่ติดลบ หรือเว้นว่าง")
        compound = session.get("compound") or "UNKNOWN"
        row.update({f"{s}_Time": parse_time(session.get("time")), f"{s}_Compound": compound if compound in KINDS else "UNKNOWN", f"{s}_TyreLife": age})
    frame = pd.DataFrame([row])
    filled = fill_sessions(frame)
    experiment = bundle["experiments"]["Time + tyres"]
    processor = experiment["processor"]
    warnings, imputations = [], []
    for s in SESSIONS:
        source = filled.iloc[0][f"{s}_filled_from"]
        if source != s:
            imputations.append(f"{s}: ใช้เวลา/ยาง/อายุยางจาก {source}")
        age = f"{s}_TyreLife"
        if pd.isna(filled.iloc[0][age]):
            filled[age] = processor["medians"][age]
            imputations.append(f"{age}: ใช้ training median {filled.iloc[0][age]:g} รอบ")
        if filled.iloc[0][f"{s}_Compound"] == "UNKNOWN":
            imputations.append(f"{s}_Compound: UNKNOWN (ไม่มีหรือไม่รู้จักชนิดยาง)")
    for column, bounds in bundle["report"]["input_ranges"].items():
        if not bounds["min"] <= filled.iloc[0][column] <= bounds["max"]:
            warnings.append(f"{column}: อยู่นอกช่วงฝึก {bounds['min']:.3f}–{bounds['max']:.3f}")
    prediction = float(experiment["models"][experiment["winner"]].predict(transform(frame, processor))[0])
    if not np.isfinite(prediction) or prediction <= 0:
        raise ValueError("input นี้ให้ผลทำนายนอกขอบเขต กรุณาใช้ค่าใกล้ข้อมูลจริง")
    interval = bundle["report"]["interval"]
    return {"prediction": prediction, "lower": prediction + interval["residual_lower"], "upper": prediction + interval["residual_upper"], "model": bundle["selected"], "warnings": warnings, "imputations": imputations, "inputs": records(filled[FEATURES["Time + tyres"]])[0]}


def row_sessions(row):
    return {s: {"time": float(row[f"{s}_Time"]), "compound": row[f"{s}_Compound"] if pd.notna(row[f"{s}_Compound"]) else None, "tyre_life": float(row[f"{s}_TyreLife"]) if pd.notna(row[f"{s}_TyreLife"]) else None} if pd.notna(row[f"{s}_Time"]) else None for s in SESSIONS}


def scenario(dataset, bundle, event_id, driver, overrides, tyre_overrides=None):
    rows = build_features(dataset)
    rows = rows.loc[rows.event_id.eq(event_id) & rows.Driver.eq(driver)]
    if rows.empty or int(rows.iloc[0].Year) != 2023:
        raise ValueError("เลือกนักขับในข้อมูลย้อนหลังปี 2023")
    sessions = row_sessions(rows.iloc[0])
    baseline = custom_predict(bundle, sessions)["prediction"]
    for column, value in overrides.items():
        session = column.removesuffix("_Time")
        if session not in SESSIONS or sessions[session] is None:
            raise ValueError("แก้ได้เฉพาะ Practice ที่มีข้อมูลก่อน Qualifying")
        sessions[session]["time"] = value
    for session, values in (tyre_overrides or {}).items():
        if sessions.get(session) is None:
            raise ValueError("ไม่มี session ต้นทางให้แก้ไข")
        sessions[session].update(values)
    result = custom_predict(bundle, sessions)
    return {**result, "baseline": baseline, "delta": round(result["prediction"] - baseline, 9)}
