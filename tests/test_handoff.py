"""Portable handoff invariants; does not require server credentials or write research rows."""
import ast
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('quality_policy',ROOT/'engine/quality_policy.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)

class HandoffTests(unittest.TestCase):
    def test_return_threshold_is_inclusive_and_not_annualized(self):
        metrics={'return_pct':50.,'trade_count':30,'profit_factor':1.1,'sharpe_ratio':0.5,'drawdown_pct':15.}
        self.assertTrue(policy.passes_metrics(metrics))
        metrics['return_pct']=49.9999
        self.assertFalse(policy.passes_metrics(metrics))

    def test_other_quality_gates_are_not_bypassed_by_high_return(self):
        metrics={'return_pct':100.,'trade_count':30,'profit_factor':1.1,'sharpe_ratio':0.5,'drawdown_pct':15.}
        for key,value in [('trade_count',29),('drawdown_pct',15.1),('profit_factor',1.09)]:
            with self.subTest(key=key):
                changed=dict(metrics);changed[key]=value
                self.assertFalse(policy.passes_metrics(changed))

    def test_engine_and_skill_scripts_have_valid_syntax(self):
        paths=list((ROOT/'engine').glob('*.py'))+list((ROOT/'skills/btc-strategy-research/scripts').glob('*.py'))
        self.assertGreater(len(paths),5)
        for p in paths:
            with self.subTest(path=p):ast.parse(p.read_text(encoding='utf-8'))

    def test_no_model_dispatcher_in_exported_runtime_or_receiver(self):
        files=[ROOT/'engine/lab_runtime.py',ROOT/'skills/btc-strategy-research/scripts/submit_candidate.py',ROOT/'engine/candidate_validation.py']
        for p in files:
            tree=ast.parse(p.read_text(encoding='utf-8'))
            imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
            self.assertNotIn('hunt_v6',imports)
            self.assertNotIn('anthropic',imports)

    def test_connection_template_contains_no_credential_value(self):
        cfg=json.loads((ROOT/'skills/btc-strategy-research/templates/connection.example.json').read_text(encoding='utf-8'))
        self.assertNotIn('password',cfg)
        self.assertNotIn('token',cfg)
        self.assertIn('REPLACE',cfg['identity_file'])

if __name__=='__main__':unittest.main()
