# Axiom Research · 科研建模与实验优化快速开始

当前以发泡 FDM 分级聚合物泡沫作为简化建模示例，其他功能模块见 [能力目录](README.md#功能模块与通用名称)。先用合成数据了解两级简化计算与模型修正，再换成自己的实验数据。

## 1. 下载与选择入口

下载[完整发布包 v1.1.2](https://github.com/yuerway983-create/axiom-research-skill/releases/download/v1.1.2/axiom-research-modeling-toolkit-v1.1.2.zip)，解压后在 `axiom-research/` 根目录操作。发布说明和校验值见[对应版本](https://github.com/yuerway983-create/axiom-research-skill/releases/tag/v1.1.2)。

- 了解方法：[泡沫研究 Skill](skills/polymer-foam-model-refinement/SKILL.md)。
- 让 LLM 整理证据与解释结果：[宿主入口](HOST_START.md)。
- 原线宽／扩散任务：[旧 VPP–DIW 模块](LEGACY_VPP_DIW.md)。

泡沫分析依赖根目录脚本与模板，请保留完整文件包。

## 2. 运行合成案例

建议 Python 3.11+。在 Windows PowerShell 中：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-foam.txt --index-url https://pypi.tuna.tsinghua.edu.cn/simple
.\.venv\Scripts\python.exe scripts/foam_model.py run --task examples/foam-refinement-demo/task.json --out outputs/foam-demo-1
```

已有虚拟环境可跳过第一行；macOS/Linux 使用 `.venv/bin/python` 替代 Windows 环境路径。首次安装依赖需要联网，数值案例无需 API 密钥。输出目录必须不存在，重跑时换成 `outputs/foam-demo-2` 等新目录。

## 3. 看懂输出

先打开 `outputs/foam-demo-1/report.md`，阅读中文诊断与优先补充事项，再按需要查看：

| 文件 | 内容 |
| --- | --- |
| `result.json` | 数值检查、候选模型比较、敏感性和判断依据 |
| `model.json` | 成功计算时保存的模型与参数 |
| `input_task.json`、`input_measurements.csv` | 本次实际使用的冻结输入 |

力学、工艺密度和尺度假设分别报告。数值检查通过不等于实物改善；敏感性不可用表示支持点不足，不能解释成没有影响。

案例使用人工设定的数据与修正项，只检验软件行为。具体说明见[合成案例](examples/foam-refinement-demo/README.md)，已有测试见[泡沫验证记录](reports/foam-0.1-optimization-validation.md)。

## 4. 让 LLM 参与分析

在有本地文件和终端能力的宿主中，可以发送：

```text
使用 $axiom-research 分析发泡 FDM 分级聚合物泡沫数据，开展简化计算与模型修正。
读取 skills/polymer-foam-model-refinement/SKILL.md 及其工作流与来源说明。
先整理关键因素和证据，再运行泡沫合成案例，读取实际输出并用中文解释模型比较、
适用范围和优先补测项。将所有合成结果标为软件演示；数值必须来自脚本。
具体实验建议应结合我提供的目标、预算和设备范围；未知参数保持未知。
```

分析自己的数据时，把上述“合成案例”改成自己的任务文件路径，并提供研究目标。宿主读取 Skill 后调用独立泡沫入口，详细说明见 [HOST_START.md](HOST_START.md)。

## 5. 使用真实研究数据

把 `templates/foam-research/` 中的[任务模板](templates/foam-research/task.json)和[测量模板](templates/foam-research/measurements.csv)复制到自己的任务目录，再填写真实来源、单位、基体参考性能和实测数据。

每次选择小应变压缩模量或初始压缩屈服强度中的一种。按材料、拓扑与测试条件限定分析范围，预先声明修正特征，并分开训练／留出条件和批次。不要把示例数值或论文特定条件下的常数直接当成自己的材料参数。

```text
python scripts/foam_model.py run --task path/to/your/task.json --out outputs/your-study-1
```

模板空值故意阻止直接运行。输入字段、数据分组及所需测量见[数据契约](skills/polymer-foam-model-refinement/references/workflow.md)。

## 6. 研究范围

当前能做两级简化计算、模型标定与有限修正，工艺到内部密度的经验关系单独评估。LLM 解释候选原因和有条件的参数方向；下一步实验由研究者审核和执行。

当前未实现端到端工艺到性能预测、自动泡沫实验规划、完整吸能曲线或疲劳／降解寿命。原 VPP–DIW 三轮闭环演示属于[旧模块](LEGACY_VPP_DIW.md)，不能作为泡沫能力证明。
