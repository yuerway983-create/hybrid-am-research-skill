---
name: descriptive-feedback
description: Import logged execution and new measurements against a frozen hybrid-AM plan; compare contemporaneous baseline and candidate outcomes descriptively.
metadata:
  version: "0.4.0"
---
# 实验反馈与模型比较
1. The operator must attach a manifest, execution CSV and measurement CSV. Never generate measured values.
2. Execute import_results; check source kind, context, units, dates, sample ids and actual-versus-planned settings.
3. Execute compare_results BEFORE any refitting. Predictions come from the frozen original model.
4. Technical repeats are averaged within sample. Grouping follows the predeclared protocol.
5. A candidate is compared only to eligible same-batch contemporaneous baseline samples.
   Missing baseline -> inconclusive. No statistical significance tests or confidence intervals in this adapter.
6. Report negative/null outcomes. Synthetic data always remain synthetic, including effect sizes.
7. An execution log is a reported observation, not a hardware-control approval or laboratory authenticity certificate.
8. Do not infer material strength, cure, fatigue or device performance from geometric width.
This local implementation is informed by the statistical-analysis and experimental-design workflows.
Their original scripts are not run. Actual tools are feedback_tools.import_feedback/compare_feedback.
