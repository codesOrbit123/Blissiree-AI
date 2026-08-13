import re

from .schemas import ConversationContext


GENERIC_QUESTIONS=(
    "what feels most important right now","what part of this feels most important","tell me what part",
    "would you like to share more","what feels most present","what is on your mind",
)

PRODUCT_TOPICS={"BLISSIREE_OVERVIEW","BLISSIREE_PROGRAMS","EMOTIONAL_EMPOWERMENT","UNSTOPPABLE_YOU","BOOST_LIBRARY","CONSULTATIONS"}
SHORT_REFERENCE=re.compile(r"^\s*(yes|yes please|please|please share|share it|show me|which one|tell me more|what about that|play it|give me one|which audio|what program|okay do that|the first one)\s*[?!.]*\s*$",re.I)
CONFIDENCE_TYPO=re.compile(r"\b(confidence|confidenc3|confidance|self[- ]?belief|self[- ]?esteem)\b",re.I)
SADNESS_EXPLICIT=re.compile(r"\b(sad|sadness|crying|unhappy|feeling low)\b",re.I)


def fallback_context(message:str,history:list[dict]) -> ConversationContext:
    """Conservative continuity when structured Gemini analysis is temporarily unavailable."""
    text=message.lower();recent=" ".join(str(x.get("content","")) for x in history[-8:] if x.get("role")=="user").lower()
    product_context=any(x in recent for x in ("blissiree","platform","program","boost","consultation"))
    if "emotional empowerment" in text:return ConversationContext(intent="PRODUCT_INFORMATION",active_topic="EMOTIONAL_EMPOWERMENT",question_to_answer="What is the Emotional Empowerment Program?",conversation_stage="INFORMATION",confidence=.8)
    if "unstoppable" in text:return ConversationContext(intent="PRODUCT_INFORMATION",active_topic="UNSTOPPABLE_YOU",question_to_answer="What is the Unstoppable You Program?",conversation_stage="INFORMATION",confidence=.8)
    if re.search(r"\b(programs?|offerings?)\b",text) and (product_context or "blissiree" in text):return ConversationContext(intent="PRODUCT_INFORMATION",active_topic="BLISSIREE_PROGRAMS",question_to_answer="What programs does Blissiree offer?",conversation_stage="INFORMATION",confidence=.75)
    if re.search(r"\b(platform|business|blissiree)\b",text) and re.search(r"\b(know|what|about|interested)\b",text):return ConversationContext(intent="PRODUCT_INFORMATION",active_topic="BLISSIREE_OVERVIEW",question_to_answer="What is Blissiree?",conversation_stage="INFORMATION",confidence=.75)
    if product_context and re.search(r"\bemotional support\b",text):return ConversationContext(intent="PRODUCT_INFORMATION",active_topic="BLISSIREE_PROGRAMS",question_to_answer="Which Blissiree offering is relevant to emotional support?",is_follow_up=True,conversation_stage="INFORMATION",confidence=.7)
    return ConversationContext(intent="COMPANION_SUPPORT",active_topic="USER_SITUATION",question_to_answer=message,conversation_stage=support_progress_stage(message,history),confidence=.4)


def context_query(context:ConversationContext,message:str) -> str:
    return " ".join(x for x in (context.active_topic.replace("_"," "),context.user_goal,context.question_to_answer,message) if x)


def reconcile_context(context:ConversationContext,message:str,history:list[dict]) -> ConversationContext:
    """Resolve a short answer against the immediately pending product question."""
    if not history:return context
    recent=" ".join(str(x.get("content","")) for x in history[-6:]).lower()
    short=len(message.split())<=5
    pending_product=any(x in recent for x in ("which program","which offering","program would you like","blissiree offers","boost library","emotional empowerment"))
    if short and pending_product and re.search(r"\b(emotional support|confidence|resilience|sleep|stress|focus|personal growth)\b",message,re.I):
        return context.model_copy(update={"intent":"PRODUCT_INFORMATION","active_topic":"BLISSIREE_PROGRAMS","is_follow_up":True,
            "question_to_answer":f"Which Blissiree offering is relevant to {message.strip()}?","conversation_stage":"INFORMATION","confidence":max(context.confidence,.85)})
    return context


