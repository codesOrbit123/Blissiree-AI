import re
from .schemas import CoachResponse

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

    def respond(self,message:str,history:list[dict],issue_id:str|None=None) -> CoachResponse:
        issue=self._issue(issue_id)
        issue_text=" ".join(str(x.get("content","")) for x in (issue or {}).get("thread",[]))
        query=" ".join((message,issue_text,(issue or {}).get("description","")))
        knowledge=self.repo.retrieve_broad(query,24)
        prompts=self._prompts(query,18)
        payload={"latest_admin_message":message,"recent_admin_conversation":history[-16:],"selected_reported_issue":issue,
                 "relevant_prompt_records":prompts,"relevant_large_source_summaries_and_exact_records":knowledge,
                 "available_categories":["PERSONA","CONVERSATION","SAFETY","BOUNDARY","RECOMMENDATION","BOOST","PROGRAM","KNOWLEDGE","MEMORY","TERMINOLOGY","OTHER"]}
        result,_=self.provider.coach(payload);return result
