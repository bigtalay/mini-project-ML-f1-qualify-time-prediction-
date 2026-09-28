import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from intelligence.data import Dataset, hashes
from intelligence import tyre_model as tm


class TyreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = Dataset()
        cls.before = hashes(cls.data.path / 'raw')
        cls.features = tm.build_features(cls.data)
        cls.bundle = tm.ensure_artifacts(cls.data)

    def test_same_lap_and_cutoff(self):
        lookup = self.data.laps.set_index('lap_id')
        for s in tm.SESSIONS:
            rows = self.features.loc[self.features[f'{s}_lap_id'].notna()]
            source = lookup.loc[rows[f'{s}_lap_id']]
            np.testing.assert_allclose(rows[f'{s}_Time'], source.LapTime)
            np.testing.assert_allclose(rows[f'{s}_TyreLife'], source.TyreLife, equal_nan=True)
            self.assertEqual(rows[f'{s}_Compound'].fillna('').tolist(), source.Compound.fillna('').tolist())
            self.assertTrue((source.usable & source.pre_qualifying).all())
        laps = self.data.laps.iloc[:2].copy()
        laps['Driver'], laps['Session'], laps['LapTime'] = 'VER', 'FP1', 90
        laps['usable'], laps['pre_qualifying'] = True, True
        laps['Compound'] = ['HARD', 'SOFT']
        test = SimpleNamespace(laps=laps.iloc[::-1], results=self.data.results)
        row = tm.build_features(test).query("event_id == '2021-01' and Driver == 'VER'").iloc[0]
        self.assertEqual(row.FP1_Compound, 'HARD')

    def test_imputation_and_fit_isolation(self):
        row = self.features.loc[self.features.predictable].iloc[:1].copy()
        row[['FP1_Time', 'FP1_Compound', 'FP1_TyreLife']] = [80, 'SOFT', 4]
        row[['FP2_Time', 'FP2_Compound', 'FP2_TyreLife']] = [90, 'HARD', 9]
        row[['FP3_Time', 'FP3_Compound', 'FP3_TyreLife']] = [np.nan, np.nan, np.nan]
        filled = tm.fill_sessions(row)
        self.assertEqual(filled.iloc[0].FP3_filled_from, 'FP1')
        self.assertEqual(filled.iloc[0].FP3_Compound, 'SOFT')
        self.assertEqual(filled.iloc[0].FP3_TyreLife, 4)
        row['FP2_TyreLife'] = -1
        processor = tm.fit_processor(row, 'Time + tyres')
        self.assertEqual(processor['medians']['FP2_TyreLife'], 4)
        original_mean = processor['scaler'].mean_.copy()
        row['FP1_Time'] = 500
        tm.transform(row, processor)
        np.testing.assert_array_equal(original_mean, processor['scaler'].mean_)
        self.assertEqual(len(tm.FEATURES['Time']), 3)
        self.assertEqual(len(tm.FEATURES['Time + tyres']), 9)
        self.assertFalse(set(tm.FEATURES['Time + tyres']) & {'Driver', 'Team', 'Year', 'circuit_id', 'QualiTime'})

    def test_selection_and_roundtrip(self):
        report = self.bundle['report']
        for feature_set, winner in report['winners'].items():
            candidates = [s for s in report['selection'] if s['model'].startswith(feature_set + ' / ')]
            self.assertEqual(winner, min(candidates, key=lambda s: s['rmse'])['model'])
        partitions = [set(p['events']) for p in report['partitions'].values()]
        for i, part in enumerate(partitions):
            for other in partitions[i+1:]:
                self.assertFalse(part & other)
        row = self.features.query("Year == 2023 and predictable").iloc[0]
        request = tm.row_sessions(row)
        prediction = tm.custom_predict(self.bundle, request)['prediction']
        experiment = self.bundle['experiments']['Time + tyres']
        expected = experiment['models'][experiment['winner']].predict(tm.transform(row.to_frame().T, experiment['processor']))[0]
        self.assertAlmostEqual(prediction, expected)
        with tempfile.TemporaryDirectory() as folder:
            path = folder + '/model.joblib'
            joblib.dump(self.bundle, path)
            self.assertAlmostEqual(tm.custom_predict(joblib.load(path), request)['prediction'], prediction)
        self.assertEqual(self.before, hashes(self.data.path / 'raw'))

    def test_custom_api_and_validation(self):
        from intelligence.api import app
        with TestClient(app) as client:
            request = {'FP1': {'time': '1:30.000', 'compound': 'SOFT', 'tyre_life': None}}
            response = client.post('/api/v1/predict/custom', json=request)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertAlmostEqual(response.json()['prediction'], tm.custom_predict(self.bundle, request)['prediction'])
            self.assertGreaterEqual(len(response.json()['imputations']), 3)
            for bad in [{}, {'FP1': {'time': 0}}, {'FP1': {'time': '1:75'}}, {'FP1': {'time': 90, 'tyre_life': -1}}, {'FP4': {'time': 90}}, {'driver': 'VER', **request}]:
                self.assertEqual(client.post('/api/v1/predict/custom', json=bad).status_code, 422)
            unknown = client.post('/api/v1/predict/custom', json={'FP1': {'time': 90, 'compound': 'TEST_UNKNOWN'}}).json()
            self.assertEqual(unknown['inputs']['FP1_Compound'], 'UNKNOWN')
            for field in ['time', 'tyre_life']:
                values = {'time': 90, field: True}
                self.assertEqual(client.post('/api/v1/predict/custom', json={'FP1': values}).status_code, 422)

    def test_training_boundaries_and_artifact_reuse(self):
        calls = []
        original = tm.fit_models

        def traced_fit(frame, feature_set):
            calls.append(set(frame.event_id))
            return original(frame, feature_set)

        with tempfile.TemporaryDirectory() as folder:
            with patch.object(tm, 'fit_models', side_effect=traced_fit):
                bundle = tm.train(self.data, folder)
            report = bundle['report']
            training = set(report['partitions']['training']['events'])
            selection = set(report['partitions']['selection']['events'])
            self.assertEqual(calls, [training, training | selection] * 2)
            with patch.object(tm, 'train', side_effect=AssertionError('must reuse saved artifact')):
                reloaded = tm.ensure_artifacts(self.data, folder)
            self.assertEqual(reloaded['fingerprint'], bundle['fingerprint'])
            csv = pd.read_csv(folder + '/predictions.csv')
            chosen = csv.loc[csv.model.eq(bundle['selected'])].iloc[0]
            feature = self.features.loc[self.features.event_id.eq(chosen.event_id) & self.features.Driver.eq(chosen.Driver)].iloc[0]
            value = tm.custom_predict(reloaded, tm.row_sessions(feature))['prediction']
            self.assertAlmostEqual(value, chosen.prediction)


if __name__ == '__main__':
    unittest.main()
