import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';

const baseUrl = process.env.VELA_URL || 'http://127.0.0.1:4174';
const outDir = 'verification';
await mkdir(outDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 412, height: 915 }, deviceScaleFactor: 1 });
try {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForFunction(() => !document.querySelector('#speak')?.disabled, null, { timeout: 90000 });
  const results = await page.evaluate(async () => {
    const THREE = await import('three');
    const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
    const head = window.talkingHead;
    const renderer = head.renderer;
    const loader = new GLTFLoader();
    const paths = [
      'assets/tripo/vela-photoreal/generated-rigged.glb',
      'assets/tripo/vela-photoreal/vela-photoreal-faced.glb'
    ];
    const records = [];
    for (const path of paths) {
      const gltf = await loader.loadAsync(`./${path}`);
      const scene = gltf.scene;
      scene.updateMatrixWorld(true);
      const box = new THREE.Box3().setFromObject(scene);
      const center = box.getCenter(new THREE.Vector3());
      const radius = Math.max(box.getBoundingSphere(new THREE.Sphere()).radius, 0.5);
      const camera = new THREE.PerspectiveCamera(30, 1, 0.01, 100);
      camera.position.copy(center).add(new THREE.Vector3(0, 0, radius * 3.2));
      camera.lookAt(center);
      camera.updateProjectionMatrix();
      const renderScene = new THREE.Scene();
      renderScene.background = new THREE.Color(0x111722);
      renderScene.add(scene);
      renderScene.add(new THREE.HemisphereLight(0xffffff, 0x596577, 2.0));
      const key = new THREE.DirectionalLight(0xffffff, 2.0);
      key.position.copy(center).add(new THREE.Vector3(1, 2, 3));
      renderScene.add(key);
      const target = new THREE.WebGLRenderTarget(256, 256, { depthBuffer: true, stencilBuffer: false });
      const gl = renderer.getContext();
      const pixels = () => {
        const data = new Uint8Array(256 * 256 * 4);
        renderer.readRenderTargetPixels(target, 0, 0, 256, 256, data);
        return data;
      };
      const meshes = [];
      scene.traverse(object => { if (object.isSkinnedMesh) meshes.push(object); });
      let vertexCount = 0, finiteDeformed = 0, neutralInfluences = 0, neutralNonzero = 0;
      for (const mesh of meshes) {
        mesh.skeleton.update();
        const point = new THREE.Vector3();
        for (const object of scene.children) { /* keep imported scene matrices current */ }
        const count = mesh.geometry.attributes.position.count;
        vertexCount += count;
        for (let i = 0; i < count; i++) {
          mesh.getVertexPosition(i, point);
          if (Number.isFinite(point.x) && Number.isFinite(point.y) && Number.isFinite(point.z)) finiteDeformed++;
        }
        for (const influence of mesh.morphTargetInfluences || []) {
          neutralInfluences++;
          if (!Number.isFinite(influence) || Math.abs(influence) > 1e-8) neutralNonzero++;
        }
      }
      renderer.setRenderTarget(target);
      renderer.render(renderScene, camera);
      const before = pixels();
      const boneName = bone => String(bone.name).toLowerCase().replace(/[^a-z0-9]/g, '');
      const bones = meshes.flatMap(mesh => mesh.skeleton.bones);
      const poseBone = bones.find(bone => boneName(bone).endsWith('hips'))
        || bones.find(bone => boneName(bone).endsWith('head'));
      if (!poseBone) throw new Error(`${path}: no controllable deformation bone found; names=${bones.map(b => b.name).slice(0,12).join(',')}`);
      const rest = poseBone.quaternion.clone();
      poseBone.quaternion.multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), 0.45));
      scene.updateMatrixWorld(true);
      for (const mesh of meshes) mesh.skeleton.update();
      renderer.render(renderScene, camera);
      const after = pixels();
      let changedPixels = 0;
      for (let i = 0; i < before.length; i += 4) {
        if (Math.abs(before[i] - after[i]) + Math.abs(before[i + 1] - after[i + 1]) + Math.abs(before[i + 2] - after[i + 2]) > 18) changedPixels++;
      }
      const canvas = document.createElement('canvas'); canvas.width = canvas.height = 256;
      const context = canvas.getContext('2d');
      const frame = context.createImageData(256, 256);
      for (let y = 0; y < 256; y++) frame.data.set(after.subarray((255 - y) * 256 * 4, (256 - y) * 256 * 4), y * 256 * 4);
      context.putImageData(frame, 0, 0);
      const image = canvas.toDataURL('image/png');
      poseBone.quaternion.copy(rest);
      scene.updateMatrixWorld(true);
      renderer.render(renderScene, camera);
      renderer.setRenderTarget(null);
      target.dispose();
      records.push({ path, skinnedMeshCount: meshes.length, skinDeformedVertices: vertexCount,
        skinDeformedFiniteVertices: finiteDeformed, skinningFiniteFraction: vertexCount ? finiteDeformed / vertexCount : null,
        deformationBone: poseBone.name, rendererChangedPixelsForPose: changedPixels,
        neutralMorphInfluences: neutralInfluences, neutralMorphNonzero: neutralNonzero,
        textureCount: new Set(meshes.flatMap(mesh => Array.isArray(mesh.material) ? mesh.material : [mesh.material]).flatMap(material =>
          ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap', 'emissiveMap'].map(key => material?.[key]?.uuid).filter(Boolean))).size,
        screenshot: image });
    }
    return records;
  });
  for (const record of results) {
    const bytes = Buffer.from(record.screenshot.split(',')[1], 'base64');
    const name = record.path.endsWith('generated-rigged.glb') ? 'tripo-gate1-rigged-render.png' : 'tripo-gate1-faced-render.png';
    await writeFile(`${outDir}/${name}`, bytes);
    delete record.screenshot;
    record.screenshot = `${outDir}/${name}`;
  }
  console.log(JSON.stringify({ gates: results }, null, 2));
  if (results.some(item => item.skinningFiniteFraction !== 1 || item.rendererChangedPixelsForPose <= 0 || item.neutralMorphNonzero)) {
    throw new Error(`Renderer skinning integrity failed: ${JSON.stringify(results)}`);
  }
} finally {
  await browser.close();
}
