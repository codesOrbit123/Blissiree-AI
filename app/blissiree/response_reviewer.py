import re
from dataclasses import dataclass


TOPICS={
    "workload":re.compile(r"\b(work|workload|overload|deadline|manager|boss|job)\b",re.I),
    "stress":re.compile(r"\b(stress|stressed|pressure|tension|overwhelmed)\b",re.I),
    "confidence":re.compile(r"\b(confidence|confidenc3|confidance|self[- ]?esteem|self[- ]?belief)\b",re.I),
    "sadness":re.compile(r"\b(sad|sadness|crying|low mood)\b",re.I),
    "grief":re.compile(r"\b(died|dead|loss|lost|grief|miss|cat|pet)\b",re.I),
    "audio":re.compile(r"\b(audio|boost|collection|listen)\b",re.I),
    "booking":re.compile(r"\b(book|booking|appointment|consultation|terri|session)\b",re.I),
}
GENERIC=re.compile(r"\b(i(?:’|'| a)m listening\. tell me what part|i(?:’|'| a)ve heard the details you(?:’|'| ha)ve shared|what feels most important right now|smallest part of this moment)\b",re.I)
DISCUSSION_SWITCH=re.compile(r"\b(done with (?:the )?audios?|stop (?:the )?audios?|want to (?:talk|discuss)|discuss my problem|keep talking)\b",re.I)


@dataclass(frozen=True)
class ReviewResult:
    passed: bool
    failures: list[str]


class ResponseReviewAgent:
    """Final, non-speaking quality gate grounded in Terri's recognition-first response model."""
    def review(self,text:str,message:str,history:list[dict],mode:str) -> ReviewResult:
        failures=[]
        if GENERIC.search(text):failures.append("generic_uncorrelated_reply")
        current_topics={name for name,pattern in TOPICS.items() if pattern.search(message)}
        response_topics={name for name,pattern in TOPICS.items() if pattern.search(text)}
        if current_topics and not (current_topics & response_topics):failures.append("missing_latest_message_correlation")
        if DISCUSSION_SWITCH.search(message) and re.search(r"\b(audio|boost|collection|program)\b",text,re.I):failures.append("ignored_discussion_preference")
        return ReviewResult(not failures,failures)

    def fallback(self,persona:str,message:str,history:list[dict]) -> str:
        if DISCUSSION_SWITCH.search(message):
            return ("Of course—we can leave the audios there and focus on what has been happening for you. Share the part of the problem you want to begin with."
                    if persona=="emma" else
                    "We can leave the audios there and focus on the problem itself. Start with what happened, and we’ll work through it clearly.")
        if re.search(r"\b(work|workload|overload|deadline|manager|boss|job)\b",message,re.I):
            return ("Having that much work land on you can leave you feeling stretched and unable to switch off. What part of the workload has been weighing on you most?"
                    if persona=="emma" else
                    "The work overload is the pressure point here. Let’s separate what is urgent from what can wait—what is creating the most pressure today?")
        if re.search(r"\b(sad|sadness|crying|low mood)\b",message,re.I):
            return ("I’m sorry you’re feeling sad. We can stay with what is behind that feeling without rushing to fix it. What has brought the sadness up today?"
                    if persona=="emma" else
                    "You’re feeling sad today. We can slow this down and understand what is driving it before deciding on a next step. What has brought it up?")
        if re.search(r"\b(confidence|confidenc3|confidance)\b",message,re.I):
            return ("Your confidence feels low, and I’m here with you in that. Is there one situation that has been knocking it lately?"
                    if persona=="emma" else
                    "Your confidence is the issue to focus on. What situation has been affecting it most lately?")
        return ("I want to stay with what you have just said rather than give you a generic reply. Tell me a little more about that, and we’ll take it gently."
                if persona=="emma" else
                "I want to respond to what you have actually said. Give me one more detail about it, and we’ll work from there.")
