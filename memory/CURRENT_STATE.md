# 当前状态（2026-10-11交接快照）

本文件是快照，不是实时狀態。接手先health并查排程，不能據快照宣稱現在正在執行。

## 已完成

- 隔離旧策略与旧Supabase，建立新專案jygaprrhtuwzffyrnipt、10張表及私密Worker。
- research-v7回測：因果性檢查、下一根開盤成交、BTC反向合約、成本／資金費用、完整分段、浮動回撤與重播同步。
- 50%門檻已部署，源審查失敗不算合格。
- 原Strategy Hunt每15分鐘、回測每5分鐘；搜索零候選通知規則已修改。
- 两個OpenClaw job的delivery.mode已設none并清除to，1494372820380160100不再自動announce。
- 建立可匯出btc-strategy-research Skill與Codex heartbeat btc-codex。
- 原电腦專用SSH金鑰、bridge health、Ready pod發現、codex_submit.py部署、lab_records變體保留修改。
- 真實4h訓練資料dry-run與錯誤方向拒絕通過；fixture未寫入研究資料庫。
- 第一次Codex直接研究：codex_20261010T160440Z（UTC，台灣2026-10-11 00:04:40啟動），兩來源拒絕、0新候選。journal同步成功，搜尋Discord HTTP204。

## 策略1

原先生成候選1，review_status=rejected、backtest/source status=source_review_failed。原來源為joseporiolcarne/backtraderalerts的src/strategies/rsi_crossover.py，commit20c45d2c8bbdb6fb4452ca17dc78667ac6bc343d。原規則只做多，生成器加入了不存在的做空與退出；4h來自框架支援列表而非策略設定。

保存的debug績效：train -6.0117%，validation -4.1422%，test -10.0352%、DD19.3435%、24交易、PF0.6869、Sharpe -0.3933；1.5倍成本return -10.4563%。這不是原始策略有效績效，不用來評估來源优劣，也不能列為盈利候選。

## 尚未完成／不可宣稱

- 策略2已正式提交、核DB且完成回測，qualified=false；無合格策略。
- 舊OpenClaw搜尋已備份及停用，回測保留；接手仍須重查即時狀態。
- 日線、持有時間動態ROI、trailing stop、限價成交、風險匹配基準等尚未支援。
- 買入持有／固定趨勢基準與完整參數穩健性還是計畫。
- 前向模拟和實盤未啟動；无已验证合格盈利策略。

## 最近研究結論

1. Superior-Trade bollinger-reverter-4h：4h BB/RSI/ADX均值回歸，原始含時間分級ROI且市場為USDC線性合約。現有引擎無法忠實重現；不能刪ROI後稱原策略。
2. sonnyparlin PrawnstarOBV gist：1h OBV/RSI、動態ROI、追蹤止損、限價進出、缺BTC具體配置；原賣出函式未完成。拒絕生成完整重現。

下一輪優先找明确BTC、單一持倉、訊號退出或固定SL/TP的完整來源。連續遇到不支援退出時要回報引擎能力瓶頸，不能只增加搜尋量。

## 快照區別

曾查到164research_runs、2856source_attempts、1candidate、7evaluation；是較早查詢快照，不是当下计数。source_attempts包含重複來源。

本repo的engine/lab_runtime.py是去除MiniMax/hunt dispatcher的移交版，尚未取代遠端runtime；其他engine文件來自部署工作副本。必須核對遠端hash再做部署，不能一鍵覆蓋現有系统。

## 最近更新

第三輪首個真實Codex候選策略2（1h雙動量5/10、controlled_variant、外部母来源、parent_version=null）通過dry-run並queued=true，Supabase核對完成。舊搜尋停用、回測保留。第四輪核實回測完成：validation -78.443%、test -88.7498%、test DD88.8033%、cost_stress -92.7841%，qualified=false。DB的strategy_hunt仍discovered但已有七組evaluation，不能用status代替結果。第四輪日線Donchian/EMA/ADX來源因週期、追蹤及反轉能力拒絕，0新候選；通知HTTP204。

使用者後續要求Codex回測排程Skill，已提供計畫，尚未啟用；本次只優化找策略GitHub移交。Supabase資料模型、99欄實際快照、恢復/查詢與最近三輪證據已補齊。
