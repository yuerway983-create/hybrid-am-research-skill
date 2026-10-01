# Hybrid-AM Research Skill · v0.2

**文献取证 → 模型可行性判断 → 可执行的轻量计算子模块。**

这是面向混合 VPP–DIW 研究的主控 Skill。研究主线保持不变：输入目标与数据、
查文献、准备轻量模型、比较候选参数、推荐试验，再用真实打印与测试更新模型。
每个技术阶段按需要选择、审核和使用 GitHub 子 Skill。

## 本版已经做了什么

| 项目 | 当前状态 |
|---|---|
| 文献子 Skill 比较 | 实际读取两个候选全文说明及相关源码，记录来源、固定提交、选择理由与适配方式 |
| 文献取证 | 在聊天宿主中实际检索并核对原文；冻结为4个来源、6条判断的证据包 |
| 轻量计算 | 新增浓度分布扩散矩工具；不调用专用模拟软件 |
| 数学核查 | 8项 SymPy 检查通过；不是材料或制造验证 |
| 软件测试 | 63项本地测试通过；包括继承的17项起步测试 |
| 缺失信息处理 | 缺扩散系数、要求未支持的几何宽度时停止，不生成虚构结果 |

**这不是已完成的打印参数优化系统。** 当前数值案例使用明确标注的合成参数。
还没有真实材料标定、轨迹宽度映射、ML拟合、优化器、设备连接或成品性能验证。

## 最快查看

- [本阶段报告](reports/PHASE2_REPORT_ZH.md)
- [模型依据、范围及缺口](references/model-feasibility.md)
- [文献与模型子 Skill 选择记录](registry/reviews/literature-001.json)
- [可读文献证据表](reports/evidence-pass-v0.2/summary.md)
- [已执行演示](reports/stage2-demo/summary.md)
- [真实实现状态](references/implementation-status.md)

从本目录运行；输出目录必须是新的：

```text
python scripts/stage2_demo.py --out runs/demo-02
python -m unittest discover -s tests -v
```

以上仅使用 Python 3.10+ 标准库。另有可选的符号核查，要求宿主已经安装 SymPy：

```text
python scripts/verify_diffusion_symbolic.py --out runs/symbolic-02.json
```

本次核查环境：Python 3.13.5、SymPy 1.14.0。项目不会自动安装软件。
`requirements-symbolic.txt`只列可选依赖；无密钥、无设备操作。

## 当前可以计算什么

固定材料、沉积及温度条件，给定参考时刻的浓度分布标准差和扩散系数，计算：

`sigma(t)^2 = sigma0^2 + 2*D*t`

论文给出的是线源关系 `sigma^2=2Dt`；有限初始高斯宽度是本项目显式推导的扩展。
输出是浓度分布的方差、标准差和高斯半高全宽，不是照片中几何轨迹宽度。
任何转化都需要单独的观测定义和标定。当前时间是相对于参考剖面的经过时间，
不能自动替代任意设备中的设定曝光延迟。

## 什么是真正执行过的，什么是回放

本阶段的 GitHub 搜索、文献读取和选择由具备工具的聊天宿主执行。
文献流程透明适配自 K-Dense research-lookup：使用宿主的授权检索工具，
不是运行原版 Parallel 后端脚本。原版脚本没有执行，项目也未读取API密钥。

下载后的 `stage2_demo.py` 是冻结证据包的离线检查与合成计算回放：
**不会新搜索 GitHub、重新检索原文、调用LLM API或自动选择并安装新技能。**
主 `SKILL.md` 给有网络和终端能力的宿主提供选择/执行规则；完整自主路由尚待接入。

## 目录

- `SKILL.md`：主控流程与验收规则。
- `skills/hybrid-am-evidence/`：经过明确适配的文献取证子 Skill。
- `skills/diffusion-moments/`：本项目的扩散矩计算子 Skill。
- `evidence/delay-evidence-001/`：文献、主张、实际读取范围和缺口。
- `registry/reviews/`：两次真实的子 Skill 选择记录。
- `scripts/`、`tests/`：可执行工具与测试。
- `examples/diffusion-demo/`：合成计算及两个停止案例。
- `templates/diffusion_*.json`：故意不完整的真实标定输入模板。
- `reports/legacy-v0.1/`：继承的旧报告，不代表v0.2当前状态。

旧的 `scripts/demo.py` 仍保留为v0.1起步回归用例，默认仍停在 needs_evidence_and_model；
本版请运行 `stage2_demo.py`。

## 下一步

先取得同一材料与固定条件下的测量定义和标定数据。只有几何宽度数据时，
优先考虑明确标注的经验宽度模型，不把经验系数冒称分子扩散率。
完成可识别性与留出验证后，再接参数推荐模块。暂不扩大到复杂零件或疲劳预测。

这是本地交付包，未安装到用户电脑、未创建或发布远程GitHub仓库。
第三方文件及改造来源见 [许可说明](THIRD_PARTY_NOTICES.md)。
