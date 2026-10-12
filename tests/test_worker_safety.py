import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'engine'))
import strategy_quality as sq

class WorkerSafetyTests(unittest.TestCase):
    def test_environment_and_cwd_are_isolated(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, FAKE_CANARY_SECRET='fake-value', PYTHONPATH='/fake', HTTPS_PROXY='fake-proxy'):
            sq.run_worker([sys.executable, '-c', 'import os; assert "FAKE_CANARY_SECRET" not in os.environ; assert "PYTHONPATH" not in os.environ; assert "HTTPS_PROXY" not in os.environ; assert os.getcwd()==os.environ["HOME"]'], d, 5)
    def test_normal_numpy_pandas_signals_unchanged(self):
        df=pd.DataFrame({'close':[1.,2.,1.,3.]})
        code='''import numpy as np
import pandas as pd
def get_signals(df):
    return df.close > df.close.shift(1), df.close < df.close.shift(1)
def get_exits(df):
    return df.close < df.close.shift(1), df.close > df.close.shift(1)
'''
        actual=sq.evaluate_isolated(code,df)
        expected=(np.array([False,True,False,True]), np.array([False,False,True,False]))
        for a,b in zip(actual,(*expected,expected[1],expected[0])): np.testing.assert_array_equal(a,b)
    def test_output_and_timeout_are_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'output limit'):
                sq.run_worker([sys.executable,'-c','import os\nwhile True: os.write(1,b"x"*8192)'],d,5)
            with self.assertRaisesRegex(ValueError,'timeout'):
                sq.run_worker([sys.executable,'-c','import time; time.sleep(10)'],d,.2)
    def test_timeout_kills_descendants(self):
        with tempfile.TemporaryDirectory() as d:
            pidpath=Path(d)/'child.pid'
            code='import subprocess,time,pathlib; p=subprocess.Popen(["'+sys.executable+'","-c","import time; time.sleep(30)"]); pathlib.Path("child.pid").write_text(str(p.pid)); time.sleep(30)'
            with self.assertRaisesRegex(ValueError,'timeout'): sq.run_worker([sys.executable,'-c',code],d,.5)
            pid=int(pidpath.read_text())
            for _ in range(20):
                stat=Path(f'/proc/{pid}/stat')
                if not stat.exists() or stat.read_text().split()[2]=='Z': break
                time.sleep(.05)
            else: self.fail('Descendant still running')
