import re


GENERIC_QUESTIONS=(
    "what feels most important right now","what part of this feels most important","tell me what part",
    "would you like to share more","what feels most present","what is on your mind",
)


def conversation_brief(message:str,history:list[dict]) -> str:
    users=[str(x.get("content","")) for x in history[-10:] if x.get("role")=="user"]+[message]
    text=" ".join(users)
    facts=[]
    if re.search(r"\b(cat|kitten|pet)\b",text,re.I):facts.append("The user is talking about their cat or pet.")
    if re.search(r"\b(dead|died|passed away|lost (?:my|their)|grief|miss)\b",text,re.I):facts.append("The conversation concerns loss or grief.")
    colour=re.search(r"\b(?:colou?r (?:was|is)|was)\s+(white|black|brown|ginger|grey|gray)\b",text,re.I)
    if colour:facts.append(f"A remembered detail is the colour {colour.group(1).lower()}.")
    if re.search(r"\b(sad|sadness|crying|low)\b",text,re.I):facts.append("The user has named sadness.")
    if re.search(r"\b(brain|mind|thoughts?)\b.{0,35}\b(stuck|loop|circl|cannot stop|can't stop)\b|\bstuck\b.{0,35}\b(thoughts?|her|him|it)\b",text,re.I):facts.append("The user says their thoughts feel stuck or repetitive.")
    return " ".join(facts) or "Use the concrete facts and emotions already stated in recent history."


def support_progress_stage(message:str,history:list[dict]) -> str:
    recent=history[-10:]
    last_product=-1
    for i,item in enumerate(recent):
        if item.get("role")=="user" and re.search(r"\b(blissiree|emotional empowerment|unstoppable you|boost library|brain reset|consultation)\b",str(item.get("content","")),re.I):last_product=i
    user_turns=[x for x in recent[last_product+1:] if x.get("role")=="user"]
    if len(user_turns)>=3 and not re.search(r"\b(what|why|when|where|who|how)\b",message,re.I):return "SUPPORT_ACTION"
    return "EXPLORATION" if user_turns else "DISCOVERY"


def response_progress_failures(text:str,history:list[dict],stage:str) -> list[str]:
    failures=[];lower=text.lower()
    if stage=="SUPPORT_ACTION" and any(q in lower for q in GENERIC_QUESTIONS):failures.append("generic_question_after_context")
    recent_assistant=[str(x.get("content","")) for x in history[-8:] if x.get("role")=="assistant"]
    questions=[q.strip().lower() for q in re.findall(r"[^?]+\?",text)]
    for question in questions:
        words={w for w in re.findall(r"[a-z']+",question) if len(w)>3}
        for prior in recent_assistant:
            prior_words={w for w in re.findall(r"[a-z']+",prior.lower()) if len(w)>3}
            if len(words)>=3 and len(words&prior_words)/len(words)>=.65:failures.append("repeated_question");return failures
    return failures


def progress_fallback(persona:str,message:str,history:list[dict]) -> str:
    all_user=" ".join(str(x.get("content","")) for x in history[-10:] if x.get("role")=="user")+" "+message
    if re.search(r"\b(cat|kitten|pet)\b",all_user,re.I) and re.search(r"\b(dead|died|sad|sadness|stuck|thought)\b",all_user,re.I):
        return ("Your thoughts seem caught around losing your cat, and the memory of her white fur is close right now. We don’t have to force the sadness away. Let’s slow this moment down together: take one easy breath, then notice one comforting memory of her—no need to explain it perfectly."
                if persona=="emma" else
                "Your thoughts are looping around losing your cat. Let’s reduce the pressure for a moment: put both feet on the floor, take one slow breath, and name three things you can see. Then decide whether remembering one good moment with her or briefly shifting your attention would feel more manageable.")
    return ("I’ve heard the details you’ve shared, so I won’t keep asking you to explain the same thing. Let’s pause for one slow breath and focus on the smallest part of this moment you can gently hold."
            if persona=="emma" else
            "We have enough context to stop analysing and take one practical step. Put both feet on the floor, breathe out slowly, and choose one thing you can handle in the next five minutes.")
