import re
from dataclasses import dataclass
from .schemas import MentalStateAnalysis, Recommendation
from .safety import TriageResult
from .knowledge import KnowledgeRepository

IMMEDIATE = re.compile(r"\b(now|right now|today|tonight|tomorrow|yesterday|this (morning|afternoon|evening)|just need|at the moment|before (an|the|my))\b",re.I)
LONG_TERM = re.compile(r"\b(for (years|months|weeks)|six months|long[- ]term|recurring|repeated|every relationship|same pattern|structured program|which program|deeper change|properly|fundamentally|journey|keep happening)\b",re.I)

@dataclass(frozen=True)
class HorizonDecision:
    horizon: str
    boost_relevance: str
    program_relevance: str
    program_assessment_required: bool

class SupportHorizonClassifier:
    def classify(self,message:str,analysis:MentalStateAnalysis) -> HorizonDecision:
        immediate=bool(IMMEDIATE.search(message) or any(pattern.search(message) for _,pattern in COLLECTION_ROUTES)) or analysis.support_horizon in {"IMMEDIATE","SHORT_TERM","BOTH"}
        # Program assessment requires explicit evidence in user text/history; model classification alone cannot authorize it.
        explicit_program=bool(re.search(r"\b(program|long[- ]term journey|structured (way|support))\b",message,re.I))
        long_term=bool(LONG_TERM.search(message)) or explicit_program
        horizon="BOTH" if immediate and long_term else "LONG_TERM" if long_term else "IMMEDIATE" if immediate else analysis.support_horizon
        if horizon not in {"IMMEDIATE","SHORT_TERM","LONG_TERM","BOTH"}: horizon="UNCLEAR"
        return HorizonDecision(horizon,"HIGH" if immediate else "MEDIUM" if long_term else "LOW",
                               "HIGH" if long_term else "VERY_LOW",long_term or explicit_program)

# Deterministic semantic routes to the supplied current collection names.
COLLECTION_ROUTES = [
    ("collection-061",re.compile(r"\b(sleep|asleep|insomnia|switch (my )?brain off|lying awake)\b",re.I)),
    ("collection-032",re.compile(r"\b(physically exhausted|physical exhaustion|no physical energy|fatigue|fatigued|wiped out)\b",re.I)),
    ("collection-055",re.compile(r"\b(public speaking|speech|presentation)\b.*\b(man|male|him)\b",re.I)),
    ("collection-056",re.compile(r"\b(public speaking|speech|presentation)\b.*\b(woman|female|her)\b",re.I)),
    ("collection-020",re.compile(r"\b(fear|afraid|scared|nervous|presentation|speech)\b",re.I)),
    ("collection-002",re.compile(r"\b(anxious|anxiety|worry|worrying|racing thoughts|overthinking|replaying)\b",re.I)),
    ("collection-003",re.compile(r"\b(sad|low|heartbroken|grief|breakup|relationship ended)\b",re.I)),
    ("collection-017",re.compile(r"\b(childhood|when I was (a )?child|father|mother|parent).{0,80}\b(hit|beat|drunk|painful memor)\w*\b",re.I)),
    ("collection-059",re.compile(r"\b(lonely|loneliness|isolated)\b",re.I)),
    ("collection-024",re.compile(r"\b(angry|anger|aggression|furious)\b",re.I)),
    ("collection-019",re.compile(r"\b(triggered|reactive|reactivity|emotional trigger)\b",re.I)),
    ("collection-025",re.compile(r"\b(confidence|self[- ]esteem|believe in myself)\b",re.I)),
    ("collection-053",re.compile(r"\b(motivation|motivated|enthusiasm|procrastinat)\w*\b",re.I)),
    ("collection-004",re.compile(r"\b(focus|concentrat|mental clarity|clear my head)\w*\b",re.I)),
    ("collection-018",re.compile(r"\b(productiv|energy today|start my day)\w*\b",re.I)),
    ("collection-045",re.compile(r"\b(stress|stressed|pressure|tension|overwhelmed|settle down|calm down)\b",re.I)),
    ("collection-030",re.compile(r"\b(inner peace|calm|settle|unwind|relax)\w*\b",re.I)),
    ("collection-013",re.compile(r"\b(present moment|be present|mindful|grounded)\b",re.I)),
]

class ImmediateSupportEngine:
    def recommend(self,message:str,analysis:MentalStateAnalysis,triage:TriageResult,repo:KnowledgeRepository,horizon:HorizonDecision,has_context:bool=False) -> tuple[list[Recommendation],str|None]:
        if triage.blocks_recommendations or horizon.horizon=="LONG_TERM": return [],None
        matches=[]
        for collection_id,pattern in COLLECTION_ROUTES:
            if pattern.search(message):
                item=repo.collection(collection_id)
                if item and collection_id not in [m[0] for m in matches]: matches.append((collection_id,item))
        if not matches:
            return [],None if has_context else "Is it more that your thoughts won’t settle, you’re feeling low, or something specific happened today?"
        primary=matches[0][1]
        rec=Recommendation(id=primary["id"],title=primary["display_name"],reason="Matches your dominant immediate need.",source=primary["source"])
        return [rec],None

class LongTermJourneyEngine:
    def assess(self,horizon:HorizonDecision,triage:TriageResult) -> bool:
        return not triage.blocks_recommendations and horizon.program_assessment_required
