"""Directed win graphs and exact reference cycle searches for football results."""
from collections import deque
import time


def strongly_connected(nodes,edges):
    adjacency={n:[] for n in nodes};reverse={n:[] for n in nodes}
    for a,b in edges:
        if a in adjacency and b in adjacency and a!=b:adjacency[a].append(b);reverse[b].append(a)
    seen=set();order=[]
    def visit(n):
        seen.add(n)
        for other in adjacency[n]:
            if other not in seen:visit(other)
        order.append(n)
    for n in sorted(nodes):
        if n not in seen:visit(n)
    seen.clear();result=[]
    def collect(n,part):
        seen.add(n);part.append(n)
        for other in reverse[n]:
            if other not in seen:collect(other,part)
    for n in reversed(order):
        if n not in seen:
            part=[];collect(n,part);result.append(sorted(part))
    return sorted(result,key=lambda p:(-len(p),p))


def canonical(cycle):
    if not cycle:return []
    index=cycle.index(min(cycle))
    return cycle[index:]+cycle[:index]


def valid_cycle(cycle,edges,minimum=3,required=None):
    edge_set=set(map(tuple,edges))
    return (len(cycle)>=minimum and len(set(cycle))==len(cycle)
            and (required is None or required in cycle)
            and all((cycle[i],cycle[(i+1)%len(cycle)]) in edge_set for i in range(len(cycle))))


def shortest_cycle(nodes,edges,minimum=3,required=None):
    """Exact shortest simple directed cycle (minimum supported lengths: 2 or 3)."""
    assert minimum in (2,3)
    adjacency={n:set() for n in nodes}
    for a,b in edges:
        if a in adjacency and b in adjacency and a!=b:adjacency[a].add(b)
    best=[]
    for start in ([required] if required is not None else sorted(nodes)):
        if start not in adjacency:continue
        for first in sorted(adjacency[start]):
            parent={first:None};queue=deque([first])
            while queue:
                here=queue.popleft()
                for other in sorted(adjacency[here]):
                    if other==start:
                        if minimum==3 and here==first:continue
                        path=[here]
                        while parent[path[-1]] is not None:path.append(parent[path[-1]])
                        candidate=canonical([start]+list(reversed(path)))
                        if not best or (len(candidate),candidate)<(len(best),best):best=candidate
                        queue.clear();break
                    if other not in parent:parent[other]=here;queue.append(other)
            if best and len(best)==minimum:return best
    return best


def longest_cycle(nodes,edges,minimum=3,time_limit=12,initial_cycle=None,initial_upper=None):
    """Solve single-cycle MILPs by eliminating subtours, retaining certified bounds.

    Every eliminated subtour is first retained as a feasible candidate. Thus no
    cycle longer than our incumbent is cut off. A maximum cycle cover bounds any
    remaining single cycle; matching that bound proves global optimality.
    """
    import numpy as np
    from scipy.optimize import milp,Bounds,LinearConstraint
    from scipy.sparse import lil_matrix
    started=time.monotonic();deadline=started+time_limit
    edges=sorted(set(map(tuple,edges)))
    components=[c for c in strongly_connected(nodes,edges) if len(c)>=minimum]
    best=shortest_cycle(nodes,edges,minimum)
    if initial_cycle and valid_cycle(initial_cycle,edges,minimum) and len(initial_cycle)>len(best):best=canonical(initial_cycle)
    if not best:return dict(cycle=[],exact=True,upper_bound=0)
    component_bounds=[]
    for component in components:
        n=len(component);upper=min(n,initial_upper) if initial_upper is not None else n
        if n<=len(best):component_bounds.append(n);continue
        allowed=set(component);links=[(a,b) for a,b in edges if a in allowed and b in allowed]
        indices={node:i for i,node in enumerate(component)};cuts=[]
        while time.monotonic()<deadline and upper>len(best):
            matrix=lil_matrix((n*2+1+len(cuts),len(links)),dtype=float)
            lower=np.full(matrix.shape[0],-np.inf);bounds=np.full(matrix.shape[0],np.inf)
            for j,(a,b) in enumerate(links):
                matrix[indices[a],j]=1;matrix[indices[b],j]-=1
                matrix[n+indices[a],j]=1;matrix[2*n,j]=1
            lower[:n]=bounds[:n]=0;bounds[n:2*n]=1;lower[2*n]=max(minimum,len(best)+1)
            for k,part in enumerate(cuts):
                for j,(a,b) in enumerate(links):
                    if a in part and b in part:matrix[2*n+1+k,j]=1
                bounds[2*n+1+k]=len(part)-1
            remaining=max(.005,deadline-time.monotonic())
            solved=milp(-np.ones(len(links)),integrality=np.ones(len(links)),bounds=Bounds(0,1),
                constraints=LinearConstraint(matrix.tocsc(),lower,bounds),
                options={'time_limit':remaining,'mip_rel_gap':0})
            if solved.status==2:upper=len(best);break
            dual=getattr(solved,'mip_dual_bound',None)
            if dual is not None:upper=min(upper,max(len(best),int(-dual+1e-6)))
            if solved.x is None:break
            successor={a:b for (a,b),value in zip(links,solved.x) if value>.5}
            visited=set();cycles=[]
            for start in sorted(successor):
                if start in visited:continue
                cycle=[];here=start
                while here not in visited:
                    visited.add(here);cycle.append(here);here=successor[here]
                assert here==start
                cycles.append(cycle)
                if len(cycle)>=minimum and (len(cycle)>len(best) or (len(cycle)==len(best) and canonical(cycle)<best)):
                    best=canonical(cycle)
            # Join disjoint cover cycles by exchanging two directed edges.
            # Every joined candidate is a genuine single cycle in the original graph.
            merged=[list(c) for c in cycles]
            changed=True
            link_set=set(links)
            while changed:
                changed=False
                for i in range(len(merged)):
                    if changed:break
                    for j in range(i+1,len(merged)):
                        first,second=merged[i],merged[j]
                        for a_index,a in enumerate(first):
                            if changed:break
                            b=first[(a_index+1)%len(first)]
                            for c_index,c in enumerate(second):
                                d=second[(c_index+1)%len(second)]
                                if (a,d) in link_set and (c,b) in link_set:
                                    joined=first[a_index+1:]+first[:a_index+1]+second[c_index+1:]+second[:c_index+1]
                                    assert valid_cycle(joined,links,minimum=2)
                                    merged[i]=joined;merged.pop(j);changed=True;break
                        if changed:break
            for cycle in merged:
                if len(cycle)>=minimum and len(cycle)>len(best):best=canonical(cycle)
            if upper<=len(best):break
            cuts.extend(set(c) for c in cycles)
        component_bounds.append(upper)
    upper=max(component_bounds+[len(best)])
    assert valid_cycle(best,edges,minimum)
    return dict(cycle=best,exact=upper<=len(best),upper_bound=upper)


