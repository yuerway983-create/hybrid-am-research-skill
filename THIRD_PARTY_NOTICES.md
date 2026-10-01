# Third-party notices and adaptation record

## K-Dense Scientific Agent Skills

Repository: https://github.com/K-Dense-AI/scientific-agent-skills
Reviewed commit: `91497e335489dcb544ec8ddc8f6b7ce5fd6d1121`.

`skills/hybrid-am-evidence/SKILL.md` is a transparent adaptation of the MIT-licensed
research-lookup workflow. Host-approved retrieval replaces its Parallel backend;
large-reference targets and unrelated report-generation steps are removed.
Licence notice: `third_party/kdense/LICENSE.txt` (Copyright 2025 K-Dense Inc.).

We also read literature-review and its verify_citations.py to compare workflow fit,
and read SymPy skill guidance for a symbolic-to-numeric verification workflow.
Those upstream executable scripts were NOT copied or run. The upstream instructions
are not treated as privileged commands. Actual file/blob identifiers are in the registry.

Attribution:
Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026).
Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents.
arXiv:2609.00065. https://arxiv.org/abs/2609.00065
Author list verified from the arXiv record on 2026-10-01.

## Original local code and optional dependencies

The local numeric, evidence-check and replay scripts are new project implementations.
SymPy is an optional installed dependency; its binaries/source are not redistributed here.
It has its own upstream licence: https://github.com/sympy/sympy/blob/master/LICENSE .
The root project publication licence and repository visibility should be decided by the user
before public release. No licence claim here supersedes third-party permissions.

## Scientific publications and data

The packet stores original summaries, equations and locators; no publisher PDFs, figures,
article-full-text dumps or user-provided PDFs are bundled. A DOI is attribution, not a
blanket permission to redistribute figures or source data.

No NIST metrology code, TrillyD13 printlog code, BoTorch code or BaratiLab code is vendored
in v0.2. They remain previously discussed candidates, not implemented dependencies.
All numerical example coefficients are synthetic; source papers are not local experiments.


## v0.3 additions

Reviewed K-Dense scikit-learn (declares BSD-3-Clause), experimental-design (MIT),
and pymoo (Apache-2.0) at the same fixed commit. No upstream code/skill text is vendored
for these additions. Project-owned adapter descriptions and implementations reference the
workflows; actual computations call separately installed NumPy, SciPy and scikit-learn.
Preserve each upstream component's own license if later vendoring code; root MIT must not
be assumed to supersede a sub-skill's license. We did not execute upstream helper scripts.
The existing K-Dense notice remains for the v0.2 evidence-workflow adaptation.

Method documentation consulted: official SciPy lsq_linear/LatinHypercube and sklearn
cross-validation pages, 2026-10-01. Exact installed versions are recorded in every run.
No package binaries, publisher PDFs, article figures or third-party datasets are bundled.
The illustrative CSVs are project-created synthetic software test data.


## v0.4 additions

The statistical-analysis workflow was read through the GitHub connector at commit
91497e335489dcb544ec8ddc8f6b7ce5fd6d1121 (MIT declared in SKILL.md). Its original
Python examples were not copied or run. Our descriptive-feedback adapter implements
project-specific plan/log/measurement joins and conservative descriptive comparison.
The existing K-Dense notice is retained. Per-skill declarations for other retained
workflows remain as recorded in earlier reviews; do not relabel all upstream content MIT.

OpenAI Responses function-calling and Agent Skills integration documentation were
consulted for protocol design. llm_agent.py is project-authored, uses the stdlib HTTP
client, and was contract-tested with a mock transport, not a live paid API.

## v1.0 additions

Read the experimental-design sequential_and_adaptive.md at the same pinned K-Dense commit
via the GitHub connector. The new round_tools.py, synthetic_campaign.py and campaign_demo.py
are project implementations. No new upstream code is copied. Prior notices remain intact.
scikit-learn common-pitfalls, Agent Skills trust/activation and OpenAI function-calling docs
were consulted for methodological and protocol checks. Online docs do not certify this software.
The project-owned publication licence remains an owner decision before making a public repository.
