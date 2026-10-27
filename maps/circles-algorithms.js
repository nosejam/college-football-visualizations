/* Pure graph operations shared by the browser, its search worker, and Node tests. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.CFBCycles=api;})(typeof globalThis!=='undefined'?globalThis:self,function(){
  'use strict';
  const key=(a,b)=>`${a}:${b}`;
  const clock=()=>typeof performance!=='undefined'?performance.now():Date.now();
  function graph(nodes,edges){
    const ids=[...new Set(nodes)].sort((a,b)=>a-b),allowed=new Set(ids);
    const adj=new Map(ids.map(id=>[id,new Set()])),rev=new Map(ids.map(id=>[id,new Set()]));
    for(const edge of edges){const [a,b]=Array.isArray(edge)?edge:[edge.source,edge.target];if(a!==b&&allowed.has(a)&&allowed.has(b)){adj.get(a).add(b);rev.get(b).add(a);}}
    return {nodes:ids,adj,rev};
  }
  function components(g){
    const seen=new Set(),order=[],parts=[];
    function visit(id){seen.add(id);for(const next of g.adj.get(id))if(!seen.has(next))visit(next);order.push(id);}
    for(const id of g.nodes)if(!seen.has(id))visit(id);
    seen.clear();
    function collect(id,part){seen.add(id);part.push(id);for(const next of g.rev.get(id))if(!seen.has(next))collect(next,part);}
    for(const id of order.reverse())if(!seen.has(id)){const part=[];collect(id,part);parts.push(part.sort((a,b)=>a-b));}
    return parts.sort((a,b)=>b.length-a.length||a[0]-b[0]);
  }
  function canonical(cycle){if(!cycle.length)return [];const index=cycle.indexOf(Math.min(...cycle));return cycle.slice(index).concat(cycle.slice(0,index));}
  function valid(cycle,g,minimum=3,required=null){
    return cycle.length>=minimum&&new Set(cycle).size===cycle.length&&requirements(required).every(id=>cycle.includes(id))&&cycle.every((id,i)=>g.adj.get(id)?.has(cycle[(i+1)%cycle.length]));
  }
  function shortest(g,minimum=3,required=null){
    let best=[];
    for(const start of required===null?g.nodes:[required]){
      if(!g.adj.has(start))continue;
      for(const first of g.adj.get(start)){
        const parents=new Map([[first,null]]),queue=[first];let found=false;
        for(let i=0;i<queue.length&&!found;i++){
          const here=queue[i];
          for(const next of g.adj.get(here)){
            if(next===start){
              if(minimum===3&&here===first)continue;
              const path=[here];while(parents.get(path.at(-1))!==null)path.push(parents.get(path.at(-1)));
              const cycle=canonical([start,...path.reverse()]);
              if(!best.length||cycle.length<best.length)best=cycle;
              found=true;break;
            }
            if(!parents.has(next)){parents.set(next,here);queue.push(next);}
          }
        }
        if(best.length===minimum)return best;
      }
    }
    return best;
  }
  function neighborhood(nodes,edges,root,depth=1){
    if(root===null)return {nodes:[...nodes],edges:[...edges],maxDepth:0,componentSize:nodes.length};
    const g=graph(nodes,edges),distance=new Map([[root,0]]),queue=g.adj.has(root)?[root]:[];
    for(let i=0;i<queue.length;i++){
      const here=queue[i];for(const other of new Set([...g.adj.get(here),...g.rev.get(here)]))if(!distance.has(other)){distance.set(other,distance.get(here)+1);queue.push(other);}
    }
    const selected=new Set(queue.filter(id=>distance.get(id)<=depth));
    return {nodes:nodes.filter(id=>selected.has(id)),edges:edges.filter(e=>selected.has(e.source??e[0])&&selected.has(e.target??e[1])),
      maxDepth:queue.length?Math.max(...distance.values()):0,componentSize:queue.length,distances:distance};
  }
  function search(options,onProgress=()=>{}){
    const {nodes,edges,minimum=3,required=null,timeLimitMs=1800,hint=null,hintExact=false,upperHint=null,seed=1}=options;
    const started=clock(),deadline=started+timeLimitMs,g=graph(nodes,edges),small=shortest(g,minimum,required);
    if(!small.length)return {shortest:[],largest:[],exact:true,upperBound:0,explored:0,timedOut:false};
    const parts=components(g).filter(c=>c.length>=minimum&&(required===null||c.includes(required)));
    let best=[...small],upperBound=Math.max(...parts.map(p=>p.length)),explored=0,timedOut=false,lastProgress=started;
    if(hint&&valid(hint,g,minimum,required)&&hint.length>best.length)best=canonical(hint);
    if(upperHint!==null&&Number.isFinite(upperHint))upperBound=Math.max(best.length,Math.min(upperBound,upperHint));
    if(hintExact&&hint&&valid(hint,g,minimum,required))return {shortest:small,largest:canonical(hint),exact:true,upperBound:hint.length,explored:0,timedOut:false};
    const result=exact=>({shortest:small,largest:[...best],exact,upperBound:exact?best.length:upperBound,explored,timedOut});
    onProgress(result(best.length===upperBound));
    if(best.length===upperBound)return result(true);
    let randomState=(seed>>>0)||1;
    function random(){randomState^=randomState<<13;randomState^=randomState>>>17;randomState^=randomState<<5;return (randomState>>>0)/4294967296;}
    let finished=false;
    for(const part of parts){
      if(part.length<=best.length)continue;
      const inPart=new Set(part),adj=new Map(part.map(id=>[id,[...g.adj.get(id)].filter(n=>inPart.has(n)).map(n=>({n,rank:random()})).sort((a,b)=>a.rank-b.rank).map(x=>x.n)]));
      const starts=required===null?[...part]:[required];
      for(const start of starts){
        if(clock()>=deadline){timedOut=true;finished=true;break;}
        const path=[start],used=new Set(path);
        function allowed(id,current){return inPart.has(id)&&(required!==null||id>=start)&&(!used.has(id)||id===current||id===start);}
        function canImprove(current){
          const forward=new Set([current]),queue=[current];
          for(let i=0;i<queue.length;i++)for(const next of g.adj.get(queue[i]))if(allowed(next,current)&&!forward.has(next)){forward.add(next);queue.push(next);}
          if(!forward.has(start))return false;
          const reverse=new Set([start]),back=[start];
          for(let i=0;i<back.length;i++)for(const next of g.rev.get(back[i]))if(allowed(next,current)&&!reverse.has(next)){reverse.add(next);back.push(next);}
          let remaining=0;for(const id of forward)if(!used.has(id)&&reverse.has(id))remaining++;
          return path.length+remaining>best.length;
        }
        function visit(current){
          explored++;
          if((explored&127)===0){
            const now=clock();if(now>=deadline){timedOut=true;finished=true;return;}
            if(now-lastProgress>250){onProgress(result(false));lastProgress=now;}
          }
          if(path.length>=minimum&&g.adj.get(current).has(start)&&path.length>best.length){best=canonical([...path]);if(best.length===upperBound){finished=true;return;}}
          if((explored&15)===0&&!canImprove(current))return;
          for(const next of adj.get(current)){
            if(finished)return;
            if(next===start||used.has(next)||(required===null&&next<start))continue;
            used.add(next);path.push(next);visit(next);path.pop();used.delete(next);
          }
        }
        visit(start);
        if(finished)break;
      }
      if(finished)break;
    }
    return result(!timedOut||best.length===upperBound);
  }
  function findLength(options,onProgress=()=>{}){
    const {nodes,edges,length,minimum=2,required=null,timeLimitMs=1800,maxCycles=50,existing=[]}=options;
    if(!Number.isInteger(length)||length<minimum)throw new Error(`Choose a whole-number circle size of at least ${minimum}.`);
    const needed=requirements(required),g=graph(nodes,edges),parts=components(g).filter(c=>c.length>=length&&needed.every(id=>c.includes(id)));
    const cycles=[],keys=new Set();let explored=0,timedOut=false,limited=false,finished=false;
    const started=clock(),deadline=started+timeLimitMs;let lastProgress=started;
    function record(path){if(!needed.every(id=>path.includes(id)))return;const cycle=canonical([...path]),id=cycle.join(':');if(!keys.has(id)){keys.add(id);cycles.push(cycle);}}
    for(const candidate of existing)if(candidate.length===length&&valid(candidate,g,minimum,required))record(candidate);
    const result=()=>({mode:'length',length,cycles:cycles.map(c=>[...c]),exhausted:!timedOut&&!limited,exact:cycles.length>0||(!timedOut&&!limited),timedOut,limited,explored});
    for(const part of parts){
      const inside=new Set(part),adj=new Map(part.map(n=>[n,[...g.adj.get(n)].filter(x=>inside.has(x)).sort((a,b)=>a-b)]));
      for(const start of needed.length?[needed[0]]:part){
        if(clock()>=deadline){timedOut=true;finished=true;break;}
        const used=new Set([start]),path=[start];
        // Shortest return distances are a safe lower bound for closing a path.
        const back=new Map([[start,0]]),queue=[start];
        for(let i=0;i<queue.length;i++)for(const previous of g.rev.get(queue[i]))if(inside.has(previous)&&!back.has(previous)){back.set(previous,back.get(queue[i])+1);queue.push(previous);}
        function visit(current){
          explored++;
          if((explored&127)===0){const now=clock();if(now>=deadline){timedOut=true;finished=true;return;}if(now-lastProgress>250){onProgress(result());lastProgress=now;}}
          if(path.length===length){if(g.adj.get(current).has(start))record(path);if(cycles.length>=maxCycles){limited=true;finished=true;}return;}
          if(!back.has(current)||back.get(current)>length-path.length+1)return;
          for(const next of adj.get(current)){
            if(finished)return;
            if(next===start||used.has(next)||(!needed.length&&next<start))continue;
            if(path.length===length-1&&!g.adj.get(next).has(start))continue;
            used.add(next);path.push(next);visit(next);path.pop();used.delete(next);
          }
        }
        visit(start);if(finished)break;
      }
      if(finished)break;
    }
    return result();
  }
  const requirements=value=>value==null?[]:[...new Set(Array.isArray(value)?value:[value])];
  // Connections follow played games in either direction, while retaining actual win arrows.
  function connection(nodes,edges,selected){
    const g=graph(nodes,edges),roots=requirements(selected),paths=[],pairs=new Set(),chosen=new Set(roots);
    function pathBetween(a,b){
      if(!g.adj.has(a)||!g.adj.has(b))return null;
      const parent=new Map([[a,null]]),queue=[a];
      for(let i=0;i<queue.length&&!parent.has(b);i++)for(const next of [...new Set([...g.adj.get(queue[i]),...g.rev.get(queue[i])])].sort((x,y)=>x-y))if(!parent.has(next)){parent.set(next,queue[i]);queue.push(next);}
      if(!parent.has(b))return null;
      const path=[b];while(parent.get(path.at(-1))!==null)path.push(parent.get(path.at(-1)));return path.reverse();
    }
    let connected=true;
    for(const other of roots.slice(1)){
      const path=pathBetween(roots[0],other);if(!path){connected=false;continue;}paths.push(path);
      path.forEach(id=>chosen.add(id));for(let i=1;i<path.length;i++){pairs.add(key(path[i-1],path[i]));pairs.add(key(path[i],path[i-1]));}
    }
    if(roots.length===1||!connected){
      for(const root of roots)for(const next of [...(g.adj.get(root)||[]),...(g.rev.get(root)||[])]){chosen.add(next);pairs.add(key(root,next));pairs.add(key(next,root));}
    }
    return {nodes:[...chosen],edges:edges.filter(e=>pairs.has(key(e.source??e[0],e.target??e[1]))),paths,connected};
  }
  function catalog(options,onProgress=()=>{}){
    const {nodes,edges,minimum=2,timeLimitMs=1800,maxListed=50,maxFound=5000,existing=[],hints=[]}=options;
    const required=requirements(options.required),g=graph(nodes,edges),startTime=clock(),deadline=startTime+timeLimitMs;
    const parts=components(g).filter(p=>p.length>=minimum&&required.every(id=>p.includes(id)));
    const keys=new Set(),all=[],low=[],high=[];let count=0,explored=0,timedOut=false,limited=false,finished=false;
    const order=(a,b)=>a.length-b.length||a.join(':').localeCompare(b.join(':'));
    function record(path){
      if(!valid(path,g,minimum,required))return;
      const cycle=canonical(path),id=cycle.join(':');if(keys.has(id))return;keys.add(id);count++;
      if(all.length<maxListed)all.push(cycle);
      low.push(cycle);low.sort(order);low.splice(5);
      high.push(cycle);high.sort((a,b)=>-order(a,b));high.splice(5);
    }
    for(const hint of [...existing,...hints])record(hint);
    let knownSmall=[];
    if(required.length<=1){knownSmall=shortest(g,minimum,required[0]??null);if(knownSmall.length)record(knownSmall);}
    // Collect short alternatives before depth-first enumeration spends its budget on long paths.
    const shortDeadline=Math.min(deadline,clock()+timeLimitMs*.2);
    for(let size=Math.max(minimum,required.length,knownSmall.length);size<=nodes.length&&low.length<5&&clock()<shortDeadline;size++){
      const found=findLength({nodes,edges,minimum,required,length:size,maxCycles:5,timeLimitMs:Math.min(80,shortDeadline-clock())});
      for(const cycle of found.cycles)record(cycle);
    }
    const largestHint=options.hint;
    if(largestHint)record(largestHint);
    // A shortcut in a known long cycle gives another verified, usually long, alternative.
    if(largestHint&&valid(largestHint,g,minimum,required))for(let i=0;i<largestHint.length;i++){
      const shorter=largestHint.filter((_,j)=>i!==j);record(shorter);
    }
    const knownMax=Boolean(options.hintExact&&largestHint&&valid(largestHint,g,minimum,required));
    const upperBound=parts.length?Math.max(...parts.map(p=>p.length)):0;
    // Spend part of the budget on long-cycle search before enumerating alternatives.
    if(required.length<=1&&knownSmall.length&&!knownMax&&clock()<deadline){
      const extrema=search({nodes,edges,minimum,required:required[0]??null,timeLimitMs:Math.max(0,(deadline-clock())*.35),hint:high[0],seed:options.seed||1});
      if(extrema.largest.length)record(extrema.largest);
    }
    function result(){
      const listed=count<=maxListed?[...all].sort(order):[...new Map([...high,...low].map(c=>[c.join(':'),c])).values()];
      const exhaustive=!timedOut&&!limited;
      return {mode:'catalog',cycles:listed,count,collapsed:count>maxListed,exhausted:exhaustive,timedOut,limited,explored,
        shortest:low[0]||[],largest:high[0]||[],shortestExact:exhaustive||Boolean(knownSmall.length)||Boolean(low.length&&low[0].length===Math.max(minimum,required.length)),exact:exhaustive||knownMax||Boolean(high.length&&high[0].length===upperBound),upperBound:knownMax?largestHint.length:upperBound};
    }
    let random=(options.seed||1)>>>0;const rank=()=>{random=(1664525*random+1013904223)>>>0;return random;};
    let lastProgress=startTime;
    for(const part of parts){
      const inside=new Set(part),adj=new Map(part.map(id=>[id,[...g.adj.get(id)].filter(x=>inside.has(x)).map(id=>({id,rank:rank()})).sort((a,b)=>a.rank-b.rank).map(x=>x.id)]));
      for(const first of required.length?[required[0]]:part){
        const path=[first],used=new Set(path);
        function visit(here){
          explored++;
          if((explored&127)===0||explored===1){const now=clock();if(now>=deadline){timedOut=true;finished=true;return;}if(now-lastProgress>250){onProgress(result());lastProgress=now;}}
          if(path.length>=minimum&&g.adj.get(here).has(first))record([...path]);
          if(count>=maxFound){limited=true;finished=true;return;}
          for(const next of adj.get(here)){
            if(finished)return;
            if(used.has(next)||(!required.length&&next<first))continue;
            used.add(next);path.push(next);visit(next);path.pop();used.delete(next);
          }
        }
        visit(first);if(finished)break;
      }
      if(finished)break;
    }
    return result();
  }
  return {key,graph,components,canonical,valid,shortest,neighborhood,search,findLength,catalog,connection};
});
