# 接入 hybrid-am-research 的具体方案 · 子 Skill 0.2

## 本次选择

本子 Skill 聚焦“原因分析与参数调整建议”，定位为有证据的解释和决策建议，数值计算继续使用现有轻量工具。
2026-10-09 优化为目标驱动的原因排查与预算内实验建议：无需完整数值模型也能推进排查，具体目标预测则必须依赖已通过关口的对应模型。
核对的原仓库为 https://github.com/yuerway983-create/hybrid-am-research-skill ，提交 `b5297fccf7e50f078e96cb4e8d4d8e43ffd0ac12`。
现版本没有调用 COMSOL、Abaqus 或其他专用模拟软件。这里可替代的是研究流程中的初步工艺解释与原因排查；复杂场计算或材料性能预测需要对应模型与验证。

2026-10-10 仓库分发版包含本子 Skill、输出 Schema，以及主 `SKILL.md`／`HOST_START.md` 的宿主调用入口。子 Skill 版本为0.2，原自动运行时仍为1.0；下文列出的自动接入接口属于后续设计。

## 插入位置

实验前：

`review_evidence → calibrate_response → LLM 原因分析／建议 → plan_experiments → 外部实验`

回传后：

`import_results → compare_results → LLM 原因分析／建议 → prepare_update → refit_update → 独立确认`

回传后的原因分析必须使用先前冻结模型的比较结果；不能先拟合新结果，再把拟合后的解释说成实验前预测。
这一阶段提出后续检查，不修改原计划或已有结果。每次报告绑定当次工况，新增数据后可产生新版本报告。

实验前没有异常数据时，报告重点是设计假设、可观测风险和需要记录的量，不编写“已发生的故障”。回传后先核对实际参数与计划，再解释偏差；实际设置变化、观测噪声、适用范围和未建模机制分别检查。

## 原因与行动的优先级

每个原因引用对应现象，并给出支持和反证。优先级使用短理由，例如“实际日志显示设置偏离”“残差与未覆盖工况一致”“只有文献机制、尚无本工况证据”。
不以通用机理列表、引用数量或模型自报置信度排序。已观察到的关联与原因成立分开：单调展宽不足以确认扩散系数增大，残差增大不足以确认某种新机制。

行动顺序先考虑可用记录中的低成本检查，再考虑能够区分优先原因的测量。检查容易做不等于原因更可能；报告分别说明证据优先级和行动优先级。

## 建议等级与预算

- `direction_only`：可解释趋势并提出下一项检查；缺边界／步长，或预算耗尽且不能复用已有试验时不提出新数字点位。预算耗尽仍可核查现有记录，不停止原因排查。
- `diagnostic_trial`：参数、上下文、网格及可用预算已声明，或可映射已有试验时可给具体区分／标定候选，即使数值模型未通过。不附预测改善量。
- `target_candidate`：模型、观测量、工况和候选适用域匹配，数值关口通过，约束检查完成后才用现有工具预测作目标排序。

任务边界为 `needs_review` 时，候选仍是待审实验；建议等级不改变设备审批或模型状态。
网格按 `lower + k * step`（k为非负整数）核对，同时检查上下界。候选在设备任务范围内、在训练域内和具备物理可行性是不同条件，分别记录。

以原任务的 `next_trials` 为本轮总试验名额，原规划器要求的基准试验占用其中一个名额。分析模块只分配剩余名额，不能再额外提出“每个原因各做一组”而不计成本。试样独立重复也要计入名额；同一试样重复测量不增加独立样本数，但测量成本仍需说明。
已有正式计划时，先标出建议可对应的试验编号；额外建议不自动进入该计划。需要换点时提出新版本草案，由原规划阶段处理。
预算不足以区分机制时，报告本轮能判断什么，优先做日志／测量定义核查；不要声称一轮已完成完整对照实验。

预算计算明确为：`剩余名额 = 总名额 − 基准名额 − 已承诺的非基准名额`。已有计划中的基准只出现在基准字段；复用已有试验的建议不新增名额。新增非基准试验及独立重复之和不得超过剩余名额，超出则降低本轮范围或提出待审的新计划版本。

每项建议的 `independent_trial_slots` 表示该建议关联的独立试验数，不一定是新增数。`mapped_to_existing_plan` 使用已有编号对应的试验；这些名额已在基准或已承诺字段计入，不再计入 `proposed_new_nonbaseline_slots`。多项建议复用同一试验编号时，预算按唯一试验计数，不能重复相加。

