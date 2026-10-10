# Codex BTC 策略研究：Zeabur OpenClaw 操作與移交手冊

版本：2.0；日期：2026-10-11。此文件適合交給另一個 Codex 使用，先閱讀整份文件，再操作現有環境。

## 1. 系統分工與已授權範圍

Codex 排程負責研究、直接閱讀與翻譯原始資料、提取交易規則、生成 Python 策略、審查及設計受控變體；不呼叫 MiniMax。OpenClaw 所在容器保留 Python 回測引擎，负责行情資料、驗證、績效計算與 Supabase 紀錄。Discord 用於結果通知。

使用者已授權研究候選直接放入遠端待回測資料夾、寫入新研究專案及送出搜尋／回測通知。此授權不包含實盤下單、刪除舊紀錄或變更交易所帳戶。

本機 Codex 排程不是伺服器上的常駐模型服務。更換電腦時要重新安裝 Skill、設定本機認證與建立排程；匯入 Skill 不會自動繼承原電腦的排程、登入或工具權限。

## 2. 目前部署識別

| 項目 | 值 |
|---|---|
| SSH 主機 | 8.209.199.155 |
| 本次部署 SSH 使用者 | root |
| Zeabur Project ID | 69e0f490345a78e2a2f798e8 |
| Environment／namespace | environment-69e0f4905ae0a69725e92658 |
| OpenClaw Service ID | 69e0fa56345a78e2a2f79a25 |
| 遠端引擎根目錄 | /home/node/.openclaw/workspace/strategy_lab_v7/sessions |
| 待回測目錄 | 引擎根目錄/pytest/Strategy |
| 接收程式 | 引擎根目錄/codex_submit.py |
| 中文翻譯與完整提交證據 | 引擎根目錄/codex_submissions/<submission_id>/ |
| 行情目錄 | 引擎根目錄/pytest/k_line_data |
| 回測結果 | 引擎根目錄/pytest/research_results/<version>.json |
| 合格研究檔案 | 引擎根目錄/pytest/Research_Qualified |
| 淘汰研究檔案 | 引擎根目錄/pytest/Research_Rejected |
| 新 Supabase 專案 | jygaprrhtuwzffyrnipt |
| 私密資料庫連線 | /home/node/.openclaw/workspace/strategy_lab_v7/connection.json |

這些是目前環境的識別，不是通用預設。若移到另一個 Zeabur 環境，需要更新主機、namespace、Service ID、根目錄與資料庫設定。Pod 名稱會改變，不能把本次 pod 名称當成永久設定。

## 3. 另一個 Codex 的安裝與前置條件

1. 解壓交付 ZIP，將 btc-strategy-research 資料夾放到該電腦的 Codex skills 目錄。Windows 通常為 `%USERPROFILE%/.codex/skills`，或該環境實際的 CODEX_HOME/skills。
2. 確認 Codex 可以讀取 Skill、使用來源搜尋工具、執行 Python 與 SSH，並取得此伺服器的合法存取權。
3. 本機 Python 使用標準函式庫即可執行 bridge；遠端引擎需既有 numpy、pandas 與回測依賴。驗證 Skill 的工具另需 PyYAML。
4. 建立自己的 SSH 金鑰，請伺服器管理者加入公鑰；不要複製原電腦私鑰。私鑰與密碼不包含在 ZIP。
5. 初次用互動 SSH 核對並信任伺服器 host key。bridge 使用 StrictHostKeyChecking=yes，未知或變更的 host key 會停止，不自動跳過。
6. 複製 templates/connection.example.json 到本機私有工作目錄，填入 identity_file 的實際絕對路徑。此設定不需要 SSH 密碼或 Supabase 金鑰。
7. 測試連線，再安装接收程式及验证候選格式，最後建立 Codex 排程。

