/* Reproducible current-season comparison. Build standalone predictor first. No network calls. */
const fs=require('node:fs'),path=require('node:path'),M=require('../maps/predictor-model.js');
const root=path.resolve(__dirname,'..'),html=fs.readFileSync(path.join(root,'build/playoff-predictor.html'),'utf8');
const data=JSON.parse(html.split('window.CFB_PREDICTOR_DATA=')[1].split(';</script>')[0]),iterations=Number(process.argv[2]||2000),seed=2026;
const cases=[['sp_objective',M.project(data,{method:'sp',iterations,seed})],['elo_objective',M.project(data,{method:'elo',iterations,seed})],['elo_legacy',M.projectLegacy(data,{iterations,seed})]];
const names=new Map(data.teams.map(t=>[t.id,t.school]));
const report={season:data.year,as_of:data.as_of,iterations,seed,sp_snapshot:data.spSnapshot?.retrieved_at||null,calibration_limitation:data.calibration.sp_calibration,models:{}};
for(const [name,result] of cases){const conferences={};for(const t of result.teams)conferences[t.conference]=(conferences[t.conference]||0)+t.playoffs/iterations;
 report.models[name]={effective_method:result.method||'legacy Elo',expected_places_by_conference:conferences,top_20:[...result.teams].sort((a,b)=>b.playoffs-a.playoffs||a.id-b.id).slice(0,20).map(t=>({id:t.id,team:names.get(t.id),qualification_probability:t.playoffs/iterations,objective_rank:t.objectiveRank??null}))};}
if(process.argv.includes('--sensitivity')){
 report.reference_sensitivity=[];const sensitivityRuns=Math.min(1000,iterations);
 for(const reference_sp of [15,20,25])for(const sor_tolerance of [0,Math.log(1.01),Math.log(1.05)]){
  const r=M.project(data,{method:'sp',iterations:sensitivityRuns,seed,modelConfig:{reference_sp,sor_tolerance}});
  report.reference_sensitivity.push({reference_sp,sor_tolerance,iterations:sensitivityRuns,expected_group_places:r.teams.filter(t=>data.rules.group_automatic.includes(t.conference)).reduce((n,t)=>n+t.playoffs/sensitivityRuns,0),
   top_12:[...r.teams].sort((a,b)=>b.playoffs-a.playoffs||a.id-b.id).slice(0,12).map(t=>({id:t.id,team:names.get(t.id),qualification_probability:t.playoffs/sensitivityRuns}))});
 }
}
fs.writeFileSync(path.join(root,'data/predictor_comparison.json'),JSON.stringify(report,null,2)+'\n');console.log(`Compared ${iterations} reproducible forecasts each: SP+/objective, Elo/objective, original Elo selection. SP+ effective method: ${cases[0][1].method}.`);
