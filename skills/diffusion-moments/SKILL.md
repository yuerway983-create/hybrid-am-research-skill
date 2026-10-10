---
name: diffusion-moments
description: Evaluate and verify a fixed-condition Gaussian diffusion-moment model from a reviewed evidence packet. Not a geometric-width, curing or mechanical-performance simulator.
compatibility: Python 3.10+ for evaluation; SymPy for the separate symbolic check. No dedicated simulation software.
metadata:
  version: "0.2.0"
---

# 扩散特征计算

Load only after the host has reviewed S1 and model-001. This is a local original
implementation, following the selected SymPy skill's verify-before-evaluate workflow.

- Read the model card and require named units and parameter provenance.
- Preserve sigma (concentration standard deviation), concentration FWHM, and physical track
  width as different quantities. Requests for geometric width or strength must stop.
- Hold speed, pressure, nozzle, material and thermal conditions fixed. There is no speed law.
- Run verify_diffusion_symbolic.py where SymPy is available; exact verification is not material validation.
- Evaluate only explicitly supplied coefficients and an approved time interval.
- Distinguish scenario bounds from probabilistic intervals. Never invent a confidence level.
- Synthetic parameters only support synthetic demonstrations, never physical-improvement claims.
- Real-mode cases additionally need a reviewed local calibration file with matching conditions.

Commands:
python scripts/diffusion_model.py --case examples/diffusion-demo/case.json --out runs/diffusion-01
python scripts/verify_diffusion_symbolic.py --out runs/symbolic-01.json
