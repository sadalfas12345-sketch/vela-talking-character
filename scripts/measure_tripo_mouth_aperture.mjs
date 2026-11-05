import { chromium } from 'playwright';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

const base = process.env.VELA_URL || 'http://127.0.0.1:4174';
const avatarFile = process.env.VELA_AVATAR_FILE || null;
const avatarName = avatarFile ? path.basename(avatarFile) : 'vela-photoreal-faced.glb';
const evidenceDir = process.env.VELA_EVIDENCE_DIR || 'assets/tripo/vela-photoreal/verification';
await mkdir(evidenceDir, { recursive: true });
const donorFit = JSON.parse(await readFile('verification/avaturn-face-fit-landmark-points.json', 'utf8'));
const donorLandmarks = {
  triangles: donorFit.donorTrianglesAtLandmarks,
  barycentric: donorFit.donorBarycentric,
  indices: { mouth_corner_left:61, mouth_corner_right:291, upper_lip:13, lower_lip:14,
    eye_top_left:159, eye_bottom_left:145, eye_top_right:386, eye_bottom_right:374 }
};
const states = ['jawOpen','viseme_PP','viseme_O','viseme_E','viseme_I','viseme_U','viseme_FF','eyeBlinkLeft','eyeBlinkRight','mouthSmileLeft'];
const browser = await chromium.launch({headless:true});
const page = await browser.newPage({viewport:{width:1280,height:900},deviceScaleFactor:1});
try {
  await page.goto(base,{waitUntil:'domcontentloaded',timeout:60000});
  await page.waitForFunction(()=>!document.querySelector('#speak')?.disabled,null,{timeout:120000});
  if (avatarFile) {
    await page.locator('#characterFile').setInputFiles(avatarFile);
    await page.getByText(`${avatarName}:`,{exact:false}).waitFor({timeout:120000});
  } else {
    await page.locator('#characterSelect').selectOption('tripo');
    await page.getByText(`${avatarName}:`,{exact:false}).waitFor({timeout:120000});
  }
  await page.waitForTimeout(1000);
  const result = await page.evaluate(async ({states, donorLandmarks}) => {
    const THREE = await import('three');
    const h=window.talkingHead;
    h.stop();
    h.animQueue=[];
    h.controls.enabled=false;
    h.scene.updateMatrixWorld(true);
    const body=h.morphs.find(m=>m.name==='VelaTripoHead') || h.morphs.find(m=>m.name.startsWith('tripo_node_'));
    if(!body) throw new Error('Tripo facial mesh is missing');
    const names=['mouth_corner_left','mouth_corner_right','upper_lip','lower_lip','eye_top_left','eye_bottom_left','eye_top_right','eye_bottom_right'];
    const useDonorSurface=body.name==='VelaTripoHead' && body.geometry.attributes.position.count>=3663;
    const markers=useDonorSurface?null:Object.fromEntries(names.map(n=>{const o=h.armature.getObjectByName(`VelaLandmark_${n}`);if(!o)throw new Error(`Missing landmark ${n}`);return[n,o.getWorldPosition(new THREE.Vector3())]}));
    h.scene.updateMatrixWorld(true); for(const m of h.morphs)if(m.isSkinnedMesh)m.skeleton.update();
    const nearest=Object.fromEntries(names.map(n=>[n,{index:-1,distance:Infinity}]));
    const v=new THREE.Vector3();
    if(!useDonorSurface)for(let i=0;i<body.geometry.attributes.position.count;i++){
      body.getVertexPosition(i,v);v.applyMatrix4(body.matrixWorld);
      for(const n of names){const d=v.distanceToSquared(markers[n]);if(d<nearest[n].distance)nearest[n]={index:i,distance:d};}
    }
    const camRight=new THREE.Vector3(1,0,0).applyQuaternion(h.camera.quaternion).normalize();
    const camUp=new THREE.Vector3(0,1,0).applyQuaternion(h.camera.quaternion).normalize();
    const positions=()=>{h.scene.updateMatrixWorld(true);for(const m of h.morphs)if(m.isSkinnedMesh)m.skeleton.update();const out={};for(const n of names){if(useDonorSurface){const li=donorLandmarks.indices[n],tri=donorLandmarks.triangles[li],bary=donorLandmarks.barycentric[li],p=new THREE.Vector3();for(let j=0;j<3;j++){body.getVertexPosition(tri[j],v);p.addScaledVector(v,bary[j]);}out[n]=body.localToWorld(p);}else{body.getVertexPosition(nearest[n].index,v);out[n]=body.localToWorld(v.clone());}}return out;};
    const project=p=>p.clone().project(h.camera);
    const measure=()=>{const p=positions();const left=p.mouth_corner_left,right=p.mouth_corner_right,upper=p.upper_lip,lower=p.lower_lip;const w=Math.abs(right.clone().sub(left).dot(camRight));const gap=Math.abs(lower.clone().sub(upper).dot(camUp));const lp=project(left),rp=project(right),up=project(upper),lo=project(lower);const screenW=Math.abs((rp.x-lp.x)*innerWidth/2),screenGap=Math.abs((lo.y-up.y)*innerHeight/2);const eyes={};for(const side of ['left','right']){const a=p[`eye_top_${side}`],b=p[`eye_bottom_${side}`];eyes[side]=Math.abs(b.clone().sub(a).dot(camUp));}return {mouthWidthMeters:w,apertureMeters:gap,apertureRatioW:w?gap/w:null,mouthWidthPixels:screenW,aperturePixels:screenGap,screenApertureRatioW:screenW?screenGap/screenW:null,eyeApertureMeters:eyes,anchorVertexDistancesMeters:Object.fromEntries(names.map(n=>[n,Math.sqrt(nearest[n].distance)])),anchorWorld:p};};
    const setState=name=>{for(const m of h.morphs)for(let i=0;i<m.morphTargetInfluences.length;i++)m.morphTargetInfluences[i]=0;for(const m of h.morphs){const i=m.morphTargetDictionary?.[name];if(i!==undefined)m.morphTargetInfluences[i]=1;}h.renderer.render(h.scene,h.camera);};
    setState('neutral');const neutral=measure();const frames={};const measurements={};
    for(const name of states){setState(name);measurements[name]=measure();frames[name]=h.renderer.domElement.toDataURL('image/png');}
    const baseEyes=neutral.eyeApertureMeters;
    for(const name of ['eyeBlinkLeft','eyeBlinkRight']){const side=name==='eyeBlinkLeft'?'left':'right';measurements[name].eyeClosureFraction=baseEyes[side]>0?1-measurements[name].eyeApertureMeters[side]/baseEyes[side]:null;}
    const smiles=measurements.mouthSmileLeft;smiles.leftCornerLiftW=(positions().mouth_corner_left.clone().sub((()=>{setState('neutral');return positions().mouth_corner_left})()).dot(camUp))/neutral.mouthWidthMeters;
    return {activation:{selected:document.querySelector('#characterSelect').value,compatibility:document.querySelector('#compatibility').textContent,mesh:body.name,landmarkMethod:useDonorSurface?'Avaturn landmark barycentric mapping on fitted full-head topology':'nearest target landmark vertices on the face surface'},neutral,measurements,frames};
  },{states,donorLandmarks});
  for(const [name,data] of Object.entries(result.frames)) await writeFile(path.join(evidenceDir,`aperture-${name}.png`),Buffer.from(data.split(',')[1],'base64'));
    const {frames,...report}=result;
    for (const measurement of [report.neutral,...Object.values(report.measurements)]) delete measurement.anchorWorld;
  await writeFile('verification/tripo-mouth-aperture-measurements.json',JSON.stringify(report,null,2)+'\n','utf8');
  console.log(JSON.stringify(report,null,2));
} finally { await browser.close(); }
