import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone, timedelta

from google.cloud import storage
from google.api_core.exceptions import PreconditionFailed


BUCKET = os.getenv("TRAINING_STORE_BUCKET", "")
PREFIX = "mobile-ai/users"
NOW = lambda: datetime.now(timezone.utc).isoformat()


def _key(external_user_id: str) -> str:
    return hashlib.sha256(external_user_id.strip().encode()).hexdigest()


class MobileConversationStore:
    """Small durable store for the first mobile integration.

    Records are isolated by a one-way user key. Firestore can replace this class
    later without changing the public API.
    """

    def __init__(self):
        self.client = storage.Client() if BUCKET else None
        self.lock = threading.RLock()
        self._local: dict[str, dict] = {}

    def _object(self, external_user_id: str) -> str:
        return f"{PREFIX}/{_key(external_user_id)}.json"

    def _load_state(self, external_user_id: str) -> tuple[dict | None, int | None]:
        name = self._object(external_user_id)
        if not self.client:
            return self._local.get(name), None
        blob = self.client.bucket(BUCKET).blob(name)
        if not blob.exists():
            return None, 0
        text = blob.download_as_text()
        return json.loads(text), blob.generation

    def _load(self, external_user_id: str) -> dict | None:
        return self._load_state(external_user_id)[0]

    def _save(self, external_user_id: str, record: dict, generation: int | None = None) -> None:
        name = self._object(external_user_id)
        if not self.client:
            self._local[name] = record
            return
        self.client.bucket(BUCKET).blob(name).upload_from_string(
            json.dumps(record, separators=(",", ":")), content_type="application/json",
            if_generation_match=generation,
        )

    def sync(self, external_user_id: str, display_name: str = "", email: str | None = None,
             phone: str | None = None) -> tuple[dict, bool]:
        with self.lock:
            for _ in range(4):
                record, generation = self._load_state(external_user_id)
                created = record is None
                if created:
                    record = {
                        "id": str(uuid.uuid4()), "external_user_id": external_user_id.strip(),
                        "created_at": NOW(), "updated_at": NOW(), "profile": {},
                        "threads": {p: self._new_thread(p) for p in ("emma", "ben")},
                    }
                record["profile"].update({
                    "display_name": display_name.strip(),
                    "email": email.strip().lower() if email else None,
                    "phone": phone.strip() if phone else None,
                })
                record["updated_at"] = NOW()
                try:
                    self._save(external_user_id, record, generation)
                    return record, created
                except PreconditionFailed:
                    continue
            raise RuntimeError("Concurrent user update could not be saved")

    @staticmethod
    def _new_thread(persona: str) -> dict:
        return {
            "id": str(uuid.uuid4()), "persona": persona, "summary": "",
            "summary_updated_at": None, "summarized_exchange_count": 0,
            "exchanges": [], "updated_at": NOW(),
        }

    def context(self, external_user_id: str, persona: str) -> tuple[dict, str, list[dict]]:
        with self.lock:
            record = self._load(external_user_id)
            if not record:
                raise KeyError(external_user_id)
            thread = record["threads"][persona]
            history = []
            for exchange in thread["exchanges"][-10:]:
                history.extend((
                    {"role": "user", "content": exchange["user"]},
                    {"role": "assistant", "content": exchange["assistant"]},
                ))
            return record, thread.get("summary", ""), history

    def append(self, external_user_id: str, persona: str, user_message: str,
               assistant_message: str, client_message_id: str) -> dict:
        with self.lock:
            for _ in range(4):
                record, generation = self._load_state(external_user_id)
                if not record:
                    raise KeyError(external_user_id)
                thread = record["threads"][persona]
                duplicate = next((x for x in thread["exchanges"] if x["client_message_id"] == client_message_id), None)
                if duplicate:
                    return duplicate
                exchange = {"id": str(uuid.uuid4()), "client_message_id": client_message_id,
                            "user": user_message, "assistant": assistant_message, "created_at": NOW()}
                thread["exchanges"].append(exchange)
                thread["updated_at"] = record["updated_at"] = NOW()
                try:
                    self._save(external_user_id, record, generation)
                    return exchange
                except PreconditionFailed:
                    continue
            raise RuntimeError("Concurrent conversation update could not be saved")

    def summary_due(self, external_user_id: str, persona: str) -> bool:
        record = self._load(external_user_id)
        if not record:
            return False
        thread = record["threads"][persona]
        unsummarized = len(thread["exchanges"]) - int(thread.get("summarized_exchange_count", 0))
        updated = thread.get("summary_updated_at")
        weekly = not updated or datetime.fromisoformat(updated) <= datetime.now(timezone.utc) - timedelta(days=7)
        return unsummarized > 0 and (weekly or unsummarized >= 8)

    def summary_input(self, external_user_id: str, persona: str) -> tuple[str, list[dict], int]:
        record = self._load(external_user_id)
        if not record:
            raise KeyError(external_user_id)
        thread = record["threads"][persona]
        start = int(thread.get("summarized_exchange_count", 0))
        return thread.get("summary", ""), thread["exchanges"][start:], len(thread["exchanges"])

    def save_summary(self, external_user_id: str, persona: str, summary: str, through_count: int) -> None:
        with self.lock:
            for _ in range(4):
                record, generation = self._load_state(external_user_id)
                if not record:
                    return
                thread = record["threads"][persona]
                thread["summary"] = summary[:6000]
                thread["summary_updated_at"] = NOW()
                thread["summarized_exchange_count"] = max(int(thread.get("summarized_exchange_count", 0)), through_count)
                try:
                    self._save(external_user_id, record, generation)
                    return
                except PreconditionFailed:
                    continue
            raise RuntimeError("Concurrent summary update could not be saved")

    def delete(self, external_user_id: str) -> bool:
        with self.lock:
            name = self._object(external_user_id)
            if not self.client:
                return self._local.pop(name, None) is not None
            blob = self.client.bucket(BUCKET).blob(name)
            if not blob.exists():
                return False
            blob.delete()
            return True
