import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import backtest_v6 as bt
import lab_records

class FixtureSafetyTests(unittest.TestCase):
    def test_approved_fixture_rejected_before_data_or_execution(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'1_Strategy_Gold.py';p.write_text('invalid code')
            p.with_suffix('.json').write_text(json.dumps(dict(db_committed=True,source_url='integration-fixture-only',source_review={'approved':True})))
            with patch.object(bt,'load_data') as load, self.assertRaisesRegex(ValueError,'Fixture'):
                bt.run_candidate(p)
            load.assert_not_called()
    def test_fixture_cannot_sync_any_ledger(self):
        for function, record in [(lab_records.sync_candidate, {'source_url':'integration-fixture-only'}), (lab_records.sync_result, {'source_url':'integration-fixture-only'}), (lab_records.sync_discovery, {'attempts':[{'url':'integration-fixture-only'}]})]:
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'record.json';p.write_text(json.dumps(record))
                with patch.object(lab_records,'write') as write, self.assertRaisesRegex(ValueError,'Fixture'):
                    function(None,p)
                write.assert_not_called()
