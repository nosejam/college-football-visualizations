/* Shared offline theme; srcdoc views inherit and follow the outer app. */
(function(){
  'use strict';
  let preferred=null;try{preferred=localStorage.getItem('cfb-theme');}catch{}
  try{if(parent!==window)preferred=parent.document.documentElement.dataset.theme||preferred;}catch{}
  const media=window.matchMedia('(prefers-color-scheme: dark)');
  const initial=preferred==='dark'||preferred==='light'?preferred:media.matches?'dark':'light';
  let button;
  function set(theme,persist=true){
    if(!['light','dark'].includes(theme))return;
    document.documentElement.dataset.theme=theme;
    if(persist)preferred=theme;
    if(persist)try{localStorage.setItem('cfb-theme',theme);}catch{}
    if(button){button.textContent=theme==='dark'?'Light mode':'Dark mode';button.setAttribute('aria-checked',String(theme==='dark'));}
    window.dispatchEvent(new CustomEvent('cfb:themechange',{detail:{theme}}));
    for(const frame of document.querySelectorAll('iframe'))frame.contentWindow?.postMessage({type:'cfb-visualizations:theme',theme},'*');
  }
  function color(key){return getComputedStyle(document.documentElement).getPropertyValue('--'+key).trim();}
  window.CFB_THEME={set,color,get value(){return document.documentElement.dataset.theme;}};
  set(initial,false);
  window.addEventListener('message',event=>{if(event.source===parent&&event.data?.type==='cfb-visualizations:theme')set(event.data.theme,false);});
  document.addEventListener('DOMContentLoaded',()=>{
    button=document.getElementById('theme-toggle');
    if(!button&&parent===window){button=document.createElement('button');button.id='theme-toggle';button.className='theme-toggle standalone-theme';document.body.append(button);}
    if(button){button.type='button';button.setAttribute('role','switch');button.setAttribute('aria-label','Dark mode');button.addEventListener('click',()=>set(CFB_THEME.value==='dark'?'light':'dark'));set(CFB_THEME.value,false);}
  });
  media.addEventListener('change',event=>{if(!preferred)set(event.matches?'dark':'light',false);});
})();
