import sys
import unittest
import os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/"app"))
from blissiree.schemas import MentalStateAnalysis
from blissiree.safety import OutputSafetyValidator,TriageEngine,deterministic_crisis_response,terminal_turn_kind,terminal_turn_response
from blissiree.recommendations import SupportHorizonClassifier,ImmediateSupportEngine
from blissiree.knowledge import KnowledgeRepository,rank_training_knowledge
from blissiree.conversation_intent import ConversationIntent,classify_conversation_intent,contextual_fallback,conversation_stage
from blissiree.product_info import is_product_information_request,product_information_response
from blissiree.intent_router import BOOKING_URL,consultation_booking_response,route_top_level_intent
from blissiree.conversation_state import apply_latest_message_authority,conversation_brief,fallback_context,information_quality_failures,progress_fallback,recommendation_fulfilment_failures,reconcile_context,resolve_conversation_reference,response_progress_failures,support_progress_stage
from blissiree.schemas import ConversationContext
from blissiree.persona import persona_quality_failures,persona_requirements
from blissiree.capability_router import public_agent,route_capability

class TriageTests(unittest.TestCase):
    def setUp(self): self.engine=TriageEngine()
    def level(self,text,stress=None): return self.engine.evaluate(text,MentalStateAnalysis(stress_score_estimate=stress)).level
    def test_self_harm(self): self.assertEqual(self.level("I might hurt myself tonight"),"T1")
    def test_others(self): self.assertEqual(self.level("I will hurt someone"),"T2")
    def test_abuse(self): self.assertEqual(self.level("My partner hits me"),"T3")
    def test_medical(self): self.assertEqual(self.level("I have chest pain"),"T4")
    def test_unexplained_weakness_red_flag(self): self.assertEqual(self.level("I have sudden one-sided weakness and slurred speech"),"T4")
    def test_drowsy_driving_red_flag(self): self.assertEqual(self.level("I am falling asleep while driving"),"T4")
    def test_drowsy_driving_stops_activity_before_escalation(self):
        reply=deterministic_crisis_response("T4","I keep falling asleep while driving")
        self.assertIn("stop driving",reply.lower())
        self.assertIn("safe alternative transport",reply.lower())
    def test_coercive_control(self): self.assertEqual(self.level("My partner controls my money and movement"),"T3")
    def test_severe(self): self.assertEqual(self.level("I can't cope anymore"),"T5")
    def test_moderate(self): self.assertEqual(self.level("I feel overwhelmed"),"T6")
    def test_stable(self): self.assertEqual(self.level("I had a pleasant morning"),"T7")
    def test_stress(self): self.assertEqual(self.level("A difficult day",9),"T5")

class OutputTests(unittest.TestCase):
    def test_diagnosis_rejected(self): self.assertFalse(OutputSafetyValidator().validate("You have depression.",set())[0])
    def test_support_passes(self): self.assertTrue(OutputSafetyValidator().validate("We can take one small step.",set())[0])
    def test_patronising_endearment_rejected(self): self.assertFalse(OutputSafetyValidator().validate("Oh, my dear, that is difficult.",set())[0])
    def test_invented_collection_rejected(self): self.assertFalse(OutputSafetyValidator().validate("Try the Magical Healing Collection.",set())[0])
    def test_invented_program_rejected(self): self.assertFalse(OutputSafetyValidator().validate('We have a program called "Understanding Relationship Patterns".',set())[0])
    def test_internal_contract_leak_rejected(self): self.assertFalse(OutputSafetyValidator().validate("{'response_contract': {'persona': 'emma', 'compiled_instructions': []}}",set())[0])
    def test_ineligible_known_title_rejected(self):
        self.assertFalse(OutputSafetyValidator().validate("Try the Sleep Support Collection.",set(),{"Sleep Support Collection"})[0])
    def test_invented_named_boost_rejected(self):
        valid,failures=OutputSafetyValidator().validate("I recommend the **Calm Mind Boost**.",{"Anxious Thoughts Support Collection"})
        self.assertFalse(valid)
        self.assertIn("unapproved_named_resource",failures)
    def test_markdown_split_invented_boost_rejected(self):
        valid,failures=OutputSafetyValidator().validate("Try the **Calm** Boost.",{"Stress and Tension Management Collection"})
        self.assertFalse(valid)
        self.assertIn("unapproved_named_resource",failures)

