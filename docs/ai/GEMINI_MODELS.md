# Gemini Models

- `GEMINI_ANALYSIS_MODEL`: structured extraction; default `gemini-2.5-flash-lite`.
- `GEMINI_CONVERSATION_MODEL`: Emma/Ben generation; default `gemini-2.5-flash`.
- `GEMINI_EMBEDDING_MODEL`: embedding provider; default `text-embedding-005`.

Identifiers are configuration, not business logic. Production uses Vertex AI workload identity; no API key is committed. Model changes require evaluation.
