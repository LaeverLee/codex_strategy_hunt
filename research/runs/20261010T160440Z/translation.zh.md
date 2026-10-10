# Codex 研究輪次：20261010T160440Z

本輪檢查兩個完整來源，零候選。沒有呼叫 MiniMax；沒有生成或提交簡化策略。

## 來源 1
https://github.com/Superior-Trade/superior-skills/blob/9d41db54b231f77e35610a73230eaeffcb456215/skills/bollinger-reverter-4h/SKILL.md

4h 布林均值回歸，雙向；BB20/2σ、RSI14、ADX14<25；2%止損。原退出含0/240/720/1440分鐘分級ROI，现有引擎只有固定止盈或訊號退出。原市場为USDC線性合約，移植BTCUSD反向合約須獨立變體；不宣稱忠實重現。來源參考config另有ROI覆寫，需核實優先順序。

## 來源 2
https://gist.github.com/sonnyparlin/558d486a1d996e42759d3f68dbc384c0

1h OBV/7期均線與RSI進場，原設定為動態ROI、15%止損、達4%後追蹤停損、限價進出及ignore_roi_if_buy_signal。未提供BTC特定配置；賣出函式未完成。現有引擎不支持其完整退出與成交行為，不補出不存在的規則。