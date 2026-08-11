#!/usr/bin/env python3
import argparse
import html
import json
import re
import subprocess
import tempfile
from datetime import datetime,timezone
from pathlib import Path

PROJECT="project-cb312c2a-9821-411b-a76"
REGION="asia-southeast1"
BUCKET="project-cb312c2a-9821-411b-a76-blissiree-models"
PREFIX="youtube-ingestion"
CHANNELS=["https://www.youtube.com/@blissiree/videos","https://www.youtube.com/@blissiree/shorts"]
NOW=lambda:datetime.now(timezone.utc).isoformat()

def run(*args,check=True):
    return subprocess.run(args,text=True,capture_output=True,check=check)

def upload(path,object_name):
    subprocess.run(["gcloud","storage","cp",str(path),f"gs://{BUCKET}/{object_name}","--quiet"],check=True,stdout=subprocess.DEVNULL)

def clean_vtt(path):
    lines=[]
    for raw in path.read_text(errors="ignore").splitlines():
        line=html.unescape(re.sub(r"<[^>]+>","",raw)).strip()
        if not line or line.startswith(("WEBVTT","Kind:","Language:")) or "-->" in line or re.fullmatch(r"\d+",line):continue
        line=re.sub(r"\s+"," ",line)
        if not lines or line!=lines[-1]:lines.append(line)
    return " ".join(lines)

def discover():
    found={}
    for channel in CHANNELS:
        data=json.loads(run("yt-dlp","--flat-playlist","--dump-single-json","--no-warnings",channel).stdout)
        for entry in data.get("entries",[]):
            if entry.get("id"):found[entry["id"]]={"id":entry["id"],"title":entry.get("title") or entry["id"],"url":f"https://www.youtube.com/watch?v={entry['id']}","channel_surface":channel.rsplit("/",1)[-1]}
    return list(found.values())

def stage(video,root):
    meta=json.loads(run("yt-dlp","-J","--skip-download","--no-warnings",video["url"]).stdout)
    template=str(root/f"{video['id']}.%(ext)s")
    result=run("yt-dlp","--skip-download","--write-subs","--write-auto-subs","--sub-langs","en,en-US,en-GB","--sub-format","vtt","--no-warnings","-o",template,video["url"],check=False)
    files=list(root.glob(f"{video['id']}*.vtt"))
    if not files:raise RuntimeError("No English captions available: "+result.stderr[-300:])
    transcript=clean_vtt(files[0])
    if not transcript:raise RuntimeError("Caption file contained no transcript")
    payload={"metadata":{"id":video["id"],"title":meta.get("title") or video["title"],"url":video["url"],"description":meta.get("description") or "","duration":meta.get("duration"),"upload_date":meta.get("upload_date"),"channel":meta.get("channel") or "Blissiree","channel_id":meta.get("channel_id"),"surface":video["channel_surface"]},"transcript_source":"youtube_captions","transcript":transcript,"staged_at":NOW()}
    out=root/f"{video['id']}.json";out.write_text(json.dumps(payload,ensure_ascii=False));upload(out,f"{PREFIX}/staged/{video['id']}.json")
    for file in files:file.unlink(missing_ok=True)
    return payload["metadata"]

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--max-items",type=int,default=0);parser.add_argument("--launch-job",action="store_true");args=parser.parse_args()
    videos=discover();videos=videos[:args.max_items] if args.max_items else videos;success=[];failures={}
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        for index,video in enumerate(videos,1):
            try:
                meta=stage(video,root);success.append(video);print(f"staged {index}/{len(videos)} {video['id']} {meta['title']}",flush=True)
            except Exception as exc:
                failures[video["id"]]=f"{type(exc).__name__}: {exc}";print(f"failed {video['id']}: {exc}",flush=True)
        inventory={"channel_id":"UCC632041igVf2YkUo7zM5PA","created_at":NOW(),"discovered":len(videos),"staged":len(success),"failures":failures,"videos":success}
        out=root/"inventory.json";out.write_text(json.dumps(inventory,ensure_ascii=False));upload(out,f"{PREFIX}/inventory.json")
    print(json.dumps({"discovered":len(videos),"staged":len(success),"failures":len(failures)}),flush=True)
    if args.launch_job and success:
        subprocess.run(["gcloud","run","jobs","update","blissiree-youtube-ingestion","--project",PROJECT,"--region",REGION,"--update-env-vars","MAX_ITEMS=0","--quiet"],check=True)
        subprocess.run(["gcloud","run","jobs","execute","blissiree-youtube-ingestion","--project",PROJECT,"--region",REGION,"--async"],check=True)

if __name__=="__main__":main()
