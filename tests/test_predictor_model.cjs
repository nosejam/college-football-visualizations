const assert=require('node:assert/strict');
const M=require('../maps/predictor-model.js');
// Compare mathematical conference qualification against every remaining outcome.
let seed=19;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};let checks=0;
for(let trial=0;trial<25;trial++){
 const pool=[1,2,3,4,5],wins=Object.fromEntries(pool.map(i=>[i,0])),totals=Object.fromEntries(pool.map(i=>[i,4])),remaining=[];
 for(const a of pool)for(const b of pool)if(a<b){if(random()<.6)remaining.push([a,b]);else wins[random()<.5?a:b]++;}
 for(const slots of [1,2])for(const target of pool){
  let possible=false;
  for(let mask=0;mask<2**remaining.length;mask++){
   const final={...wins};remaining.forEach(([a,b],i)=>final[mask&(1<<i)?a:b]++);
   if(pool.filter(i=>i!==target&&final[i]>final[target]).length<slots){possible=true;break;}
  }
  assert.equal(M.canQualify({target,pool,wins,totals,remaining,slots}),possible,`feasibility ${trial}/${slots}/${target}`);checks++;
 }
}
assert(!M.canQualify({target:1,pool:[1,2,3,4],wins:{1:0,2:1,3:0,4:0},totals:{1:3,2:3,3:3,4:3},remaining:[[3,4]],slots:2}));
assert(M.canQualify({target:1,pool:[1,2],wins:{1:7,2:7},totals:{1:9,2:8},remaining:[],slots:1,alternate:true}));
const rules={power_automatic:['ACC','Big Ten','Big 12','SEC'],group_automatic:['Conference USA','Mid-American'],notre_dame_top_12_guarantee:true,sun_belt_east:[]};
const conferences=['ACC','ACC','Big Ten','Big Ten','Big 12','Big 12','SEC','SEC','Conference USA','Conference USA','Mid-American','Mid-American','FBS Independents','FBS Independents'];
const teams=conferences.map((conference,i)=>({id:i===12?87:i+1,school:'Team '+i,conference,fbs:true})),roster=teams.map(t=>t.id);
const games=[];for(let i=0;i<12;i+=2)games.push({id:i+1,home:teams[i].id,away:teams[i+1].id,week:1,date:'2026-09-05T18:00:00Z',score:null,conference:true,championship:false});
const base={rules,year:2026,teams,roster,games,frames:[{week:null,label:'Preseason',elo:Object.fromEntries(roster.map(id=>[id,1500]))}]};
const projection=M.project(base,{iterations:500,seed:7});
assert.equal(projection.teams.reduce((n,t)=>n+t.playoffs,0),500*12);
assert.equal(projection.teams.reduce((n,t)=>n+t.championships,0),500);
assert.equal(projection.teams.reduce((n,t)=>n+t.conferenceWins,0),500*6);
assert(projection.teams.every(t=>t.elo===1500&&t.championships<=t.playoffs));
assert(projection.teams.filter(t=>t.conference==='FBS Independents').every(t=>t.conferenceWins===0));
assert.deepEqual(M.project(base,{iterations:500,seed:7}),projection);
let choice=M.setChoice(base,0,{},1,'win-out',true);assert.equal(choice.choices[1],1);
choice=M.setChoice(base,0,choice.choices,2,'win-next',true);assert.equal(choice.replaced,1);assert.equal(choice.choices[1],2);
const scenario=M.project(base,{choices:choice.choices,iterations:200,seed:7});assert.equal(scenario.teams.find(t=>t.id===1).elo,1484);assert.equal(scenario.teams.find(t=>t.id===2).elo,1516);
assert.equal(Object.keys(M.setChoice(base,0,choice.choices,2,'win-next',false).choices).length,0);
// CFP: all P4 champions, highest-ranked G6 team even when not a champion, and Notre Dame top-12 protection.
const cfpTeams=Array.from({length:22},(_,i)=>({id:i===11?87:i+100,conference:i===0?'Conference USA':'FBS Independents'}));
['ACC','Big Ten','Big 12','SEC'].forEach((c,k)=>cfpTeams[18+k].conference=c);
const champions=new Map(['ACC','Big Ten','Big 12','SEC'].map((c,k)=>[c,18+k]));
champions.set('Conference USA',17);cfpTeams[17].conference='Conference USA';
const field=M.selectField({ranking:cfpTeams.map((_,i)=>i),champions,teams:cfpTeams,rules});
assert.equal(field.length,12);for(const i of [0,11,18,19,20,21])assert(field.includes(i));assert(!field.includes(17));
const rounds=[];assert.equal(M.championship(Array.from({length:12},(_,i)=>i+1),(a,b)=>{rounds.push([a,b]);return Math.min(a,b);}),1);assert.equal(rounds.length,11);assert(rounds.slice(0,4).flat().every(i=>i>=5));
console.log(`Passed ${checks} exhaustive conference-elimination comparisons; mutually consistent picks, deterministic Elo and simulations, 2026 automatic bids/Notre Dame, fixed bracket, and probability conservation.`);
// Interval Elo bounds contain every ordered completion, not just Monte Carlo samples.
for(let trial=0;trial<30;trial++){
 const t=[{id:1},{id:2},{id:3},{id:4}],start=Float64Array.from(t,()=>1300+random()*400),future=[];
 for(let j=0;j<6;j++){const a=Math.floor(random()*4);let b=Math.floor(random()*3);if(b>=a)b++;future.push({id:j+1,a,b});}
 const fixed={};if(trial%2)fixed[future[2].id]=t[future[2].a].id;
 const bounds=M.ratingBounds(start,future,fixed,t);
 for(let mask=0;mask<64;mask++){
  const ratings=Float64Array.from(start);
  future.forEach((g,j)=>M.update(ratings,g.a,g.b,fixed[g.id]===undefined?Number(Boolean(mask&(1<<j))):Number(fixed[g.id]===t[g.a].id)));
  for(let i=0;i<4;i++)assert(ratings[i]>=bounds.low[i]-1e-8&&ratings[i]<=bounds.high[i]+1e-8);
 }
}
console.log('Passed 1,920 exhaustive rating completions against conservative elimination bounds.');
// Games after Selection Day can affect playoff strength, but cannot retroactively change qualification.
const lateData={...base,games:[...base.games,{id:999,home:1,away:3,week:15,date:'2026-12-12T18:00:00Z',score:null,conference:false,championship:false,after_selection:true}]};
const lateWin=M.project(lateData,{choices:{999:1},iterations:300,seed:11}),lateLoss=M.project(lateData,{choices:{999:3},iterations:300,seed:11});
assert.deepEqual(lateWin.teams.map(t=>t.playoffs),lateLoss.teams.map(t=>t.playoffs));
assert.notEqual(lateWin.teams.find(t=>t.id===1).elo,lateLoss.teams.find(t=>t.id===1).elo);
console.log('Passed Selection Day isolation for late regular-season scenario picks.');
