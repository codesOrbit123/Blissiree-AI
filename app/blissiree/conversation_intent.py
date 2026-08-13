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
FEEDBACK = re.compile(
    r"\b(you(?:'re| are) (?:too )?(?:rude|cold|robotic|repetitive|not listening)|"
    r"that was rude|you don'?t understand|you are not helping|that wasn'?t helpful|"
    r"stop repeating|your tone|don'?t call me that)\b",
    re.I,
)
SUPPORT_SIGNAL = re.compile(
    r"\b(i (?:am|feel|felt|was|'m)|feeling|stressed|stress|anxious|anxiety|worried|worry|"
    r"sad|low|lonely|angry|overwhelmed|upset|exhausted|tired|sleep|calm|confidence|"
    r"motivation|relationship|grief|thoughts?|emotion(?:al|ally)?|support|help me|cope|"
    r"personal development|blissiree|boost|program|crying|cried|lost|loss|money|dollars?|financial)\b",
    re.I,
)
EXPLICIT_RECOMMENDATION = re.compile(
    r"\b(what (?:should|can) i (?:listen to|use|try)|recommend(?:ation| something)?|"
    r"which (?:audio|boost|collection|program)|suggest (?:an? )?(?:audio|boost|collection|program)|"
    r"give me (?:an? )?(?:audio|boost|collection|program)|i want (?:an? )?(?:audio|boost|collection|program))\b",
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
    if FEEDBACK.search(message):
        return ConversationIntent(
            "FEEDBACK",
            "Treat this as feedback about your response. Acknowledge it briefly and sincerely without over-apologising, "
            "defending yourself, repeating emotional validation, or recommending content. Ask at most one short question "
            "about how the user would prefer you to respond.",
        )
    if CASUAL.fullmatch(message):
        return ConversationIntent(
            "CASUAL",
            "Respond naturally to the greeting or capability question, briefly describe your Blissiree companion role, and invite the user to share what kind of emotional or personal-development support would help.",
        )
    # Emotional meaning takes precedence when an otherwise off-topic subject is
    # affecting the user, such as distress after a financial loss.
    if SUPPORT_SIGNAL.search(message):
        return ConversationIntent("SUPPORT", None)
    if OFF_TOPIC.search(message):
        return ConversationIntent(
            "OUT_OF_SCOPE",
            "Acknowledge the request briefly. Explain naturally that your role is Blissiree emotional support and personal development, then offer one optional way to connect the topic to how the user is feeling. Do not use the standard emotional clarification question.",
        )
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
    if intent.mode == "FEEDBACK":
        return (
            "I’m sorry—that didn’t feel supportive. I’ll keep my tone straightforward and gentle. How would you prefer me to respond?"
            if persona == "emma"
            else "I’m sorry—that response missed the mark. I’ll be more direct and measured. What would work better for you?"
        )
    if re.search(r"\b(lost|loss)\b.{0,80}\b(\$|money|dollars?|btc|bitcoin|crypto|savings?|financial)",message,re.I) or re.search(
        r"\b(\$|money|dollars?|btc|bitcoin|crypto|savings?|financial)\b.{0,80}\b(lost|loss)\b",message,re.I
        ):
        return (
            "Losing that much sounds deeply upsetting and destabilising. What feels most urgent right now—the shock of it, worry about what happens next, or simply getting through this moment?"
            if persona == "emma"
            else "That is a serious financial loss, and the immediate emotional impact can be intense. What needs attention first—the shock, your next practical step, or getting steadier right now?"
        )
    if re.search(r"\b(confidence|confidenc3|confidance|self[- ]?belief|self[- ]?esteem)\b",message,re.I):
        return ("You’re saying your confidence feels low. I won’t turn that into a different emotion. Is this showing up in one situation, or more generally at the moment?"
                if persona=="emma" else
                "Your confidence feels low. Let’s keep the focus there: is one situation affecting it, or has it been broader lately?")
    if has_context:
        if re.search(r"\b(sad|sadness|low|crying)\b",message,re.I):
            return ("You’re feeling sad today, and we can stay with that gently. What happened today, or what has been coming back to mind?"
                    if persona=="emma" else
                    "You’re feeling sad today. Let’s understand what is driving it so we can choose a manageable next step. What has been weighing on you?")
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


def conversation_stage(message: str, history: list[dict]) -> str:
    """Require companion exploration before content routing unless the user asks directly."""
    if EXPLICIT_RECOMMENDATION.search(message):
        return "RECOMMENDATION"
    prior_user_turns = sum(1 for item in history[-8:] if item.get("role") == "user")
    if prior_user_turns == 0:
        return "DISCOVERY"
    return "EXPLORATION"


def stage_guidance(stage: str) -> str:
    if stage == "DISCOVERY":
        return (
            "This is the user's opening disclosure. Validate the specific experience, reflect its meaning without diagnosis, "
            "and ask one relevant question that helps understand onset, duration, context, impact, or safety. Do not name, "
            "offer, or recommend any Blissiree audio, Boost, collection, or Program yet."
        )
    if stage == "EXPLORATION":
        return (
            "Continue the companion conversation. Reflect the new detail and ask one next useful, non-repetitive question "
            "based on what remains unclear. Do not name, offer, or recommend a Blissiree audio, Boost, collection, or Program yet."
        )
    if stage == "SUPPORT_ACTION":
        return (
            "Enough relevant details have already been shared. Do not ask another discovery question or ask the user to repeat themselves. "
            "Reflect the specific topic, facts and emotion already known, then offer one small persona-appropriate supportive action. "
            "Do not recommend Blissiree content unless the user explicitly requests it."
        )
    return (
        "Enough conversational context is available, or the user directly requested a recommendation. If an eligible exact "
        "resource is supplied, connect at most one primary recommendation to the user's observable pattern. Otherwise continue "
        "the conversation without inventing or forcing a recommendation."
    )
