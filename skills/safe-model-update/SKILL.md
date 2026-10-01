---
name: safe-model-update
description: Version model updates, score fresh confirmation and create the next round without recycling test data.
metadata:
  version: "1.0"
---

# Safe model update and round continuation

1. Call prepare_update only after original predictions were scored and concurrent
   same-batch results compared. Preserve negative results.
2. Call refit_update. It freezes a new candidate using fit rows only and produces
   a separate prospective confirmation plan. Model class, thresholds, target and
   bounds remain fixed. The numerical library, not the LLM, does the fitting.
3. If no operator-attached confirmation exists, stop and request it, or start a
   calibration_only next round with no validated numerical predictions. Never
   create response data. The synthetic environment is test/operator code only.
4. After operator attachment, call evaluate_update. If any numerical or
   non-degradation gate fails, do not promote the model or change thresholds.
5. On pass: start_next_round with mode=validated_update. On failure/missing data:
   use calibration_only or finish_report. Follow the declared maximum-round budget.
6. Switch the host to the returned next_round session; choose and activate its
   planning skill before plan_experiments. Repeat only when external data arrive.

Retired holdouts and confirmations stay in their original round, never silently
reused for fitting or claimed as fresh evaluation. Identifiers/provenance are
operator declarations, not an authentication of physical measurements.
A model passing development gates is not proof of scientific truth, causal
performance improvement or calibrated uncertainty. No p-values/intervals here.

The project implements numerical adapters using scikit-learn/SciPy; upstream
workflow reference: registry/reviews/round-update-001.json. Original K-Dense
example scripts are not automatically executed.
