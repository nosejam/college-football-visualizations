const assert=require('node:assert/strict'),M=require('../maps/predictor-model.js');
const close=(a,b,t=1e-6)=>assert(Math.abs(a-b)<t,`${a} vs ${b}`);
close(M.normalCDF(0),.5);close(M.normalCDF(1),.841344746);
close(M.sorDistribution([.5,.5])[2],-Math.log(.25));close(M.sorDistribution([.9,.1])[1],-Math.log(.91));
assert(M.sorDistribution([.3,.4])[2]>M.sorDistribution([.9,.95])[2]);
assert(M.sorDistribution([.1,.2,.3])[2]>M.sorDistribution([.9,.9,.9])[2]);
close(M.sorDistribution(Array(500).fill(.001))[500],-500*Math.log(.001),1e-8);
assert.equal(M.sorDistribution([])[0],0);assert.throws(()=>M.sorDistribution([NaN]));
const cal=require('../data/sources/ratings/calibration.json');
const provider={method:'sp',values:[20,20,-10]},ratings=[1500,1500,1500];
close(M.gameProbability(provider,0,1,ratings,0,cal),.5);assert(M.gameProbability(provider,0,1,ratings,1,cal)>.5);
close(M.gameProbability(provider,0,2,ratings,1,cal)+M.gameProbability(provider,2,0,ratings,-1,cal),1);
const rules={field_size:12,byes:4,power_automatic:['ACC','Big Ten','Big 12','SEC'],group_automatic:['American Athletic','Conference USA','Mid-American','Mountain West','Pac-12','Sun Belt'],notre_dame_top_12_guarantee:true,notre_dame_id:87,sun_belt_east:[]};
const conferences=['ACC','ACC','Big Ten','Big Ten','Big 12','Big 12','SEC','SEC','Conference USA','Conference USA','Mid-American','Mid-American','FBS Independents','FBS Independents'];
const teams=conferences.map((conference,i)=>({id:i===12?87:i+1,school:'Team '+i,conference,fbs:true})),roster=teams.map(t=>t.id);
const games=[];for(let i=0;i<12;i+=2)games.push({id:i+1,home:teams[i].id,away:teams[i+1].id,week:1,date:'2026-09-05T18:00:00Z',score:null,conference:true,championship:false,neutral:true});
const data={rules,year:2026,teams,roster,games,objective:{},calibration:cal,frames:[{week:null,label:'Preseason',elo:Object.fromEntries(roster.map(id=>[id,1500]))}]};
const a=M.project(data,{iterations:100,seed:7}),b=M.project(data,{iterations:100,seed:7});assert.deepEqual(a,b);
assert.equal(a.teams.reduce((n,t)=>n+t.playoffs,0),1200);assert.equal(a.teams.reduce((n,t)=>n+t.byes,0),400);assert.equal(a.teams.reduce((n,t)=>n+t.championships,0),100);
for(const t of a.teams){assert.equal(t.automatic+t.atlarge,t.playoffs);assert(t.playoffs>=0&&t.playoffs<=100);assert(t.championships<=t.playoffs);assert(!t.playoffOut);}
const forced=M.project(data,{iterations:20,seed:7,choices:{1:1}});assert(forced.teams.find(t=>t.id===1).projectedWins>=1);assert(forced.teams.find(t=>t.id===2).projectedLosses>=1);
assert(forced.teams.find(t=>t.id===1).sor>a.teams.find(t=>t.id===1).sor);
const observed={...data,games:games.map((g,i)=>i?g:{...g,score:[7,21]}),frames:[{...data.frames[0],week:1}]};
const unchanged=M.project(observed,{iterations:20,choices:{1:1}});assert.equal(unchanged.teams.find(t=>t.id===1).record.losses,1);assert.equal(unchanged.teams.find(t=>t.id===2).record.wins,1);
const snapshot={season:2026,retrieved_at:new Date().toISOString(),scale:{verified:true},coverage:{matched:14,expected:14},ratings:Object.fromEntries(roster.map((id,i)=>[id,{rating:20-i}]))};
const spdata={...data,spSnapshot:snapshot};assert.equal(M.ratingProvider(spdata,0).method,'sp');
const sp=M.project(spdata,{iterations:30,choices:{1:1}}),spOther=M.project(spdata,{iterations:30,choices:{1:2}});
assert.deepEqual(sp.teams.map(t=>t.sp),spOther.teams.map(t=>t.sp));
assert.equal(M.ratingProvider({...spdata,spSnapshot:{...snapshot,retrieved_at:'2020-01-01T00:00:00Z'}},0).method,'elo');
assert.equal(M.ratingProvider({...spdata,frames:[{...data.frames[0],date:'2026-09-01'},data.frames[0]]},0).method,'elo');
assert.equal(M.ratingProvider(spdata,0,'elo').method,'elo');
const missing=M.ratingProvider({...spdata,spSnapshot:{...snapshot,ratings:{}}},0);assert.equal(missing.values[0],null);
const all=Array.from({length:24},(_,i)=>({id:i===11?87:i+100,conference:i===0?'Pac-12':'FBS Independents'}));
const champs=new Map();rules.power_automatic.forEach((c,j)=>{all[20+j].conference=c;champs.set(c,20+j);});all[18].conference='Pac-12';champs.set('Pac-12',18);
const field=M.selectField({ranking:all.map((_,i)=>i),champions:champs,teams:all,rules});assert.equal(new Set(field).size,12);for(const i of [0,11,20,21,22,23])assert(field.includes(i));assert(!field.includes(18));assert.deepEqual(field.slice(-4),[20,21,22,23]);
const automatic=new Set([0,11,20,21,22,23]);assert.equal(field.filter(i=>!automatic.has(i)).length,6);
all[11].id=999;const noND=M.selectField({ranking:all.map((_,i)=>i),champions:champs,teams:all,rules});assert.equal(noND.filter(i=>![0,20,21,22,23].includes(i)).length,7);
// Deterministic rank and reference-strength / tolerance sensitivity.
const resumes=[{sor:1,sos:.1,power:20},{sor:1.005,sos:.2,power:10},{sor:.5,sos:.5,power:40}];
assert.deepEqual(M.objectiveRanking([0,1,2],resumes,teams,new Map()),[1,0,2]);
assert.deepEqual(M.objectiveRanking([0,1,2],resumes,teams,new Map(),0),[1,0,2]);
for(const reference_sp of [15,20,25])for(const sor_tolerance of [0,Math.log(1.01),Math.log(1.05)]){
 const r=M.project(spdata,{iterations:10,seed:5,modelConfig:{reference_sp,sor_tolerance}});assert.equal(r.teams.reduce((n,t)=>n+t.playoffs,0),120);
}
assert.equal(M.commonDraw(2,7,'g1'),M.commonDraw(2,7,'g1'));assert.notEqual(M.commonDraw(2,7,'g1'),M.commonDraw(2,7,'g2'));
assert(cal.test.normal.n>1000);for(const kind of ['normal','logistic','legacy_elo'])assert(cal.test[kind].brier>0&&cal.test[kind].brier<.3);
console.log('Passed objective predictor: log-space SOR, calibrated baseline, sites/complements, snapshot/fallback, deterministic selection, 2026 bids/seeds, fixed results, reproducibility, probability conservation and sensitivity.');
// Fully observed selection: no stochastic selection decisions, exact endpoint flags.
const finished={...data,games:games.map(g=>({...g,score:[28,7]})).concat(games.map(g=>({...g,id:g.id+1000,championship:true,week:2,score:[31,14]}))),frames:[{...data.frames[0],week:2}]};
const exact=M.project(finished,{iterations:8,seed:1});assert(exact.teams.every(t=>t.playoffs===0||t.playoffs===8));assert(exact.teams.every(t=>t.playoffClinched===Boolean(t.playoffs)&&t.playoffOut===!t.playoffs));
// Same SOR, harder schedule wins near tie; stricter SOR dominates outside tolerance.
assert.deepEqual(M.objectiveRanking([0,1],[{sor:1,sos:.5,power:1},{sor:1.001,sos:.1,power:1}],teams,new Map()),[0,1]);
assert.deepEqual(M.objectiveRanking([0,1],[{sor:1,sos:.5,power:1},{sor:1.001,sos:.1,power:1}],teams,new Map(),0),[1,0]);
const sites=[];M.championship(Array.from({length:12},(_,i)=>i),(a,b,site=0)=>{sites.push(site);return a;});assert.deepEqual(sites.slice(0,4),[1,1,1,1]);assert(sites.slice(4).every(s=>s===0));
// Fixed scheduled title outcome cannot manufacture participants; when qualified it is honored.
const titleData={...data,games:[...data.games,{...data.games[0],id:900,championship:true,week:2}],frames:data.frames};
const titleForced=M.project(titleData,{iterations:30,choices:{900:1},seed:4});assert.equal(titleForced.teams.find(t=>t.id===1).conferenceWins,30);
console.log('Passed exact completed-season endpoint proofs, near-tie policy, playoff venues and conditional title picks.');