Windows 建立金鑰可在互動終端執行：

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE/.ssh/btc_strategy_codex" -C "codex-btc-strategy"
ssh -i "$env:USERPROFILE/.ssh/btc_strategy_codex" root@8.209.199.155
```

無人值守時若金鑰有 passphrase，須事先配置可用的 SSH agent。不要將 passphrase 寫進排程提示詞。伺服器端由管理者把公鑰加入對應使用者的 `~/.ssh/authorized_keys`，並確認目錄／檔案權限。

目前這台電腦已設定 `C:/Users/250726/.ssh/btc_strategy_codex`，本地連線設定為工作區 `work/zeabur-codex.json`。這兩個路徑不能直接套用到別台電腦。公鑰註解為 codex-btc-strategy；撤銷時只刪除相應公鑰那一行。

## 4. 連線實際怎麼走

本機 Codex → 本機 Python bridge → SSH 伺服器 → kubectl exec → OpenClaw 容器 Python 接收程式 → 新 Supabase Worker。

不是對 OpenClaw 對話發一段文字請它自行翻譯，也不是透過網頁檔案管理器操作。策略 JSON 用 SSH stdin 傳遞，內容不拼接成 shell 指令。

手動定位服務時：

```bash
kubectl get pods -n environment-69e0f4905ae0a69725e92658 -o json
kubectl exec -i -n environment-69e0f4905ae0a69725e92658 <READY_POD> -- python3 /home/node/.openclaw/workspace/strategy_lab_v7/sessions/lab_runtime.py health
```

`<READY_POD>` 必須是名稱以 `service-69e0fa56345a78e2a2f79a25-` 開頭、Running、Ready 且未終止的 pod。bridge 已自動執行這項選擇；沒有或超過一個符合 pod 時停止，由操作者確認部署狀態。多容器服務可在 connection.json 指定 container。

## 5. Bridge 操作

以下為命令格式；將 `<SKILL>`、`<CONFIG>`、`<BUNDLE>` 換成實際檔案路徑。Windows 可使用 `python -X utf8`。

```text
python -X utf8 <SKILL>/scripts/zeabur_bridge.py health --config <CONFIG>
python -X utf8 <SKILL>/scripts/zeabur_bridge.py install --config <CONFIG>
python -X utf8 <SKILL>/scripts/zeabur_bridge.py submit --config <CONFIG> --bundle <BUNDLE> --dry-run
python -X utf8 <SKILL>/scripts/zeabur_bridge.py submit --config <CONFIG> --bundle <BUNDLE>
python -X utf8 <SKILL>/scripts/zeabur_bridge.py result --config <CONFIG> --version 2
```

- health：使用現有私密 Worker 設定，只輸出新專案的控制狀態，不讀出密鑰。
- install：安裝 codex_submit.py，並對既有 lab_records.py 做最小修改，使重播同步保留 research_mode 與 parent_version。原檔備份為 lab_records.py.pre_codex。若檔案版本不符合已知格式，停止而非盲改。
- submit --dry-run：驗證規格、程式、方向與因果性，使用訓練資料檢查；不建立候選、不寫入資料庫。
- submit：驗證後登記來源與候選，寫入待回測檔案並回傳版本及遠端檔案路徑。
- result：讀取指定版本結果；未完成時回傳 RESULT_PENDING，不代表錯誤或合格。

提交命令預設等待至多 180 秒。SSH／遠端非零退出只輸出經限制的錯誤摘要，以免原始 traceback 暴露私密設定；需要診斷時在伺服器端核對錯誤並先遮蔽密鑰。

## 6. 提交格式：不是只傳一個 py

每個提交使用一份 JSON bundle。讀取 templates/candidate.schema-guide.json 作為欄位說明，不能直接將該模板提交。

必填頂層欄位：submission_id、generator、research_mode、keyword、title、source、translation_zh、source_review、spec、code。

- submission_id：最多 120 字元，只用英數、底線與連字號。同一次提交重試使用同一 ID 與相同內容；內容變更必須換 ID。
- generator：固定 Codex；表示生成工作由本次 Codex 完成，不是 MiniMax。
- research_mode：reproduction 或 controlled_variant。變體必填已登記的 parent_version 與 changes。
- source：url、text，以及可選 commit／files。text 保留完整必要來源，不能僅存搜尋摘要。
- translation_zh：中文規則、來源段落對應、所有參數、缺失、假設與改動。
- source_review：approved=true、checks 與 evidence。此欄位是 Codex 另一步審查的紀錄，不代表第二個獨立模型或實盤證明。
- spec：引擎可理解的規格，詳見下節。
- code：完整 Python 原始碼，以 JSON 字串傳輸。

接收端會重新檢查技術條件，但不能自動證明所有來源語意正確；Codex 仍需在生成後重新對照來源，而非只填 approved=true。

## 7. 現有策略介面與限制

程式必須提供：

```python
def get_signals(df):
    # 回傳 long_entry, short_entry
    # 每個為長度 len(df) 的一維 boolean array
    ...

def get_exits(df):
    # 回傳 long_exit, short_exit，同樣是 boolean arrays
    ...
