import json
import logging
import time
import uuid
from .config import AIConfig
from .knowledge import KnowledgeRepository
from .providers import AnalysisLLMProvider, ConversationLLMProvider
from .recommendations import ImmediateSupportEngine, LongTermJourneyEngine, SupportHorizonClassifier
from .safety import OutputSafetyValidator, TriageEngine, deterministic_crisis_response, terminal_turn_kind, terminal_turn_response
from .schemas import MentalStateAnalysis, ResponseContract, UserState

log = logging.getLogger("blissiree.ai")

def contract_fallback(persona:str,immediate:list,clarification:str|None,program_assessment:bool) -> str:
    if immediate:
        lead="Let’s focus on what would support you right now." if persona=="emma" else "Let’s deal with what you need right now first."
        return f"{lead} The {immediate[0].title} is the best current match."
    if clarification:
        return clarification
    if program_assessment:
        return "A structured Blissiree journey may be appropriate to assess. To help distinguish between Emotional Empowerment and Unstoppable You, what longer-term change are you most hoping to make?"
    return deterministic_crisis_response("T5")

class BlissireeOrchestrator:
    def __init__(self, config: AIConfig, provider, repository: KnowledgeRepository,training_store=None):
        self.config=config; self.analysis:AnalysisLLMProvider=provider; self.conversation:ConversationLLMProvider=provider; self.repo=repository;self.training_store=training_store
        self.triage=TriageEngine(); self.horizon=SupportHorizonClassifier(); self.immediate=ImmediateSupportEngine(); self.long_term=LongTermJourneyEngine(); self.validator=OutputSafetyValidator()

    def respond(self, message: str, persona: str, history: list[dict], conversation_id: str | None = None) -> dict:
        request_id=str(uuid.uuid4()); started=time.perf_counter(); errors=[]
        terminal_kind=terminal_turn_kind(message,self.triage)
        if terminal_kind:
            text=terminal_turn_response(persona,terminal_kind)
            event={"request_id":request_id,"conversation_id":conversation_id,"persona":persona,"analysis_model":self.config.analysis_model,
                "conversation_model":self.config.conversation_model,"triage_level":"T7","retrieved_content_ids":[],"recommended_boost_ids":[],
                "recommended_program_id":None,"support_horizon":"UNCLEAR","boost_relevance_score":"VERY_LOW","program_relevance_score":"VERY_LOW",
                "latency_analysis_ms":0,"latency_retrieval_ms":0,"latency_generation_ms":0,
                "latency_total_ms":round((time.perf_counter()-started)*1000),"token_usage":{},"model_errors":[],
                "output_validation_result":"pass:terminal_"+terminal_kind}
            log.info(json.dumps(event,separators=(",",":")))
            return {"message":text,"persona":persona,"triage":"T7","request_id":request_id,"sources":[]}
        recent_user=[str(x.get("content","")) for x in history[-8:] if x.get("role")=="user"]
        safety_context="\n".join(recent_user[-3:]+[message])
        t=time.perf_counter()
        try:
            analysis=self.analysis.analyze({"message":message,"recentConversationSummary":history[-8:],"recentCheckins":{},"currentProgram":{},"userPreferences":{}}) if self.config.analysis_enabled else MentalStateAnalysis()
        except Exception as exc:
            errors.append(f"analysis:{type(exc).__name__}"); analysis=MentalStateAnalysis(confidence=0)
        analysis_ms=round((time.perf_counter()-t)*1000)
        triage=self.triage.evaluate(safety_context,analysis)
        horizon=self.horizon.classify(safety_context,analysis)
        t=time.perf_counter(); docs=self.repo.retrieve(message) if self.config.rag_enabled else []
        if self.config.rag_enabled and self.training_store:docs.extend(self.training_store.retrieve_knowledge(message,target=persona.upper()))
        retrieval_ms=round((time.perf_counter()-t)*1000)
        immediate,clarification=self.immediate.recommend(safety_context,analysis,triage,self.repo,horizon,bool(recent_user))
        program_assessment=self.long_term.assess(horizon,triage); long_term=[]
        contract=ResponseContract(persona=persona,user_state=UserState(triage=triage.level,stress=analysis.stress_score_estimate,
            reported_emotions=analysis.reported_emotions,current_need=analysis.current_need),
            allowed_actions={"ask_followup":True,"recommend_boost":bool(immediate),"recommend_program":False,"assess_program":program_assessment,"use_pas":triage.level in {"T6","T7"}},
            immediate_recommendations=immediate,long_term_recommendations=long_term,
            retrieved_knowledge=[{"id":d["id"],"source":d["source"],"authority":d["authority"],"text":d["text"]} for d in docs],
            response_limits={"max_recommendations":2,"avoid_diagnosis":True,"avoid_medical_claims":True,"use_exact_recommendation_titles":True,
                             "boost_first":True,"do_not_append_program_upsell":True},support_horizon=horizon.horizon,
            clarification_question=clarification,program_assessment_required=program_assessment,
            compiled_instructions=[{"id":x["id"],"instruction":x["instruction"],"priority":x["priority"]} for x in (self.training_store.effective(persona.upper()) if self.training_store else [])])
        t=time.perf_counter(); usage={}; validation="fallback"
        if triage.blocks_recommendations:
            text=deterministic_crisis_response(triage.level,message)
        else:
            try:
                text,usage=self.conversation.generate(contract,message,history)
                valid,failures=self.validator.validate(text,{r.title for r in immediate+long_term}) if self.config.output_validation_enabled else (True,[])
                validation="pass" if valid else "failed:"+",".join(failures)
                if not valid: text=contract_fallback(persona,immediate,clarification,program_assessment)
            except Exception as exc:
                errors.append(f"generation:{type(exc).__name__}"); text=contract_fallback(persona,immediate,clarification,program_assessment)
        generation_ms=round((time.perf_counter()-t)*1000)
        event={"request_id":request_id,"conversation_id":conversation_id,"persona":persona,"analysis_model":self.config.analysis_model,
            "conversation_model":self.config.conversation_model,"triage_level":triage.level,"retrieved_content_ids":[d["id"] for d in docs],
            "recommended_boost_ids":[r.id for r in immediate],"recommended_program_id":long_term[0].id if long_term else None,
            "support_horizon":horizon.horizon,"boost_relevance_score":horizon.boost_relevance,"program_relevance_score":horizon.program_relevance,
            "latency_analysis_ms":analysis_ms,"latency_retrieval_ms":retrieval_ms,"latency_generation_ms":generation_ms,
            "latency_total_ms":round((time.perf_counter()-started)*1000),"token_usage":usage,"model_errors":errors,"output_validation_result":validation}
        log.info(json.dumps(event,separators=(",",":")))
        return {"message":text,"persona":persona,"triage":triage.level,"request_id":request_id,"sources":sorted({d["source"] for d in docs})}
