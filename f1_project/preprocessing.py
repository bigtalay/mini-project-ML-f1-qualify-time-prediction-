"""Notebook-friendly imports for the single shared preprocessing implementation.

Preprocessor.fit_transform uses GroupKFold(event_id), median imputation,
target encoding, one-hot Team, scaling and SelectKBest. Fit only on the
training partition; call transform for validation/calibration/test/inference.
"""
from intelligence.ml import CATEGORIES, NUMERIC, Preprocessor

TARGET = "QualiTime"
NUMERIC_FEATURES = NUMERIC
TARGET_ENCODE_FEATURES = CATEGORIES


def transform_features(frame, artifacts: Preprocessor):
    return artifacts.transform(frame)
