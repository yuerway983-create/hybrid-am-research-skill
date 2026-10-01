# 已核对外部技术来源 · 2026-10-01

以下用于工程结构及候选审核；没有从这些仓库复制第三方源码。

- Agent Skills specification: https://agentskills.io/specification
- Agent integration: https://agentskills.io/integrate-skills

GitHub候选固定提交：K-Dense-AI/scientific-agent-skills
`91497e335489dcb544ec8ddc8f6b7ce5fd6d1121`

| 路径 | 本轮实际读取范围 | blob SHA | 局部发现 |
|---|---|---|---|
| skills/literature-review/SKILL.md | 1–130行 | c1ea86e86e3b5ec34db1f5e567dc16ee9709bda9 | MIT标记；Parallel搜索及额外图示要求；非自动可执行 |
| skills/research-lookup/SKILL.md | 1–170行 | e2f57fed797930e0e5a055ba7f1fa4fc46a004ba | MIT标记；Parallel接口；证据包/来源矩阵；默认参考数量需缩小 |
| skills/sympy/SKILL.md | 1–80行 | 392497a3d5c0972110c85123ba46dc0cb80dc911 | 数学与代码生成；需另查完整许可和运行资源 |
| skills/experimental-design/SKILL.md | 1–90行 | 46227bb09abd5afa7db91fb6eefba1bbafc523b4 | MIT标记；numpy/pandas/pyDOE3；试验设计 |

局部阅读 != 完整源码审计 != 安装 != 运行测试 != 科学有效性验证。
这些候选都未自动批准。本包测试只覆盖自写本地检查工具。
