import json,cv2,numpy as np
from pathlib import Path
def align(x,ref,stable=[33,263,1,152]):
 M,_=cv2.estimateAffinePartial2D(x[stable,:2].astype(np.float32),ref[stable,:2].astype(np.float32),method=cv2.LMEDS);return np.c_[x[:,:2],np.ones(len(x))]@M.T
def main():
 d=json.loads(Path('verification/goal2-browInnerUp-proof/step1/video_landmarks.json').read_text());valid=[np.asarray(x['landmarks'],float) for x in d['frames'] if x['valid']];neutral=np.median(np.asarray(valid[:8]),axis=0);ref=neutral;eye=np.linalg.norm(ref[33,:2]-ref[263,:2]);base=valid[min(99,len(valid)-1)]
 tests={}
 for name,A in [('translation',np.array([[1,0,0.13],[0,1,-0.07]],float)),('rotation',np.array([[np.cos(.17),-np.sin(.17),0],[np.sin(.17),np.cos(.17),0]],float)),('scale',np.array([[1.21,0,0],[0,1.21,0]],float)),('combined',np.array([[1.13*np.cos(.11),-1.13*np.sin(.11),.09],[1.13*np.sin(.11),1.13*np.cos(.11),-.04]],float))]:
  xy=np.c_[base[:,:2],np.ones(468)]@A.T;z=base.copy();z[:,:2]=xy;got=align(z,ref);expected=align(base,ref);tests[name]={'maxErrorNormalized':float(np.max(np.linalg.norm(got-expected,axis=1)/eye)),'pass':bool(np.max(np.linalg.norm(got-expected,axis=1)/eye)<=.001)}
 # Controlled expression preservation: apply known brow and eyelid motion, then rigid transform.
 known=np.zeros((468,2));known[[70,63,105,336,293,334]]=[.011,.037];known[[159,145,386,374]]=[-.002,.006];expr=base.copy();expr[:,:2]+=known*eye;A=np.array([[1.17*np.cos(.13),-1.17*np.sin(.13),.08],[1.17*np.sin(.13),1.17*np.cos(.13),-.03]]);z=expr.copy();z[:,:2]=np.c_[expr[:,:2],np.ones(468)]@A.T;rec=align(z,base);meas=(rec-base[:,:2])/eye;err=np.linalg.norm(meas-known,axis=1);tests['expressionPreservation']={'maxErrorNormalized':float(err.max()),'medianErrorNormalized':float(np.median(err)),'pass':bool(np.mean(err[[70,63,105,336,293,334,159,145,386,374]]<=.001)>=.95)}
 out={'neutralRmsJitterNormalized':d['neutralRmsJitterNormalized'],'tests':tests,
      'criteria':{
        'neutral':{'value':float(d['neutralRmsJitterNormalized']),'threshold':0.005,'pass':bool(d['neutralRmsJitterNormalized']<=0.005)},
        'translation':tests['translation'],
        'rotationAndScale':{'maxErrorNormalized':float(max(tests['rotation']['maxErrorNormalized'],tests['scale']['maxErrorNormalized'])),'threshold':0.001,'pass':bool(tests['rotation']['pass'] and tests['scale']['pass'])},
        'expressionPreservation':tests['expressionPreservation']},
      'score':sum([5 if d['neutralRmsJitterNormalized']<=0.005 else 0,5 if tests['translation']['pass'] else 0,5 if tests['rotation']['pass'] and tests['scale']['pass'] else 0,5 if tests['expressionPreservation']['pass'] else 0]),
      'pass':bool(d['neutralRmsJitterNormalized']<=0.005 and tests['translation']['pass'] and tests['rotation']['pass'] and tests['scale']['pass'] and tests['expressionPreservation']['pass'])};Path('verification/goal2-browInnerUp-proof/step2-normalization.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
