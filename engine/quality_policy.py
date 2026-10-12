"""User-selected net cumulative BTC return gates; shared by discovery and backtesting."""
import json
import math

POLICY = 'net_btc_cumulative_50_v1'
THRESHOLDS = {'min_return_pct':50.0,'min_trades':30,'min_pf':1.10,'min_sharpe':0.5,'max_dd_pct':15.}
CONTRACT = 'Binance COIN-M BTCUSD_PERP'


def strict_json(text):
    def reject(value):
        raise ValueError('Nonfinite JSON number rejected')
    value = json.loads(text, parse_constant=reject)
    # Also rejects overflowing JSON exponents such as 1e999.
    json.dumps(value, allow_nan=False)
    return value


def valid_metrics(metrics):
    if not isinstance(metrics, dict) or metrics.get('return_currency') != 'BTC':
        return False
    for key in ['return_pct', 'trade_count', 'profit_factor', 'sharpe_ratio', 'drawdown_pct']:
        value = metrics.get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            return False
    return (type(metrics['trade_count']) is int and metrics['trade_count'] >= 0
            and 0 <= metrics['drawdown_pct'] <= 100 and metrics['profit_factor'] >= 0
            and metrics['return_pct'] >= -100)


def passes_metrics(metrics):
    return (valid_metrics(metrics)
        and metrics['return_pct'] >= THRESHOLDS['min_return_pct']
        and metrics['trade_count'] >= THRESHOLDS['min_trades']
        and metrics['profit_factor'] >= THRESHOLDS['min_pf']
        and metrics['sharpe_ratio'] >= THRESHOLDS['min_sharpe']
        and metrics['drawdown_pct'] <= THRESHOLDS['max_dd_pct'])


def validate_result(result):
    """Validate all seven segments before qualification or any ledger write."""
    json.dumps(result, allow_nan=False)
    if (result.get('contract') != CONTRACT or result.get('return_currency') != 'BTC'
            or result.get('cost_model', {}).get('contract_type') != 'inverse'
            or result.get('cost_model', {}).get('return_currency') != 'BTC'):
        raise ValueError('Result requires inverse BTCUSD contract and BTC currency throughout')
    folds = result.get('test_folds')
    if not isinstance(folds, list) or len(folds) != 3:
        raise ValueError('Result requires exactly three test folds')
    segments = [result.get(k) for k in ['train', 'validation', 'test', 'cost_stress']] + folds
    if any(not isinstance(s, dict) or not valid_metrics(s.get('metrics')) for s in segments):
        raise ValueError('Invalid, missing, nonfinite or non-BTC segment metrics')
    if result.get('data', {}).get('contract_type', 'inverse') != 'inverse' or result.get('data', {}).get('return_currency', 'BTC') != 'BTC':
        raise ValueError('Dataset contract/currency mismatch')
