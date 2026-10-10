# 已知限制與按順序接手工作

## 優先工作

1. 重查health、排程、queue、receipts与Supabase，不以交接快照代替即時狀態。
2. 用明确BTC、支援週期、訊號／固定SLTP來源完成一個可信候選；審查後dry-run→submit→資料庫核對→首次完整回測。
3. 確認提交、檔案、父子記錄一致後備份並停旧搜尋，保留回測；避免两模型搜索並行。
4. 將每輪journal及通知整理為可重用工具；已有第一輪實作證據，但目前不是一般bridge notification子命令。
5. 強化提交恢復、journal終態、跨檔案／資料庫競態与server-side去重。
6. 加基準、參數敏感度、跨週期比較與前向模擬；每項先明確定義再實作。

## 接收程式限制

- 文件+DB不是單一交易。db_committed在候選登記後才設true，但receipt與consumer之間仍有中斷窗口；先檢查已歸檔版本，不能盲重試覆寫。
- 目前來源审查approved是Codex自己另一步對照，不是獨立模型／第三方審核；技術檢查只能證明指定項目。
- 去重以訓練訊號指紋與已批准sidecar为基礎，並非完整跨機器研究去重。
- version取值與DB列表查詢受API分頁影響；長期運行應改為資料庫原子version分配或完整分頁。已知少量候選環境不代表可无限擴張。
- sync_all journal依hash重播；候選已提交後不能原地改code。变体要新版本。
- candidate_validation假設年度CSV檔名為數字年份，数据格式变化須更新。
- 現有failure journal .rejected.json不進完整evaluation，只留兼容status及本地原因，後續應完善。
- static code audit與受限子程序不是OS沙箱，不能運行不信任的外部程式。

## 引擎與市場限制

仅5m/15m/30m/1h/4h，單倉位邏輯。缺日線、ROI階梯、trailing、限價成交、盤中順序、複雜加倉與多標的组合。從USDT/USDC線性移到BTCUSD反向合約要標變體，不能宣稱一樣績效。

資金費用以bar-open時間及價格代理；缺order book／intrabar。已看過2025–2026历史結果不是fresh holdout。低頻30交易門檻可能造成樣本不足拒绝，不能偷偷放寬。

## 資料與文件限制

config/schema-reference.sql為當時schema合成參考，含历史migration片段；不是幂等迁移，勿對已有DB直接執行。先用Supabase工具核對實際schema与policy。

archive報告是不同階段快照。副本中的runtime已去模型API調用，但远端runtime未據此全量替換。repo文件变更不代表live部署。今後每次部署記錄hash、備份與驗證结果。

原電腦本地完整來源快照未連同第三方全文发布；repo有commit與hash供重新取得。首次研究state是snapshot，需初始化自己的當前state。

## 排程與通知限制

Codex本機排程可用性取決於實際app／主機及使用額度，不能當作雲端24/7保障。驗證當前官方排程要求，不任意承諾離線執行。

原排程不隨repo匯入；需避免原/新机器同時研究。每輪通知包含0候選，與保持Codex聊天安靜不是同一件事。

## 驗收證據

原部署曾報40測試及真實4h整合成功；這是歷史已记录结果，不是本repo新測試覆盖。此repo的tests只验证確定性政策與移交檔案，不能证明整個遠端提交系統完備。實盤完全不在驗收範圍。

## 2026-10-11更新優先

首個真實候選整合已完成，策略2不合格，舊搜尋已停用。新Codex回測Skill尚未接管。資料模型文件揭露目前未填finished_at、可能滯後status及backtest鍵不含資料/政策hash等限制；不得當作已修復。