每项建议使用以下交接状态：

- `report_only`：方向或信息补充，暂不进入实验表；
- `proposed_for_planner`：满足本轮约束的候选，等待规划器检查、排序与编号；
- `mapped_to_existing_plan`：对应已有试验编号，不重复占预算；
- `requires_revised_plan`：希望替换已排定点位，先提出新计划草案；
- `requires_task_revision`：新增因素、工况或响应，明确需要补齐的新任务字段。

这些状态表示交接意图，不是运行时执行结果。规划器未真正返回结果前，不把建议称为已接受、已排定或已执行。

原规划器当前采用“目标候选＋覆盖点＋基准”的固定方法。它尚不能消费原因分析优先级：完成本子 Skill 注册和结果记录之后，还需明确规划器如何选择诊断点，才能形成自动实验闭环。

## 目标对齐示例

原合成示例目标为500 μm；在10 mm/s下，等待1／3／5 s的平均几何线宽约449／471／504 μm。缩短等待虽会使这一数据中的线宽变小，却可能远离目标。
因此应先确认研究者关注的是接近500 μm还是保持边界清晰；后者还需要独立的边界评价指标。目标未改变时，不将“线宽更小”当成改善。

若本轮要区分等待时间的作用，且三次预算和待审边界沿用原任务，可以提出一个基准试验加两个同速度、不同等待的诊断候选。基准参数来自原任务，两个诊断点用于同工况比较，不能把改变了速度的基准当成等待时间的单因素对照。具体点位仍由规划阶段检查和安排。

## 可以马上使用的宿主接法

先通过现有流程取得诊断文件，再让文件型宿主读取本子 Skill 和有关文件，生成 `llm_analysis_pre.json` 或 `llm_analysis_post.json`。
将分析保存到仓库的 `outputs/cause-analysis/<session-id>/`，与原会话的冻结工件分开，已有报告保留并另存新版本。当前运行时未把它纳入 artifact 哈希、审计、状态机或候选排序，因此不能把这条手动路径称为已经完成自动接入。
有必要进入正式计划的数字候选，仍由已声明的规划步骤生成和检查；在当前版本中不能通过文本建议强行替换 `plan.json`。

## 自动接入时要改的文件

| 文件 | 具体改动 |
|---|---|
| `SKILL.md`、`HOST_START.md` | 已提供两处宿主补充分析入口；自动接入后再更新运行时调用与结果记录说明 |
| `skills/hybrid-am-cause-analysis/SKILL.md` | 已提供本子 Skill，自动接入后更新状态与接口说明 |
| `registry/runtime-skills.json` | 增加 `analysis` 阶段候选；适配器完成前标 `implemented=false` |
| `scripts/agent_runtime.py` | 扩展阶段与工具 schema；准备受控分析输入、接收宿主生成的摘要、做确定性校验、登记结果及哈希 |
| `scripts/llm_agent.py` | 在返回诊断后调用分析阶段；提示词说明哪些是假设、何时要补测量，不能因文本分析通过就提升数值模型 |
| `finish_report` 对应报告生成逻辑 | 展示分析版本、证据、建议和仍未确认的原因，不把文本建议记为实测提升 |
| `scripts/calibration_planning.py` 与规划适配逻辑 | 明确接收哪些诊断候选；合并约束／预算检查，保留基准，输出候选来源与假设编号 |
| 测试 | 验证错单位、未声明因素、越界／不在网格、缺证据和合成来源处理；检查已有冻结评分与确认流程不被绕过 |

建议接口名仅作为设计：

- `prepare_analysis_context(phase)`：返回允许解释的任务、观测、数值诊断和证据，绑定输入哈希；
- `record_analysis(analysis)`：保存宿主 LLM 给出的结构化摘要，检查字段、引用标识、范围、步长和预算；
- 文本内容由宿主生成；`record_analysis` 自身不是 LLM，也不能证明机制成立。

这两个接口目前不存在，不能在原 `agent_bridge.py` 中直接调用。正式实现还需加入源文件快照、子轮次继承和调用重放规则，并验证不影响现有状态机。

## 中文提示词

