"""Download and cache F1 qualifying features from the FastF1 API."""

from __future__ import annotations

import argparse
import logging
import warnings
from pathlib import Path

import fastf1
import pandas as pd
from fastf1.exceptions import DataNotLoadedError, RateLimitExceededError


PRACTICE_SESSIONS = ("FP1", "FP2", "FP3")
DATA_COLUMNS = [
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


def configure_fastf1(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))
    fastf1.set_log_level("WARNING")
    logging.getLogger("fastf1").setLevel(logging.WARNING)


def get_practice_best_laps(year: int, event: str, session_code: str) -> pd.DataFrame:
    """Return each driver's fastest valid lap, or an empty frame if unavailable."""
    column = f"{session_code}_Time"
    try:
        session = fastf1.get_session(year, event, session_code)
        session.load(telemetry=False, weather=False, laps=True, messages=False)
        if session.laps.empty:
            return pd.DataFrame(columns=["Driver", column])
        best = session.laps.groupby("Driver", observed=True)["LapTime"].min().reset_index()
        best.columns = ["Driver", column]
        best[column] = best[column].dt.total_seconds()
        return best
    except (ValueError, DataNotLoadedError) as exc:
        # Some sprint/cancelled weekends do not have every FP session.
        print(f"    {session_code}: unavailable ({type(exc).__name__})")
        return pd.DataFrame(columns=["Driver", column])


def get_event_data(year: int, event: str) -> pd.DataFrame:
    print(f"  Collecting {year} {event}")
    qualifying = fastf1.get_session(year, event, "Q")
    qualifying.load(telemetry=False, weather=True, laps=False, messages=False)

    results = qualifying.results[["Abbreviation", "TeamName", "Q1", "Q2", "Q3"]].copy()
    results = results.rename(columns={"Abbreviation": "Driver", "TeamName": "Team"})
    for column in ("Q1", "Q2", "Q3"):
        results[column] = results[column].dt.total_seconds()
    results["QualiTime"] = results[["Q1", "Q2", "Q3"]].min(axis=1)
    if results.empty or results["QualiTime"].notna().sum() == 0:
        print("    Results unavailable; falling back to qualifying lap timing")
        qualifying.load(telemetry=False, weather=True, laps=True, messages=False)
        laps = qualifying.laps.dropna(subset=["Driver", "LapTime"])
        results = (
            laps.groupby("Driver", observed=True)
            .agg(Team=("Team", "first"), QualiTime=("LapTime", "min"))
            .reset_index()
        )
        results["QualiTime"] = results["QualiTime"].dt.total_seconds()
        results[["Q1", "Q2", "Q3"]] = pd.NA
    if results.empty:
        raise RuntimeError("No qualifying results or lap timing available")

    weather = qualifying.weather_data
    for column in ("AirTemp", "TrackTemp", "Humidity", "Rainfall"):
        results[column] = pd.to_numeric(weather[column], errors="coerce").mean()

    for session_code in PRACTICE_SESSIONS:
        results = results.merge(
            get_practice_best_laps(year, event, session_code),
            on="Driver",
            how="left",
        )
    results["Year"] = year
    results["Circuit"] = event
    return results[DATA_COLUMNS]


def collect_season(year: int, output_dir: Path, force: bool = False) -> pd.DataFrame:
    """Collect one season and checkpoint after every event for safe resumption."""
    output_path = output_dir / f"f1_{year}_raw.csv"
    if output_path.exists() and not force:
        season = pd.read_csv(output_path)
    else:
        season = pd.DataFrame(columns=DATA_COLUMNS)

    schedule = fastf1.get_event_schedule(year)
    schedule = schedule.loc[
        (schedule["EventFormat"] != "testing") & (schedule["RoundNumber"] > 0)
    ]
    expected_events = schedule["EventName"].astype(str).tolist()
    if season.empty:
        completed = set()
    else:
        has_practice_data = season[[f"{code}_Time" for code in PRACTICE_SESSIONS]].notna().any(axis=1)
        completed = set(season.loc[has_practice_data, "Circuit"].dropna().astype(str))
    failures = []

    print(f"Season {year}: {len(completed)}/{len(expected_events)} events already present")
    for event in expected_events:
        if event in completed:
            continue
        try:
            event_data = get_event_data(year, event)
            if season.empty:
                season = event_data.copy()
            else:
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message="The behavior of DataFrame concatenation with empty or all-NA entries",
                        category=FutureWarning,
                    )
                    season = pd.concat([season, event_data], ignore_index=True)
            season = season.drop_duplicates(subset=["Year", "Circuit", "Driver"], keep="last")
            season.to_csv(output_path, index=False)
        except RateLimitExceededError as exc:
            raise RuntimeError(
                "FastF1 rate limit reached. Rerun the pipeline; completed events are checkpointed."
            ) from exc
        except Exception as exc:
            failures.append((year, event, repr(exc)))
            print(f"    FAILED: {event}: {exc}")

    present = set(season.get("Circuit", pd.Series(dtype=str)).dropna().astype(str))
    missing = sorted(set(expected_events).difference(present))
    if failures or missing:
        details = "; ".join(f"{event}: {reason}" for _, event, reason in failures)
        raise RuntimeError(f"Season {year} incomplete. Missing: {missing}. Failures: {details}")
    print(f"Season {year}: complete ({len(season)} rows, {len(present)} events)")
    return season[DATA_COLUMNS]


def collect_dataset(
    years=(2021, 2022, 2023),
    output_dir: str | Path = ".",
    cache_dir: str | Path = "f1_cache",
    force: bool = False,
) -> pd.DataFrame:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_fastf1(Path(cache_dir))
    seasons = [collect_season(year, output_dir, force=force) for year in years]
    combined = pd.concat(seasons, ignore_index=True)
    combined = combined.drop_duplicates(subset=["Year", "Circuit", "Driver"], keep="last")
    combined_path = output_dir / "f1_all_circuits_raw.csv"
    combined.to_csv(combined_path, index=False)
    print(f"Combined dataset: {len(combined)} rows -> {combined_path}")
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=[2021, 2022, 2023])
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--cache-dir", default="f1_cache")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    collect_dataset(args.years, args.output_dir, args.cache_dir, args.force)


if __name__ == "__main__":
    main()
