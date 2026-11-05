import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.VELA_URL || 'http://127.0.0.1:4174';
const file = process.env.VELA_AVATAR_FILE || 'assets/tripo/vela-photoreal/vela-photoreal-faced.glb';
const fileName = path.basename(file);
const expectedSelection = /^(?:vela-photoreal-(?:faced|facefit-prototype)|vela-face-(?:surfacefit|fullprojection)-prototype|vela-fullhead-expanded-prototype)\.glb$/i.test(fileName) ? 'tripo' : 'imported';
const evidenceDir = process.env.VELA_EVIDENCE_DIR || 'verification/tripo-photoreal-runtime';
await mkdir(evidenceDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
const errorCounts = new Map();
let synthStatus = null;
page.on('pageerror', error => {
  const key = error.message;
  errorCounts.set(key, { count: (errorCounts.get(key)?.count || 0) + 1, stack: error.stack });
});
page.on('response', response => { if (response.url().includes('/v1/synthesize')) synthStatus = response.status(); });

try {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForFunction(() => !document.querySelector('#speak')?.disabled, null, { timeout: 90000 });
  const original = await page.evaluate(() => window.talkingHead?.avatar?.url);
  if (!original?.includes('avaturn.glb')) throw new Error(`Default avatar failed to load: ${original}`);

  await page.locator('#characterFile').setInputFiles(file);
  await page.getByText(`${fileName}:`, { exact: false }).waitFor({ timeout: 90000 });
  await page.waitForFunction(() => window.talkingHead?.avatar?.url?.startsWith('blob:'), null, { timeout: 90000 });
  const imported = await page.evaluate(() => ({
    status: document.querySelector('#compatibility').textContent,
    active: window.talkingHead.avatar.url,
    selected: document.querySelector('#characterSelect').value,
    morphs: Object.keys(window.talkingHead.mtAvatar || {}).filter(key => /^(jawOpen|mouthOpen|viseme_|eyeBlink|mouthSmile|mouthFrown|brow)/.test(key))
  }));
  if (imported.selected !== expectedSelection || imported.status.includes('activation failed')) throw new Error(`Tripo avatar did not activate cleanly: ${JSON.stringify(imported)}`);
  if (!imported.morphs.includes('viseme_aa') || !imported.morphs.includes('eyeBlinkLeft')) throw new Error(`Tripo morphs not registered: ${JSON.stringify(imported)}`);

  // First prove the imported mesh responds to real geometry controls directly.
  const direct = await page.evaluate(() => {
    const h = window.talkingHead;
    const mesh = [];
    h.scene.traverse(o => { if (o.isMesh && o.morphTargetDictionary?.jawOpen !== undefined) mesh.push(o); });
    const morphIndex = mesh[0]?.morphTargetDictionary.jawOpen;
    if (!mesh.length) return { meshCount: 0 };
    const values = mesh[0].morphTargetInfluences;
    const before = values[morphIndex] || 0;
    values[morphIndex] = 1;
    const changed = values[morphIndex] !== before;
    values[morphIndex] = 0;
    return { meshCount: mesh.length, morphIndex, changed };
  });
  if (!direct.meshCount || !direct.changed) throw new Error(`Imported jawOpen shape key is not controllable: ${JSON.stringify(direct)}`);
  const renderChecks=[];
  for (const [name, imageName] of [['jawOpen','jaw-open.png'],['viseme_aa','viseme-aa.png'],['eyeBlinkLeft','blink-left.png'],['eyeBlinkRight','blink-right.png'],['mouthSmileLeft','smile-left.png'],['mouthFrownLeft','frown-left.png'],['browInnerUp','brow-up.png']]) {
    const renderCheck=await page.evaluate(async name => {
      const THREE=await import('three');
      const h=window.talkingHead;
      const eyeWorld=h.objectLeftEye?.getWorldPosition(new THREE.Vector3());if(eyeWorld)eyeWorld.project(h.camera);
      let result={trackedMorphMeshes:h.morphs?.length||0,sceneMeshes:[],camera:{position:h.camera.position.toArray(),target:h.controls.target.toArray(),fov:h.camera.fov,distance:h.camera.position.distanceTo(h.controls.target)},leftEyeNdc:eyeWorld?.toArray()};
      const gl=h.renderer.getContext(),w=h.renderer.domElement.width,hh=h.renderer.domElement.height;
      const capture=()=>{const pixels=new Uint8Array(w*hh*4);gl.readPixels(0,0,w,hh,gl.RGBA,gl.UNSIGNED_BYTE,pixels);return pixels;};
      h.renderer.render(h.scene,h.camera);const before=capture();
      const beforeImage=h.renderer.domElement.toDataURL('image/png');
      const meshes=[];h.scene.traverse(o=>{if(o.isMesh){result.sceneMeshes.push({name:o.name,targets:Object.keys(o.morphTargetDictionary||{}).length,hasTarget:o.morphTargetDictionary?.[name]!==undefined});meshes.push(o);}});
      meshes.forEach(o=>{if(o.morphTargetDictionary?.[name]!==undefined){
        const i=o.morphTargetDictionary[name];o.morphTargetInfluences[i]=1;
        const a=o.geometry.morphAttributes.position?.[i];
        let maxDelta=0;if(a)for(let k=0;k<a.array.length;k++)maxDelta=Math.max(maxDelta,Math.abs(a.array[k]));
        const bounds=[Infinity,Infinity,-Infinity,-Infinity];let moved=0;
        if(a){h.scene.updateMatrixWorld(true);if(o.isSkinnedMesh)o.skeleton.update();h.camera.updateMatrixWorld(true);const p=new THREE.Vector3();for(let v=0;v<a.count;v++){const dx=a.getX(v),dy=a.getY(v),dz=a.getZ(v);if(Math.abs(dx)+Math.abs(dy)+Math.abs(dz)<1e-7)continue;moved++;if(o.getVertexPosition)o.getVertexPosition(v,p);else{p.fromBufferAttribute(o.geometry.attributes.position,v);if(o.geometry.morphTargetsRelative)p.add(new THREE.Vector3(dx,dy,dz));else p.set(dx,dy,dz);if(o.isSkinnedMesh)o.applyBoneTransform(v,p);}o.localToWorld(p);p.project(h.camera);const sx=(p.x+1)*w/2,sy=(1-p.y)*hh/2;bounds[0]=Math.min(bounds[0],sx);bounds[1]=Math.min(bounds[1],sy);bounds[2]=Math.max(bounds[2],sx);bounds[3]=Math.max(bounds[3],sy);}}
        result={...result,mesh:o.name,skinned:o.isSkinnedMesh,index:i,influence:o.morphTargetInfluences[i],targets:o.geometry.morphAttributes.position?.length,targetCount:a?.count,targetFirst:a?Array.from(a.array.slice(0,3)):null,maxDelta,relative:o.geometry.morphTargetsRelative,movedVertices:moved,projectedBounds:bounds};
      }});
      h.renderer.render(h.scene,h.camera);
      const after=capture();let changed=0;
      for(let i=0;i<after.length;i+=4)if(Math.abs(after[i]-before[i])+Math.abs(after[i+1]-before[i+1])+Math.abs(after[i+2]-before[i+2])>12)changed++;
      return { ...result, changedPixels:changed, beforeImage, image:h.renderer.domElement.toDataURL('image/png') };
    },name);
    const { image: renderedImage, beforeImage: neutralImage, ...renderSummary } = renderCheck;
    renderChecks.push({name, ...renderSummary});
    if(name==='jawOpen'&&renderCheck?.beforeImage)await writeFile(path.join(evidenceDir,'neutral.png'),Buffer.from(renderCheck.beforeImage.split(',')[1],'base64'));
    if(renderCheck?.image)await writeFile(path.join(evidenceDir,imageName),Buffer.from(renderCheck.image.split(',')[1],'base64'));
    if(!renderCheck?.changedPixels && (!renderCheck?.movedVertices || renderCheck.maxDelta < 0.0001))throw new Error(`${name} has neither rendered nor geometric deformation: ${JSON.stringify({...renderCheck,image:undefined,beforeImage:undefined})}`);
    await page.evaluate(name => {
      const h=window.talkingHead;
      h.morphs.forEach(o=>{if(o.morphTargetDictionary?.[name]!==undefined)o.morphTargetInfluences[o.morphTargetDictionary[name]]=0;});
      h.renderer.render(h.scene,h.camera);
    },name);
  }
  await page.screenshot({ path: path.join(evidenceDir,'desktop-neutral.png'), fullPage: true });
  await page.evaluate(() => {
    window.__tripoMotion = { mouth: 0, blink: 0, expression: 0, channels: {}, animationNames: [] };
    const head=window.talkingHead, originalSpeakAudio=head.speakAudio.bind(head);
    head.speakAudio=(payload,...args)=>{
      window.__tripoSpeechStartedAt=performance.now();
      window.__tripoAudioPayload={keys:Object.keys(payload||{}),wordCount:payload?.words?.length||0,visemes:payload?.visemes?.slice?.(0,8)||null,vtimes:payload?.vtimes?.slice?.(0,4)||null,vdurations:payload?.vdurations?.slice?.(0,4)||null};
      const result=originalSpeakAudio(payload,...args);
      const queued=head.speechQueue?.[0]?.anim;
      window.__tripoAudioPayload.queuedCount=queued?.length||0;
      window.__tripoAudioPayload.queuedFirst=queued?.[0] ? {ts:queued[0].ts,vs:queued[0].vs} : null;
      return result;
    };
    const started = performance.now();
    const sample = () => {
      const h = window.talkingHead, p = window.__tripoMotion;
      let liveMouthWeight=0;
      for (const n of ['jawOpen','mouthOpen','viseme_aa','viseme_E','viseme_O','viseme_PP','viseme_FF']) { const c=h.mtAvatar[n]; const weight=Math.max(c?.applied||0,c?.value||0); liveMouthWeight=Math.max(liveMouthWeight,weight); p.mouth=Math.max(p.mouth,weight); p.channels[n]=Math.max(p.channels[n]||0,weight); }
      p.animationNames=[...new Set(h.animQueue.filter(a=>a.template?.name==='viseme').map(a=>a.template.name+':'+Object.keys(a.vs||{}).join(',')))].slice(0,8);
      for (const n of ['eyeBlinkLeft','eyeBlinkRight']) p.blink = Math.max(p.blink, h.mtAvatar[n]?.applied || 0);
      for (const n of ['mouthSmileLeft','mouthSmileRight','mouthFrownLeft','mouthFrownRight','browInnerUp']) p.expression = Math.max(p.expression, h.mtAvatar[n]?.applied || 0);
      if (window.__tripoSpeechStartedAt && liveMouthWeight > (p.liveFrameWeight || 0.20)) {
        h.renderer.render(h.scene,h.camera);
        p.liveFrameWeight=liveMouthWeight;
        p.liveFrame={weight:liveMouthWeight,speaking:Boolean(h.isSpeaking),elapsedMs:performance.now()-window.__tripoSpeechStartedAt,image:h.renderer.domElement.toDataURL('image/png')};
      }
      if (performance.now() - started < 180000) requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
  });
  await page.locator('#emotion').selectOption('happy');
  await page.locator('#text').fill('I am absolutely gorgeous, and apparently I just failed my math test. Mother is going to be furious!');
  await page.locator('#speak').click();
  await page.waitForFunction(() => {
    const h=window.talkingHead;
    const weights=Object.fromEntries(['viseme_aa','viseme_O','viseme_U'].map(name=>[name,h?.mtAvatar[name]?.applied||0]));
    if (!h?.isSpeaking || Math.max(...Object.values(weights)) <= 0.20) return false;
    h.renderer.render(h.scene,h.camera);
    window.__tripoLiveVisemeFrame={weight:Math.max(...Object.values(weights)),weights,speaking:true,image:h.renderer.domElement.toDataURL('image/png')};
    return true;
  }, null, { timeout: 120000 }).catch(()=>{});
  const liveVisemeFrame = await page.evaluate(() => {
    return window.__tripoMotion?.liveFrame || window.__tripoLiveVisemeFrame || {weight:0,weights:{},speaking:false,image:null};
  });
  if (liveVisemeFrame.weight > 0 && liveVisemeFrame.image) await writeFile(path.join(evidenceDir,'speaking-canvas.png'),Buffer.from(liveVisemeFrame.image.split(',')[1],'base64'));
  await page.screenshot({ path: path.join(evidenceDir,'speaking-frame.png'), fullPage: true });
  await page.waitForFunction(() => !window.talkingHead?.isSpeaking, null, { timeout: 120000 }).catch(()=>{});
  await page.waitForTimeout(600);
  const motion = await page.evaluate(() => {
    const h=window.talkingHead;
    return {
    sampled: {...window.__tripoMotion,liveFrame:window.__tripoMotion.liveFrame?{weight:window.__tripoMotion.liveFrame.weight,speaking:window.__tripoMotion.liveFrame.speaking,elapsedMs:window.__tripoMotion.liveFrame.elapsedMs}:null},
    audioPayload:window.__tripoAudioPayload,
    audioContext:{state:h.audioCtx.state,currentTime:h.audioCtx.currentTime},
    currentVisemes:Object.fromEntries(['jawOpen','mouthOpen','viseme_aa','viseme_E','viseme_O','viseme_PP','viseme_FF'].map(n=>[n,h.mtAvatar[n]&&{value:h.mtAvatar[n].value,applied:h.mtAvatar[n].applied,realtime:h.mtAvatar[n].realtime,system:h.mtAvatar[n].system}])),
    isSpeaking: window.talkingHead.isSpeaking,
    mood: window.talkingHead.moodName,
    progress: document.querySelector('#progress').textContent,
    avatar: window.talkingHead.avatar.url
    };
  });
  await page.screenshot({ path: path.join(evidenceDir,'talking-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 412, height: 915 });
  await page.screenshot({ path: path.join(evidenceDir,'talking-mobile-viewport.png'), fullPage: true });
  const errors = [...errorCounts.entries()].map(([message, value]) => ({ message, ...value }));
  const result = { original, imported, direct, renderChecks,synthStatus, liveVisemeFrame:{weight:liveVisemeFrame.weight,captured:liveVisemeFrame.weight>0,speaking:liveVisemeFrame.speaking,elapsedMs:liveVisemeFrame.elapsedMs}, motion, mobile: await page.evaluate(() => ({ width: innerWidth, height: innerHeight, canvas: [document.querySelector('canvas').width, document.querySelector('canvas').height] })), errors };
  console.log(JSON.stringify(result, null, 2));
  if (synthStatus !== 200 || motion.sampled.mouth <= 0 || motion.sampled.blink <= 0 || motion.sampled.expression <= 0 || !liveVisemeFrame.weight || errors.length) {
    throw new Error(`Tripo speech/facial animation validation failed: ${JSON.stringify(result)}`);
  }
} finally {
  await browser.close();
}