class RecommendationTests(unittest.TestCase):
    immediate=[
      "I'm struggling to sleep tonight.","I have a presentation tomorrow and feel nervous.","My relationship ended yesterday and I'm struggling.",
      "I'm stressed from work today.","What should I listen to tonight?","I'm feeling low right now.","I need to calm down now.",
      "My thoughts are racing tonight.","I feel lonely today.","I am angry after work today.","I need motivation today.",
      "Help me focus this afternoon.","I need confidence before an event.","I feel triggered right now.","I need to unwind tonight.",
      "I can't switch my brain off tonight.","I am worrying about tomorrow.","I need energy today.","Help me be present now.",
      "I feel sad tonight.","Work pressure is high today.","I need something to settle down.","I'm replaying everything tonight.",
      "I feel scared about tomorrow.","I want a quick confidence boost now.","I cannot concentrate today.","I need calm this evening.",
      "I feel overwhelmed at the moment.","I need support before my speech.","I feel isolated tonight."
    ]
    long_term=[
      "I've experienced the same relationship patterns for years and want to work through them properly.",
      "I want a structured program to build long-term emotional resilience.","Which Blissiree program should I start?",
      "I've been struggling for six months and want to make deeper changes.","This pattern has continued for years.",
      "I want a long-term journey.","The same pattern keeps happening.","I need structured support for recurring patterns.",
      "I want to fundamentally change how I respond.","Which program is suitable for me?",
      "This happens in every relationship and I want deeper change.","I have had this problem for months.",
      "I want to work through these patterns properly.","I need a structured way to make deeper change.","My reactions are recurring and I want a program."
    ]
    unclear=["I feel bad.","Can you help?","Something is off.","I don't know what I need.","I want support."]
    def setUp(self): self.classifier=SupportHorizonClassifier(); self.analysis=MentalStateAnalysis()
    def test_50_realistic_horizons(self):
        self.assertEqual(len(self.immediate+self.long_term+self.unclear),50)
        for text in self.immediate: self.assertEqual(self.classifier.classify(text,self.analysis).horizon,"IMMEDIATE",text)
        for text in self.long_term: self.assertIn(self.classifier.classify(text,self.analysis).horizon,{"LONG_TERM","BOTH"},text)
        for text in self.unclear: self.assertEqual(self.classifier.classify(text,self.analysis).horizon,"UNCLEAR",text)
    def test_sleep_routes_to_sleep_collection(self):
        repo=KnowledgeRepository(Path(__file__).parents[1]/"knowledge")
        triage=TriageEngine().evaluate("I'm struggling to sleep tonight.",self.analysis)
        recs,_=ImmediateSupportEngine().recommend("I'm struggling to sleep tonight.",self.analysis,triage,repo,self.classifier.classify("I'm struggling to sleep tonight.",self.analysis))
        self.assertEqual(recs[0].title,"Sleep Support Collection")
    def test_switch_mind_off_routes_to_sleep_collection(self):
        message="What should I listen to tonight? I cannot switch my mind off."
        repo=KnowledgeRepository(Path(__file__).parents[1]/"knowledge")
        triage=TriageEngine().evaluate(message,self.analysis)
        recs,_=ImmediateSupportEngine().recommend(message,self.analysis,triage,repo,self.classifier.classify(message,self.analysis))
        self.assertEqual(recs[0].title,"Sleep Support Collection")
    def test_physical_exhaustion_routes_to_approved_collection(self):
        message="I feel physically exhausted today"
        decision=self.classifier.classify(message,self.analysis)
        triage=TriageEngine().evaluate(message,self.analysis)
        repo=KnowledgeRepository(Path(__file__).parents[1]/"knowledge")
        recs,_=ImmediateSupportEngine().recommend(message,self.analysis,triage,repo,decision)
        self.assertEqual(recs[0].title,"Fatigue to Energy Support Collection")
    def test_program_request_has_no_boost(self):
        decision=self.classifier.classify("Which Blissiree program should I start?",self.analysis)
        self.assertTrue(decision.program_assessment_required)
        self.assertEqual(decision.program_relevance,"HIGH")

