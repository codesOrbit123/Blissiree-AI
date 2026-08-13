import threading
import unittest
import sys
import types

google=types.ModuleType("google");cloud=types.ModuleType("google.cloud");storage=types.ModuleType("google.cloud.storage")
storage.Client=object;cloud.storage=storage;google.cloud=cloud
sys.modules.setdefault("google",google);sys.modules.setdefault("google.cloud",cloud);sys.modules.setdefault("google.cloud.storage",storage)
from blissiree.issue_store import ConversationIssueStore


class ConversationIssueStoreTests(unittest.TestCase):
    def setUp(self):
        self.store=ConversationIssueStore.__new__(ConversationIssueStore)
        self.store.lock=threading.Lock();self.store.client=None;self.store._rows=[]

    def test_create_preserves_complete_thread_and_terri_comment(self):
        thread=[{"role":"user","content":"I feel overwhelmed"},{"role":"assistant","content":"I’m here with you."}]
        row=self.store.create("emma","conversation-1",thread,"The reply needed more context.","Terri/Admin")
        self.assertEqual(row["thread"],thread)
        self.assertEqual(row["description"],"The reply needed more context.")
        self.assertEqual(row["conversation_id"],"conversation-1")
        self.assertEqual(row["status"],"OPEN")

    def test_report_can_move_through_review_lifecycle(self):
        row=self.store.create("ben","conversation-2",[{"role":"user","content":"Hello"}],"Tone issue","Terri/Admin")
        reviewed=self.store.update_status(row["id"],"REVIEWED","Terri/Admin")
        self.assertEqual(reviewed["status"],"REVIEWED")
        resolved=self.store.update_status(row["id"],"RESOLVED","Terri/Admin")
        self.assertEqual(resolved["status"],"RESOLVED")
        self.assertEqual(resolved["updated_by"],"Terri/Admin")


if __name__=="__main__":unittest.main()
