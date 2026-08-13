import re
from dataclasses import dataclass


BOOKING_URL = "https://brain-wellness-spa.au1.cliniko.com/bookings"

_BOOK_ACTION = re.compile(
    r"\b(book|booking|schedule|appointment|reserve|available times?|calendar|pay(?:ment)?|sign me up)\b",
    re.I,
)
_TERRI_SERVICE = re.compile(r"\b(terri|consultation|discovery call|introductory session|one[- ]to[- ]one|1[- ]?1|session)\b", re.I)
_BOOKING_FOLLOW_UP = re.compile(r"^\s*(yes|yes please|sure|okay|ok|please|book it|let'?s do it|show me)\s*[.!]*\s*$", re.I)


@dataclass(frozen=True)
class RoutedIntent:
    kind: str
    service: str | None = None


def _service_from(text: str) -> str | None:
    if re.search(r"\b(free|discovery|25[- ]?minute)\b", text, re.I):
        return "FREE_CONSULTATION"
    if re.search(r"\b(introductory|intro|first session|\$?79)\b", text, re.I):
        return "INTRODUCTORY_SESSION"
    if re.search(r"\b(personali[sz]ed|14[- ]?session|full (?:journey|program))\b", text, re.I):
        return "PERSONALISED_PROGRAM"
    return None


def route_top_level_intent(message: str, history: list[dict]) -> RoutedIntent:
    """Route only high-confidence deterministic intents; companion support remains the default."""
    if _BOOK_ACTION.search(message) and _TERRI_SERVICE.search(message):
        return RoutedIntent("CONSULTATION_BOOKING", _service_from(message))
    if _BOOKING_FOLLOW_UP.fullmatch(message):
        recent = " ".join(str(item.get("content", "")) for item in history[-4:])
        if _BOOK_ACTION.search(recent) and _TERRI_SERVICE.search(recent):
            return RoutedIntent("CONSULTATION_BOOKING", _service_from(recent))
    return RoutedIntent("COMPANION_OR_INFORMATION")


def consultation_booking_response(service: str | None) -> str:
    if service == "FREE_CONSULTATION":
        lead = "The best match is the Free Consultation, a 25-minute discovery call with Terri."
    elif service == "INTRODUCTORY_SESSION":
        lead = "The best match is the Introductory Session, currently shown by Blissiree as $79 (usually $250)."
    elif service == "PERSONALISED_PROGRAM":
        lead = "You’re asking about Terri’s Personalised Program, described as a 14-session journey."
    else:
        lead = ("Terri currently offers a Free Consultation (25-minute discovery call), an Introductory Session, "
                "and a Personalised Program (14 sessions). You can choose the appropriate service in the booking portal.")
    return (f"{lead}\n\nView live availability, choose a time, and complete any required payment here:\n{BOOKING_URL}\n\n"
            "Blissiree provides wellbeing and personal-development support, not medical care.")
