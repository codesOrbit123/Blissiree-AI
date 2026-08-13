import re


INTENSIFIERS=re.compile(r"\b(truly|incredibly|completely|deeply|devastating|terrifying|traumatic)\b",re.I)
GENERIC_OPENING=re.compile(r"^\s*(it sounds like|i(?:’|'| a)m listening\. tell me what part|you seem)\b",re.I)
COLOURS={"white","black","brown","ginger","grey","gray","orange","golden"}


def persona_requirements(persona:str) -> list[str]:
    if persona=="emma":return [
        "Be warm, gentle, calm, reassuring, emotionally intelligent and trauma-aware.",
        "Use recognition, validation, exploration, insight and supportive action in that order across the conversation.",
        "Create safety before solutions; use compassionate adult-to-adult language without sentimentality.",
    ]
    return [
        "Be calm, grounded, clear, practical, encouraging and emotionally respectful.",
        "Create sufficient safety before structure, then offer one manageable next step.",
        "Never minimise emotion, pressure performance or sound interchangeable with Emma.",
    ]


def persona_quality_failures(text:str,persona:str,history:list[dict],message:str,mode:str) -> list[str]:
    failures=[];lower=text.lower()
    if GENERIC_OPENING.search(text):failures.append("generic_or_mechanical_opening")
    if len(INTENSIFIERS.findall(text))>=2:failures.append("stacked_emotional_intensifiers")
    user_text=" ".join(str(x.get("content","")) for x in history if x.get("role")=="user")+" "+message
    stated={c for c in COLOURS if re.search(rf"\b{c}\b",user_text,re.I)}
    used={c for c in COLOURS if re.search(rf"\b{c}\b",text,re.I)}
    if used-stated:failures.append("invented_thread_detail")
    if persona=="emma" and mode=="SUPPORT" and not re.search(r"\b(you|your|that|this)\b",lower):failures.append("emma_lacks_relational_recognition")
    if persona=="ben" and mode=="SUPPORT" and not re.search(r"\b(next|step|first|start|focus|choose|let(?:’|')s)\b",lower):failures.append("ben_lacks_grounded_structure")
    return failures
