"""Measure native Blender Laplacian control-set capacity for existing brow targets.

Diagnostic only. Consumes existing Goal-1 attachments and transferred marker
trajectories. It does not recalculate video motion, edit source GLBs, or use a
custom deformation solver.
"""
import json, sys
from pathlib import Path
from collections import defaultdict
import bpy
import numpy as np
from mathutils import Vector

CONTROL_ORDER = [70,63,105,336,293,334,159,145,386,374,46,53,52,65,55,276,283,282,295,285,
                 10,67,103,109,108,338,297,333,332,299,300,301,302,303,304,305,306,307,308,309,310,311,312,313,314,315]
SIZES = [3,6,12,24,48]

def arg(name):
    a=sys.argv[sys.argv.index('--')+1:]
    return Path(a[a.index(name)+1]).resolve()

def components(n, faces):
    p=list(range(n))
    def f(x):
        while p[x]!=x: p[x]=p[p[x]]; x=p[x]
        return x
    def u(a,b):
        a,b=f(a),f(b)
        if a!=b:p[b]=a
    for t in faces:u(int(t[0]),int(t[1]));u(int(t[1]),int(t[2]));u(int(t[2]),int(t[0]))
    out=defaultdict(list)
    for i in range(n):out[f(i)].append(i)
    return list(out.values())

def edges(faces):
    c=defaultdict(int)
    for t in faces:
        for a,b in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])):c[tuple(sorted((int(a),int(b))))]+=1
    return c

def extract(source, goal_path, marker_path):
    goal=json.loads(goal_path.read_text()); rec={int(x['index']):x for x in goal['records'] if x.get('meshXYZ') is not None}
    markers=json.loads(marker_path.read_text());
    if any(i not in rec for i in range(468)): raise RuntimeError('Goal-1 attachments do not cover all 468 IDs')
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(source))
    body=max([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices))
    local=np.empty((len(body.data.vertices),3),float);body.data.vertices.foreach_get('co',local.ravel())
    m=np.asarray(body.matrix_world,float); world=local@m[:3,:3].T+m[:3,3]
    target=np.asarray([rec[i]['meshXYZ'] for i in range(468)])
    center=np.mean(target[[33,263,1,152]],axis=0); radius=float(np.max(np.linalg.norm(target-center,axis=1))*1.20)
    dist=np.linalg.norm(world-center,axis=1); raw=[];seen=set()
    for poly in body.data.polygons:
        pv=[int(v) for v in poly.vertices]
        if any(dist[v]<=radius for v in pv):
            for k in range(1,len(pv)-1):
                t=(pv[0],pv[k],pv[k+1]); key=tuple(sorted(t))
                if key in seen:continue
                if np.linalg.norm(np.cross(world[t[1]]-world[t[0]],world[t[2]]-world[t[0]]))<=max(radius*radius*1e-12,1e-18):continue
                seen.add(key);raw.append(t)
    original=sorted({v for t in raw for v in t});lookup={v:i for i,v in enumerate(original)};faces=[tuple(lookup[v] for v in t) for t in raw]
    comps=components(len(original),faces); d=markers['samples']['100']; n=markers['neutral']; eye=float(markers['eyeWidth'])
    motion=np.asarray([np.linalg.norm(np.asarray(d[i])-np.asarray(n[i])) for i in range(468)])
    candidates=[i for i in CONTROL_ORDER if i in rec]
    # Keep the canonical brow/eyelid ordering, then add other actually moving
    # landmarks by descending measured displacement. No new targets are made.
    candidates += [i for i in np.argsort(-motion).tolist() if i not in candidates and motion[i] > max(1e-4, .001*eye)]
    return body,local,world,rec,markers,original,faces,comps,radius,candidates,motion,m

def basis_anchors(coords, members):
    ids=list(range(len(members))); p=coords[np.asarray(ids)]
    out=[0]
    if len(ids)>1:out.append(int(np.argmax(np.linalg.norm(p-p[0],axis=1))))
    if len(ids)>2:
        a,b=p[out[0]],p[out[1]]; line=b-a; ln=max(float(np.linalg.norm(line)),1e-12)
        out.append(int(np.argmax([np.linalg.norm(q-a-line*np.dot(q-a,line)/(ln*ln)) for q in p])))
    return out

def solve_anchor_deltas(rec, neutral, target, ids, local_vertices):
    cols=sorted({int(v) for i in ids for v in rec[i]['triangleVertexIndices']}); col={v:j for j,v in enumerate(cols)}
    A=np.zeros((len(ids),len(cols))); b=np.zeros((len(ids),3))
    for row,i in enumerate(ids):
        tri=rec[i]['triangleVertexIndices']; bary=np.asarray(rec[i]['barycentricCoordinates'],float)
        for v,w in zip(tri,bary): A[row,col[int(v)]]=w
        b[row]=np.asarray(target[i])-np.asarray(neutral[i])
    rank=int(np.linalg.matrix_rank(A)); x=np.linalg.lstsq(A,b,rcond=None)[0]; residual=float(np.max(np.abs(A@x-b))) if len(b) else 0
    return cols,x,rank,residual

