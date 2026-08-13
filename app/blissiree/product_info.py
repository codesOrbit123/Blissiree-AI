import re

from .conversation_intent import SUPPORT_SIGNAL
from .schemas import ConversationContext


PRODUCT_QUERY = re.compile(
    r"\b(what (?:is|does) blissiree|about blissiree|this business|this platform|blissiree (?:app|offer|program|boost|audio|science|story)|"
    r"what (?:programs?|services?|features?|audios?) (?:does )?blissiree|what (?:do|does) (?:you|the app) offer|"
    r"tell me about (?:the )?(?:app|programs?|boost|blissiree)|emotional empowerment|unstoppable you|"
    r"brain reset|boost library|consultations? with terri)\b",re.I)
FOLLOW_UP = re.compile(r"^\s*(yes(?: please)?(?: share details)?|sure|okay|ok|please|share details|tell me more|more details)\s*[?!.]*\s*$",re.I)


def _recent_user_topic(history):
    return " ".join(str(x.get("content","")) for x in history[-4:] if x.get("role")=="user")


def is_product_information_request(message,history):
    # Emotional need always ends product-information mode, even if the message
    # begins with a conversational acknowledgement such as “ok”.
    if SUPPORT_SIGNAL.search(message) and not PRODUCT_QUERY.search(message):return False
    if PRODUCT_QUERY.search(message):return True
    return bool(FOLLOW_UP.fullmatch(message) and PRODUCT_QUERY.search(_recent_user_topic(history)))


def _topic(message,history):
    explicit=message.lower()
    context=explicit if PRODUCT_QUERY.search(message) else (_recent_user_topic(history)+" "+message).lower()
    if "emotional empowerment" in context:return "EMOTIONAL_EMPOWERMENT"
    if "unstoppable you" in context:return "UNSTOPPABLE_YOU"
    if "boost" in context or "audio" in context or "brain reset" in context:return "BOOST"
    if "consult" in context or "terri" in context:return "CONSULTATION"
    return "OVERVIEW"


def product_information_response(message,history):
    topic=_topic(message,history)
    if topic=="EMOTIONAL_EMPOWERMENT":
        return ("The Emotional Empowerment Program is Blissiree’s structured 14-session personal-development journey for people aged 13 and above. "
                "It is designed to help users explore longer-standing emotional patterns, beliefs, fears, perceptions and responses through guided sessions and app support. "
                "It supports wellbeing and personal development rather than providing medical care. Would you like to know how the sessions are structured, who it is for, or how to get started?")
    if topic=="UNSTOPPABLE_YOU":
        return ("The Unstoppable You Program is Blissiree’s adult personal-development pathway for ages 18 and above. "
                "It focuses on confidence, focus, resilience, direction, motivation and personal growth through structured content in the app. "
                "It is not medical care. Would you like to know how it is structured or who it may suit?")
    if topic=="BOOST":
        return ("The Blissiree app includes a 30-minute Brain Reset and a Boost Library with more than 200 sleep-based audios and curated playlists. "
                "They provide optional wellbeing and personal-development support for areas such as stress, anxious thinking, sleep and emotional balance; they are not medical treatment. "
                "Would you like an overview of the library or help finding an approved audio for a situation?")
    if topic=="CONSULTATION":
        return ("Blissiree offers consultations with Terri: a Free Consultation (25-minute discovery call), an Introductory Session currently shown as $79 (usually $250), "
                "and a Personalised Program described as a 14-session journey. If you want to book, tell me which option interests you and I’ll provide the official calendar and payment link.")
    return ("Blissiree is a wellbeing and personal-development platform. It brings together Emma and Ben AI companions, a Boost Library with more than 200 audios, "
            "a 30-minute Brain Reset, the Emotional Empowerment Program, the Unstoppable You Program, and optional consultations with Terri. "
            "People can use it either to talk through how they are feeling or to explore relevant Blissiree resources. It is not a medical or healthcare service. "
            "What part would you like to explore?")


def contextual_product_fallback(context:ConversationContext,message:str,history:list[dict]) -> str:
    topic=context.active_topic
    if topic=="EMOTIONAL_EMPOWERMENT":return product_information_response("Emotional Empowerment Program",history)
    if topic=="UNSTOPPABLE_YOU":return product_information_response("Unstoppable You Program",history)
    if topic=="BOOST_LIBRARY":return product_information_response("Boost Library",history)
    if topic=="CONSULTATIONS":return product_information_response("consultations with Terri",history)
    if topic=="BLISSIREE_PROGRAMS":
        if "emotional support" in (context.question_to_answer+" "+message).lower():
            return ("For emotional support, Blissiree offers two main pathways. The Boost Library provides optional audio support for immediate situations, "
                    "while the Emotional Empowerment Program is a structured 14-session journey for longer-standing emotional patterns. "
                    "Tell me whether you want something for right now or information about the structured program, and I can explain that option.")
        return ("Blissiree offers the Emotional Empowerment Program for longer-standing emotional patterns and responses, and the Unstoppable You Program "
                "for adult confidence, focus, resilience, direction and personal growth. The app also includes the Boost Library and 30-minute Brain Reset "
                "for optional wellbeing support. Which program would you like explained?")
    return product_information_response("What is Blissiree?",history)
