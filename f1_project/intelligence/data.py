"""Offline source loading, auditable cleaning and shared weekend analytics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PRACTICE = ["FP1_Time", "FP2_Time", "FP3_Time"]


def records(frame: pd.DataFrame) -> list[dict]:
    """JSON-safe scalars; NaN/NaT never escape into API responses."""
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def hashes(directory: Path) -> dict:
    return {p.name: hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for p in sorted(directory.glob("*.csv"))}


def flag(series):
    return series.astype("string").str.lower().isin(["true", "1"])


def clean_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """First matching rule is the removal reason; independent flags retain overlaps."""
    frame = laps.copy()
    numeric = ["LapTime", "LapNumber", "Time", "Sector1Time", "Sector2Time", "Sector3Time",
               "SpeedI1", "SpeedI2", "SpeedFL", "SpeedST", "TyreLife", "Stint"]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    rules = {
        "duplicate": frame.drop(columns=["lap_id", "source_row"], errors="ignore").duplicated(),
        "missing_time_or_driver": frame.LapTime.isna() | frame.Driver.isna(),
        "nonpositive_time": frame.LapTime.le(0),
        "deleted": flag(frame.Deleted),
        "inaccurate": frame.IsAccurate.notna() & ~flag(frame.IsAccurate),
        "generated": flag(frame.FastF1Generated),
    }
    frame["reason"] = "kept"
    for name, condition in rules.items():
        frame[f"flag_{name}"] = condition
        frame.loc[frame.reason.eq("kept") & condition, "reason"] = name
    frame["usable"] = frame.reason.eq("kept")
    return frame


class Dataset:
    def __init__(self, data: Path = DATA):
        self.path = Path(data)
        self.manifest = json.loads((self.path / "reference/manifest.json").read_text())
        if hashes(self.path / "raw") != self.manifest["sha256"]:
            raise ValueError("Raw checksum mismatch; restore the source files before starting.")
        self.events = pd.read_csv(self.path / "reference/events.csv", dtype={"circuit_id": str})
        self.sessions = pd.read_csv(self.path / "reference/sessions.csv")
        for column in ["start_utc", "end_utc"]:
            self.sessions[column] = pd.to_datetime(self.sessions[column], utc=True, errors="raise")
        if not self.events.event_id.is_unique or self.sessions.duplicated(["event_id", "session"]).any():
            raise ValueError("Duplicate event or session identity")
        if set(self.sessions.event_id) != set(self.events.event_id):
            raise ValueError("Session metadata does not cover the dataset")
        q_start = self.sessions.loc[self.sessions.session.eq("Q")].set_index("event_id").start_utc
        self.sessions["before_qualifying"] = self.sessions.end_utc.lt(self.sessions.event_id.map(q_start))
        self.results = self._join(pd.read_csv(self.path / "raw/qualifying_results.csv"))
        self.results["source_row"] = np.arange(len(self.results)) + 2
        self.results["duplicate"] = self.results.duplicated(["event_id", "Driver"], keep="first")
        qcols = ["Q1", "Q2", "Q3"]
        self.results[qcols] = self.results[qcols].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
        self.results["QualiTime"] = self.results[qcols].where(self.results[qcols].gt(0)).min(axis=1)
        self.laps = self._join(pd.read_csv(self.path / "raw/practice_laps.csv", low_memory=False))
        self.laps["source_row"] = np.arange(len(self.laps)) + 2
        self.laps["lap_id"] = "lap-" + self.laps.source_row.astype(str)
        self.laps = clean_laps(self.laps)
        timing = self.sessions.set_index(["event_id", "session"]).before_qualifying
        self.laps["pre_qualifying"] = pd.MultiIndex.from_frame(self.laps[["event_id", "Session"]]).map(timing).fillna(False).astype(bool)
        self.weather = self._join(pd.read_csv(self.path / "raw/qualifying_weather.csv"))
        self.features = self._features()
        self.lap_groups = {key: frame for key, frame in self.laps.groupby("event_id", sort=False)}

    def _join(self, frame):
        joined = frame.merge(self.events, left_on=["Year", "Circuit"], right_on=["year", "name"],
                             how="left", validate="many_to_one", sort=False)
        if joined.event_id.isna().any():
            raise ValueError("Unmapped raw event; reference metadata must cover every row")
        return joined

    def _features(self):
        valid = self.laps.loc[self.laps.usable & self.laps.pre_qualifying]
        best = valid.groupby(["event_id", "Driver", "Session"]).LapTime.min().unstack("Session")
        best = best.rename(columns={s: f"{s}_Time" for s in ["FP1", "FP2", "FP3"]})
        result = self.results.loc[~self.results.duplicate].copy()
        result = result.merge(best.reindex(columns=PRACTICE), on=["event_id", "Driver"], how="left", validate="one_to_one")
        result["predictable"] = result[PRACTICE].notna().any(axis=1)
        return result

    def event(self, event_id):
        event = self.events.loc[self.events.event_id.eq(event_id)]
        if event.empty:
            raise KeyError(event_id)
        return records(event)[0]

    def filtered_laps(self, event_id, drivers=None, session=None, compound=None, usable=True, search="", sort="Time", descending=False):
        self.event(event_id)
        frame = self.lap_groups.get(event_id, self.laps.iloc[:0])
        mask = pd.Series(True, index=frame.index)
        if drivers:
            mask &= frame.Driver.isin(drivers)
        if session:
            mask &= frame.Session.eq(session)
        if compound:
            mask &= frame.Compound.eq(compound)
        if usable:
            mask &= frame.usable
        if search:
            mask &= frame.Driver.fillna("").str.contains(search, case=False, regex=False) | frame.Team.fillna("").str.contains(search, case=False, regex=False)
        return frame.loc[mask].sort_values([sort, "lap_id"], ascending=[not descending, True], na_position="last")

    def overview(self, event_id):
        event = self.event(event_id)
        result = self.results.loc[self.results.event_id.eq(event_id) & ~self.results.duplicate].sort_values("Position", na_position="last")
        sessions = self.sessions.loc[self.sessions.event_id.eq(event_id)].copy()
        lap_frame = self.lap_groups.get(event_id, self.laps.iloc[:0])
        counts = lap_frame.groupby("Session").size()
        sessions["lap_count"] = sessions.session.map(counts).fillna(0).astype(int)
        weather = self.weather.loc[self.weather.event_id.eq(event_id)]
        weather = weather[["Time", "AirTemp", "TrackTemp", "Rainfall", "Humidity"]].copy()
        return {"event": event, "results": records(result), "sessions": records(sessions), "weather": records(weather)}

    def compare(self, event_id, drivers, session=None, compound=None, search=""):
        frame = self.filtered_laps(event_id, drivers, session, compound, search=search)
        output = []
        for driver in drivers:
            sample = frame.loc[frame.Driver.eq(driver)]
            times = sample.LapTime
            output.append({"driver": driver, "count": len(sample),
                "median": float(times.median()) if len(sample) else None,
                "iqr": float(times.quantile(.75) - times.quantile(.25)) if len(sample) >= 5 else None,
                "enough_laps": len(sample) >= 5,
                "best_lap": records(sample.nsmallest(1, "LapTime"))[0] if len(sample) else None})
        return output

    def quality(self, event_id=None):
        laps = self.laps if event_id is None else self.laps.loc[self.laps.event_id.eq(event_id)]
        results = self.results if event_id is None else self.results.loc[self.results.event_id.eq(event_id)]
        features = self.features if event_id is None else self.features.loc[self.features.event_id.eq(event_id)]
        reasons = laps.reason.value_counts().to_dict()
        return {"version": self.manifest["version"], "checksums": self.manifest["sha256"],
                "raw_laps": len(laps), "raw_results": len(results), "kept_laps": int(laps.usable.sum()),
                "removals": {name: int(count) for name, count in reasons.items() if name != "kept"},
                "overlapping_flags": {c[5:]: int(laps[c].sum()) for c in laps if c.startswith("flag_")},
                "after_qualifying_laps": int((laps.usable & ~laps.pre_qualifying).sum()),
                "pre_qualifying_laps": int((laps.usable & laps.pre_qualifying).sum()),
                "result_duplicates": int(results.duplicate.sum()),
                "missing_targets": int(features.QualiTime.isna().sum()),
                "no_practice_rows": int((~features.predictable).sum()),
                "feature_rows": len(features), "missing_features": features[PRACTICE].isna().sum().to_dict()}
