---
name: bounded-experiment-planning
description: Propose a small batch for model-predicted target verification, parameter-space coverage and baseline replication; use calibration-only proposals when data checks fail.
compatibility: Uses local NumPy/SciPy plus the calibration adapter. No pyDOE3/BoTorch or simulation software needed.
metadata:
  version: "0.3.0"
---
# Bounded experiment planning

Read the calibration result and `registry/reviews/planning-001.json`.
Adapted from K-Dense experimental-design workflow: retain replication and randomized run order.
We use our own attainable-grid/maximin code and SciPy LatinHypercube for large candidate spaces,
NOT the upstream pyDOE3 scripts. Do not call this Bayesian optimisation or information-gain maximisation.

- User-supplied bounds and steps are required; zero implicit device limits.
- Only models passing the preset diagnostic gates may rank candidates by target error.
- Predict only inside the fit-data convex hull (or observed time interval), not merely the rectangular bounds.
- A coverage trial may be outside the fit hull, but its prediction is null and human approval is required.
- Reserve a concurrent independent baseline specimen. Old measurements do not constitute fresh controls.
- Randomise suggested run order reproducibly; the user must approve physical execution.
- No numeric prediction interval is implemented; CV error is not a confidence interval.
- Return an empty measurement import template; never synthesize a purported follow-up experiment.

This adapter is called by calibration_planning.propose after measurement validation.
The plan is a finite-grid heuristic and candidate set, never a proven global/physical optimum.
