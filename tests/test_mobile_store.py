import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "app"))

from blissiree.mobile_store import MobileConversationStore


class MobileConversationStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = MobileConversationStore()
        self.store.client = None

    def test_sync_is_idempotent_and_creates_separate_persona_threads(self):
        first, created = self.store.sync("app-user-1", "Sarah")
        second, created_again = self.store.sync("app-user-1", "Sarah Updated")
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first["id"], second["id"])
        self.assertNotEqual(second["threads"]["emma"]["id"], second["threads"]["ben"]["id"])

    def test_context_contains_summary_and_latest_ten_complete_exchanges(self):
        self.store.sync("app-user-2")
        for number in range(12):
            self.store.append("app-user-2", "emma", f"user {number}", f"emma {number}", f"client-{number}")
        self.store.save_summary("app-user-2", "emma", "Long-term Emma context", 2)
        _, summary, history = self.store.context("app-user-2", "emma")
        self.assertEqual(summary, "Long-term Emma context")
        self.assertEqual(len(history), 20)
        self.assertEqual(history[0]["content"], "user 2")
        self.assertEqual(history[-1]["content"], "emma 11")

    def test_persona_history_is_isolated(self):
        self.store.sync("app-user-3")
        self.store.append("app-user-3", "emma", "Emma only", "Emma reply", "emma-1")
        _, _, ben_history = self.store.context("app-user-3", "ben")
        self.assertEqual(ben_history, [])

    def test_duplicate_client_message_is_not_stored_twice(self):
        self.store.sync("app-user-4")
        first = self.store.append("app-user-4", "emma", "Hello", "Hi", "same-id")
        second = self.store.append("app-user-4", "emma", "Hello", "Different", "same-id")
        self.assertEqual(first["id"], second["id"])
        _, _, history = self.store.context("app-user-4", "emma")
        self.assertEqual(len(history), 2)

    def test_delete_removes_all_persona_data(self):
        self.store.sync("app-user-5")
        self.store.append("app-user-5", "emma", "One", "Two", "m1")
        self.store.append("app-user-5", "ben", "Three", "Four", "m2")
        self.assertTrue(self.store.delete("app-user-5"))
        with self.assertRaises(KeyError):
            self.store.context("app-user-5", "emma")


if __name__ == "__main__":
    unittest.main()
