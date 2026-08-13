class ResponseReviewAgent:
    """Builds the brief for the mandatory final persona-and-correlation rewrite."""

    def brief(self, persona: str, message: str, history: list[dict], mode: str) -> dict:
        recent = [
            {"role": item.get("role", ""), "content": str(item.get("content", ""))}
            for item in history[-8:]
            if item.get("role") in {"user", "assistant"}
        ]
        return {
            "persona": persona,
            "mode": mode,
            "latest_user_message": message,
            "recent_conversation": recent,
            "editorial_requirements": [
                "Rewrite the draft; do not grade, reject, or discuss it.",
                "Make the opening respond to the specific meaning of the latest user message.",
                "Connect naturally with relevant facts already shared and do not restart the conversation.",
                "Preserve the draft's approved facts, exact resource titles, booking links, boundaries, and safety meaning.",
                "Do not add facts, emotions, diagnoses, memories, products, promises, or recommendations.",
                "Emma is warm, gentle, emotionally present and unhurried; Ben is calm, grounded, clear and practical.",
                "Use recognition and validation before exploration or action when emotion is present.",
                "Avoid canned empathy, repeated questions, theatrical language, endearments, and internal system language.",
                "Ask at most one useful question and do not ask one when the user is finished, refusing, thanking, or saying goodbye.",
                "Return only the final user-facing reply.",
            ],
        }