def apply_latest_message_authority(context:ConversationContext,message:str,history:list[dict]) -> ConversationContext:
    """Explicit current words override weaker emotional inference from prior turns."""
    updates={"raw_user_message":message};themes=[]
    if CONFIDENCE_TYPO.search(message):themes.append("LOW_CONFIDENCE")
    if SADNESS_EXPLICIT.search(message):themes.append("SADNESS")
    if themes:
        updates["current_explicit_themes"]=themes
        updates["current_inferred_themes"]=[]
        updates["reported_emotions"]=["sadness"] if "SADNESS" in themes else []
        if "LOW_CONFIDENCE" in themes:
            updates.update({"intent":"COMPANION_SUPPORT","active_topic":"USER_SITUATION","user_goal":"support with low confidence",
                            "question_to_answer":"Support the user's explicitly stated low confidence as the current issue."})
    elif context.intent=="PRODUCT_INFORMATION":
        recent_users=" ".join(str(x.get("content","")) for x in history[-6:] if x.get("role")=="user")
        if CONFIDENCE_TYPO.search(recent_users):
            updates["current_explicit_themes"]=["LOW_CONFIDENCE"]
    correction=re.search(r"\b(no|not|i said|meant)\b.*\b(confidence|confidenc3|confidance)\b",message,re.I)
    if correction:updates.update({"intent":"FEEDBACK","user_goal":"correct the misunderstanding about low confidence",
                                  "question_to_answer":"Acknowledge that the user meant confidence, not sadness, then continue naturally.",
                                  "current_explicit_themes":["LOW_CONFIDENCE"],"reported_emotions":[]})
    direct_content=bool(re.search(r"\b(anything|something|what)\b.{0,35}\bblissi\w*\b.{0,35}\b(offer|audio|boost|program|content)\b|\bblissi\w*\b.{0,35}\b(offer|audio|boost|program|content)\b",message,re.I))
    direct_content=direct_content or bool(re.search(r"\b(which|what|recommend|suggest)\b.{0,35}\b(audio|boost|collection|program)\b|\b(audio|boost|collection|program)\b.{0,25}\b(should i|for me|listen to|recommend)\b",message,re.I))
    if direct_content:
        topic="work stress content" if re.search(r"\b(work|workload|too m(?:u|ch)+ch work|deadline|stress|stressed)\b",message,re.I) else None
        updates.update({"intent":"RESOURCE_GUIDANCE","active_topic":"USER_SITUATION","conversation_stage":"RECOMMENDATION",
                        "needs_clarification":topic is None,"resolved_reference":topic,"pending_offer_type":"BOOST_RECOMMENDATION",
                        "user_goal":topic or "find relevant Blissiree content","question_to_answer":"Match approved Blissiree content to the user's current request."})
    if not context.interpreted_message:updates["interpreted_message"]=context.question_to_answer or message
    return context.model_copy(update=updates)


def resolve_conversation_reference(context:ConversationContext,message:str,history:list[dict]) -> ConversationContext:
    """Resolve terse requests against the assistant's recent Blissiree offer before scope classification."""
    if not SHORT_REFERENCE.fullmatch(message):return context
    assistants=[str(x.get("content","")) for x in history[-6:] if x.get("role")=="assistant"]
    recent=" ".join(assistants).lower()
    if not recent:
        return context.model_copy(update={"intent":"RESOURCE_GUIDANCE","needs_clarification":True,"question_to_answer":"Ask what the user wants shared.","confidence":.5})
    topic=None
    for label,pattern in (("work stress",r"work.{0,30}stress|stress.{0,30}work"),("sleep",r"sleep"),("confidence",r"confidence|self-belief|self-esteem"),("stress",r"stress|tension")):
        if re.search(pattern,recent,re.I):topic=label;break
    offered=bool(re.search(r"\b(audio|boost|collection|program|blissiree|content|offer|recommend|show you)\b",recent,re.I))
    if offered:
        reference=(topic+" content") if topic else "the Blissiree content just offered"
        return context.model_copy(update={"intent":"RESOURCE_GUIDANCE","active_topic":"USER_SITUATION","is_follow_up":True,
            "needs_clarification":topic is None,"resolved_reference":reference,"pending_offer_type":"BOOST_RECOMMENDATION",
            "question_to_answer":f"Fulfil the user's request for {reference}.","user_goal":reference,"conversation_stage":"RECOMMENDATION","confidence":.9 if topic else .65})
    return context.model_copy(update={"intent":"RESOURCE_GUIDANCE","needs_clarification":True,"question_to_answer":"Ask one short clarification about what they want shared.","confidence":.5})


