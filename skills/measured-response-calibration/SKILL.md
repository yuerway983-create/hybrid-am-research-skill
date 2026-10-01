---
name: measured-response-calibration
description: Fit and diagnose either a fixed-condition concentration-moment model OR an explicitly empirical two-factor geometric-width response model. Never map one observable to the other.
compatibility: Python 3.11+ with NumPy, SciPy and scikit-learn; tested versions in requirements-calibration.txt. Local/offline only.
metadata:
  version: "0.3.0"
---
# Measured-response calibration

Read `references/stage3-methods.md`, `registry/reviews/calibration-002.json` and the task before running.
This is a project-owned adapter informed by the reviewed K-Dense scikit-learn workflow;
it is not the upstream example runner and does not silently install anything.

1. Require `schema_version=0.3`, explicit measurement quantity/method/units and provenance.
2. Validate CSV and partition integrity. Aggregate technical repeats; use declared independent groups.
3. Concentration data: condition on fixed deposition and pre-gel assumptions; fit bounded variance.
4. Geometric data: use preset degree and alpha in a fold-local sklearn Pipeline. This does not infer D.
5. Use GroupKFold on fit groups. Fit final coefficients on fit rows only; evaluate untouched holdout separately.
6. Record constant-predictor baseline, failures, errors and exact groups. No uncalibrated ± intervals.
7. Failed/insufficient evidence goes to calibration planning; don't auto-lower acceptance thresholds.

Execute `python scripts/calibration_planning.py --task <task.json> --out <new_dir>` from repository root.
A passed numerical gate is not physical validation. Outputs remain drafts needing scientific review.
No external code execution, hardware, physics solver, LLM API or live literature request occurs in this command.
