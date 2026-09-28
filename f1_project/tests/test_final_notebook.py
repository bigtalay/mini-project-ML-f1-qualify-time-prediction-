"""Exercise notebook logic on synthetic rows, without network or project data."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import joblib
import nbformat
import numpy as np
import pandas as pd


class FinalNotebookTest(unittest.TestCase):
    def test_cancelled_practice_is_missing_not_failed(self):
        notebook = nbformat.read(Path(__file__).resolve().parents[1] / 'final.ipynb', as_version=4)
        collector = next(c.source for c in notebook.cells if 'collector' in c.metadata.get('tags', []))
        session = SimpleNamespace(
            load=Mock(), api_path='/test/',
            session_info={'StartDate': '2021-09-24T08:00:00Z', 'EndDate': '2021-09-24T09:00:00Z'},
            laps=pd.DataFrame({'Driver': ['HAM'], 'LapTime': ['0 days 00:01:30']}),
            results=pd.DataFrame({'Abbreviation': ['HAM'], 'Q1': ['0 days 00:01:29']}))
        api = SimpleNamespace(get_session=Mock(return_value=session))
        namespace = {'pd': pd, 'fastf1': api}
        exec(compile(collector, 'final.ipynb:collector', 'exec'), namespace)
        event = pd.Series({'Year': 2021, 'RoundNumber': 15, 'event_id': '2021-15',
                           'Session1': 'Practice 1', 'Session2': 'Practice 2',
                           'Session3': 'Practice 3', 'Session4': 'Qualifying', 'Session5': 'Race'})
        with contextlib.redirect_stdout(io.StringIO()):
            laps, results, sessions = namespace['load_event'](event)
        self.assertEqual(set(laps.Session), {'FP1', 'FP2'})
        self.assertFalse(results.empty)
        cancelled = sessions.loc[sessions.Session.eq('FP3')].iloc[0]
        self.assertEqual(cancelled.status, 'cancelled')
        self.assertIsNone(cancelled.start_utc)
        self.assertEqual([call.args[2] for call in api.get_session.call_args_list], ['FP1', 'FP2', 'Q'])
        # An unconfirmed missing session must still fail, not silently become cancelled.
        session.laps = pd.DataFrame()
        with self.assertRaisesRegex(ValueError, 'FP1'):
            namespace['load_event'](event)

    def test_visible_workflow(self):
        notebook = nbformat.read(Path(__file__).resolve().parents[1] / 'final.ipynb', as_version=4)
        nbformat.validate(notebook)
        code = {cell.metadata['tags'][0]: cell.source for cell in notebook.cells if cell.cell_type == 'code'}
        laps, results, events, sessions = [], [], [], []
        for year in [2021, 2022, 2023]:
            for round_number in [1, 2]:
                event_id = f'{year}-{round_number:02d}'
                events.append(dict(event_id=event_id, Year=year, EventName=event_id))
                for session, start, end in [('FP1', '08:00', '09:00'), ('FP2', '10:00', '11:00'),
                                             ('FP3', '12:00', '13:00'), ('Q', '14:00', '15:00')]:
                    if event_id == '2023-01' and session == 'FP3':
                        start, end = '16:00', '17:00'
                    sessions.append(dict(event_id=event_id, Session=session,
                                         start_utc=f'{year}-03-01T{start}:00Z', end_utc=f'{year}-03-01T{end}:00Z'))
                for driver in range(6):
                    base = 80 + round_number * 5 + driver / 3
                    results.append(dict(event_id=event_id, Abbreviation=f'D{driver}',
                                        Q1=str(pd.Timedelta(seconds=base)), Q2=None, Q3=None))
                    for practice in [1, 2, 3]:
                        if event_id == '2021-01' and driver == 0 and practice == 2:
                            continue
                        laps.append(dict(event_id=event_id, Session=f'FP{practice}', Driver=f'D{driver}',
                                         LapTime=str(pd.Timedelta(seconds=base + 5 - practice)),
                                         Compound='SOFT', TyreLife=None if practice == 2 else 3,
                                         Deleted=False, IsAccurate=True, FastF1Generated=False))
        # Equal times with different tyres must not select a later source row.
        laps.append({**laps[0], 'Compound': 'HARD'})
        laps.append(laps[1].copy())
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            namespace = dict(pd=pd, np=np, joblib=joblib, display=lambda *args: None,
                             laps=pd.DataFrame(laps), results=pd.DataFrame(results),
                             events=pd.DataFrame(events), sessions=pd.DataFrame(sessions),
                             PROCESSED=Path(folder), MODELS=Path(folder), YEARS=[2021, 2022, 2023])
            for tag in ['clean', 'cutoff', 'features', 'missing', 'split', 'impute', 'encode',
                        'train', 'tune', 'refit', 'evaluate', 'save', 'predict']:
                if tag == 'save':
                    namespace['raw_checksums'] = {'synthetic': 'test-only'}
                exec(compile(code[tag], f'final.ipynb:{tag}', 'exec'), namespace)
            ranking = namespace['validation_scores']
            self.assertEqual(set(ranking.Model), {
                'Linear Regression', 'Random Forest', 'Gradient Boosting', 'SVR (RBF)'})
            self.assertTrue(np.isfinite(ranking[['MAE', 'RMSE']]).all().all())
            self.assertEqual(namespace['chosen'], namespace['best_tuned'].iloc[0].Model)
            self.assertTrue((namespace['comparison'].RMSE_after <= namespace['comparison'].RMSE_before + 1e-10).all())
            self.assertEqual(namespace['final_model'].named_steps['model'].get_params(),
                             namespace['tuned_estimators'][namespace['chosen']].get_params())
            features = namespace['features']
            self.assertTrue(features.loc[features.event_id.eq('2023-01'), 'FP3_Time'].isna().all())
            first = features.loc[features.event_id.eq('2021-01') & features.Driver.eq('D0')].iloc[0]
            self.assertEqual(first.FP1_Compound, 'SOFT')
            self.assertTrue(pd.isna(first.FP2_Time))
            self.assertEqual(len(namespace['FEATURES']), 9)
            self.assertFalse(set(namespace['FEATURES']) & {'Driver', 'Year', 'event_id', 'Team', 'QualiTime'})
            self.assertTrue(namespace['X_train'].notna().all().all())
            self.assertEqual(set(namespace['train'].Year), {2021})
            self.assertEqual(set(namespace['validation'].Year), {2022})
            self.assertEqual(set(namespace['final_train'].Year), {2021, 2022})
            self.assertTrue((namespace['test'].Year == 2023).all())
            empty = namespace['new_data'].copy()
            empty[namespace['TIMES']] = np.nan
            with self.assertRaises(ValueError):
                namespace['fill_sessions'](empty)


if __name__ == '__main__':
    unittest.main()
