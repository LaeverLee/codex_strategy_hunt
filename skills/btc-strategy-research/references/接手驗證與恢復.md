# 接手驗證與恢復

## 啟動與只讀核對

1. 讀AGENTS、CURRENT_STATE、資料模型及完整操作手冊。認證只從本機config/connection.local.json及遠端私密connection.json讀，不把Token寫進命令示例或Git。
2. 以自己的SSH金鑰執行bridge health，核對新專案jygaprrhtuwzffyrnipt；bridge自動選Ready Pod。
3. 核對Codex研究排程及OpenClaw兩job。舊搜尋52d4bf14-f93e-4f00-8e67-fc770aef6929已停用；回測a8f06958-e766-4780-b4bf-a845977100b7保留。不要因旧手冊的首次接管步驟重新啟用搜尋。
4. 查看Strategy、Research_Qualified、Research_Rejected與結果；只有Strategy空不能判定故障。
5. 對版本查候選review、metadata db_committed及receipt queued；回測完成再查完整result及七組evaluation。

SQL用Supabase有授權的SQL工具執行；一般運作由遠端Backend.request透過私密Worker /rest/v1/<table>。POST upsert以on_conflict+Prefer執行，PATCH限定module。不得把service_role交給策略程式。RLS、角色權限及Worker憑證屬現有部署，不在此任務改動。

```sql
-- 候選、來源審查、實際評估筆數
select c.version,c.research_mode,c.parent_version,c.review_status,h.status,
       count(e.id) as evaluation_count
from research_candidates c join strategy_hunt h using(version)
left join research_evaluations e using(version)
group by c.version,c.research_mode,c.parent_version,c.review_status,h.status;

-- 策略2完整分段摘要：qualified為整套驗收，非該段單獨通過
select split,metrics,qualified,reasons,evaluation_key
from research_evaluations where version='2' order by split;

-- 該候選來源與研究輪
select c.version,r.run_key,a.source_url,a.outcome,a.reason,a.details
from research_candidates c join research_runs r on r.id=c.run_id
left join source_attempts a on a.run_id=r.id where c.version='2';

-- 最近輪次；created timestamp不必然是heartbeat啟動時間
select run_key,kind,status,started_at,finished_at,configuration,summary
from research_runs order by started_at desc limit 10;
```

## 可重試及停止條件

| 情況 | 下一步 | 禁止事項 |
|---|---|---|
| SSH/Pod/Worker不可用 | 完成本地研究；保存未提交並稍後重試；連續2次同失敗先診斷 | 猜Token、關閉host驗證、聲稱已排隊 |
| dry-run失敗 | 保存错误與来源；修正後新内容使用新ID，重新審查 | 直接正式提交、假造approved |
| 正式submit回應丟失 | 同ID同bundle重試；讀遠端receipt及DB | 換ID重複候選 |
| receipt queued=false、已有檔案/DB | 使用接收程式續跑並逐步核對；保留原檔與日誌 | 人工設db_committed=true或刪DB重來 |
| 鎖被占用 | 等下一輪，確認持有程序與時限；記錄未提交 | 刪鎖強搶版本 |
| queued=true但Strategy找不到 | 先查archive、result、DB；可能已回測 | 再放相同py進佇列 |
| DB缺journal/result同步 | 先確認來源檔完整再用已部署sync_all重播；核對主鍵與內容 | 把完整fixture写正式資料 |
| 結果存在但status仍discovered | 以result+evaluation核實；保存欄位不一致待處理 | 僅憑status宣稱仍待回測 |
| 通知失敗 | 保存HTTP結果，只重試通知，成功收據防重送 | 重跑策略回測來觸發通知 |
| source/code hash不一致 | 停止領取，保存證據並回報 | 覆蓋hash假裝一致 |

兩次相同錯誤後先改做診斷，不能無限制重試。通知應去敏感；完整Webhook只從私密設定/既有job讀。通知不能提供不實績效。

## 真實例子與排程交互

策略2：submission_id=codex-20261010T163842Z-dual-momentum-1h，version=2，1h雙向5/10動量；原BTCUSDT移植到BTCUSD反向合約，母來源外部，非完整重現。dry-run validated=true但queued=false；正式submit queued=true，再核DB approved、變體mode及code_hash後停舊搜尋。

程式/metadata原位于pytest/Strategy/2_Strategy_Gold.py及.json；翻譯在codex_submissions/<submission_id>/translation.zh.md；完整回測在pytest/research_results/2.json。實際qualified=false，test-88.7498%、DD88.8033%，因此不能推薦實盤。

研究排程由Codex直接推進每輪研究、來源審查與提交；回測仍由OpenClaw現有每5分鐘job領取。新的Codex回測Skill只有計畫，尚未接管。研究每輪通知1495818814024318976；回測通知1500532618310058055；1494372820380160100保持停用。

repo engine/lab_runtime.py去除模型調度，是移交副本而非遠端runtime；repo接收程式用candidate_validation helper，現有部署曾使用hunt_v6純資料函式（不呼叫模型）。不要一鍵覆蓋runtime，先差異核對與備份。repo bridge install會安裝helper及receiver；只在需要升级時執行，不在每輪研究重裝。
