# Codex 研究輪次：20261010T162341Z

本輪檢查兩個完整來源，零候選。沒有呼叫 MiniMax；沒有生成或提交簡化策略。

## 來源 1
https://github.com/PeetCrypto/freqtrade-stuff/blob/f6c38def0b2fe01d8d42e47740cdeab53511527b/SupertrendStrategy.py

1h多重Supertrend方向、StochRSI及EMA90过滤，訊號退出，99%止損及100倍ROI被來源註解為inactive，但非真正關閉。缺BTC專用實際配置、原成交設定及pandas_ta版本，不能把原多幣USDT結果當BTC反向合約結果。保留可研究規則，尚未生成可信完整重現。

## 來源 2
https://nirius.dev/projects/freqtrade/report.pdf

30m RSI/MACD預設範例，雙向、固定10%ROI與10%止損；作者結果是多幣USDT線性合約、3同時持倉、1m細節及hyperopt後績效。報告未列重現該結果所需完整最終參數；不可將預設參數當最佳策略。報告52.66%為組合USDT收益，回撤38.24%，不代表BTC計價達50%，且作者指出不及同期買入持有。保留作規則研究，不提交為已重現績效策略。