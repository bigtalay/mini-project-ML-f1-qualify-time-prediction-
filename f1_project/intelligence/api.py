"""Typed API and same-origin production frontend. No FastF1 calls at startup."""
from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .data import ROOT, Dataset, records
from .ml import ARTIFACTS, ensure_artifacts, scenario


class Event(BaseModel):
    event_id: str
    year: int
    round: int
    name: str
    circuit_id: str
    circuit: str
    country: str
    location: str
    format: str


class Result(BaseModel):
    Driver: str
    Team: str | None = None
    Position: float | None = None
    Q1: float | None = None
    Q2: float | None = None
    Q3: float | None = None
    QualiTime: float | None = None
    source_row: int


class Session(BaseModel):
    session: str
    start_utc: str
    end_utc: str
    before_qualifying: bool
    lap_count: int
    timing_source: str


class Weather(BaseModel):
    Time: float
    AirTemp: float | None = None
    TrackTemp: float | None = None
    Rainfall: float | None = None
    Humidity: float | None = None


class Overview(BaseModel):
    event: Event
    results: list[Result]
    sessions: list[Session]
    weather: list[Weather]


class Lap(BaseModel):
    lap_id: str
    source_row: int
    event_id: str
    Driver: str | None = None
    Team: str | None = None
    Session: str
    LapNumber: float | None = None
    LapTime: float | None = None
    Time: float | None = None
    Sector1Time: float | None = None
    Sector2Time: float | None = None
    Sector3Time: float | None = None
    SpeedI1: float | None = None
    SpeedI2: float | None = None
    SpeedFL: float | None = None
    SpeedST: float | None = None
    Compound: str | None = None
    TyreLife: float | None = None
    Stint: float | None = None
    usable: bool
    pre_qualifying: bool
    reason: str


class LapPage(BaseModel):
    items: list[Lap]
    total: int
    offset: int
    limit: int


class Comparison(BaseModel):
    driver: str
    count: int
    median: float | None
    iqr: float | None
    enough_laps: bool
    best_lap: Lap | None


class ModelScore(BaseModel):
    model: str
    count: int
    mae: float
    rmse: float


class EventScore(ModelScore):
    event_id: str


class Interval(BaseModel):
    percentiles: list[int]
    residual_lower: float
    residual_upper: float
    calibration_count: int
    test_coverage: float


class Partition(BaseModel):
    rows: int
    events: list[str]


class InputRange(BaseModel):
    min: float
    max: float


class Evaluation(BaseModel):
    selected_model: str
    selection: list[ModelScore]
    test: list[ModelScore]
    per_event: list[EventScore]
    interval: Interval
    partitions: dict[str, Partition]
    selected_features: list[str]
    excluded_test_rows: int
    input_ranges: dict[str, InputRange]


class Quality(BaseModel):
    version: str
    checksums: dict[str, str]
    raw_laps: int
    raw_results: int
    kept_laps: int
    removals: dict[str, int]
    overlapping_flags: dict[str, int]
    after_qualifying_laps: int
    pre_qualifying_laps: int
    result_duplicates: int
    missing_targets: int
    no_practice_rows: int
    feature_rows: int
    missing_features: dict[str, int]


class PredictionRow(BaseModel):
    event_id: str
    Driver: str
    QualiTime: float | None = None
    FP1_Time: float | None = None
    FP2_Time: float | None = None
    FP3_Time: float | None = None
    prediction: float | None = None
    error: float | None = None
    lower: float | None = None
    upper: float | None = None
    predictable: bool


class ScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    driver: str
    overrides: dict[Literal["FP1_Time", "FP2_Time", "FP3_Time"], float] = Field(default_factory=dict)


class ScenarioResponse(BaseModel):
    prediction: float
    baseline: float
    delta: float
    lower: float
    upper: float
    warnings: list[str]
    inputs: dict[str, float | None]
    model: str


SORTS = Literal["Time", "LapTime", "LapNumber", "Driver", "Sector1Time", "Sector2Time", "Sector3Time", "SpeedST", "TyreLife"]


@asynccontextmanager
async def lifespan(app):
    app.state.dataset = Dataset()
    app.state.bundle = ensure_artifacts(app.state.dataset)
    app.state.predictions = pd.read_csv(ARTIFACTS / "predictions.csv")
    yield


