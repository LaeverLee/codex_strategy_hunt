import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('submit', Path(__file__).resolve().parents[1] / 'skills/btc-strategy-research/scripts/submit_candidate.py')
submit = importlib.util.module_from_spec(spec); spec.loader.exec_module(submit)

class Backend:
    def request(self, table, **kwargs):
        return [{'code_hash': hashlib.sha256(b'code\n').hexdigest()}] if table == 'research_candidates' else []

class RetryTests(unittest.TestCase):
    def test_published_and_completed_receipts_never_republish(self):
        for queued in [False, True]:
            for folder in ['Strategy', 'Research_Rejected', 'Research_Qualified']:
                with self.subTest(queued=queued, folder=folder), tempfile.TemporaryDirectory() as d:
                    root = Path(d); path = root / 'pytest' / folder / '2_Strategy_Gold.py'
                    path.parent.mkdir(parents=True); path.write_bytes(b'code\n')
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    path.with_suffix('.json').write_text(json.dumps({'code_hash': digest, 'db_committed': True}))
                    before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
                    result = submit.retry_state(root, {'version': 2, 'content_hash': 'same', 'queued': queued}, 'same', digest, Backend())
                    self.assertFalse(result['queued_this_call'])
                    self.assertEqual(result['queued'], folder == 'Strategy')
                    self.assertEqual(before, {p: p.read_bytes() for p in root.rglob('*') if p.is_file()})
    def test_missing_corrupt_or_conflicting_evidence_stops(self):
        with tempfile.TemporaryDirectory() as d:
            for saved in [{'version': 2, 'content_hash': 'same'}, {'version': 2, 'content_hash': 'different'}, {'content_hash': 'same'}]:
                with self.assertRaises((RuntimeError, ValueError)):
                    submit.retry_state(Path(d), saved, 'same', 'hash', Backend())

    def test_receipt_false_result_finished_never_requeues(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); path=root/'pytest/research_results/2.json';path.parent.mkdir(parents=True)
            digest=hashlib.sha256(b'code\n').hexdigest();path.write_text(json.dumps({'code_hash':digest}))
            result=submit.retry_state(root,{'version':2,'content_hash':'same','queued':False},'same',digest,Backend())
            self.assertEqual(result['current_state'],'completed')
            self.assertFalse(result['queued'])
            self.assertFalse((root/'pytest/Strategy').exists())
    def test_terminal_and_queue_conflict_requires_reconciliation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'pytest/Strategy/2_Strategy_Gold.py';p.parent.mkdir(parents=True);p.write_bytes(b'code\n')
            digest=hashlib.sha256(p.read_bytes()).hexdigest();p.with_suffix('.json').write_text(json.dumps({'code_hash':digest,'db_committed':True}))
            r=root/'pytest/research_results/2.json';r.parent.mkdir(parents=True);r.write_text(json.dumps({'code_hash':digest}))
            with self.assertRaisesRegex(RuntimeError,'Terminal'):
                submit.retry_state(root,{'version':2,'content_hash':'same'},'same',digest,Backend())
