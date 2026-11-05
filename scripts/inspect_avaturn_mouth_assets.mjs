import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
try {
  await page.goto(process.env.VELA_URL || 'http://127.0.0.1:4174', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !document.querySelector('#speak')?.disabled, null, { timeout: 90000 });
  const data = await page.evaluate(async () => {
    const THREE = await import('three');
    const h = window.talkingHead;
    const list = [];
    h.scene.traverse(o => {
      if (!o.isMesh) return;
      o.geometry.computeBoundingBox();
      const b = o.geometry.boundingBox;
      const world = new THREE.Box3().setFromObject(o);
      list.push({
        name: o.name, type: o.type, parent: o.parent?.name, skinned: o.isSkinnedMesh,
        vertices: o.geometry.attributes.position?.count, triangles: o.geometry.index?.count / 3,
        localBounds: { min: b.min.toArray(), max: b.max.toArray() },
        worldBounds: { min: world.min.toArray(), max: world.max.toArray() },
        morphs: Object.keys(o.morphTargetDictionary || {}),
        materials: (Array.isArray(o.material) ? o.material : [o.material]).map(m => ({ name:m?.name, type:m?.type, color:m?.color?.getHexString(), side:m?.side, transparent:m?.transparent }))
      });
    });
    return { avatar: h.avatar?.url, meshes:list };
  });
  console.log(JSON.stringify({ avatar:data.avatar, meshNames:data.meshes.map(o=>o.name), dental:data.meshes.filter(o=>/teeth|tongue/i.test(o.name)) }, null, 2));
} finally { await browser.close(); }
