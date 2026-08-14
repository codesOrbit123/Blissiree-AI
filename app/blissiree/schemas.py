from typing import Literal
from pydantic import BaseModel, Field

class MentalStateAnalysis(BaseModel):
    intent: str = "general_support"
    reported_emotions: list[str] = []
    emotional_themes: list[str] = []
    reported_issues: list[str] = []
    current_need: list[str] = []
    sleep_difficulty: bool = False
    stress_score_estimate: int | None = Field(default=None, ge=0, le=10)
    distress_signals: list[str] = []
    safety_signals: list[str] = []
    relationship_context: list[str] = []
    user_reported_diagnoses: list[str] = []
    confidence: float = Field(default=0.0, ge=0, le=1)
    support_horizon: Literal["IMMEDIATE", "SHORT_TERM", "LONG_TERM", "BOTH", "UNCLEAR"] = "UNCLEAR"
    primary_current_need: str | None = None
    secondary_current_needs: list[str] = []
    boost_relevance_score: Literal["VERY_LOW", "LOW", "MEDIUM", "HIGH"] = "LOW"
    program_relevance_score: Literal["VERY_LOW", "LOW", "MEDIUM", "HIGH"] = "VERY_LOW"
    boost_intent: bool = False
    program_intent: bool = False

class ConversationContext(BaseModel):
    intent: Literal["PRODUCT_INFORMATION","COMPANION_SUPPORT","RESOURCE_GUIDANCE","CONSULTATION_BOOKING","OUT_OF_SCOPE","FEEDBACK","REFUSAL"] = "COMPANION_SUPPORT"
    active_topic: Literal["BLISSIREE_OVERVIEW","BLISSIREE_PROGRAMS","EMOTIONAL_EMPOWERMENT","UNSTOPPABLE_YOU","BOOST_LIBRARY","CONSULTATIONS","USER_SITUATION","OTHER"] = "USER_SITUATION"
    user_goal: str = ""
    question_to_answer: str = ""
    is_follow_up: bool = False
    needs_clarification: bool = False
    known_facts: list[str] = []
    reported_emotions: list[str] = []
    already_answered: list[str] = []
    conversation_stage: Literal["INFORMATION","DISCOVERY","EXPLORATION","SUPPORT_ACTION","RECOMMENDATION"] = "DISCOVERY"
    confidence: float = Field(default=0.0,ge=0,le=1)
    current_explicit_themes: list[str] = []
    current_inferred_themes: list[str] = []
    resolved_reference: str | None = None
    pending_offer_type: str | None = None
    raw_user_message: str = ""
    interpreted_message: str = ""
    ambiguities: list[str] = []

class Recommendation(BaseModel):
    id: str
    title: str
    reason: str
    source: str

class UserState(BaseModel):
    triage: Literal["T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7"]
    stress: int | None = None
    reported_emotions: list[str] = []
    current_need: list[str] = []

class ResponseContract(BaseModel):
    persona: Literal["emma", "ben"]
    user_state: UserState
    allowed_actions: dict[str, bool]
    immediate_recommendations: list[Recommendation] = []
    long_term_recommendations: list[Recommendation] = []
    retrieved_knowledge: list[dict]
    response_limits: dict
    support_horizon: Literal["IMMEDIATE", "SHORT_TERM", "LONG_TERM", "BOTH", "UNCLEAR"]
    clarification_question: str | None = None
    program_assessment_required: bool = False
    compiled_instructions: list[dict] = []
    interaction_mode: Literal["SUPPORT", "INFORMATION", "CASUAL", "OUT_OF_SCOPE", "REFUSAL", "FEEDBACK"] = "SUPPORT"
    response_guidance: str | None = None
    conversation_stage: Literal["INFORMATION", "DISCOVERY", "EXPLORATION", "SUPPORT_ACTION", "RECOMMENDATION"] = "DISCOVERY"
    conversation_brief: str | None = None
    persona_requirements: list[str] = []
    question_to_answer: str | None = None

class CoachProposal(BaseModel):
    title: str
    instruction: str
    target: Literal["ALL","EMMA","BEN"] = "ALL"
    category: str = "CONVERSATION"
    priority: Literal["CRITICAL","HIGH","NORMAL","PREFERENCE"] = "HIGH"
    why_it_exists: str
    regression_tests: list[str] = []

class CoachResponse(BaseModel):
    message: str
    proposal: CoachProposal | None = None
