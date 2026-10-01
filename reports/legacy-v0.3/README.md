# Hybrid-AM Research Skill · v0.3

**测量数据 → 选择标定路线 → 分组验证 → 有界候选参数 → 下一轮试验表。**

研究主线不变：以文献和实验为依据，用适合当前技术步骤的 GitHub 子 Skill 完成计算，
不调用专用模拟软件。本版把原 v0.2 的证据/公式阶段继续接到了数据标定与候选推荐。

> **当前数值演示全部为合成数据。** 代码运行与测试不证明真实打印精度、性能提升或
> 真实材料的扩散行为。没有设备操作，也没有自动连接外部LLM或自动安装GitHub技能。

## 直接查看

- [离线演示网页](reports/stage3-demo/index.html)：无需安装，浏览器打开。
- [第三阶段报告](reports/PHASE3_REPORT_ZH.md)：做了什么、没做什么。
- [使用说明](START_HERE.md)：运行方法和真实数据模板。
- [主控 Skill](SKILL.md)：给具备文件/终端/网络工具的智能体宿主加载。
- [方法、数据要求和限制](references/stage3-methods.md)。

## 新增能力

| 输入类型 | 做什么 | 不做什么 |
|---|---|---|
| 浓度标准差随时间的测量 | 固定条件下拟合 sigma² = a + b*t，估计初始标准差和条件性扩散系数，独立验证 | 不把几何宽度当sigma；不预测固化程度或强度 |
| 几何轨迹宽度＋速度/延迟 | 经验多项式岭回归、常数基准比较、分组交叉验证和留出验证 | 不宣称经验系数就是材料扩散系数 |
| 数据不足或验证不通过 | 生成有界标定/覆盖试验和基准重复，预测栏留空 | 不强行报告最佳参数或虚构精度 |

所有数据要求明确材料、context_id、测量定义、单位、source_ref和fit/holdout分区。
技术重复先按样品和条件聚合；同一独立组不能跨fit/holdout。拟合器不使用留出数据。

## 运行

推荐 Python 3.11+；实际测试 Python 3.13.5。先建立项目虚拟环境，手动安装依赖：

```text
python -m pip install -r requirements-calibration.txt
python scripts/preflight.py
python scripts/stage3_demo.py --out runs/demo-03
python -m unittest discover -s tests -v
```

输出目录必须是新的。库版本固定为本次实际测试环境；安装可能需要网络，
但以上分析/演示命令本身不联网、不读取密钥、不连接设备、不调用模拟软件。
旧的stage2_demo.py与标准库工具仍保留，可以独立运行。

## 科研与执行的两层

**科研层：**目标/数据 → 文献 → 模型 → 候选虚拟试验 → 检查 → 下一轮试验 → 真实测量 → 更新。

**执行层：**由宿主比较GitHub子Skill，阅读和审核后选用；本地工具按约定输出，主控检查。
本次实际通过GitHub连接读取了scikit-learn、experimental-design和pymoo子Skill，
并复用了v0.2对SymPy的审核。选择/不选理由见registry/reviews。

本版本地脚本只在已审核本地适配器之间确定性分流；不在运行时重新搜索GitHub。
读取上游说明、运行本项目适配器和调用上游原版脚本是三件事；本版执行了前两项，
未执行原版示例脚本。SciPy/sklearn是实际使用的库，pyDOE3/pymoo/BoTorch未安装或调用。

## 主要产物

每次运行输出result.json、calibration.json、next_experiments.csv、候选预测表、
分组与样品记录、summary.md和events.jsonl。模型参数以JSON记录，不用pickle。
新测量导入模板仅有表头，不生成假的后续实验；自动新结果回传评价仍待下一版。

## 仍然未实现

完整自主GitHub路由、真实图像测量、实际材料标定验证、贝叶斯采集函数、
点位预测区间、自动回传新实验评价、设备控制和成品性能试验均未完成。
论文证据包继承自v0.2，本次未重新检索混合打印科学文献或取得补充图S5。

项目尚未发布到远程GitHub。许可证与可见性由用户在发布前确认；第三方声明独立保留。
