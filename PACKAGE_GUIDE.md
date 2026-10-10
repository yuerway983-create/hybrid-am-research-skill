# Axiom Research · Package guide / 文件包说明

This guide is new in documentation patch **1.1.3**. It explains how the complete framework is organised and where to begin. Package and directory names remain compatible: `axiom-research-modeling-toolkit-v1.1.3.zip` extracts to `axiom-research/`, and the main Skill identifier remains `axiom-research`.

本文件是 1.1.3 文档补丁新增内容，说明完整包“是什么、什么时候用、先读哪里”。模块按实际能力使用；通用工作流可扩展，不代表所有材料都已有可用数值模型。请保留完整文件包，子 Skill 可能依赖根目录的工具、模板和方法资料。

[Overview](README.md) · [中文总览](README.zh-CN.md) · [Quick start / 运行入口](START_HERE.md) · [Host guide / 宿主入口](HOST_START.md) · [Offline presentation / 离线展示](index.html)

## Choose a starting point / 按需求找入口

| What you want to do / 你想做什么 | Start here / 先读哪里 |
| --- | --- |
| Understand the framework and its supported scope / 了解框架与范围 | [README](README.md), [中文 README](README.zh-CN.md), or local `index.html` |
| Run an existing local synthetic example / 运行现有本地合成案例 | [START_HERE](START_HERE.md), then choose VPP–DIW or foam modelling |
| Let an LLM host choose and execute reviewed Skills / 由 LLM 宿主选择并执行已审核 Skill | [HOST_START](HOST_START.md), [main Skill](SKILL.md), then the matching sub-Skill |
| Prepare your own measurements and constraints / 准备自己的测量与约束 | Relevant module workflow, then the corresponding files in `templates/` |
| Inspect software evidence, provenance or limitations / 检查软件记录、来源及限制 | `tests/`, `reports/`, `references/` and the relevant sub-Skill references |

## Files and directories / 文件与目录

The entries below exist in this package. Local run folders such as `outputs/`, `runs/`, virtual environments and caches are not distributed as research evidence.

以下仅列实际交付内容；本地生成的输出、运行目录、虚拟环境和缓存不作为发布包内的研究证据交付。

