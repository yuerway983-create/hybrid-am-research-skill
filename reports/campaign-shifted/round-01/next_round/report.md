# Hybrid-AM v1.0 执行与回传报告

数据标记：**synthetic_demo**；执行来源：`deterministic_demo`。
当前状态：`awaiting_external_experiment`。
本程序没有打印、没有运行专用模拟软件。来源标记由操作者声明，不是独立真实性认证。

## 实际完成阶段
{
  "inspected": true,
  "evidence_checked": true,
  "calibrated": true,
  "planned": true,
  "feedback_attached": false,
  "imported": false,
  "compared": false,
  "update_prepared": false
}

## 候选实验（未由软件批准或执行）
| 编号 | 目的 | 参数 | 冻结预测 μm |
|---|---|---|---|
| T03 | baseline_replication | {"speed_mm_s": 5.0, "delay_s": 3.0} | None |
| T01 | coverage_or_calibration | {"speed_mm_s": 12.5, "delay_s": 2.0} | None |
| T02 | coverage_or_calibration | {"speed_mm_s": 12.5, "delay_s": 4.0} | None |

## 下一步
finish_report
WAIT: operator must attach new reported measurements; never invent them

## 审计
events.jsonl 记录实际请求、响应、调用来源、哈希与错误；calls/保留结构化结果。
程序日志证明代码执行，不证明实验真实性；固定回放不是在线LLM运行。
