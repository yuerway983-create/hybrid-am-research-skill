# Documentation verification — v1.1.3

This record is new in the documentation revision. It records local software and presentation checks, not new scientific validation. The checks below were performed on 2026-10-11 for the local documentation candidate, before publication was authorised.

## Executed checks

- Existing full suite: `python -X utf8=0 -m unittest discover -s tests` — 347 tests passed in 29.088 seconds.
- `python scripts/preflight.py` — dependencies discoverable; Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0, scikit-learn 1.8.0. This is not a clean dependency installation test.
- `python scripts/campaign_demo.py --out <delivery-directory>/quickstart-vpp-diw-1` — deterministic synthetic campaign completed two feedback/update rounds; third round awaiting external experiment. No LLM, hardware or solver call.
- `python scripts/foam_model.py run --task examples/foam-refinement-demo/task.json --out <delivery-directory>/quickstart-foam-1` — `synthetic_calculation_complete`, numerical gates passed. This does not establish real foam performance.

Both output directories were new and outside the repository. Bundled Python and pre-existing test dependencies were used.

- Main Skill structural check: `python <skill-creator>/scripts/quick_validate.py .` — `Skill is valid!`.
- `git diff --check` — passed. Git emitted only existing LF/CRLF conversion notices.
- The ten existing fenced command blocks in `HOST_START.md` were compared with the base commit and are unchanged.

The full suite used the existing local test dependency directories through `PYTHONPATH` and the bundled Python interpreter. The `-X utf8=0` flag matches the existing Windows test environment. These are software regression checks, not a new LLM-host run or an installation test on a clean machine.

## Documentation build

The original repository had no dedicated documentation check command. This revision adds `docs/build-docs.mjs` for local HTML export, links/anchors, bilingual field counts and Mermaid/SVG source consistency. It does not execute or change research tools.

Use Node.js 22 or later and `marked@17.0.5`. Dependencies may be installed outside the repository with `npm install --prefix <docs-tools-directory> marked@17.0.5`; set `NODE_PATH` to that directory's `node_modules` before running:

```sh
node docs/build-docs.mjs
node docs/build-docs.mjs --check
```

For users needing a mainland China mirror, `--registry https://registry.npmmirror.com` is optional for dependency installation. Reading the built HTML and SVG needs no Node, npm, external fonts or network.

The initial build and check both passed: **10 Markdown documents, 208 local Markdown links, 10 HTML pages, 177 local HTML links/assets, 24 fragment checks, 2 same-source diagrams and 108 bilingual fields per language**. The checker rejects stale HTML exports, stale diagram source hashes, duplicate HTML IDs and missing local anchors. Release links are restricted to the current distribution version and the retained previous version.

The current README workflow was compared with the historical research line in commit `d1f90bb9f3427a4e81fa98b31ab1ebf05dfc2105`. Only its research logic was retained; no old installation instructions, version metadata or capability claims were restored.

## Actual browser previews

Local headless Microsoft Edge, controlled with Playwright, rendered `file://` pages with HTTP(S) requests blocked. Screenshots were taken from actual browser rendering, not mock-ups.

- Static page in both languages: 1440 px desktop and 390 px mobile. No document-width overflow, missing local anchors, JavaScript errors or failed workflow images; no external asset request occurred.
- English and Chinese README HTML previews: 1280 px desktop. Chinese anchor checks decode URL fragments before comparing IDs.
- All nine exported guide pages were checked at desktop and mobile sizes, with local navigation and anchors checked.
- JavaScript-disabled mobile reading: English core content remains visible and the Chinese offline overview link remains available.
- Both workflow SVGs include accessible title/description, local source hashes, feedback arrows and responsive view boxes; there are no external images or `foreignObject` dependencies. Region labels were visually checked for arrow overlap.

Actual preview PNGs are delivered separately in `previews/` and `workflow-render/`, alongside the ZIP, not embedded in the research package. README previews use the local Markdown export; they are **not** screenshots of a newly published GitHub page.

## Package checks

The candidate contains **728 files**, including the root `MANIFEST.json`; that manifest lists the other **727 files**. Package preparation uses the base Git archive plus an explicit documentation-only overlay, without staging files or making a commit. UTF-8 documentation files use LF line endings, and hashes are computed from the actual staged package bytes.

All **697 baseline files outside the nine edited existing entry/metadata files** were byte-compared with the base Git archive. This includes scientific programs, sub-Skills, registry, schemas, examples, templates, evidence, references, tests, historical reports and licences. They remain unchanged. There are 22 new documentation/asset/export files.

The archive root is `axiom-research/`. Packaging excludes Git metadata, virtual environments, caches, local run output, private data, environment files, keys, dependencies installed for documentation tooling and old ZIPs. The archive checksum is delivered in the separate `SHA256SUMS.txt`; a final extraction and manifest check are recorded in the accompanying `package-verification.json`.

## Scope and publication

The base is commit `0adb4794d38385b4fb23b417a4caf253eedfd589`. Public release v1.1.2 was verified before editing. During the initial local-delivery phase, no push, release, tag or public About edit was performed. The user subsequently authorised publication of v1.1.3. Release preparation replaces pending-version labels, refreshes local HTML exports and rebuilds the current manifest and ZIP checksum; runtime and sub-module versions remain unchanged.

Computational tools, sub-Skill directories and IDs, schemas, registry, data partitions, validation gates, evidence, historical reports, licences and numerical outputs are outside this change. The main Skill's scope description and operational rules remain intact; only its introduction, display headings and distribution metadata change.

Not covered by the initial checks: public deployment or GitHub-hosted Markdown rendering after upload. A clean-machine dependency installation, live LLM orchestration, live literature retrieval, commercial-solver integration, equipment control and physical materials experiments were not performed and are not implied by this documentation patch. GitHub Pages was not enabled on the inspected repository; the static page is a local/repository artifact. Publication does not enable additional website hosting.
