# 本次提交內容與證據範圍

## 收錄

- Skill完整操作要求、references、templates、SSH／kubectl bridge、候選接收程式及独立訓練資料helper。
- 去除舊模型API dispatcher的確定性runtime、副本回測、資料刷新、規格審查、品質政策與同步器。
- 最新計畫、完整操作手冊、bootstrap、用户意圖、目前狀態、來源拒绝记录與已知限制。
- 可見對話的去敏感重建稿及三份歷史掃描／部署報告。
- schema參考、第一輪中文分析、source hash/commit/URL、run報告與通知204證據。
- 五項可攜性、政策邊界與語法測試。

## 刻意未收錄

私鑰、密碼、完整Webhook與APItoken、遠端connection.json、整個OpenClawstate SQLite、用戶登入資料、完整行情100MB、整合fixture、臨時部署ZIP、第三方全文及無關檔案。

不包含平台原始對話匯出，因本次工具／上下文只提供可見訊息與部分重建摘要。交接對話文件明確標示來源範圍，沒有宣稱是完整逐字匯出。

## 源碼定位

engine副本來自原工作區work/strategy-v7，lab_records补保留變體型態；runtime剔除legacy_api_defaults、services與hunt分支。receiver／bridge來自原Skill，在repo内增加独立candidate_validation以避免旧模型模块依赖。

code generation根源仍由Codex負責。引擎副本没有OpenAI/MiniMax API調用，也不包含Tavily憑證。不要因此以为repo能自行启动大模型；需要由Codex排程执行Skill。

## 本次驗證

`python -X utf8 -m unittest discover -s tests -v`：5項通過。另做Skill格式驗證、文字檔秘密模式掃描與git diff --check。

這些檢查不替代遠端全流程验证。首次真实候选正式submit→回測仍待完成，不能把测试成功写成策略盈利。