app = FastAPI(title="F1 Weekend Intelligence", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def timing(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["Server-Timing"] = f"app;dur={(time.perf_counter()-started)*1000:.1f}"
    return response


def dataset():
    return app.state.dataset


def event_or_404(event_id):
    try:
        return dataset().event(event_id)
    except KeyError:
        raise HTTPException(404, "ไม่พบรายการแข่งนี้")


def driver_list(event_id, drivers):
    selected = list(dict.fromkeys(filter(None, (drivers or "").split(","))))
    known = set(dataset().results.loc[dataset().results.event_id.eq(event_id), "Driver"])
    if len(selected) > 4 or set(selected) - known:
        raise HTTPException(422, "เลือกนักขับในรายการนี้ได้ไม่เกิน 4 คน")
    return selected


@app.get("/api/v1/health")
def health():
    return {"status": "ready", "dataset": dataset().manifest["version"], "model": app.state.bundle["selected"]}


@app.get("/api/v1/events", response_model=list[Event])
def events():
    return records(dataset().events)


@app.get("/api/v1/events/{event_id}", response_model=Overview)
def overview(event_id: str):
    event_or_404(event_id)
    return dataset().overview(event_id)


@app.get("/api/v1/events/{event_id}/laps", response_model=LapPage)
def laps(event_id: str, drivers: str = "", session: Literal["FP1", "FP2", "FP3"] | None = None,
         compound: str | None = None, usable: bool = True, search: str = "", sort: SORTS = "Time",
         descending: bool = False, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=4000)):
    event_or_404(event_id)
    frame = dataset().filtered_laps(event_id, driver_list(event_id, drivers), session, compound, usable, search, sort, descending)
    return {"items": records(frame.iloc[offset:offset+limit]), "total": len(frame), "offset": offset, "limit": limit}


@app.get("/api/v1/events/{event_id}/compare", response_model=list[Comparison])
def comparison(event_id: str, drivers: str, session: Literal["FP1", "FP2", "FP3"] | None = None, compound: str | None = None, search: str = ""):
    event_or_404(event_id)
    selected = driver_list(event_id, drivers)
    if not 2 <= len(selected) <= 4:
        raise HTTPException(422, "กรุณาเลือกนักขับ 2–4 คน")
    return dataset().compare(event_id, selected, session, compound, search)


@app.get("/api/v1/evaluation", response_model=Evaluation)
def evaluation():
    return app.state.bundle["report"]


@app.get("/api/v1/quality", response_model=Quality)
def quality(event_id: str | None = None):
    if event_id:
        event_or_404(event_id)
    return dataset().quality(event_id)


@app.get("/api/v1/events/{event_id}/predictions", response_model=list[PredictionRow])
def predictions(event_id: str):
    event = event_or_404(event_id)
    if event["year"] != 2023:
        return []
    rows = dataset().features.loc[dataset().features.event_id.eq(event_id), ["event_id", "Driver", "QualiTime", "FP1_Time", "FP2_Time", "FP3_Time", "predictable"]]
    selected = app.state.predictions
    selected = selected.loc[selected.event_id.eq(event_id) & selected.model.eq(app.state.bundle["selected"])]
    return records(rows.merge(selected[["event_id", "Driver", "prediction", "error", "lower", "upper"]], on=["event_id", "Driver"], how="left"))


@app.post("/api/v1/predict", response_model=ScenarioResponse)
def what_if(payload: ScenarioRequest):
    event_or_404(payload.event_id)
    try:
        return scenario(dataset(), app.state.bundle, payload.event_id, payload.driver, payload.overrides)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get("/api/v1/events/{event_id}/export")
def export(event_id: str, kind: Literal["laps", "results", "predictions", "audit"] = "laps",
           drivers: str = "", session: Literal["FP1", "FP2", "FP3"] | None = None,
           compound: str | None = None, usable: bool = True, search: str = "", sort: SORTS = "Time", descending: bool = False):
    event_or_404(event_id)
    selected = driver_list(event_id, drivers)
    if kind in ["laps", "audit"]:
        frame = dataset().filtered_laps(event_id, selected, session, compound, usable if kind == "laps" else False, search, sort, descending)
    elif kind == "results":
        frame = dataset().results.loc[dataset().results.event_id.eq(event_id) & ~dataset().results.duplicate].sort_values("Position")
        if selected:
            frame = frame.loc[frame.Driver.isin(selected)]
        if search:
            frame = frame.loc[frame.Driver.str.contains(search, case=False, regex=False) | frame.Team.str.contains(search, case=False, regex=False)]
    else:
        frame = pd.DataFrame(predictions(event_id))
        if selected and not frame.empty:
            frame = frame.loc[frame.Driver.isin(selected)]
    # UTF-8 BOM for spreadsheet programs; guard strings that spreadsheets treat as formulas.
    safe = frame.copy()
    for c in safe.select_dtypes(include=["object", "string"]):
        safe[c] = safe[c].map(lambda v: "'"+v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v)
    return Response(safe.to_csv(index=False).encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{event_id}-{kind}.csv"'})


static = Path(os.environ.get("F1_FRONTEND", ROOT.parent / "frontend/dist"))
if static.exists():
    app.mount("/", StaticFiles(directory=static, html=True), name="frontend")
