"""Shared analytics over the verified final.ipynb snapshot."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRACTICE = ["FP1_Time", "FP2_Time", "FP3_Time"]


def records(frame: pd.DataFrame) -> list[dict]:
    """JSON-safe scalars; NaN/NaT never escape into API responses."""
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def flag(series):
    return series.astype("string").str.lower().isin(["true", "1"])


class Dataset:
    """Tables populated and checksum-verified by final_model.load_final."""

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
