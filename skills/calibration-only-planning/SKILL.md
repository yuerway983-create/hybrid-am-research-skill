---
name: calibration-only-planning
description: Generate calibration, coverage and baseline-repeat proposals when current response models fail evidence gates.
metadata:
  version: "0.4.0"
---
# 标定实验规划
Read the actual calibration result and failure reasons. Do not relax acceptance thresholds.
Execute plan_experiments. When the current model failed, prediction cells must remain empty.
This is the project's adapter of experimental-design workflow, not upstream code execution.
Do not call maximin distance information gain. Await real operator-attached observations.
