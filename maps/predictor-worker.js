self.onmessage=event=>{
  const {request,data,options}=event.data;
  try{const result=CFBPredictor.project(data,options,result=>self.postMessage({request,type:'progress',result}));self.postMessage({request,type:'complete',result});}
  catch(error){self.postMessage({request,type:'error',message:error.message});}
};
