/* Standalone map logic. Pinned Plotly 3.3.0 supplies the SVG geo projection. */
(async function () {
  'use strict';
  const data = window.CFB_MAP_DATA;
  const gd = document.getElementById('map');
  const overlay = document.getElementById('logo-overlay');
  const $ = id => document.getElementById(id);
  const svgNS = 'http://www.w3.org/2000/svg';
  const teams = data.teams;
  const byId = new Map(teams.map((t, i) => [t.team_id, {...t, index:i}]));
  const regionById = new Map(data.regions.features.map(f => [f.id, f]));
  const radians = x => x * Math.PI / 180;
  function distance(lat, lon, team) {
    const a = radians(lat), b = radians(team.latitude);
    const h = Math.sin((b-a)/2)**2 + Math.cos(a)*Math.cos(b)*Math.sin(radians(team.longitude-lon)/2)**2;
    return 6371.0088 * 2 * Math.asin(Math.sqrt(Math.min(1,h)));
  }
  // Calculate assignments in JavaScript, using precisely the offline audit method.
  const assignments = data.counties.features.map(f => {
    const p=f.properties;
    let best=teams[0], km=Infinity;
    for (const t of teams) {
      const d=distance(p.latitude,p.longitude,t);
      if (d<km || (d===km && t.team_id<best.team_id)) {best=t;km=d;}
    }
    if (best.team_id!==p.team_id) throw new Error(`Assignment audit failed for ${f.id}`);
    return {fips:f.id, team:byId.get(best.team_id), distance_km:km, county:p.name, state:p.state};
  });
  window.CFB_MAP = {assignments, data, logoMetrics:[], ready:false};
  const scale = teams.flatMap((t,i) => [[i/teams.length,t.color],[(i+1)/teams.length,t.color]]);
  let selected = null;
  const countyTrace={type:'choropleth',geojson:data.counties,locations:assignments.map(a=>a.fips),
    z:assignments.map(a=>a.team.index+.5),zmin:0,zmax:teams.length,colorscale:scale,showscale:false,
    marker:{line:{width:0,color:'#ffffff55'}},
    customdata:assignments.map(a=>[a.county,a.state,a.team.school,a.distance_km*.621371,a.team.team_id]),
    hovertemplate:'<b>%{customdata[0]}, %{customdata[1]}</b><br>%{customdata[2]}<br>%{customdata[3]:.1f} miles to campus<extra></extra>'};
  const locationTrace={type:'scattergeo',mode:'markers',lon:teams.map(t=>t.longitude),lat:teams.map(t=>t.latitude),
    customdata:teams.map(t=>[t.school,t.county_count,t.team_id]),
    marker:{size:4,color:'#fff',line:{width:1,color:'#243b43'}},
    hovertemplate:'<b>%{customdata[0]}</b><br>Main campus · %{customdata[1]} counties<extra></extra>',showlegend:false};
  const layout={paper_bgcolor:'#f6f5f0',plot_bgcolor:'#f6f5f0',margin:{l:5,r:5,t:52,b:28},
    font:{family:'system-ui, sans-serif',color:'#142c35'},hoverlabel:{bgcolor:'#fffdf8',bordercolor:'#cdd6cf',font:{size:13}},
    geo:{scope:'usa',projection:{type:'albers usa',scale:1},bgcolor:'#f6f5f0',showland:true,landcolor:'#eceee8',
      showocean:false,showlakes:false,showcoastlines:false,showframe:false,
      showsubunits:true,subunitcolor:'#f6f5f080',subunitwidth:.45,showcountries:false},
    showlegend:false,dragmode:'pan',uirevision:'closest-campus-2025'};
  let frame = null;
  function scheduleOverlay() {
    if (frame!==null) cancelAnimationFrame(frame);
    frame=requestAnimationFrame(()=>{frame=null;drawOverlay();});
  }
  // Distance from a center to one boundary segment in the same projected SVG pixels.
  function segmentDistance(p,a,b) {
    const dx=b[0]-a[0],dy=b[1]-a[1],length=dx*dx+dy*dy;
    const t=length ? Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length)) : 0;
    return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);
  }
  function projectedBoundary(feature,projection) {
    const rings=[];
    let ring;
    const sink={point(x,y){if(ring)ring.push([x,y]);},lineStart(){ring=[];},
      lineEnd(){if(ring.length>1){ring.push(ring[0]);rings.push(ring);}ring=null;},polygonStart(){},polygonEnd(){},sphere(){}};
    d3.geoStream(feature,projection.stream(sink));
    return rings;
  }
  function element(name,attributes,parent=overlay) {
    const el=document.createElementNS(svgNS,name);
    for(const [key,value] of Object.entries(attributes))el.setAttribute(key,String(value));
    parent.appendChild(el);return el;
  }
  function drawOverlay() {
    const geo=gd._fullLayout?.geo?._subplot;
    if(!geo?.projection)return;
    const projection=geo.projection;
    const width=gd._fullLayout.width,height=gd._fullLayout.height;
    overlay.setAttribute('width',width);overlay.setAttribute('height',height);
    overlay.setAttribute('viewBox',`0 0 ${width} ${height}`);
    overlay.replaceChildren();
    const path=d3.geoPath(projection);
    const boundaries=element('g',{display:$('show-borders').checked?'inline':'none'});
    for (const region of data.regions.features) {
      const d=path(region);
      if(d)element('path',{d,class:'territory-border'},boundaries);
    }
    const metrics=[];
    const logos=element('g',{display:$('show-logos').checked?'inline':'none'});
    // Larger logos go first so small regions remain legible.
    for(const team of [...teams].sort((a,b)=>b.county_count-a.county_count)) {
      const center=projection([team.longitude,team.latitude]);
      if(!center || !center.every(Number.isFinite))continue;
      let radius=0;
      if(team.logo_fits_at_campus) {
        const rings=projectedBoundary(regionById.get(team.team_id),projection);
        radius=Infinity;
        for(const ring of rings)for(let i=1;i<ring.length;i++)radius=Math.min(radius,segmentDistance(center,ring[i-1],ring[i]));
        if(!Number.isFinite(radius))radius=0;
      }
      // The half-diagonal is strictly inside the nearest region boundary.
      const size=Math.min(105,Math.max(0,radius*Math.SQRT2*.88));
      const visible=team.logo_fits_at_campus && size>0;
      metrics.push({team_id:team.team_id,center,radius,size,visible,reason:team.logo_exception});
      if(visible) {
        element('image',{href:team.logo_data,x:center[0]-size/2,y:center[1]-size/2,width:size,height:size,
          class:'school-logo','data-team-id':team.team_id,preserveAspectRatio:'xMidYMid meet'},logos);
      }
    }
    if(selected!==null) {
      const region=regionById.get(selected),team=byId.get(selected);
      if(region)element('path',{d:path(region),class:'selected-border'});
      const center=projection([team.longitude,team.latitude]);
      if(center)element('circle',{cx:center[0],cy:center[1],r:6,fill:'none',stroke:'#142c35','stroke-width':1.5});
    }
    window.CFB_MAP.logoMetrics=metrics;
    window.CFB_MAP.ready=true;
  }
  function selectTeam(id) {
    selected=id; $('team-select').value=id===null?'':String(id);
    const t=byId.get(id);
    if(!t) {
      $('team-logo').hidden=true;$('team-name').textContent='Who’s closest?';
      $('county-count').textContent=assignments.length.toLocaleString();$('county-label').textContent='counties & equivalents';
      $('region-share').textContent=teams.length;$('share-label').textContent='FBS programs';
      $('panel-label').textContent='A geography of proximity';
      $('team-detail').textContent='Distance alone decides the color. State lines, conference affiliations, and fan allegiances do not affect the result.';
      $('team-coordinates').textContent='';
    } else {
      $('team-logo').src=t.logo_data;$('team-logo').alt=t.school+' logo';$('team-logo').hidden=false;
      $('team-name').textContent=t.school;$('panel-label').textContent='Main campus · '+t.state;
      $('county-count').textContent=t.county_count.toLocaleString();$('county-label').textContent='counties assigned';
      $('region-share').textContent=(100*t.county_count/assignments.length).toFixed(1)+'%';$('share-label').textContent='of all counties';
      $('team-detail').replaceChildren();
      const swatch=document.createElement('span');swatch.id='team-color';swatch.style.background=t.color;
      const p=document.createElement('p');p.append(swatch,document.createTextNode(t.color.toUpperCase()+' · primary color'));$('team-detail').append(p);
      const note=document.createElement('p');
      note.textContent=t.logo_exception==='no_counties'?'No county reference point is closest to this campus. Its location is shown as a dot.':
        t.logo_exception==='campus_outside_region'?'This campus lies in a county assigned to another team. A centered logo cannot fit in its own region; the campus is shown as a dot.':
        'The logo is centered on campus and sized to stay inside its county region. Zoom in to see smaller regions.';
      $('team-detail').append(note);
      $('team-coordinates').textContent=`${t.latitude.toFixed(4)}°, ${t.longitude.toFixed(4)}°`;
    }
    scheduleOverlay();
  }
  try {
    await Plotly.newPlot(gd,[countyTrace,locationTrace],layout,{responsive:true,displayModeBar:false,scrollZoom:true,showLink:false});
    gd.on('plotly_afterplot',scheduleOverlay);gd.on('plotly_relayout',scheduleOverlay);gd.on('plotly_relayouting',scheduleOverlay);
    gd.on('plotly_click',event=>{
      const p=event.points?.[0];if(!p)return;
      selectTeam(Number(p.customdata[p.curveNumber===0?4:2]));
    });
    for(const t of [...teams].sort((a,b)=>a.school.localeCompare(b.school))) {
      const opt=document.createElement('option');opt.value=t.team_id;opt.textContent=t.school;$('team-select').append(opt);
    }
    $('team-select').addEventListener('change',e=>selectTeam(e.target.value?Number(e.target.value):null));
    for(const name of ['show-logos','show-borders'])$(name).addEventListener('change',scheduleOverlay);
    $('show-counties').addEventListener('change',()=>Plotly.restyle(gd,{'marker.line.width':$('show-counties').checked?.28:0},[0]));
    $('reset').addEventListener('click',async()=>{
      selectTeam(null);await Plotly.relayout(gd,{'geo.projection.scale':1,'geo.center.lon':-96,'geo.center.lat':38});scheduleOverlay();
    });
    for(const [id,factor] of [['zoom-in',1.5],['zoom-out',1/1.5]])$(id).addEventListener('click',()=>{
      Plotly.relayout(gd,{'geo.projection.scale':Math.max(.8,Math.min(30,gd._fullLayout.geo.projection.scale*factor))});
    });
    $('export').addEventListener('click',async()=>{
      const button=$('export');button.disabled=true;
      try {
        const url=await Plotly.toImage(gd,{format:'svg',width:gd._fullLayout.width,height:gd._fullLayout.height});
        const content=await (await fetch(url)).text();
        const doc=new DOMParser().parseFromString(content,'image/svg+xml');
        const group=doc.createElementNS(svgNS,'g');
        for(const child of overlay.children)group.appendChild(doc.importNode(child,true));
        // Inline style so the exported file preserves boundaries and shadows without page CSS.
        group.querySelectorAll('.territory-border').forEach(p=>{p.setAttribute('fill','none');p.setAttribute('stroke','#ffffff99');p.setAttribute('stroke-width','.65');});
        group.querySelectorAll('.selected-border').forEach(p=>{p.setAttribute('fill','none');p.setAttribute('stroke','#162e36');p.setAttribute('stroke-width','2');});
        doc.documentElement.appendChild(group);
        const blob=new Blob([new XMLSerializer().serializeToString(doc)],{type:'image/svg+xml'});
        const href=URL.createObjectURL(blob),a=document.createElement('a');a.href=href;a.download='closest-fbs-teams-2025.svg';a.click();setTimeout(()=>URL.revokeObjectURL(href),1000);
      } catch(error){$('footer-status').textContent='Export failed: '+error.message;}finally{button.disabled=false;}
    });
    $('header-count').textContent=`${teams.length} campuses · 50 states + D.C.`;
    $('fit-note').textContent=`${data.logo_exceptions.length} campuses cannot fit a logo under whole-county assignment. Their locations remain visible as dots.`;
    $('footer-status').textContent=`${assignments.length.toLocaleString()} counties & equivalents · ${teams.length} FBS teams · Great-circle distance · Main campus`;
    $('map-status').hidden=true;selectTeam(null);drawOverlay();
    new ResizeObserver(()=>{Plotly.Plots.resize(gd);scheduleOverlay();}).observe(gd.parentElement);
  } catch(error) {
    $('map-status').hidden=false;$('map-status').textContent='Unable to draw the map: '+error.message;
    console.error(error);
  }
})();
