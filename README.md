# Codex BTC Strategy Hunt

本專案交接一套「由 Codex 直接研究、翻譯與生成 BTC 策略，再送到 Zeabur OpenClaw 回測」的系統。使用者希望找到可靠的自動交易策略，研究門檻包含 BTC 累積淨报酬 ≥50%。**不呼叫 MiniMax 生成策略、不自動實盤下單、不保證找到盈利策略。**

## 給完全沒有前文的 Codex

先讀 [AGENTS.md](AGENTS.md)，再依序讀：

1. [目前狀態與接手任務](memory/CURRENT_STATE.md)：已做、未做、不能誤認的事項。
2. [使用者意圖與固定決策](memory/USER_INTENT_AND_DECISIONS.md)。
3. [Skill](skills/btc-strategy-research/SKILL.md)。
4. [操作手冊](docs/Codex策略研究Zeabur操作與移交手冊.md)：連線、提交、回測、通知、恢復。
5. [新 Agent 啟動步驟](docs/BOOTSTRAP.md)：本 repo 的可執行命令與認證設定。
6. [對話交接紀錄](docs/CONVERSATION_HISTORY_REDACTED.md)：使用者問題、答覆脈絡與修正。
7. [已知限制與下一步](docs/KNOWN_LIMITATIONS_AND_NEXT_STEPS.md)。

先核實目前服務狀態，再繼續研究；不要從頭重建 Supabase、覆蓋現有策略或把規劃功能當成已實作。

## 工作流程

Codex 搜尋並閱讀來源 → 中文翻譯與完整規格 → 生成程式 → 對照來源審查 → 遠端 dry-run → 正式 submit → OpenClaw 回測 Worker → Supabase 分段結果 → 各自 Discord 通知。

待回測目錄：

```text
/home/node/.openclaw/workspace/strategy_lab_v7/sessions/pytest/Strategy
```

只有通過審查、完成資料庫登記的候選進入此目錄。回測完成後檔案移到 Research_Qualified 或 Research_Rejected；空資料夾不必然代表排程故障。

## 專案內容

| 路徑 | 用途 |
|---|---|
| skills/btc-strategy-research | 可安裝 Skill、連線／提交工具及模板 |
| engine | 不含模型 API 調用的確定性引擎副本，含規格檢查、回測與同步 |
| docs | 最新計畫、操作手冊、開機步驟、對話與限制 |
| docs/archive | 歷史掃描及部署報告；只作背景證據 |
| memory | 使用者決策、狀態與研究快照 |
| research/runs | 第一輪 Codex 研究紀錄、來源指紋及中文分析 |
| config | 現有 schema 參考；不可直接套用到已存在資料庫 |
| tests | 本地可執行的政策、格式及無模型依賴檢查 |

## 目前實際證據

交接日期：2026-10-11（Asia/Taipei）。

- 已設定原電腦 SSH 金鑰，非互動連線、pod 發現與資料庫 health 通過。
- 接收程式已部署，真實 4h 訓練資料 dry-run 通過，錯誤方向候選會被拒絕。
- Codex 研究排程 btc-codex 已建立，每 15 分鐘；這個排程位於原電腦／原對話，不會跟 repo 自動轉移。
- 第一輪直接閱讀兩個來源，均因引擎不支持完整退出行為而拒絕；零候選、未提交回測。
- 該輪 journal 已同步新 Supabase；搜尋結果 Discord HTTP 204。
- 第一個真實 Codex 候選的正式提交及完整回測 **尚未驗證**。舊搜尋排程是否仍啟用須重查。
- 沒有已驗證的合格盈利策略，策略 1 來源審查失敗。

## 憑證与可攜性

本 repo 不含 SSH 密碼、私鑰、完整 Discord Webhook、Supabase Worker token 或模型 API 金鑰。主機、專案、namespace 與目的地 ID 是交接資訊，不能代替登入授權。不同 Codex 必須配置自己的存取權。

本 repo 的 engine 是整理過的可交接副本，**不是整套 OpenClaw 或伺服器備份**。完整行情、遠端狀態 SQLite 與私密設定仍在現有後台。原研究來源全文保留於原本本地快照，本 repo 保存連結、commit／hash 與分析，避免重發第三方全文。

對話紀錄是可見上下文的去敏感重建稿，含明確使用者要求及已知答覆，並非平台逐字聊天匯出。無法取得的歷史助理逐字內容不會捏造。