class ConversationEndingTests(unittest.TestCase):
    def setUp(self): self.triage=TriageEngine()
    def test_goodbye_ends_without_followup(self):
        self.assertEqual(terminal_turn_kind("no thanks good bye",self.triage),"farewell")
        reply=terminal_turn_response("emma","farewell")
        self.assertIn("Goodbye",reply)
        self.assertNotIn("?",reply)
    def test_resolved_issue_closes_gently(self):
        self.assertEqual(terminal_turn_kind("my issue is solved",self.triage),"farewell")
    def test_short_thanks_does_not_repeat_recommendation(self):
        self.assertEqual(terminal_turn_kind("thanks alot emma you are best",self.triage),"thanks")
        self.assertNotIn("Collection",terminal_turn_response("emma","thanks"))
    def test_safety_language_overrides_goodbye(self):
        self.assertIsNone(terminal_turn_kind("goodbye, I am going to kill myself",self.triage))

class ConversationRelevanceTests(unittest.TestCase):
    def test_hostile_refusal_respects_space_without_question(self):
        intent=classify_conversation_intent("get lost",MentalStateAnalysis())
        self.assertEqual(intent.mode,"REFUSAL")
        reply=contextual_fallback("emma","get lost",intent,False)
        self.assertNotIn("?",reply)
        self.assertNotIn("thoughts won",reply.lower())

    def test_out_of_scope_request_redirects_to_core_role(self):
        intent=classify_conversation_intent("What is the bitcoin price?",MentalStateAnalysis())
        self.assertEqual(intent.mode,"OUT_OF_SCOPE")
        reply=contextual_fallback("ben","What is the bitcoin price?",intent,False)
        self.assertIn("emotional wellbeing",reply)
        self.assertNotIn("thoughts won",reply.lower())

    def test_casual_greeting_is_answered_naturally(self):
        intent=classify_conversation_intent("hello",MentalStateAnalysis())
        self.assertEqual(intent.mode,"CASUAL")
        self.assertIn("Hi, I’m Emma",contextual_fallback("emma","hello",intent,False))

    def test_unknown_support_fallback_does_not_use_stock_question(self):
        intent=classify_conversation_intent("Something happened",MentalStateAnalysis())
        reply=contextual_fallback("emma","Something happened",intent,False)
        self.assertNotIn("thoughts won",reply.lower())

    def test_emotional_language_overrides_model_off_topic_false_positive(self):
        analysis=MentalStateAnalysis(intent="off_topic")
        self.assertEqual(classify_conversation_intent("I am stressed about tomorrow",analysis).mode,"SUPPORT")

    def test_financial_loss_is_emotional_support_not_btc_lookup(self):
        self.assertEqual(classify_conversation_intent("I lost $9000 in BTC and I am crying",MentalStateAnalysis()).mode,"SUPPORT")
        reply=contextual_fallback("emma","I lost $9000 in BTC and I am crying",ConversationIntent("SUPPORT",None),True)
        self.assertIn("losing that much",reply.lower())

    def test_tone_criticism_is_feedback_not_new_support_topic(self):
        intent=classify_conversation_intent("You are too rude",MentalStateAnalysis())
        self.assertEqual(intent.mode,"FEEDBACK")
        self.assertIn("missed the mark",contextual_fallback("ben","You are too rude",intent,True))

    def test_opening_disclosure_stays_in_discovery(self):
        self.assertEqual(conversation_stage("I feel emotionally exhausted",[]),"DISCOVERY")

    def test_second_disclosure_stays_in_exploration(self):
        history=[{"role":"user","content":"I feel exhausted"},{"role":"assistant","content":"When did this begin?"}]
        self.assertEqual(conversation_stage("It started two months ago",history),"EXPLORATION")

    def test_third_user_turn_still_requires_explicit_recommendation_request(self):
        history=[{"role":"user","content":"I feel exhausted"},{"role":"assistant","content":"When?"},
                 {"role":"user","content":"Two months"},{"role":"assistant","content":"What affects it?"}]
        self.assertEqual(conversation_stage("Work pressure makes it worse",history),"EXPLORATION")

    def test_direct_resource_request_can_reach_recommendation(self):
        self.assertEqual(conversation_stage("What should I listen to tonight?",[]),"RECOMMENDATION")

