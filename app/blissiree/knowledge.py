import json
import re
from pathlib import Path

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
