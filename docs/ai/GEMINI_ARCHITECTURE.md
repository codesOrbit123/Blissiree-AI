# Gemini Architecture

Gemini is the managed language platform for Blissiree 2.0 v1. The backend owns safety, state, content eligibility, provenance, and auditability. Gemini owns structured language extraction and natural conversation.

Pipeline: request → structured Flash-Lite analysis → deterministic T0–T7 triage → eligibility → retrieval → response contract → Flash conversation → output validation.

The previous self-hosted Qwen/GPU architecture is **SUPERSEDED**. Its artifacts remain only as decision history and are not part of the production runtime.
