import json
import logging
import time
import uuid
from .config import AIConfig
from .knowledge import KnowledgeRepository
from .providers import AnalysisLLMProvider, ConversationLLMProvider
from .recommendations import ImmediateSupportEngine, LongTermJourneyEngine, SupportHorizonClassifier
from .safety import OutputSafetyValidator, TriageEngine, deterministic_crisis_response, terminal_turn_kind, terminal_turn_response
from .schemas import ConversationContext,MentalStateAnalysis,ResponseContract,UserState
from .conversation_intent import classify_conversation_intent, contextual_fallback, conversation_stage, stage_guidance
from .product_info import contextual_product_fallback
from .intent_router import route_top_level_intent,consultation_booking_response
from .conversation_state import accepted_recent_recommendation,apply_latest_message_authority,context_query,conversation_brief,fallback_context,information_quality_failures,progress_fallback,recommendation_acceptance_response,recommendation_fulfilment_failures,reconcile_context,resolve_conversation_reference,response_progress_failures,support_progress_stage
from .persona import persona_quality_failures,persona_requirements
from .capability_router import public_agent,route_capability
from .response_reviewer import ResponseReviewAgent

log = logging.getLogger("blissiree.ai")

def contract_fallback(persona:str,message:str,immediate:list,clarification:str|None,program_assessment:bool,intent,has_context:bool) -> str:
    if immediate:
        lead="Let’s focus on what would support you right now." if persona=="emma" else "Let’s deal with what you need right now first."
        return f"{lead} The {immediate[0].title} is the best current match."
    if clarification:
        return clarification
    if program_assessment:
        return "A structured Blissiree journey may be appropriate to assess. To help distinguish between Emotional Empowerment and Unstoppable You, what longer-term change are you most hoping to make?"
    return contextual_fallback(persona,message,intent,has_context)

