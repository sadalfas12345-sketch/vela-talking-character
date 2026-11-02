import { chromium } from 'playwright';

const baseUrl = process.env.VELA_URL || 'http://127.0.0.1:4174';
const browser = await chromium.launch({ headless: true });
const errors = [];
const page = await browser.newPage({ viewport: { width: 412, height: 915 }, deviceScaleFactor: 1 });
page.on('pageerror', error => errors.push(error.message));
let synthStatus = null;
page.on('response', response => { if (response.url().includes('/v1/synthesize')) synthStatus = response.status(); });

async function ready() {
  await page.waitForFunction(() => !document.querySelector('#speak')?.disabled, null, { timeout: 90000 });
}
async function upload(file) {
  await page.locator('#characterFile').setInputFiles(file);
}

try {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await ready();
  const original = await page.evaluate(() => ({
    avatar: Boolean(window.talkingHead?.avatar),
    defaultUrl: window.talkingHead?.avatar?.url,
    morphs: Object.keys(window.talkingHead?.mtAvatar || {}).length,
    canvas: [document.querySelector('canvas').width, document.querySelector('canvas').height]
  }));
  if (!original.avatar) throw new Error('Default Vela avatar failed to load');

  const adapterTest = await page.evaluate(async () => {
    const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
    const { inspectCharacter, adaptCharacterGLTF } = await import('./character-adapter.mjs');
    const gltf = await new GLTFLoader().loadAsync('./TalkingHead/avatars/avatarsdk.glb');
    const mesh = { ...gltf.scene.children.find(object => object.morphTargetDictionary) };
    const keys = { ...mesh.morphTargetDictionary };
    const jawIndex = keys.jawOpen;
    delete keys.jawOpen;
    keys.ARKIT_Mouth_Open = jawIndex;
    mesh.morphTargetDictionary = keys;
    const fake = { scene: { traverse(fn) { gltf.scene.traverse(fn); fn(mesh); } } };
    const report = inspectCharacter(fake);
    adaptCharacterGLTF(fake, report);
    return { importable: report.importable, detectedJawAlias: mesh.morphTargetDictionary.jawOpen === jawIndex, mappedIndex: mesh.morphTargetDictionary.jawOpen, originalIndex:jawIndex };
  });
  if (!adapterTest.detectedJawAlias || !adapterTest.importable) throw new Error(`Morph alias mapping failed: ${JSON.stringify(adapterTest)}`);

  await upload('TalkingHead/avatars/avatarsdk.glb');
  await page.getByText('avatarsdk.glb:', { exact: false }).waitFor({ timeout: 30000 });
  const imported = await page.evaluate(() => ({
    selected: document.querySelector('#characterSelect').value,
    name: window.talkingHead?.avatar?.url,
    morphs: Object.keys(window.talkingHead?.mtAvatar || {}).length,
    report: document.querySelector('#compatibility')?.textContent
  }));
  if (imported.selected !== 'imported' || !imported.name?.startsWith('blob:')) throw new Error(`Compatible import did not activate: ${JSON.stringify(imported)}`);

  // Export a valid copy of the known compatible GLB with its facial morph deformation removed.
  const noFaceGlb = await page.evaluate(async () => {
    const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
    const { GLTFExporter } = await import('three/addons/exporters/GLTFExporter.js');
    const gltf = await new GLTFLoader().loadAsync('./TalkingHead/avatars/avatarsdk.glb');
    gltf.scene.traverse(object => {
      if (object.isMesh && object.morphTargetDictionary) {
        object.geometry.morphAttributes = {};
        delete object.morphTargetDictionary;
        delete object.morphTargetInfluences;
      }
    });
    const data = await new Promise((resolve, reject) => new GLTFExporter().parse(gltf.scene, resolve, reject, { binary: true }));
    let binary = ''; for (const byte of new Uint8Array(data)) binary += String.fromCharCode(byte);
    return btoa(binary);
  });
  await upload({ name:'no-facial-morphs.glb', mimeType:'model/gltf-binary', buffer:Buffer.from(noFaceGlb,'base64') });
  await page.getByText('no-facial-morphs.glb:', { exact: false }).waitFor({ timeout: 30000 });
  const missing = await page.locator('#compatibility').textContent();
  if (!missing.includes('Not activated') || !missing.includes('facial shape keys')) throw new Error(`Missing-face import was not diagnosed: ${missing}`);
  const activeAfterReject = await page.evaluate(() => window.talkingHead?.avatar?.url);
  if (activeAfterReject !== imported.name) throw new Error('Incompatible import silently replaced the active avatar');

  await upload({ name:'broken.glb', mimeType:'model/gltf-binary', buffer:Buffer.from('not a glb') });
  await page.getByText('Could not import broken.glb:', { exact:false }).waitFor({ timeout:30000 });
  if (await page.evaluate(() => window.talkingHead?.avatar?.url) !== imported.name) throw new Error('Malformed GLB changed the active avatar');

  await page.locator('#characterSelect').selectOption('default');
  await page.waitForFunction(()=>window.talkingHead?.avatar?.url?.includes('avaturn.glb'),null,{timeout:30000});
  const switchedDefault=await page.evaluate(()=>({selected:document.querySelector('#characterSelect').value,url:window.talkingHead.avatar.url}));
  if (switchedDefault.selected!=='default') throw new Error('Could not switch back to original Vela avatar');

  // Re-import the compatible model, speak through RTX HeadTTS and sample live mouth/blink/expression values.
  await page.locator('#characterSelect').selectOption('imported');
  await upload('TalkingHead/avatars/avatarsdk.glb');
  await page.getByText('avatarsdk.glb:', { exact: false }).waitFor({ timeout: 30000 });
  await ready();
  await page.evaluate(() => {
    const head=window.talkingHead; window.__faceMotion={mouth:0,blink:0,expression:0};
    const start=performance.now(); const sample=()=>{
      const p=window.__faceMotion; for(const key of ['viseme_aa','viseme_E','viseme_O','viseme_PP'])p.mouth=Math.max(p.mouth,head.mtAvatar[key]?.applied||0);
      for(const key of ['eyeBlinkLeft','eyeBlinkRight'])p.blink=Math.max(p.blink,head.mtAvatar[key]?.applied||0);
      for(const key of ['mouthSmileLeft','mouthSmileRight','browInnerUp'])p.expression=Math.max(p.expression,head.mtAvatar[key]?.applied||0);
      if(performance.now()-start<18000)requestAnimationFrame(sample);
    }; requestAnimationFrame(sample);
  });
  await page.locator('#emotion').selectOption('happy');
  await page.locator('#text').fill('The imported character is speaking with synchronized facial movement.');
  await page.locator('#speak').click();
  await page.waitForTimeout(18000);
  const speech=await page.evaluate(()=>({motion:window.__faceMotion,mood:window.talkingHead.moodName,progress:document.querySelector('#progress').textContent}));
  if (synthStatus !== 200 || speech.motion.mouth <= 0 || speech.motion.blink <= 0 || speech.motion.expression <= 0) throw new Error(`Speech/face motion check failed: ${JSON.stringify({synthStatus,speech})}`);

  await page.setViewportSize({ width: 1365, height: 900 });
  await page.screenshot({ path:'artifacts-character-import-desktop.png', fullPage:true });
  await page.setViewportSize({ width:412, height:915 });
  await page.screenshot({ path:'artifacts-character-import-mobile.png', fullPage:true });
  const mobile = await page.evaluate(() => ({ viewport:innerWidth,canvasWidth:document.querySelector('canvas').width,selected:document.querySelector('#characterSelect').value }));
  if (errors.length) throw new Error(`Browser errors: ${errors.join('; ')}`);
  console.log(JSON.stringify({ original, adapterTest, imported:{...imported,report:imported.report?.slice(0,260)}, missingMorphDiagnostic:missing, speech:{synthStatus,...speech}, mobile, errors },null,2));
} finally { await browser.close(); }
