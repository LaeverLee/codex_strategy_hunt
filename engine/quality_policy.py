"""User-selected net cumulative BTC return gates; shared by discovery and backtesting."""
POLICY = 'net_btc_cumulative_50_v1'
THRESHOLDS = {'min_return_pct':50.0,'min_trades':30,'min_pf':1.10,'min_sharpe':0.5,'max_dd_pct':15.}

def passes_metrics(metrics):
    return (metrics.get('return_pct',float('-inf')) >= THRESHOLDS['min_return_pct']
        and metrics.get('trade_count',0) >= THRESHOLDS['min_trades']
        and metrics.get('profit_factor',0) >= THRESHOLDS['min_pf']
        and metrics.get('sharpe_ratio',float('-inf')) >= THRESHOLDS['min_sharpe']
        and metrics.get('drawdown_pct',float('inf')) <= THRESHOLDS['max_dd_pct'])
