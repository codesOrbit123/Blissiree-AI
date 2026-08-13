import json,os,threading,uuid
from datetime import datetime,timezone
from google.cloud import storage

BUCKET=os.getenv("TRAINING_STORE_BUCKET","");OBJECT="conversation-review/issues.json"
class ConversationIssueStore:
    def __init__(self):self.lock=threading.Lock();self.client=storage.Client() if BUCKET else None;self._rows=None
    def load(self):
        if self._rows is not None:return self._rows
        if not self.client:self._rows=[];return self._rows
        blob=self.client.bucket(BUCKET).blob(OBJECT);self._rows=json.loads(blob.download_as_text()) if blob.exists() else [];return self._rows
    def save(self):
        if self.client:self.client.bucket(BUCKET).blob(OBJECT).upload_from_string(json.dumps(self._rows,separators=(",",":")),content_type="application/json")
    def create(self,persona,conversation_id,thread,description,actor):
        with self.lock:
            row={"id":str(uuid.uuid4()),"status":"OPEN","created_at":datetime.now(timezone.utc).isoformat(),"reported_by":actor,"persona":persona,"conversation_id":conversation_id,"description":description.strip(),"thread":thread}
            self.load().append(row);self.save();return row
    def list(self):return list(reversed(self.load()))
