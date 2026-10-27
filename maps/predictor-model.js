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
    const selected=new Set(),power=new Set(rules.power_automatic),group=new Set(rules.group_automatic);
    for(const [conf,id] of champions)if(power.has(conf))selected.add(id);
    const groupBest=ranking.find(id=>group.has(teams[id].conference));if(groupBest!==undefined)selected.add(groupBest);
    const nd=ranking.slice(0,12).find(id=>teams[id].id===87);if(nd!==undefined&&rules.notre_dame_top_12_guarantee)selected.add(nd);
    for(const id of ranking){if(selected.size>=12)break;selected.add(id);}
    return ranking.filter(id=>selected.has(id)).slice(0,12);
  }
  function championship(field,play){
    if(field.length!==12)throw new Error('A projected playoff must contain 12 teams');
    const first=[play(field[4],field[11]),play(field[5],field[10]),play(field[6],field[9]),play(field[7],field[8])];
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
      const complete=tied.every(i=>tied.every(j=>i===j||matches[local.get(i)*m+local.get(j)]));
      const common=members.filter(j=>tied.every(i=>i!==j&&matches[local.get(i)*m+local.get(j)]));
      function scores(i){const a=local.get(i);let head=0,headGames=0,commonScore=0,commonGames=0,opp=0,oppGames=0;
        for(const j of tied)if(j!==i){head+=h2h[a*m+local.get(j)];headGames+=matches[a*m+local.get(j)];}
        for(const j of common){commonScore+=h2h[a*m+local.get(j)];commonGames+=matches[a*m+local.get(j)];}
        for(const j of members)if(j!==i){const count=matches[a*m+local.get(j)];opp+=count*(totals[j]?cw[j]/totals[j]:0);oppGames+=count;}
        return [complete&&headGames?head/headGames:0,commonGames?commonScore/commonGames:0,oppGames?opp/oppGames:0,lottery[i]];
      }
      const scored=tied.map(i=>({i,score:scores(i)}));scored.sort((a,b)=>{for(let k=0;k<4;k++){const d=b.score[k]-a.score[k];if(Math.abs(d)>1e-9)return d;}return 0;});return scored[0].i;
    }
    const eligible=members.filter(i=>!p.eliminated.has(i));
    if(teams[members[0]].conference==='Sun Belt'){
      const east=new Set(p.data.rules.sun_belt_east);return [one(eligible.filter(i=>east.has(teams[i].id))),one(eligible.filter(i=>!east.has(teams[i].id)))];
    }
    const a=one(eligible);return [a,one(eligible.filter(i=>i!==a))];
  }
  function project(data,options={},progress=()=>{}){
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
  return {probability,update,rng,maxflow,canQualify,ratingBounds,prepare,selectField,championship,conferenceFinalists,project,targets,setChoice};
});
