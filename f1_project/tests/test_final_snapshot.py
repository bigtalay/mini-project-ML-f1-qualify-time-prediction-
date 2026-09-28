"""Cell 2.4 must skip all published events, without network or a FastF1 cache."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import nbformat
import pandas as pd


class SnapshotTest(unittest.TestCase):
    def test_download_cell_skips_all_66_events(self):
        root = Path(__file__).resolve().parents[1]
        raw = root / 'data/final/raw'
        events = pd.read_csv(raw / 'events.csv')
        self.assertEqual(len(events), 66)
        self.assertEqual(set(events.Year), {2021, 2022, 2023})
        notebook = nbformat.read(root / 'final.ipynb', as_version=4)
        code = next(c.source for c in notebook.cells if 'download' in c.metadata.get('tags', []))
        load_event = Mock(side_effect=AssertionError('Snapshot should not download'))
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stdout(io.StringIO()) as output:
            scope = dict(RAW=raw, PROCESSED=Path(temporary), events=events, pd=pd, json=json,
                         load_event=load_event, display=lambda *args: None,
                         csv_hashes=lambda folder: {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                                    for p in sorted(folder.glob('*.csv'))})
            exec(compile(code, 'final.ipynb:download', 'exec'), scope)
        load_event.assert_not_called()
        self.assertTrue(scope['failed'].empty)
        self.assertEqual(output.getvalue().count('มี CSV ครบแล้ว'), 66)


if __name__ == '__main__':
    unittest.main()
