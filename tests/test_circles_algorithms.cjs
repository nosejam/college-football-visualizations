const assert=require('node:assert/strict');
const C=require('../maps/circles-algorithms.js');
function brute(nodes,edges,minimum,required){
  const graph=C.graph(nodes,edges),cycles=[];
  for(const start of nodes){
    const path=[start],used=new Set(path);
    function visit(here){
      if(path.length>=minimum&&graph.adj.get(here).has(start)&&(required===null||path.includes(required)))cycles.push([...path]);
      for(const next of graph.adj.get(here))if(next>start&&!used.has(next)){used.add(next);path.push(next);visit(next);path.pop();used.delete(next);}
    }
    visit(start);
  }
  return cycles;
}
const triangle=[[1,2],[2,3],[3,1]];
assert.deepEqual(C.shortest(C.graph([1,2,3],triangle)),[1,2,3]);
assert.deepEqual(C.shortest(C.graph([1,2,3],[[1,2],[2,1],[1,3],[3,2]]),3),[1,3,2]);
assert.equal(C.shortest(C.graph([1,2],[[1,2],[2,1]]),3).length,0);
assert.equal(C.shortest(C.graph([1,2],[[1,2],[2,1]]),2).length,2);
assert.equal(C.valid([1,2,1],C.graph([1,2],[[1,2],[2,1]])),false);
const neighbors=C.neighborhood([1,2,3,4,5],[[1,2],[3,2],[3,4],[5,4]],1,2);
assert.deepEqual(neighbors.nodes,[1,2,3]); // Traversal follows played connections in both directions.
assert.deepEqual(neighbors.edges,[[1,2],[3,2]]);
assert.equal(neighbors.maxDepth,4);
assert.equal(C.neighborhood([1,2,3,4,5],[[1,2],[3,2],[3,4],[5,4]],1,Infinity).nodes.length,5);
let random=73;
function rng(){random=(1664525*random+1013904223)>>>0;return random/4294967296;}
let checks=0;
for(let trial=0;trial<45;trial++){
  const n=3+trial%5,nodes=Array.from({length:n},(_,i)=>i+1),edges=[];
  for(const a of nodes)for(const b of nodes)if(a!==b&&rng()<.36)edges.push([a,b]);
  for(const minimum of [2,3])for(const required of [null,nodes[trial%n]]){
    const cycles=brute(nodes,edges,minimum,required),small=cycles.length?Math.min(...cycles.map(c=>c.length)):0,large=cycles.length?Math.max(...cycles.map(c=>c.length)):0;
    const result=C.search({nodes,edges,minimum,required,timeLimitMs:2000,seed:trial+1});
    assert.equal(result.shortest.length,small,`shortest trial ${trial}`);
    assert.equal(result.largest.length,large,`longest trial ${trial}`);
    assert.equal(result.exact,true,`proof trial ${trial}`);
    assert.equal(result.upperBound,large);
    if(large)assert(C.valid(result.largest,C.graph(nodes,edges),minimum,required));
    checks++;
  }
}
const timeout=C.search({nodes:Array.from({length:20},(_,i)=>i),edges:Array.from({length:20},(_,i)=>[[i,(i+1)%20],[i,(i+3)%20]]).flat(),timeLimitMs:0});
assert.equal(timeout.exact,false);assert.equal(timeout.timedOut,true);
const hint=C.search({nodes:[1,2,3,4],edges:triangle,minimum:3,hint:[1,2,3],hintExact:true});
assert.equal(hint.exact,true);assert.equal(hint.largest.length,3);
const invalidHint=C.search({nodes:[1,2,3],edges:triangle,hint:[1,3,2],hintExact:true});
assert(C.valid(invalidHint.largest,C.graph([1,2,3],triangle)));
console.log(`Passed ${checks} random exhaustive comparisons plus direction, rematch, neighborhood, timeout, and hint checks.`);
// Exact-size searches must find intermediate lengths, not just size extremes.
let lengthChecks=0;
for(let trial=0;trial<20;trial++){
  const nodes=Array.from({length:6},(_,i)=>i+1),edges=[];
  for(const a of nodes)for(const b of nodes)if(a!==b&&rng()<.38)edges.push([a,b]);
  for(const required of [null,1])for(const length of [2,3,4,5,6]){
    const expected=new Set(brute(nodes,edges,2,required).filter(c=>c.length===length).map(c=>C.canonical(c).join(':')));
    const got=C.findLength({nodes,edges,length,required,timeLimitMs:2000,maxCycles:10000});
    assert.equal(got.exhausted,true);
    assert.deepEqual(new Set(got.cycles.map(c=>C.canonical(c).join(':'))),expected);
    for(const cycle of got.cycles)assert(C.valid(cycle,C.graph(nodes,edges),2,required));
    lengthChecks++;
  }
}
const chain=[[130,201],[201,251],[251,194],[194,2294],[2294,130]];
assert.deepEqual(C.findLength({nodes:[130,201,251,194,2294],edges:chain,length:5,required:130}).cycles,[[130,201,251,194,2294]]);
const tooShort=C.findLength({nodes:[1,2,3],edges:triangle,length:4});assert.equal(tooShort.cycles.length,0);assert.equal(tooShort.exhausted,true);
const capped=C.findLength({nodes:[1,2,3,4],edges:[[1,2],[2,3],[3,1],[2,4],[4,1]],length:3,maxCycles:1});assert.equal(capped.cycles.length,1);assert.equal(capped.exhausted,false);
const resumed=C.findLength({nodes:[1,2,3,4],edges:[[1,2],[2,3],[3,1],[2,4],[4,1]],length:3,maxCycles:50,existing:capped.cycles});assert.equal(resumed.cycles.length,2);
const uncertain=C.findLength({nodes:[1,2,3],edges:triangle,length:3,timeLimitMs:0});assert.equal(uncertain.cycles.length,0);assert.equal(uncertain.exhausted,false);assert.equal(uncertain.exact,false);
console.log(`Passed ${lengthChecks} exhaustive exact-size comparisons, the Michigan example, continuation, and timeout checks.`);
// Catalogs enumerate all small sets and require every chosen team on one simple cycle.
let catalogChecks=0;
for(let trial=0;trial<30;trial++){
  const nodes=[1,2,3,4,5,6],edges=[];
  for(const a of nodes)for(const b of nodes)if(a!==b&&rng()<.32)edges.push([a,b]);
  for(const required of [[],[1],[1,3],[1,3,5]]){
    const expected=brute(nodes,edges,2,null).filter(c=>required.every(id=>c.includes(id)));
    const got=C.catalog({nodes,edges,minimum:2,required,maxListed:10000,maxFound:10000,timeLimitMs:2000});
    assert.equal(got.exhausted,true);
    assert.deepEqual(new Set(got.cycles.map(c=>c.join(':'))),new Set(expected.map(c=>C.canonical(c).join(':'))));
    assert.equal(got.count,expected.length);
    assert.equal(got.shortest.length,expected.length?Math.min(...expected.map(c=>c.length)):0);
    assert.equal(got.largest.length,expected.length?Math.max(...expected.map(c=>c.length)):0);
    assert.equal(got.exact,true);assert.equal(got.shortestExact,true);
    for(const cycle of got.cycles)assert(C.valid(cycle,C.graph(nodes,edges),2,required));
    for(const length of [3,5]){
      const sized=C.findLength({nodes,edges,minimum:2,required,length,maxCycles:10000,timeLimitMs:2000});
      assert.deepEqual(new Set(sized.cycles.map(c=>c.join(':'))),new Set(expected.filter(c=>c.length===length).map(c=>C.canonical(c).join(':'))));
    }
    catalogChecks++;
  }
}
const completeNodes=[1,2,3,4,5,6],completeEdges=completeNodes.flatMap(a=>completeNodes.filter(b=>a!==b).map(b=>[a,b]));
const collapsed=C.catalog({nodes:completeNodes,edges:completeEdges,maxListed:10,maxFound:10000,timeLimitMs:2000});
assert(collapsed.collapsed);assert(collapsed.exhausted);assert.equal(collapsed.cycles.length,10);
assert.equal(collapsed.cycles.filter(c=>c.length===6).length,5);
assert.equal(collapsed.cycles.filter(c=>c.length===2).length,5);
const bounded=C.catalog({nodes:completeNodes,edges:completeEdges,maxFound:30,timeLimitMs:2000});
assert(bounded.limited);assert(!bounded.exhausted);
const noTime=C.catalog({nodes:completeNodes,edges:completeEdges,required:[1,3],timeLimitMs:0});
assert(noTime.timedOut);assert(!noTime.exhausted);assert(!noTime.shortestExact);
const hinted=C.catalog({nodes:[1,2,3],edges:triangle,required:[1,3],hint:[1,2,3],hintExact:true,timeLimitMs:0});
assert(hinted.exact);assert(!hinted.exhausted);assert.deepEqual(hinted.largest,[1,2,3]);
const played=[[1,2],[3,2],[3,4],[6,5]],path=C.connection([1,2,3,4,5,6],played,[1,4]);
assert.deepEqual(path.paths,[[1,2,3,4]]);assert.deepEqual(path.edges,[[1,2],[3,2],[3,4]]);assert(path.connected);
assert.deepEqual(new Set(C.connection([1,2,3,4,5,6],played,[2]).nodes),new Set([2,3,1]));
const disconnected=C.connection([1,2,3,4,5,6],played,[1,5]);assert(!disconnected.connected);assert.deepEqual(disconnected.edges,[[1,2],[6,5]]);
console.log(`Passed ${catalogChecks} exhaustive catalog and multi-team comparisons; bounded lists, proof flags, shortest paths, and disconnected fallbacks.`);