class TerriWorkbookTrainingTests(unittest.TestCase):
    def test_all_fifteen_companion_records_are_loaded(self):
        repo=KnowledgeRepository(Path(__file__).parents[1]/"knowledge")
        rows=[d for d in repo.documents if d["source"]=="TERRI_WORKBOOK"]
        self.assertEqual(len(rows),15)

    def test_emotional_exhaustion_retrieves_terri_companion_exemplar(self):
        repo=KnowledgeRepository(Path(__file__).parents[1]/"knowledge")
        rows=repo.retrieve("I feel emotionally exhausted and drained all the time")
        self.assertTrue(any(d["id"]=="terri-workbook:EX-004A" for d in rows))

class ProductInformationTests(unittest.TestCase):
    def test_program_question_is_product_information(self):
        self.assertTrue(is_product_information_request("What programs does Blissiree offer?",[]))
    def test_contextual_yes_retains_product_topic(self):
        history=[{"role":"user","content":"what programs blissiree has to offer"},{"role":"assistant","content":"I can share details."}]
        self.assertTrue(is_product_information_request("yes please share details",history))
    def test_program_overview_uses_exact_offerings(self):
        text=product_information_response("What programs does Blissiree offer?",[])
        self.assertIn("Emotional Empowerment Program",text);self.assertIn("Unstoppable You Program",text)
    def test_generic_followup_does_not_select_assistant_mentioned_consultation(self):
        history=[{"role":"user","content":"what programs blissiree has to offer"},
                 {"role":"assistant","content":"Programs, Boost Library and consultations with Terri are available."}]
        text=product_information_response("yes please share details",history)
        self.assertIn("Emotional Empowerment Program",text)
        self.assertNotIn("free 25-minute discovery call",text)
    def test_official_site_knowledge_is_loaded(self):
        repo=KnowledgeRepository(Path(__file__).parents[1]/"knowledge")
        self.assertTrue(any(d["source"]=="BLISSIREE_OFFICIAL_WEBSITE" for d in repo.documents))
    def test_blissiree_overview_explains_the_platform(self):
        text=product_information_response("What is Blissiree?",[])
        self.assertIn("wellbeing and personal-development platform",text)
        self.assertIn("Emma and Ben AI companions",text)
    def test_emotional_empowerment_gets_specific_details(self):
        text=product_information_response("What is the Emotional Empowerment Program?",[])
        self.assertIn("structured 14-session",text)
        self.assertNotIn("three main in-app pathways",text)
    def test_emotional_topic_change_ends_product_mode(self):
        history=[{"role":"user","content":"What is Blissiree?"},{"role":"assistant","content":"Blissiree is a platform."}]
        self.assertFalse(is_product_information_request("ok i am sad",history))