| File or directory / 路径 | What it is and when to use it / 用途与使用时机 | First read / 建议先读 |
| --- | --- | --- |
| `README.md`, `README.zh-CN.md` | Project overview, workflow and capability status in English and Chinese / 中英文项目总览、流程与能力状态 | [English](README.md) / [中文](README.zh-CN.md) |
| `index.html` | Bilingual static presentation with a local SVG; core content works offline / 双语静态展示，本地图示离线可读 | Open `index.html` in a browser / 在浏览器打开 |
| `START_HERE.md` | Separate paths for project readers, numerical examples and LLM hosts / 阅读、数值案例、LLM 宿主三种入口 | [Quick start](START_HERE.md) |
| `HOST_START.md` | Operator and LLM-host instructions; preserves routing, data freeze and feedback rules / 宿主与操作者流程，含路由、冻结和回传规则 | [Host guide](HOST_START.md) |
| `PACKAGE_GUIDE.md` | This new guide to the package contents / 本次新增文件包说明 | This document / 本文 |
| `SKILL.md` | Main Skill `axiom-research`, including actual scope and host rules / 主 Skill、实际适用范围及主控规则 | [Main Skill](SKILL.md) |
| `agents/` | Host-facing display metadata; not equipment or network permissions / 宿主展示元数据，不是设备或网络授权 | [Display metadata](agents/openai.yaml) |
| `skills/` | Nine existing capability-specific Skills and their instructions; routes and directory IDs stay unchanged / 九个现有子 Skill 及规则，目录和调用标识保持兼容 | Match the [main Skill's routing](SKILL.md); each subdirectory contains `SKILL.md` |
| `registry/` | Runtime registrations and adaptation metadata, review records and a separate unapproved seed-candidate pool / 运行时登记、适配与审核记录，以及未获准候选池 | [Runtime registry](registry/runtime-skills.json), [selection method](references/skill-selection.md); `implemented: false` entries and `seed_candidates.json` are not executable approvals |
| `scripts/` | Numerical, validation and runtime command-line programs / 数值计算、校验与运行工具 | [Local commands](START_HERE.md), then module instructions |
| `schemas/` | Task contracts and historical tool-schema snapshots; module-specific contracts live with their Skills / 任务约定与历史工具契约快照，其他模块契约位于相应 Skill | [Task schema](schemas/task.schema.json), [historical v0.4 tool snapshot / 历史工具快照](schemas/tool-schemas-v0.4.json); get the current exact tool contracts with `python scripts/agent_bridge.py tools` |
| `examples/` | Existing runnable scenarios and labelled synthetic fixtures / 可运行案例与明确标记的合成数据 | [Linewidth fixture](examples/width-calibration-demo/README.md), [foam fixture](examples/foam-refinement-demo/README.md) |
| `templates/` | Templates for study inputs, constraints, evidence and feedback / 研究输入、约束、证据与回传模板 | [Input preparation](START_HERE.md#4-bring-your-own-research-inputs), [feedback contract](templates/feedback_v0.4/README.md) |
| `evidence/` | Frozen evidence packets supplied to existing examples / 现有案例使用的冻结证据包 | [Example packet](evidence/delay-evidence-001/evidence_packet.json), [evidence protocol](references/evidence-protocol.md) |
| `references/` | Method, source, model-contract and implementation documents / 方法、来源、模型契约与实现说明 | [Model contract](references/model-contract.md), [source list](references/sources.md), then module-specific references |
| `tests/` | Software checks for the implemented tools and constraints / 工具及科学约束的软件测试，不是新实物实验 | Run the documented test commands in the current release validation record; inspect relevant `test_*.py` files |
| `reports/` | Preserved historical software runs, acceptance records and past release documents / 保留的历史运行、验收及旧版说明，结论属于其原始版本 | [VPP–DIW records](LEGACY_VPP_DIW.md), [foam validation](reports/foam-0.1-optimization-validation.md) |
| `docs/` | Added in this revision: workflow sources and SVGs, offline HTML document exports, documentation build/check tooling and release notes / 本次新增：流程图源文件和 SVG、离线文档页面、文档构建检查工具及发布说明 | [Workflow source](docs/assets/research-workflow.mmd), [SVG](docs/assets/research-workflow.svg), `docs/pages/`, `docs/build-docs.mjs` |
| `third_party/` | Retained upstream material and attribution context / 保留的上游资料及归属信息 | [Third-party notices](THIRD_PARTY_NOTICES.md) before reusing upstream assets |
| `LEGACY_VPP_DIW.md` | Existing VPP–DIW module details and historical reports; compatible filename, still executable module / VPP–DIW 专项入口与历史记录；保留旧文件名不表示模块失效 | [VPP–DIW guide](LEGACY_VPP_DIW.md) |
| `requirements*.txt` | Dependency sets for different local tools; installing them does not connect an LLM / 各本地工具依赖，安装依赖不会自动连接 LLM | [Quick start](START_HERE.md); choose `requirements-agent.txt` or `requirements-foam.txt` |
| `VERSION` | Full distribution version, separate from runtime and module versions / 整体文件包版本，与运行时和模块版本分开 | [Version file](VERSION) and table below |
| `MANIFEST.json` | SHA-256 hashes for the files in the current package, excluding the manifest itself / 当前包内文件校验，自身除外 | [Current manifest](MANIFEST.json); match the package version before checking |
| `LICENSE` | Project licence / 项目许可 | [Licence](LICENSE) |
| `THIRD_PARTY_NOTICES.md` | Upstream licences and attribution / 第三方许可与归属 | [Notices](THIRD_PARTY_NOTICES.md) |

`registry/` is not live GitHub or literature search. A host may retrieve new sources through authorised tools, but source review and an approved adapter are required before execution. Cause-analysis remains a host supplement, and the foam module remains an independent entry. Directory presence alone does not imply runtime integration.

`registry/` 不是实时检索服务。新来源由获得授权的宿主工具检索，新增可执行工具需先审核并完成适配登记。原因分析仍为宿主补充步骤，泡沫仍为独立入口；文件存在不等于已接入主运行时。

## Versions and integrity

| Component | Version | Meaning / 含义 |
| --- | --- | --- |
| Current distribution / 当前整体包 | `1.1.3` | General project documentation, restored workflow diagram and package guide / 通用项目介绍、恢复流程图与文件包说明 |
| Previous public distribution / 旧版公开包 | `1.1.2` | Previously published package; does not contain this revision / 已公开旧包，不含本次文档改版 |
| VPP–DIW runtime | `1.0.0` | Existing bounded local runtime / 现有受约束本地运行时 |
| Cause-analysis module | `0.2.0` | Host-read supplementary analysis / 宿主补充分析 |
| Foam module | `foam-0.1` | Independent lightweight numerical modelling / 独立轻量数值建模 |

The full package is named `axiom-research-modeling-toolkit-v1.1.3.zip`, with top-level directory `axiom-research/`. Get the [v1.1.3 ZIP](https://github.com/yuerway983-create/axiom-research-skill/releases/download/v1.1.3/axiom-research-modeling-toolkit-v1.1.3.zip) and [release checksum](https://github.com/yuerway983-create/axiom-research-skill/releases/tag/v1.1.3). The still-available [v1.1.2 ZIP](https://github.com/yuerway983-create/axiom-research-skill/releases/download/v1.1.2/axiom-research-modeling-toolkit-v1.1.2.zip) and [v1.1.2 release](https://github.com/yuerway983-create/axiom-research-skill/releases/tag/v1.1.2) remain clearly labelled as that version.

The `SHA256SUMS.txt` file delivered **alongside** a ZIP checks that archive. After extracting it, use the root `MANIFEST.json` to check the listed file hashes; that manifest excludes itself. Old manifests and reports are preserved for their own versions and must not be used to validate changed files from a later package. A matching checksum proves file consistency, not experimental truth or scientific generality.

v1.1.3 ZIP 保留通用包名与 `axiom-research/` 根目录；新版下载和发布入口见上方链接。随 ZIP 单独交付的 `SHA256SUMS.txt` 校验压缩包，解压后的根 `MANIFEST.json` 校验包内文件。旧报告、旧清单仅对应原版本；校验一致不代表实验真实性或任意材料适用性。

This patch changes presentation and documentation only. It does not change numerical algorithms, input schemas, tool routing, runtime permissions, data partitions, thresholds or outputs, and does not add scientific validation. The revised overview states implemented capabilities, host-dependent analysis and possible future applications separately.

本次仅调整展示和文档：科研算法、输入约定、工具路由、权限、数据分区、门槛及数值输出不变，没有新增科学验证。项目总览分别标明已执行模块、需宿主完成的分析和可扩展用途。
