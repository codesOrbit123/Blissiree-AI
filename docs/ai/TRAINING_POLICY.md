# Blissiree Qwen Training Policy — SUPERSEDED

This self-hosted Qwen/QLoRA plan is retained as architectural history and is not used by the Gemini v1 production runtime. See `GEMINI_ARCHITECTURE.md`.

Fine-tuning teaches companion behavior, persona consistency, non-medical boundaries, safety ordering, structured responses, and refusal to infer unapproved benefits. Mutable product facts and eligibility decisions remain retrieval-authoritative.

No generative model can guarantee zero hallucinations. Production controls therefore require deterministic triage, approved-content filtering, provenance, abstention when evidence is missing, response-schema validation, and regression evaluation in addition to QLoRA.

Unapproved Boost titles appear only in negative examples that teach the model not to recommend from titles alone.
