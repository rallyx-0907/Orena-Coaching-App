/* Phase 1 of ORENA_GRAMMAR_LESSON_DESIGN_SYSTEM §30: audit every concept in
 * both curricula against the pedagogical contract, and report per §34.
 *
 * This reads the closed knowledge layer and writes nothing. Its job is to say,
 * with numbers, which lessons the design system would accept and which still
 * need authored content - so "Grammar is done" is never claimed for a system
 * where only the sample lesson was looked at.
 */
import {readFileSync} from 'node:fs';
import {
  classifyArchetype,
  deriveSegmentRole,
  isGenericLabel,
  ARCHETYPE_PRIMARY_VISUAL,
  VISUAL_BLOCK_TYPE,
} from '../static/orena/capabilities/grammar-pedagogy.js';

const load=path=>{
  const raw=JSON.parse(readFileSync(new URL(path,import.meta.url),'utf8'));
  return Array.isArray(raw)?raw:(raw.concepts||raw.items||[]);
};

const CURRICULA=[
  ['en',load('../writing_coach/languages/english/grammar_knowledge.json')],
  ['zh',load('../writing_coach/languages/chinese/grammar_knowledge.json')],
];

const blocksOf=concept=>Array.isArray(concept?.learning_model?.blocks)?concept.learning_model.blocks:[];
const patternParts=concept=>blocksOf(concept)
  .filter(block=>block?.stage==='pattern')
  .flatMap(block=>[...(block.payload?.parts||[]),...(block.payload?.segments||[])]);

const report={};
let totalParts=0, namedParts=0, genericLabels=0;

for(const [language,concepts] of CURRICULA){
  const archetypes={}, missingVisual=[], missingContrast=[], missingPractice=[], noPattern=[];
  for(const concept of concepts){
    const archetype=classifyArchetype(concept);
    archetypes[archetype]=(archetypes[archetype]||0)+1;

    const types=new Set(blocksOf(concept).map(block=>block?.type));
    const wanted=VISUAL_BLOCK_TYPE[ARCHETYPE_PRIMARY_VISUAL[archetype]];
    if(wanted&&!types.has(wanted))missingVisual.push({id:concept.id,archetype,wanted});
    if(!types.has('contrast'))missingContrast.push(concept.id);
    if(!types.has('micro_practice')&&!types.has('sentence_builder'))missingPractice.push(concept.id);

    const parts=patternParts(concept);
    if(!parts.length)noPattern.push(concept.id);
    for(const part of parts){
      totalParts+=1;
      const role=deriveSegmentRole(part?.text,part?.role);
      if(role&&role!=='marker')namedParts+=1;
      const label=part?.label;
      const text=typeof label==='string'?label:(label?.en||label?.vi||label?.zh||'');
      if(isGenericLabel(text))genericLabels+=1;
    }
  }
  report[language]={count:concepts.length,archetypes,missingVisual,missingContrast,missingPractice,noPattern};
}

console.log('ORENA GRAMMAR PEDAGOGY AUDIT');
console.log('============================\n');
for(const [language,data] of Object.entries(report)){
  console.log(`${language.toUpperCase()} — ${data.count} concepts`);
  const rows=Object.entries(data.archetypes).sort((a,b)=>b[1]-a[1]);
  for(const [archetype,n] of rows){
    console.log(`   ${archetype.padEnd(26)} ${String(n).padStart(4)}  (${Math.round((n/data.count)*100)}%)`);
  }
  console.log(`   concepts without any pattern block: ${data.noPattern.length}`);
  console.log(`   missing the visual their archetype calls for: ${data.missingVisual.length}`);
  const byWanted={};
  for(const row of data.missingVisual)byWanted[row.wanted]=(byWanted[row.wanted]||0)+1;
  for(const [wanted,n] of Object.entries(byWanted).sort((a,b)=>b[1]-a[1])){
    console.log(`       needs an authored "${wanted}" block: ${n}`);
  }
  console.log(`   missing contrast: ${data.missingContrast.length}`);
  console.log(`   missing practice: ${data.missingPractice.length}\n`);
}
console.log(`Pattern parts across both curricula: ${totalParts}`);
console.log(`   parts a role can be named for:  ${namedParts} (${Math.round((namedParts/totalParts)*100)}%)`);
console.log(`   parts labelled only by position: ${genericLabels} (${Math.round((genericLabels/totalParts)*100)}%)`);
