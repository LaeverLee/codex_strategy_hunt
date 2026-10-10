# Supabase 資料模型與存放流程

核對日期：2026-10-11（Asia/Taipei）。以實際 public schema、submit_candidate.py、lab_records.py 與策略2紀錄核對。新專案 jygaprrhtuwzffyrnipt；舊專案不使用。本文件描述目前實作，不是新資料庫建置指令。

## 1. 資料存在哪裡

| 位置 | 保存內容 | 判讀方式 |
|---|---|---|
| 本地 research-codex/runs/<UTC>/ | 完整來源快照、翻譯、策略、bundle、審查與每輪報告 | 研究證據及尚未提交工作的來源 |
| 本地 research-codex/state.json | 來源hash、最近提交、通知、已知回測 | 去重快取；接手需與遠端核對 |
| 遠端 sessions/codex_submissions/<submission_id>/ | bundle.json、translation.zh.md | 正式提交證據，包含原來源全文及changes |
| 遠端 codex_submissions/<submission_id>.json | content_hash、version、queued | 同次重試的持久收據；不是績效證明 |
| 遠端 goldhuntv2/research/ | source_hash.source.json、run_id.run.json | 可重播研究 journal |
| 遠端 pytest/Strategy/ | 同名py/json，db_committed及規格 | 待回測，不是完整歷史 |
| 遠端 pytest/Research_Qualified 或 Research_Rejected | 完成候選及metadata | 離開佇列不等於遺失 |
| 遠端 pytest/research_results/<version>.json | 完整分段、交易、曲線、資料指紋 | 績效與完成證據；輸出摘要避免巨量曲線 |
| Supabase | 關聯帳本、規格、hash、摘要及每段metrics | 查詢、追查；不是原始CSV或完整策略碼備份 |

根目錄 sessions=/home/node/.openclaw/workspace/strategy_lab_v7/sessions。GitHub只保存去敏感報告、來源連結/commit/hash、分析及自有策略，不包含行情CSV、第三方全文、私密bundle憑證。

## 2. 十張表及欄位字典

下表解釋所有欄位群組。完整型別、nullable及default以 config/schema-columns.snapshot.json 為準（實際只讀查詢99個欄位）；schema-reference.sql是歷史建表參考，不可重跑。

| 表 | 欄位意義與注意事項 |
|---|---|
| ctrl_manager | id識別；module唯一模組(strategy_hunt/backtest)；status執行狀態；current_version/last_version相容進度；updated_at時間。不是佇列本身，搜尋current_version在提交後設為下一可分配版本。 |
| strategy_keywords | id；category研究家族；keyword唯一搜尋詞；is_active啟用；used_count/success_count/last_used_at舊流程計數；created_at建立。success_count不代表盈利。Codex可直接產生研究假設，未必引用keyword_id或更新這些計數。 |
| strategy_hunt | id；version唯一文字版本；file_name遠端檔名；source_url/source_site來源；discovered_at建立；status相容狀態；search_keyword搜尋家族；strategy_description摘要；last_tested_at/notes附註。不保證回測完成會更新status。 |
| backtest_strategy | id；strategy_name；version唯一、連strategy_hunt；timeframe；atr_param相容ATR欄；return_pct/drawdown_pct/win_rate/profit_factor/sharpe_ratio/trade_count摘要；created_at；status/first_err結果或錯誤。不能代替完整分段評估。 |
| backtest_version_status | id；version唯一；status/retry_count/error_detail操作狀態；created_at/updated_at。無version外鍵，須核對候選存在；技術失败與績效淘汰不同。 |
| research_runs | id UUID；run_key唯一可重播鍵；engine版本；kind=discovery/backtest/paper；started_at/finished_at；status；configuration保存keyword、查詢、成本或split等；summary保存created、attempt數或合格及journal位置。現有同步不寫finished_at，started_at預設是資料庫建立時間，不必然是真實輪次起點。 |
| source_attempts | id UUID；run_id連研究輪；attempt_key輪內索引；keyword_id可空；query可空；source_url、source_hash、commit_hash；outcome、reason；details原attempt物件；created_at。accepted只表示接納研究，非獲利；同一來源可能跨輪重複。 |
| dataset_snapshots | id UUID；fingerprint唯一資料指紋；market/contract_type/timeframe；first_bar_ms/last_bar_ms毫秒；bar_count；manifest資料摘要；created_at。不包含完整行情CSV。 |
| research_candidates | version主鍵連strategy_hunt；run_id連discovery輪；source_hash/code_hash/signal_hash；specification策略規格；research_mode；parent_version可空、自關聯；created_at；review_status/source_review來源審查。approved是審查通過，不是歷史驗收通過。 |
| research_evaluations | id UUID；evaluation_key唯一；version連candidate；run_id連backtest輪；dataset_id連快照；split；cost_model；metrics；qualified；reasons；created_at。現有qualified是整套結果，並非該split獨立過關；reasons可能僅是一般失敗敘述。 |

