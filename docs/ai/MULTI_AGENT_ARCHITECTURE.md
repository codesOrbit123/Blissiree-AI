# Blissiree modular capability architecture

Blissiree presents one continuous Emma or one continuous Ben. “Agent” means an internal capability; it never means a second customer-facing personality.

## Request path

1. Preserve the raw user message.
2. Run deterministic safety checks against raw text and recent context.
3. Use structured Gemini language understanding to produce interpreted meaning, explicit and inferred themes, ambiguity, intent and resolved references.
4. Reconcile the latest message and pending offers deterministically.
5. Route to Reception, Platform Information, Discussion, Content Matching or Booking. Safety can override all routes.
6. Execute the specialist capability using structured contracts and approved knowledge.
7. Generate one final response through the shared Emma/Ben persona layer.
8. Validate safety, claims, approved content, persona consistency, continuity and natural Australian English.

Ordinary turns use at most one structured understanding call and one response-generation call. Known closures, bookings, safety responses and fallbacks remain deterministic where appropriate.

## Capability ownership

- Reception: entry, navigation and true out-of-scope boundaries.
- Platform Information: factual Blissiree explanations from official knowledge.
- Discussion: supportive, friend-like conversation without selecting content.
- Content Matching: approved Boost, collection and Program eligibility and matching.
- Booking: approved practitioner/service identification and booking fulfilment.
- Safety: deterministic triage and override; not a conversational persona.

All customer language is owned by the shared persona response layer. Capability names are returned only as safe admin diagnostics and are never mentioned by Emma or Ben.

## State and continuity

The request carries raw and interpreted messages, explicit and inferred themes, active topic, goal, pending offer and resolved reference. The Test Chat stores safe `active_agent` metadata on the assistant turn so the next request can report the previous capability. Safety decisions are always recomputed and never trusted from client metadata.

For production app accounts beyond this admin test surface, durable summaries, pending offers, declines, booking context and recent recommendations should be persisted in a server-side conversation store rather than Cloud Run process memory.

## Admin UI

Test Chat displays an `Active agent` flag. It exposes only the capability label—never hidden prompts, chain-of-thought, retrieved private instructions or safety reasoning.
