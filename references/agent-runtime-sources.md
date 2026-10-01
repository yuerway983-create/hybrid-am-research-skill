# v0.4 source and implementation notes

Reviewed 2026-10-01.

- Agent Skills integration: https://agentskills.io/client-implementation/adding-skills-support
  Used for discover / activate / execute separation. Runtime registry is reviewed local candidates.
- OpenAI function calling: https://developers.openai.com/api/docs/guides/function-calling
  Used for tool schemas, function_call_output, call_id and sequential tool execution.
- OpenAI reasoning continuation: https://developers.openai.com/api/docs/guides/reasoning
  Preserve every output item in memory, including encrypted reasoning, when store=false.
- OpenAI data controls: https://developers.openai.com/api/docs/guides/your-data
  store=false does not itself promise zero data retention. User authorizes external data use.
- K-Dense statistical-analysis at commit 91497e335489dcb544ec8ddc8f6b7ce5fd6d1121:
  https://github.com/K-Dense-AI/scientific-agent-skills/blob/91497e335489dcb544ec8ddc8f6b7ce5fd6d1121/skills/statistical-analysis/SKILL.md
  Actual GitHub search/read in this conversation. Selection/adaptation: registry/reviews/feedback-001.json.

New code does not run upstream inferential tests or assume those recommendations automatically apply.
Descriptive quantities are computed explicitly. Per-trial averages use equal batch weighting when
batch_id is the declared independent unit. Contrasts use the difference in mean absolute target
error within shared batches, then equal-weight batches. No confidence intervals or causal inference.

The historical CV/holdout report is preserved. Follow-up observations are first scored with the
frozen model at actual settings. The optional update export retires old holdout; it is a new
training-data proposal, not a newly validated model. No automatic acceptance threshold changes.

The dispatcher is a controlled allowlist, not a complete operating-system security sandbox.
Input/call provenance is operator-declared, not externally signed or laboratory-certified.
