# 階段 0／1 修正證據（2026-10-12 UTC）

## 修正前基線

| Repo | HEAD | numpy | pandas | 既有測試 |
|---|---|---|---|---|
| H | 290c964027329006c5398a3a79b84c7b8e65d2e6 | 2.4.6 | 3.0.6 | 5 通過、0 失敗 |
| B | 6d2e6491c44b779d06d24c5eec37ec5a50de6921 | 2.4.6 | 3.0.6 | 11 通過、0 失敗 |

兩 repo 均在 Linux 執行 `python3 -X utf8 -m unittest discover -s tests -v`；未連 Zeabur、Supabase、Discord，未操作排程、資料庫或歷史結果。GitHub push 僅發布程式，沒有部署執行環境。

## 實作與限制

- #2：提交重試在既有 hunt/backtest 兩把非阻塞鎖內讀 queue、archive、result、候選 DB hash 及回測狀態。已發布／終態不再發布，`queued_this_call=false`；`queued` 僅表示目前核實仍在佇列。收據損壞、不完整 staging 或衝突停止，需後續 reconciliation，不自動重建。重試不呼叫 sync_all 或重送通知。這是安全止血，不是完整持久狀態機。
- #3＋#5：正式計算只接受 inverse BTCUSD；頂層、成本、七段 metrics 需 BTC；新 dataset manifest 記錄 inverse/BTC，既有缺少這兩個 dataset 輔助欄位時仍須其他契約證據全部有效，有欄位則核對。七段各驗證數值型別、有限值、DD 0–100、整數非負交易數、非負 PF、收益不低於 -100%。政策門檻及 PF=99 保持不變。JSON 解析及寫入拒絕非有限值；同步前先驗證，不改寫歷史錯標資料。B audit 維持獨立實作。
- #7A：固定環境白名單、临時 cwd、無 stdin、單執行緒 BLAS、CPU／2 GiB 位址空間／程序數／檔案大小／檔案描述符限制、stdout+stderr 合計 64 KiB、timeout 及所有退出清理程序群組。只接受大小受限的四個 bool 向量。不回顯 worker 診斷以避免秘密外洩。仍同 UID、同檔案系統且未禁網路；不是 OS 沙箱。RLIMIT_NPROC 對 root 等情況不構成可靠程序隔離，完整隔離屬 #7B。
- #12：即使 approved，fixture 也不能正式回測或同步 candidate/result/discovery 帳本。B bridge 寫入前在 Ready pod 唯讀核對舊搜尋關閉、announce 關閉及無 fixture；run 要求舊回測關閉，sync 不領取工作所以允許舊回測保持啟用。此輪不執行 bridge；未接管排程。preflight 是前置快照，不是完整跨排程交易式互斥；完整 preflight／狀態機仍在後續階段。

## 共用引擎維護

`config/common-engine.sha256` 是七個共用檔案完整清單與鎖定 hash；兩 repo manifest 與七檔逐一一致。本次以 H 維護來源同步至 B，兩 repo 各自 commit。unit test 驗證各自副本符合 manifest；GitHub 憑證缺 workflow scope，首次 push 被拒絕，改保存 `config/engine-integrity.workflow-template.yml` 為未啟用 CI 範本；取得 workflow 權限後才能移到 `.github/workflows/` 啟用。沒有把範本標成已部署 CI。每次引擎修改必須同步兩 repo 並更新相同 manifest。跨 repo 比較仍需雙工作副本核對，不能把單 repo manifest CI 宣稱成跨 repo 自動查核。

## 離線驗證

涵蓋 queued=true/false 已發布／封存／已有結果重試、不完整／衝突證據、七段異常數值與幣別、inclusive 門檻、stress 嚴格正收益、fixture 零 DB 副作用、排程 gate、假秘密環境、numpy/pandas 訊號等價、輸出／記憶體耗盡、timeout 子程序群组清理、異常訊號輸出。測試只使用假 Backend 與临時目錄。

最終驗收：H 24 通過、0 失敗；B 30 通過、0 失敗。沒有新增策略、回測真實資料、通知、改成本或成交規則。
