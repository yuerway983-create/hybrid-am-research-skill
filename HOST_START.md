# Axiom Research · LLM 宿主使用入口

## 当前主入口：Reece 相关分级聚合物泡沫

发泡 FDM 任务先读取 [polymer-foam-model-refinement](skills/polymer-foam-model-refinement/SKILL.md) 及其工作流和来源说明。由宿主整理证据和预声明候选修正，再调用独立数值脚本；不创建旧的 `agent_bridge.py` 会话。

从完整发布包根目录、已安装 `requirements-foam.txt` 的环境运行合成示例：

```text
python scripts/foam_model.py run --task examples/foam-refinement-demo/task.json --out outputs/foam-host-1
```

读取实际生成的 `report.md`、`result.json`、成功时的 `model.json` 与输入快照。解释模型比较、误差、支持范围、尺度审核和优先补测项，所有示例输出保持合成数据标记。真实分析改用自己的任务文件；安装和输入准备见 [快速开始](START_HERE.md)。

LLM 根据来源与数值结果给出候选原因和有条件的参数方向，具体实验建议需结合用户目标、预算和设备约束。该模块目前没有自动实验规划和端到端工艺到性能验证；下方旧流程的自动工具与三轮能力不适用于泡沫。

## 旧 VPP–DIW v1.0 主控流程

以下 `agent_bridge.py`、线宽／扩散、原因分析与回传更新操作保留给原有任务。历史结果和重跑入口见 [LEGACY_VPP_DIW.md](LEGACY_VPP_DIW.md)。

## 执行角色
LLM宿主一次选择一个工具，agent_bridge.py执行真实Python工具并记录结果。
GitHub负责获取第三方Skill，不是运行环境。宿主必须具备文件/终端能力，实际检索需授权网络工具。
origin标签由操作者声明，不是独立身份认证。固定campaign_demo不等于LLM运行。

## 创建第一轮
```text
python scripts/agent_bridge.py init --task examples/width-calibration-demo/task.json --protocol examples/agent-feedback-demo/comparison_protocol.json --evidence evidence/delay-evidence-001/evidence_packet.json --session runs/host-1 --origin chat_host
python scripts/agent_bridge.py tools
```

可用 `--update-policy templates/update_policy_v1.json` 在运行前声明最大轮数、确认条件数及不退化容许量。
任务/数据/协议/软件随后冻结；不能看过结果再改门槛。默认最多3轮，是演示预算而非科研结论。

## 给宿主的完整指令
读取SKILL.md，使用agent_bridge逐条调用；不要调用固定demo替代自己的选择。
先session_status、inspect_task。每个技术阶段先find_skills，比较候选并记录简短理由，
activate_skill后读取返回说明，再执行该阶段工具。数值计算来自Python，不得编造测量或预测。
证据不足用实际宿主检索取得资料并按证据格式导入；工具缺口用实际GitHub搜索/读取审核，不执行未知代码。

典型调用：
```text
python scripts/agent_bridge.py call --session runs/host-1 --origin chat_host --call-id h01 --tool session_status
```
含参数的调用，建议 `--args-file request.json`，避免Windows命令行引号差异。

第一轮流程：
inspect_task → 激活evidence/review_evidence → 激活calibration/calibrate_response → 根据返回选择planning → plan_experiments。
没有外部结果时finish_report并等待。回传/确认文件不允许由主控模型生成。

## LLM 原因分析与参数建议（宿主补充步骤）

新增 [hybrid-am-cause-analysis v0.2](skills/hybrid-am-cause-analysis/SKILL.md)，由宿主直接读取，在以下位置生成补充分析：

- 实验前：`calibrate_response` 返回后、`plan_experiments` 前；解释现有现象、模型诊断或设计风险。
- 回传后：`compare_results` 完成后、`prepare_update` 前；依据实际设置与冻结模型偏差提出待验证原因。

可直接给宿主以下指令（从仓库根目录开始；替换会话路径）：