class ConversationProgressTests(unittest.TestCase):
    def setUp(self):
        self.history=[{"role":"user","content":"I am remembering my dead cat"},{"role":"assistant","content":"Would you like to share more?"},
                      {"role":"user","content":"Her colour was white"},{"role":"assistant","content":"What comes to mind?"},
                      {"role":"user","content":"Sadness"},{"role":"assistant","content":"What feels most present?"}]
    def test_known_facts_are_compiled(self):
        brief=conversation_brief("my brain is stuck in thoughts of her",self.history)
        self.assertIn("colour white",brief);self.assertIn("sadness",brief);self.assertIn("stuck",brief)
    def test_longer_conversation_moves_to_support_action(self):
        self.assertEqual(support_progress_stage("my brain is stuck",self.history),"SUPPORT_ACTION")
    def test_product_turns_do_not_count_as_emotional_discovery(self):
        history=[{"role":"user","content":"What is Blissiree?"},{"role":"assistant","content":"A wellbeing platform"},
                 {"role":"user","content":"What is Emotional Empowerment?"},{"role":"assistant","content":"A 14-session program"}]
        self.assertEqual(support_progress_stage("ok i am sad",history),"DISCOVERY")
    def test_generic_question_is_blocked_after_context(self):
        failures=response_progress_failures("What feels most important right now?",self.history,"SUPPORT_ACTION")
        self.assertIn("generic_question_after_context",failures)
    def test_unsolicited_audio_is_blocked_during_support(self):
        failures=response_progress_failures("Would you like to try a brief audio?",self.history,"SUPPORT_ACTION")
        self.assertIn("unsolicited_resource_in_support_action",failures)
    def test_repeated_full_response_is_blocked(self):
        history=[{"role":"assistant","content":"Let’s slow this moment down gently."}]
        self.assertIn("repeated_full_response",response_progress_failures("Let’s slow this moment down gently.",history,"SUPPORT_ACTION"))
    def test_peace_request_advances_accident_fallback(self):
        history=[{"role":"user","content":"my cat died in a car accident"}]
        text=progress_fallback("emma","I want some peace of mind",history)
        self.assertIn("little calm",text);self.assertNotIn("what you need most",text)
    def test_accident_disclosure_fallback_uses_thread_facts(self):
        history=[{"role":"user","content":"my cat died one year ago in a car accident"}]
        text=progress_fallback("emma","the car fell from a cliff and she died",history)
        self.assertIn("accident",text.lower());self.assertNotIn("what part of this feels most important",text.lower())
    def test_persona_fallbacks_are_distinct_and_contextual(self):
        emma=progress_fallback("emma","I am stuck in thoughts of her",self.history)
        ben=progress_fallback("ben","I am stuck in thoughts of her",self.history)
        self.assertIn("losing your cat",emma);self.assertIn("feet on the floor",ben);self.assertNotEqual(emma,ben)
    def test_fallback_never_invents_colour_from_another_thread(self):
        history=[{"role":"user","content":"my cat died in a car accident"}]
        text=progress_fallback("emma","I want some peace of mind",history)
        self.assertNotIn("white",text.lower());self.assertIn("accident",text.lower())

class ContextEngineTests(unittest.TestCase):
    def test_latest_low_confidence_is_not_sadness(self):
        initial=ConversationContext(reported_emotions=["sadness"],current_inferred_themes=["SADNESS"])
        result=apply_latest_message_authority(initial,"I feel low in confidenc3",[])
        self.assertEqual(result.current_explicit_themes,["LOW_CONFIDENCE"])
        self.assertEqual(result.reported_emotions,[])
        self.assertNotIn("sadness",result.question_to_answer.lower())
    def test_explicit_sadness_is_preserved(self):
        result=apply_latest_message_authority(ConversationContext(),"I feel sad today",[])
        self.assertEqual(result.current_explicit_themes,["SADNESS"])
        self.assertEqual(result.reported_emotions,["sadness"])
    def test_confidence_correction_requires_explicit_repair(self):
        result=apply_latest_message_authority(ConversationContext(),"No, I said confidence",[])
        self.assertEqual(result.intent,"FEEDBACK")
        self.assertIn("confidence, not sadness",result.question_to_answer)
    def test_short_followup_resolves_pending_work_stress_offer(self):
        history=[{"role":"assistant","content":"Blissiree may have an audio collection for work stress. Would you like me to share it?"}]
        result=resolve_conversation_reference(ConversationContext(intent="OUT_OF_SCOPE"),"please share",history)
        self.assertEqual(result.intent,"RESOURCE_GUIDANCE")
        self.assertEqual(result.resolved_reference,"work stress content")
        self.assertFalse(result.needs_clarification)
    def test_short_followup_resolves_natural_content_offer_wording(self):
        history=[{"role":"assistant","content":"I can show you relevant work-stress content if you would like."}]
        result=resolve_conversation_reference(ConversationContext(intent="RESOURCE_GUIDANCE"),"please share",history)
        self.assertEqual(result.resolved_reference,"work stress content")
        self.assertFalse(result.needs_clarification)
    def test_short_followup_without_context_clarifies(self):
        result=resolve_conversation_reference(ConversationContext(intent="OUT_OF_SCOPE"),"please share",[])
        self.assertEqual(result.intent,"RESOURCE_GUIDANCE")
        self.assertTrue(result.needs_clarification)
    def test_typo_tolerant_direct_blissiree_content_request(self):
        result=apply_latest_message_authority(ConversationContext(),"too mch work today anything blissire can offer",[])
        self.assertEqual(result.intent,"RESOURCE_GUIDANCE")
        self.assertEqual(result.resolved_reference,"work stress content")
        self.assertFalse(result.needs_clarification)

