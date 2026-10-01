# Hybrid-AM v1.0 执行与回传报告

数据标记：**synthetic_demo**；执行来源：`deterministic_demo`。
当前状态：`next_round_ready`。
本程序没有打印、没有运行专用模拟软件。来源标记由操作者声明，不是独立真实性认证。

## 实际完成阶段
{
  "inspected": true,
  "evidence_checked": true,
  "calibrated": true,
  "planned": true,
  "feedback_attached": true,
  "imported": true,
  "compared": true,
  "update_prepared": true
}

## 候选实验（未由软件批准或执行）
| 编号 | 目的 | 参数 | 冻结预测 μm |
|---|---|---|---|
| T03 | baseline_replication | {"speed_mm_s": 5.0, "delay_s": 3.0} | 498.2893527797503 |
| T01 | predicted_target_candidate | {"speed_mm_s": 7.5, "delay_s": 4.25} | 499.91959294782254 |
| T02 | coverage_or_calibration | {"speed_mm_s": 7.5, "delay_s": 2.0} | 470.0355652064819 |

## 回传数据的描述性对照
不是统计显著性结论。合成数据的任何改善或变差都不是实际制造成果。
| 编号 | 独立组数 | 平均目标绝对误差 μm | 冻结模型RMSE μm |
|---|---|---|---|
| T03 | 3 | 2.4869518655293255 | 0.817496076400844 |
| T01 | 3 | 4.284024997415344 | 4.370658231671031 |
| T02 | 3 | 25.907882546422247 | 4.06504054016338 |

T01: descriptive_worsening；同批基准误差减去候选误差=-1.7970731318860185 μm；共享批次=3。

T02: descriptive_worsening；同批基准误差减去候选误差=-23.420930680892923 μm；共享批次=3。

不推断界面强度、疲劳或器件性能；没有置信区间与p值。

## 冻结候选模型
状态：frozen_candidate_needs_fresh_confirmation；只拟合update/measurements.csv，未使用确认数据。

## 新模型验收
状态：updated_model_rejected；允许用于下一轮候选预测：False。
{"cv_within_preset_tolerance": true, "cv_beats_constant_if_required": true, "positive_fit_and_cv_predictions": true, "fresh_independent_groups": true, "confirmation_inside_training_domain": true, "positive_confirmation_predictions": true, "confirmation_within_preset_tolerance": false, "non_degradation_if_comparable": true}
确认数据验收后即成为已使用数据，不再算独立测试。

## 下一轮已创建
进入next_round/，继续由主控选择规划Skill。没有执行真实打印。

## 下一步
finish_report
SWITCH_SESSION: next_round; select the planning skill there

## 审计
events.jsonl 记录实际请求、响应、调用来源、哈希与错误；calls/保留结构化结果。
程序日志证明代码执行，不证明实验真实性；固定回放不是在线LLM运行。
