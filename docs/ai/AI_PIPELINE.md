# AI Pipeline

Stage A returns schema-validated observations only. There is no inferred `diagnosis` field; professional diagnoses explicitly reported by users are represented separately as `user_reported_diagnoses`.

The backend applies deterministic triage, eligibility, and provenance-aware retrieval. Stage B receives a constrained response contract. A deterministic validator checks output and falls back safely on failure.

Current state is request-scoped. Long-term state must be persisted separately and changed only using multiple observations, explicit answers, and program history.