## 3. 關聯、識別碼與去重

- research_runs → source_attempts 為一對多；discovery run → research_candidates 一對多。
- strategy_hunt.version → research_candidates.version及backtest_strategy.version；版本是text，數值排序必須顯式轉型。
- research_candidates → research_evaluations；backtest research_runs及dataset_snapshots也各連到多組evaluation。
- UUID採 identity(key)=uuid5(NAMESPACE_URL, 'openclaw-strategy-lab-v7:'+key)。不要人工改UUID以製造新輪次。
- discovery run_key='codex_'+submission_id；例如策略2是codex_codex-20261010T163842Z-dual-momentum-1h。heartbeat本地輪次codex_20261010T163842Z不等於提交journal鍵。
- backtest run_key='backtest:'+version+':'+code_hash；evaluation_key再加':train'等split。
- source_hash是來源text的SHA256；code_hash是實際儲存程式（rstrip後一個換行）；signal_hash含週期、dry-run行情timestamp與四組訊號。訊號去重只是訓練窗口相同行為，不證明所有歷史相同。
- 同submission_id且相同content_hash才能重試。新ID不能用來繞過重複行為拒絕。
- 目前backtest鍵未包含資料/引擎/政策hash；同版本同程式重新測新資料可能覆寫evaluation。需先設計新版本/鍵政策，不能宣稱已支援不可變多次回測。

## 4. 正式提交的實際寫入順序

1. 技術驗證來源、方向、規格與因果性；dry-run到此停止，不写DB。
2. 正式submit核對已登記parent（若有），取得/tmp/strategy_lab_v7_hunt.lock。
3. 讀收據；新提交檢查訊號重複，從DB、檔案、ctrl_manager分配version；先存queued=false收據。
4. 寫同名py/json，json的db_committed=false；保存source、bundle、翻譯及discovery journal。
5. upsert strategy_hunt(version)，PATCH搜尋current_version=version+1。
6. sync_discovery先upsert research_runs(run_key)，再source_attempts(run_id,attempt_key)。
7. upsert research_candidates(version)，保存spec與source_review。
8. metadata原子替換為db_committed=true；收據替換queued=true，回傳正式排隊。

DB與檔案沒有共同交易；不能視為整批原子提交。回測只領取research-v7且db_committed=true的候選；回應丟失時按相同ID重試並核對收據，不能自己翻旗標。

## 5. 回測同步與零候選

sync_result先upsert dataset_snapshots(fingerprint)，再backtest research_runs(run_key)，再七組research_evaluations(evaluation_key)：train、validation、test、cost_stress、test_fold_1/2/3。相容摘要/狀態由回測入口維護，詳細評估由lab_records同步。

零候選仍保存discovery journal並sync_discovery，形成research_runs及source_attempts，不應製造strategy_hunt或research_candidates。通知收據在codex_submissions/<heartbeat_run_id>.notification.json，不是新DB通知表。HTTP成功才記delivered。

sync_all依序重播discovery、已提交候選、結果，以sync_journal的檔案hash避免重複。只看db_committed=true候選；.rejected.json操作拒絕不走完整result同步。upsert可恢復但無法自動修復所有中途損壞。

## 6. 外部母來源變體

已登記候選變體：parent_version必須存在，changes必填。首次外部來源移植：controlled_variant、parent_version=null、parent_origin=external_source、changes必填。來源原始市場、倉位、成本與執行差異必須寫source_review。

parent_origin及changes目前是bundle/metadata欄位，沒有獨立DB欄位；查DB時用source_review中的證據，完整差異再讀遠端bundle。策略2使用後者，不能為填parent_version假造一個重現候選。

## 7. 現存資料的陷阱

2026-10-11實際核對：策略1source_review_failed、審查rejected；策略2controlled_variant、審查approved、七組evaluation，但strategy_hunt仍discovered。策略2qualified=false，驗證-78.443%、測試-88.7498%；不可解讀為待回測或盈利。

研究輪finished_at未必填、關鍵字計數非Codex完整試驗數、回測鍵覆寫風險、一般reasons與各split同qualified均是已知限制。接手需讀報告和metrics，不靠單一status猜測。
