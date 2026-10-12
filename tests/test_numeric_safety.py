import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
import quality_policy as policy
import backtest_v6 as bt
import lab_records
from strategy_quality import atomic_json


def passing():
    m = dict(return_currency='BTC', return_pct=50., trade_count=30, profit_factor=1.1, sharpe_ratio=.5, drawdown_pct=15.)
    return dict(contract=policy.CONTRACT, return_currency='BTC', cost_model=dict(contract_type='inverse', return_currency='BTC'),
                **{k: {'metrics': dict(m)} for k in ['train', 'validation', 'test', 'cost_stress']},
                test_folds=[{'metrics': dict(m)} for _ in range(3)])

class NumericSafetyTests(unittest.TestCase):
    def test_exact_gates_and_strict_positive_stress(self):
        r = passing(); self.assertTrue(bt.qualify(r)[0])
        r['cost_stress']['metrics']['return_pct'] = 0
        self.assertFalse(bt.qualify(r)[0])
        r = passing(); r['test_folds'][0]['metrics']['return_pct'] = 0
        self.assertTrue(bt.qualify(r)[0])
        r['test_folds'][1]['metrics']['return_pct'] = 0
        self.assertFalse(bt.qualify(r)[0])
    def test_all_seven_segments_reject_invalid_metrics(self):
        for index in range(7):
            for key, values in {'return_pct':[float('nan'), float('inf'), float('-inf'), '50', None, True, -101], 'trade_count':[30., -1, True], 'drawdown_pct':[-1, 101], 'profit_factor':[-1, float('inf')], 'sharpe_ratio':[None]}.items():
                for value in values:
                    r = passing(); segments = [r[k] for k in ['train', 'validation', 'test', 'cost_stress']] + r['test_folds']
                    segments[index]['metrics'][key] = value
                    with self.subTest(index=index,key=key,value=value), self.assertRaises((ValueError, TypeError)):
                        bt.qualify(r)
    def test_contract_and_currency_mismatches(self):
        for mode in ['linear', 'unknown', '']:
            with patch.dict(os.environ, STRATEGY_CONTRACT_TYPE=mode), self.assertRaises(ValueError):
                bt.require_inverse()
        with patch.dict(os.environ, STRATEGY_CONTRACT_TYPE='inverse'): bt.require_inverse()
        for location in ['top', 'cost', 'data', 'segment']:
            r=passing()
            if location=='top': r['return_currency']='USD'
            elif location=='cost': r['cost_model']['contract_type']='linear'
            elif location=='data': r['data']={'return_currency':'USD'}
            else: r['test_folds'][2]['metrics']['return_currency']='USD'
            with self.assertRaises(ValueError): policy.validate_result(r)
    def test_json_parse_and_serialization_reject_nonfinite(self):
        for value in ['NaN', 'Infinity', '-Infinity', '1e999']:
            with self.assertRaises(ValueError): policy.strict_json('{"v":'+value+'}')
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'result.json'
            with self.assertRaises(ValueError): atomic_json(path, {'v':float('inf')})
            self.assertFalse(path.exists())
    def test_invalid_sync_has_no_db_side_effects(self):
        r=passing();r['train']['metrics']['return_currency']='USD'
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'result.json';path.write_text(json.dumps(r))
            with patch.object(lab_records, 'write') as write, self.assertRaises(ValueError):
                lab_records.sync_result(None,path)
            write.assert_not_called()
    def test_missing_segment_and_fold_count(self):
        for field in ['train','validation','test','cost_stress','test_folds']:
            r=passing(); del r[field]
            with self.assertRaises(ValueError): bt.qualify(r)
