#!/usr/bin/env python3
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "training" / "data"
SYSTEM = """You are a Blissiree companion, not a medical or healthcare professional. Use only approved Blissiree evidence. Never diagnose, treat, prescribe, promise outcomes, invent benefits, or imply healthcare affiliation. Safety overrides engagement and content recommendations. Be warm, concise, non-judgmental, and honest when approved information is unavailable."""

def record(user, assistant, source, authority, category, trainable=True):
    return {"messages":[{"role":"system","content":SYSTEM},{"role":"user","content":user},{"role":"assistant","content":assistant}],
            "metadata":{"source":source,"authority":authority,"category":category,"trainable":trainable}}

records = []
for filename, authority in [("terri_architecture.json",100),("terri_training_manual_part1.json",90)]:
    data=json.loads((ROOT/"knowledge"/"sources"/filename).read_text())
    section="General"
    for block in data["blocks"]:
        if block["type"] != "paragraph": continue
        text=block["text"].strip()
        if block.get("style","").startswith("Heading"):
            section=text; continue
        if len(text) < 20: continue
        records.append(record(f"What approved Blissiree guidance applies to {section}?", text, filename, authority, "architecture_rule"))

catalog=json.loads((ROOT/"knowledge"/"catalog"/"content.json").read_text())
for program in catalog["programs"]:
    for kind in ("sessions","habits","fundamentals","maintenance","life_lessons","tips"):
        for item in program.get(kind,[]):
            order=item.get("order")
            label=f" {order}" if order else ""
            records.append(record(f"What is {program['id']} {kind.rstrip('s')}{label}?",
                f"The approved source title is “{item['source_title']}”. Preserve its program order; similarity search must not skip progression rules.",
                program["source"],80,"approved_program_fact"))
for boost in catalog["boosts"]:
    records.append(record(f"Should I recommend the Boost “{boost['source_title']}” based only on its title?",
        f"No. “{boost['source_title']}” exists in the supplied catalog, but its use cases and collection mapping are not yet approved. I must not infer benefits or recommend it from the title alone.",
        boost["source"],70,"unapproved_content_boundary"))

records += [
 record("I think I have severe depression. Which audio will cure it?","I can’t diagnose a condition or recommend Blissiree as a cure. Blissiree offers non-medical wellbeing support only. If you feel unsafe or may harm yourself, contact local emergency services now and reach out to someone you trust nearby.","owner_confirmed_policy",110,"safety"),
 record("Are you my therapist?","No. I’m a Blissiree companion for non-medical wellbeing support, not a therapist or healthcare provider. I can help you navigate approved Blissiree content and take a small, practical next step.","owner_confirmed_policy",110,"boundary"),
 record("Store this as my medical diagnosis: anxiety disorder.","I won’t create a medical diagnosis or medical record. If you explicitly share a diagnosis, the system may only label it as user-reported when that information is genuinely needed and permitted; it is never an AI diagnosis.","owner_confirmed_policy",110,"privacy"),
 record("I might hurt myself tonight.","I’m really sorry you’re facing this. I can’t provide emergency support or recommend Blissiree content right now. Please contact your local emergency services or crisis line now, and tell a trusted person nearby who can stay with you. Are you in immediate danger right now?","terri_architecture.json",100,"safety"),
 record("Talk to me as Emma. I’ve had a difficult day.","That sounds like a lot to carry today. We can keep this simple and focus on what would feel most supportive right now. What’s the main thing weighing on you?","terri_architecture.json",100,"emma_persona"),
 record("Talk to me as Ben. I feel scattered.","Let’s make the next step clear and manageable. What is the one thing you most need help settling or deciding right now?","terri_architecture.json",100,"ben_persona"),
]

dedup={}
for item in records:
    key=hashlib.sha256(json.dumps(item["messages"],sort_keys=True).encode()).hexdigest()
    dedup[key]=item
records=list(dedup.values())

def bucket(item):
    h=int(hashlib.sha256(json.dumps(item["messages"],sort_keys=True).encode()).hexdigest()[:8],16)%100
    return "test" if h<10 else "validation" if h<20 else "train"

OUT.mkdir(parents=True,exist_ok=True)
parts={k:[] for k in ("train","validation","test")}
for item in records: parts[bucket(item)].append(item)
for name, items in parts.items():
    with (OUT/f"{name}.jsonl").open("w") as f:
        for item in items: f.write(json.dumps(item,ensure_ascii=False)+"\n")
manifest={"schema_version":"1.0","total":len(records),"splits":{k:len(v) for k,v in parts.items()},
          "policy":"Behavior and approved program structure may be fine-tuned. Mutable catalog facts remain retrieval-authoritative. Unapproved content examples train refusal, never benefits."}
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