def certify_cycle(nodes,edges,initial_cycle,initial_upper,minimum=3,time_limit=60):
    """Stronger connected-cycle MILP for difficult cached snapshots.

    Exactly one selected vertex is designated root. Lazy connectivity cuts force
    every selected vertex into its root's directed cycle, without fixing a root
    that might exclude a better answer.
    """
    import numpy as np
    from scipy.optimize import milp,Bounds,LinearConstraint
    from scipy.sparse import lil_matrix
    links=sorted(set(map(tuple,edges)))
    assert valid_cycle(initial_cycle,links,minimum)
    parts=[p for p in strongly_connected(nodes,links) if len(p)>len(initial_cycle)]
    if not parts:return dict(cycle=canonical(initial_cycle),exact=True,upper_bound=len(initial_cycle))
    eligible=set(n for p in parts for n in p)
    nodes=sorted(eligible);links=[(a,b) for a,b in links if a in eligible and b in eligible]
    best=canonical(initial_cycle)
    n=len(nodes);m=len(links);indices={node:i for i,node in enumerate(nodes)};cuts=[];upper=initial_upper
    upper=min(upper,max(map(len,parts)))
    # Any improvement must contain a vertex outside the incumbent cycle.
    variable_upper=np.ones(m+n)
    for i,node in enumerate(nodes):
        if node in initial_cycle:variable_upper[m+i]=0
    deadline=time.monotonic()+time_limit
    outgoing={node:[j for j,(a,b) in enumerate(links) if a==node] for node in nodes}
    while time.monotonic()<deadline and upper>len(best):
        row_count=3*n+2+sum(len(part) for part in cuts)
        A=lil_matrix((row_count,m+n));lb=np.full(row_count,-np.inf);ub=np.full(row_count,np.inf)
        for j,(a,b) in enumerate(links):
            A[indices[a],j]=1;A[indices[b],j]-=1;A[n+indices[a],j]=1
            A[2*n+indices[a],j]=-1;A[3*n,j]=1
        lb[:n]=ub[:n]=0;ub[n:2*n]=1;ub[2*n:3*n]=0;lb[3*n]=max(minimum,len(best)+1)
        for node,i in indices.items():A[2*n+i,m+i]=1;A[3*n+1,m+i]=1
        lb[3*n+1]=ub[3*n+1]=1
        row=3*n+2
        for part in cuts:
            crossing=[j for j,(a,b) in enumerate(links) if a in part and b not in part]
            for node in part:
                for j in crossing:A[row,j]+=1
                for j in outgoing[node]:A[row,j]-=1
                for root in part:A[row,m+indices[root]]+=1
                lb[row]=0;row+=1
        solved=milp(np.r_[-np.ones(m),np.zeros(n)],integrality=np.ones(m+n),bounds=Bounds(np.zeros(m+n),variable_upper),
            constraints=LinearConstraint(A.tocsc(),lb,ub),options={'time_limit':max(.005,deadline-time.monotonic()),'mip_rel_gap':0})
        if solved.status==2:return dict(cycle=best,exact=True,upper_bound=len(best))
        dual=getattr(solved,'mip_dual_bound',None)
        if dual is not None:upper=min(upper,max(len(best),int(-dual+1e-6)))
        if solved.x is None:break
        successor={a:b for (a,b),value in zip(links,solved.x[:m]) if value>.5};seen=set();cycles=[]
        for start in sorted(successor):
            if start in seen:continue
            here=start;cycle=[]
            while here not in seen:seen.add(here);cycle.append(here);here=successor[here]
            assert here==start;cycles.append(cycle)
            if len(cycle)>=minimum and len(cycle)>len(best):best=canonical(cycle)
        if upper<=len(best):break
        cuts.extend(set(c) for c in cycles)
    return dict(cycle=best,exact=upper<=len(best),upper_bound=max(upper,len(best)))
