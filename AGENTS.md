# 給接手 Codex 的操作指示

先依 README 的順序讀 memory 與文件。此 repo 的記憶優先於歷史 archive 的說法；使用者新指示再優先於 repo。

## 使用者要什麼

由 Codex 本身直接搜尋、讀來源、翻譯、生成及審查 BTC 自動策略，不呼叫 MiniMax。生成且通過審查後直接排到現有 Zeabur OpenClaw 待回測目錄，使用既有 Python 引擎、新 Supabase 與各自 Discord 管道。只做研究，不實盤下單。

## 接手必做

1. 讀 memory/CURRENT_STATE.md、memory/USER_INTENT_AND_DECISIONS.md 與 Skill。
2. 找本機 config/connection.local.json；不存在則按 BOOTSTRAP 配置自己的 SSH 存取權，不能使用別台電腦私鑰。
3. health 確認新 Supabase 專案；重新發現 Ready pod，不硬編碼 pod 名稱。
4. 核對遠端引擎／接收程式版本、兩個 OpenClaw 排程、佇列、已完成结果及当前 Codex 排程。
5. 讀已有研究 state 與來源指紋，避免重複搜尋相同拒絕來源。
6. 按來源證據生成候選，通過 dry-run 再 submit。queued=true 才能報告已排隊。
7. 舊搜尋已在策略2核對後停用；核對即時狀態並維持停用，回測排程保留。
8. 讀docs/SUPABASE_DATA_MODEL.md與docs/RECOVERY_AND_QUERIES.md；不能只靠strategy_hunt.status判回測完成。

## 固定限制

- 新 Supabase 專案 jygaprrhtuwzffyrnipt；不能重新建立或混用舊專案。
- 50% 是 BTC 計價累積淨收益，驗證與測試各達標；不是年化或USD收益。
- 原始重現與controlled_variant分開，來源只做多不能加做空，缺週期不能隨意稱原始設定。
- 過去已看過的測試期不宣稱是新的獨立留出資料。
- 目前支援5m/15m/30m/1h/4h；日線、動態ROI、追蹤止損等功能尚未完成。
- 每輪最多一個候選與兩個變體；規則不足可換一次來源，仍不足就保存零候選。
- 搜尋結果每輪送到Webhook ID1495818814024318976，即使零候選。回測到1500532618310058055。
- 頻道1494372820380160100自動announce停用，勿重新打開。
- 不存／提交密碼、private key、Worker token或完整Webhook。產出與日誌也要去敏感。
- 不刪鎖、不編造績效、不以整合fixture污染研究資料庫、不把planned標成deployed。

## 文件與操作要求

更新遠端引擎前備份、核對本地副本差異並驗證。engine/為Linux回測程式；Windows不提供fcntl，需在Linux容器跑相關整合測試。本地檢查命令：`python -X utf8 -m unittest discover -s tests -v`。

完成每輪後保存來源、中文分析、程式與source review、提交／通知狀態；建立可重試紀錄。研究結果沒有变化時不重複發Codex聊天訊息，但Discord每輪通知是使用者明確要求。

不要求每輪一定找到策略；拒絕完整規則但引擎不支持的來源後，記錄能力瓶頸，不改寫成假重現。未经新指示不要擅自擴大下單或資金權限。
