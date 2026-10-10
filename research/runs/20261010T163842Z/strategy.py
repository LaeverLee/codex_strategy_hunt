import numpy as np

def get_signals(df):
    fast = df.close - df.close.shift(5)
    slow = df.close - df.close.shift(10)
    return ((slow > 0) & (fast > 0)).to_numpy(dtype=bool), ((slow < 0) & (fast < 0)).to_numpy(dtype=bool)

def get_exits(df):
    fast = df.close - df.close.shift(5)
    slow = df.close - df.close.shift(10)
    return ((slow < 0) | (fast < 0)).to_numpy(dtype=bool), ((slow > 0) | (fast > 0)).to_numpy(dtype=bool)