def information_quality_failures(text:str,context:ConversationContext) -> list[str]:
    if context.intent!="PRODUCT_INFORMATION":return []
    failures=[];lower=text.lower()
    if re.match(r"\s*(it sounds like|you seem|i hear (?:that )?you)",lower):failures.append("indirect_information_opening")
    if not text.strip():failures.append("empty_answer")
    if context.active_topic=="BLISSIREE_OVERVIEW":
        concrete=sum(term in lower for term in ("emma","ben","boost library","emotional empowerment","unstoppable you","terri","brain reset"))
        if "blissiree" not in lower or concrete<2:failures.append("missing_platform_answer")
    if context.active_topic=="BLISSIREE_PROGRAMS" and not any(x in lower for x in ("emotional empowerment","unstoppable you","boost library")):failures.append("missing_program_answer")
    if "LOW_CONFIDENCE" in context.current_explicit_themes and context.active_topic=="BLISSIREE_OVERVIEW" and "confidence" not in lower:
        failures.append("missing_relevant_confidence_context")
    return failures


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
    if stage=="SUPPORT_ACTION" and re.search(r"\b(audio|boost|collection|program)\b",text,re.I):failures.append("unsolicited_resource_in_support_action")
    recent_assistant=[str(x.get("content","")) for x in history[-8:] if x.get("role")=="assistant"]
    normalized=lambda s:re.sub(r"\s+"," ",s.strip().lower())
    if any(normalized(text)==normalized(prior) for prior in recent_assistant):failures.append("repeated_full_response")
    questions=[q.strip().lower() for q in re.findall(r"[^?]+\?",text)]
    for question in questions:
        words={w for w in re.findall(r"[a-z']+",question) if len(w)>3}
        for prior in recent_assistant:
            prior_words={w for w in re.findall(r"[a-z']+",prior.lower()) if len(w)>3}
            if len(words)>=3 and len(words&prior_words)/len(words)>=.65:failures.append("repeated_question");return failures
    return failures


def recommendation_fulfilment_failures(text:str,eligible_titles:list[str],stage:str) -> list[str]:
    if stage!="RECOMMENDATION" or not eligible_titles:return []
    return [] if any(title.lower() in text.lower() for title in eligible_titles) else ["missing_eligible_recommendation_title"]


def progress_fallback(persona:str,message:str,history:list[dict]) -> str:
    all_user=" ".join(str(x.get("content","")) for x in history[-10:] if x.get("role")=="user")+" "+message
    if re.search(r"\b(cat|kitten|pet)\b",all_user,re.I) and re.search(r"\b(dead|died|sad|sadness|stuck|thought)\b",all_user,re.I):
        accident=bool(re.search(r"\b(accident|cliff|crash|car)\b",all_user,re.I))
        if re.search(r"\b(peace|calm|settle|quiet)\b",message,re.I):
            return ("Let’s make room for a little calm without asking you to erase what happened. Feel the support beneath your feet, let your shoulders soften, and take one unforced breath. For the next moment, you can hold a gentler memory of your cat rather than the accident itself."
                    if persona=="emma" else
                    "Let’s focus on calm first. Put both feet on the floor, breathe out slowly, and name three things you can see. For the next five minutes, choose one memory of your cat from before the accident and let the accident image stay in the background.")
        return (("That was a sudden and frightening loss, and the accident still seems close in your mind. We don’t have to force the memory away. Let’s slow this moment down gently and notice what you need most right now: space to remember your cat, or a brief pause from the accident memory."
                 if accident else "The sadness of losing your cat is still close, and your thoughts seem caught around her. We don’t have to force that away. Let’s slow this moment down gently and notice one memory of her that feels comforting rather than painful.")
                if persona=="emma" else
                "Your thoughts are looping around losing your cat and the accident. First, reduce the pressure: place both feet on the floor and name three things you can see. Then choose whether to remember one good moment with her or briefly shift your attention.")
    return ("I’ve heard the details you’ve shared, so I won’t keep asking you to explain the same thing. Let’s pause for one slow breath and focus on the smallest part of this moment you can gently hold."
            if persona=="emma" else
            "We have enough context to stop analysing and take one practical step. Put both feet on the floor, breathe out slowly, and choose one thing you can handle in the next five minutes.")
