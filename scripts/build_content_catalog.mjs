import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const [collectionsFile, boostsFile, eeFile, uyFile] = process.argv.slice(2);
const load = async (file) => SpreadsheetFile.importXlsx(await FileBlob.load(file));
const values = (wb) => wb.worksheets.getItemAt(0).getUsedRange().values;
const slug = (s) => s.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const safetyTerms = {
  self_harm: /self.?harm|suicid/i, trauma: /trauma|flashback/i, medical_condition: /arthritis|pain|migraine|immune|bladder|spinal|pms|fatigue|depression|mental illness|disorder|hyperactivity|tinnitus|ear ringing|urinary|drug|alcohol|medication|cold and flu|gut health/i,
  addiction: /addiction|smoking|doing drugs/i, eating_disorder: /starvation|eating disorder|binging|purging|body dysmorphia/i,
  pregnancy: /pregnan|unborn|womb/i, children: /child|teen|birth to|1-12|5-12/i,
  claim_language: /heal|healing|relief|eliminat|abolish|combat|cure|fat burner|weight loss|stabiliser|rebalanc/i,
};

const collections = values(await load(collectionsFile)).slice(1).filter(r => r[0] || r[1]).map((r, i) => ({
  id: `collection-${String(i + 1).padStart(3, "0")}`, legacy_name: r[0] || null, display_name: r[1] || null,
  source: "AUDIOS - old and new bundles_collections.xlsx", version: "2026", approved_for_ai_recommendation: false,
}));
const boosts = values(await load(boostsFile)).slice(1).filter(r => r[0]).map((r, i) => {
  const title = String(r[0]); const flags = Object.entries(safetyTerms).filter(([, rx]) => rx.test(title)).map(([k]) => k);
  return { id: `boost-${String(i + 1).padStart(3, "0")}-${slug(title)}`, source_title: title, display_title: title,
    content_type: "BOOST", collection_ids: [], description: null, emotional_themes: [], user_needs: [], goals: [],
    recommended_when: [], avoid_when: [], stress_range: null, recovery_stage_eligibility: [], target_audience: null,
    age_restrictions: null, sleep_suitable: null, quick_support: true, safety_flags: flags,
    requires_safety_review: flags.some(x => x !== "claim_language"), requires_claim_review: flags.includes("claim_language"),
    approved_for_ai_recommendation: false, active: true, source: "Old Boost Names 2026.xlsx", version: "2026" };
});
const eeRows = values(await load(eeFile)).slice(1);
const emotionalEmpowerment = { id:"emotional_empowerment", content_type:"PROGRAM", program_type:"FOUNDATIONAL_LONG_TERM_JOURNEY",
  sessions: eeRows.filter(r=>r[0]).map(r=>({order:Number(String(r[0]).match(/\d+/)?.[0]), source_title:r[1]})),
  maintenance: eeRows.filter(r=>r[3]).map(r=>({order:Number(String(r[3]).match(/\d+/)?.[0]), source_title:r[4]})),
  life_lessons: eeRows.filter(r=>r[6]).map(r=>({order:Number(String(r[6]).match(/\d+/)?.[0]), source_title:r[7]})),
  tips: eeRows.filter(r=>r[9]).map(r=>({source_title:r[9]})), source:"Emotional Empowerment (1).xlsx", sequential:true };
const uyRows = values(await load(uyFile)).slice(1);
const unstoppableYou = { id:"unstoppable_you", content_type:"PROGRAM", program_type:"GROWTH_LONG_TERM_JOURNEY",
  habits:uyRows.filter(r=>r[0]).map(r=>({order:Number(String(r[0]).match(/\d+/)?.[0]),source_title:r[1]})),
  fundamentals:uyRows.filter(r=>r[3]).map(r=>({order:Number(String(r[3]).match(/\d+/)?.[0]),source_title:r[4]})),
  sessions:uyRows.filter(r=>r[6]).map(r=>({order:Number(String(r[6]).match(/\d+/)?.[0]),source_title:r[7]})),
  tips:uyRows.filter(r=>r[9]).map(r=>({source_title:r[9]})), source:"Unstoppable You (1).xlsx", sequential:true };
const normalized = new Map(); for (const b of boosts) { const k=slug(b.source_title).replace(/s$/,''); normalized.set(k,[...(normalized.get(k)||[]),b.source_title]); }
const nearDuplicates=[...normalized.values()].filter(x=>x.length>1);
const catalog={schema_version:"1.0",source_authority:80,boost_collections:collections,boosts,programs:[emotionalEmpowerment,unstoppableYou],
  report:{boosts:boosts.length,collections:collections.length,unmapped_boosts:boosts.length,near_duplicates:nearDuplicates,
    safety_review:boosts.filter(x=>x.requires_safety_review).length,claim_review:boosts.filter(x=>x.requires_claim_review).length,
    emotional_empowerment_sessions:emotionalEmpowerment.sessions.length,unstoppable_you_sessions:unstoppableYou.sessions.length,
    unstoppable_you_habits:unstoppableYou.habits.length,unstoppable_you_fundamentals:unstoppableYou.fundamentals.length}};
await fs.mkdir("knowledge/catalog",{recursive:true}); await fs.writeFile("knowledge/catalog/content.json",JSON.stringify(catalog,null,2));
console.log(JSON.stringify(catalog.report,null,2));
