"""Development-only data validation; no search/model API dependencies."""
import pandas as pd
from strategy_quality import ROOT

def load_validation(tf, warmup):
    files=[p for p in sorted((ROOT/'pytest/k_line_data'/tf).glob('*.csv')) if int(p.stem)<2024]
    if not files: raise ValueError('Development data before 2024 unavailable')
    df=pd.concat([pd.read_csv(p) for p in files],ignore_index=True).sort_values('timestamp')
    duplicated=df[df.timestamp.duplicated(False)]
    if not duplicated.empty and (duplicated.groupby('timestamp')[['open','high','low','close','volume']].nunique().max(axis=1)>1).any():
        raise ValueError('Conflicting candle duplicates')
    df=df.drop_duplicates('timestamp').reset_index(drop=True)
    if len(df)<max(500,warmup*3):raise ValueError('Insufficient development data')
    return df.iloc[-min(len(df),max(4096,warmup*3)):].reset_index(drop=True)