def native(coords,faces,anchors,move_deltas,local_to_global):
    mesh=bpy.data.meshes.new('__goal2_controlset_mesh__');mesh.from_pydata(coords.tolist(),[],[tuple(map(int,t)) for t in faces]);mesh.update()
    obj=bpy.data.objects.new('__goal2_controlset_obj__',mesh);bpy.context.collection.objects.link(obj)
    group=obj.vertex_groups.new(name='__goal2_controlset_anchors__');group.add([int(x) for x in anchors],1.0,'REPLACE')
    mod=obj.modifiers.new(name='__goal2_controlset_laplacian__',type='LAPLACIANDEFORM');mod.vertex_group=group.name;mod.iterations=30
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    bind=False;bind_error=None;eval_error=None
    try:bpy.ops.object.laplaciandeform_bind(modifier=mod.name);bind=bool(mod.is_bind)
    except Exception as e:bind_error=repr(e)
    out=None
    if bind:
        try:
            for v,d in move_deltas.items():obj.data.vertices[int(v)].co+=Vector(tuple(map(float,d)))
            obj.data.update();bpy.context.view_layer.update();ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();out=np.empty((len(me.vertices),3),float);me.vertices.foreach_get('co',out.ravel());ev.to_mesh_clear()
        except Exception as e:eval_error=repr(e)
    base=coords; free=np.ones(len(base),bool);free[list(set(anchors))]=False
    delta=None if out is None else out-base; fd=None if delta is None else delta[free]
    result={'bind':bind,'bindError':bind_error,'evaluationError':eval_error,'maxFreeMotion':None if fd is None or not len(fd) else float(np.max(np.linalg.norm(fd,axis=1))),'rmsFreeMotion':None if fd is None or not len(fd) else float(np.sqrt(np.mean(np.sum(fd*fd,axis=1)))),'solverStatus':'free_motion' if fd is not None and len(fd) and np.max(np.linalg.norm(fd,axis=1))>1e-9 else ('no_free_motion' if fd is not None else 'not_evaluated')}
    bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh);return result,out

def main():
    source,goal_path,marker_path,out_path=arg('--source'),arg('--goal1'),arg('--markers'),arg('--output')
    body,local,world,rec,markers,original,faces,comps,radius,candidates,motion,matrix=extract(source,goal_path,marker_path)
    target={i:markers['samples']['100'][i] for i in range(468)}; neutral={i:markers['neutral'][i] for i in range(468)}; eye=float(markers['eyeWidth'])
    controls_by_component=[]; rows=[]
    for ci,members in enumerate(comps):
        member_set=set(members); comp_faces=[t for t in faces if all(v in member_set for v in t)]
        clook={v:j for j,v in enumerate(members)}; cf=[tuple(clook[v] for v in t) for t in comp_faces]; co=local[np.asarray([original[i] for i in members])]; cw=world[np.asarray([original[i] for i in members])]
        ids=[]
        original_to_proxy={v:i for i,v in enumerate(original)}
        for i in candidates:
            if all(original_to_proxy.get(int(v)) in member_set for v in rec[i]['triangleVertexIndices']):ids.append(i)
        if len(ids)<3:continue
        control_sets={s:ids[:min(s,len(ids))] for s in SIZES}
        control_sets['all_relevant']=ids
        component_row={'component':ci,'vertices':len(members),'triangles':len(cf),'candidateLandmarks':ids,'tests':[]}
        comp_orig_to_local={original[members[j]]:j for j in range(len(members))}
        for size,sel in control_sets.items():
            cols,x,rank,res=solve_anchor_deltas(rec,neutral,target,sel,local)
            moving={comp_orig_to_local[v]:x[j] for j,v in enumerate(cols) if v in comp_orig_to_local}
            chosen=basis_anchors(cw,members); anchors=sorted(set(chosen)|set(moving))
            r,out=native(co,cf,anchors,moving,None)
            # Reconstruct selected attachments from evaluated component mesh.
            achieved=[];requested=[]
            if out is not None:
                for i in sel:
                    tri=[clook[original_to_proxy[int(v)]] for v in rec[i]['triangleVertexIndices']];b=np.asarray(rec[i]['barycentricCoordinates'],float)
                    achieved.append(np.sum(b[:,None]*out[tri],axis=0) @ matrix[:3,:3].T + matrix[:3,3]);requested.append(np.asarray(target[i]))
            err=np.linalg.norm(np.asarray(achieved)-np.asarray(requested),axis=1) if achieved else np.asarray([])
            component_row['tests'].append({'controlSet':size,'independentLandmarks':len(sel),'actualAnchorVertices':len(anchors),'selectedIds':sel,'barycentricRank':rank,'barycentricResidual':res,'requestedMotionMax':float(np.max([motion[i] for i in sel])),'achievedMotionMax':None if out is None else float(np.max(np.linalg.norm(np.asarray(achieved)-np.asarray([neutral[i] for i in sel]),axis=1))),'landmarkErrorMedian':None if not len(err) else float(np.median(err)),'landmarkErrorP95':None if not len(err) else float(np.percentile(err,95)),**r})
        rows.append(component_row)
    out={'source':str(source),'goal1':str(goal_path),'markers':str(marker_path),'body':body.name,'targetVertices':len(local),'proxyVertices':len(original),'proxyTriangles':len(faces),'goal1AttachmentCount':len(rec),'required468AttachmentCount':sum(i in rec for i in range(468)),'eyeWidth':eye,'meaningfulCandidateCount':len(candidates),'canonicalControlOrder':CONTROL_ORDER,'components':rows,'step1Pass':all(i in rec for i in range(468)),'step2Executed':True}
    out_path.parent.mkdir(parents=True,exist_ok=True);out_path.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
