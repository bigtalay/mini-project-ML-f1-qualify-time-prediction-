"""Leakage-safe preprocessing for the F1 qualifying dataset."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.feature_selection import SelectKBest, f_regression
from sklearn.impute import SimpleImputer
from sklearn.model_selection import KFold, train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler


TARGET = "QualiTime"
NUMERIC_FEATURES = [
    "AirTemp",
    "TrackTemp",
    "Humidity",
    "Rainfall",
    "FP1_Time",
    "FP2_Time",
    "FP3_Time",
    "Year",
]
TARGET_ENCODE_FEATURES = ["Driver", "Circuit"]
ONE_HOT_FEATURES = ["Team"]


@dataclass
class PreprocessingResult:
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series
    train_rows: pd.Index
    test_rows: pd.Index
    split_description: str
    report: dict
    artifacts: dict


def transform_features(df, artifacts):
    """Apply fitted preprocessing artifacts to new rows for inference."""
    required = {*NUMERIC_FEATURES, *TARGET_ENCODE_FEATURES, *ONE_HOT_FEATURES}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Prediction data is missing required columns: {missing}")

    features = df.copy()
    for column in NUMERIC_FEATURES:
        features[column] = pd.to_numeric(features[column], errors="coerce")
    for column in [*TARGET_ENCODE_FEATURES, *ONE_HOT_FEATURES]:
        features[column] = features[column].fillna("Unknown").astype(str)

    numeric = artifacts["numeric_imputer"].transform(features[NUMERIC_FEATURES])
    parts = [pd.DataFrame(numeric, columns=NUMERIC_FEATURES, index=features.index)]
    for column in TARGET_ENCODE_FEATURES:
        encoded_name = f"{column}_TargetEncoded"
        parts.append(
            features[column]
            .map(artifacts["target_maps"][column])
            .fillna(artifacts["target_defaults"][column])
            .rename(encoded_name)
            .to_frame()
        )

    one_hot = artifacts["one_hot_encoder"].transform(features[ONE_HOT_FEATURES])
    one_hot_names = artifacts["one_hot_encoder"].get_feature_names_out(ONE_HOT_FEATURES)
    parts.append(pd.DataFrame(one_hot, columns=one_hot_names, index=features.index))
    encoded = pd.concat(parts, axis=1)
    scaled_columns = [*NUMERIC_FEATURES, *[f"{c}_TargetEncoded" for c in TARGET_ENCODE_FEATURES]]
    encoded[scaled_columns] = artifacts["scaler"].transform(encoded[scaled_columns])
    selected = artifacts["feature_selector"].transform(encoded)
    selected_names = encoded.columns[artifacts["feature_selector"].get_support()].tolist()
    return pd.DataFrame(selected, columns=selected_names, index=features.index)


def _smoothed_target_map(category, target, smoothing=10.0):
    stats = pd.DataFrame({"category": category, "target": target}).groupby(
        "category", dropna=False
    )["target"].agg(["mean", "count"])
    global_mean = float(target.mean())
    encoded = (
        stats["count"] * stats["mean"] + smoothing * global_mean
    ) / (stats["count"] + smoothing)
    return encoded.to_dict(), global_mean


def _validate_and_clean(df):
    required = {TARGET, *NUMERIC_FEATURES, *TARGET_ENCODE_FEATURES, *ONE_HOT_FEATURES}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")

    clean = df.copy()
    input_rows = len(clean)
    duplicate_rows = int(clean.duplicated().sum())
    clean = clean.drop_duplicates().copy()

    numeric_columns = [TARGET, *NUMERIC_FEATURES]
    for column in numeric_columns:
        clean[column] = pd.to_numeric(clean[column], errors="coerce")
    clean[numeric_columns] = clean[numeric_columns].replace([np.inf, -np.inf], np.nan)

    invalid_target_rows = int((clean[TARGET].isna() | (clean[TARGET] <= 0)).sum())
    clean = clean.loc[clean[TARGET].notna() & (clean[TARGET] > 0)].copy()
    for column in [*TARGET_ENCODE_FEATURES, *ONE_HOT_FEATURES]:
        clean[column] = clean[column].fillna("Unknown").astype(str)

    if len(clean) < 2:
        raise ValueError("At least two valid rows are required after cleaning.")

    report = {
        "input_rows": input_rows,
        "duplicate_rows_removed": duplicate_rows,
        "invalid_target_rows_removed": invalid_target_rows,
        "clean_rows": len(clean),
        "missing_values_before_imputation": clean.isna().sum().to_dict(),
    }
    return clean, report


def prepare_data(df, test_year=2023, test_size=0.2, random_state=42, max_features=15):
    """Clean, split, encode, scale, and select features without test leakage."""
    clean, report = _validate_and_clean(df)
    feature_columns = [*NUMERIC_FEATURES, *TARGET_ENCODE_FEATURES, *ONE_HOT_FEATURES]
    X = clean[feature_columns]
    y = clean[TARGET]

    year_mask = X["Year"].eq(test_year)
    if year_mask.any() and (~year_mask).any():
        X_train_raw, X_test_raw = X.loc[~year_mask].copy(), X.loc[year_mask].copy()
        y_train, y_test = y.loc[~year_mask].copy(), y.loc[year_mask].copy()
        split_description = f"Chronological split: years before/other than {test_year} train, {test_year} test"
    else:
        X_train_raw, X_test_raw, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )
        split_description = f"Random {int((1-test_size)*100)}/{int(test_size*100)} split (year {test_year} unavailable)"

    imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    train_numeric = imputer.fit_transform(X_train_raw[NUMERIC_FEATURES])
    test_numeric = imputer.transform(X_test_raw[NUMERIC_FEATURES])
    train_parts = [pd.DataFrame(train_numeric, columns=NUMERIC_FEATURES, index=X_train_raw.index)]
    test_parts = [pd.DataFrame(test_numeric, columns=NUMERIC_FEATURES, index=X_test_raw.index)]

    target_maps = {}
    target_defaults = {}
    target_folds = KFold(
        n_splits=min(5, len(X_train_raw)), shuffle=True, random_state=random_state
    )
    for column in TARGET_ENCODE_FEATURES:
        encoded_name = f"{column}_TargetEncoded"
        train_encoded = pd.Series(index=X_train_raw.index, dtype=float, name=encoded_name)
        for fit_positions, validation_positions in target_folds.split(X_train_raw):
            fold_map, fold_default = _smoothed_target_map(
                X_train_raw.iloc[fit_positions][column], y_train.iloc[fit_positions]
            )
            validation_index = X_train_raw.index[validation_positions]
            train_encoded.loc[validation_index] = (
                X_train_raw.loc[validation_index, column]
                .map(fold_map)
                .fillna(fold_default)
            )

        mapping, default = _smoothed_target_map(X_train_raw[column], y_train)
        target_maps[column] = mapping
        target_defaults[column] = default
        train_parts.append(train_encoded.to_frame())
        test_parts.append(
            X_test_raw[column].map(mapping).fillna(default).rename(encoded_name).to_frame()
        )

    one_hot = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    train_one_hot = one_hot.fit_transform(X_train_raw[ONE_HOT_FEATURES])
    test_one_hot = one_hot.transform(X_test_raw[ONE_HOT_FEATURES])
    one_hot_names = one_hot.get_feature_names_out(ONE_HOT_FEATURES)
    train_parts.append(pd.DataFrame(train_one_hot, columns=one_hot_names, index=X_train_raw.index))
    test_parts.append(pd.DataFrame(test_one_hot, columns=one_hot_names, index=X_test_raw.index))

    X_train_encoded = pd.concat(train_parts, axis=1)
    X_test_encoded = pd.concat(test_parts, axis=1)
    scaled_columns = [*NUMERIC_FEATURES, *[f"{c}_TargetEncoded" for c in TARGET_ENCODE_FEATURES]]
    scaler = StandardScaler()
    X_train_encoded[scaled_columns] = scaler.fit_transform(X_train_encoded[scaled_columns])
    X_test_encoded[scaled_columns] = scaler.transform(X_test_encoded[scaled_columns])

    k = "all" if max_features is None else min(max_features, X_train_encoded.shape[1])
    selector = SelectKBest(score_func=f_regression, k=k)
    train_selected = selector.fit_transform(X_train_encoded, y_train)
    test_selected = selector.transform(X_test_encoded)
    selected_names = X_train_encoded.columns[selector.get_support()].tolist()
    X_train = pd.DataFrame(train_selected, columns=selected_names, index=X_train_raw.index)
    X_test = pd.DataFrame(test_selected, columns=selected_names, index=X_test_raw.index)

    report.update(
        {
            "train_rows": len(X_train),
            "test_rows": len(X_test),
            "encoded_feature_count": X_train_encoded.shape[1],
            "selected_feature_count": len(selected_names),
            "selected_features": selected_names,
            "remaining_missing_values": int(X_train.isna().sum().sum() + X_test.isna().sum().sum()),
        }
    )
    artifacts = {
        "numeric_imputer": imputer,
        "target_maps": target_maps,
        "target_defaults": target_defaults,
        "one_hot_encoder": one_hot,
        "scaler": scaler,
        "feature_selector": selector,
        "encoded_feature_names": X_train_encoded.columns.tolist(),
    }
    return PreprocessingResult(
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
        train_rows=X_train_raw.index,
        test_rows=X_test_raw.index,
        split_description=split_description,
        report=report,
        artifacts=artifacts,
    )
