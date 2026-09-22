import io
import unittest

import pandas as pd
from fastapi.testclient import TestClient

from intelligence.api import app


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def test_all_events_and_special_weekends(self):
        events = self.client.get('/api/v1/events').json()
        self.assertEqual(len(events), 66)
        for event in events:
            response = self.client.get('/api/v1/events/' + event['event_id'])
            self.assertEqual(response.status_code, 200)
            positions = [r['Position'] for r in response.json()['results'] if r['Position'] is not None]
            self.assertEqual(positions, sorted(positions))
        self.assertEqual(self.client.get('/api/v1/events/no-event').status_code, 404)

    def test_csv_and_paging_match_shared_analysis(self):
        query = 'drivers=VER,HAM&session=FP2&compound=SOFT&sort=LapTime'
        endpoint = '/api/v1/events/2023-01/'
        page = self.client.get(endpoint + 'laps?' + query).json()
        csv = pd.read_csv(io.BytesIO(self.client.get(endpoint + 'export?' + query).content))
        self.assertEqual(page['total'], len(csv))
        self.assertEqual([x['lap_id'] for x in page['items']], csv.lap_id.tolist())
        comparison = self.client.get(endpoint + 'compare?drivers=VER,HAM&session=FP2&compound=SOFT').json()
        self.assertEqual(sum(r['count'] for r in comparison), len(csv))
        self.assertEqual(self.client.get(endpoint + 'laps?limit=0').status_code, 422)
        self.assertEqual(self.client.get(endpoint + 'laps?sort=bogus').status_code, 422)

    def test_missing_session_and_invalid_input(self):
        empty = self.client.get('/api/v1/events/2023-04/laps?session=FP3').json()
        self.assertEqual(empty['items'], [])
        for body in [dict(event_id='2021-01', driver='VER'), dict(event_id='2023-01', driver='XXX'),
                     dict(event_id='2023-01', driver='VER', overrides={'FP1_Time': -2}),
                     dict(event_id='2023-04', driver='VER', overrides={'FP3_Time': 80})]:
            self.assertEqual(self.client.post('/api/v1/predict', json=body).status_code, 422)
        self.assertEqual(self.client.get('/api/v1/events/2021-01/predictions').json(), [])
        response = self.client.post('/api/v1/predict', json=dict(event_id='2023-01', driver='VER'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['delta'], 0)


if __name__ == '__main__':
    unittest.main()
