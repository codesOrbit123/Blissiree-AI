import json
import hmac
import base64
import hashlib
import time
import logging
import os
from pathlib import Path
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import FileResponse, StreamingResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from blissiree.config import settings
from blissiree.knowledge import KnowledgeRepository
from blissiree.orchestrator import BlissireeOrchestrator
from blissiree.providers import GeminiProvider
from blissiree.training_store import TrainingStore
from blissiree.issue_store import ConversationIssueStore
from blissiree.admin_coach import AdminAICoach

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"),format="%(message)s")
ROOT=Path(__file__).parent
provider=GeminiProvider(settings)
repository=KnowledgeRepository(ROOT/"knowledge")
training_store=TrainingStore(repository)
issue_store=ConversationIssueStore()
orchestrator=BlissireeOrchestrator(settings,provider,repository,training_store)
admin_coach=AdminAICoach(provider,repository,training_store,issue_store)
app=FastAPI()
app.mount("/assets",StaticFiles(directory=ROOT/"assets"),name="assets")

PUBLIC_PATHS={"/login","/api/auth/login","/health","/sw.js"}
def session_token(username:str) -> str:
    payload=f"{username}:{int(time.time())+43200}"
    encoded=base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    signature=hmac.new(os.environ["SESSION_SIGNING_KEY"].encode(),encoded.encode(),hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"

def valid_session(token:str|None) -> bool:
    if not token or "." not in token:return False
    encoded,signature=token.rsplit(".",1)
    expected=hmac.new(os.environ["SESSION_SIGNING_KEY"].encode(),encoded.encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,signature):return False
    try:
        payload=base64.urlsafe_b64decode(encoded+"="*(-len(encoded)%4)).decode();username,expires=payload.rsplit(":",1)
        return hmac.compare_digest(username,os.environ["APP_USERNAME"]) and int(expires)>int(time.time())
    except Exception:return False

@app.middleware("http")
async def protect_app(request:Request,call_next):
    path=request.url.path
    if path in PUBLIC_PATHS or path.startswith("/assets/"):return await call_next(request)
    if not valid_session(request.cookies.get("blissiree_session")):
        if path.startswith("/api/"):return JSONResponse({"detail":"Please sign in"},status_code=401)
        return FileResponse(ROOT/"login.html",status_code=401)
    return await call_next(request)

class ChatRequest(BaseModel):
    message:str=Field(min_length=1,max_length=4000)
    persona:str="emma"
    history:list[dict]=[]
    conversation_id:str|None=None

class TrainingPayload(BaseModel):
    id:str|None=None;title:str;instruction:str;target:str="ALL";category:str="OTHER";priority:str="NORMAL";status:str="DRAFT";source:str="TERRI";kind:str="INSTRUCTION";affected_components:list[str]=[];related_tests:list[str]=[];why_it_exists:str=""

class IssuePayload(BaseModel):
    persona:str;conversation_id:str;description:str=Field(min_length=3,max_length=2000);thread:list[dict]=Field(min_length=1,max_length=200)

class CoachRequest(BaseModel):
    message:str=Field(min_length=1,max_length=8000)
    history:list[dict]=Field(default=[],max_length=40)
    issue_id:str|None=None

def admin():
    return "Terri/Admin"

@app.get("/login")
def login_page():return FileResponse(ROOT/"login.html")

@app.post("/api/auth/login")
async def login(request:Request):
    body=await request.json();username=str(body.get("username", ""));password=str(body.get("password", ""))
    valid=hmac.compare_digest(username,os.getenv("APP_USERNAME","")) and hmac.compare_digest(password,os.getenv("APP_PASSWORD",""))
    if not valid:raise HTTPException(401,"Username or password is incorrect")
    response=JSONResponse({"ok":True});response.set_cookie("blissiree_session",session_token(username),max_age=43200,httponly=True,secure=True,samesite="strict",path="/")
    return response

@app.post("/api/auth/logout")
def logout():
    response=JSONResponse({"ok":True});response.delete_cookie("blissiree_session",path="/");return response

@app.get("/")
def index(): return FileResponse(ROOT/"index.html")

@app.get("/health")
def health(): return {"status":"ok","provider":"vertex-ai","analysis_model":settings.analysis_model,"conversation_model":settings.conversation_model}

@app.get("/api/meta")
def meta():
    return {"analysis_model":settings.analysis_model,"conversation_model":settings.conversation_model,
            "boost_collections":len(orchestrator.repo.catalog["boost_collections"]),
            "boost_audios":len(orchestrator.repo.catalog["boosts"]),"programs":len(orchestrator.repo.catalog["programs"])}

@app.get("/api/training/library")
def training_library(q:str="",category:str="ALL",target:str="ALL"):
    admin();rows=training_store.list(q,category,target)
    return {"items":rows,"total":len(rows)}

@app.get("/api/training/item/{item_id}")
def training_item(item_id:str):
    admin();row=training_store.get(item_id)
    if not row:raise HTTPException(404,"Training item not found")
    return row

@app.post("/api/training/validate")
def validate_training(payload:TrainingPayload):
    admin();conflicts=training_store.conflicts(payload.instruction,payload.id)
    components=payload.affected_components or (["TriageEngine","Output Validator","Safety tests"] if payload.category in {"SAFETY","BOUNDARY"} else ["ImmediateSupportEngine","Program routing tests"] if payload.category in {"BOOST","PROGRAM","RECOMMENDATION"} else [f"{payload.target.title()} conversation","Persona tests"])
    tests=[f"Verify {payload.target} obeys: {payload.title}",f"Verify conflicting or prohibited response is rejected"]
    return {"valid":not conflicts,"conflicts":conflicts,"affected_components":components,"proposed_tests":tests,"clarification_required":len(payload.instruction.strip())<20,"expected_impact":f"Changes {payload.target} behaviour in {payload.category.lower()} situations."}

@app.post("/api/training/items")
def save_training(payload:TrainingPayload):
    actor=admin();conflicts=training_store.conflicts(payload.instruction,payload.id)
    if payload.status=="ACTIVE" and conflicts:raise HTTPException(409,{"message":"Conflict detected","conflicts":conflicts})
    return training_store.upsert(payload.model_dump(exclude_none=True),actor)

@app.post("/api/training/item/{item_id}/status")
def training_status(item_id:str,body:dict):
    actor=admin()
    try:return training_store.transition(item_id,body.get("status","DISABLED"),actor,body.get("reason",""))
    except KeyError:raise HTTPException(404,"Training item not found")
    except PermissionError as exc:raise HTTPException(409,str(exc))

@app.get("/api/training/effective/{target}")
def effective_training(target:str):
    admin();target=target.upper()
    if target not in {"EMMA","BEN"}:raise HTTPException(400,"Target must be Emma or Ben")
    return {"target":target,"items":training_store.effective(target)}

@app.get("/api/training/history")
def training_history():
    admin();return {"versions":list(reversed(training_store.load()["versions"]))}

@app.post("/api/conversation-issues")
def report_conversation_issue(payload:IssuePayload):
    persona=payload.persona if payload.persona in {"emma","ben"} else "emma"
    safe_thread=[{"role":str(x.get("role",""))[:20],"content":str(x.get("content",""))[:4000]} for x in payload.thread]
    return issue_store.create(persona,payload.conversation_id,safe_thread,payload.description,admin())

@app.get("/api/conversation-issues")
def conversation_issues():return {"items":issue_store.list()}

@app.post("/api/conversation-issues/{issue_id}/status")
def conversation_issue_status(issue_id:str,body:dict):
    status=str(body.get("status","")).upper()
    if status not in {"OPEN","REVIEWED","RESOLVED"}:raise HTTPException(400,"Status must be OPEN, REVIEWED or RESOLVED")
    try:return issue_store.update_status(issue_id,status,admin())
    except KeyError:raise HTTPException(404,"Conversation issue not found")

@app.post("/api/admin-coach/chat")
def admin_coach_chat(body:CoachRequest):
    result=admin_coach.respond(body.message,body.history,body.issue_id)
    return result.model_dump()

@app.post("/api/admin-coach/apply")
def admin_coach_apply(payload:TrainingPayload):
    actor=admin();data=payload.model_dump(exclude_none=True);data.update({"status":"ACTIVE","source":"TERRI_AI_COACH","kind":"INSTRUCTION"})
    conflicts=training_store.conflicts(payload.instruction,payload.id)
    if conflicts:raise HTTPException(409,{"message":"Conflict detected","conflicts":conflicts})
    saved=training_store.upsert(data,actor)
    return {"applied":True,"item":saved,"message":"The approved instruction is active in the Training Library."}

@app.post("/api/training/build")
def build_training():
    return training_store.build(admin())

@app.post("/api/training/restore/{version}")
def restore_training(version:int):
    try:return training_store.restore(version,admin())
    except KeyError:raise HTTPException(404,"Configuration snapshot not available for this version")

@app.get("/sw.js")
def service_worker(): return FileResponse(ROOT/"sw.js",media_type="application/javascript")

@app.post("/api/chat")
def chat(body:ChatRequest):
    persona=body.persona if body.persona in {"emma","ben"} else "emma"
    result=orchestrator.respond(body.message,persona,body.history,body.conversation_id)
    def stream():
        yield json.dumps({"text":result["message"]})+"\n"
        yield json.dumps({k:v for k,v in result.items() if k!="message"}|{"done":True})+"\n"
    return StreamingResponse(stream(),media_type="application/x-ndjson",headers={"Cache-Control":"no-cache, no-transform"})

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=int(os.getenv("PORT","8080")))
