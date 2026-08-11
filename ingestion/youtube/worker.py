import html
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from google.genai import types
from google.cloud import storage

logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
log=logging.getLogger("blissiree.youtube")
PROJECT=os.environ["PROJECT_ID"]
REGION=os.getenv("REGION","asia-southeast1")
BUCKET=os.environ["TRAINING_STORE_BUCKET"]
MODEL=os.getenv("GEMINI_MODEL","gemini-2.5-flash-lite")
CHANNELS=[x.strip() for x in os.getenv("CHANNEL_URLS","https://www.youtube.com/@blissiree/videos,https://www.youtube.com/@blissiree/shorts").split(",") if x.strip()]
MAX_ITEMS=int(os.getenv("MAX_ITEMS","0"))
PREFIX="youtube-ingestion"
LIBRARY_OBJECT="training-studio/library.json"
NOW=lambda:datetime.now(timezone.utc).isoformat()

storage_client=storage.Client(project=PROJECT)
bucket=storage_client.bucket(BUCKET)
gemini=genai.Client(vertexai=True,project=PROJECT,location=REGION)

def run(*args):
    command=list(args)
    if command and command[0]=="yt-dlp":command[1:1]=["--js-runtimes","node"]
    result=subprocess.run(command,text=True,capture_output=True)
    if result.returncode:
        log.error("command failed: %s",result.stderr[-1200:])
        result.check_returncode()
    return result.stdout

def upload_json(name,data):
    bucket.blob(name).upload_from_string(json.dumps(data,ensure_ascii=False,separators=(",",":")),content_type="application/json")

def load_json(name,default):
    blob=bucket.blob(name)
    return json.loads(blob.download_as_text()) if blob.exists() else default

def discover():
    staged_inventory=load_json(f"{PREFIX}/inventory.json",None)
    if staged_inventory:
        rows=staged_inventory.get("videos",[])
        return rows[:MAX_ITEMS] if MAX_ITEMS else rows
    found={}
    for channel in CHANNELS:
        data=json.loads(run("yt-dlp","--flat-playlist","--dump-single-json","--no-warnings",channel))
        for entry in data.get("entries",[]):
            if entry.get("id"):
                found[entry["id"]]={"id":entry["id"],"title":entry.get("title") or entry["id"],"url":f"https://www.youtube.com/watch?v={entry['id']}","channel_surface":channel.rsplit("/",1)[-1]}
    rows=list(found.values())
    return rows[:MAX_ITEMS] if MAX_ITEMS else rows

def clean_vtt(path):
    lines=[]
    for raw in path.read_text(errors="ignore").splitlines():
        line=html.unescape(re.sub(r"<[^>]+>","",raw)).strip()
        if not line or line.startswith(("WEBVTT","Kind:","Language:")) or "-->" in line or re.fullmatch(r"\d+",line):continue
        line=re.sub(r"\s+"," ",line)
        if not lines or line!=lines[-1]:lines.append(line)
    return " ".join(lines)

def captions(video,workdir):
    template=str(workdir/f"{video['id']}.%(ext)s")
    try:
        run("yt-dlp","--skip-download","--write-subs","--write-auto-subs","--sub-langs","en,en-US,en-GB","--sub-format","vtt","--no-warnings","-o",template,video["url"])
    except subprocess.CalledProcessError as exc:
        log.warning("caption download failed %s: %s",video["id"],exc.stderr[-300:])
    files=list(workdir.glob(f"{video['id']}*.vtt"))
    if not files:return "",None
    text=clean_vtt(files[0])
    return text,"youtube_captions" if text else ("",None)

def audio_transcript(video,workdir):
    template=str(workdir/f"{video['id']}.%(ext)s")
    run("yt-dlp","-f","bestaudio/best","-x","--audio-format","mp3","--audio-quality","7","--no-warnings","-o",template,video["url"])
    audio=next(workdir.glob(f"{video['id']}*.mp3"))
    object_name=f"{PREFIX}/audio/{audio.name}"
    bucket.blob(object_name).upload_from_filename(audio,content_type="audio/mpeg")
    response=gemini.models.generate_content(model=MODEL,contents=[types.Part.from_uri(file_uri=f"gs://{BUCKET}/{object_name}",mime_type="audio/mpeg"),"Transcribe this public Blissiree video faithfully. Return only the spoken words. Do not add interpretation."],config=types.GenerateContentConfig(temperature=0,max_output_tokens=8192))
    return response.text.strip(),"gemini_audio_transcription"

def metadata(video):
    data=json.loads(run("yt-dlp","-J","--skip-download","--no-warnings",video["url"]))
    return {"id":video["id"],"title":data.get("title") or video["title"],"url":video["url"],"description":data.get("description") or "","duration":data.get("duration"),"upload_date":data.get("upload_date"),"channel":data.get("channel") or "Blissiree","channel_id":data.get("channel_id"),"surface":video["channel_surface"]}

