/* CFBCycles is prepended to this worker in the standalone HTML. */
self.onmessage=event=>{
  const {request,options}=event.data;
  try {
    const result=(options.mode==='length'?CFBCycles.findLength:options.mode==='catalog'?CFBCycles.catalog:CFBCycles.search)(options,progress=>self.postMessage({request,type:'progress',result:progress}));
    self.postMessage({request,type:'complete',result});
  } catch(error){self.postMessage({request,type:'error',message:error.message});}
};
