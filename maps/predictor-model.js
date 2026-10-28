/* Offline Elo scenario and 2026 CFP projection model. Also used directly by Node tests. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.CFBPredictor=api;})(typeof globalThis!=='undefined'?globalThis:self,function(){
  'use strict';
  const probability=(a,b)=>1/(1+10**((b-a)/400));
  function update(ratings,a,b,result){const change=32*(result-probability(ratings[a],ratings[b]));ratings[a]+=change;ratings[b]-=change;}
  function rng(seed){let x=(seed>>>0)||1;return ()=>{x=(Math.imul(1664525,x)+1013904223)>>>0;return x/4294967296;};}
  function maxflow(count,edges,source,sink){
    const adj=Array.from({length:count},()=>[]);
    for(const [a,b,capacity] of edges){const f={to:b,cap:capacity,rev:adj[b].length},r={to:a,cap:0,rev:adj[a].length};adj[a].push(f);adj[b].push(r);}
    let flow=0;
    for(;;){
      const level=Array(count).fill(-1),queue=[source];level[source]=0;
      for(let i=0;i<queue.length;i++)for(const e of adj[queue[i]])if(e.cap>0&&level[e.to]<0){level[e.to]=level[queue[i]]+1;queue.push(e.to);}
      if(level[sink]<0)return flow;
      const cursor=Array(count).fill(0);
      function send(a,limit){if(a===sink)return limit;for(;cursor[a]<adj[a].length;cursor[a]++){const e=adj[a][cursor[a]];if(e.cap>0&&level[e.to]===level[a]+1){const n=send(e.to,Math.min(limit,e.cap));if(n){e.cap-=n;adj[e.to][e.rev].cap+=n;return n;}}}return 0;}
      let n;while((n=send(source,1e9)))flow+=n;
    }
  }
  // Exact standings feasibility with optimistic tiebreaks: can this team reach a qualifying slot?
  function canQualify({target,pool,wins,totals,remaining,slots=2,alternate=false}){
    const members=new Set(pool),w={...wins},games=[];
    if(!members.has(target)||!totals[target])return false;
    for(const [a,b] of remaining){if(!members.has(a)&&!members.has(b))continue;if(a===target||b===target)w[target]=(w[target]||0)+1;else games.push([a,b]);}
    const targetWins=w[target]||0,targetTotal=totals[target],targetLosses=targetTotal-targetWins;
    const exemptOptions=slots===1?[null]:[null,...pool.filter(id=>id!==target)];
    const ids=[...new Set([...pool,...games.flat()])],index=new Map(ids.map((id,i)=>[id,i]));
    for(const exempt of exemptOptions){
      const caps={};let impossible=false;
      for(const id of ids){
        if(id===target||id===exempt||!members.has(id)){caps[id]=games.length;continue;}
        let allowed=targetWins*totals[id]/targetTotal;
        if(alternate&&totals[id]!==targetTotal)allowed=Math.max(allowed,targetWins,totals[id]-targetLosses);
        caps[id]=Math.floor(allowed-(w[id]||0)+1e-9);
        if(caps[id]<0){impossible=true;break;}
      }
      if(impossible)continue;
      const source=games.length+ids.length,sink=source+1,edges=[];
      games.forEach(([a,b],i)=>{edges.push([source,i,1],[i,games.length+index.get(a),1],[i,games.length+index.get(b),1]);});
      for(const id of ids)edges.push([games.length+index.get(id),sink,Math.max(0,caps[id])]);
      if(maxflow(sink+1,edges,source,sink)===games.length)return true;
    }
    return false;
  }
  // Each postgame rating is increasing in both pregame ratings for K=32, scale=400.
  // Propagating interval endpoints therefore bounds every completion, including fixed outcomes.
  function ratingBounds(base,future,choices,teams){
    const low=Float64Array.from(base),high=Float64Array.from(base);
    for(const g of future){
      const loA=low[g.a],loB=low[g.b],hiA=high[g.a],hiB=high[g.b],pLow=probability(loA,loB),pHigh=probability(hiA,hiB),fixed=choices[g.id];
      const home=fixed===undefined?null:fixed===teams[g.a].id;
      low[g.a]=loA+32*((home===null?0:Number(home))-pLow);
      high[g.a]=hiA+32*((home===null?1:Number(home))-pHigh);
      low[g.b]=loB+32*(pLow-(home===null?1:Number(home)));
      high[g.b]=hiB+32*(pHigh-(home===null?0:Number(home)));
    }
    return {low,high};
  }
  function prepare(data,frameIndex,choices={}){
    const frame=data.frames[frameIndex],teams=data.teams,ids=teams.map(t=>t.id),index=new Map(ids.map((id,i)=>[id,i]));
    const roster=data.roster.map(id=>index.get(id)),local=new Map(roster.map((i,j)=>[i,j])),m=roster.length,n=teams.length;
    const base=Float64Array.from(teams,t=>frame.elo[t.id]??1500),wins=new Float64Array(n),losses=new Float64Array(n),cw=new Float64Array(n),totals=new Int16Array(n),h2h=new Uint8Array(m*m),matches=new Uint8Array(m*m);
    const groups=new Map(),future=[],knownChampions=new Map();
    for(const i of roster){const c=teams[i].conference;if(c&&c!=='FBS Independents'){if(!groups.has(c))groups.set(c,[]);groups.get(c).push(i);}}
    const games=data.games.map(g=>({...g,a:index.get(g.home),b:index.get(g.away)}));
    for(const g of games){
      const known=frame.week!==null&&g.score&&g.week<=frame.week;
      if(g.championship){if(known){const winner=g.score[0]>g.score[1]?g.a:g.b;knownChampions.set(teams[winner].conference,winner);}continue;}
      if(g.conference){totals[g.a]++;totals[g.b]++;const a=local.get(g.a),b=local.get(g.b);matches[a*m+b]++;matches[b*m+a]++;}
      if(known){
        const result=g.score[0]>g.score[1]?1:g.score[0]<g.score[1]?0:.5;
        wins[g.a]+=result;wins[g.b]+=1-result;losses[g.a]+=1-result;losses[g.b]+=result;
        if(g.conference){cw[g.a]+=result;cw[g.b]+=1-result;h2h[local.get(g.a)*m+local.get(g.b)]+=2*result;h2h[local.get(g.b)*m+local.get(g.a)]+=2*(1-result);}
      }else future.push(g);
    }
    const validChoices={};for(const g of future)if(choices[g.id]===g.home||choices[g.id]===g.away)validChoices[g.id]=choices[g.id];
    const scenario=Float64Array.from(base),fixedCw=Float64Array.from(cw);
    for(const g of future)if(validChoices[g.id]!==undefined){const result=validChoices[g.id]===g.home?1:0;update(scenario,g.a,g.b,result);if(g.conference){fixedCw[g.a]+=result;fixedCw[g.b]+=1-result;}}
    const eliminated=new Set(),remaining=future.filter(g=>g.conference&&validChoices[g.id]===undefined).map(g=>[g.a,g.b]);
    const w=Object.fromEntries(roster.map(i=>[i,fixedCw[i]])),t=Object.fromEntries(roster.map(i=>[i,totals[i]]));
    const east=new Set(data.rules.sun_belt_east||[]);
    for(const [conf,members] of groups)for(const target of members){
      if(knownChampions.has(conf)){if(knownChampions.get(conf)!==target)eliminated.add(target);continue;}
      const pool=conf==='Sun Belt'?members.filter(i=>east.has(teams[i].id)===east.has(teams[target].id)):members;
      if(!canQualify({target,pool,wins:w,totals:t,remaining,slots:conf==='Sun Belt'?1:2,alternate:conf==='ACC'}))eliminated.add(target);
    }
    // Conservative Elo bounds prove a few selection impossibilities; sample zeros are not treated as proofs.
    const {low,high}=ratingBounds(base,future.filter(g=>!g.after_selection),validChoices,teams),beforeLow=Float64Array.from(low),beforeHigh=Float64Array.from(high);
    for(const [conf,members] of groups)if(!knownChampions.has(conf))for(const i of members)if(!eliminated.has(i)){
      const opponents=members.filter(j=>j!==i&&!eliminated.has(j));
      if(opponents.length){const weakest=Math.min(...opponents.map(j=>beforeLow[j])),strongest=Math.max(...opponents.map(j=>beforeHigh[j]));low[i]=beforeLow[i]-32*probability(beforeLow[i],weakest);high[i]=beforeHigh[i]+32*(1-probability(beforeHigh[i],strongest));}
    }
    const playoffOut=new Set(),power=new Set(data.rules.power_automatic),group=new Set(data.rules.group_automatic);
    for(const i of roster){
      const auto=power.has(teams[i].conference)&&!eliminated.has(i);
      const groupPossible=group.has(teams[i].conference)&&!roster.some(j=>j!==i&&group.has(teams[j].conference)&&low[j]>high[i]);
      if(!auto&&!groupPossible&&roster.filter(j=>j!==i&&low[j]>high[i]).length>=12)playoffOut.add(i);
    }
    return {data,frame,frameIndex,teams,ids,index,roster,local,m,n,base,wins,losses,cw,totals,h2h,matches,groups,future,choices:validChoices,scenario,eliminated,playoffOut,knownChampions};
  }
  function selectField({ranking,champions,teams,rules}){
    const size=rules.field_size||12;
    const selected=new Set(),power=new Set(rules.power_automatic),group=new Set(rules.group_automatic);
    for(const [conf,id] of champions)if(power.has(conf))selected.add(id);
    const groupBest=ranking.find(id=>group.has(teams[id].conference));if(groupBest!==undefined)selected.add(groupBest);
    const nd=ranking.slice(0,size).find(id=>teams[id].id===(rules.notre_dame_id||87));if(nd!==undefined&&rules.notre_dame_top_12_guarantee)selected.add(nd);
    for(const id of ranking){if(selected.size>=size)break;selected.add(id);}
    return ranking.filter(id=>selected.has(id)).slice(0,size);
  }
  function championship(field,play){
    if(field.length!==12)throw new Error('A projected playoff must contain 12 teams');
    const first=[play(field[4],field[11],1),play(field[5],field[10],1),play(field[6],field[9],1),play(field[7],field[8],1)];
    const quarters=[play(field[0],first[3]),play(field[3],first[0]),play(field[1],first[2]),play(field[2],first[1])];
    return play(play(quarters[0],quarters[1]),play(quarters[2],quarters[3]));
  }
  function conferenceFinalists(p,members,cw,h2h,lottery){
    const {teams,totals,local,m,matches}=p;
    function one(pool){
      let best=-1;for(const i of pool)best=Math.max(best,totals[i]?cw[i]/totals[i]:0);
      let tied=pool.filter(i=>Math.abs((totals[i]?cw[i]/totals[i]:0)-best)<1e-9);
      if(teams[pool[0]].conference==='ACC'){
        const leaders=[...tied];for(const i of pool)if(!tied.includes(i)&&leaders.some(j=>totals[i]!==totals[j]&&(cw[i]===cw[j]||totals[i]-cw[i]===totals[j]-cw[j])))tied.push(i);
      }
      if(tied.length===1)return tied[0];
      if(p.tiebreakWarnings)p.tiebreakWarnings.add(teams[pool[0]].conference);
      const complete=tied.every(i=>tied.every(j=>i===j||matches[local.get(i)*m+local.get(j)]));
      const common=members.filter(j=>tied.every(i=>i!==j&&matches[local.get(i)*m+local.get(j)]));
      function scores(i){const a=local.get(i);let head=0,headGames=0,commonScore=0,commonGames=0,opp=0,oppGames=0;
        for(const j of tied)if(j!==i){head+=h2h[a*m+local.get(j)];headGames+=matches[a*m+local.get(j)];}
        for(const j of common){commonScore+=h2h[a*m+local.get(j)];commonGames+=matches[a*m+local.get(j)];}
        for(const j of members)if(j!==i){const count=matches[a*m+local.get(j)];opp+=count*(totals[j]?cw[j]/totals[j]:0);oppGames+=count;}
        return [complete&&headGames?head/headGames:0,commonGames?commonScore/commonGames:0,oppGames?opp/oppGames:0,p.tiebreakWarnings?-teams[i].id:lottery[i]];
      }
      const scored=tied.map(i=>({i,score:scores(i)}));scored.sort((a,b)=>{for(let k=0;k<4;k++){const d=b.score[k]-a.score[k];if(Math.abs(d)>1e-9)return d;}return 0;});return scored[0].i;
    }
    const eligible=members.filter(i=>!p.eliminated.has(i));
    if(teams[members[0]].conference==='Sun Belt'){
      const east=new Set(p.data.rules.sun_belt_east);return [one(eligible.filter(i=>east.has(teams[i].id))),one(eligible.filter(i=>!east.has(teams[i].id)))];
    }
    const a=one(eligible);return [a,one(eligible.filter(i=>i!==a))];
  }
  function projectLegacy(data,options={},progress=()=>{}){
    const p=prepare(data,options.frameIndex??data.frames.length-1,options.choices||{}),iterations=options.iterations||2000,random=rng(options.seed||2026);
    const conf=new Uint32Array(p.n),playoff=new Uint32Array(p.n),title=new Uint32Array(p.n);
    function result(done){return {iterations:done,frameIndex:p.frameIndex,choices:p.choices,teams:p.roster.map(i=>({id:p.teams[i].id,elo:p.scenario[i],conference:p.teams[i].conference,conferenceWins:conf[i],playoffs:playoff[i],championships:title[i],conferenceOut:p.eliminated.has(i),playoffOut:p.playoffOut.has(i)}))};}
    for(let trial=0;trial<iterations;trial++){
      const ratings=Float64Array.from(p.base),cw=Float64Array.from(p.cw),h2h=Uint8Array.from(p.h2h),lottery=Float64Array.from({length:p.n},random);
      const draw=g=>{
        const roll=random(),forced=p.choices[g.id],win=forced===undefined?roll<probability(ratings[g.a],ratings[g.b]):forced===g.home;
        update(ratings,g.a,g.b,win?1:0);
        if(g.conference){cw[g.a]+=win?1:0;cw[g.b]+=win?0:1;h2h[p.local.get(g.a)*p.m+p.local.get(g.b)]+=win?2:0;h2h[p.local.get(g.b)*p.m+p.local.get(g.a)]+=win?0:2;}
      };
      for(const g of p.future)if(!g.after_selection)draw(g);
      const play=(a,b)=>{const win=random()<probability(ratings[a],ratings[b]);update(ratings,a,b,win?1:0);return win?a:b;};
      const champions=new Map();
      for(const [name,members] of p.groups){const known=p.knownChampions.get(name),winner=known!==undefined?known:play(...conferenceFinalists(p,members,cw,h2h,lottery));champions.set(name,winner);conf[winner]++;}
      const ranking=[...p.roster].sort((a,b)=>ratings[b]-ratings[a]||lottery[b]-lottery[a]);
      const field=selectField({ranking,champions,teams:p.teams,rules:data.rules});for(const i of field)playoff[i]++;
      for(const g of p.future)if(g.after_selection)draw(g);
      title[championship(field,play)]++;
      if((trial+1)%250===0)progress(result(trial+1));
    }
    return result(iterations);
  }
  function targets(data,frameIndex,teamId){const frame=data.frames[frameIndex];return data.games.filter(g=>!g.championship&&(!g.score||frame.week===null||g.week>frame.week)&&(g.home===teamId||g.away===teamId));}
  function setChoice(data,frameIndex,choices,teamId,mode,checked){
    const games=targets(data,frameIndex,teamId),selected=mode.endsWith('next')?games.slice(0,1):games,next={...choices};let replaced=0;
    for(const g of selected){const winner=mode.startsWith('win')?teamId:g.home===teamId?g.away:g.home;if(checked){if(next[g.id]!==undefined&&next[g.id]!==winner)replaced++;next[g.id]=winner;}else if(next[g.id]===winner)delete next[g.id];}
    return {choices:next,replaced};
  }
  // Predictive power and selection résumé are deliberately separate.
  const MODEL_VERSION='objective-sor-1';
  const normalCDF=x=>{const sign=x<0?-1:1,z=Math.abs(x)/Math.SQRT2,t=1/(1+.3275911*z),erf=1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-.284496736)*t+.254829592)*t*Math.exp(-z*z);return .5*(1+sign*erf);};
  function ratingProvider(data,frameIndex,method='sp'){
    const s=data.spSnapshot,frame=data.frames[frameIndex],now=Date.now(),stamp=Date.parse(s?.retrieved_at),age=(now-stamp)/86400000;
    const historical=frameIndex<data.frames.length-1&&(!frame.date||stamp>Date.parse(frame.date));
    const valid=s?.season===data.year&&s.scale?.verified&&s.ratings&&Object.keys(s.ratings).length>0&&Object.values(s.ratings).every(r=>Number.isFinite(r.rating)&&Math.abs(r.rating)<=100)&&age>=-1&&age<=10&&!historical;
    const useSP=method==='sp'&&valid;
    const values=data.teams.map(t=>useSP&&Number.isFinite(s.ratings[t.id]?.rating)?s.ratings[t.id].rating:null);
    return {method:useSP?'sp':'elo',requested:method,values,snapshot:useSP?s:null,
      message:method==='elo'?'Elo legacy prediction baseline':useSP?`SP+ fixed snapshot; ${s.coverage.matched}/${s.coverage.expected} FBS coverage. Missing opponents use the identified Elo baseline.`:
      historical?'Elo fallback: no SP+ snapshot available as of this historical week.':`Elo fallback: SP+ snapshot ${!s?'unavailable':age>10?'stale':'invalid'}.`};
  }
  function gameProbability(provider,a,b,ratings,site=0,calibration){
    if(provider.method!=='sp'||provider.values[a]===null||provider.values[b]===null){
      if(!calibration)return probability(ratings[a],ratings[b]);
      if(calibration.selected==='logistic')return 1/(1+Math.exp(-(calibration.logistic.elo_slope*(ratings[a]-ratings[b])+calibration.logistic.home_logit*site)));
      return normalCDF(((ratings[a]-ratings[b])*calibration.margin.elo_point_scale+calibration.margin.home_field*site)/calibration.margin.sigma);
    }
    const margin=provider.values[a]-provider.values[b]+calibration.margin.home_field*site;
    return calibration.selected==='logistic'?1/(1+Math.exp(-margin*calibration.logistic.elo_slope/calibration.margin.elo_point_scale)):normalCDF(margin/calibration.margin.sigma);
  }
  function logadd(a,b){if(a===-Infinity)return b;if(b===-Infinity)return a;const m=Math.max(a,b);return m+Math.log1p(Math.exp(Math.min(a,b)-m));}
  function sorDistribution(probabilities){
    let d=[0];
    for(const p of probabilities){if(!Number.isFinite(p)||p<0||p>1)throw Error('Invalid reference game probability');const next=Array(d.length+1).fill(-Infinity),w=p===0?-Infinity:Math.log(p),l=p===1?-Infinity:Math.log1p(-p);
      for(let j=0;j<d.length;j++){next[j]=logadd(next[j],d[j]+l);next[j+1]=logadd(next[j+1],d[j]+w);}d=next;}
    const tails=Array(d.length);let total=-Infinity;for(let j=d.length-1;j>=0;j--){total=logadd(total,d[j]);tails[j]=Math.max(0,-total);}return tails;
  }
  function objectiveRanking(roster,resumes,teams,h2h,tolerance=Math.log(1.01)){
    const ordered=[...roster].sort((a,b)=>resumes[b].sor-resumes[a].sor||teams[a].id-teams[b].id),answer=[];
    // Anchor near-tie groups to the best remaining score; avoids a non-transitive epsilon comparator.
    for(let at=0;at<ordered.length;){let end=at+1;while(end<ordered.length&&resumes[ordered[at]].sor-resumes[ordered[end]].sor<=tolerance)end++;
      const group=ordered.slice(at,end),head=i=>group.reduce((n,j)=>n+(h2h?.get(`${i}:${j}`)||0)-(h2h?.get(`${j}:${i}`)||0),0);
      group.sort((a,b)=>resumes[b].sos-resumes[a].sos||head(b)-head(a)||resumes[b].power-resumes[a].power||teams[a].id-teams[b].id);answer.push(...group);at=end;
    }return answer;
  }
  // Counter-based common random draws: changing a pick or a title matchup never shifts other games' draws.
  function commonDraw(seed,trial,key){let x=(seed^Math.imul(trial+1,0x9e3779b1))>>>0;for(let j=0;j<String(key).length;j++)x=Math.imul(x^String(key).charCodeAt(j),16777619)>>>0;x^=x>>>16;x=Math.imul(x,0x7feb352d);x^=x>>>15;x=Math.imul(x,0x846ca68b);x^=x>>>16;return (x>>>0)/4294967296;}
  function projectObjective(data,options={},progress=()=>{}){
    const p=prepare(data,options.frameIndex??data.frames.length-1,options.choices||{}),provider=ratingProvider(data,p.frameIndex,options.method||'sp'),cal=data.calibration;
    if(!cal)throw Error('Saved calibration is required for objective projections');
    const config={reference_sp:20,reference_elo:1625,sor_tolerance:Math.log(1.01),...data.objective,...options.modelConfig};
    const seed=options.seed??2026,iterations=options.iterations??50000;
    if(!Number.isInteger(iterations)||iterations<1||iterations>200000)throw Error('Invalid simulation count');
    p.playoffOut.clear(); // Elo bounds cannot prove SOR elimination.
    p.tiebreakWarnings=new Set();
    const selectionResolved=p.future.filter(g=>!g.after_selection).length===0&&[...p.groups.keys()].every(c=>p.knownChampions.has(c));
    const relevant=p.data.games.filter(g=>!g.after_selection&&(g.score&&p.frame.week!==null&&g.week<=p.frame.week||!g.championship)&& (data.roster.includes(g.home)||data.roster.includes(g.away))).map(g=>({...g,a:p.index.get(g.home),b:p.index.get(g.away)}));
    const scheduled=p.future.filter(g=>!g.after_selection&&(p.local.has(g.a)||p.local.has(g.b)));
    const proofKeys=[...scheduled.filter(g=>p.choices[g.id]===undefined).map(g=>'g'+g.id),...[...p.groups.keys()].filter(c=>!p.knownChampions.has(c)).map(c=>'c'+c)];
    const proofSlots=new Map(proofKeys.map((k,j)=>[k,j])),sample=(trial,key)=>options.enumerate&&proofSlots.has(key)?((trial>>>proofSlots.get(key))&1):commonDraw(seed,trial,key);
    if(options.enumerate&&proofKeys.length>10)throw Error('Exact proof enumeration is limited to ten uncertain regular/title results');
    const conf=new Uint32Array(p.n),playoff=new Uint32Array(p.n),title=new Uint32Array(p.n),auto=new Uint32Array(p.n),atlarge=new Uint32Array(p.n),byes=new Uint32Array(p.n),winSum=new Float64Array(p.n),lossSum=new Float64Array(p.n),rankSum=new Float64Array(p.n),champParticipants=new Uint32Array(p.n);
    const reference=(opponent,site)=>{
      const sp=provider.method==='sp'&&provider.values[opponent]!==null;
      if(sp){const margin=config.reference_sp-provider.values[opponent]+cal.margin.home_field*site;return cal.selected==='logistic'?1/(1+Math.exp(-margin*cal.logistic.elo_slope/cal.margin.elo_point_scale)):normalCDF(margin/cal.margin.sigma);}
      return cal.selected==='logistic'?1/(1+Math.exp(-(cal.logistic.elo_slope*(config.reference_elo-p.base[opponent])+cal.logistic.home_logit*site))):normalCDF(((config.reference_elo-p.base[opponent])*cal.margin.elo_point_scale+cal.margin.home_field*site)/cal.margin.sigma);
    };
    const refSchedules=Array.from({length:p.n},()=>[]),observedSchedules=Array.from({length:p.n},()=>[]),observedWins=new Float64Array(p.n),observedLosses=new Float64Array(p.n),observedCw=new Float64Array(p.n),observedCl=new Float64Array(p.n),actualTitle=new Map(),observedHead=new Map(),quality=new Uint16Array(p.n),weakLosses=new Uint16Array(p.n);
    const power=i=>provider.method==='sp'&&provider.values[i]!==null?provider.values[i]:(p.base[i]-1500)*cal.margin.elo_point_scale;
    const powerOrder=[...p.roster].sort((a,b)=>power(b)-power(a)||p.teams[a].id-p.teams[b].id),powerRanks=new Map(powerOrder.map((i,j)=>[i,j+1])),top=new Set(powerOrder.slice(0,config.quality_win_top_n||25));
    const probs=new Map(),champCache=new Map(),titleMatchups=new Map();let fallbackGames=0;
    for(const g of p.data.games.filter(g=>g.championship)){titleMatchups.set([g.home,g.away].sort((a,b)=>a-b).join(':'),g);}
    const lateGames=p.future.filter(g=>g.after_selection),homeTitles=new Set(data.rules.championship_home_conferences||[]);
    for(const g of relevant){const site=g.neutral?0:1,pa=reference(g.b,site),pb=reference(g.a,-site);refSchedules[g.a].push(pa);refSchedules[g.b].push(pb);
      const observed=g.score&&p.frame.week!==null&&g.week<=p.frame.week,fixed=!observed&&p.choices[g.id]!==undefined;
      if(observed||fixed){const winner=observed?(g.score[0]>g.score[1]?g.a:g.b):p.choices[g.id]===g.home?g.a:g.b,loser=winner===g.a?g.b:g.a;
        observedSchedules[g.a].push(pa);observedSchedules[g.b].push(pb);observedWins[winner]++;observedLosses[loser]++;if(g.conference){observedCw[winner]++;observedCl[loser]++;}if(observed&&g.championship){actualTitle.set(winner,'Won');actualTitle.set(loser,'Lost');}
        observedHead.set(`${winner}:${loser}`,(observedHead.get(`${winner}:${loser}`)||0)+1);if(top.has(loser))quality[winner]++;if(power(loser)>power(winner))weakLosses[loser]++;
      }
      if(provider.method==='sp'&&(provider.values[g.a]===null||provider.values[g.b]===null))fallbackGames++;
      probs.set(g.id,gameProbability(provider,g.a,g.b,p.base,site,cal));
    }
    const baseSOS=refSchedules.map(s=>s.length?1-s.reduce((a,b)=>a+b,0)/s.length:0);
    const tables=refSchedules.map(sorDistribution),observed=observedSchedules.map((s,i)=>({sor:sorDistribution(s)[observedWins[i]],sos:s.length?1-s.reduce((a,b)=>a+b,0)/s.length:0,power:power(i)}));
    const rawSorRanks=new Map([...p.roster].sort((a,b)=>observed[b].sor-observed[a].sor||p.teams[a].id-p.teams[b].id).map((i,j)=>[i,j+1]));
    const observedRanking=objectiveRanking(p.roster,observed,p.teams,observedHead,config.sor_tolerance),observedRanks=new Map(observedRanking.map((i,j)=>[i,j+1]));
    const eligibleChampChoices={};for(const g of p.data.games.filter(g=>g.championship&&!(g.score&&p.frame.week!==null&&g.week<=p.frame.week)))if(options.choices?.[g.id]===g.home||options.choices?.[g.id]===g.away)eligibleChampChoices[g.id]=options.choices[g.id];
    function result(done){return {iterations:done,frameIndex:p.frameIndex,choices:{...p.choices,...eligibleChampChoices},method:provider.method,ratingMessage:provider.message,modelVersion:MODEL_VERSION,snapshot:provider.snapshot?.retrieved_at||null,fallbackGames,
      warnings:[...p.tiebreakWarnings].sort().map(c=>`${c}: conference tiebreaker approximation used; complete official rule sequence unavailable.`),
      teams:p.roster.map(i=>({id:p.teams[i].id,elo:p.scenario[i],sp:provider.values[i],powerRank:powerRanks.get(i),objectiveRank:observedRanks.get(i),sorRank:rawSorRanks.get(i),sor:observed[i].sor,sos:observed[i].sos,record:{wins:observedWins[i],losses:observedLosses[i]},qualityWins:quality[i],weakLosses:weakLosses[i],standingWins:observedCw[i],standingLosses:observedCl[i],conferenceTitleResult:actualTitle.get(i)||(p.knownChampions.has(p.teams[i].conference)?'Did not participate':'Not yet played'),
        headToHead:[...observedHead].filter(([k])=>k.startsWith(i+':')||k.endsWith(':'+i)).map(([k,wins])=>({winner:p.teams[Number(k.split(':')[0])].id,loser:p.teams[Number(k.split(':')[1])].id,wins})),
        projectedWins:done?winSum[i]/done:observedWins[i],projectedLosses:done?lossSum[i]/done:observedLosses[i],projectedRank:done?rankSum[i]/done:observedRanks.get(i),conference:p.teams[i].conference,conferenceWins:conf[i],conferenceFinals:champParticipants[i],playoffs:playoff[i],automatic:auto[i],atlarge:atlarge[i],byes:byes[i],championships:title[i],conferenceOut:p.eliminated.has(i),playoffOut:selectionResolved&&done>0&&playoff[i]===0,playoffClinched:selectionResolved&&done>0&&playoff[i]===done}))};}
    for(let trial=0;trial<iterations;trial++){
      const ratings=Float64Array.from(p.base),cw=Float64Array.from(p.cw),h2h=Uint8Array.from(p.h2h),wins=new Float64Array(p.n),losses=new Float64Array(p.n),head=new Map();
      const apply=(g,win)=>{const a=win?g.a:g.b,b=win?g.b:g.a;wins[a]++;losses[b]++;head.set(`${a}:${b}`,(head.get(`${a}:${b}`)||0)+1);};
      for(const g of relevant)if(g.score&&p.frame.week!==null&&g.week<=p.frame.week)apply(g,g.score[0]>g.score[1]);
      for(const g of scheduled){const forced=p.choices[g.id],win=forced===undefined?sample(trial,'g'+g.id)<(provider.method==='sp'&&provider.values[g.a]!==null&&provider.values[g.b]!==null?probs.get(g.id):gameProbability(provider,g.a,g.b,ratings,g.neutral?0:1,cal)):forced===g.home;apply(g,win);
        if(provider.method==='elo')update(ratings,g.a,g.b,Number(win));
        if(g.conference){cw[g.a]+=Number(win);cw[g.b]+=Number(!win);h2h[p.local.get(g.a)*p.m+p.local.get(g.b)]+=win?2:0;h2h[p.local.get(g.b)*p.m+p.local.get(g.a)]+=win?0:2;}
      }
      const champions=new Map(),extra=new Map();
      for(const [name,members] of p.groups){const known=p.knownChampions.get(name);let winner=known;
        if(known===undefined){const [a,b]=conferenceFinalists(p,members,cw,h2h,new Float64Array(p.n));if(a===undefined||b===undefined)throw Error(`Cannot determine championship participants: ${name}`);
          champParticipants[a]++;champParticipants[b]++;
          const game=titleMatchups.get([p.teams[a].id,p.teams[b].id].sort((a,b)=>a-b).join(':'));
          const fixed=game&&eligibleChampChoices[game.id],site=game?(game.neutral?0:game.home===p.teams[a].id?1:-1):homeTitles.has(name)?1:0;
          winner=fixed!==undefined?p.index.get(fixed):sample(trial,'c'+name)<gameProbability(provider,a,b,ratings,site,cal)?a:b;
          const loser=winner===a?b:a;apply({a,b},winner===a);if(provider.method==='elo')update(ratings,a,b,Number(winner===a));
          extra.set(a,{opponent:b,site});extra.set(b,{opponent:a,site:-site});
        }champions.set(name,winner);conf[winner]++;
      }
      const resumes=Array(p.n);
      for(const i of p.roster){let table=tables[i],schedule=refSchedules[i],e=extra.get(i);if(e){const key=`${i}:${e.opponent}:${e.site}`;if(!champCache.has(key)){const all=[...schedule,reference(e.opponent,e.site)];champCache.set(key,{table:sorDistribution(all),sos:1-all.reduce((a,b)=>a+b,0)/all.length});}const cached=champCache.get(key);resumes[i]={sor:cached.table[wins[i]],sos:cached.sos,power:power(i)};}
        else resumes[i]={sor:table[wins[i]],sos:baseSOS[i],power:power(i)};
        winSum[i]+=wins[i];lossSum[i]+=losses[i];
      }
      const ranking=objectiveRanking(p.roster,resumes,p.teams,head,config.sor_tolerance);ranking.forEach((i,j)=>rankSum[i]+=j+1);
      const field=selectField({ranking,champions,teams:p.teams,rules:data.rules}),automatic=new Set();
      for(const [name,i] of champions)if(data.rules.power_automatic.includes(name))automatic.add(i);
      const group=ranking.find(i=>data.rules.group_automatic.includes(p.teams[i].conference));if(group!==undefined)automatic.add(group);
      const nd=ranking.slice(0,data.rules.field_size||12).find(i=>p.teams[i].id===(data.rules.notre_dame_id||87));if(nd!==undefined&&data.rules.notre_dame_top_12_guarantee)automatic.add(nd);
      for(const i of field){playoff[i]++;if(automatic.has(i))auto[i]++;else atlarge[i]++;}field.slice(0,data.rules.byes||4).forEach(i=>byes[i]++);
      // Late games cannot change selection; Elo may update playoff strength afterwards.
      for(const g of lateGames)if(provider.method==='elo'){const forced=p.choices[g.id],win=forced===undefined?sample(trial,'g'+g.id)<gameProbability(provider,g.a,g.b,ratings,g.neutral?0:1,cal):forced===g.home;update(ratings,g.a,g.b,Number(win));}
      if(!options.enumerate)title[championship(field,(a,b,site=0)=>{const win=commonDraw(seed,trial,`p${a}:${b}`)<gameProbability(provider,a,b,ratings,site,cal);if(provider.method==='elo')update(ratings,a,b,Number(win));return win?a:b;})]++;
      if((trial+1)%500===0)progress(result(trial+1));
    }
    const answer=result(iterations);
    if(!options.enumerate&&!selectionResolved&&proofKeys.length<=10){
      const proof=projectObjective(data,{...options,enumerate:true,iterations:2**proofKeys.length},()=>{}),byId=new Map(proof.teams.map(t=>[t.id,t]));
      for(const team of answer.teams){const exact=byId.get(team.id);team.playoffOut=exact.playoffs===0;team.playoffClinched=exact.playoffs===proof.iterations;}
      answer.proof={method:'Exhaustive modeled regular/title outcome enumeration',completions:proof.iterations};
    }else if(selectionResolved)answer.proof={method:'Selection resolved from completed results',completions:1};
    return answer;
  }

  const project=(data,options={},progress=()=>{})=>(data.objective?projectObjective:projectLegacy)(data,options,progress);
  return {MODEL_VERSION,normalCDF,ratingProvider,gameProbability,sorDistribution,objectiveRanking,commonDraw,projectObjective,projectLegacy,probability,update,rng,maxflow,canQualify,ratingBounds,prepare,selectField,championship,conferenceFinalists,project,targets,setChoice};
});