```text
你正在执行混合 VPP-DIW 打印的原因分析与参数建议。
从仓库根目录读取 skills/hybrid-am-cause-analysis/SKILL.md 和所提供的任务、数据诊断、
模型诊断、原计划及证据。若是回传分析，再读取实际设置与冻结模型比较结果。

先读取目标，确认本轮是原因排查、补标定或追求目标。
没有异常记录时检查设计风险；有记录时描述实际观察到什么。
每个优先原因列出证据位置、反证／替代解释和优先检查理由。
检查方案说明改变什么、保持什么、测什么，结果怎样支持或削弱假设。
对建议说明与目标的关系、取舍，并选择direction_only、diagnostic_trial
或target_candidate。缺边界可给方向，缺模型可给有约束的诊断候选；
具体目标预测必须来自匹配且通过关口的现有工具。
具体参数检查范围和lower+k*step网格。读取next_trials，保留原流程需要的
基准名额，诊断点和独立重复计入剩余预算。边界未审核时标为待审候选。

实测、已有模型计算、文献机制与本次假设分别标明。
不存在的数据留空并说明缺口。几何线宽不能等同浓度 sigma，
等待时间不能等同曝光时间。不要给未经模型和数据支持的强度、寿命或概率。
输出中文短报告和结构化分析摘要，保留简短依据，不输出私人思考过程。
不要改写原数据、验收门槛或已冻结模型，不发送设备指令。
```

## 结构化摘要字段

正式结构定义见 [analysis.schema.json](../schemas/analysis.schema.json)。以下为字段说明，不作为可直接提交的分析实例。

```json
{
  "schema_version": "0.2",
  "analysis_id": "独立分析编号",
  "phase": "pre_experiment 或 post_feedback",
  "task_id": "从原任务读取",
  "context_id": "从原任务读取",
  "data_kind": "保留原始来源分类",
  "observable": "从原任务读取",
  "analysis_goal": "diagnosis、calibration 或 target_seeking",
  "input_refs": [],
  "budget": {
    "total_trial_slots": null,
    "reserved_baseline_slots": null,
    "committed_nonbaseline_slots": null,
    "remaining_slots": null,
    "proposed_new_nonbaseline_slots": null,
    "accounting_note": "基准单列；复用已有试验不新增名额，独立重复计入新名额"
  },
  "observations": [],
  "hypotheses": [
    {
      "hypothesis_id": "本次分析内唯一编号",
      "hypothesis": "候选原因",
      "support_refs": [],
      "contradicting_refs": [],
      "evidence_basis": "context_observation、model_diagnostic、literature_mechanism 或 untested_hypothesis",
      "priority_reason": "为何优先检查；没有原因概率",
      "alternative_explanations": [],
      "missing_information": [],
      "discriminating_check": {
        "kind": "log_review、measurement 或 controlled_trial",
        "comparison": "比较哪些记录、试样或条件",
        "varied_factor": null,
        "held_fixed": [],
        "response_to_measure": "测什么",
        "supports_if": "哪些趋势支持假设",
        "weakens_if": "哪些趋势削弱假设"
      }
    }
  ],
  "suggestions": [
    {
      "suggestion_id": "本次分析内唯一编号",
      "level": "direction_only、diagnostic_trial 或 target_candidate",
      "hypothesis_refs": [],
      "factor": "给具体值时必须是任务中已有因素",
      "direction": "建议调整方向",
      "proposed_value": null,
      "candidate_parameters": null,
      "unit": "从任务读取",
      "purpose": "区分原因、补标定或改善已测指标",
      "relation_to_goal": "为何接近目标，或为何本轮先验证原因",
      "trial_role": "direction、diagnostic、calibration 或 target",
      "independent_trial_slots": null,
      "reuses_planned_trial_ids": [],
      "handoff_status": "report_only、proposed_for_planner、mapped_to_existing_plan、requires_revised_plan 或 requires_task_revision",
      "held_fixed": [],
      "support_refs": [],
      "tradeoffs": [],
      "constraint_checks": {
        "bounds": "not_checked、pass、fail 或 not_applicable",
        "grid": "not_checked、pass、fail 或 not_applicable",
        "fixed_conditions": "not_checked、pass、fail 或 not_applicable",
        "budget": "not_checked、pass、fail 或 not_applicable",
        "model_domain": "not_checked、pass、fail 或 not_applicable"
      },
      "prediction_ref": null,
      "review_status": "needs_review"
    }
  ],
  "information_gaps": [
    {
      "missing": "缺失信息",
      "blocks": [],
      "next_check": "最小补充检查"
    }
  ],
  "unsupported_requests": [],
  "next_action": "明确下一步及所需输入"
}
```

