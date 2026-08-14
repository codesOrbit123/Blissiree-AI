import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app"))

from blissiree.admin_coach import AdminAICoach
from blissiree.knowledge import KnowledgeRepository
from blissiree.schemas import CoachProposal,CoachResponse

class FakeProvider:
    def __init__(self):self.payload=None
    def coach(self,payload):
        self.payload=payload
        return CoachResponse(message="I found the context.",proposal=CoachProposal(title="Natural acceptance",instruction="Acknowledge accepted recommendations without restarting discovery.",target="ALL",category="CONVERSATION",why_it_exists="Preserves continuity.",regression_tests=["checking it ends without a question"])),{}

class FakeTraining:
    def load(self):return {"items":[{"id":"p1","title":"Conversation continuity","instruction":"Continue from the latest user action.","target":"ALL","category":"CONVERSATION","priority":"HIGH","source":"TERRI","protected":False,"kind":"INSTRUCTION","status":"ACTIVE","authority":95}]}

class FakeIssues:
    def load(self):return [{"id":"i1","description":"Reply restarted discovery","thread":[{"role":"user","content":"checking it"}]}]

class AdminCoachTests(unittest.TestCase):
    def test_selective_summaries_are_loaded_alongside_exact_records(self):
        repo=KnowledgeRepository(ROOT/"knowledge")
        self.assertTrue(any(x.get("summary") for x in repo.documents))
        self.assertTrue(any(not x.get("summary") for x in repo.documents))

    def test_coach_receives_issue_prompts_and_broad_knowledge(self):
        provider=FakeProvider();repo=KnowledgeRepository(ROOT/"knowledge")
        coach=AdminAICoach(provider,repo,FakeTraining(),FakeIssues())
        result=coach.respond("Fix this conversation",[],"i1")
        self.assertEqual(result.proposal.target,"ALL")
        self.assertEqual(provider.payload["selected_reported_issue"]["id"],"i1")
        self.assertTrue(provider.payload["relevant_prompt_records"])
        self.assertTrue(provider.payload["relevant_large_source_summaries_and_exact_records"])

    def test_summary_policy_does_not_summarise_short_core_prompts(self):
        data=json.loads((ROOT/"knowledge/sources/large_source_summaries.json").read_text())
        self.assertIn("concise rules",data["policy"])
        self.assertFalse(any("persona" in x["id"] for x in data["summaries"]))

if __name__=="__main__":unittest.main()
