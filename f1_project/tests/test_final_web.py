"""API parity with the actual saved notebook artifact and dataset."""
import unittest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from intelligence.api import app
from intelligence.final_model import FINAL, parse_time


class FinalWebTest(unittest.TestCase):
    def test_input_validation_cutoff_audit_and_training_isolation(self):
        self.assertAlmostEqual(parse_time('1:32.123'), 92.123)
        for value in [True, False, None, '', 'abc', '1:99', 0, -1, np.nan, np.inf]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_time(value)
        with TestClient(app) as client:
            ds = app.state.dataset
            quality = client.get('/api/v1/quality').json()
            self.assertEqual(quality['raw_laps'], quality['kept_laps'] + sum(quality['removals'].values()))
            self.assertTrue(ds.laps.loc[ds.laps.usable, 'pre_qualifying'].all())
            self.assertTrue(ds.features.loc[ds.features.event_id.eq('2021-10'), 'FP2_Time'].isna().all())
            report = app.state.bundle['report']
            parts = [set(p['events']) for p in report['partitions'].values()]
            for i, part in enumerate(parts):
                for other in parts[i + 1:]:
                    self.assertFalse(part & other)
            model_data = pd.read_csv(FINAL / 'processed/model_dataset.csv')
            training = model_data.loc[model_data.Year.isin([2021, 2022]), app.state.bundle['features']]
            np.testing.assert_allclose(app.state.bundle['model'].named_steps['preprocess'].mean_, training.mean())
            self.assertEqual(len(training), 868)
            self.assertIsNone(report['interval'])

    def test_saved_model_api_and_analytics(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/v1/health').json()['model'], app.state.bundle['selected'])
            self.assertEqual(app.state.bundle['features'], ['FP1_Time', 'FP2_Time', 'FP3_Time', 'circuit_length_km', 'corner_count'])
            circuits = app.state.bundle['circuits']
            self.assertEqual(circuits.loc['2022-06', 'corner_count'], 16)
            self.assertEqual(circuits.loc['2023-07', 'corner_count'], 14)
            self.assertEqual(circuits.loc['2022-17', 'corner_count'], 23)
            self.assertEqual(circuits.loc['2023-15', 'corner_count'], 19)
            features = app.state.features
            expected = app.state.predictions
            for r in features.loc[features.event_id.eq('2023-12') & features.predictable].itertuples():
                payload = {s: {'time': getattr(r, s+'_Time')}
                           for s in ['FP1', 'FP2', 'FP3'] if pd.notna(getattr(r, s+'_Time'))}
                payload['event_id'] = r.event_id
                response = client.post('/api/v1/predict/custom', json=payload)
                self.assertEqual(response.status_code, 200, response.text)
                prediction = expected.loc[expected.event_id.eq(r.event_id) & expected.Driver.eq(r.Driver), 'prediction'].iloc[0]
                self.assertAlmostEqual(response.json()['prediction'], prediction, places=8)
                self.assertIsNone(response.json()['lower'])
                scenario = client.post('/api/v1/predict', json={'event_id': r.event_id, 'driver': r.Driver})
                self.assertEqual(scenario.status_code, 200, scenario.text)
                self.assertAlmostEqual(scenario.json()['delta'], 0)
            saved = pd.read_csv(FINAL / 'processed/test_predictions_2023.csv')
            np.testing.assert_allclose(saved.Prediction, expected.prediction)
            for event in app.state.dataset.events.event_id:
                for endpoint in ['', '/predictions', '/laps']:
                    response = client.get('/api/v1/events/' + event + endpoint)
                    self.assertEqual(response.status_code, 200, response.text[:200])
            for endpoint in ['/api/v1/evaluation', '/api/v1/quality', '/api/v1/events/2023-12/export?kind=predictions']:
                self.assertEqual(client.get(endpoint).status_code, 200)
            for payload in [{}, {'FP1': {'time': -1}}, {'FP1': {'time': '1:99'}}, {'FP1': {'time': 90, 'tyre_life': -1}}]:
                self.assertEqual(client.post('/api/v1/predict/custom', json={'event_id': '2023-01', **payload}).status_code, 422)
            self.assertEqual(client.post('/api/v1/predict/custom', json={'event_id': '2023-01', 'FP1': {'time': '1:30.000'}}).status_code, 200)
            self.assertEqual(client.post('/api/v1/predict/custom', json={'event_id': 'unknown', 'FP1': {'time': 90}}).status_code, 422)
            self.assertEqual(client.post('/api/v1/predict/custom', json={'event_id': '2023-01', 'FP1': {'time': 90, 'compound': 'SOFT'}}).status_code, 422)


if __name__ == '__main__':
    unittest.main()
