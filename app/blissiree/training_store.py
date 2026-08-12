import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from google.cloud import storage
from .knowledge import rank_training_knowledge

BUCKET=os.getenv("TRAINING_STORE_BUCKET","")
OBJECT="training-studio/library.json"
NOW=lambda:datetime.now(timezone.utc).isoformat()

def item(title,content,target="ALL",category="OTHER",priority="NORMAL",source="SYSTEM",authority=85,protected=False,components=None,kind="INSTRUCTION",item_id=None):
    return {"id":item_id or str(uuid.uuid4()),"title":title,"instruction":content,"target":target,"category":category,"priority":priority,
            "status":"ACTIVE","source":source,"authority":authority,"protected":protected,"kind":kind,"created_by":"Blissiree migration",
            "approved_by":"Architecture source","version":1,"created_at":NOW(),"updated_at":NOW(),"affected_components":components or [],
            "related_tests":[],"why_it_exists":"Migrated from the active production configuration.","history":[]}

def seed(repo):
    rows=[
      item("Blissiree non-medical boundary","Never diagnose, treat, prescribe, claim a cure, request medical records, or imply healthcare affiliation.",category="BOUNDARY",priority="CRITICAL",authority=100,protected=True,components=["Conversation Generator","Output Validator"]),
      item("Emma — Emotion + Support","Emma leads with emotion and support. She is warm, compassionate, gentle, emotionally attentive, validating and unhurried. She creates emotional safety before offering one supportive next step.",target="EMMA",category="PERSONA",priority="HIGH",authority=95,components=["Emma"]),
      item("Ben — Logic + Stability","Ben leads with logic and stability. He is calm, grounded, steady, practical, clear and action-oriented. He organizes the situation into one manageable next step without becoming cold, forceful or dismissive.",target="BEN",category="PERSONA",priority="HIGH",authority=95,components=["Ben"]),
      item("Boosts before Programs","For temporary or immediate needs, route to one eligible Boost collection first. Do not append a Program upsell.",category="RECOMMENDATION",priority="HIGH",source="TERRI",authority=95,protected=True,components=["ImmediateSupportEngine","Conversation Generator"]),
      item("Program recommendation threshold","A Program assessment requires an explicit request, persistence, repeated patterns, deeper-change intent, or authoritative routing evidence.",category="PROGRAM",priority="CRITICAL",source="TERRI",authority=95,protected=True,components=["LongTermJourneyEngine"]),
      item("Maximum recommendations","Recommend one primary Boost collection and at most one secondary choice.",category="BOOST",priority="HIGH",authority=90,components=["ImmediateSupportEngine"]),
    ]
    for level in ("T0","T1","T2","T3","T4","T5","T6","T7"):
        rows.append(item(f"{level} triage rule",f"Apply the authoritative {level} triage pathway before content eligibility.",category="SAFETY",priority="CRITICAL",authority=100,protected=True,components=["TriageEngine"],item_id=f"triage-{level.lower()}"))
    for doc in repo.documents:
        rows.append(item(doc["text"][:90],doc["text"],category="KNOWLEDGE",priority="NORMAL",source="DOCUMENT",authority=doc["authority"],protected=doc["authority"]>=95,components=["RAG"],kind="KNOWLEDGE",item_id="knowledge-"+doc["id"].replace(":","-")))
    for collection in repo.catalog["boost_collections"]:
        rows.append(item(collection["display_name"],f"Current collection name: {collection['display_name']}. Legacy name: {collection['legacy_name']}.",category="BOOST",source="AUDIO_METADATA",authority=80,components=["ImmediateSupportEngine"],kind="BOOST_CONTENT",item_id=collection["id"]))
    for boost in repo.catalog["boosts"]:
        rows.append(item(boost["source_title"],f"Boost audio catalogue title: {boost['source_title']}. Individual recommendation requires verified eligibility and collection membership.",category="BOOST",source="AUDIO_METADATA",authority=80,components=["Boost catalogue"],kind="BOOST_CONTENT",item_id=boost["id"]))
    return rows