```text
读取 skills/hybrid-am-cause-analysis/SKILL.md 及其引用的接入说明。
基于 runs/host-1 中已有的任务、测量、证据和工具报告，分析原因并提出参数建议。
先对齐任务目标，列出证据、替代解释及区分检查。具体试验候选核对范围、步长、
固定条件和预算，保留基准名额。缺失文件按信息缺口处理，继续能完成的排查。
若有回传结果，先完成 compare_results，再解释冻结模型偏差，随后才可更新模型。
将中文短报告和符合分析 Schema 的摘要保存到 outputs/cause-analysis/host-1/，
分别使用 llm_analysis_pre 或 llm_analysis_post 作为文件名；已有报告保留并另存新版本。
输出说明哪些建议仅供阅读、哪些等待规划器接入，以及下一项最有价值的检查。
```

该模块未注册到自动运行时；不要传入 `stage=analysis` 或调用设计中的 `record_analysis`。
当前规划器仍按原方法选点，`finish_report` 和审计不会自动收录补充报告。
宿主可以对照正式计划记录建议的交接状态；需要新诊断点时保留待接入建议，不能用文字报告覆盖冻结的 `plan.json`。
完整输入约定、输出 Schema 和后续自动接入位置见 [接入说明](skills/hybrid-am-cause-analysis/references/integration.md)。


## 文献与结果由操作者附加
无初始文献包时，可由授权宿主检索后：
```text
python scripts/agent_bridge.py attach-evidence --session runs/host-1 --packet path/to/evidence_packet.json
```
这只是导入，不会执行在线检索；包中的主张仍需宿主科学核查。已使用证据不覆盖。

真实实验回传结构沿用templates/feedback_v0.4，manifest绑定原计划及比较协议的哈希：
```text
python scripts/agent_bridge.py attach-feedback --session runs/host-1 --manifest path/to/feedback/manifest.json
```
主控随后激活descriptive-feedback，import_results → compare_results。先评分原模型，不先重拟合。

## 更新与第二轮
激活safe-model-update后依次：prepare_update → refit_update。
此时原模型/结果保留；候选模型已经冻结，同时生成confirmation_plan.json。
尚无独立确认：可以等待，或start_next_round(mode=calibration_only)，但不提供已验证的数值预测。

有确认数据后，操作者导入：
```text
python scripts/agent_bridge.py attach-confirmation --session runs/host-1 --manifest path/to/confirmation/manifest.json
```
manifest格式见templates/confirmation_v1。它绑定已冻结候选与预先生成的确认计划。
已使用的任何样品/批次不得重用；确认覆盖条件不完整时会拒收。真实性是操作者声明，程序不认证实验。

主控evaluate_update：通过才可start_next_round(mode=validated_update)；失败则calibration_only或停止。
start_next_round返回next_round目录，宿主将--session切换过去，再选择planning Skill，生成第二轮试验。
后续重复同样步骤。所有轮次保留历史，达到预定最大轮数则停止，不擅自延长预算。

## 软件演示时的外部环境
只能由操作者/测试工具在synthetic_demo中运行，绝不是agent工具：
```text
python scripts/synthetic_campaign.py feedback --session runs/host-1 --out runs/host-1/test-fixtures/feedback
python scripts/synthetic_campaign.py confirmation --session runs/host-1 --out runs/host-1/test-fixtures/confirmation
```
需要在相应plan和candidate已经冻结后调用，然后用上面的attach命令附加。禁止将这些数据改标为真实数据。

## 审计和可选API
```text
python scripts/agent_bridge.py audit --session runs/host-1
```
llm_agent.py提供Responses循环，start_next_round后自动切换工具会话。运行前创建origin=openai_responses会话。
```text
python scripts/llm_agent.py --session runs/api-1 --model YOUR_ACCOUNT_MODEL_ID --allow-external-data
```
模型名由账户实际可用模型指定。API密钥只在OPENAI_API_KEY环境变量/宿主凭据中配置，不发聊天、不写GitHub。
联机可能付费并发送任务/工具结果；本包只做模拟传输和本地工具测试，未使用你的账户验收远程API。
store=false不是对服务方数据保留政策的独立保证。更多能力由所选宿主承担，不是SKILL.md自动获得。
