---
name: hybrid-am-evidence
description: Gather a bounded, source-located evidence packet for a hybrid VPP-DIW process question; distinguish literature, local measurements, and missing calibration.
license: MIT
compatibility: A host with authorised scholarly web retrieval and file tools. The Python evidence checker is offline; it does not retrieve sources.
metadata:
  version: "0.2.0"
  adaptation-basis: "K-Dense research-lookup at 91497e335489dcb544ec8ddc8f6b7ce5fd6d1121"
---

# Hybrid-AM evidence pass

This is an explicit adaptation, not the unchanged Parallel-backed research-lookup runner.
Retain its scope, provenance, contradictory-evidence and access-level discipline; replace
the backend with host-approved retrieval. No mandatory reference count or figures.

1. Read the main task, input status, prior packet, and registry/reviews/literature-001.json.
2. State one bounded research question and output contract. Exclude confidential input from web queries.
3. Search reviewed candidates first. New GitHub skills require source/permission/implementation review.
4. Search primary publications. Use supplied files for their own contents. Read the relevant text;
   inspect figures when the decision requires them. Report failed visual retrieval, never infer pixels.
5. Build evidence_packet.json: source identity, actual access level and locations, equations,
   conditions, limitations, claim-source links, and explicit calibration gaps. DOI existence does
   not verify a scientific claim. Do not reclassify an abstract as full text.
6. Use the installed local checker: python scripts/review_evidence.py --packet <file> --out <new_dir>.
   It checks structure, not the truth of source interpretations. Host review remains required.
7. If the required model coefficients or observation map are absent, return needs_calibration.
   Do not harvest unrelated literature coefficients to make a numeric demonstration look real.
8. Log actual tools and adaptations. A cached packet replay is not a new live literature search.

The successful host-assisted run is documented in evidence/delay-evidence-001/search_ledger.json.
See ../../third_party/kdense/LICENSE.txt and ../../THIRD_PARTY_NOTICES.md.
