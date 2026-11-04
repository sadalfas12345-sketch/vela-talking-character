import { mkdir, readFile, writeFile, access } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const baseUrl = 'https://openapi.tripo3d.ai/v3';
const apiKey = process.env.TRIPO_API_KEY;
const inputPath = resolve(root, process.argv[2] || 'assets/tripo/vela-photoreal/reference-image.png');
const outputDir = resolve(root, process.argv[3] || 'assets/tripo/vela-photoreal');
const manifestPath = resolve(outputDir, 'generation.json');
const glbPath = resolve(outputDir, 'generated-original.glb');
const model = 'v3.1-20260211';
const request = {
  input: null,
  model,
  texture: true,
  pbr: true,
  texture_quality: 'detailed',
  geometry_quality: 'detailed',
  orientation: 'default',
};
// Official H3.1 pricing: image-to-3D with detailed textures 40 credits,
// plus 20 credits for detailed geometry. Tripo pricing may change; verify before each run.
const estimatedCredits = 60;

if (!apiKey) throw new Error('TRIPO_API_KEY is not set in this process environment.');
await mkdir(outputDir, { recursive: true });
try {
  await access(manifestPath);
  throw new Error(`Refusing a second paid generation: ${manifestPath} already exists.`);
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}
try {
  await access(glbPath);
  throw new Error(`Refusing to overwrite an existing generated GLB: ${glbPath}`);
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}

async function api(path, init = {}) {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: { ...(init.headers || {}), Authorization: `Bearer ${apiKey}` },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok || body?.code !== 0) {
    const detail = body?.message || body?.error?.message || response.statusText || 'Unknown Tripo API error';
    throw new Error(`Tripo API ${path} failed with HTTP ${response.status}: ${detail}`);
  }
  return body.data;
}

const balanceData = await api('/account/balance');
const balance = Number(balanceData.balance);
if (!Number.isFinite(balance)) throw new Error('Tripo balance response did not include a numeric available balance.');
console.log(`Available credits: ${balance}; frozen: ${balanceData.frozen}; estimated task cost: ${estimatedCredits}; estimated remainder: ${balance - estimatedCredits}.`);
if (balance < estimatedCredits) throw new Error('Insufficient credits for the documented H3.1 request estimate. No task was submitted.');

const image = await readFile(inputPath);
const form = new FormData();
form.append('file', new Blob([image], { type: 'image/png' }), 'vela-photoreal-reference.png');
const uploaded = await api('/files', { method: 'POST', body: form });
if (typeof uploaded.file_token !== 'string' || !uploaded.file_token) throw new Error('Tripo upload did not return a file_token. No generation task was submitted.');
request.input = uploaded.file_token;

// Exactly one paid create call. Never retry this POST automatically.
const created = await api('/generation/image-to-model', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(request),
});
if (typeof created.task_id !== 'string' || !created.task_id) throw new Error('Tripo generation response did not include a task_id.');

const manifest = {
  task_id: created.task_id,
  status: 'queued',
  created_at: new Date().toISOString(),
  model,
  input: 'reference-image.png',
  parameters: { ...request, input: '[uploaded file token omitted]' },
  estimated_credits: estimatedCredits,
  available_before_task: balance,
};
await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, { flag: 'wx' });
console.log(`Single generation task accepted. Task ID: ${created.task_id}`);

let completed = null;
for (let attempt = 0; attempt < 180; attempt++) {
  await new Promise(resolve => setTimeout(resolve, 5000));
  const task = await api(`/tasks/${encodeURIComponent(created.task_id)}`);
  manifest.status = task.status;
  manifest.progress = task.progress ?? null;
  manifest.last_polled_at = new Date().toISOString();
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`Task ${task.status}; progress ${task.progress ?? 0}%.`);
  if (task.status === 'success') { completed = task; break; }
  if (['failed', 'cancelled', 'banned', 'expired'].includes(task.status)) {
    manifest.error = task.error || task.message || null;
    await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
    throw new Error(`Tripo task ended with status ${task.status}. It will not be resubmitted automatically.`);
  }
}
if (!completed) throw new Error(`Polling timed out; task ${created.task_id} remains recorded and will not be resubmitted.`);

const modelUrl = completed.output?.model_url;
if (typeof modelUrl !== 'string' || !modelUrl) throw new Error('Successful Tripo response did not include output.model_url.');
const modelResponse = await fetch(modelUrl);
if (!modelResponse.ok) throw new Error(`GLB download failed with HTTP ${modelResponse.status}; rerun must resume the recorded task, not create a new task.`);
const bytes = Buffer.from(await modelResponse.arrayBuffer());
if (bytes.length < 12 || bytes.toString('ascii', 0, 4) !== 'glTF') throw new Error('Downloaded model is not a valid GLB binary.');
await writeFile(glbPath, bytes, { flag: 'wx' });
manifest.status = 'success';
manifest.progress = 100;
manifest.completed_at = completed.completed_at || new Date().toISOString();
manifest.downloaded_file = 'generated-original.glb';
manifest.download_bytes = bytes.length;
manifest.preview_available = Boolean(completed.output?.rendered_image_url);
await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`Saved original GLB: ${glbPath} (${bytes.length} bytes).`);