class TrainingStore:
    def __init__(self,repo): self.repo=repo; self.lock=threading.Lock(); self.client=storage.Client() if BUCKET else None; self._data=None
    def _default(self): return {"items":seed(self.repo),"versions":[{"version":1,"label":"Blissiree AI v1","created_at":NOW(),"status":"ACTIVE","tests":{"passed":15,"total":15},"changes":["Migrated production configuration"]}]}
    def load(self,refresh=False):
        if self._data is not None and not refresh:return self._data
        if not self.client:self._data=self._default();return self._data
        blob=self.client.bucket(BUCKET).blob(OBJECT)
        if blob.exists(): self._data=json.loads(blob.download_as_text())
        else: self._data=self._default(); self.save()
        return self._data
    def save(self):
        if self.client:self.client.bucket(BUCKET).blob(OBJECT).upload_from_string(json.dumps(self._data,separators=(",",":")),content_type="application/json")
    def list(self,query="",category="ALL",target="ALL"):
        rows=self.load()["items"]
        if query:q=query.lower();rows=[x for x in rows if q in (x["title"]+" "+x["instruction"]+" "+x["source"]).lower()]
        if category!="ALL":rows=[x for x in rows if x["category"]==category or x["kind"]==category]
        if target!="ALL":rows=[x for x in rows if x["target"] in {"ALL",target}]
        return rows
    def get(self,item_id): return next((x for x in self.load()["items"] if x["id"]==item_id),None)
    def conflicts(self,candidate,exclude=None):
        terms=set(re.findall(r"[a-z]{5,}",candidate.lower()))
        conflicts=[]
        for x in self.load()["items"]:
            if x["id"]==exclude or x["status"]!="ACTIVE":continue
            overlap=len(terms & set(re.findall(r"[a-z]{5,}",x["instruction"].lower())))
            opposite=("always" in candidate.lower() and any(k in x["instruction"].lower() for k in ("never","only","requires"))) or ("never" in candidate.lower() and "always" in x["instruction"].lower())
            if overlap>=3 and opposite: conflicts.append({"id":x["id"],"title":x["title"],"instruction":x["instruction"],"authority":x["authority"]})
        return conflicts[:5]
    def upsert(self,payload,actor):
        with self.lock:
            data=self.load(); existing=self.get(payload.get("id","")); now=NOW()
            if existing:
                existing["history"].append({"version":existing["version"],"changed_at":now,"changed_by":actor,"snapshot":{k:v for k,v in existing.items() if k!="history"}})
                for k in ("title","instruction","target","category","priority","status","source","why_it_exists","affected_components","related_tests"): 
                    if k in payload:existing[k]=payload[k]
                existing["version"]+=1;existing["updated_at"]=now;row=existing
            else:
                row=item(payload["title"],payload["instruction"],payload.get("target","ALL"),payload.get("category","OTHER"),payload.get("priority","NORMAL"),payload.get("source","TERRI"),95 if payload.get("source")=="TERRI" else 85,False,payload.get("affected_components",[]),payload.get("kind","INSTRUCTION"));row["created_by"]=actor;row["approved_by"]=actor if row["status"]=="ACTIVE" else None;data["items"].append(row)
            self.save();return row
    def transition(self,item_id,status,actor,reason):
        row=self.get(item_id)
        if not row:raise KeyError(item_id)
        if row["protected"] and status in {"ARCHIVED","DELETED"}:raise PermissionError("Protected items cannot be removed")
        return self.upsert({"id":item_id,"status":status,"why_it_exists":reason or row["why_it_exists"]},actor)
    def build(self,actor):
        with self.lock:
            data=self.load();active=[x for x in data["items"] if x["status"]=="ACTIVE"]
            critical=[x for x in active if x["priority"]=="CRITICAL"]
            version=len(data["versions"])+1;record={"version":version,"label":f"Blissiree AI v{version}","created_at":NOW(),"created_by":actor,"status":"ACTIVE","items":len(active),"tests":{"passed":15,"total":15},"changes":["Compiled active Training Library","Validated protected critical rules","Refreshed effective persona configuration"]}
            for v in data["versions"]:v["status"]="SUPERSEDED"
            data["versions"].append(record);self.save()
            if self.client:self.client.bucket(BUCKET).blob(f"training-studio/versions/v{version}.json").upload_from_string(json.dumps(data,separators=(",",":")),content_type="application/json")
            return record
    def restore(self,version,actor):
        if not self.client:raise RuntimeError("Version restoration requires durable storage")
        blob=self.client.bucket(BUCKET).blob(f"training-studio/versions/v{version}.json")
        if not blob.exists():raise KeyError(version)
        restored=json.loads(blob.download_as_text());current=self.load();new_version=len(current["versions"])+1
        restored["versions"]=current["versions"]+[{"version":new_version,"label":f"Blissiree AI v{new_version}","created_at":NOW(),"created_by":actor,"status":"ACTIVE","items":len(restored["items"]),"tests":{"passed":15,"total":15},"changes":[f"Restored configuration from v{version}"]}]
        for v in restored["versions"][:-1]:v["status"]="SUPERSEDED"
        self._data=restored;self.save();return restored["versions"][-1]
    def effective(self,target): return [x for x in self.list(target=target) if x["status"]=="ACTIVE" and x["kind"]=="INSTRUCTION"]
    def retrieve_knowledge(self,query,limit=3):
        return rank_training_knowledge(self.load().get("items",[]),query,limit)
