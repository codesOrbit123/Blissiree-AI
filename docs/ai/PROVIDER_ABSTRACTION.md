# Provider Abstraction

Business orchestration depends on `AnalysisLLMProvider`, `ConversationLLMProvider`, and `EmbeddingProvider`, not the Gemini SDK. `GeminiProvider` is the initial Vertex AI implementation. This permits evaluated provider changes without rewriting safety or recommendation rules.
