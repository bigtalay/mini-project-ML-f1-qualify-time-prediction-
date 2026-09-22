"""Explicit maintenance command: collect FastF1 session metadata, never at app startup."""
import argparse
import hashlib
import json
from pathlib import Path

import fastf1
import pandas as pd
from fastf1 import _api


def raw_manifest(raw_dir):
    return {
        p.name: hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for p in sorted(Path(raw_dir).glob("*.csv"))
    }


def collect(cache, data):
    fastf1.Cache.enable_cache(str(cache))
    results = pd.read_csv(data / "raw/qualifying_results.csv")
    events, sessions = [], []
    aliases = {"Practice 1": "FP1", "Practice 2": "FP2", "Practice 3": "FP3", "Qualifying": "Q"}
    for year in sorted(results.Year.unique()):
        schedule = fastf1.get_event_schedule(int(year))
        for _, row in schedule.iterrows():
            if row.EventName not in set(results.loc[results.Year.eq(year), "Circuit"]):
                continue
            event_id = f"{year}-{int(row.RoundNumber):02d}"
            q = fastf1.get_session(int(year), int(row.RoundNumber), "Q")
            info = _api.session_info(q.api_path)
            circuit = info["Meeting"]["Circuit"]
            events.append(dict(event_id=event_id, year=int(year), round=int(row.RoundNumber),
                               name=row.EventName, circuit_id=str(circuit["Key"]),
                               circuit=circuit["ShortName"], country=row.Country,
                               location=row.Location, format=row.EventFormat))
            for i in range(1, 6):
                code = aliases.get(row[f"Session{i}"])
                if not code:
                    continue
                session = fastf1.get_session(int(year), int(row.RoundNumber), code)
                detail = _api.session_info(session.api_path)
                offset = detail["GmtOffset"]
                sessions.append(dict(event_id=event_id, session=code,
                    start_utc=(pd.Timestamp(detail["StartDate"]) - offset).tz_localize("UTC").isoformat(),
                    end_utc=(pd.Timestamp(detail["EndDate"]) - offset).tz_localize("UTC").isoformat(),
                    timing_source="FastF1 SessionInfo StartDate/EndDate", source_path=session.api_path))
            print(event_id, row.EventName, flush=True)
    target = data / "reference"
    target.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(events).to_csv(target / "events.csv", index=False)
    pd.DataFrame(sessions).to_csv(target / "sessions.csv", index=False)
    manifest = {"version": "2021-2023.v1", "source": "FastF1 3.8.3 selected source columns",
                "hash_normalization": "CRLF to LF", "sha256": raw_manifest(data / "raw")}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=Path("data"))
    args = parser.parse_args()
    collect(args.cache, args.data)
