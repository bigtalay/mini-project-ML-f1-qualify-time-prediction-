"""API parity with the actual saved notebook artifact and dataset."""
import unittest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from intelligence.api import app
from intelligence.final_model import FINAL


class FinalWebTest(unittest.TestCase):
    def test_saved_model_api_and_analytics(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/v1/health').json()['model'], 'SVR')
            features = app.state.features
            expected = app.state.predictions
            for r in features.loc[features.event_id.eq('2023-12') & features.predictable].itertuples():
                payload = {s: {'time': getattr(r, s+'_Time'),
                               'compound': getattr(r, s+'_Compound') if pd.notna(getattr(r, s+'_Compound')) else None,
                               'tyre_life': getattr(r, s+'_TyreLife') if pd.notna(getattr(r, s+'_TyreLife')) else None}
                           for s in ['FP1', 'FP2', 'FP3'] if pd.notna(getattr(r, s+'_Time'))}
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
                self.assertEqual(client.post('/api/v1/predict/custom', json=payload).status_code, 422)
            self.assertEqual(client.post('/api/v1/predict/custom', json={'FP1': {'time': '1:30.000', 'compound': 'SOFT'}}).status_code, 200)


if __name__ == '__main__':
    unittest.main()
