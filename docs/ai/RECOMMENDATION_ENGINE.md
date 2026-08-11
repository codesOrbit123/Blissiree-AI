# Recommendation Engine

Blissiree separates two product decisions:

- Boost collection: immediate or short-term support for what the user needs now.
- Program: a structured, sequential, longer-term journey requiring stronger evidence and readiness assessment.

## Deterministic order

1. T0–T7 safety triage.
2. Classify `support_horizon`: `IMMEDIATE`, `SHORT_TERM`, `LONG_TERM`, `BOTH`, or `UNCLEAR`.
3. Calculate separate Boost and program relevance.
4. For immediate needs, route the dominant need to one of the 61 current collection names.
5. Recommend one primary collection. Individual audio titles remain unavailable until verified collection membership exists.
6. If routing is unclear, ask one clarification question.
7. Assess a program only for explicit program requests, meaningful persistence, repeated patterns, deeper-change intent, or authoritative routing evidence.

Programs are never appended as generic upsells. A single emotion does not authorize a program recommendation. Safety can block every content recommendation.

Collection names and legacy mappings come from `AUDIOS - old and new bundles_collections.xlsx`. User-facing output uses the current display name. The model may communicate an eligible result but may not create eligibility or invent titles.
