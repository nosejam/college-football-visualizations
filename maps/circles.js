/* Offline directed-results explorer. D3 7.9.0 is vendored and embedded. */
(function(){
  'use strict';
  const data=window.CFB_CIRCLES_DATA,$=id=>document.getElementById(id),svg=d3.select('#network');
  const byId=new Map(data.teams.map(t=>[t.id,t])),years=Object.keys(data.seasons).map(Number).sort((a,b)=>b-a);
  const state={year:years[0],index:data.seasons[years[0]].frames.length-1,scope:'fbs',root:null,selected:[],fallback:null,depth:1,view:'network',which:'smallest',
    full:null,visible:null,results:null,worker:null,workerURL:null,request:0,searching:false,positions:new Map(),run:1,cycleIndex:0};
  let width=1000,height=650,renderedNodes=[],renderedEdges=[],nodeLayer,edgeLayer,viewGroup,fitTransform=d3.zoomIdentity;
  const formatDate=value=>new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'America/New_York'}).format(new Date(value));
  const name=id=>byId.get(id)?.school||String(id),season=()=>data.seasons[state.year],frame=()=>season().frames[state.index];
  const color=key=>CFB_THEME.color(key);
  const publicState=window.CFB_CIRCLES={ready:false,data,state};
  function stopSearch(){state.request++;if(state.worker)state.worker.terminate();if(state.workerURL)URL.revokeObjectURL(state.workerURL);state.worker=null;state.workerURL=null;state.searching=false;}
  function clearResults(){state.fallback=null;$('cycle-list').replaceChildren();$('catalog-summary').textContent='';$('extreme-results').hidden=false;stopSearch();state.results=null;publicState.results=null;state.cycleIndex=0;$('length-result').hidden=true;$('length-navigation').hidden=true;state.view='network';$('back-network').hidden=true;$('search-longer').hidden=true;
    for(const kind of ['smallest','largest']){$(kind).disabled=true;$(kind).classList.remove('active');$(kind+'-size').textContent='—';$(kind+'-proof').textContent='Not searched';$(kind+'-proof').className='';}
    $('search-status').textContent='Find circles in the teams currently shown.';resetEvidence();}
  function makeSnapshot(){
    const roster=new Set(season().roster),games=frame().week===null?[]:season().games.filter(g=>g.week<=frame().week);
    const ids=new Set(roster);
    if(state.scope==='opponents')for(const g of games)if(roster.has(g.winner)||roster.has(g.loser)){ids.add(g.winner);ids.add(g.loser);}
    const grouped=new Map();
    for(const game of games){if(!ids.has(game.winner)||!ids.has(game.loser))continue;
      const key=CFBCycles.key(game.winner,game.loser);if(!grouped.has(key))grouped.set(key,{id:key,source:game.winner,target:game.loser,games:[]});grouped.get(key).games.push(game);}
    return {nodes:[...ids].sort((a,b)=>a-b),edges:[...grouped.values()],games:games.filter(g=>ids.has(g.winner)&&ids.has(g.loser))};
  }
  function refresh(){
    clearResults();state.full=makeSnapshot();state.selected=state.selected.filter(id=>state.full.nodes.includes(id));state.root=state.selected[0]??null;
    if(!state.selected.length)state.visible=CFBCycles.neighborhood(state.full.nodes,state.full.edges,null,state.depth);
    else {
      const groups=state.selected.map(id=>CFBCycles.neighborhood(state.full.nodes,state.full.edges,id,state.depth));
      const ids=new Set(groups.flatMap(g=>g.nodes)),all=new Set(state.selected.flatMap(id=>CFBCycles.neighborhood(state.full.nodes,state.full.edges,id,Infinity).nodes));
      state.visible={nodes:[...ids],edges:state.full.edges.filter(e=>ids.has(e.source)&&ids.has(e.target)),componentSize:all.size,maxDepth:Math.max(...groups.map(g=>g.maxDepth))};
    }
    updateControls();render();publicState.ready=true;
  }
  function changeFrame(year,index){state.year=Number(year);state.index=Math.max(0,Math.min(season().frames.length-1,Number(index)||0));refresh();}
  function focusTeam(id){if(id===null)state.selected=[];else if(!state.selected.includes(id))state.selected.push(id);state.root=state.selected[0]??null;state.depth=Infinity;refresh();}
  function updateControls(){
    const current=frame();$('season-select').value=state.year;$('week-slider').max=season().frames.length-1;$('week-slider').value=state.index;
    $('week-slider').setAttribute('aria-valuetext',`${state.year}, ${current.label}`);$('week-label').textContent=current.label;
    $('week-description').textContent=current.date?`Cumulative through ${formatDate(current.date)}`:'Before the first game of the season';
    $('timeline-end').textContent=season().frames.at(-1).label;$('previous-week').disabled=state.index===0;$('next-week').disabled=state.index===season().frames.length-1;
    $('team-count').textContent=state.visible.nodes.length;$('edge-count').textContent=state.visible.edges.length;
    $('team-select').replaceChildren(new Option(state.selected.length?'Add another team…':'Choose a team…',''));
    for(const id of [...state.full.nodes].sort((a,b)=>name(a).localeCompare(name(b))))if(!state.selected.includes(id))$('team-select').append(new Option(name(id),String(id)));
    $('selected-teams').replaceChildren();for(const id of state.selected){const chip=document.createElement('button');chip.className='team-chip';chip.textContent=name(id)+' ×';chip.setAttribute('aria-label','Remove '+name(id));chip.addEventListener('click',()=>{state.selected=state.selected.filter(t=>t!==id);refresh();});$('selected-teams').append(chip);}
    $('team-select').value='';$('focus-panel').hidden=state.root===null;$('focus-help').hidden=state.root!==null;
    $('require-team').disabled=state.root===null;$('require-row').hidden=state.root===null;
    $('require-label').textContent=state.root===null?'Must include the selected team':state.selected.length>1?'Must include every selected team':`Must include ${name(state.root)}`;
    if(state.root!==null){
      const t=byId.get(state.root);$('focus-name').textContent=state.selected.length===1?t.school:`${state.selected.length} teams selected`;$('focus-logo').hidden=!t.logo;if(t.logo)$('focus-logo').src=t.logo;
      $('focus-logo').alt=t.school+' logo';$('focus-detail').textContent=`${state.depth===Infinity?'Entire connected group':state.depth+' '+(state.depth===1?'hop':'hops')} · ${state.visible.nodes.length} of ${state.visible.componentSize} connected teams.`;
      $('direct-hops').disabled=state.depth===1;$('less-hops').disabled=state.depth<=1;$('more-hops').disabled=state.depth>=state.visible.maxDepth;$('all-hops').disabled=state.depth===Infinity||state.visible.nodes.length===state.visible.componentSize;
    }
    $('find-circles').disabled=state.visible.edges.length===0&&!state.selected.length;$('find-length').disabled=state.visible.edges.length===0&&!state.selected.length;
    $('circle-length').min=$('include-pairs').checked?2:3;$('circle-length').max=Math.max(Number($('circle-length').min),state.visible.nodes.length);
    if(Number($('circle-length').value)<Number($('circle-length').min))$('circle-length').value=$('circle-length').min;
    $('search-scope').textContent=`Search scope: ${state.root===null?'entire network':state.selected.map(name).join(' + ')+' connected network'} · ${state.visible.nodes.length} teams.`;
    $('footer-status').textContent=`${state.year} · ${current.label} · ${state.scope==='fbs'?'FBS only':'FBS + opponents'} · Saved results available through ${formatDate(season().frames.at(-1).date)}`;
  }
  function tooltip(text,event){
    const box=$('network').getBoundingClientRect(),tip=$('tooltip');tip.textContent=text;tip.hidden=false;
    tip.style.left=Math.max(8,Math.min(box.width-285,event.clientX-box.left+14))+'px';tip.style.top=Math.max(60,Math.min(box.height-100,event.clientY-box.top+10))+'px';
  }
  function resetEvidence(){
    $('evidence-title').textContent='The proof, one game at a time';$('evidence-list').replaceChildren();
    const p=document.createElement('p');p.className='small-note';p.textContent='Click an arrow to inspect its games. A circle will list every win that closes the loop.';$('evidence-list').append(p);
  }
  function showEvidence(edges,cycle=false){
    $('evidence-title').textContent=cycle?'Every win in the circle':'Matchup results';$('evidence-list').replaceChildren();
    edges.forEach((edge,index)=>{
      const games=cycle?[edge.games[0]]:edge.games;
      for(const game of games){
        const row=document.createElement('div');row.className='evidence-row';
        if(cycle){const number=document.createElement('span');number.className='step';number.textContent=index+1;row.append(number);}
        const team=byId.get(game.winner);if(team.logo){const img=document.createElement('img');img.src=team.logo;img.alt='';row.append(img);}
        const text=document.createElement('div'),title=document.createElement('b'),detail=document.createElement('small');
        title.textContent=`${name(game.winner)} → ${name(game.loser)}`;detail.textContent=`${game.winner_points}–${game.loser_points} · ${formatDate(game.date)} · Week ${game.week} · Elo after game: ${game.winner_elo_after.toFixed(1)} / ${game.loser_elo_after.toFixed(1)}`;
        text.append(title,detail);row.append(text);row.addEventListener('mouseenter',()=>edgeLayer.selectAll('.edge').classed('emphasized',d=>d.id===edge.id));
        row.addEventListener('mouseleave',()=>edgeLayer.selectAll('.edge').classed('emphasized',false));$('evidence-list').append(row);
      }
    });
  }
  const zoom=d3.zoom().scaleExtent([.15,8]).on('zoom',event=>{if(viewGroup)viewGroup.attr('transform',event.transform);});
  svg.call(zoom).on('dblclick.zoom',null);
  function edgePath(d){
    const a=d.source,b=d.target,dx=b.x-a.x,dy=b.y-a.y,length=Math.max(1,Math.hypot(dx,dy));
    const gap=Math.max(.5,length-a.r-b.r),startGap=state.view==='cycle'?Math.min(2,gap*.15):2,endGap=state.view==='cycle'?Math.min(4,gap*.2):8;
    const x1=a.x+dx/length*(a.r+startGap),y1=a.y+dy/length*(a.r+startGap),x2=b.x-dx/length*(b.r+endGap),y2=b.y-dy/length*(b.r+endGap);
    const reverse=renderedEdges.some(e=>e.source.id===b.id&&e.target.id===a.id),bend=reverse?.23:state.view==='cycle'?.09:0;
    return `M${x1},${y1} Q${(x1+x2)/2-dy*bend},${(y1+y2)/2+dx*bend} ${x2},${y2}`;
  }
  function updatePositions(){nodeLayer.selectAll('.team-node').attr('transform',d=>`translate(${d.x},${d.y})`);edgeLayer.selectAll('.edge').attr('d',edgePath);}
  function fit(){svg.call(zoom.transform,fitTransform);}
  function displayedCycle(which=state.which){
    let cycle=which==='target'?state.results?.cycles?.[state.cycleIndex]:state.results?.[which==='smallest'?'shortest':'largest'];
    if(!cycle?.length)return null;
    const index=state.root===null?-1:cycle.indexOf(state.root);
    return index<0?[...cycle]:cycle.slice(index).concat(cycle.slice(0,index));
  }
  function render(){
    const ratings=frame().elo;
    const values=state.full.nodes.map(id=>ratings[id]),eloMin=Math.min(...values),eloMax=Math.max(...values);
    const eloScale=d3.scaleLinear().domain([eloMin,(eloMin+eloMax)/2,eloMax]).range(['#df4a48','#efc65b','#2eae63']).clamp(true);
    const eloColor=value=>eloMin===eloMax?'#efc65b':eloScale(value);
    publicState.elo={...ratings};publicState.eloRange={min:eloMin,max:eloMax};
    $('elo-low').textContent=eloMin.toFixed(0);$('elo-high').textContent=eloMax.toFixed(0);
    $('elo-scope').textContent=eloMin===eloMax?`All teams tied at ${eloMin.toFixed(0)} Elo`:`${state.scope==='fbs'?'All FBS teams':'FBS + opponents'} · ${frame().label}`;
    const box=$('network').getBoundingClientRect();width=box.width||1000;height=box.height||650;svg.attr('viewBox',`0 0 ${width} ${height}`);svg.selectAll('*').remove();
    const defs=svg.append('defs');
    for(const [id,fill] of [['arrow',color('edge')],['circle-arrow',color('green')]])defs.append('marker').attr('id',id).attr('viewBox','0 -4 8 8').attr('refX',7).attr('refY',0).attr('markerWidth',7).attr('markerHeight',7).attr('orient','auto').attr('markerUnits','userSpaceOnUse').append('path').attr('d','M0,-3.5L7,0L0,3.5Z').attr('fill',fill);
    viewGroup=svg.append('g');edgeLayer=viewGroup.append('g');nodeLayer=viewGroup.append('g');
    const cycle=state.view==='cycle'?displayedCycle():null;
    const displayGraph=state.view==='fallback'?state.fallback:state.visible;
    const ids=cycle||displayGraph.nodes,lookupEdges=new Map(state.visible.edges.map(e=>[e.id,e]));
    const links=cycle?cycle.map((id,i)=>lookupEdges.get(CFBCycles.key(id,cycle[(i+1)%cycle.length]))):displayGraph.edges;
    $('team-count').textContent=ids.length;$('edge-count').textContent=links.length;
    $('team-count-label').textContent=cycle?'teams in circle':'teams in view';$('edge-count-label').textContent=cycle?'wins in circle':'directed matchups';
    renderedNodes=ids.map((id,i)=>({id,...byId.get(id),elo:ratings[id],eloColor:eloColor(ratings[id]),record:frame().records[id],r:19,...(state.positions.get(`${state.year}:${id}`)||{}),order:i}));
    if(cycle){
      const radius=Math.max(70,Math.min(width,height)/2-78),nodeRadius=Math.max(3,Math.min(22,Math.PI*radius/cycle.length*.56));
      renderedNodes.forEach((n,i)=>{const angle=-Math.PI/2+2*Math.PI*i/cycle.length;n.r=nodeRadius;n.x=width/2+radius*Math.cos(angle);n.y=height/2+radius*Math.sin(angle);});
    } else {
      const initialRadius=Math.min(width,height)*.36;
      for(const [i,n] of renderedNodes.entries())if(!Number.isFinite(n.x)){n.x=width/2+initialRadius*Math.cos(i/Math.max(1,ids.length)*2*Math.PI);n.y=height/2+initialRadius*Math.sin(i/Math.max(1,ids.length)*2*Math.PI);}
      const sim=d3.forceSimulation(renderedNodes).randomSource(d3.randomLcg(state.year+state.index/100)).force('charge',d3.forceManyBody().strength(-180)).force('center',d3.forceCenter(width/2,height/2)).force('collide',d3.forceCollide(26));
      sim.force('links',d3.forceLink(links.map(e=>({source:e.source,target:e.target}))).id(d=>d.id).distance(ids.length>80?75:100).strength(.35));
      sim.stop();sim.tick(220);
      for(const n of renderedNodes)state.positions.set(`${state.year}:${n.id}`,{x:n.x,y:n.y});
    }
    if(cycle){
      const first=renderedNodes[0],second=renderedNodes[1],gap=Math.max(.5,Math.hypot(second.x-first.x,second.y-first.y)-first.r-second.r);
      defs.select('#circle-arrow').attr('markerWidth',Math.max(1.5,Math.min(7,gap*.6))).attr('markerHeight',Math.max(1.5,Math.min(7,gap*.6)));
      const center=viewGroup.append('g').attr('text-anchor','middle').attr('pointer-events','none').attr('transform',`translate(${width/2},${height/2})`);
      center.append('text').attr('font-family','Georgia, serif').attr('font-size',62).attr('fill',color('ink')).attr('y',-9).text(cycle.length);
      center.append('text').attr('font-family','system-ui, sans-serif').attr('font-size',12).attr('fill',color('muted')).attr('y',17).text('teams in a directed circle');
      center.append('text').attr('font-family','system-ui, sans-serif').attr('font-size',12).attr('fill',color('green')).attr('y',42).text(state.which==='target'?'Every win verified':state.which==='smallest'?(state.results.shortestExact===false?'Shortest found':'Proven smallest'):state.results.exact?'Proven longest':'Best found so far');
    }
    const nodesById=new Map(renderedNodes.map(n=>[n.id,n]));
    renderedEdges=links.map(e=>({...e,source:nodesById.get(e.source),target:nodesById.get(e.target)}));
    edgeLayer.selectAll('path').data(renderedEdges,d=>d.id).join('path').attr('class','edge').attr('stroke',cycle?color('green'):color('edge')).attr('stroke-width',cycle?1.8:1.05).attr('opacity',cycle?.9:.42).attr('marker-end',`url(#${cycle?'circle-arrow':'arrow'})`)
      .on('mouseenter',(event,d)=>{const g=d.games[0];tooltip(`${name(d.source.id)} beat ${name(d.target.id)}\n${g.winner_points}–${g.loser_points} · ${formatDate(g.date)}${d.games.length>1?'\n'+d.games.length+' wins on this arrow':''}`,event);})
      .on('mouseleave',()=>$('tooltip').hidden=true).on('click',(event,d)=>{event.stopPropagation();showEvidence([d]);});
    const groups=nodeLayer.selectAll('g').data(renderedNodes,d=>d.id).join('g').attr('class',d=>'team-node'+(state.selected.includes(d.id)?' focused':'')).attr('tabindex',0).attr('role','button').attr('aria-label',d=>`${d.school}. Elo ${d.elo.toFixed(1)}. Record ${d.record.wins} wins, ${d.record.losses} losses, ${d.record.ties} ties. Add to selected teams.`)
      .on('click',(event,d)=>{if(!event.defaultPrevented)focusTeam(d.id);}).on('keydown',(event,d)=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();focusTeam(d.id);}})
      .on('mouseenter',(event,d)=>tooltip(`${d.school}\nElo ${d.elo.toFixed(1)} · ${frame().label}\nRecord ${d.record.wins}–${d.record.losses}${d.record.ties?'–'+d.record.ties:''}\nClick to add this team to the cycle search.`,event)).on('mouseleave',()=>$('tooltip').hidden=true);
    groups.append('circle').attr('class','elo-ring').attr('r',d=>d.r).attr('fill',d=>d.eloColor).attr('data-elo',d=>d.elo).attr('stroke','none');
    groups.append('circle').attr('class','logo-disc').attr('r',d=>d.r*.8).attr('fill','#fffdf8').attr('stroke','none');
    groups.append('circle').attr('class','selection-ring').attr('r',d=>d.r+2).attr('fill','none').attr('stroke',color('ink')).attr('stroke-width',state.selected.length?1.5:1).attr('opacity',d=>state.selected.includes(d.id)?1:0);
    groups.append('title').text(d=>`${d.school} · Elo ${d.elo.toFixed(1)}`);
    groups.filter(d=>d.logo).append('image').attr('href',d=>d.logo).attr('x',d=>-d.r*.55).attr('y',d=>-d.r*.55).attr('width',d=>d.r*1.1).attr('height',d=>d.r*1.1).attr('preserveAspectRatio','xMidYMid meet');
    groups.filter(d=>!d.logo).append('text').attr('text-anchor','middle').attr('dy','.35em').attr('font-size',d=>d.r*.55).attr('fill','#263f47').text(d=>d.abbreviation);
    groups.append('text').attr('class','node-name').attr('text-anchor','middle').attr('y',d=>d.r+13).attr('display',$('show-names').checked?'inline':'none').text(d=>d.school);
    groups.on('mouseenter.names',function(){d3.select(this).select('.node-name').attr('display','inline');}).on('mouseleave.names',function(){if(!$('show-names').checked)d3.select(this).select('.node-name').attr('display','none');});
    if(!cycle)groups.call(d3.drag().container(()=>viewGroup.node()).on('drag',(event,d)=>{d.x=event.x;d.y=event.y;state.positions.set(`${state.year}:${d.id}`,{x:d.x,y:d.y});updatePositions();}));
    updatePositions();
    if(renderedNodes.length){
      const x0=d3.min(renderedNodes,n=>n.x-n.r-10),x1=d3.max(renderedNodes,n=>n.x+n.r+10),y0=d3.min(renderedNodes,n=>n.y-n.r-15),y1=d3.max(renderedNodes,n=>n.y+n.r+20);
      const scale=Math.min(1.5,(width-75)/Math.max(60,x1-x0),(height-115)/Math.max(60,y1-y0));
      fitTransform=d3.zoomIdentity.translate(width/2-scale*(x0+x1)/2,(height+35)/2-scale*(y0+y1)/2).scale(scale);
    }else fitTransform=d3.zoomIdentity;
    fit();$('tooltip').hidden=true;$('back-network').hidden=!cycle&&state.view!=='fallback';
    $('view-title').textContent=cycle?`${state.which==='target'?(state.results.mode==='length'?'Exact-size cycle':'Victory cycle'):state.which==='smallest'?'Smallest circle':state.results.exact?'Longest cycle':'Longest found'} · ${cycle.length} teams`:state.root===null?'Season network':`${name(state.root)} · ${state.depth===Infinity?'connected group':state.depth+' '+(state.depth===1?'hop':'hops')}`;
    $('view-subtitle').textContent=`${state.year} · ${frame().label}`;
    $('graph-caption').textContent=cycle?'Clockwise: each team beat the next · The final team beat the first · Click a team to explore':'Arrow: winner → loser · Click a logo to explore · Drag to move · Scroll to zoom';
    if(state.view==='fallback'){
      $('view-title').textContent=state.selected.length===1?`${name(state.root)} · immediate opponents`:state.fallback.connected?'Shortest played-game connection':'Immediate opponent networks';
      $('graph-caption').textContent='Arrow: winner → loser · Connections follow played games in either direction';
    }
    const noGames=displayGraph.edges.length===0;
    $('graph-notice').hidden=!noGames;
    if(noGames){$('notice-title').textContent=frame().week===null?'Before the first kickoff.':'No matchups in this view.';$('notice-copy').textContent=frame().week===null?'Move the week slider to begin building the season’s results network.':'Try another team, expand the neighborhood, or choose a later week.';}
    Object.assign(publicState,{fallback:state.fallback,nodes:state.visible.nodes,edges:state.visible.edges,renderedNodes,renderedEdges,view:state.view,cycle});
  }
  function paintList(result,complete){
    const active=state.view==='cycle'?displayedCycle():null,activeKey=active?CFBCycles.canonical(active).join(':'):null;
    $('cycle-list').replaceChildren();
    const indexed=[...(result.cycles||[]).entries()];
    const choices=(indexed.length>50?[...indexed.slice(0,5),...indexed.slice(-5)]:indexed).sort((a,b)=>a[1].length-b[1].length);
    for(const [displayIndex,[index,cycle]] of choices.entries()){
      const button=document.createElement('button');button.className='cycle-option';button.disabled=!complete;button.dataset.cycle=CFBCycles.canonical(cycle).join(':');button.setAttribute('aria-pressed',String(button.dataset.cycle===activeKey));
      const title=document.createElement('strong'),detail=document.createElement('small');title.textContent=`${cycle.length} teams · Cycle ${displayIndex+1}`;
      detail.textContent=cycle.slice(0,6).map(name).join(' → ')+(cycle.length>6?` → … (+${cycle.length-6})`:' → '+name(cycle[0]));
      button.append(title,detail);button.addEventListener('click',()=>{state.cycleIndex=index;showCycle('target');});$('cycle-list').append(button);
    }
    const count=result.count??result.cycles.length;
    $('catalog-summary').textContent=result.mode==='length'&&indexed.length>50?`${count} matching cycles found · Showing 10 examples of the same size; Another cycle browses all found results.`:result.collapsed?`${count.toLocaleString()}${result.exhausted?'':'+'} cycles found · Showing the 5 longest and 5 shortest found (overlaps shown once).`:
      `${count} cycle${count===1?'':'s'} found · ${complete&&result.exhausted?'All cycles in this search are listed.':'More may exist; these are the cycles found so far.'}`;
    if(activeKey){const index=result.cycles.findIndex(c=>CFBCycles.canonical(c).join(':')===activeKey);if(index>=0)state.cycleIndex=index;}
  }
  function showFallback(){
    if(!state.selected.length){state.view='network';render();return;}
    state.fallback=CFBCycles.connection(state.full.nodes,state.full.edges,state.selected);state.view='fallback';render();showEvidence(state.fallback.edges);
    $('search-status').textContent+=' '+(state.selected.length===1?'Showing immediate opponents.':state.fallback.connected?'Showing the shortest played-game path; arrows retain the direction of each win.':'No played-game path connects every selected team; showing their immediate opponents.');
  }
  function paintCatalog(result,complete){
    paintResults(result,complete);paintList(result,complete);
    if(result.shortest.length){$('smallest-proof').textContent=result.shortestExact?'teams · Proven smallest':'Shortest found · More may exist';$('smallest-proof').className=result.shortestExact?'proven':'unproven';}
    $('search-status').textContent=result.count?`${result.exhausted&&complete?'Search complete.':'Search is bounded; more cycles may exist.'} Select a cycle from the list to trace every win.`:
      complete?(result.exhausted?'No valid cycle exists in this search.':'No matching cycle found within the search budget. Try Search longer.'):'Searching for matching cycles…';
    $('search-longer').hidden=!complete||result.exhausted;
  }
  function paintResults(result,complete){
    state.results=result;
    const noCycles=result.shortest.length===0;
    $('smallest').disabled=noCycles;$('largest').disabled=result.largest.length===0;
    $('smallest-size').textContent=noCycles?'None':result.shortest.length;$('largest-size').textContent=result.largest.length||'None';
    $('smallest-proof').textContent=noCycles?'No valid circle':'teams · Proven smallest';$('smallest-proof').className='proven';
    $('largest-proof').textContent=noCycles?'No valid circle':result.exact?'teams · Proven longest':`Best found · at most ${result.upperBound}`;
    $('largest-proof').className=result.exact?'proven':'unproven';
    $('search-longer').hidden=!complete||result.exact||noCycles;
    if(noCycles)$('search-status').textContent=`No circle of ${$('include-pairs').checked?'2':'3'} or more teams${state.root!==null&&$('require-team').checked?' through '+name(state.root):''} in this view. Try expanding connections or choosing a later week.`;
    else if(complete)$('search-status').textContent=result.exact?'Both size extremes are proven for this network scope. Click either result to trace every win.':`The ${result.largest.length}-team circle is valid. The maximum is between ${result.largest.length} and ${result.upperBound}; Search longer continues the search.`;
    else $('search-status').textContent=`Found a ${result.largest.length}-team circle. Checking for a longer one…`;
    publicState.results=result;
  }
  function showCycle(which){
    const cycle=displayedCycle(which);if(!cycle?.length)return;
    state.which=which;state.view='cycle';$('smallest').classList.toggle('active',which==='smallest');$('largest').classList.toggle('active',which==='largest');$('length-result').classList.toggle('active',which==='target');render();
    for(const button of $('cycle-list').children)button.setAttribute('aria-pressed',String(button.dataset.cycle===CFBCycles.canonical(cycle).join(':')));
    if(which==='target')$('length-counter').textContent=`${state.cycleIndex+1} of ${state.results.cycles.length} found`;
    const edges=new Map(state.visible.edges.map(e=>[e.id,e]));showEvidence(cycle.map((id,i)=>edges.get(CFBCycles.key(id,cycle[(i+1)%cycle.length]))),true);
  }
  function paintLength(result,complete){
    state.results=result;publicState.results=result;paintList(result,complete);
    $('length-result').hidden=false;$('length-result').disabled=!result.cycles.length;
    $('length-size').textContent=result.cycles.length?`${result.length} teams`:'None';
    $('length-proof').textContent=`${result.cycles.length} circle${result.cycles.length===1?'':'s'} found${result.exhausted&&complete?' · All checked':''}`;
    $('length-proof').className=result.cycles.length?'proven':'';
    $('length-navigation').hidden=result.cycles.length<2;
    $('length-counter').textContent=`${state.cycleIndex+1} of ${result.cycles.length} found`;
    $('search-longer').hidden=!complete||result.exhausted;
    if(result.cycles.length)$('search-status').textContent=`Found ${result.cycles.length} valid ${result.length}-team circle${result.cycles.length===1?'':'s'}${state.root!==null&&$('require-team').checked?' through '+name(state.root):''}. ${result.cycles.length>1?'Use Another circle to browse. ':''}${complete&&!result.exhausted?'More may exist; Search longer looks for additional circles.':''}`;
    else $('search-status').textContent=complete&&result.exhausted?`No ${result.length}-team circle${state.root!==null&&$('require-team').checked?' through '+name(state.root):''} in this network scope. Try another size or expand connections.`:`No ${result.length}-team circle found yet. ${complete?'Search longer to keep checking.':'Searching…'}`;
  }
  function launchSearch(options){
    const request=state.request;state.searching=true;
    try{
      state.workerURL=URL.createObjectURL(new Blob([$('cycle-worker-source').textContent],{type:'text/javascript'}));state.worker=new Worker(state.workerURL);
      state.worker.onmessage=event=>{
        if(event.data.request!==state.request)return;
        if(event.data.type==='error'){$('search-status').textContent='Search failed: '+event.data.message;stopSearch();return;}
        const complete=event.data.type==='complete',target=event.data.result.mode==='length';
        if(target)paintLength(event.data.result,complete);else paintCatalog(event.data.result,complete);
        if(complete){state.searching=false;state.worker.terminate();state.worker=null;URL.revokeObjectURL(state.workerURL);state.workerURL=null;
          if(target){if(state.results.cycles.length)showCycle('target');}
          else if(state.results.largest.length&&state.view!=='cycle')showCycle('smallest');else if(state.view==='cycle')showCycle(state.which);
          if(!(target?state.results.cycles.length:state.results.largest.length))showFallback();
        }
      };
      state.worker.onerror=event=>{$('search-status').textContent='The background search could not run: '+event.message;stopSearch();};
      state.worker.postMessage({request,options});
    }catch(error){$('search-status').textContent='The browser could not start a background search: '+error.message;stopSearch();}
  }
  function findCircles(longer=false){
    const previous=longer?state.results:null;if(longer)stopSearch();else clearResults();
    state.fallback=null;state.view='network';
    const minimum=$('include-pairs').checked?2:3,required=$('require-team').checked?state.selected:[];
    const reference=season().reference[state.index],saved=reference.longest;
    const hint=saved.cycle.length?saved.cycle:reference.shortest_with_pairs;
    $('search-status').textContent='Finding victory cycles and collecting alternatives…';$('search-longer').hidden=true;render();
    launchSearch({mode:'catalog',nodes:state.visible.nodes,edges:state.visible.edges.map(e=>[e.source,e.target]),minimum,required,
      timeLimitMs:longer?8000:1800,maxFound:longer?(previous?.count||5000)+5000:5000,seed:++state.run,hint,hintExact:state.scope==='fbs'&&saved.exact,
      existing:previous?.cycles||[],hints:[reference.shortest,reference.shortest_with_pairs]});
  }
  function findSize(longer=false){
    if(!$('circle-length').reportValidity())return;
    const previous=longer&&state.results?.mode==='length'?state.results:null;
    if(previous)stopSearch();else clearResults();
    const length=Number($('circle-length').value);$('extreme-results').hidden=true;
    state.fallback=null;state.view='network';
    $('search-status').textContent=`Finding cycles with exactly ${length} teams…`;$('search-longer').hidden=true;render();
    launchSearch({mode:'length',nodes:state.visible.nodes,edges:state.visible.edges.map(e=>[e.source,e.target]),
      length,minimum:$('include-pairs').checked?2:3,required:$('require-team').checked?state.selected:[],
      timeLimitMs:longer?8000:1800,maxCycles:(previous?.cycles.length||0)+50,existing:previous?.cycles||[]});
  }
  for(const year of years)$('season-select').append(new Option(String(year),String(year)));
  $('season-select').addEventListener('change',event=>changeFrame(event.target.value,0));$('week-slider').addEventListener('input',event=>changeFrame(state.year,event.target.value));
  $('previous-week').addEventListener('click',()=>changeFrame(state.year,state.index-1));$('next-week').addEventListener('click',()=>changeFrame(state.year,state.index+1));
  $('scope-select').addEventListener('change',event=>{state.scope=event.target.value;refresh();});$('team-select').addEventListener('change',event=>focusTeam(event.target.value?Number(event.target.value):null));
  $('direct-hops').addEventListener('click',()=>{state.depth=1;refresh();});
  $('less-hops').addEventListener('click',()=>{state.depth=state.depth===Infinity?Math.max(1,state.visible.maxDepth-1):Math.max(1,state.depth-1);refresh();});
  $('more-hops').addEventListener('click',()=>{state.depth++;refresh();});$('all-hops').addEventListener('click',()=>{state.depth=Infinity;refresh();});$('clear-focus').addEventListener('click',()=>focusTeam(null));
  for(const id of ['include-pairs','require-team'])$(id).addEventListener('change',()=>{clearResults();updateControls();render();});
  $('find-circles').addEventListener('click',()=>findCircles());$('search-longer').addEventListener('click',()=>state.results?.mode==='length'?findSize(true):findCircles(true));
  $('find-length').addEventListener('click',()=>findSize());$('length-result').addEventListener('click',()=>showCycle('target'));
  $('circle-length').addEventListener('change',()=>{if(state.results?.mode==='length'){clearResults();render();}});
  $('next-circle').addEventListener('click',()=>{if(state.results?.cycles?.length){state.cycleIndex=(state.cycleIndex+1)%state.results.cycles.length;showCycle('target');}});
  $('smallest').addEventListener('click',()=>showCycle('smallest'));$('largest').addEventListener('click',()=>showCycle('largest'));
  $('back-network').addEventListener('click',()=>{state.view='network';$('smallest').classList.remove('active');$('largest').classList.remove('active');resetEvidence();render();});
  $('fit').addEventListener('click',fit);$('show-names').addEventListener('change',()=>nodeLayer.selectAll('.node-name').attr('display',$('show-names').checked?'inline':'none'));
  $('export').addEventListener('click',()=>{
    const clone=$('network').cloneNode(true);clone.setAttribute('xmlns','http://www.w3.org/2000/svg');clone.setAttribute('width',width);clone.setAttribute('height',height);
    clone.querySelectorAll('.edge').forEach(el=>el.setAttribute('fill','none'));
    clone.querySelectorAll('.node-name').forEach(el=>{el.setAttribute('fill',color('ink'));el.setAttribute('font-size','10');el.setAttribute('stroke',color('paper'));el.setAttribute('stroke-width','3');el.setAttribute('paint-order','stroke');});
    clone.querySelectorAll('.team-node.focused .selection-ring').forEach(el=>{el.setAttribute('stroke',color('ink'));el.setAttribute('stroke-width','1.5');});
    const ns='http://www.w3.org/2000/svg',background=document.createElementNS(ns,'rect');background.setAttribute('width','100%');background.setAttribute('height','100%');background.setAttribute('fill',color('paper'));clone.insertBefore(background,clone.firstChild);
    const label=document.createElementNS(ns,'text');label.setAttribute('x','22');label.setAttribute('y','28');label.setAttribute('font-family','sans-serif');label.setAttribute('font-size','16');label.setAttribute('fill',color('ink'));label.textContent=`${state.year} · ${frame().label} · ${$('view-title').textContent}`;clone.append(label);
    const legend=document.createElementNS(ns,'text');legend.setAttribute('x','22');legend.setAttribute('y',String(height-12));legend.setAttribute('font-family','sans-serif');legend.setAttribute('font-size','11');legend.setAttribute('fill',color('ink'));legend.textContent=`Elo rings: red ${publicState.eloRange.min.toFixed(0)} → green ${publicState.eloRange.max.toFixed(0)} · ${$('elo-scope').textContent}`;clone.append(legend);
    const href=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)],{type:'image/svg+xml'})),link=document.createElement('a');link.href=href;link.download=`circles-${state.year}-${frame().week===null?'preseason':'week-'+frame().week}-${state.view}.svg`;link.click();setTimeout(()=>URL.revokeObjectURL(href),1000);
  });
  window.addEventListener('cfb:themechange',()=>{if(state.visible)render();});
  window.addEventListener('message',event=>{if(event.source===window.parent&&event.data?.type==='cfb-visualizations:visibility')$('tooltip').hidden=true;});
  let resize;
  new ResizeObserver(()=>{clearTimeout(resize);resize=setTimeout(()=>{if(state.visible)render();},80);}).observe($('network').parentElement);
  refresh();
})();
