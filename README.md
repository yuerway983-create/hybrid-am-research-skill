# Axiom Research

**LLM 辅助分级聚合物泡沫的材料设计、工艺优化与模型修正**

LLM-Assisted Materials Design, Process Optimisation and Model Refinement for Additively Manufactured Hierarchical Polymer Foams

围绕牛津大学 **Reece Oosterbeek 团队的发泡 FDM 分级多孔聚合物研究**，连接文献因素提取、两级简化计算、模型标定与实验建议。当前实现侧重因素整理、压缩性能分析和候选模型修正；材料设计与工艺优化是研究目标，具体改进仍需真实实验检验。

[快速开始](START_HERE.md) · [泡沫研究 Skill](skills/polymer-foam-model-refinement/SKILL.md) · [LLM 宿主入口](HOST_START.md) · [下载完整 v1.1.1 文件包](https://github.com/yuerway983-create/axiom-research-skill/releases/download/v1.1.1/axiom-research-skill-v1.1.1.zip)

## 与 Reece 研究的衔接

研究依据是 Sevcenco、Walters、Siviour 与 Oosterbeek 的论文：[Mechanics and modeling of hierarchically porous metamaterials manufactured by foaming fused deposition modeling](https://doi.org/10.1063/5.0301777)。原研究将打印形成的宏观孔结构与材料内部微观泡孔结合，用两级密度与 Gibson–Ashby 型关系描述力学响应。

本项目以这套已有简化模型为基础，加入 LLM 辅助的证据整理、候选原因解释与预声明修正，再用数值程序完成标定和比较。这些 LLM 分析与软件扩展属于本项目，并非原论文已经实现的方法，也不是牛津大学或 Reece 团队的官方软件。

Reece 的研究背景见[牛津个人主页](https://eng.ox.ac.uk/people/reece-oosterbeek)，公式、原文位置和适用限制见[来源与证据边界](skills/polymer-foam-model-refinement/references/sources.md)。其更广泛的降解、疲劳与回收研究并不等于本模块已支持这些预测。

## 当前可以完成什么

| 环节 | 当前能力 |
| --- | --- |
| 因素与证据 | LLM 宿主整理温度、出料倍率、密度、微观孔隙份额与实测几何，标注出处和缺失信息 |
| 两级简化计算 | 由总相对密度和微观孔隙份额换算微／宏两级密度，分别标定单尺度幂律 |
| 压缩性能 | 每次分析小应变压缩模量或初始压缩屈服强度中的一种 |
| 工艺关系 | 独立拟合温度／出料倍率到内部密度的经验响应面 |
| 模型修正 | 比较原模型、普通密度残差修正与最多两个预声明宿主修正特征 |
| 诊断与建议 | 输出误差、有限支持范围内的敏感性、尺度审核及优先补测项；由宿主解释并提出人工可审查的实验建议 |

这里的“虚拟仿真”是简化模型计算与有限参数扫描。LLM 负责证据、机制假设和中文解释，脚本负责可复算的数值。当前没有完整发泡过程仿真、端到端工艺到性能验证、预测区间或自动泡沫实验规划，也不输出完整吸能曲线与疲劳／降解寿命。

## 研究流程

1. 定义材料、宏观拓扑、测试条件与目标观测量，整理文献和已有测量。
2. 核对密度定义、单位、样品身份及训练／留出条件与批次。
3. 标定两级模型，预声明候选修正，只用训练条件交叉验证选择模型。
4. 冻结模型后评分留出数据，检查误差、适用域与尺度假设。
5. LLM 依据报告解释候选原因；研究者结合预算、设备约束审核下一步实验并获得新数据。

温度／出料倍率到内部密度与密度到性能的模型分别评估，不能直接拼接成已验证的全流程预测。技术重复先合并，再按条件等权；不能根据留出误差反复挑选修正项。

## 快速运行泡沫案例

下载[最新完整包 v1.1.1](https://github.com/yuerway983-create/axiom-research-skill/releases/tag/v1.1.1)，解压后在 `axiom-research/` 根目录操作。Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-foam.txt --index-url https://pypi.tuna.tsinghua.edu.cn/simple
.\.venv\Scripts\python.exe scripts/foam_model.py run --task examples/foam-refinement-demo/task.json --out outputs/foam-demo-1
```

已有环境可跳过创建环境；macOS/Linux 用 `.venv/bin/python`。输出目录必须不存在，重复运行换新目录。数值步骤不需要 LLM API 密钥，也不调用商业仿真软件或打印设备。

运行后查看 `report.md` 的中文诊断，结合 `result.json`、`model.json` 和输入快照核查计算。脚本先冻结任务和 CSV 快照，再对快照计算并记录哈希。

案例全部是[合成软件夹具](examples/foam-refinement-demo/README.md)，刻意包含已知修正项；只能验证计算和数据隔离，不能证明真实 PLA 性能或 LLM 优势。泡沫模块已有 73 项测试记录，完整项目已有 347 项测试记录，详见[优化验证](reports/foam-0.1-optimization-validation.md)；本次页面更新没有改变数值实现。

## 换成自己的实验数据

从[任务模板](templates/foam-research/task.json)和[CSV 字段模板](templates/foam-research/measurements.csv)另存新任务。准备同材料、拓扑与测试条件下的基体参考性能、单尺度和分级结构数据，以及分开的训练与留出条件。

模板的 `null`、空数组和空数据表示尚未完成，不能直接运行或继承演示常数。微观孔隙份额表示微观孔隙占全部孔隙的比例，不是微观孔隙率；出料倍率也不等同于实测体积流量。切换模量／屈服强度时需同步修改观测量、测量定义和独立基体参考值。

完整输入规则见[工作流](skills/polymer-foam-model-refinement/references/workflow.md)。缺少数据或支持范围不足时，报告保留失败原因与优先补测项；“无法判断”不会被写成零效应或已确认改善。

## Skill 与文件包

主 Skill 调用名为 `axiom-research`，展示名为 **Axiom Research**。发泡 FDM 任务使用独立子 Skill `polymer-foam-model-refinement` 与 `scripts/foam_model.py`；保留完整发布包，不单独复制子 Skill 文件夹。

发布包版本 **1.1.1**，泡沫模块 **foam-0.1**。下载附件同时提供 `SHA256SUMS.txt`，根 `MANIFEST.json` 记录包内文件哈希（自身除外）。旧 v1.1.0 清单保留于 `reports/releases/v1.1.0/MANIFEST.json`，旧发布继续作为历史版本。包中不含虚拟环境、凭据或私有数据。

输入记录由操作者提供，软件检查不能独立认证实验真实性。外部文献和仓库需要核对来源；未经审核的外部代码不会自动安装执行。第三方归属见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 旧模块与历史记录

原混合 VPP–DIW v1.0 工作流和原因分析 v0.2 保留在[旧模块入口](LEGACY_VPP_DIW.md)，历史报告保持原始标题与结论。旧的 14 工具流程、三轮演示和线宽／扩散结果不代表泡沫模块已经完成自动闭环。

维护仓库：[yuerway983-create/axiom-research-skill](https://github.com/yuerway983-create/axiom-research-skill)。