```

DataFrame 至少有 timestamp、open、high、low、close、volume。只允許目前 AST 檢查器接受的 numpy／pandas 與函式結構；不能任意 import 套件、定義 class 或在模組頂層執行操作。這是資源限制與程式檢查，不是完整 OS 安全沙箱。

spec 至少含 market=BTC、timeframe、directions、hypothesis、entry_rules、exit_rules、failure_conditions、evidence_quotes、warmup_bars、signal_exit、risk。

目前引擎允許週期為 **5m、15m、30m、1h、4h**。日線仍是未實作規劃，不可提交為已支援。不能只修改週期白名單就宣稱完成，還需資料、TF_MS 與成本／資金費用對齊支援。

directions 允許 long_only、short_only、long_short。risk 明確包含 stop_atr、take_atr、max_hold_bars，不使用就設 null；可選 stop_pct、take_pct。使用 ATR 退出時需 atr_period 與 atr_method。沒有停損或持有時間退出時需 signal_exit=true 並實作來源支持的退出訊號。

現有引擎對倉位、加倉與成交的能力有限。遇到原始策略需要多倉位、動態加倉、限價簿或盤中順序而現有引擎不支持時，拒絕忠實重現或明確列為受控變體，不可以默默簡化。

## 8. 接收、排隊與資料庫的順序

1. 驗證 bundle、来源审查資訊、spec 與 code。
2. 在訓練資料上檢查訊號、因果性與交易方向。
3. 取得 /tmp/strategy_lab_v7_hunt.lock；鎖占用時稍後重試，不能刪鎖。
4. 檢查 submission_id 重試與已批准訊號去重。
5. 根據資料庫控制值、已存在的策略版本與檔案取得下一個版本，避免覆蓋。
6. 保存恢復 receipt，再寫 `<version>_Strategy_Gold.json`（db_committed=false）與同名 .py。
7. 保存來源、完整 bundle、中文翻譯及 discovery journal。
8. 登記 strategy_hunt、research_runs、source_attempts、research_candidates，更新版本控制。
9. 原子更新 sidecar 的 db_committed=true，才開放回測領取。
10. 回傳 queued=true、version、queue_file 與 translation_file。

回測依據是 sidecar 的 engine=research-v7 與 db_committed=true。單独 scp 一個 py 不算成功提交，也不會被正常回測。

supabase sync adapter 已修改為保留 controlled_variant 與 parent_version。所有型態使用現有 research-v7 引擎版本，pipeline_revision=codex-direct-v1 與 model=Codex 標示生成來源；不要將舊 MiniMax 結果改名成 Codex 結果。

若檔案已排隊就不再修改該版本。改動程式使用新 submission_id／版本。提交中斷時先檢查 receipt、sidecar、資料庫與是否已被回測歸檔，再重試；不要手動把 db_committed 設 true。跨檔案與遠端資料庫不是單一交易，程序被強制終止的極小時間窗仍可能需要人工恢復，不能承諾任何故障都自動恢復。

## 9. 回測領取、結果及通知

現有回測排程 ID：a8f06958-e766-4780-b4bf-a845977100b7，每 5 分鐘領取候選。不是提交後同步完成，也不保證同一輪處理所有候選。

正常完成後，py 與 sidecar 移到 Research_Qualified 或 Research_Rejected；績效保存到 research_results，並同步 Supabase 分段結果。RESULT_PENDING 時先查看佇列與回測排程，不能重複提交同一策略以催促。

透過 Supabase 工具查詢：

```sql
select version, review_status, research_mode, parent_version
from public.research_candidates where version = '2';

select version, status, error_detail
from public.backtest_version_status where version = '2';

