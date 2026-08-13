import re

PRODUCT_QUERY = re.compile(
    r"\b(what (?:is|does) blissiree|about blissiree|blissiree (?:app|offer|program|boost|audio|science|story)|"
    r"what (?:programs?|services?|features?|audios?) (?:does )?blissiree|what (?:do|does) (?:you|the app) offer|"
    r"tell me about (?:the )?(?:app|programs?|boost|blissiree)|emotional empowerment|unstoppable you|"
    r"brain reset|boost library|consultations? with terri)\b",re.I)
FOLLOW_UP = re.compile(r"^\s*(yes(?: please)?|sure|okay|ok|please|share details|tell me more|more details)(?:[\s,!.]+.*)?$",re.I)

def is_product_information_request(message,history):
    if PRODUCT_QUERY.search(message):return True
    if not FOLLOW_UP.fullmatch(message):return False
    recent=" ".join(str(x.get("content","")) for x in history[-4:])
    return bool(PRODUCT_QUERY.search(recent) or re.search(r"\b(Blissiree|Emotional Empowerment|Unstoppable You|Boost Library)\b",recent,re.I))

def product_information_response(message,history):
    context=(" ".join(str(x.get("content","")) for x in history[-4:])+" "+message).lower()
    if "consult" in context:
        return "Blissiree also offers consultations with Terri. The official site describes a free 25-minute discovery call, an introductory session, and a personalised 14-session journey. Current availability and booking details are on blissiree.com/consultations."
    if "boost" in context or "audio" in context or "brain reset" in context:
        return "The Blissiree app includes a 30-minute Brain Reset and a Boost Library with more than 200 sleep-based audios and curated playlists for areas such as stress, anxious thinking, sleep and emotional balance. These are wellbeing and personal-development resources, not medical treatment."
    return ("Blissiree currently offers three main in-app pathways:\n\n"
            "• Boost Library — more than 200 sleep-based audios and curated playlists for immediate wellbeing support.\n"
            "• Emotional Empowerment Program — a structured 14-session journey for ages 13+, focused on longer-standing emotional patterns and responses.\n"
            "• Unstoppable You Program — for adults 18+, focused on confidence, focus, resilience, direction and personal growth.\n\n"
            "The app also begins with a 30-minute Brain Reset, and consultations with Terri are available separately. Blissiree supports wellbeing and personal development; it is not medical care. Which offering would you like details about?")
