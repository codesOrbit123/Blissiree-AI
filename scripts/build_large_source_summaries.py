#!/usr/bin/env python3
"""Build compact, source-linked summaries only for genuinely large knowledge sources."""
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/"knowledge"/"sources"
OUT=SOURCES/"large_source_summaries.json"
KEY=re.compile(r"\b(must|never|always|before|after|priority|safety|persona|emma|ben|triage|response|conversation|recommend|boundary|validate|avoid|requires?|only|sequence|stage)\b",re.I)

def clean(text):return re.sub(r"\s+"," ",str(text)).strip()

def architecture():
    data=json.loads((SOURCES/"terri_architecture.json").read_text())
    paragraphs=[clean(x.get("text","")) for x in data["blocks"] if x.get("type")=="paragraph" and clean(x.get("text",""))]
    sections={};current="FOUNDATION"
    for p in paragraphs:
        match=re.fullmatch(r"DOC-(\d{2})",p)
        if match:current="DOC-"+match.group(1);sections.setdefault(current,[]);continue
        sections.setdefault(current,[]).append(p)
    rows=[]
    for name,parts in sections.items():
        if name=="FOUNDATION":continue
        selected=[]
        for p in parts:
            if len(p)<140 or KEY.search(p):selected.append(p)
            if len(" ".join(selected))>=4200:break
        rows.append({"id":"summary:architecture:"+name.lower(),"source":"TERRI_ARCHITECTURE_SUMMARY","authority":100,
                     "source_ids":["terri_architecture.json"],"title":name+" architecture summary","text":clean(" ".join(selected))[:5000]})
    return rows

def workbooks():
    data=json.loads((SOURCES/"terri_exhaustion_training.json").read_text());rows=[]
    for wrapper in data.get("records",[]):
        x=wrapper.get("active_companion_training",{});rid=x.get("record_id") or wrapper.get("id")
        if not x:continue
        text=(f"{x.get('topic','')}. User expressions: {' | '.join(x.get('user_language',[]))}. "
              f"Emotional context: {'; '.join(x.get('reported_emotional_context',[]))}. "
              f"Personalisation signals: {'; '.join(x.get('personalization_signals',[]))}. "
              f"Useful follow-up areas: {'; '.join(x.get('safe_follow_up_prompts',[]))}. "
              f"Must avoid: {'; '.join(x.get('must_avoid',[]))}. {x.get('safety_override','')} {x.get('recommendation_boundary','')}")
        rows.append({"id":f"summary:workbook:{rid}","source":"TERRI_WORKBOOK_SUMMARY","authority":95,
                     "source_ids":[f"terri-workbook:{rid}"],"title":x.get("topic",rid),"text":clean(text)[:3000]})
    return rows

def main():
    rows=architecture()+workbooks()
    OUT.write_text(json.dumps({"schema_version":1,"policy":"Only large sources are summarised; concise rules and exact records remain verbatim.","summaries":rows},ensure_ascii=False,indent=2)+"\n")
    print(f"Wrote {len(rows)} selective summaries to {OUT}")

if __name__=="__main__":main()
