import re
from dataclasses import dataclass
from .schemas import MentalStateAnalysis

PATTERNS = {
    "T0": re.compile(r"\b(right now|immediate danger|actively|already (did|taken)|can't stay safe)\b", re.I),
    "T1": re.compile(r"\b(kill myself|suicide|end my life|hurt myself|self[- ]harm)\b", re.I),
    "T2": re.compile(r"\b(kill|hurt|attack|harm) (him|her|them|someone|people)\b", re.I),
    "T3": re.compile(r"\b(domestic violence|abuse[ds]? me|partner (hits|threatens)|not safe at home|coercive control|controls? my (money|movement)|afraid of my partner)\b", re.I),
    "T4": re.compile(r"\b(chest pain|can't breathe|severe breathlessness|overdose|seizure|medical emergency|one[- ]sided weakness|facial droop(?:ing)?|slurred speech|sudden severe headache|vision loss|faint(?:ed|ing)|falling asleep (while )?driving|fell asleep (while )?driving)\b", re.I),
    "T5": re.compile(r"\b(can't cope|cannot cope|falling apart|severe distress|hopeless)\b", re.I),
    "T6": re.compile(r"\b(overwhelmed|anxious|very stressed|grief|lonely|ruminating|poor sleep|painful memor|not feeling well|deeply upset)\w*\b", re.I),
}

FAREWELL_PATTERN = re.compile(r"\b(good\s*bye|bye(?:\s+for\s+now)?|see\s+you|talk\s+(?:to\s+you\s+)?later|that(?:'s| is)\s+all|no\s+thanks?|nothing\s+else|issue\s+(?:is\s+)?solved|problem\s+(?:is\s+)?solved)\b", re.I)
THANKS_PATTERN = re.compile(r"^\s*(?:thanks?(?:\s+(?:a\s+lot|alot|very\s+much))?|thank\s+you)(?:[\s,!.'’]*(?:emma|ben|you\s+are\s+(?:the\s+)?best)\b[\s,!.'’]*)*$", re.I)

@dataclass(frozen=True)
class TriageResult:
    level: str
    matched_rules: list[str]
    blocks_recommendations: bool

class TriageEngine:
    def evaluate(self, message: str, analysis: MentalStateAnalysis) -> TriageResult:
        matches = [level for level, pattern in PATTERNS.items() if pattern.search(message)]
        signal_text = " ".join(analysis.safety_signals + analysis.distress_signals)
        matches += [level for level, pattern in PATTERNS.items() if pattern.search(signal_text)]
        priority = next((level for level in ("T0","T1","T2","T3","T4","T5","T6") if level in matches), "T7")
        if analysis.stress_score_estimate is not None and priority == "T7":
            priority = "T5" if analysis.stress_score_estimate >= 9 else "T6" if analysis.stress_score_estimate >= 6 else "T7"
        return TriageResult(priority, sorted(set(matches)), priority in {"T0","T1","T2","T3","T4","T5"})

def terminal_turn_kind(message: str, triage: TriageEngine, analysis: MentalStateAnalysis | None = None) -> str | None:
    """Return a terminal conversational intent without masking same-turn safety signals."""
    current_triage=triage.evaluate(message,analysis or MentalStateAnalysis())
    if current_triage.level in {"T0","T1","T2","T3","T4","T5"}:
        return None
    if FAREWELL_PATTERN.search(message):
        return "farewell"
    if len(message) <= 100 and THANKS_PATTERN.fullmatch(message):
        return "thanks"
    return None

def terminal_turn_response(persona: str, kind: str) -> str:
    if kind == "thanks":
        return "You’re very welcome. I’m glad I could support you." if persona == "emma" else "You’re welcome. I’m glad that helped."
    return ("I’m glad I could be here with you. Take gentle care of yourself, and you’re welcome back anytime. Goodbye for now."
            if persona == "emma" else
            "I’m glad we could work through it. Take care, and come back anytime you want support. Goodbye for now.")

class OutputSafetyValidator:
    prohibited = [
        re.compile(r"\b(I diagnose|you (have|suffer from) (depression|anxiety disorder|PTSD|bipolar))\b", re.I),
        re.compile(r"\b(take|stop taking|increase|decrease) (this |your )?(medication|medicine|dose)\b", re.I),
        re.compile(r"\b(guaranteed|will cure|clinically proven to treat)\b", re.I),
        re.compile(r"\b(you only need me|don't tell anyone|I am all you need)\b", re.I),
    ]
    def validate(self, text: str, allowed_titles: set[str]) -> tuple[bool, list[str]]:
        failures = [p.pattern for p in self.prohibited if p.search(text)]
        leakage_markers=("response_contract","compiled_instructions","allowed_actions","retrieved_knowledge","response_limits","program_assessment_required","interaction_mode","response_guidance","'persona':","\"persona\":")
        if any(marker in text for marker in leakage_markers) or re.match(r"^\s*[\[{]",text):failures.append("internal_configuration_leak")
        if re.search(r"\bCollection\b", text) and not any(title in text for title in allowed_titles):
            failures.append("unsupported_collection")
        invented_program = re.search(r"\bprogram called\s+[\"']?([^\"'.\n]+)", text, re.I)
        if invented_program and not any(title.lower() in invented_program.group(1).lower() for title in allowed_titles):
            failures.append("unsupported_program")
        return not failures, failures

def deterministic_crisis_response(level: str, message: str = "") -> str:
    if level == "T4" and re.search(r"\b(falling asleep|fell asleep).{0,30}\b(driving|machinery)\b",message,re.I):
        return "Please stop driving or operating machinery now and arrange safe alternative transport or ask someone nearby to help. Blissiree content is not appropriate until your immediate safety is addressed. If you cannot stay safely awake or your symptoms are sudden or severe, contact your local emergency services."
    if level in {"T0","T1","T2","T3","T4"}:
        return "Your immediate safety matters most. Please contact your local emergency services now and reach out to a trusted person nearby who can stay with you. Blissiree cannot provide emergency or medical support. Are you in immediate danger right now?"
    return "It sounds like you are carrying a lot right now. Let’s keep this gentle and focus on one small, safe next step. What feels most urgent in this moment?"