class CapabilityRouterTests(unittest.TestCase):
    def route(self,intent,history=None,**kwargs):
        return route_capability(ConversationContext(intent=intent,confidence=.9),history or [],**kwargs)
    def test_platform_information_agent(self):self.assertEqual(self.route("PRODUCT_INFORMATION").active_agent,"PLATFORM_INFORMATION")
    def test_discussion_agent(self):self.assertEqual(self.route("COMPANION_SUPPORT").active_agent,"DISCUSSION")
    def test_content_matching_agent(self):self.assertEqual(self.route("RESOURCE_GUIDANCE").active_agent,"CONTENT_MATCHING")
    def test_booking_agent(self):self.assertEqual(self.route("CONSULTATION_BOOKING").active_agent,"BOOKING")
    def test_safety_overrides_every_capability(self):self.assertEqual(self.route("PRODUCT_INFORMATION",safety_override=True).active_agent,"SAFETY")
    def test_previous_agent_continues_as_safe_metadata(self):
        route=self.route("CONSULTATION_BOOKING",[{"role":"assistant","content":"...","active_agent":"DISCUSSION"}])
        self.assertEqual(public_agent(route),{"id":"BOOKING","label":"Booking","previous":"DISCUSSION"})
    def test_content_matching_must_fulfil_accepted_offer(self):
        failures=recommendation_fulfilment_failures("I can share some options.",["Stress and Tension Management Collection"],"RECOMMENDATION")
        self.assertIn("missing_eligible_recommendation_title",failures)
        self.assertEqual(recommendation_fulfilment_failures("Try the Stress and Tension Management Collection.",["Stress and Tension Management Collection"],"RECOMMENDATION"),[])
    def test_natural_platform_language_routes_to_overview(self):
        context=fallback_context("I am interested in knowing about platform",[])
        self.assertEqual(context.intent,"PRODUCT_INFORMATION");self.assertEqual(context.active_topic,"BLISSIREE_OVERVIEW")
    def test_program_followup_uses_prior_product_context(self):
        history=[{"role":"user","content":"what blissiree is"},{"role":"assistant","content":"Blissiree is a platform"}]
        context=fallback_context("what are the programs",history)
        self.assertEqual(context.active_topic,"BLISSIREE_PROGRAMS")
    def test_emotional_support_is_product_followup_in_reported_thread(self):
        history=[{"role":"user","content":"what blissiree is"},{"role":"assistant","content":"Blissiree is a platform"},
                 {"role":"user","content":"what are the programs"},{"role":"assistant","content":"Blissiree offers programs"}]
        context=fallback_context("emotional support",history)
        self.assertEqual(context.intent,"PRODUCT_INFORMATION");self.assertIn("offering",context.question_to_answer)
    def test_indirect_curiosity_opening_fails_information_quality(self):
        context=ConversationContext(intent="PRODUCT_INFORMATION",active_topic="BLISSIREE_OVERVIEW")
        self.assertIn("indirect_information_opening",information_quality_failures("It sounds like you're curious about Blissiree.",context))
    def test_vague_platform_answer_fails_information_quality(self):
        context=ConversationContext(intent="PRODUCT_INFORMATION",active_topic="BLISSIREE_OVERVIEW",current_explicit_themes=["LOW_CONFIDENCE"])
        failures=information_quality_failures("Blissiree offers resources for low confidence.",context)
        self.assertIn("missing_platform_answer",failures)
    def test_short_answer_is_reconciled_with_pending_program_question(self):
        context=ConversationContext(intent="COMPANION_SUPPORT",active_topic="USER_SITUATION",question_to_answer="What support does the user need?")
        history=[{"role":"assistant","content":"Blissiree offers Emotional Empowerment and Unstoppable You. Which program would you like explained?"}]
        result=reconcile_context(context,"emotional support",history)
        self.assertEqual(result.intent,"PRODUCT_INFORMATION");self.assertEqual(result.active_topic,"BLISSIREE_PROGRAMS")

