import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from intelligence.data import Dataset, PRACTICE, clean_laps, hashes
from intelligence.ml import CATEGORIES, NUMERIC, ensure_artifacts, scenario


class DataModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = Dataset()
        cls.temp = tempfile.TemporaryDirectory()
        cls.before = hashes(cls.data.path / "raw")
        cls.bundle = ensure_artifacts(cls.data, Path(cls.temp.name))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_sources_and_cleaning_reconcile(self):
        report = self.data.quality()
        self.assertEqual(report["raw_laps"], report["kept_laps"] + sum(report["removals"].values()))
        self.assertEqual(report["kept_laps"], report["pre_qualifying_laps"] + report["after_qualifying_laps"])
        self.assertEqual(self.before, hashes(self.data.path / "raw"))
        self.assertEqual(len(self.data.events), 66)

    def test_overlapping_rules_have_one_removal_reason(self):
        sample = self.data.laps.iloc[:2].copy()
        sample.loc[:, "LapTime"] = np.nan
        sample.loc[:, "Deleted"] = True
        clean = clean_laps(sample)
        self.assertTrue(clean.reason.eq("missing_time_or_driver").all())
        self.assertTrue(clean.flag_deleted.all())

    def test_sprint_practice_after_qualifying_excluded(self):
        sample = self.data.features.loc[self.data.features.event_id.eq("2021-10")]
        self.assertTrue(sample.FP2_Time.isna().all())
        timing = self.data.sessions
        self.assertFalse(timing.loc[timing.event_id.eq("2021-10") & timing.session.eq("FP2"), "before_qualifying"].iloc[0])
        for (event_id, driver), laps in self.data.laps.loc[self.data.laps.usable & self.data.laps.pre_qualifying].groupby(["event_id", "Driver"]):
            row = self.data.features.loc[self.data.features.event_id.eq(event_id) & self.data.features.Driver.eq(driver)]
            if len(row):
                self.assertAlmostEqual(row[PRACTICE].min(axis=1).iloc[0], laps.LapTime.min())

    def test_test_and_calibration_never_in_fit_or_selection(self):
        report = self.bundle["report"]
        parts = {k: set(v["events"]) for k, v in report["partitions"].items()}
        for name, events in parts.items():
            for other, other_events in parts.items():
                if other != name:
                    self.assertFalse(events & other_events)
        for fold in self.bundle["processor"].fold_events:
            self.assertFalse(set(fold["fit"]) & set(fold["validation"]))
            self.assertFalse((set(fold["fit"]) | set(fold["validation"])) & (parts["test"] | parts["calibration"]))
        self.assertEqual(self.bundle["selected"], min(report["selection"], key=lambda r: r["rmse"])["model"])
        self.assertFalse(set(NUMERIC + CATEGORIES) & {"Q1", "Q2", "Q3", "Position", "AirTemp", "TrackTemp", "Rainfall", "Humidity"})

    def test_scenario_bounds_missing_and_unknown_categories(self):
        baseline = scenario(self.data, self.bundle, "2023-01", "VER", {})
        self.assertAlmostEqual(baseline["delta"], 0)
        self.assertLess(baseline["lower"], baseline["upper"])
        with self.assertRaises(ValueError):
            scenario(self.data, self.bundle, "2021-01", "VER", {})
        with self.assertRaises(ValueError):
            scenario(self.data, self.bundle, "2023-01", "VER", {"FP1_Time": -1})
        frame = self.data.features.loc[self.data.features.predictable].head(1).copy()
        frame["Driver"] = "UNKNOWN"
        frame["Team"] = "UNKNOWN"
        frame["circuit_id"] = "UNKNOWN"
        transformed = self.bundle["processor"].transform(frame)
        self.assertTrue(np.isfinite(transformed).all())

    def test_artifact_reuse(self):
        path = Path(self.temp.name) / "bundle.joblib"
        before = path.stat().st_mtime_ns
        ensure_artifacts(self.data, Path(self.temp.name))
        self.assertEqual(before, path.stat().st_mtime_ns)


if __name__ == "__main__":
    unittest.main()