select split, metrics, qualified, reasons
from public.research_evaluations where version = '2' order by split;
```

門檻為驗證與測試各 BTC 累積淨收益≥50%、各≥30交易、PF≥1.1、Sharpe≥0.5、最大浮動回撤≤15%；至少兩個測試子段正收益，1.5倍成本後正收益。來源審查仍必須有效。歷史合格不等於實盤允許。

Strategy Hunt 搜尋通知使用 Webhook ID 1495818814024318976，零候選也通知；回測使用 1500532618310058055。頻道 1494372820380160100 自動 announce 保持停用。

完整 Webhook 從既有 job payload 或新私密通知設定讀取，不寫進本文件或 ZIP。接收／bridge 程式本身不發 Discord，也不修改 cron；Codex 研究排程與既有回測通知流程分别負責發送。以真實 HTTP 回應記錄傳送結果。若生成但提交失敗，通知寫「生成完成、提交失敗、尚未回測」，不能寫成搜尋合格。

## 10. Codex 排程移交

在另一個 Codex 中先用排程工具查看是否已存在相同任務，避免重複建立。依使用者目前設定，每 15 分鐘在持續研究對話中執行。不要把原電腦 automation.toml 複製當成已建立排程。

排程提示詞建議內容：

> 使用已安裝的 btc-strategy-research Skill。直接搜尋、閱讀、翻譯、生成與審查 BTC 策略，不呼叫 MiniMax。讀取本機私有連線設定，health 確认遠端，通過 dry-run 後立即 submit，將生成的 py 與 sidecar 放入既有待回測目錄，中文翻譯保存於 codex_submissions。保留來源與版本證據，按既定50%研究門檻處理結果，不下實盤單。使用現有各自 Webhook 發送每輪搜尋及回測結果，保持自動 announce 停用。連線或提交失敗時保留本地候選並標記未提交，不宣稱已回測。狀態不變時不要重複發 Codex 聊天通知，重要候選、完成、失敗及需要使用者操作時回報。

旧 OpenClaw 搜尋任務 ID 為 52d4bf14-f93e-4f00-8e67-fc770aef6929。第一個真實候選完成提交驗證後停止舊搜尋，保留回測；切換前備份原 job。CLI 先看 `node /app/openclaw.mjs cron edit --help`，使用私密 gateway token，不打印 token；不得直接修改 SQLite。

目前旧搜尋是否仍启用，需要在實际切換时重查。本手冊不把「已建立 Codex 排程」當成「旧搜尋已停用」。

## 11. 實測紀錄與未完成項目

2026-10-11 已完成：專用 SSH 金鑰登入、服務 pod 自動定位、新 Supabase health、接收程式安裝、同步 adapter 最小修改，以及使用真實4h訓練資料的 dry-run 訊號與因果性檢查。

dry-run 使用明確標示的整合 fixture，回應 validated=true、queued=false；fixture 沒有作為研究策略寫入資料庫或待回測佇列。正式資料庫提交與全流程回測需第一個真實來源候選驗證；不以假策略污染新研究紀錄。

尚不宣稱完成：日線支援、所有週期基準比較、前向模擬、第一個 Codex 真實候選的提交與回測，以及新研究排程的實際 Webhook 送達驗證。

## 12. 故障處理與回復

| 現象 | 核對與動作 |
|---|---|
| SSH 認證失敗 | 金鑰路徑、authorized_keys、agent 與主機使用者；不把密碼塞進排程 |
| host key 未知／變更 | 與管理者核對主機指紋後再更新 known_hosts |
| 找不到唯一 Ready pod | namespace、Service ID、部署切換與容器狀態 |
| health 失敗 | connection.json、Worker 可達性與現有資料庫授權；不輸出秘密 |
| dry-run 失敗 | 引擎不支援規格、資料缺失、訊號方向或因果性；修正候選而非跳過檢查 |
| submit 鎖占用 | 本輪保存並稍後重試，不能刪鎖 |
| 同 ID 不同內容 | 新候選使用新 ID，不覆蓋原 submission |
| 提交後結果仍 pending | 排程、佇列 sidecar、回測鎖與錯誤狀態 |
| 已有 .py 但未被領取 | 同名 JSON、engine、db_committed 與資料庫提交狀態 |
| 紀錄變體變成重現 | 檢查 lab_records.py adapter 是否被其他部署覆蓋 |

回復時先停 Codex 研究排程，確認沒有提交與回測正在進行，再使用備份恢复 adapter；有變體資料時不可盲目回復會覆寫型態的舊同步器。需要重啟舊搜尋時，按備份恢复原 job，確保不会與 Codex 同時搜尋。

容器重建後檢查引擎根目錄、接收程式、私密連線與行情是否仍存在；無法確認持久性時重新核對 Zeabur volume 配置。不要把寫入容器視為永遠不會隨部署消失。

## 13. 匯出包內容與排除項

ZIP 包含 SKILL.md、references、scripts、templates 與完整計畫書副本。另一個 Codex 可依相對路徑讀取全部操作說明。

ZIP 不包含 SSH 私鑰、密碼、connection.json 的 Worker token、完整 Discord Webhook、Tavily／MiniMax／Supabase API key，也不包含原電腦的 automation 狀態。每個操作者配置自己的認證及排程。
