import sys
import unittest
import os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/"app"))
from blissiree.schemas import MentalStateAnalysis
from blissiree.safety import OutputSafetyValidator,TriageEngine,deterministic_crisis_response,terminal_turn_kind,terminal_turn_response
from blissiree.recommendations import SupportHorizonClassifier,ImmediateSupportEngine
from blissiree.knowledge import KnowledgeRepository,rank_training_knowledge

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
    def test_invented_collection_rejected(self): self.assertFalse(OutputSafetyValidator().validate("Try the Magical Healing Collection.",set())[0])
    def test_invented_program_rejected(self): self.assertFalse(OutputSafetyValidator().validate('We have a program called "Understanding Relationship Patterns".',set())[0])
    def test_internal_contract_leak_rejected(self): self.assertFalse(OutputSafetyValidator().validate("{'response_contract': {'persona': 'emma', 'compiled_instructions': []}}",set())[0])

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
