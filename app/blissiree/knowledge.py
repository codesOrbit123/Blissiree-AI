import json
import re
from pathlib import Path

def rank_training_knowledge(rows,query,limit=3,target=None):
    terms=set(re.findall(r"[a-z]{4,}",query.lower()))
    if not terms:return []
    scored=[]
    for row in rows:
        if row.get("status")!="ACTIVE" or row.get("kind")!="KNOWLEDGE":continue
        if target and row.get("target","ALL") not in {"ALL",target}:continue
        text=(row.get("title","")+" "+row.get("instruction","")).lower()
        score=len(terms & set(re.findall(r"[a-z]{4,}",text)))
        if score:scored.append((score,row))
    scored.sort(key=lambda pair:(pair[0],pair[1].get("authority",0)),reverse=True)
    return [{"id":row["id"],"source":row.get("source","TRAINING_STUDIO"),"authority":row.get("authority",70),"text":row.get("instruction","")[:8000]} for _,row in scored[:limit]]

class KnowledgeRepository:
    def __init__(self, root: Path):
        self.documents = []
        self.catalog = json.loads((root / "catalog/content.json").read_text())
        for filename, authority in [("terri_architecture.json",100),("terri_training_manual_part1.json",95)]:
            data = json.loads((root / "sources" / filename).read_text())
            for block in data["blocks"]:
                if block["type"] == "paragraph" and block["text"].strip():
                    self.documents.append({"id":f"{filename}:{block['index']}","source":filename,"authority":authority,"text":block["text"]})
        for program in self.catalog["programs"]:
            for kind in ("sessions","habits","fundamentals","maintenance","life_lessons"):
                for item in program.get(kind,[]):
                    self.documents.append({"id":f"{program['id']}:{kind}:{item.get('order','')}","source":program["source"],"authority":85,
                                           "text":f"{program['id']} {kind} {item.get('order','')}: {item['source_title']}"})
        for collection in self.catalog["boost_collections"]:
            self.documents.append({"id":collection["id"],"source":collection["source"],"authority":80,
                                   "text":f"Current Boost collection: {collection['display_name']}. Legacy name: {collection['legacy_name']}."})
        workbook_training = root / "sources" / "terri_exhaustion_training.json"
        if workbook_training.exists():
            data=json.loads(workbook_training.read_text())
            for record in data.get("records",[]):
                exemplar=record.get("active_companion_training",{})
                if not exemplar:continue
                parts=[
                    f"Terri companion exemplar {exemplar.get('record_id')}: {exemplar.get('topic','')}",
                    "User language: "+" | ".join(exemplar.get("user_language",[])),
                    "Emotional context: "+" | ".join(exemplar.get("reported_emotional_context",[])),
                    "Personalisation signals: "+"; ".join(exemplar.get("personalization_signals",[])),
                    "Safe opening examples: "+" | ".join(exemplar.get("safe_empathy_openings",[])),
                    "Useful follow-up areas: "+" | ".join(exemplar.get("safe_follow_up_prompts",[])),
                    "Must avoid: "+"; ".join(exemplar.get("must_avoid",[])),
                    exemplar.get("recommendation_boundary",""),exemplar.get("medical_boundary","")]
                self.documents.append({"id":f"terri-workbook:{record.get('id')}","source":"TERRI_WORKBOOK",
                                       "authority":95,"text":"\n".join(x for x in parts if x)})

    def retrieve(self, query: str, limit: int = 10) -> list[dict]:
        terms = set(re.findall(r"[a-z]{4,}", query.lower()))
        scored=[]
        for doc in self.documents:
            overlap=len(terms & set(re.findall(r"[a-z]{4,}",doc["text"].lower())))
            if overlap:
                scored.append((overlap*10+doc["authority"]/100,doc))
        scored.sort(key=lambda x:(x[0],x[1]["authority"]),reverse=True)
        return [doc for _,doc in scored[:limit]]

    def approved_boosts(self) -> list[dict]:
        return [b for b in self.catalog["boosts"] if b.get("approved_for_ai_recommendation")]

    def collection(self, collection_id: str) -> dict | None:
        return next((c for c in self.catalog["boost_collections"] if c["id"] == collection_id), None)

    def programs(self) -> list[dict]:
        return self.catalog["programs"]
