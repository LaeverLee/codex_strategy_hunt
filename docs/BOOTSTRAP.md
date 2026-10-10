# 空白 Codex 啟動與交互步驟

## 1. 複製repo，認識環境

```bash
git clone https://github.com/LaeverLee/codex_strategy_hunt.git
cd codex_strategy_hunt
```

按README順序讀文件。本repo不包含完整OpenClaw安裝與行情，只銜接現有服務。

## 2. 安裝Skill

把skills/btc-strategy-research复制到你自己的Codex skills目录，或让Codex从当前repo读取该Skill。不要将原工作區C:/Users/250726路徑直接当成自己的路徑。

本repo Skill脚本已解耦旧hunt_v6，只需确定性candidate_validation helper。install会将helper一起部署，避免为了读取训练数据而导入旧模型搜索模块。旧操作手册的绝对路径是原部署例子；你自己的repo与配置路径优先。

## 3. SSH认证

自己创建SSH key、公钥由服务器管理者加入authorized_keys，确认host key。另一台机器不能复制原私钥。root为当前原部署用户；改用受限用户时须确实有kubectl与目标namespace访问权。

复制Skill的templates/connection.example.json为config/connection.local.json，填写你的identity_file绝对路径。此文件被gitignore排除。主机8.209.199.155，namespace与service_id见模板。多容器可添加container键。

```text
python -X utf8 skills/btc-strategy-research/scripts/zeabur_bridge.py health --config config/connection.local.json
```

期望project=jygaprrhtuwzffyrnipt。失败时按手册排查，勿改为另一个数据库。

## 4. 核对远端，不盲目覆盖

通过SSH列出Ready pod，再kubectl exec核对引擎、锁与目录。Bridge会自动发现pod。

远端必须已有strategy_quality.py、backtest_v6.py、quality_policy.py、lab_records.py、lab_runtime.py、私密connection.json与历史k_line_data。

本repo提供这些确定性源码用于比对及恢复，但没有私密凭证和完整行情。不要在已有环境直接执行schema-reference.sql，会与现有表冲突。全新环境重建时须另外确认Worker、数据与数据库迁移；本仓库不是即开即用的独立云服务。

完成核对并备份后安装接收端：

```text
python -X utf8 skills/btc-strategy-research/scripts/zeabur_bridge.py install --config config/connection.local.json
```

install新增codex_submit.py与candidate_validation.py，并最小修改lab_records.py保留变体关系。不会安装完整engine、不会改变排程，也不会发送Discord。

## 5. 研究、生成与提交

读取research状态；从完整来源提取规则，生成符合get_signals/get_exits接口的Python。按templates/candidate.schema-guide.json生成真正bundle，不能提交模板或fixture。

```text
python -X utf8 skills/btc-strategy-research/scripts/zeabur_bridge.py submit --config config/connection.local.json --bundle research-codex/runs/<RUN>/bundle.json --dry-run
python -X utf8 skills/btc-strategy-research/scripts/zeabur_bridge.py submit --config config/connection.local.json --bundle research-codex/runs/<RUN>/bundle.json
```

dry-run通过不代表写入；只有正式命令queued=true才已排队。中文翻译保存在远端codex_submissions，py/sidecar在pytest/Strategy。正式提交前保存完整来源、证据与审查记录。

## 6. 查回测结果

现有回测每5分钟领一个候选。保持原频率与Webhook。不要反复提交同一个候选。

```text
python -X utf8 skills/btc-strategy-research/scripts/zeabur_bridge.py result --config config/connection.local.json --version <VERSION>
```

读取结果中的spec、data、split、cost_model、train/validation/test/test_folds/cost_stress、qualified、limitations。用Supabase查询确认research_candidates、research_evaluations与backtest_version_status一致。

## 7. 排程与切换

使用Codex正式automation工具建/更新heartbeat，每15分钟，指向本Skill。先查看是否已有任务避免重复；repo不能替你创建账号上的排程。

原排程在原对话：btc-codex，thread01a11aa9-ade1-70c0-a368-0a96b8cc4676。新机器若与原排程并行会重复研究，先协调移交，勿误认clone已转移排程。

提示词参考操作手册，替换本机路径。固定要求直接生成、禁止MiniMax、通過检查后立即submit、每轮Discord、保持停止频道公告、不实盘。

第一次真实候选提交、父子记录与队列核对完成后，备份旧OpenClaw搜索job再disable；保留回测job。CLI token从openclaw.json私下读取，subprocess传入不打印。先cron edit --help发现命令。绝不直接UPDATE状态SQLite。

## 8. 通知怎么交互

搜索与回测各自Webhook。完整Webhook现保存在OpenClaw cron payload，或用另行创建的private设置；不提交到GitHub。

Codex每轮生成摘要：研究方向、来源检查数、候选/提交数、淘汰原因、是否待回测、错误。HTTP 2xx才记录成功，204为此前实际结果。失败事件保存并有限重试，使用run_id防止重复发送。不得以最后聊天回复代替实际Webhook。

当前bridge没有通用notification动作，第一次研究轮次的本地工具通过SSH在容器读取Webhook后POST；需把此逻辑变成通用且去敏感的通知helper。不要复制任何完整URL到源码。

## 9. 数据库与状态

backend Worker地址固定新项目；认证在远端私密connection.json。RLS开启，普通anon/auth角色没有这些研究表权限，不为方便而关闭RLS。

每个run保存唯一key；策略version由receiver分配，不由Agent猜下一号。重试同ID同内容；变更必须新ID。已排队代码不修改。

memory/research-state.snapshot.json是交接快照。当前运行状态写本机research-codex/state.json，并保留提交、通知及来源指纹。持久化跨机器需另行同步状态，不能假设本地state自动共享。