这是字段说明，示例文字不能直接作为运行结果；正式输出要用真实任务值替换。无依据的数值留 `null`。
`prediction_ref` 仅引用已有工具计算；LLM不在该字段生成新预测。`direction_only` 的具体值、试验名额可为 `null`；有数字候选时须明确范围／网格、固定条件和预算检查。用于实际规划的 `target_candidate` 还须有通过的对应数值关口与适用域记录。
预算字段记录未核验时不能声称预算检查通过；已经占用的基准与其他试验名额只计一次。保存结果的适配器还需检查引用存在性、唯一编号和上下文一致性，结构正确不等于机理正确。

`candidate_parameters` 给完整试验点，包含任务的所有因素；`proposed_value` 是其中拟调整因素的值，二者必须一致。未声明因素只能给方向或提出新任务需求。
Schema检查字段、枚举与类型；实际任务中的因素／单位、证据与假设编号、完整点位、边界网格、预算算式及模型关口需要接入适配器核验。没有这些检查结果时，不能因JSON合法就标为已通过。

## 第一轮如何评价这一步

用原仓库合成案例检查流程、引用与参数约束，再用有完整过程记录的真实案例评价科学用途。
建议按实验发生顺序冻结输入：向 LLM 只提供当时可知的现象、记录和诊断，保留后续检查结果供评价。
若只是回顾性分析并已提供后续结果，应标为回顾分析，不宣称盲诊断能力。

对比同一案例的原流程与新增步骤，查看：

- 建议是否对应现象和可见证据，是否漏掉数据／单位问题；
- 是否将未验证机制说成确定原因；
- 调参是否符合范围、步长、固定条件及预算；
- 提出的检查是否能区分不同原因，后续观察是否支持该假设；
- 相同实验预算下，是否减少无效尝试或改善实际测得的指标。

现有软件验收和合成案例只能证明流程行为。没有后续受控检查时，报告原因是假设，不能计算“根因识别准确率”或宣称替代效果已经成立。

## 0.1草案的历史检查记录

2026-10-08：Skill Creator 的 `quick_validate.py` 返回 `Skill is valid!`。
独立宿主 LLM 读取本子 Skill、参考文件及原仓库合成线宽案例，回答了一个测试请求：解释等待时间增加与线宽增加的关系，并评价将等待改到 0.1 s、功率改到 800 mW及保证界面强度的要求。

实际返回识别了以下问题：

- 合成案例中，10 mm/s、等待 1／3／5 s的平均几何线宽约为448.93／470.62／504.13 μm；明确标注合成来源。
- 恒定扩散系数也可对应随时间增长的浓度展宽；几何线宽与浓度 sigma 的映射缺失，不能反推扩散系数增加。
- 0.1 s超出任务声明的1～5 s范围且不在0.25 s网格；功率未列为任务因素，不能直接给该调整。
- 建议先固定其他条件、补充可区分测量，并保留边界待审；没有承诺界面强度。

这是单个合成案例的指令行为检查，没有测量真实原因识别准确率、调用用户付费 API、修改原运行时或执行打印。
0.2优化后的行为检查单独记录，不将上述历史结果当成新版已经通过的证据。

## 0.2草案的检查记录

2026-10-09：Skill Creator 格式检查通过；JSON Schema 自身合法性检查及13项针对性结构测试通过。检查覆盖缺模型仍可给方向、方向不含数字点位、诊断候选不依赖目标预测、网格／预算状态、工况绑定、目标候选的工具引用与适用域、非负整数预算，以及复用计划必须有试验编号。

独立宿主 LLM 读取新版子 Skill、参考文件、结构定义和原仓库合成输入，完成两个场景的前向行为检查，未提供标定／规划报告：

- 目标500 μm、总预算3：输出待审的 `diagnostic_trial`，保留基准 `(5 mm/s, 3 s)`，提出 `(10 mm/s, 3 s)` 与 `(10 mm/s, 5 s)` 两个诊断点。明确基准不能作为等待时间的单因素对照；没有将“缩短等待／减小线宽”误称为接近目标，没有用缺失模型预测达标。
- 无目标值、总预算1：继续排查与记录核查，保留基准后剩余诊断名额为0，不增加独立试验；明确现有标量线宽不能区分扩散与铺展。该检查发现建议等级表对“预算已耗尽”描述不足，已补充为 `direction_only`／`report_only`。

两次回答均标明合成来源、技术重复不等于独立样本，以及边界待审和未执行状态。结构测试不验证实际边界数值、引用真实性或预算算式；前向行为检查也不是根因准确率、真实工艺改善或自动运行时接入的验证。