class BlissireeOrchestrator:
    def __init__(self, config: AIConfig, provider, repository: KnowledgeRepository,training_store=None):
        self.config=config; self.analysis:AnalysisLLMProvider=provider; self.conversation:ConversationLLMProvider=provider; self.repo=repository;self.training_store=training_store
        self.triage=TriageEngine(); self.horizon=SupportHorizonClassifier(); self.immediate=ImmediateSupportEngine(); self.long_term=LongTermJourneyEngine(); self.validator=OutputSafetyValidator();self.reviewer=ResponseReviewAgent()

    def _rewrite(self,text:str,persona:str,message:str,history:list[dict],mode:str,errors:list[str]) -> str:
        """Every user-facing draft passes through the persona/correlation editor."""
        try:
            rewrite=getattr(self.conversation,"rewrite_response",None)
            if rewrite:
                rewritten,_=rewrite(text,self.reviewer.brief(persona,message,history,mode))
                return rewritten or text
        except Exception as exc:
            errors.append(f"response_rewrite:{type(exc).__name__}")
        return text

    def respond(self, message: str, persona: str, history: list[dict], conversation_id: str | None = None) -> dict:
        request_id=str(uuid.uuid4()); started=time.perf_counter(); errors=[]
        terminal_kind=terminal_turn_kind(message,self.triage)
        if terminal_kind:
            route=route_capability(ConversationContext(),history,terminal=True)
            text=terminal_turn_response(persona,terminal_kind)
            text=self._rewrite(text,persona,message,history,"TERMINAL",errors)
            event={"request_id":request_id,"conversation_id":conversation_id,"persona":persona,"analysis_model":self.config.analysis_model,
                "conversation_model":self.config.conversation_model,"triage_level":"T7","retrieved_content_ids":[],"recommended_boost_ids":[],
                "recommended_program_id":None,"support_horizon":"UNCLEAR","boost_relevance_score":"VERY_LOW","program_relevance_score":"VERY_LOW",
                "latency_analysis_ms":0,"latency_retrieval_ms":0,"latency_generation_ms":0,
                "latency_total_ms":round((time.perf_counter()-started)*1000),"token_usage":{},"model_errors":[],
                "output_validation_result":"pass:terminal_"+terminal_kind}
            log.info(json.dumps(event,separators=(",",":")))
            return {"message":text,"persona":persona,"triage":"T7","request_id":request_id,"sources":[],"active_agent":public_agent(route)}
        casual_intent=classify_conversation_intent(message,MentalStateAnalysis())
        if casual_intent.mode=="CASUAL":
            route=route_capability(ConversationContext(),history)
            text=contextual_fallback(persona,message,casual_intent,bool(history))
            text=self._rewrite(text,persona,message,history,"CASUAL",errors)
            event={"request_id":request_id,"conversation_id":conversation_id,"persona":persona,"analysis_model":self.config.analysis_model,
                "conversation_model":self.config.conversation_model,"triage_level":"T7","retrieved_content_ids":[],"recommended_boost_ids":[],
                "recommended_program_id":None,"support_horizon":"UNCLEAR","boost_relevance_score":"VERY_LOW","program_relevance_score":"VERY_LOW",
                "latency_analysis_ms":0,"latency_retrieval_ms":0,"latency_generation_ms":round((time.perf_counter()-started)*1000),
                "latency_total_ms":round((time.perf_counter()-started)*1000),"token_usage":{},"model_errors":errors,
                "output_validation_result":"pass:casual"}
            log.info(json.dumps(event,separators=(",",":")))
            return {"message":text,"persona":persona,"triage":"T7","request_id":request_id,"sources":[],"active_agent":public_agent(route)}
        if accepted_recent_recommendation(message,history):
            context=ConversationContext(intent="RESOURCE_GUIDANCE",conversation_stage="RECOMMENDATION",confidence=1)
            route=route_capability(context,history)
            text=recommendation_acceptance_response(persona,message)
            text=self._rewrite(text,persona,message,history,"RECOMMENDATION_ACCEPTANCE",errors)
            event={"request_id":request_id,"conversation_id":conversation_id,"persona":persona,"analysis_model":self.config.analysis_model,
                "conversation_model":self.config.conversation_model,"triage_level":"T7","retrieved_content_ids":[],"recommended_boost_ids":[],
                "recommended_program_id":None,"support_horizon":"IMMEDIATE","boost_relevance_score":"VERY_LOW","program_relevance_score":"VERY_LOW",
                "latency_analysis_ms":0,"latency_retrieval_ms":0,"latency_generation_ms":round((time.perf_counter()-started)*1000),
                "latency_total_ms":round((time.perf_counter()-started)*1000),"token_usage":{},"model_errors":errors,
                "output_validation_result":"pass:recommendation_acceptance"}
            log.info(json.dumps(event,separators=(",",":")))
            return {"message":text,"persona":persona,"triage":"T7","request_id":request_id,"sources":[],"active_agent":public_agent(route)}
        context_started=time.perf_counter()
        try:context=self.analysis.contextualize(message,history) if self.config.analysis_enabled else fallback_context(message,history)
        except Exception as exc:
            errors.append(f"context:{type(exc).__name__}");context=fallback_context(message,history)
        context=resolve_conversation_reference(reconcile_context(apply_latest_message_authority(context,message,history),message,history),message,history)
        context_ms=round((time.perf_counter()-context_started)*1000)
        routed_intent=route_top_level_intent(message,history)
        booking_safety_context="\n".join([str(x.get("content","")) for x in history[-4:] if x.get("role")=="user"]+[message])
        booking_safety=self.triage.evaluate(booking_safety_context,MentalStateAnalysis())
        if (context.intent=="CONSULTATION_BOOKING" or routed_intent.kind == "CONSULTATION_BOOKING") and not booking_safety.blocks_recommendations:
            route=route_capability(context.model_copy(update={"intent":"CONSULTATION_BOOKING"}),history)
            text=consultation_booking_response(routed_intent.service,persona)
            text=self._rewrite(text,persona,message,history,"BOOKING",errors)
            event={"request_id":request_id,"conversation_id":conversation_id,"persona":persona,"analysis_model":self.config.analysis_model,
                "conversation_model":self.config.conversation_model,"triage_level":"T7","retrieved_content_ids":["official-site:consultations"],
                "recommended_boost_ids":[],"recommended_program_id":None,"support_horizon":"UNCLEAR","boost_relevance_score":"VERY_LOW",
                "program_relevance_score":"VERY_LOW","latency_analysis_ms":0,"latency_retrieval_ms":0,"latency_generation_ms":0,
                "latency_total_ms":round((time.perf_counter()-started)*1000),"token_usage":{},"model_errors":[],
                "output_validation_result":"pass:consultation_booking","conversation_stage":"BOOKING","service":routed_intent.service}
            log.info(json.dumps(event,separators=(",",":")))
            return {"message":text,"persona":persona,"triage":"T7","request_id":request_id,"sources":["BLISSIREE_OFFICIAL_WEBSITE"],"active_agent":public_agent(route)}
        if context.intent=="PRODUCT_INFORMATION":
            route=route_capability(context,history)
            query=context_query(context,message);t=time.perf_counter();docs=self.repo.retrieve(query) if self.config.rag_enabled else []
            docs=[d for d in docs if d["source"]=="BLISSIREE_OFFICIAL_WEBSITE"][:6];retrieval_ms=round((time.perf_counter()-t)*1000)
            contract=ResponseContract(persona=persona,user_state=UserState(triage="T7"),allowed_actions={"ask_followup":context.needs_clarification,"recommend_boost":False,"recommend_program":False,"assess_program":False,"use_pas":False},
                retrieved_knowledge=[{"id":d["id"],"source":d["source"],"authority":d["authority"],"text":d["text"]} for d in docs],
                response_limits={"avoid_diagnosis":True,"avoid_medical_claims":True,"answer_question_directly":True},support_horizon="UNCLEAR",
                interaction_mode="INFORMATION",response_guidance="Answer the actual product question directly from approved official knowledge.",conversation_stage="INFORMATION",
                conversation_brief="Known context: "+"; ".join(context.known_facts+context.already_answered+context.current_explicit_themes),question_to_answer=context.question_to_answer,
                persona_requirements=persona_requirements(persona))
            t=time.perf_counter();usage={};failures=[]
            product_titles={"Emotional Empowerment Program","Unstoppable You Program"}
            try:
                text,usage=self.conversation.generate(contract,message,history)
                failures=self.validator.validate(text,product_titles,product_titles)[1]+information_quality_failures(text,context)+persona_quality_failures(text,persona,history,message,"INFORMATION")
                if failures:
                    text,usage=self.conversation.generate(contract,message,history,"; ".join(failures))
                    failures=self.validator.validate(text,product_titles,product_titles)[1]+information_quality_failures(text,context)+persona_quality_failures(text,persona,history,message,"INFORMATION")
                if failures:text=contextual_product_fallback(context,message,history)
            except Exception as exc:
                errors.append(f"information_generation:{type(exc).__name__}");text=contextual_product_fallback(context,message,history)
            text=self._rewrite(text,persona,message,history,"INFORMATION",errors)
            generation_ms=round((time.perf_counter()-t)*1000)
            event={"request_id":request_id,"conversation_id":conversation_id,"persona":persona,"analysis_model":self.config.analysis_model,
                "conversation_model":self.config.conversation_model,"triage_level":"T7","retrieved_content_ids":[d["id"] for d in docs],
                "recommended_boost_ids":[],"recommended_program_id":None,"support_horizon":"UNCLEAR","boost_relevance_score":"VERY_LOW",
                "program_relevance_score":"VERY_LOW","latency_analysis_ms":context_ms,"latency_retrieval_ms":retrieval_ms,"latency_generation_ms":generation_ms,
                "latency_total_ms":round((time.perf_counter()-started)*1000),"token_usage":usage,"model_errors":errors,
                "output_validation_result":"pass:contextual_information" if not failures else "fallback:contextual_information","conversation_stage":"INFORMATION","active_topic":context.active_topic}
            log.info(json.dumps(event,separators=(",",":")))
            return {"message":text,"persona":persona,"triage":"T7","request_id":request_id,"sources":["BLISSIREE_OFFICIAL_WEBSITE"],"active_agent":public_agent(route)}
        recent_user=[str(x.get("content","")) for x in history[-8:] if x.get("role")=="user"]
        safety_context="\n".join(recent_user[-3:]+[message])
        t=time.perf_counter()
        try:
            analysis=self.analysis.analyze({"message":message,"recentConversationSummary":history[-8:],"recentCheckins":{},"currentProgram":{},"userPreferences":{}}) if self.config.analysis_enabled else MentalStateAnalysis()
        except Exception as exc:
            errors.append(f"analysis:{type(exc).__name__}"); analysis=MentalStateAnalysis(confidence=0)
        if context.current_explicit_themes:
            analysis.reported_emotions=list(context.reported_emotions)
            analysis.emotional_themes=list(context.current_explicit_themes)
        analysis_ms=round((time.perf_counter()-t)*1000)
        triage=self.triage.evaluate(safety_context,analysis)
        route=route_capability(context,history,safety_override=triage.blocks_recommendations)
        horizon=self.horizon.classify(safety_context,analysis)
        conversation_intent=classify_conversation_intent(message,analysis)
        correction=context.intent=="FEEDBACK" and "LOW_CONFIDENCE" in context.current_explicit_themes
        if context.intent in {"COMPANION_SUPPORT","RESOURCE_GUIDANCE"} or correction:conversation_intent=type(conversation_intent)("SUPPORT",None)
        if context.intent=="OUT_OF_SCOPE":conversation_intent=type(conversation_intent)("OUT_OF_SCOPE","Acknowledge the actual request and bridge naturally to Blissiree's role.")
        elif context.intent=="FEEDBACK" and not correction:conversation_intent=type(conversation_intent)("FEEDBACK","Accept the feedback and adjust directly.")
        elif context.intent=="REFUSAL":conversation_intent=type(conversation_intent)("REFUSAL","Respect the request for space and end without a question.")
        stage="RECOMMENDATION" if context.intent=="RESOURCE_GUIDANCE" and not context.needs_clarification else conversation_stage(message,history)
        if stage != "RECOMMENDATION":
            deterministic_stage=support_progress_stage(message,history)
            stage="SUPPORT_ACTION" if deterministic_stage=="SUPPORT_ACTION" else context.conversation_stage if context.conversation_stage in {"DISCOVERY","EXPLORATION","SUPPORT_ACTION"} else deterministic_stage
        t=time.perf_counter(); query=context_query(context,message);docs=self.repo.retrieve(query) if self.config.rag_enabled else []
        if self.config.rag_enabled and self.training_store:docs.extend(self.training_store.retrieve_knowledge(query,target=persona.upper()))
        retrieval_ms=round((time.perf_counter()-t)*1000)
        recommendation_context=" ".join(x for x in (safety_context,context.resolved_reference or "",context.user_goal) if x)
        immediate,clarification=self.immediate.recommend(recommendation_context,analysis,triage,self.repo,horizon,bool(recent_user))
        if context.intent=="RESOURCE_GUIDANCE" and context.needs_clarification:
            immediate=[];clarification=("Do you mean the Blissiree content I just mentioned?" if history else "What would you like me to share—an audio, a Program, or information about Blissiree?")
        program_assessment=self.long_term.assess(horizon,triage); long_term=[]
        if conversation_intent.mode != "SUPPORT":
            immediate,clarification,program_assessment=[],None,False
        elif stage != "RECOMMENDATION":
            immediate,clarification,program_assessment=[],None,False
        contract=ResponseContract(persona=persona,user_state=UserState(triage=triage.level,stress=analysis.stress_score_estimate,
            reported_emotions=analysis.reported_emotions,current_need=analysis.current_need),
            allowed_actions={"ask_followup":True,"recommend_boost":bool(immediate),"recommend_program":False,"assess_program":program_assessment,"use_pas":triage.level in {"T6","T7"}},
            immediate_recommendations=immediate,long_term_recommendations=long_term,
            retrieved_knowledge=[{"id":d["id"],"source":d["source"],"authority":d["authority"],"text":d["text"]} for d in docs],
            response_limits={"max_recommendations":2,"avoid_diagnosis":True,"avoid_medical_claims":True,"use_exact_recommendation_titles":True,
                             "boost_first":True,"do_not_append_program_upsell":True},support_horizon=horizon.horizon,
            clarification_question=clarification,program_assessment_required=program_assessment,
            compiled_instructions=[{"id":x["id"],"instruction":x["instruction"],"priority":x["priority"]} for x in (self.training_store.effective(persona.upper()) if self.training_store else [])],
            interaction_mode=conversation_intent.mode,
            response_guidance=" ".join(x for x in (conversation_intent.guidance,stage_guidance(stage)) if x),
            conversation_stage=stage,conversation_brief=" ".join(context.known_facts) or conversation_brief(message,history),question_to_answer=context.question_to_answer,
            persona_requirements=persona_requirements(persona))
        t=time.perf_counter(); usage={}; validation="fallback"
        if triage.blocks_recommendations:
            text=deterministic_crisis_response(triage.level,message)
        elif conversation_intent.mode in {"REFUSAL","FEEDBACK"}:
            text=contextual_fallback(persona,message,conversation_intent,bool(recent_user)); validation="pass:refusal"
        else:
            try:
                text,usage=self.conversation.generate(contract,message,history)
                known_titles={x["display_name"] for x in self.repo.catalog["boost_collections"]}|{
                    x["display_title"] for x in self.repo.catalog["boosts"]}|{
                    "Emotional Empowerment Program","Unstoppable You Program"}
                valid,failures=self.validator.validate(text,{r.title for r in immediate+long_term},known_titles) if self.config.output_validation_enabled else (True,[])
                progress_failures=response_progress_failures(text,history,stage)
                progress_failures+=recommendation_fulfilment_failures(text,[r.title for r in immediate+long_term],stage)
                persona_failures=persona_quality_failures(text,persona,history,message,"SUPPORT")
                failures.extend(progress_failures+persona_failures);valid=valid and not progress_failures and not persona_failures
                validation="pass" if valid else "failed:"+",".join(failures)
                if not valid and (progress_failures or persona_failures):
                    text,usage=self.conversation.generate(contract,message,history,"; ".join(progress_failures+persona_failures))
                    valid,failures=self.validator.validate(text,{r.title for r in immediate+long_term},known_titles) if self.config.output_validation_enabled else (True,[])
                    remaining=response_progress_failures(text,history,stage)+recommendation_fulfilment_failures(text,[r.title for r in immediate+long_term],stage)+persona_quality_failures(text,persona,history,message,"SUPPORT")
                    if remaining or not valid:
                        text=contract_fallback(persona,message,immediate,clarification,program_assessment,conversation_intent,bool(recent_user))
                    validation="pass:regenerated" if not remaining and valid else "fallback:"+",".join(remaining or failures)
                elif not valid:text=contract_fallback(persona,message,immediate,clarification,program_assessment,conversation_intent,bool(recent_user))
            except Exception as exc:
                errors.append(f"generation:{type(exc).__name__}")
                text=contract_fallback(persona,message,immediate,clarification,program_assessment,conversation_intent,bool(recent_user))
        text=self._rewrite(text,persona,message,history,"SAFETY" if triage.blocks_recommendations else "SUPPORT",errors)
        generation_ms=round((time.perf_counter()-t)*1000)
        event={"request_id":request_id,"conversation_id":conversation_id,"persona":persona,"analysis_model":self.config.analysis_model,
            "conversation_model":self.config.conversation_model,"triage_level":triage.level,"retrieved_content_ids":[d["id"] for d in docs],
            "recommended_boost_ids":[r.id for r in immediate],"recommended_program_id":long_term[0].id if long_term else None,
            "support_horizon":horizon.horizon,"boost_relevance_score":horizon.boost_relevance,"program_relevance_score":horizon.program_relevance,
            "latency_analysis_ms":analysis_ms,"latency_retrieval_ms":retrieval_ms,"latency_generation_ms":generation_ms,
            "latency_total_ms":round((time.perf_counter()-started)*1000),"token_usage":usage,"model_errors":errors,"output_validation_result":validation}
        event["conversation_stage"]=stage
        event["resolved_intent"]=context.intent;event["resolved_reference"]=context.resolved_reference;event["current_explicit_themes"]=context.current_explicit_themes
        log.info(json.dumps(event,separators=(",",":")))
        return {"message":text,"persona":persona,"triage":triage.level,"request_id":request_id,"sources":sorted({d["source"] for d in docs}),"active_agent":public_agent(route)}
