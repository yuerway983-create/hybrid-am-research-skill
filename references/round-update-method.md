# Frozen update and continuation

This is a project-specific sequential DEVELOPMENT workflow, not a confirmatory clinical-study protocol.
We consulted the existing scikit-learn calibration workflow and K-Dense experimental-design reference at
commit 91497e335489dcb544ec8ddc8f6b7ce5fd6d1121. No upstream example script is copied or automatically executed.
The latter warns that repeatedly looking at data is not a valid unadjusted significance-testing scheme.
Accordingly this package makes descriptive comparisons only, reports no p-values and claims no stopping-time inference.

1. Evaluate old predictions and concurrent baseline before any update.
2. Use previously fitting samples plus eligible follow-up samples for the fixed-class refit.
3. Retire old holdout; do not silently assign it to fresh validation.
4. Freeze updated coefficients, preprocessing, target, bounds and thresholds.
5. Generate a bounded confirmation coverage plan, with independent groups to be newly measured.
   These confirmation experiments are a separate cost and not covered by next_trials.
6. Attach declared independent confirmation after freezing the candidate, score once and compare
   candidate/previous model on the same set when both are in-domain. Apply unchanged tolerance and
   predeclared non-degradation margin. This is model acceptance, not an unbiased final test estimate.
7. When pass: inherit accepted snapshot in a new child session and propose again. When fail or absent:
   allow only calibration-only continuation. Do not silently keep trusting the old model under drift.
8. No confirmation is used to fit that candidate. After acceptance all confirmation is consumed and
   cannot be treated as a new test set in later rounds. Final scientific claims require new confirmation
   outside this development process; the package does not manufacture it.

Group counts and conditions are prototype settings, not a power calculation. IDs can catch declared
reuse but cannot detect relabelled specimens or authenticate a laboratory record. Technical repeats
are averaged, and comparisons respect the declared batch/sample grouping. No confidence intervals.

Primary methodological references consulted 2026-10-01:
- https://scikit-learn.org/1.9/common_pitfalls.html
- https://github.com/K-Dense-AI/scientific-agent-skills/blob/91497e335489dcb544ec8ddc8f6b7ce5fd6d1121/skills/experimental-design/references/sequential_and_adaptive.md
- https://agentskills.io/integrate-skills
- https://developers.openai.com/api/docs/guides/function-calling

Library versions actually executed are frozen in requirements-calibration.txt, not inferred from a web page.
