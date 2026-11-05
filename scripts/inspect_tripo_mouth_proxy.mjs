import { chromium } from 'playwright';
import { writeFile } from 'node:fs/promises';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
try {
  await page.goto(process.env.VELA_URL || 'http://127.0.0.1:4174', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !document.querySelector('#speak')?.disabled, null, { timeout: 90000 });
  await page.locator('#characterSelect').selectOption('tripo');
  await page.getByText('vela-photoreal-faced.glb:', { exact: false }).waitFor({ timeout: 90000 });
  await page.waitForTimeout(1800);
  const result = await page.evaluate(async () => {
    const THREE = await import('three');
    const h = window.talkingHead;
    const meshes=[];
    h.armature.traverse(object=>{if(object.isMesh){object.visible=true;meshes.push({object,name:object.name});}});
    const cavity=meshes.find(x=>/Generated_inner_mouth_surface/.test(x.name))?.object;
    const body=meshes.find(x=>x.object!==cavity)?.object;
    const teeth=meshes.find(x=>/VelaTransplantedTeeth/.test(x.name))?.object;
    const tongue=meshes.find(x=>/VelaTransplantedTongue/.test(x.name))?.object;
    if(!cavity||!body)throw new Error(`Expected face and mouth meshes; found ${meshes.map(x=>x.name).join(', ')}`);
    const stableTarget=new THREE.Vector3(0.04,1.65,0.1);
    h.controls.enabled=false;h.controls.target.copy(stableTarget);h.camera.position.set(0.04,1.65,3.0);h.camera.lookAt(stableTarget);h.camera.updateProjectionMatrix();h.camera.updateMatrixWorld(true);
    for(const mesh of [cavity,body,teeth,tongue].filter(Boolean))for(const name of Object.keys(mesh.morphTargetDictionary||{}))mesh.morphTargetInfluences[mesh.morphTargetDictionary[name]]=0;
    h.armature.updateMatrixWorld(true);if(cavity.isSkinnedMesh)cavity.skeleton.update();
    const boundsFor=()=>{
      const camera=h.camera;camera.updateMatrixWorld(true);h.scene.updateMatrixWorld(true);if(cavity.isSkinnedMesh)cavity.skeleton.update();
      const world=[],screen=[],v=new THREE.Vector3();
      for(let i=0;i<cavity.geometry.attributes.position.count;i++){cavity.getVertexPosition(i,v);const p=cavity.localToWorld(v.clone());world.push(p.clone());screen.push(p.project(camera));}
      return {worldMin:[Math.min(...world.map(p=>p.x)),Math.min(...world.map(p=>p.y)),Math.min(...world.map(p=>p.z))],worldMax:[Math.max(...world.map(p=>p.x)),Math.max(...world.map(p=>p.y)),Math.max(...world.map(p=>p.z))],projected:{left:Math.min(...screen.map(p=>(p.x+1)*innerWidth/2)),right:Math.max(...screen.map(p=>(p.x+1)*innerWidth/2)),top:Math.min(...screen.map(p=>(1-p.y)*innerHeight/2)),bottom:Math.max(...screen.map(p=>(1-p.y)*innerHeight/2))}};
    };
    const index=cavity.morphTargetDictionary.jawOpen;
    const neutral=boundsFor();
    cavity.visible=true;body.visible=true;
    const neutralImage=h.renderer.domElement.toDataURL('image/png');
    cavity.morphTargetInfluences[index]=1;body.morphTargetInfluences[body.morphTargetDictionary.jawOpen]=1;
    for(const mesh of [teeth,tongue].filter(Boolean))if(mesh.morphTargetDictionary.jawOpen!==undefined)mesh.morphTargetInfluences[mesh.morphTargetDictionary.jawOpen]=1;
    h.armature.updateMatrixWorld(true);if(cavity.isSkinnedMesh)cavity.skeleton.update();if(body.isSkinnedMesh)body.skeleton.update();h.renderer.render(h.scene,h.camera);
    const open=boundsFor(),openImage=h.renderer.domElement.toDataURL('image/png');
    const attr=body.geometry.morphAttributes.position[body.morphTargetDictionary.jawOpen],verts=[],p=new THREE.Vector3();
    for(let i=0;i<attr.count;i++)if(Math.abs(attr.getX(i))+Math.abs(attr.getY(i))+Math.abs(attr.getZ(i))>1e-7){body.getVertexPosition(i,p);const q=body.localToWorld(p.clone()).project(h.camera);verts.push([(q.x+1)*innerWidth/2,(1-q.y)*innerHeight/2]);}
    const bodyOpenBounds={left:Math.min(...verts.map(v=>v[0])),right:Math.max(...verts.map(v=>v[0])),top:Math.min(...verts.map(v=>v[1])),bottom:Math.max(...verts.map(v=>v[1])),moved:verts.length};
    const materials=Array.isArray(body.material)?body.material:[body.material];
    const materialSides=materials.map(m=>({name:m.name,side:m.side,doubleSide:THREE.DoubleSide,transparent:m.transparent}));
    materials.forEach(m=>m.side=THREE.FrontSide);cavity.material.side=THREE.DoubleSide;cavity.material.needsUpdate=true;h.renderer.render(h.scene,h.camera);
    const frontOnlyImage=h.renderer.domElement.toDataURL('image/png');
    cavity.material=new THREE.MeshBasicMaterial({color:0x160407,side:THREE.DoubleSide,depthTest:false,depthWrite:false});cavity.renderOrder=1000;h.renderer.render(h.scene,h.camera);
    const darkOverlayImage=h.renderer.domElement.toDataURL('image/png');
    cavity.visible=false;
    if(teeth){teeth.material=new THREE.MeshBasicMaterial({color:0xffffff,side:THREE.DoubleSide,depthTest:false});teeth.renderOrder=20;}
    if(tongue){tongue.material=new THREE.MeshBasicMaterial({color:0xff426e,side:THREE.DoubleSide,depthTest:false});tongue.renderOrder=21;}
    h.renderer.render(h.scene,h.camera);
    const dentalDebugImage=h.renderer.domElement.toDataURL('image/png');
    cavity.material.color.set(0xff00ff);h.renderer.render(h.scene,h.camera);
    const visibleImage=h.renderer.domElement.toDataURL('image/png');
    return {cavityName:cavity.name,bodyName:body.name,dentalMeshes:[teeth?.name,tongue?.name],targetCount:Object.keys(cavity.morphTargetDictionary).length,jawIndex:index,cameraPosition:h.camera.position.toArray(),cameraTarget:h.controls.target.toArray(),mouthMarkers:['upper_lip','lower_lip','mouth_corner_left','mouth_corner_right'].map(name=>({name,world:h.armature.getObjectByName(`VelaLandmark_${name}`).getWorldPosition(new THREE.Vector3()).toArray()})),neutral,open,bodyOpenBounds,materialSides,neutralImage,openImage,frontOnlyImage,darkOverlayImage,dentalDebugImage,visibleImage};
  });
  for(const [key,file] of [['neutralImage','verification/tripo-mouth-proxy-neutral.png'],['openImage','verification/tripo-mouth-proxy-open.png'],['frontOnlyImage','verification/tripo-mouth-front-only.png'],['darkOverlayImage','verification/tripo-mouth-dark-overlay.png'],['dentalDebugImage','verification/tripo-dental-transfer-debug.png'],['visibleImage','verification/tripo-mouth-proxy-debug.png']])await writeFile(file,Buffer.from(result[key].split(',')[1],'base64'));
  const {neutralImage,openImage,frontOnlyImage,darkOverlayImage,dentalDebugImage,visibleImage,...summary}=result;console.log(JSON.stringify(summary,null,2));
} finally { await browser.close(); }
