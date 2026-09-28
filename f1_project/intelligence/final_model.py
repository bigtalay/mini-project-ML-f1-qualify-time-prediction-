"""Serve the saved final.ipynb pipeline; never train or download at web startup."""
import hashlib
import joblib
import numpy as np
import pandas as pd

from .data import ROOT, Dataset, records, flag
from .tyre_model import parse_time

SESSIONS = ["FP1", "FP2", "FP3"]
TIMES = [f"{s}_Time" for s in SESSIONS]
CIRCUIT_FEATURES = ["circuit_length_km", "corner_count"]
FEATURES = TIMES + CIRCUIT_FEATURES
from .ml import metrics

FINAL = ROOT / 'data/final'


def load_final():
    bundle = joblib.load(FINAL / 'models/qualifying-circuit.joblib')
    if bundle.get('version') != 'practice-circuit-v1' or bundle['features'] != FEATURES:
        raise ValueError('Run final.ipynb to save the practice-circuit-v1 model')
    circuit_file = FINAL / 'reference/circuits.csv'
    if hashlib.sha256(circuit_file.read_bytes()).hexdigest() != bundle['circuit_checksum']:
        raise ValueError('Circuit reference changed since training')
    bundle['circuits'] = pd.read_csv(circuit_file).set_index('event_id')
    for name, expected in bundle['raw_checksums'].items():
        if hashlib.sha256((FINAL / 'raw' / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Raw changed since notebook training: {name}')
    bundle['selected'] = type(bundle['model'].named_steps['model']).__name__
    ds = Dataset.__new__(Dataset)
    ds.manifest = {'version': 'final-notebook-2021-2023', 'sha256': bundle['raw_checksums']}
    events = pd.read_csv(FINAL / 'raw/events.csv').rename(columns={
        'Year': 'year', 'RoundNumber': 'round', 'EventName': 'name',
        'Country': 'country', 'Location': 'location', 'EventFormat': 'format'})
    events['circuit'] = events.location
    events['circuit_id'] = events.location
    if set(events.event_id) != set(bundle['circuits'].index) or not bundle['circuits'].index.is_unique:
        raise ValueError('Circuit reference must match every event exactly once')
    ds.events = events.drop(columns=['circuit_id']).merge(bundle['circuits'].reset_index(), on='event_id', validate='one_to_one')
    if ds.events[CIRCUIT_FEATURES].isna().any().any():
        raise ValueError('Circuit reference does not cover events')
    ds.sessions = pd.read_csv(FINAL / 'raw/sessions.csv').rename(columns={'Session': 'session', 'source_path': 'timing_source'})
    for c in ['start_utc', 'end_utc']:
        ds.sessions[c] = pd.to_datetime(ds.sessions[c], utc=True)
    q_start = ds.sessions.loc[ds.sessions.session.eq('Q')].set_index('event_id').start_utc
    ds.sessions['before_qualifying'] = ds.sessions.end_utc.lt(ds.sessions.event_id.map(q_start))
    ds.results = pd.read_csv(FINAL / 'raw/qualifying_results.csv').rename(columns={'Abbreviation': 'Driver', 'TeamName': 'Team'})
    ds.results['source_row'] = np.arange(len(ds.results)) + 2
    ds.results['duplicate'] = ds.results.duplicated(['event_id', 'Driver'])
    for c in ['Q1', 'Q2', 'Q3']:
        ds.results[c] = pd.to_timedelta(ds.results[c]).dt.total_seconds()
    ds.results['QualiTime'] = ds.results[['Q1', 'Q2', 'Q3']].where(lambda x: x > 0).min(axis=1)
    ds.laps = pd.read_csv(FINAL / 'processed/lap_audit.csv', low_memory=False)
    for c in ['Time', 'Sector1Time', 'Sector2Time', 'Sector3Time']:
        ds.laps[c] = pd.to_timedelta(ds.laps[c]).dt.total_seconds()
    ds.laps['lap_id'] = 'lap-' + ds.laps.source_row.astype(str)
    ds.laps['usable'] = ds.laps.reason.eq('kept')
    ds.laps['pre_qualifying'] = flag(ds.laps.before_q)
    ds.weather = pd.DataFrame(columns=['event_id', 'Time', 'AirTemp', 'TrackTemp', 'Rainfall', 'Humidity'])
    ds.features = pd.read_csv(FINAL / 'processed/features_before_fill.csv')
    ds.features['predictable'] = ds.features[TIMES].notna().any(axis=1)
    for s in SESSIONS:
        ds.features[f'{s}_lap_id'] = ds.features[f'{s}_source_row'].map(lambda v: f'lap-{int(v)}' if pd.notna(v) else None)
    ds.lap_groups = dict(tuple(ds.laps.groupby('event_id', sort=False)))
    # Recompute reports with this exact artifact, so stale CSV scores cannot mislabel the model.
    model_data = pd.read_csv(FINAL / 'processed/model_dataset.csv')
    testing = model_data.loc[model_data.Year.eq(2023)].copy()
    testing['prediction'] = bundle['model'].predict(testing[bundle['features']])
    testing['error'] = testing.prediction - testing.QualiTime
    testing['model'] = bundle['selected']
    testing['lower'], testing['upper'] = np.nan, np.nan
    tuning = pd.read_csv(FINAL / 'processed/tuning_validation.csv').sort_values('RMSE').drop_duplicates('Model')
    bundle['report'] = {
        'selected_model': bundle['selected'],
        'selection': [{'model': r.Model, 'count': int(model_data.Year.eq(2022).sum()), 'mae': r.MAE, 'rmse': r.RMSE} for r in tuning.itertuples()],
        'test': [{'model': bundle['selected'], **metrics(testing.QualiTime, testing.prediction)},
                 {'model': 'Practice baseline', **metrics(testing.QualiTime, testing[TIMES].min(axis=1))}],
        'per_event': [{'event_id': event, 'model': bundle['selected'], **metrics(g.QualiTime, g.prediction)} for event, g in testing.groupby('event_id')],
        'interval': None, 'groups': [], 'winners': {'Time + circuit': bundle['selected']},
        'partitions': {name: {'rows': len(g), 'events': sorted(g.event_id.unique())}
                       for name, year in [('training', 2021), ('selection', 2022), ('test', 2023)]
                       for g in [model_data.loc[model_data.Year.eq(year)]]},
        'selected_features': bundle['features'], 'raw_features': bundle['features'],
        'excluded_test_rows': int(ds.features.Year.eq(2023).sum() - len(testing)),
        'input_ranges': {c: {'min': float(bundle['numeric_min'][c]), 'max': float(bundle['numeric_max'][c])} for c in FEATURES},
    }
    return ds, bundle, testing


def custom_predict(bundle, payload):
    event_id = payload.get('event_id')
    if event_id not in bundle['circuits'].index:
        raise ValueError('เลือกสนามและปีที่มีข้อมูลอ้างอิง')
    supplied = {s: payload.get(s) for s in SESSIONS if payload.get(s) is not None}
    if not supplied:
        raise ValueError('ต้องมี Practice อย่างน้อยหนึ่ง session')
    times = {s: parse_time(v['time']) for s, v in supplied.items()}
    donor = min(times, key=lambda s: (times[s], SESSIONS.index(s)))
    row, imputations, warnings = {}, [], []
    for s in SESSIONS:
        row[f'{s}_Time'] = times.get(s, times[donor])
        if s not in times:
            imputations.append(f'{s}: เติมเวลาจาก {donor}')
    circuit = bundle['circuits'].loc[event_id]
    for c in CIRCUIT_FEATURES:
        row[c] = float(circuit[c])
    for c in FEATURES:
        if not bundle['numeric_min'][c] <= row[c] <= bundle['numeric_max'][c]:
            warnings.append(f'{c}: อยู่นอกช่วงข้อมูลฝึก')
    frame = pd.DataFrame([row])[FEATURES]
    predicted = float(bundle['model'].predict(frame)[0])
    if not np.isfinite(predicted) or predicted <= 0:
        raise ValueError('โมเดลให้เวลาที่ไม่สมเหตุผลสำหรับ input นี้')
    return {'prediction': predicted, 'lower': None, 'upper': None, 'model': bundle['selected'],
            'inputs': records(frame)[0], 'imputations': imputations, 'warnings': warnings}


def scenario(dataset, bundle, event_id, driver, overrides, session_overrides=None):
    rows = dataset.features.loc[dataset.features.event_id.eq(event_id) & dataset.features.Driver.eq(driver)]
    if rows.empty or not event_id.startswith('2023-'):
        raise ValueError('เลือกนักขับและรายการปี 2023 ที่มีข้อมูล')
    row = rows.iloc[0]
    sessions = {s: {'time': row[f'{s}_Time']} for s in SESSIONS if pd.notna(row[f'{s}_Time'])}
    baseline = custom_predict(bundle, {'event_id': event_id, **sessions})['prediction']
    for key, value in overrides.items():
        s = key.split('_')[0]
        if s not in sessions:
            raise ValueError('ไม่มี session นี้ก่อน Qualifying')
        sessions[s]['time'] = value
    for s, value in (session_overrides or {}).items():
        if s not in sessions:
            raise ValueError('ไม่มี session นี้ก่อน Qualifying')
        sessions[s] = value
    result = custom_predict(bundle, {'event_id': event_id, **sessions})
    return {**result, 'baseline': baseline, 'delta': result['prediction'] - baseline}
