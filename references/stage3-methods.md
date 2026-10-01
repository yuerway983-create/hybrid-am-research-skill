# v0.3 方法、来源和可检验边界

## 0. 与v0.2关系

v0.2文件及证据保留。其浓度矩公式用于固定条件下的窄模型；本版没有新获取Small补充图S5。
本版新增的是标定和经验响应建模工具，不补写论文尚未取得的测量映射。
几何宽度分支是明确独立的经验模型，不从浓度方差转换得到。

## 1. 输入、数据来源与重复

文件必须显式标注synthetic_demo、measured或public_measured，且与运行模式一致。
软件不能认证用户声明或判断照片刻度真实性；source_ref和context_id是可追溯入口，非真实性证明。
所有测量暂要求μm，时间s，速度mm/s。实际条件必须对应同一材料和context_id。

同一样品/条件的技术重复先聚合。给定sample_id或batch_id作为独立验证单元。
每个组的行权重总和一致，避免某组因为记录多而主导误差。对于未记录的更高层级依赖，
该规则仍不能消除混杂；需要研究者选择合适组别。不是通用混合效应模型。

## 2. 扩散标定分支

拟合 y² = a + b*t，以组平衡的方差残差最小二乘为目标，a,b非负。
SciPy lsq_linear执行有界拟合，σ0=sqrt(a)，D=b/2。报告的预测误差回到sigma的μm单位。
若无约束斜率明显为负，则当前常D扩散假设不合适，停止此模型。
该方法不把量测sigma的噪声传播成最优方差权重，也不估计参数置信区间；测量噪声大时需更合适似然。
未观测t=0时初始宽度属模型外推，输出会注明。该模型不确定固化阈值或几何宽度。
估计D是条件性拟合值，不能仅据拟合优度称为分子扩散系数。

## 3. 几何宽度经验分支

预先指定一次/二次PolynomialFeatures→StandardScaler→Ridge。
多项式次数和alpha写入任务，不通过留出数据选择。每折独立拟合预处理，避免泄漏。
设计矩阵秩不足时不勉强拟合，返回需要更多参数组合的标定计划。
同时计算DummyRegressor常数基准，不以“模型能跑”代替预测价值。

## 4. 验证关口

只在fit分区上做GroupKFold，最多5折，至少3个独立fit组。这是原型的结构门槛，不是样本量充分证明。
最终模型只用fit数据拟合；holdout保留，不回填训练。
要求至少两个独立holdout组，且位于训练凸包/时间范围内，并满足用户事先填写的CV和holdout RMSE容许值。
某些任务可要求CV优于常数基准。所有关口用于筛选，不是科学认证。
边界CV折可能包含相对于该折训练集的外推，因此验证可能比最终域内预测更苛刻。
一次留出检查不等于跨设备、跨材料泛化。最终方案需新样品独立确认。

## 5. 候选与实验设计

用户给出允许范围、可实现的步长、基准和预算。小空间枚举可达网格；超过5000个组合时，
使用SciPy LatinHypercube抽样后映射到可达值并去重。这是量化后的候选子集，不再声称严格LHS性质。
选择目标误差最小的域内候选、归一化参数空间maximin覆盖点及新基准重复，按固定种子随机运行次序。
没有目标优势或候选预算不足时，相应角色可以缺省。基准若未在已有数据出现，输出会提示。
预算小于设计所需试验量时，输出只是下一批次，不是完整DOE或统计功效证明。

训练矩形范围不足以保证插值：二维预测使用训练凸包，时间模型使用已观测时间区间。
域外仍可提议探索性测量，但预测值为null。缺数据或误差关口失败时，所有候选预测为null。
未量化逐点不确定性，不把RMSE复制成±区间。maximin覆盖不是贝叶斯信息增益。
仅对已测的几何或浓度响应选点；界面强度、固化和设备能力未验证，不能宣布工艺合格。

## 6. GitHub子Skill与执行真实性

实际读取：K-Dense scikit-learn、experimental-design、pymoo完整SKILL.md（固定提交见registry）。
复用：v0.2对SymPy的审核。前两者分别作为标定与实验设计工作流依据；pymoo目前不选。
本项目写了适配器，实际调用已安装的SciPy/sklearn，不复制或执行上游示例程序。
源码网络直接下载失败已记录；GitHub连接成功返回原文及指定文件blob SHA。
本地回放不再联网，也不是动态自主搜索。后续真实宿主按主SKILL规则决定复用还是重新检索。

## 7. 主要方法依据（官方文档）

- scikit-learn cross validation：分组、留出与Pipeline。
  https://scikit-learn.org/stable/modules/cross_validation.html
- SciPy bounded linear least squares：
  https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.lsq_linear.html
- SciPy LatinHypercube：
  https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.LatinHypercube.html
- K-Dense固定源路径见registry/reviews/calibration-002.json和planning-001.json。

文档在线版本可能高于本地版本；实际运行环境为numpy2.3.5/scipy1.17.0/sklearn1.8.0，已在该环境测试。
