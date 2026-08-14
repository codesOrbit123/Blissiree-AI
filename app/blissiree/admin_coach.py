import base64
import io
import json
import os
import re
import threading
import zipfile
from datetime import datetime,timezone
from xml.etree import ElementTree
try:from google.cloud import storage
except ImportError:storage=None
from .schemas import CoachResponse

BUCKET=os.getenv("TRAINING_STORE_BUCKET","")
THREAD_OBJECT="admin-coach/thread.json"
ALLOWED={"image/png","image/jpeg","image/webp","application/pdf","text/plain","text/markdown","text/csv","application/json",
         "application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

class AdminCoachThreadStore:
    def __init__(self):self.lock=threading.Lock();self.client=storage.Client() if BUCKET and storage else None;self._messages=None
    def load(self):
        if self._messages is not None:return self._messages
        if not self.client:self._messages=[];return self._messages
        blob=self.client.bucket(BUCKET).blob(THREAD_OBJECT)
        self._messages=json.loads(blob.download_as_text()) if blob.exists() else []
        return self._messages
    def save(self):
        if self.client:self.client.bucket(BUCKET).blob(THREAD_OBJECT).upload_from_string(json.dumps(self._messages,separators=(",",":")),content_type="application/json")
    def append_exchange(self,message,result,attachments):
        with self.lock:
            now=datetime.now(timezone.utc).isoformat();rows=self.load()
            rows.append({"role":"user","content":message,"attachments":[{"name":x["name"],"mime_type":x["mime_type"]} for x in attachments],"created_at":now})
            rows.append({"role":"assistant","content":result.message,"proposal":result.proposal.model_dump() if result.proposal else None,"created_at":now})
            self._messages=rows[-100:];self.save();return self._messages
    def clear(self):
        with self.lock:self._messages=[];self.save()

def _xml_text(raw):
    root=ElementTree.fromstring(raw);return " ".join(x.text for x in root.iter() if x.text)

def decode_attachments(attachments):
    textual=[];media=[]
    for item in attachments[:5]:
        name=str(item.get("name","attachment"))[:160];mime=str(item.get("mime_type",""));encoded=str(item.get("data_base64",""))
        if mime not in ALLOWED:raise ValueError(f"Unsupported attachment type: {mime or name}")
        raw=base64.b64decode(encoded,validate=True)
        if len(raw)>10*1024*1024:raise ValueError(f"{name} is larger than 10 MB")
        if mime.startswith("image/") or mime=="application/pdf":media.append({"name":name,"mime_type":mime,"data":raw})
        elif mime=="application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            with zipfile.ZipFile(io.BytesIO(raw)) as z:textual.append({"name":name,"text":_xml_text(z.read("word/document.xml"))[:50000]})
        elif mime=="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                parts=[]
                for filename in z.namelist():
                    if filename=="xl/sharedStrings.xml" or filename.startswith("xl/worksheets/sheet"):
                        try:parts.append(_xml_text(z.read(filename)))
                        except Exception:pass
                textual.append({"name":name,"text":"\n".join(parts)[:50000]})
        else:textual.append({"name":name,"text":raw.decode("utf-8",errors="replace")[:50000]})
    return textual,media

class AdminAICoach:
    def __init__(self,provider,repository,training_store,issue_store):
        self.provider=provider;self.repo=repository;self.training=training_store;self.issues=issue_store

    def _issue(self,issue_id):
        return next((x for x in self.issues.load() if x.get("id")==issue_id),None) if issue_id else None

    def _prompts(self,query,limit=18):
        terms=set(re.findall(r"[a-z]{4,}",query.lower()));scored=[]
        for row in self.training.load().get("items",[]):
            if row.get("status")!="ACTIVE":continue
            text=(row.get("title","")+" "+row.get("instruction","")).lower()
            score=len(terms & set(re.findall(r"[a-z]{4,}",text)))
            if score:scored.append((score,row.get("authority",0),row))
        scored.sort(key=lambda x:(x[0],x[1]),reverse=True)
        return [{k:r.get(k) for k in ("id","title","instruction","target","category","priority","source","protected","kind")}
                for _,_,r in scored[:limit]]

    def respond(self,message:str,history:list[dict],issue_id:str|None=None,attachments:list[dict]|None=None) -> CoachResponse:
        attachments=attachments or [];textual,media=decode_attachments(attachments)
        combined="\n".join([str(x.get("content","")) for x in history[-10:] if x.get("role")=="user"]+[message])
        problem=bool(re.search(r"\b(issue|problem|wrong|fix|repeated|repeating|context|reply|response|conversation|emma|ben)\b",message,re.I))
        pasted=(bool(re.search(r"(?im)^\s*(user|emma|ben|assistant)\s*:",combined)) and len(combined.splitlines())>=3) or bool(issue_id)
        if problem and not pasted and not attachments:
            return CoachResponse(message="Please copy and paste the complete conversation where you saw the issue, including the user’s messages and every Emma or Ben reply. Then add a short note explaining what felt wrong and how you would prefer the AI to respond.")
        issue=self._issue(issue_id)
        issue_text=" ".join(str(x.get("content","")) for x in (issue or {}).get("thread",[]))
        query=" ".join((message,issue_text,(issue or {}).get("description","")))
        knowledge=self.repo.retrieve_broad(query,24)
        prompts=self._prompts(query,18)
        payload={"latest_admin_message":message,"recent_admin_conversation":history[-16:],"selected_reported_issue":issue,
                 "relevant_prompt_records":prompts,"relevant_large_source_summaries_and_exact_records":knowledge,
                 "uploaded_documents":textual,"uploaded_media_names":[{"name":x["name"],"mime_type":x["mime_type"]} for x in media],
                 "available_categories":["PERSONA","CONVERSATION","SAFETY","BOUNDARY","RECOMMENDATION","BOOST","PROGRAM","KNOWLEDGE","MEMORY","TERMINOLOGY","OTHER"]}
        result,_=self.provider.coach(payload,media);return result
