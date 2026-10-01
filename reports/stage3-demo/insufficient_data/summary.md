# v0.3 标定与实验规划结果

模式：**offline_demo / synthetic_demo**。
合成数据只用于软件演示；数值检查通过不代表真实材料模型已验证。

观测量：`geometric_track_width_um`；状态：`calibration_plan_without_validated_predictions`。

## 模型检查
数值拟合：False；可用于候选排序：False。
留出数据未用于拟合或超参数选择；重复测量先聚合，验证按独立组划分。
交叉验证误差不是每个候选点的置信区间；本版本不输出±精度。

未通过或缺失：
- Need at least three independent fit groups for this prototype's grouped diagnostics; this is not a sample-size guarantee

## 下一轮试验（待人工确认）

| 次序 | 编号 | 目的 | 参数 | 预测值（μm） |
|---|---|---|---|---|
| 1 | T03 | baseline_replication | {"speed_mm_s": 5.0, "delay_s": 3.0} | 不提供 |
| 2 | T01 | coverage_or_calibration | {"speed_mm_s": 15.0, "delay_s": 2.0} | 不提供 |
| 3 | T02 | coverage_or_calibration | {"speed_mm_s": 13.0, "delay_s": 5.0} | 不提供 |

覆盖性试验采用距离准则，不宣称最优信息增益。超出训练凸包不提供预测。
没有新实际打印/测试，因此不能报告成品性能改善。真实设备范围仍须人工核查。
`measurement_import_template.csv`为空白表头模板，不包含编造的新测量。
