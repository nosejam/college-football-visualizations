/* One offline document; each visualization keeps its own independent state. */
(function(){
  'use strict';
  const views=JSON.parse(document.getElementById('embedded-views').textContent);
  const tabs=[...document.querySelectorAll('[role=tab]')],loaded=new Set();
  const state=window.CFB_VISUALIZATIONS={active:null,loaded:[]};
  function sendVisibility(id,visible){
    if(loaded.has(id))document.getElementById('view-'+id).contentWindow.postMessage({type:'cfb-visualizations:visibility',visible},'*');
  }
  function activate(id,focus=false){
    if(!Object.hasOwn(views,id))id='predictor';
    const previous=state.active;
    if(previous&&previous!==id)sendVisibility(previous,false);
    state.active=id;
    for(const tab of tabs){
      const active=tab.dataset.view===id,panel=document.getElementById(tab.getAttribute('aria-controls'));
      tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;
      panel.classList.toggle('active',active);panel.setAttribute('aria-hidden',String(!active));panel.inert=!active;
      if(active&&focus)tab.focus();
    }
    if(!loaded.has(id)){
      const frame=document.getElementById('view-'+id);
      frame.addEventListener('load',()=>{
        document.querySelector('#panel-'+id+' .loading').hidden=true;
        sendVisibility(id,state.active===id);
      },{once:true});
      loaded.add(id);state.loaded=[...loaded];frame.srcdoc=views[id];
    }else sendVisibility(id,true);
    if(location.hash!=='#'+id){try{history.replaceState(null,'','#'+id);}catch{location.hash=id;}}
  }
  function initialTab(){const hash=location.hash.slice(1);if(hash==='playoff-predictor')return 'predictor';return hash==='victory-cycles'||hash==='circle-of-suck'||hash==='circles-of-suck'?'circles':hash==='imperialism-map'?'imperialism':hash;}
  for(const [index,tab] of tabs.entries()){
    tab.addEventListener('click',()=>activate(tab.dataset.view));
    tab.addEventListener('keydown',event=>{
      let next=null;
      if(event.key==='ArrowRight')next=(index+1)%tabs.length;
      if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;
      if(event.key==='Home')next=0;if(event.key==='End')next=tabs.length-1;
      if(next!==null){event.preventDefault();activate(tabs[next].dataset.view,true);}
    });
  }
  window.addEventListener('hashchange',()=>activate(initialTab()));
  activate(initialTab());
})();
