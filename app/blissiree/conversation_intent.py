import re
from dataclasses import dataclass

from .schemas import MentalStateAnalysis


REFUSAL = re.compile(
    r"\b(get lost|go away|leave me alone|stop talking|shut up|fuck off|piss off|do not talk to me|don't talk to me)\b",
    re.I,
)
OFF_TOPIC = re.compile(
    r"\b(weather|stock price|share price|bitcoin|crypto|write (?:me )?code|debug (?:my )?code|"
    r"recipe|football score|sports score|latest news|president of|capital of|solve this equation|"
    r"translate this|book a flight|order food)\b",
    re.I,
)
CASUAL = re.compile(r"^\s*(hi|hello|hey|what'?s up|how are you|who are you|what can you do)[\s?!.]*$", re.I)
SUPPORT_SIGNAL = re.compile(
    r"\b(i (?:am|feel|felt|was|'m)|feeling|stressed|stress|anxious|anxiety|worried|worry|"
    r"sad|low|lonely|angry|overwhelmed|upset|exhausted|tired|sleep|calm|confidence|"
    r"motivation|relationship|grief|thoughts?|emotion(?:al|ally)?|support|help me|cope|"
    r"personal development|blissiree|boost|program)\b",
    re.I,
)


@dataclass(frozen=True)
class ConversationIntent:
    mode: str
    guidance: str | None


def classify_conversation_intent(message: str, analysis: MentalStateAnalysis) -> ConversationIntent:
    """Identify conversational boundaries without treating ambiguity as emotional distress."""
    if REFUSAL.search(message):
        return ConversationIntent(
            "REFUSAL",
            "Respect the user's request for space. Reply briefly, do not challenge the tone, and do not ask a question.",
        )
    if OFF_TOPIC.search(message):
        return ConversationIntent(
            "OUT_OF_SCOPE",
            "Acknowledge the request briefly. Explain naturally that your role is Blissiree emotional support and personal development, then offer one optional way to connect the topic to how the user is feeling. Do not use the standard emotional clarification question.",
        )
    if CASUAL.fullmatch(message):
        return ConversationIntent(
            "CASUAL",
            "Respond naturally to the greeting or capability question, briefly describe your Blissiree companion role, and invite the user to share what kind of emotional or personal-development support would help.",
        )
    # Explicit wellbeing language is authoritative. A model's broad off-topic label
    # must not redirect a genuine request such as "I am stressed about tomorrow."
    if SUPPORT_SIGNAL.search(message):
        return ConversationIntent("SUPPORT", None)
    if analysis.intent.lower() in {"off_topic", "out_of_scope", "unrelated"}:
        return ConversationIntent(
            "OUT_OF_SCOPE",
            "Acknowledge the message without pretending expertise. Briefly remind the user that your role is Blissiree emotional support and personal development, and offer a natural bridge back only if useful.",
        )
    return ConversationIntent("SUPPORT", None)


def contextual_fallback(persona: str, message: str, intent: ConversationIntent, has_context: bool) -> str:
    """Safe user-facing response used when generation is unavailable or rejected."""
    if intent.mode == "REFUSAL":
        return (
            "I hear you. I’ll give you space. If you want emotional support later, I’ll be here."
            if persona == "emma"
            else "Understood. I’ll give you space. I’m here if you want practical emotional support later."
        )
    if intent.mode == "OUT_OF_SCOPE":
        return (
            "I may not be the right assistant for that specific request. My role is to support your emotional wellbeing and personal development. If this is affecting how you feel, you’re welcome to tell me what part is weighing on you."
            if persona == "emma"
            else "That specific request is outside my role. I focus on emotional wellbeing and practical personal-development support. If it is creating stress or affecting you, tell me which part you want to work through."
        )
    if intent.mode == "CASUAL":
        return (
            "Hi, I’m Emma. I’m here for gentle emotional support and personal development. What would feel helpful today?"
            if persona == "emma"
            else "Hi, I’m Ben. I offer calm, practical support for emotional wellbeing and personal development. What would you like to work through?"
        )
    if has_context:
        return (
            "I’m listening. Tell me what part of this feels most important right now, and we can take it one step at a time."
            if persona == "emma"
            else "Let’s keep this relevant to what you need. Which part would you like to handle first?"
        )
    return (
        "I want to understand rather than make assumptions. What is happening for you, and what kind of support would feel useful?"
        if persona == "emma"
        else "I don’t want to assume what you need. What is happening, and what would you like help working through?"
    )