class PersonaContractTests(unittest.TestCase):
    def test_terri_persona_contract_applies_to_both_personas(self):
        self.assertIn("trauma-aware"," ".join(persona_requirements("emma")))
        self.assertIn("grounded"," ".join(persona_requirements("ben")))
    def test_generic_it_sounds_like_opening_is_rejected(self):
        failures=persona_quality_failures("It sounds like you're feeling sad.","emma",[],"I am sad","SUPPORT")
        self.assertIn("generic_or_mechanical_opening",failures)
    def test_stacked_dramatic_language_is_rejected(self):
        text="That was a truly terrifying and deeply traumatic event."
        self.assertIn("stacked_emotional_intensifiers",persona_quality_failures(text,"emma",[],"My cat died","SUPPORT"))
    def test_unstated_colour_is_rejected(self):
        failures=persona_quality_failures("The memory of her white fur is close.","emma",[],"My cat died in an accident","SUPPORT")
        self.assertIn("invented_thread_detail",failures)
    def test_stated_colour_is_allowed(self):
        failures=persona_quality_failures("The memory of her white fur is close.","emma",[{"role":"user","content":"Her colour was white"}],"I miss her","SUPPORT")
        self.assertNotIn("invented_thread_detail",failures)

class ConsultationBookingTests(unittest.TestCase):
    def test_direct_free_consultation_booking_is_routed(self):
        intent=route_top_level_intent("I want to book a free consultation with Terri",[])
        self.assertEqual(intent.kind,"CONSULTATION_BOOKING")
        self.assertEqual(intent.service,"FREE_CONSULTATION")

    def test_introductory_session_is_identified(self):
        intent=route_top_level_intent("Can I schedule the $79 introductory session?",[])
        self.assertEqual(intent.service,"INTRODUCTORY_SESSION")

    def test_general_companion_message_is_not_booking(self):
        self.assertEqual(route_top_level_intent("I want to talk about a difficult day",[]).kind,"COMPANION_OR_INFORMATION")

    def test_information_question_is_not_forced_into_booking(self):
        self.assertEqual(route_top_level_intent("What consultations does Blissiree offer?",[]).kind,"COMPANION_OR_INFORMATION")

    def test_booking_response_uses_only_official_portal(self):
        response=consultation_booking_response("PERSONALISED_PROGRAM")
        self.assertIn("14-session",response)
        self.assertIn(BOOKING_URL,response)


class TrainingKnowledgeTests(unittest.TestCase):
    def test_active_case_study_is_retrievable(self):
        items=[{"id":"youtube-test","title":"Feeling calmer after stress","instruction":"A participant described stress and finding calm through a gentle pause.","status":"ACTIVE","kind":"KNOWLEDGE","source":"YOUTUBE_PUBLIC","authority":70}]
        rows=rank_training_knowledge(items,"I feel stress and want calm")
        self.assertEqual(rows[0]["id"],"youtube-test")

    def test_inactive_case_study_is_not_retrievable(self):
        items=[{"id":"youtube-test","title":"Stress story","instruction":"A participant described stress.","status":"DISABLED","kind":"KNOWLEDGE","source":"YOUTUBE_PUBLIC","authority":70}]
        self.assertEqual(rank_training_knowledge(items,"stress"),[])

    def test_persona_specific_knowledge_does_not_cross_personas(self):
        items=[{"id":"emma-only","title":"Exhaustion","instruction":"Emotionally exhausted and depleted.","target":"EMMA","status":"ACTIVE","kind":"KNOWLEDGE"}]
        self.assertEqual(rank_training_knowledge(items,"emotionally exhausted",target="BEN"),[])
        self.assertEqual(rank_training_knowledge(items,"emotionally exhausted",target="EMMA")[0]["id"],"emma-only")

if __name__=="__main__": unittest.main()