def case_study(meta,transcript):
    prompt={"task":"Convert a public, consented Blissiree video transcript into grounded companion knowledge.","rules":["Treat it as an individual testimonial or educational video, not medical evidence.","Do not diagnose or create claims not explicitly stated.","Separate participant-reported outcomes from Blissiree explanations.","Extract language and supportive conversation lessons Emma and Ben can use.","Never generalize an individual outcome as guaranteed or universal."],"required_json":{"content_type":"testimonial|educational|marketing|other","story_summary":"string","situation_and_feelings":["string"],"support_elements":["string"],"participant_reported_outcomes":["string"],"helpful_language_patterns":["string"],"companion_lessons":["string"],"claims_to_avoid":["string"]},"source":meta,"transcript":transcript[:40000]}
    response=gemini.models.generate_content(model=MODEL,contents=json.dumps(prompt,ensure_ascii=False),config=types.GenerateContentConfig(temperature=0,response_mime_type="application/json",max_output_tokens=4096))
    return json.loads(response.text)

def publish_library(meta,study,transcript_source):
    item_id=f"youtube-{meta['id']}"
    instruction=json.dumps({"source_url":meta["url"],"source_title":meta["title"],"transcript_source":transcript_source,"case_study":study},ensure_ascii=False)
    for attempt in range(6):
        blob=bucket.blob(LIBRARY_OBJECT)
        blob.reload()
        generation=blob.generation
        data=json.loads(blob.download_as_text())
        row=next((x for x in data.get("items",[]) if x.get("id")==item_id),None)
        now=NOW()
        payload={"id":item_id,"title":meta["title"],"instruction":instruction,"target":"ALL","category":"KNOWLEDGE","priority":"NORMAL","status":"ACTIVE","source":"YOUTUBE_PUBLIC","authority":70,"protected":False,"kind":"KNOWLEDGE","created_by":"YouTube background ingestion","approved_by":"Public participant-consented channel import","version":1,"created_at":now,"updated_at":now,"affected_components":["RAG","Emma","Ben"],"related_tests":[],"why_it_exists":f"Public Blissiree case study: {meta['url']}","history":[]}
        if row:row.update({k:v for k,v in payload.items() if k not in {"created_at","version","history"}});row["version"]=int(row.get("version",1))+1
        else:data.setdefault("items",[]).append(payload)
        try:
            blob.upload_from_string(json.dumps(data,ensure_ascii=False,separators=(",",":")),content_type="application/json",if_generation_match=generation)
            return
        except Exception:
            if attempt==5:raise
            time.sleep(1+attempt)

def main():
    manifest=load_json(f"{PREFIX}/manifest.json",{"channel_id":"UCC632041igVf2YkUo7zM5PA","started_at":NOW(),"processed":{},"failures":{}})
    videos=discover();manifest["discovered"]=len(videos);upload_json(f"{PREFIX}/manifest.json",manifest)
    log.info("discovered %d unique videos and shorts",len(videos))
    for index,video in enumerate(videos,1):
        if manifest["processed"].get(video["id"]):continue
        try:
            with tempfile.TemporaryDirectory() as tmp:
                workdir=Path(tmp);staged=load_json(f"{PREFIX}/staged/{video['id']}.json",None)
                if staged:meta=staged["metadata"];transcript=staged["transcript"];source=staged.get("transcript_source","youtube_captions")
                else:
                    meta=metadata(video);transcript,source=captions(video,workdir)
                    if not transcript:transcript,source=audio_transcript(video,workdir)
                transcript_record={"metadata":meta,"transcript_source":source,"transcript":transcript,"ingested_at":NOW()}
                upload_json(f"{PREFIX}/transcripts/{video['id']}.json",transcript_record)
                study=case_study(meta,transcript)
                upload_json(f"{PREFIX}/case-studies/{video['id']}.json",{"metadata":meta,"case_study":study,"created_at":NOW()})
                publish_library(meta,study,source)
                manifest["processed"][video["id"]]={"title":meta["title"],"url":meta["url"],"source":source,"completed_at":NOW()};manifest["failures"].pop(video["id"],None)
                log.info("processed %d/%d %s %s",index,len(videos),video["id"],meta["title"])
        except Exception as exc:
            log.exception("failed %s",video["id"]);manifest["failures"][video["id"]]={"error":f"{type(exc).__name__}: {exc}","updated_at":NOW()}
        manifest["updated_at"]=NOW();upload_json(f"{PREFIX}/manifest.json",manifest)
    manifest["finished_at"]=NOW();upload_json(f"{PREFIX}/manifest.json",manifest)
    log.info("complete processed=%d failures=%d",len(manifest["processed"]),len(manifest["failures"]))
    if not manifest["processed"] and manifest["failures"]:sys.exit(1)

if __name__=="__main__":main()
