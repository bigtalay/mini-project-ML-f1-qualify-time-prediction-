"""Extract source-granularity qualifying, practice-lap, and weather tables."""

from __future__ import annotations

import argparse
import logging
import warnings
from pathlib import Path

import fastf1
import pandas as pd
from fastf1.exceptions import DataNotLoadedError, RateLimitExceededError


PRACTICE_SESSIONS = ("FP1", "FP2", "FP3")
RESULT_COLUMNS = [
    "Year",
    "Circuit",
    "DriverNumber",
    "Driver",
    "DriverId",
    "Team",
    "Position",
    "Q1",
    "Q2",
    "Q3",
    "Status",
]
LAP_COLUMNS = [
    "Year",
    "Circuit",
    "Session",
    "Time",
    "Driver",
    "DriverNumber",
    "LapTime",
    "LapNumber",
    "Stint",
    "Sector1Time",
    "Sector2Time",
    "Sector3Time",
    "SpeedI1",
    "SpeedI2",
    "SpeedFL",
    "SpeedST",
    "Compound",
    "TyreLife",
    "FreshTyre",
    "Team",
    "TrackStatus",
    "Deleted",
    "DeletedReason",
    "FastF1Generated",
    "IsAccurate",
]
WEATHER_COLUMNS = [
    "Year",
    "Circuit",
    "Session",
    "Time",
    "AirTemp",
    "Humidity",
    "Pressure",
    "Rainfall",
    "TrackTemp",
    "WindDirection",
    "WindSpeed",
]
TIME_COLUMNS = {
    "Q1",
    "Q2",
    "Q3",
    "Time",
    "LapTime",
    "Sector1Time",
    "Sector2Time",
    "Sector3Time",
}


def configure_fastf1(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))
    fastf1.set_log_level("WARNING")
    logging.getLogger("fastf1").setLevel(logging.WARNING)


def _seconds(frame: pd.DataFrame) -> pd.DataFrame:
    """Serialize FastF1 timedeltas as seconds without imputing or aggregating."""
    frame = frame.copy()
    for column in TIME_COLUMNS.intersection(frame.columns):
        if pd.api.types.is_timedelta64_dtype(frame[column]):
            frame[column] = frame[column].dt.total_seconds()
    return frame


def _qualifying_results(session, year: int, circuit: str) -> pd.DataFrame:
    source = session.results[
        ["DriverNumber", "Abbreviation", "DriverId", "TeamName", "Position", "Q1", "Q2", "Q3", "Status"]
    ].copy()
    source = source.rename(columns={"Abbreviation": "Driver", "TeamName": "Team"})
    source.insert(0, "Circuit", circuit)
    source.insert(0, "Year", year)
    return _seconds(source)[RESULT_COLUMNS]


def _qualifying_weather(session, year: int, circuit: str) -> pd.DataFrame:
    source = session.weather_data.copy()
    source.insert(0, "Session", "Q")
    source.insert(0, "Circuit", circuit)
    source.insert(0, "Year", year)
    return _seconds(source)[WEATHER_COLUMNS]


def _practice_laps(year: int, circuit: str, session_code: str) -> pd.DataFrame:
    try:
        session = fastf1.get_session(year, circuit, session_code)
        session.load(telemetry=False, weather=False, laps=True, messages=False)
        source = session.laps[
            [column for column in LAP_COLUMNS if column in session.laps.columns]
        ].copy()
    except (ValueError, DataNotLoadedError) as exc:
        print(f"    {session_code}: unavailable ({type(exc).__name__})")
        return pd.DataFrame(columns=LAP_COLUMNS)

    source.insert(0, "Session", session_code)
    source.insert(0, "Circuit", circuit)
    source.insert(0, "Year", year)
    return _seconds(source)[LAP_COLUMNS]


def collect_event(year: int, circuit: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    print(f"  Extracting {year} {circuit}")
    qualifying = fastf1.get_session(year, circuit, "Q")
    qualifying.load(telemetry=False, weather=True, laps=False, messages=False)
    results = _qualifying_results(qualifying, year, circuit)
    weather = _qualifying_weather(qualifying, year, circuit)
    practice_frames = [_practice_laps(year, circuit, code) for code in PRACTICE_SESSIONS]
    available_practices = [frame for frame in practice_frames if not frame.empty]
    practices = (
        pd.concat(available_practices, ignore_index=True)
        if available_practices
        else pd.DataFrame(columns=LAP_COLUMNS)
    )
    if results.empty:
        raise RuntimeError("FastF1 returned no qualifying result rows")
    return results, practices, weather


def _read_or_empty(path: Path, columns: list[str], force: bool) -> pd.DataFrame:
    if path.exists() and not force:
        return pd.read_csv(path)
    return pd.DataFrame(columns=columns)


def _append(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        return new.copy()
    if new.empty:
        return existing
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="The behavior of DataFrame concatenation with empty or all-NA entries",
            category=FutureWarning,
        )
        return pd.concat([existing, new], ignore_index=True)


def collect_raw_dataset(
    years=(2021, 2022, 2023),
    raw_dir: str | Path = "data/raw",
    cache_dir: str | Path = "f1_cache",
    force: bool = False,
) -> dict[str, pd.DataFrame]:
    """Extract raw tables and checkpoint them after every complete event."""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    configure_fastf1(Path(cache_dir))

    paths = {
        "results": raw_dir / "qualifying_results.csv",
        "laps": raw_dir / "practice_laps.csv",
        "weather": raw_dir / "qualifying_weather.csv",
    }
    results = _read_or_empty(paths["results"], RESULT_COLUMNS, force)
    laps = _read_or_empty(paths["laps"], LAP_COLUMNS, force)
    weather = _read_or_empty(paths["weather"], WEATHER_COLUMNS, force)
    result_events = set(zip(results.get("Year", []), results.get("Circuit", [])))
    lap_events = set(zip(laps.get("Year", []), laps.get("Circuit", [])))
    weather_events = set(zip(weather.get("Year", []), weather.get("Circuit", [])))
    completed = result_events & lap_events & weather_events

    for year in years:
        schedule = fastf1.get_event_schedule(year)
        schedule = schedule.loc[
            (schedule["EventFormat"] != "testing") & (schedule["RoundNumber"] > 0)
        ]
        for circuit in schedule["EventName"].astype(str):
            if (year, circuit) in completed:
                continue
            try:
                event_results, event_laps, event_weather = collect_event(year, circuit)
                results = _append(results, event_results)
                laps = _append(laps, event_laps)
                weather = _append(weather, event_weather)
                results.to_csv(paths["results"], index=False)
                laps.to_csv(paths["laps"], index=False)
                weather.to_csv(paths["weather"], index=False)
                completed.add((year, circuit))
            except RateLimitExceededError as exc:
                raise RuntimeError(
                    "FastF1 rate limit reached. Rerun; complete events are checkpointed."
                ) from exc

    expected = sum(
        len(
            fastf1.get_event_schedule(year).loc[
                lambda table: (table["EventFormat"] != "testing") & (table["RoundNumber"] > 0)
            ]
        )
        for year in years
    )
    if len(completed) < expected:
        raise RuntimeError(f"Raw extraction incomplete: {len(completed)}/{expected} events")
    print(
        f"Raw extraction complete: {len(results)} result rows, "
        f"{len(laps)} lap rows, {len(weather)} weather rows"
    )
    return {"results": results, "laps": laps, "weather": weather}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=[2021, 2022, 2023])
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--cache-dir", default="f1_cache")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    collect_raw_dataset(args.years, args.raw_dir, args.cache_dir, args.force)


if __name__ == "__main__":
    main()
