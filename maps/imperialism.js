/* Imperialism playback. Plotly 3.3.0 and TopoJSON 3.1.0 are pinned for projection alignment. */
(async function () {
  'use strict';
  const data=window.CFB_IMPERIALISM_DATA;
  const $=id=>document.getElementById(id), gd=$('map'), overlay=$('logo-overlay');
  const svgNS='http://www.w3.org/2000/svg';
  const teams=data.teams, byId=new Map(teams.map((t,i)=>[t.team_id,{...t,index:i}]));
  const counties=topojson.feature(data.topology,data.topology.objects.counties);
  const countyIndex=new Map(data.county_ids.map((id,i)=>[id,i]));
  const geometries=data.topology.objects.counties.geometries;
  const cache=new Map();
  const years=Object.keys(data.seasons).map(Number).sort((a,b)=>b-a);
  let active=null,selected=null,wanted=null,rendering=false,animationFrame=null,playTimer=null,playing=false;
  window.CFB_IMPERIALISM={ready:false,rendering:false,data,logoMetrics:[]};
  const formatDate=value=>new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'America/New_York'}).format(new Date(value));
  const teamName=id=>byId.get(id)?.school||String(id);
  function geographicData(index) {
    if(cache.has(index))return cache.get(index);
    const original=data.geographies[index];
    const seedOf=g=>original.assignments[countyIndex.get(g.id)];
    const grouped=new Map(original.seeds.map(seed=>[seed,[]]));
    for(const g of geometries)grouped.get(seedOf(g)).push(g);
    const regions=new Map([...grouped].map(([seed,group])=>[seed,{type:'Feature',id:seed,geometry:topojson.merge(data.topology,group)}]));
    const mesh=topojson.mesh(data.topology,data.topology.objects.counties,(a,b)=>a===b||seedOf(a)!==seedOf(b));
    const result={...original,regions,mesh};cache.set(index,result);return result;
  }
  function frameState(year,index) {
    const season=data.seasons[year],frame=season.frames[index],geo=geographicData(season.geography);
    const ownerOf=new Map(geo.seeds.map((seed,i)=>[seed,frame.owners[i]]));
    const countyOwners=geo.assignments.map(seed=>ownerOf.get(seed));
    const counts=new Map(),territories=new Map();
    for(const owner of countyOwners)counts.set(owner,(counts.get(owner)||0)+1);
    for(const owner of frame.owners)territories.set(owner,(territories.get(owner)||0)+1);
    const transfers=new Map();
    for(let i=1;i<=index;i++)for(const event of season.frames[i].events)for(const seed of event.territories)transfers.set(seed,event);
    return {year:Number(year),index,season,frame,geo,ownerOf,countyOwners,counts,territories,transfers};
  }
  const scale=teams.flatMap((t,i)=>[[i/teams.length,t.color],[(i+1)/teams.length,t.color]]);
  const trace={type:'choropleth',geojson:counties,locations:data.county_ids,z:Array(counties.features.length).fill(.5),
    zmin:0,zmax:teams.length,colorscale:scale,showscale:false,marker:{line:{width:.5,color:'#0000'}},
    customdata:[],hoverinfo:'none'};
  const theme=key=>CFB_THEME.color(key);
  const layout={paper_bgcolor:theme('paper'),plot_bgcolor:theme('paper'),margin:{l:5,r:5,t:61,b:23},
    font:{family:'system-ui, sans-serif',color:theme('ink')},hoverlabel:{bgcolor:'#102a34',bordercolor:'#97b7ad',font:{size:13,color:'#fff'}},
    geo:{scope:'usa',projection:{type:'albers usa',scale:1},bgcolor:theme('paper'),showland:true,landcolor:theme('land'),
      showocean:false,showlakes:false,showcoastlines:false,showframe:false,showsubunits:false,showcountries:false},
    showlegend:false,dragmode:'pan',uirevision:'imperialism'};
  const tooltip=document.createElement('div');tooltip.id='map-tooltip';tooltip.setAttribute('role','tooltip');tooltip.hidden=true;document.body.appendChild(tooltip);
  let pointer={clientX:0,clientY:0};
  function hideTooltip(){tooltip.hidden=true;}
  function positionTooltip(event=pointer){
    const gap=14,pad=10;
    const x=Math.max(pad,Math.min(window.innerWidth-tooltip.offsetWidth-pad,event.clientX+gap));
    const y=Math.max(pad,Math.min(window.innerHeight-tooltip.offsetHeight-pad,event.clientY+gap));
    tooltip.style.left=x+'px';tooltip.style.top=y+'px';
  }
  function showTooltip(event){
    const point=event.points?.[0],info=point?.customdata;if(!info||rendering)return;
    tooltip.replaceChildren();
    const title=document.createElement('strong');title.textContent=`${info[0]}, ${info[1]}`;tooltip.appendChild(title);
    for(const text of [`Owner: ${info[2]}`,`Started with: ${info[3]}`,info[4]]){const line=document.createElement('div');line.textContent=text;tooltip.appendChild(line);}
    tooltip.hidden=false;positionTooltip(event.event?.clientX!==undefined?event.event:pointer);
  }
  gd.addEventListener('pointermove',event=>{pointer={clientX:event.clientX,clientY:event.clientY};if(!tooltip.hidden)positionTooltip(pointer);});
  gd.addEventListener('pointerleave',hideTooltip);gd.addEventListener('pointerdown',hideTooltip);
  // Albers USA's native clip uses its initial fitted rectangle. Fill the full
  // visible viewport, matching the separately drawn borders and logos.
  function alignViewport(geo,width,height){
    for(const selection of [geo.clipRect,geo.bgRect])selection?.attr('x',0).attr('y',0).attr('width',width).attr('height',height);
    geo.xaxis._offset=0;geo.xaxis._length=width;geo.yaxis._offset=0;geo.yaxis._length=height;
    window.CFB_IMPERIALISM.viewport={x:0,y:0,width,height};
  }
  function element(name,attributes,parent=overlay) {
    const el=document.createElementNS(svgNS,name);
    for(const [key,value] of Object.entries(attributes))el.setAttribute(key,String(value));
    parent.appendChild(el);return el;
  }
  function segmentDistance(p,a,b) {
    const dx=b[0]-a[0],dy=b[1]-a[1],length=dx*dx+dy*dy;
    const t=length?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length)):0;
    return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);
  }
  function boundary(feature,projection) {
    const rings=[];let ring;
    const sink={point(x,y){if(ring)ring.push([x,y]);},lineStart(){ring=[];},lineEnd(){if(ring.length>1){ring.push(ring[0]);rings.push(ring);}ring=null;},polygonStart(){},polygonEnd(){},sphere(){}};
    d3.geoStream(feature,projection.stream(sink));return rings;
  }
  function scheduleOverlay() {
    if(animationFrame!==null)cancelAnimationFrame(animationFrame);
    animationFrame=requestAnimationFrame(()=>{animationFrame=null;if(!rendering)drawOverlay();});
  }
  function drawOverlay() {
    if(!active)return;
    const projection=gd._fullLayout?.geo?._subplot?.projection;if(!projection)return;
    const width=gd._fullLayout.width,height=gd._fullLayout.height;
    alignViewport(gd._fullLayout.geo._subplot,width,height);
    overlay.setAttribute('width',width);overlay.setAttribute('height',height);overlay.setAttribute('viewBox',`0 0 ${width} ${height}`);
    overlay.replaceChildren();
    const defs=element('defs',{}),clip=element('clipPath',{id:'imperialism-viewport'},defs);
    element('rect',{x:0,y:0,width,height},clip);
    const layers=element('g',{'clip-path':'url(#imperialism-viewport)'});
    const path=d3.geoPath(projection);
    element('path',{d:path(active.geo.mesh),class:'territory-border',display:$('show-borders').checked?'inline':'none'},layers);
    const logoGroup=element('g',{display:$('show-logos').checked?'inline':'none'},layers);
    const rings=new Map(),metrics=[];
    for(const anchor of active.geo.anchors) {
      const center=projection([anchor.longitude,anchor.latitude]);
      if(!center||!center.every(Number.isFinite))continue;
      if(center[0]<layout.margin.l||center[0]>width-layout.margin.r||center[1]<layout.margin.t||center[1]>height-layout.margin.b)continue;
      if(!rings.has(anchor.seed))rings.set(anchor.seed,boundary(active.geo.regions.get(anchor.seed),projection));
      let radius=Infinity;
      for(const ring of rings.get(anchor.seed))for(let i=1;i<ring.length;i++)radius=Math.min(radius,segmentDistance(center,ring[i-1],ring[i]));
      if(!Number.isFinite(radius))continue;
      radius=Math.min(radius,center[0],width-center[0],center[1],height-center[1]);
      const size=Math.min(115,Math.max(0,radius*Math.SQRT2*.84));
      const owner=active.ownerOf.get(anchor.seed);
      metrics.push({seed:anchor.seed,part:anchor.part,owner,center,radius,size});
      if(size>0)element('image',{href:byId.get(owner).logo_data,x:center[0]-size/2,y:center[1]-size/2,width:size,height:size,
        class:'owner-logo','data-seed':anchor.seed,'data-owner':owner,preserveAspectRatio:'xMidYMid meet'},logoGroup);
    }
    if(selected!==null && active.counts.has(selected)) {
      const group=geometries.filter(g=>active.countyOwners[countyIndex.get(g.id)]===selected);
      element('path',{d:path(topojson.merge(data.topology,group)),class:'selected-border'},layers);
    }
    window.CFB_IMPERIALISM.logoMetrics=metrics;
  }
  function updateSelection() {
    $('team-select').value=selected===null?'':String(selected);
    $('team-panel').hidden=selected===null;$('selection-help').hidden=selected!==null;
    if(selected===null)return;
    const team=byId.get(selected),count=active.counts.get(selected)||0,territories=active.territories.get(selected)||0;
    $('team-logo').src=team.logo_data;$('team-logo').alt=team.school+' logo';$('team-name').textContent=team.school;
    $('team-detail').textContent=count?`${count.toLocaleString()} counties · ${territories} starting territories · ${(100*count/active.countyOwners.length).toFixed(1)}% of all counties.`:
      'No land this week. A win over any landholder puts this team back on the map.';
  }
  function selectTeam(id) {selected=id;updateSelection();scheduleOverlay();}
  function updateSidebar() {
    const frame=active.frame;
    $('owners-count').textContent=active.counts.size;
    $('transfers-count').textContent=frame.events.length;
    const ranking=[...active.counts].sort((a,b)=>b[1]-a[1]||a[0]-b[0]);
    $('leaderboard').replaceChildren();
    for(const [owner,count] of ranking.slice(0,5)) {
      const button=document.createElement('button');button.className='ranking';
      const img=document.createElement('img');img.src=byId.get(owner).logo_data;img.alt='';
      const name=document.createElement('span');name.className='name';name.textContent=teamName(owner);
      const total=document.createElement('span');total.className='total';total.textContent=count.toLocaleString();
      button.append(img,name,total);button.addEventListener('click',()=>selectTeam(owner));$('leaderboard').append(button);
    }
    const options=new Set([...active.season.roster,...active.counts.keys()]);
    for(let i=0;i<=active.index;i++)for(const event of active.season.frames[i].events)options.add(event.winner);
    $('team-select').replaceChildren(new Option('All teams',''));
    for(const id of [...options].sort((a,b)=>teamName(a).localeCompare(teamName(b))))$('team-select').append(new Option(teamName(id),String(id)));
    if(selected!==null&&!options.has(selected))selected=null;
    updateSelection();
    $('battles').replaceChildren();
    $('battle-label').textContent=frame.week===null?'Starting positions':'This week’s conquests';
    if(!frame.events.length) {
      const p=document.createElement('p');p.className='empty';p.textContent=frame.week===null?'Every county starts with its closest FBS campus.':'No land changed hands this week.';$('battles').append(p);
    }
    for(const event of [...frame.events].reverse()) {
      const button=document.createElement('button');button.className='battle';
      const title=document.createElement('strong');title.textContent=teamName(event.winner)+' over '+teamName(event.loser);
      const detail=document.createElement('span');detail.textContent=`${event.winner_points}–${event.loser_points} · ${event.counties.toLocaleString()} counties claimed`;
      button.append(title,detail);button.addEventListener('click',()=>selectTeam(event.winner));$('battles').append(button);
    }
  }
  function updateTimeline() {
    const {year,season,index,frame}=active;
    $('season-select').value=year;
    $('week-slider').max=season.frames.length-1;$('week-slider').value=index;
    $('week-slider').setAttribute('aria-valuetext',`${year}, ${frame.label}`);
    $('week-label').textContent=frame.label;
    $('week-description').textContent=frame.date?`Results through ${formatDate(frame.date)} · ${frame.games} completed games`:'Before the first game of the season';
    $('timeline-end').textContent=season.frames.at(-1).label;
    $('timeline-middle').textContent=`${season.roster.length} starting teams`;
    $('map-title').textContent=`${year} · ${frame.label}`;
    $('map-subtitle').textContent=frame.date?`Results through ${formatDate(frame.date)}`:'Closest-campus starting territories';
    $('previous-week').disabled=index===0;$('next-week').disabled=index===season.frames.length-1;
    const latest=season.frames.at(-1).date;
    $('footer-status').textContent=`${active.countyOwners.length.toLocaleString()} counties & equivalents · ${season.roster.length} starting FBS programs · ${year} results available through ${formatDate(latest)}`;
  }
  async function requestRender(year,index) {
    hideTooltip();
    year=Number(year);
    wanted={year,index:Math.max(0,Math.min(data.seasons[year].frames.length-1,Number(index)||0))};
    if(rendering)return;
    rendering=true;window.CFB_IMPERIALISM.rendering=true;$('export').disabled=true;
    $('map-status').hidden=false;$('map-status').textContent='Updating ownership…';
    try {
      while(wanted) {
        const request=wanted;wanted=null;
        const next=frameState(request.year,request.index);
        const hover=counties.features.map((f,i)=>{
          const seed=next.geo.assignments[countyIndex.get(f.id)],last=next.transfers.get(seed);
          return [f.properties.name,f.properties.state,teamName(next.countyOwners[countyIndex.get(f.id)]),teamName(seed),
            last?`${teamName(last.winner)} defeated ${teamName(last.loser)}, ${last.winner_points}–${last.loser_points}`:'No conquests yet',next.countyOwners[countyIndex.get(f.id)]];
        });
        await Plotly.restyle(gd,{z:[next.countyOwners.map(id=>byId.get(id).index+.5)],customdata:[hover],
          'marker.line.color':[next.countyOwners.map(id=>byId.get(id).color)]},[0]);
        active=next;
        if(wanted)continue;
        updateTimeline();updateSidebar();
        Object.assign(window.CFB_IMPERIALISM,{season:active.year,frameIndex:active.index,frame:active.frame,
          owners:Object.fromEntries(active.ownerOf),countyOwners:active.countyOwners,geography:active.geo});
      }
    } catch(error) {
      $('map-status').textContent='Unable to update the map: '+error.message;console.error(error);throw error;
    } finally {
      rendering=false;window.CFB_IMPERIALISM.rendering=false;$('export').disabled=false;
      if(active){drawOverlay();window.CFB_IMPERIALISM.ready=true;$('map-status').hidden=true;}
    }
  }
  function stopPlaying() {
    playing=false;clearTimeout(playTimer);playTimer=null;$('play').textContent='Play';$('play').setAttribute('aria-label','Play season');
  }
  function continuePlaying() {
    if(!playing)return;
    playTimer=setTimeout(async()=>{
      if(!active || active.index>=active.season.frames.length-1){stopPlaying();return;}
      if(!rendering)await requestRender(active.year,active.index+1);
      continuePlaying();
    },900);
  }
  try {
    for(const year of years)$('season-select').append(new Option(String(year),String(year)));
    await Plotly.newPlot(gd,[trace],layout,{responsive:true,displayModeBar:false,scrollZoom:true,showLink:false});
    gd.on('plotly_afterplot',scheduleOverlay);
    for(const name of ['plotly_relayout','plotly_relayouting'])gd.on(name,()=>{hideTooltip();scheduleOverlay();});
    gd.on('plotly_hover',showTooltip);gd.on('plotly_unhover',hideTooltip);
    gd.on('plotly_click',event=>{const point=event.points?.[0];if(point&&!rendering)selectTeam(Number(point.customdata[5]));});
    $('season-select').addEventListener('change',event=>{stopPlaying();selected=null;requestRender(event.target.value,0);});
    $('week-slider').addEventListener('input',event=>{stopPlaying();requestRender($('season-select').value,event.target.value);});
    $('team-select').addEventListener('change',event=>selectTeam(event.target.value?Number(event.target.value):null));
    for(const id of ['show-logos','show-borders'])$(id).addEventListener('change',scheduleOverlay);
    for(const [id,step] of [['previous-week',-1],['next-week',1]])$(id).addEventListener('click',()=>{
      stopPlaying();requestRender(active.year,Math.max(0,Math.min(active.season.frames.length-1,active.index+step)));
    });
    $('play').addEventListener('click',async()=>{
      if(playing){stopPlaying();return;}
      playing=true;
      if(active.index===active.season.frames.length-1)await requestRender(active.year,0);
      if(!playing)return;
      $('play').textContent='Pause';$('play').setAttribute('aria-label','Pause playback');continuePlaying();
    });
    $('reset').addEventListener('click',async()=>{selected=null;updateSelection();await Plotly.relayout(gd,{'geo.projection.scale':1,'geo.center.lon':-96,'geo.center.lat':38});scheduleOverlay();});
    for(const [id,factor] of [['zoom-in',1.5],['zoom-out',1/1.5]])$(id).addEventListener('click',()=>Plotly.relayout(gd,{'geo.projection.scale':Math.max(.8,Math.min(30,gd._fullLayout.geo.projection.scale*factor))}));
    $('export').addEventListener('click',async()=>{
      $('export').disabled=true;
      try {
        const url=await Plotly.toImage(gd,{format:'svg',width:gd._fullLayout.width,height:gd._fullLayout.height});
        const content=await (await fetch(url)).text(),doc=new DOMParser().parseFromString(content,'image/svg+xml');
        const group=doc.createElementNS(svgNS,'g');
        for(const child of overlay.children)group.appendChild(doc.importNode(child,true));
        group.querySelectorAll('.territory-border').forEach(path=>{path.setAttribute('fill','none');path.setAttribute('stroke','#11252e');path.setAttribute('stroke-opacity','.55');path.setAttribute('stroke-width','.65');});
        group.querySelectorAll('.selected-border').forEach(path=>{path.setAttribute('fill','none');path.setAttribute('stroke','#fff');path.setAttribute('stroke-width','2');});
        group.querySelectorAll('.owner-logo').forEach(image=>image.setAttribute('style','filter:drop-shadow(0 0 .8px #fff) drop-shadow(0 1px 1px #0004)'));
        // toImage recreates Plotly's native fit clip; expand it just as on screen.
        for(const rect of doc.querySelectorAll('clipPath[id$="geo"] rect')){rect.setAttribute('x','0');rect.setAttribute('y','0');rect.setAttribute('width',gd._fullLayout.width);rect.setAttribute('height',gd._fullLayout.height);}
        doc.documentElement.appendChild(group);
        // Include the chosen season/week in the exported image itself.
        const label=doc.createElementNS(svgNS,'text');label.setAttribute('x',gd._fullLayout.width-24);label.setAttribute('y',30);
        label.setAttribute('text-anchor','end');label.setAttribute('font-family','sans-serif');label.setAttribute('font-size','18');label.setAttribute('fill',theme('ink'));label.textContent=`${active.year} · ${active.frame.label}`;doc.documentElement.appendChild(label);
        const blob=new Blob([new XMLSerializer().serializeToString(doc)],{type:'image/svg+xml'});
        const href=URL.createObjectURL(blob),link=document.createElement('a');link.href=href;link.download=`imperialism-${active.year}-${active.frame.week===null?'preseason':'week-'+active.frame.week}.svg`;link.click();setTimeout(()=>URL.revokeObjectURL(href),1000);
      } catch(error){$('footer-status').textContent='Export failed: '+error.message;}finally{$('export').disabled=false;}
    });
    const year=years[0];await requestRender(year,data.seasons[year].frames.length-1);
    window.addEventListener('cfb:themechange',()=>{hideTooltip();Plotly.relayout(gd,{paper_bgcolor:theme('paper'),plot_bgcolor:theme('paper'),'geo.bgcolor':theme('paper'),'geo.landcolor':theme('land'),'font.color':theme('ink')}).then(scheduleOverlay);});
    new ResizeObserver(()=>{if(gd.getBoundingClientRect().width>0){Plotly.Plots.resize(gd);scheduleOverlay();}}).observe(gd.parentElement);
    window.addEventListener('message',event=>{if(event.source!==window.parent||event.data?.type!=='cfb-visualizations:visibility')return;hideTooltip();if(!event.data.visible)stopPlaying();else{Plotly.Plots.resize(gd);scheduleOverlay();}});
  } catch(error) {
    $('map-status').hidden=false;$('map-status').textContent='Unable to draw the map: '+error.message;console.error(error);
  }
})();
