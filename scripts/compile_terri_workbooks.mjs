import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const args=process.argv.slice(2);
const outIndex=args.indexOf("--out");
if(outIndex<0||outIndex===args.length-1)throw new Error("Usage: node compile_terri_workbooks.mjs workbook... --out output.json");
const output=args[outIndex+1],files=args.slice(0,outIndex);
const medical=/\b(GP|doctor|clinician|healthcare|medical|diagnos|medication|blood test|psychologist|psychiatrist|depression|PTSD|dissociat|hormone|thyroid|biochemical|neurolog|sleep apnoea)\b/i;
const headers={};
const split=value=>String(value||"").split("|").map(x=>x.trim()).filter(Boolean);
const clauses=value=>String(value||"").split(/;|\?|\.(?:\s|$)/).map(x=>x.trim()).filter(x=>x&&!medical.test(x));
const empathy=value=>{
  const lead=String(value||"").split("?")[0].trim();
  return lead&&!medical.test(lead)?lead+(lead.endsWith(".")?"":"."):null;
};
const safetyClass=id=>id==="EX-004C"?"RELATIONSHIP_SAFETY":id==="EX-005C"?"PHYSICAL_RED_FLAG":id==="EX-002E"?"DROWSY_DRIVING":id==="EX-004D"?"DETACHMENT_OR_CRISIS":"GENERAL_SAFETY";
const records=[];
for(const path of files){
  const workbook=await SpreadsheetFile.importXlsx(await FileBlob.load(path));
  const sheet=workbook.worksheets.getItemAt(0),values=sheet.getRange("A1:X7").values;
  values[1].forEach((name,index)=>headers[index]=name);
  for(const row of values.slice(2)){
    const full=Object.fromEntries(row.map((value,index)=>[headers[index],value]));
    const id=row[0];
    records.push({
      id,source_file:path.split("/").pop(),source_sheet:sheet.name,full_source_record:full,
      active_companion_training:{
        record_id:id,target:"EMMA",topic:row[1],user_language:split(row[2]),reported_emotional_context:split(row[3]),
        personalization_signals:clauses(row[6]),safe_empathy_openings:[row[8],row[9],row[10]].map(empathy).filter(Boolean),
        safe_follow_up_prompts:clauses(row[11]),must_avoid:clauses(row[22]),safety_class:safetyClass(id),
        safety_override:"If immediate danger, abuse, dangerous driving, severe physical warning signs, self-harm, or inability to stay safe is disclosed, stop recommendations and use the deterministic safety pathway.",
        recommendation_boundary:"This exemplar does not authorize a product. Only the deterministic recommendation engine may offer an exact approved catalogue title after safety and eligibility checks.",
        medical_boundary:"Do not diagnose, investigate symptoms as healthcare, request medical records, or present nervous-system or neuroplasticity explanations as medical fact."
      }
    });
  }
}
await fs.mkdir(output.split("/").slice(0,-1).join("/"),{recursive:true});
await fs.writeFile(output,JSON.stringify({schema_version:1,source:"TERRI_WORKBOOK",record_count:records.length,records},null,2));
