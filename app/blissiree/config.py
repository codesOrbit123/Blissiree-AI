import os
from dataclasses import dataclass

def flag(name: str, default: bool = True) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}

@dataclass(frozen=True)
class AIConfig:
    project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    region: str = os.getenv("GOOGLE_CLOUD_REGION", os.getenv("GOOGLE_CLOUD_LOCATION", "global"))
    analysis_model: str = os.getenv("GEMINI_ANALYSIS_MODEL", "gemini-2.5-flash-lite")
    conversation_model: str = os.getenv("GEMINI_CONVERSATION_MODEL", "gemini-2.5-flash")
    embedding_model: str = os.getenv("GEMINI_EMBEDDING_MODEL", "text-embedding-005")
    analysis_enabled: bool = flag("AI_ANALYSIS_ENABLED")
    rag_enabled: bool = flag("AI_RAG_ENABLED")
    output_validation_enabled: bool = flag("AI_OUTPUT_VALIDATION_ENABLED")

settings = AIConfig()
