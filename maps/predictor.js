/* Scenario editing, sortable projections, and an isolated simulation worker. */
(function(){
  'use strict';
  const data=window.CFB_PREDICTOR_DATA,$=id=>document.getElementById(id),byId=new Map(data.teams.map(t=>[t.id,t]));
  const state={index:data.frames.length-1,choices:{},result:null,sort:'objectiveRank',descending:false,worker:null,url:null,request:0,running:false};
  const columnOrder=[10,11,1,2,3,4,5,6,7,8,9,18,19,20,13,15,16,12,14,17,0];
  const headers=[...document.querySelectorAll('#prediction-table thead tr th')];document.querySelector('#prediction-table thead tr').replaceChildren(...columnOrder.map(i=>headers[i]));
  const api=window.CFB_PLAYOFF={ready:false,state,data};
  const date=value=>new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',timeZone:'America/New_York'}).format(new Date(value));
  const opponent=(g,id)=>g.home===id?g.away:g.home;
  const current=()=>data.frames[state.index];
  function stop(){state.request++;state.worker?.terminate();if(state.url)URL.revokeObjectURL(state.url);state.worker=null;state.url=null;state.running=false;}
  function count(item,key){return item?.[key]||0;}
  function pct(cell,item,key,out,na=false){
    cell.className='pct';
    if(na){cell.textContent='—';cell.title='Independent: no conference championship';return;}
    if(!state.result){cell.textContent='…';return;}
    const n=state.result.iterations,value=count(item,key);
    if(out){cell.textContent='0.0%';cell.title='Proven out under this model';cell.classList.add('out');}
    else if(!value){cell.textContent='~0%';cell.title=`No wins in ${n.toLocaleString()} simulations; not proven eliminated`;cell.classList.add('rare');}
    else if(value===n&&item?.playoffClinched&&key==='playoffs'){cell.textContent='100%';cell.title='Verified: selection is resolved from completed results';}
    else if(value===n){cell.textContent='~100%';cell.title=`All ${n.toLocaleString()} simulations; not proven clinched`;}
    else{const rounded=(100*value/n).toFixed(n>=20000?1:0);cell.textContent=Number(rounded)===0?'<0.1%':Number(rounded)===100?'>99.9%':rounded+'%';const ph=value/n,se=1.96*Math.sqrt(ph*(1-ph)/n);cell.title=`${value.toLocaleString()} of ${n.toLocaleString()} simulations · approximate 95% sampling interval ${Math.max(0,100*(ph-se)).toFixed(1)}–${Math.min(100,100*(ph+se)).toFixed(1)}%; model uncertainty is additional`;}

  }
  function rows(){
    const result=new Map((state.result?.teams||[]).map(t=>[t.id,t])),needle=$('team-filter').value.trim().toLowerCase();
    const teams=data.roster.map(id=>({team:byId.get(id),item:result.get(id)})).filter(({team})=>(team.school+' '+team.conference).toLowerCase().includes(needle));
    const metric=({team,item})=>state.sort==='name'?team.school:state.sort==='elo'?(item?.elo??current().elo[team.id]):(item?.[{conference:'conferenceWins',playoff:'playoffs',championship:'championships'}[state.sort]||state.sort]??(state.sort.endsWith('Rank')?999:0));
    teams.sort((a,b)=>{const x=metric(a),y=metric(b),d=typeof x==='string'?x.localeCompare(y):x-y;return (state.descending?-d:d)||a.team.school.localeCompare(b.team.school);});
    const active=document.activeElement?.dataset,focus=active?.mode?{team:active.team,mode:active.mode}:null;
    $('prediction-rows').replaceChildren();
    for(const {team,item} of teams){
      const tr=document.createElement('tr');tr.dataset.team=team.id;
      const elo=document.createElement('td');elo.className=Object.keys(state.choices).length?'scenario-elo':'';elo.textContent=(item?.elo??current().elo[team.id]).toFixed(1);tr.append(elo);
      const logo=document.createElement('td'),img=document.createElement('img');img.src=team.logo;img.alt=team.school+' logo';logo.append(img);tr.append(logo);
      const name=document.createElement('td'),strong=document.createElement('span'),detail=document.createElement('span');strong.className='team-name';strong.textContent=team.school;strong.tabIndex=0;strong.setAttribute('role','button');strong.style.cursor='pointer';strong.addEventListener('click',()=>explain(team.id));strong.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();explain(team.id);}});detail.className='team-detail';
      const games=CFBPredictor.targets(data,state.index,team.id),next=games[0],fixed=games.filter(g=>state.choices[g.id]!==undefined),w=fixed.filter(g=>state.choices[g.id]===team.id).length;
      const r=current().records?.[team.id],record=r?` · ${r.wins}–${r.losses}${r.ties?'–'+r.ties:''}`:'';
      detail.textContent=`${team.conference}${record}${next?' · Next: '+byId.get(opponent(next,team.id)).school+' ('+date(next.date)+')'+(next.after_selection?' · After Selection Day':''):' · No known remaining regular-season game'}${fixed.length?' · Fixed '+w+' W / '+(fixed.length-w)+' L':''}`;
      name.append(strong,detail);tr.append(name);
      for(const mode of ['win-next','lose-next','win-out','lose-out']){
        const td=document.createElement('td');td.className='check-cell';const input=document.createElement('input');input.type='checkbox';input.dataset.team=team.id;input.dataset.mode=mode;
        const selection=mode.endsWith('next')?games.slice(0,1):games,agree=selection.filter(g=>state.choices[g.id]!==undefined&&(mode.startsWith('win')?state.choices[g.id]===team.id:state.choices[g.id]!==team.id)).length;
        input.checked=selection.length>0&&agree===selection.length;input.indeterminate=agree>0&&agree<selection.length;input.disabled=!selection.length;
        input.setAttribute('aria-label',mode.replace('-',' ')+' for '+team.school);input.title=selection.length?selection.map(g=>date(g.date)+': '+team.school+' vs '+byId.get(opponent(g,team.id)).school).join('\n'):'No known remaining regular-season game';
        input.addEventListener('change',()=>{const change=CFBPredictor.setChoice(data,state.index,state.choices,team.id,mode,input.checked);state.choices=change.choices;$('scenario-note').textContent=change.replaced?`${change.replaced} earlier fixed outcome${change.replaced===1?' was':'s were'} replaced. Both teams now agree on each game's result.`:'';launch();});td.append(input);tr.append(td);
      }
      const conf=document.createElement('td'),playoff=document.createElement('td'),champ=document.createElement('td');pct(conf,item,'conferenceWins',item?.conferenceOut,!team.conference||team.conference==='FBS Independents');pct(playoff,item,'playoffs',item?.playoffOut);pct(champ,item,'championships',item?.playoffOut);tr.append(conf,playoff,champ);
      for(const key of ['objectiveRank','sp','powerRank','sor','sorRank','sos','projectedWins','projectedRank','automatic','atlarge','byes']){const td=document.createElement('td');
        if(['automatic','atlarge','byes'].includes(key))pct(td,item,key,false);
        else if(!item)td.textContent='…';
        else if(key==='sp'){td.textContent=item.sp===null?'—':item.sp.toFixed(1);td.title=item.sp===null?'No applicable SP+ rating; Elo is used explicitly.':'Fixed SP+ snapshot rating';}
        else if(key==='sos')td.textContent=(100*item.sos).toFixed(1)+'%';
        else if(key==='projectedWins')td.textContent=item.projectedWins.toFixed(1)+'–'+item.projectedLosses.toFixed(1);
        else td.textContent=Number.isInteger(item[key])?item[key]:item[key]?.toFixed(2)??'—';tr.append(td);
      }const cells=[...tr.children];tr.replaceChildren(...columnOrder.map(i=>cells[i]));$('prediction-rows').append(tr);
    }
    if(focus)$('prediction-rows').querySelector(`input[data-team="${focus.team}"][data-mode="${focus.mode}"]`)?.focus({preventScroll:true});
    for(const th of document.querySelectorAll('th[data-column]')){const selected=th.dataset.column===state.sort;th.setAttribute('aria-sort',selected?(state.descending?'descending':'ascending'):'none');th.querySelector('.sort-mark').textContent=selected?(state.descending?'↓':'↑'):'';}
    $('table-caption').textContent=`${teams.length} of ${data.roster.length} FBS teams · Objective rank = completed + fixed résumé · Power rank predicts strength · Sort columns to compare`;
  }
  function scenario(){
    const selected=data.games.filter(g=>state.choices[g.id]!==undefined);$('scenario-summary').textContent=`${selected.length} fixed future result${selected.length===1?'':'s'} · Win/lose out applies to known regular-season games.`;
    $('scenario-details').hidden=!selected.length;
    $('scenario-heading').textContent=`Fixed future results (${selected.length})`;$('clear-scenario').disabled=!selected.length;$('scenario-games').replaceChildren();
    for(const g of selected){const row=document.createElement('div');row.className='scenario-item';const text=document.createElement('span'),remove=document.createElement('button'),win=state.choices[g.id],lose=opponent(g,win);text.textContent=`${date(g.date)} · ${byId.get(win).school} beats ${byId.get(lose).school}`;remove.textContent='Remove';remove.setAttribute('aria-label','Remove fixed result '+g.id);remove.addEventListener('click',()=>{delete state.choices[g.id];launch();});row.append(text,remove);$('scenario-games').append(row);}
  }
  function launch(){
    stop();state.result=null;state.running=true;const request=state.request;const available=new Set(data.games.filter(g=>(!g.score||current().week===null||g.week>current().week)).map(g=>String(g.id)));
    state.choices=Object.fromEntries(Object.entries(state.choices).filter(([id])=>available.has(id)));scenario();titleControls();rows();
    const iterations=Number($('simulation-count').value);$('progress').max=iterations;$('progress').value=0;$('prediction-table-wrap').setAttribute('aria-busy','true');$('prediction-status').textContent='Simulating remaining games, conference titles, and the CFP…';
    try{
      state.url=URL.createObjectURL(new Blob([$('predictor-worker-source').textContent],{type:'text/javascript'}));state.worker=new Worker(state.url);
      state.worker.onmessage=event=>{if(event.data.request!==state.request)return;if(event.data.type==='error'){stop();$('prediction-status').textContent='Projection failed: '+event.data.message;$('prediction-table-wrap').setAttribute('aria-busy','false');return;}
        state.result=event.data.result;api.result=state.result;if(event.data.type==='complete'){rows();if(state.explained)explain(state.explained);$('rating-status').textContent=state.result.ratingMessage+' · '+(state.result.snapshot?'Snapshot '+new Date(state.result.snapshot).toLocaleString()+' · ':'')+'Model '+state.result.modelVersion+' · '+state.result.fallbackGames+' SP+-missing matchups in the selection schedule. SP+ probability calibration: unvalidated transfer from pregame Elo.';$('model-warnings').hidden=!state.result.warnings.length;$('model-warning-list').textContent=state.result.warnings.join(' ');}$('progress').value=state.result.iterations;
        const complete=event.data.type==='complete';$('prediction-status').textContent=`${state.result.iterations.toLocaleString()} simulations ${complete?'complete':'processed'} · 12 playoff places · ${data.year}, ${current().label}`;
        if(complete){state.running=false;state.worker.terminate();state.worker=null;URL.revokeObjectURL(state.url);state.url=null;$('prediction-table-wrap').setAttribute('aria-busy','false');api.ready=true;}
      };
      state.worker.onerror=event=>{stop();$('prediction-status').textContent='Background simulation failed: '+event.message;};
      state.worker.postMessage({request,data,options:{frameIndex:state.index,choices:state.choices,iterations,seed:Number($('simulation-seed').value),method:$('rating-method').value}});
    }catch(error){stop();$('prediction-status').textContent='Could not start simulation: '+error.message;}
  }
  function change(index){state.index=Math.max(0,Math.min(data.frames.length-1,index));state.choices={};$('scenario-note').textContent='Changing the week clears future picks.';controls();launch();}
  function controls(){const f=current();$('week-slider').max=data.frames.length-1;$('week-slider').value=state.index;$('week-slider').setAttribute('aria-valuetext',f.label);$('week-label').textContent=f.label;$('week-description').textContent=f.date?'Observed results through '+date(f.date):'No observed results · all teams start at 1500';$('timeline-end').textContent=data.frames.at(-1).label;$('previous-week').disabled=!state.index;$('next-week').disabled=state.index===data.frames.length-1;$('data-status').textContent=`${data.year} · ${data.roster.length} FBS teams · Saved results as of ${new Date(data.as_of).toLocaleString()} · Objective SOR selection`;}
  for(const button of document.querySelectorAll('[data-sort]'))button.addEventListener('click',()=>{const key=button.dataset.sort;if(state.sort===key)state.descending=!state.descending;else{state.sort=key;state.descending=key!=='name'&&!key.endsWith('Rank');}rows();});
  $('team-filter').addEventListener('input',rows);$('recompute').addEventListener('click',launch);$('simulation-count').addEventListener('change',launch);$('rating-method').addEventListener('change',launch);$('simulation-seed').addEventListener('change',launch);$('clear-scenario').addEventListener('click',()=>{state.choices={};$('scenario-note').textContent='All future results are uncertain again.';launch();});
  $('week-slider').addEventListener('input',event=>change(Number(event.target.value)));$('previous-week').addEventListener('click',()=>change(state.index-1));$('next-week').addEventListener('click',()=>change(state.index+1));
  function explain(id){
    state.explained=id;const item=state.result?.teams.find(t=>t.id===id),team=byId.get(id);if(!item)return;
    const panel=$('resume-content');panel.replaceChildren();const p=document.createElement('p');
    p.textContent=`${team.school}: objective rank ${item.objectiveRank}, power rank ${item.powerRank}. Completed + fixed record ${item.record.wins}–${item.record.losses}; SOR ${item.sor.toFixed(4)} (reference tail ${Math.exp(-item.sor).toPrecision(3)}); SOS difficulty ${(item.sos*100).toFixed(1)}%. ${item.qualityWins} wins over top-25 power opponents, ${item.weakLosses} losses to lower-power opponents. Conference wins ${item.standingWins}. Projected title-game participation ${(100*item.conferenceFinals/state.result.iterations).toFixed(1)}%; title wins ${(100*item.conferenceWins/state.result.iterations).toFixed(1)}%. Projected final record ${item.projectedWins.toFixed(1)}–${item.projectedLosses.toFixed(1)} through Selection Day. SP+ ${item.sp===null?'unavailable (Elo fallback)':item.sp.toFixed(1)}. Near ties: SOS, head-to-head differential, power, stable ID.`;
    panel.append(p);const h=document.createElement('p');h.textContent='Head-to-head: '+(item.headToHead.map(g=>`${byId.get(g.winner)?.school} beat ${byId.get(g.loser)?.school}${g.wins>1?' ('+g.wins+' times)':''}`).join('; ')||'No completed or fixed matchups.');panel.append(h);$('resume-explanation').open=true;
  }
  function titleControls(){
    $('title-pick-controls').replaceChildren();const games=data.games.filter(g=>g.championship&&(!g.score||current().week===null||g.week>current().week));
    if(!games.length)$('title-pick-controls').textContent='No championship matchup is scheduled yet. Participants will be determined by simulated conference standings.';
    for(const g of games){const label=document.createElement('label'),select=document.createElement('select');label.textContent=byId.get(g.home).school+' vs '+byId.get(g.away).school+' ';for(const [value,text] of [['','Simulate'],[g.home,byId.get(g.home).school+' wins'],[g.away,byId.get(g.away).school+' wins']]){const option=document.createElement('option');option.value=value;option.textContent=text;select.append(option);}select.value=state.choices[g.id]??'';select.addEventListener('change',()=>{if(select.value)state.choices[g.id]=Number(select.value);else delete state.choices[g.id];launch();});label.append(select);$('title-pick-controls').append(label);}
  }
  const oldControls=controls;controls=function(){oldControls();titleControls();};
  controls();launch();
})();
