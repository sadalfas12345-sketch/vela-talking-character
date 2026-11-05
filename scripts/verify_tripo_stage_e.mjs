import { chromium } from 'playwright';
import { readFile, writeFile } from 'node:fs/promises';

const url = process.env.VELA_URL || 'http://127.0.0.1:4174';
const calibration = JSON.parse(await readFile('assets/tripo/vela-photoreal/face-calibration.json', 'utf8'));
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
const errors = [];
const consoleErrors=[];
page.on('pageerror', error => errors.push(error.message));
page.on('console',message=>{if(message.type()==='error')consoleErrors.push(message.text());});
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForFunction(() => !document.querySelector('#speak')?.disabled, null, { timeout: 90000 });
  await page.locator('#characterSelect').selectOption('tripo');
  await page.getByText('vela-photoreal-faced.glb:', { exact: false }).waitFor({ timeout: 120000 });
  const activation=await page.evaluate(()=>({selected:document.querySelector('#characterSelect').value,progress:document.querySelector('#progress').textContent,compatibility:document.querySelector('#compatibility').textContent,avatar:window.talkingHead?.avatar?.url}));
  if(activation.selected!=='tripo'||activation.progress==='Character load failed'||activation.compatibility.includes('activation failed'))throw new Error(`Tripo activation failed: ${JSON.stringify({activation,consoleErrors})}`);
  await page.waitForFunction(() => window.talkingHead?.avatar?.url?.startsWith('blob:'), null, { timeout: 120000 });
  await page.waitForTimeout(1200);
  const result = await page.evaluate(async calibration => {
    const THREE = await import('three');
    const h = window.talkingHead;
    const root = h.armature;
    if (!root) throw new Error('TalkingHead initialized without the Tripo Armature root.');
    h.scene.updateMatrixWorld(true);
    const bonePoint = name => {
      const bone = root.getObjectByName(name);
      return bone?.getWorldPosition(new THREE.Vector3()) || null;
    };
    const lm = name => {
      const marker=root.getObjectByName(`VelaLandmark_${name}`);
      if(!marker) throw new Error(`Missing live registered landmark ${name}`);
      return marker.getWorldPosition(new THREE.Vector3());
    };
    const eyeLeft = lm('eye_top_left').add(lm('eye_bottom_left')).multiplyScalar(0.5);
    const eyeRight = lm('eye_top_right').add(lm('eye_bottom_right')).multiplyScalar(0.5);
    const eyeLine=eyeRight.clone().sub(eyeLeft).normalize();
    const brow = lm('brow_left').add(lm('brow_right')).multiplyScalar(0.5);
    const chin = lm('chin');
    const faceUp = brow.clone().sub(chin).normalize();
    const faceForward = faceUp.clone().cross(eyeLine).normalize();
    const faceOrigin = lm('upper_lip').add(lm('lower_lip')).multiplyScalar(0.5);
    const faceHeightBox = new THREE.Box3().setFromObject(root);
    const characterHeight = faceHeightBox.max.y - faceHeightBox.min.y;
    const skeletons=new Set();root.traverse(object=>{if(object.isSkinnedMesh&&object.skeleton)skeletons.add(object.skeleton);});
    const savedBones=[];
    for(const skeleton of skeletons)for(const bone of skeleton.bones)savedBones.push({bone,position:bone.position.clone(),quaternion:bone.quaternion.clone(),scale:bone.scale.clone()});
    const hipsObject=root.getObjectByName('Hips');
    const liveHipsWorld=hipsObject?.getWorldPosition(new THREE.Vector3())||new THREE.Vector3();
    const liveHipsLocal=hipsObject?.position.clone()||new THREE.Vector3();
    const displacementStats=(rootTranslationArmature=new THREE.Vector3())=>{
      h.scene.updateMatrixWorld(true);
      const distances=[];
      root.traverse(object=>{
        if(!object.isSkinnedMesh||!object.geometry.attributes.position)return;
        object.skeleton.update();
        const worldOrigin=object.localToWorld(new THREE.Vector3());
        const armatureOrigin=root.localToWorld(new THREE.Vector3());
        const armatureShift=root.localToWorld(rootTranslationArmature.clone()).sub(armatureOrigin);
        const meshShift=object.worldToLocal(worldOrigin.clone().add(armatureShift)).sub(object.worldToLocal(worldOrigin.clone()));
        const source=object.geometry.attributes.position,actual=new THREE.Vector3(),base=new THREE.Vector3();
        for(let i=0;i<source.count;i++){
          base.fromBufferAttribute(source,i);object.getVertexPosition(i,actual);
          distances.push(actual.sub(base).sub(meshShift).length());
        }
      });
      distances.sort((a,b)=>a-b);
      const percentile=p=>distances[Math.min(distances.length-1,Math.floor((distances.length-1)*p))]||0;
      return {vertexCount:distances.length,maxDisplacementMeters:distances.at(-1)||0,medianDisplacementMeters:percentile(.5),p95DisplacementMeters:percentile(.95),maxDisplacementFractionOfHeight:characterHeight?(distances.at(-1)||0)/characterHeight:null};
    };
    const runtimeRawDisplacement=displacementStats();
    const boneRestDeviation=[];
    for(const skeleton of skeletons)skeleton.pose();
    h.scene.updateMatrixWorld(true);
    const restHipsWorld=hipsObject?.getWorldPosition(new THREE.Vector3())||new THREE.Vector3();
    const expectedRootTranslation=liveHipsWorld.sub(restHipsWorld);
    const expectedRootTranslationLocal=liveHipsLocal.sub(hipsObject?.position||new THREE.Vector3());
    for(const item of savedBones){
      const restPosition=item.bone.position.clone(),restQuaternion=item.bone.quaternion.clone();
      boneRestDeviation.push({bone:item.bone.name,translationMeters:item.position.distanceTo(restPosition),rotationDegrees:THREE.MathUtils.radToDeg(item.quaternion.angleTo(restQuaternion))});
    }
    const restPoseDisplacement=displacementStats();
    for(const item of savedBones){item.bone.position.copy(item.position);item.bone.quaternion.copy(item.quaternion);item.bone.scale.copy(item.scale);}
    for(const skeleton of skeletons)skeleton.update();
    const runtimeUnexpectedDisplacement=displacementStats(expectedRootTranslationLocal);
    const meshToSkeleton={characterHeightMeters:characterHeight,expectedRootTranslationMeters:expectedRootTranslation.length(),runtimeRaw:runtimeRawDisplacement,runtimeUnexpected:runtimeUnexpectedDisplacement,bindRest:restPoseDisplacement,boneRestDeviation:boneRestDeviation.filter(x=>x.translationMeters>1e-6||x.rotationDegrees>.01).sort((a,b)=>b.translationMeters-a.translationMeters).slice(0,12)};
    const cameraToward = h.camera.position.clone().sub(faceOrigin).normalize();
    const cameraViewTowardFace=new THREE.Vector3(0,0,1).applyQuaternion(h.camera.quaternion).normalize();
    const hips = bonePoint('Hips'), neck = bonePoint('Neck');
    const leftShoulder = bonePoint('LeftShoulder'), rightShoulder = bonePoint('RightShoulder');
    const leftHip = bonePoint('LeftUpLeg'), rightHip = bonePoint('RightUpLeg');
    const angle = (a,b) => THREE.MathUtils.radToDeg(Math.acos(THREE.MathUtils.clamp(a.clone().normalize().dot(b.clone().normalize()),-1,1)));
    const torsoUp = neck.clone().sub(hips).normalize();
    const shoulderLine = rightShoulder.clone().sub(leftShoulder).normalize();
    const hipLine = rightHip.clone().sub(leftHip).normalize();
    const worldUp=new THREE.Vector3(0,1,0);
    const torsoForward = worldUp.clone().cross(shoulderLine).normalize();
    const hipForward = worldUp.clone().cross(hipLine).normalize();
    if (torsoForward.dot(faceForward) < 0) torsoForward.negate();
    if (hipForward.dot(faceForward) < 0) hipForward.negate();
    const canvas = h.renderer.domElement.getBoundingClientRect();h.camera.updateMatrixWorld(true);
    const faceBoxPoints = ['eye_outer_left','eye_outer_right','brow_left','brow_right','mouth_corner_left','mouth_corner_right','chin'].map(name=>lm(name).project(h.camera));
    const projected={left:canvas.left+Math.min(...faceBoxPoints.map(p=>(p.x+1)*canvas.width/2)),right:canvas.left+Math.max(...faceBoxPoints.map(p=>(p.x+1)*canvas.width/2)),top:canvas.top+Math.min(...faceBoxPoints.map(p=>(1-p.y)*canvas.height/2)),bottom:canvas.top+Math.max(...faceBoxPoints.map(p=>(1-p.y)*canvas.height/2))};
    const cameraRight = new THREE.Vector3(1,0,0).applyQuaternion(h.camera.quaternion);
    const cameraUp = new THREE.Vector3(0,1,0).applyQuaternion(h.camera.quaternion);
    const cameraForward = new THREE.Vector3(0,0,-1).applyQuaternion(h.camera.quaternion);
    const referenceUp = new THREE.Vector3(0,1,0).addScaledVector(cameraForward,-new THREE.Vector3(0,1,0).dot(cameraForward)).normalize();
    const cameraRoll = THREE.MathUtils.radToDeg(Math.atan2(cameraRight.dot(referenceUp),cameraUp.dot(referenceUp)));
    const cameraYaw=Math.atan2(cameraViewTowardFace.dot(eyeLine),cameraViewTowardFace.dot(faceForward))*180/Math.PI;
    const cameraPitch=Math.asin(THREE.MathUtils.clamp(cameraViewTowardFace.dot(faceUp),-1,1))*180/Math.PI;
    const poseOf=name=>{const b=root.getObjectByName(name);return b?{position:b.position.toArray(),rotation:b.rotation.toArray(),quaternion:b.quaternion.toArray()}:null;};
    const bones={hips:hips?.toArray(),neck:neck?.toArray(),leftShoulder:leftShoulder?.toArray(),rightShoulder:rightShoulder?.toArray(),leftHip:leftHip?.toArray(),rightHip:rightHip?.toArray(),pose:{Hips:poseOf('Hips'),Spine:poseOf('Spine'),Spine1:poseOf('Spine1'),Spine2:poseOf('Spine2'),Neck:poseOf('Neck'),Head:poseOf('Head')},rotationChannels:Object.fromEntries(['bodyRotateX','bodyRotateY','bodyRotateZ','headRotateX','headRotateY','headRotateZ'].map(n=>[n,h.mtAvatar[n]?{value:h.mtAvatar[n].value,applied:h.mtAvatar[n].applied,baseline:h.mtAvatar[n].baseline}:null]))};
    const eyeInfo=eye=>({name:eye?.name,parent:eye?.parent?.name,world:eye?.getWorldPosition(new THREE.Vector3()).toArray(),projected:eye?.getWorldPosition(new THREE.Vector3()).project(h.camera).toArray()});
    const live={faceForwardWorld:faceForward.toArray(),cameraFacingDegrees:angle(faceForward,cameraViewTowardFace),cameraPositionToFaceDegrees:angle(faceForward,cameraToward),cameraYawDegrees:cameraYaw,cameraPitchDegrees:cameraPitch,cameraRollDegrees:cameraRoll,headToHipDegrees:angle(faceForward,hipForward),headToTorsoDegrees:angle(faceForward,torsoForward),shoulderToHipDegrees:angle(torsoForward,hipForward)};
    const targetProjected=h.controls.target.clone().project(h.camera);
    return {stage:'E_talkinghead_initialized',viewport:[innerWidth,innerHeight],canvas:{x:canvas.x,y:canvas.y,width:canvas.width,height:canvas.height},document:{width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight},avatar:h.avatar.url,live,meshToSkeleton,projectedLandmarkFaceBox:projected,projectedControlsTarget:[canvas.left+(targetProjected.x+1)*canvas.width/2,canvas.top+(1-targetProjected.y)*canvas.height/2],eyes:{left:eyeInfo(h.objectLeftEye),right:eyeInfo(h.objectRightEye)},bones,camera:{position:h.camera.position.toArray(),target:h.controls.target.toArray(),fov:h.camera.fov},poseDiagnostics:{queue:h.animQueue.map(item=>item.template?.name),poseName:h.poseName,targetTemplate:h.poseTarget?.template,poseHead:h.poseTarget?.props?.['Head.quaternion']?.toArray?.(),poseBaseHead:h.poseBase?.props?.['Head.quaternion']?.toArray?.(),avatarDisableMoodPose:h.avatar?.avatarDisableMoodPose},errors:[]};
  }, calibration);
  result.errors=errors;result.consoleErrors=consoleErrors;result.activation=activation;
  await page.screenshot({path:'verification/tripo-stage-e-desktop.png',fullPage:true});
  result.neutralRestPose=await page.evaluate(async()=>{
    const THREE=await import('three'),h=window.talkingHead,root=h.armature;h.stop();
    const skeletons=new Set();root.traverse(o=>{if(o.isSkinnedMesh&&o.skeleton)skeletons.add(o.skeleton);});for(const skeleton of skeletons)skeleton.pose();h.scene.updateMatrixWorld(true);
    const lm=name=>root.getObjectByName(`VelaLandmark_${name}`).getWorldPosition(new THREE.Vector3());
    const eyeL=lm('eye_top_left').add(lm('eye_bottom_left')).multiplyScalar(.5),eyeR=lm('eye_top_right').add(lm('eye_bottom_right')).multiplyScalar(.5);
    const faceUp=lm('brow_left').add(lm('brow_right')).multiplyScalar(.5).sub(lm('chin')).normalize(),faceForward=faceUp.clone().cross(eyeR.sub(eyeL).normalize()).normalize();
    const hipL=root.getObjectByName('LeftUpLeg').getWorldPosition(new THREE.Vector3()),hipR=root.getObjectByName('RightUpLeg').getWorldPosition(new THREE.Vector3()),shL=root.getObjectByName('LeftShoulder').getWorldPosition(new THREE.Vector3()),shR=root.getObjectByName('RightShoulder').getWorldPosition(new THREE.Vector3()),hips=root.getObjectByName('Hips').getWorldPosition(new THREE.Vector3()),neck=root.getObjectByName('Neck').getWorldPosition(new THREE.Vector3()),up=new THREE.Vector3(0,1,0);
    const hipForward=up.clone().cross(hipR.sub(hipL).normalize()).normalize(),torsoForward=up.clone().cross(shR.sub(shL).normalize()).normalize();if(hipForward.dot(faceForward)<0)hipForward.negate();if(torsoForward.dot(faceForward)<0)torsoForward.negate();
    const cameraDirection=h.camera.position.clone().sub(lm('upper_lip').add(lm('lower_lip')).multiplyScalar(.5)).normalize(),angle=(a,b)=>THREE.MathUtils.radToDeg(Math.acos(THREE.MathUtils.clamp(a.clone().normalize().dot(b.clone().normalize()),-1,1)));
    return {faceForwardWorld:faceForward.toArray(),cameraFacingDegrees:angle(faceForward,cameraDirection),headToHipDegrees:angle(faceForward,hipForward),headToTorsoDegrees:angle(faceForward,torsoForward),shoulderToHipDegrees:angle(torsoForward,hipForward)};
  });
  await page.setViewportSize({width:412,height:915});await page.waitForTimeout(350);
  result.mobile=await page.evaluate(async()=>{
    const THREE=await import('three'),h=window.talkingHead,root=h.armature;h.renderer.render(h.scene,h.camera);h.camera.updateMatrixWorld(true);
    const canvas=h.renderer.domElement.getBoundingClientRect(),panel=document.querySelector('#talkForm').getBoundingClientRect(),names=['eye_outer_left','eye_outer_right','brow_left','brow_right','mouth_corner_left','mouth_corner_right','chin'];
    const p=names.map(name=>root.getObjectByName(`VelaLandmark_${name}`).getWorldPosition(new THREE.Vector3()).project(h.camera));
    const box={left:canvas.left+(Math.min(...p.map(x=>x.x))+1)*canvas.width/2,right:canvas.left+(Math.max(...p.map(x=>x.x))+1)*canvas.width/2,top:canvas.top+(1-Math.max(...p.map(x=>x.y)))*canvas.height/2,bottom:canvas.top+(1-Math.min(...p.map(x=>x.y)))*canvas.height/2};
    return {viewport:[innerWidth,innerHeight],canvas:{left:canvas.left,top:canvas.top,width:canvas.width,height:canvas.height},document:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],panelTop:panel.top,faceBox:box,faceWidthFraction:(box.right-box.left)/canvas.width,faceCenterOffsetFraction:(box.left+box.right-canvas.width)/2/canvas.width,errors:[]};
  });
  await page.screenshot({path:'verification/tripo-stage-e-mobile.png',fullPage:true});
  await page.setViewportSize({width:1280,height:900});await page.waitForTimeout(250);
  const landmarkDebug=await page.evaluate(async()=>{
    const THREE=await import('three');const h=window.talkingHead;const rows=[];
    const names=['eye_outer_left','eye_outer_right','eye_top_left','eye_top_right','brow_left','brow_right','upper_lip','lower_lip','mouth_corner_left','mouth_corner_right','chin'];
    for(const name of names){const marker=h.armature?.getObjectByName(`VelaLandmark_${name}`);if(!marker)continue;const color=name.includes('eye')?0x00ffff:name.includes('brow')?0xffff00:name.includes('lip')||name.includes('mouth')?0xff0000:0x00ff00;const geometry=new THREE.SphereGeometry(0.012,10,8);const material=new THREE.MeshBasicMaterial({color,depthTest:false});const sphere=new THREE.Mesh(geometry,material);sphere.position.copy(marker.getWorldPosition(new THREE.Vector3()));sphere.renderOrder=999;h.scene.add(sphere);rows.push({name,position:sphere.position.toArray(),color});}
    h.renderer.render(h.scene,h.camera);return rows;
  });
  await page.screenshot({path:'verification/tripo-stage-e-landmark-overlay.png',fullPage:true});
  await writeFile('verification/tripo-stage-e-landmark-overlay.json',JSON.stringify(landmarkDebug,null,2)+'\n');
  await writeFile('verification/tripo-gate2-stage-e.json',JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify(result,null,2));
  if(errors.length) throw new Error(`Uncaught browser errors: ${JSON.stringify(errors)}`);
} finally { await browser.close(); }
