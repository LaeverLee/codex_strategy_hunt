# 研究與整合設定

## GitHub 移交版入口

本 Skill 已收錄於 LaeverLee/codex_strategy_hunt。另一個 Codex 從 repo 的 AGENTS.md、memory/CURRENT_STATE.md、docs/BOOTSTRAP.md 開始。下列 C:/Users/250726 路徑只描述原電腦，請改用自己的 checkout 與 config/connection.local.json；確定性引擎副本在 repo 的 engine/。

提交工具已改用 candidate_validation.py，不依賴舊 hunt_v6。install 會部署該 helper。既有远端接收端當時仍是較早版，repo工具更新不代表遠端全量覆蓋，接手須先核對。

- 工作區：C:/Users/250726/Documents/Codex/2026-10-08/new-chat-2
- 規劃文件：outputs/BTC優質自動交易策略研究Skill計畫書.md
- 引擎副本：work/strategy-v7/；先檢查 strategy_quality.py、backtest_v6.py、lab_records.py、quality_policy.py。
- 新 Supabase：jygaprrhtuwzffyrnipt。使用 Supabase 連接工具核實欄位，資料不得混入舊專案。
- 伺服器：8.209.199.155；使用已設定認證，若無非互動認證則記錄整合待完成，不把對話密碼寫入文件或脚本。
- Kubernetes namespace：environment-69e0f4905ae0a69725e92658。先重新發現 Running pod，不硬編碼 pod 名稱。
- 遠端引擎：/home/node/.openclaw/workspace/strategy_lab_v7/sessions。
- 遠端私密連線：上層 connection.json；只供程式使用，不輸出內容。
- 搜尋排程 ID：52d4bf14-f93e-4f00-8e67-fc770aef6929。切換前先備份并验证提交入口；使用 CLI help 發現操作，不直接改 SQLite。
- 回測排程 ID：a8f06958-e766-4780-b4bf-a845977100b7。保留現有回測功能。
- Strategy Hunt Webhook ID：1495818814024318976；回測 Webhook ID：1500532618310058055。完整 URL 僅能從既有私密 job/config 讀取，不寫入 Skill。
- 頻道 1494372820380160100 自動 announce 維持停用。

現況：策略 1 已來源審查失敗，因生成做空與無依據 4h 設定。不得列為有效原策略結果。現有 backtest helper 不代表可以接受任意生成程式，必須讀取規格驗證器與候選 sidecar 格式後銜接。

每輪先研究一個假設；完整來源不足可換一次來源，仍不足則記錄原因。成本較高的回測只針對通過審查的候選。不要無限制增加候選、調參或反覆重跑已有結果。
