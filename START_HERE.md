# Axiom Research · Start here / 从这里开始

Choose an entry according to what you want to do: understand the project, run a local numerical example, or work with an LLM host that can read files and use a terminal. The two current application examples are VPP–DIW linewidth/diffusion and hierarchical polymer foams; neither defines the whole framework.

[Project overview](README.md) · [中文项目总览](README.zh-CN.md) · [Package guide / 文件包说明](PACKAGE_GUIDE.md) · [Host guide / 宿主说明](HOST_START.md)

## 1. Understand the project

Start with the [research workflow](README.md#research-workflow) and the capability status table in the README. Open `index.html` in a browser for the bilingual presentation; its core text and local workflow SVG work offline. The [editable diagram source](docs/assets/research-workflow.mmd) and [SVG](docs/assets/research-workflow.svg) are included in the package.

LLM hosts organise evidence and choose reviewed Skills at each technical stage. Numerical programs carry out supported calculations; researchers approve and perform physical experiments. The overall diagram describes the research workflow, while each module implements a defined subset of it.

The documentation patch is **v1.1.3**. Download the [complete package](https://github.com/yuerway983-create/axiom-research-skill/releases/download/v1.1.3/axiom-research-modeling-toolkit-v1.1.3.zip) and verify it with the checksum attached to [the release](https://github.com/yuerway983-create/axiom-research-skill/releases/tag/v1.1.3). The previous [v1.1.2 release](https://github.com/yuerway983-create/axiom-research-skill/releases/tag/v1.1.2) remains available but does not contain this documentation layout. See the [package guide](PACKAGE_GUIDE.md#versions-and-integrity) for version and integrity information.

## 2. Run a local numerical or synthetic example

Keep the complete package together and run all commands from its `axiom-research/` root. Use Python 3.11 or later and a project virtual environment. Installing dependencies initially requires network access. The example scripts below do not connect to an LLM or need an API key.

Choose either example. Both use **synthetic software fixtures**, not laboratory measurements. Their results demonstrate program behaviour and do not establish real materials improvement or an advantage from LLM decisions.

<a id="local-vpp-diw"></a>

### A. VPP–DIW: linewidth calibration and bounded feedback

This example exercises the existing VPP–DIW runtime: calibration, candidate planning, frozen-model comparison, versioned refitting and independent synthetic confirmation. Its deterministic controller follows a fixed sequence; host-selected execution is a separate entry below.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-agent.txt
.\.venv\Scripts\python.exe scripts/preflight.py
.\.venv\Scripts\python.exe scripts/campaign_demo.py --out outputs/quickstart-vpp-diw-1
```

macOS / Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-agent.txt
.venv/bin/python scripts/preflight.py
.venv/bin/python scripts/campaign_demo.py --out outputs/quickstart-vpp-diw-1
```

Open `outputs/quickstart-vpp-diw-1/index.html` for the campaign report; `campaign.json` and each round's linked report contain the actual records. The dependency check reports discoverable packages, not scientific validity. For the input fixture and module-specific history, see [linewidth example](examples/width-calibration-demo/README.md) and [VPP–DIW module guide](LEGACY_VPP_DIW.md).

<a id="local-foam"></a>

### B. Hierarchical polymer foams: model calibration and refinement

This independent entry compares bounded lightweight models and reports fit diagnostics, applicability and supported sensitivity checks. It uses one declared observable per task: small-strain compressive modulus or initial compressive yield strength. It does not use the VPP–DIW session runtime or its multi-round planner.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-foam.txt
.\.venv\Scripts\python.exe scripts/foam_model.py run --task examples/foam-refinement-demo/task.json --out outputs/quickstart-foam-1
```

macOS / Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-foam.txt
.venv/bin/python scripts/foam_model.py run --task examples/foam-refinement-demo/task.json --out outputs/quickstart-foam-1
```

Open `outputs/quickstart-foam-1/report.md` in a Markdown reader. `result.json` contains numerical checks and comparisons; `model.json` is saved on successful calculation; `input_task.json` and `input_measurements.csv` record the inputs actually used. Missing support for a sensitivity estimate does not mean that factor has no effect. Read the [synthetic fixture explanation](examples/foam-refinement-demo/README.md) and [foam Skill](skills/polymer-foam-model-refinement/SKILL.md) for the method and scope.

If `.venv` already exists, skip its creation. Every output directory must be new: use suffix `-2`, `-3`, etc. when repeating a run. Commands intentionally write to `outputs/`, leaving bundled examples and historical reports unchanged.

Optional for users who need a mainland China package mirror: append `--index-url https://pypi.tuna.tsinghua.edu.cn/simple` to the relevant `pip install` command. The default commands use the normal pip index; the mirror is not required.

## 3. Use a file-and-terminal-capable LLM host

Provide the complete package to your host and start with [SKILL.md](SKILL.md), whose invocation identifier remains `axiom-research`. A host must actually be able to read these files and run the supported tools. Copying the Skill text alone does not install dependencies, connect a model service or grant terminal/network permissions.

Example user instruction (Chinese):

```text
使用 $axiom-research。先读取 README、SKILL.md 和 HOST_START.md，
根据我提供的研究目标、资料、已有数据和约束，说明当前哪个模块适用。
在每个技术阶段选择经过审核的 Skill，读取其规则并调用相应数值工具。
如果运行示例，明确标注合成数据；数值结论必须来自实际工具输出。
证据或数据不足时列出补充材料、标定需求或停止原因，不编造测量结果。
给出可追溯的结果解释和待人工审核的研究建议，真实实验由研究者完成。
```

Continue with the relevant route in [HOST_START.md](HOST_START.md): VPP–DIW uses `agent_bridge.py`; foam modelling uses `foam_model.py` independently. The cause-analysis Skill is a host-read supplement and is not automatically registered in the planner, report or audit. The reviewed local registry does not perform live GitHub or literature search; new evidence and tools require the host's authorised retrieval and review.

## 4. Bring your own research inputs

Define the observable, source records, units, material/process scope, constraints and budget before running a research task. Use the appropriate templates rather than changing only the label on a synthetic example.

| Module | Start from | Read before use |
| --- | --- | --- |
| VPP–DIW linewidth/diffusion | `templates/task_geometric_v0.3.json`, `templates/task_geometric_v0.3.csv`, or the corresponding `task_sigma_v0.3.*` pair | [Model contract](references/model-contract.md), [host workflow](HOST_START.md), [feedback template](templates/feedback_v0.4/README.md) |
| Hierarchical polymer foams | `templates/foam-research/task.json` and `templates/foam-research/measurements.csv` | [Foam data contract and workflow](skills/polymer-foam-model-refinement/references/workflow.md) |

The foam templates intentionally contain missing values that prevent direct execution. Preserve independent training/holdout conditions and batches, declare refinement features in advance, and use measured matrix properties appropriate to the task. In VPP–DIW, the protocol, evidence and session inputs are frozen before feedback; compare the frozen model before refitting. Full rules stay in the linked module and host documents.

## 中文阅读提示

- **看项目**：先读 [中文总览](README.zh-CN.md)，或离线打开 `index.html`。流程图表达总体研究路径，具体已实现范围见能力状态表。
- **本地运行**：上方 A 为 VPP–DIW 固定流程合成演示，B 为泡沫独立数值案例。选择对应依赖，在完整包根目录执行；两者都不自动调用 LLM，重跑必须换新输出目录。
- **使用 LLM 宿主**：从主 Skill `axiom-research` 和 [HOST_START](HOST_START.md) 开始。每个技术阶段按适用范围选 Skill，真实实验由研究者审核和完成。
- **查文件用途**：读 [PACKAGE_GUIDE](PACKAGE_GUIDE.md)。本次文档补丁为 1.1.3；旧版 1.1.2 下载仍保留，但不含本次新版文档。科研模块版本和科学验证范围没有因文档改版而提升。
