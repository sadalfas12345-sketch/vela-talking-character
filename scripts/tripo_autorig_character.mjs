import { mkdir, readFile, writeFile, access } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const dir = resolve(root, 'assets/tripo/vela-photoreal');
const generation = JSON.parse(await readFile(resolve(dir, 'generation.json'), 'utf8'));
const rigCheck = JSON.parse(await readFile(resolve(dir, 'rig-check.json'), 'utf8'));
const outputPath = resolve(dir, 'generated-rigged.glb');
const manifestPath = resolve(dir, 'rigging.json');
const apiKey = process.env.TRIPO_API_KEY;
const base = 'https://openapi.tripo3d.ai/v3';
const estimatedCredits = 25;

if (!apiKey) throw new Error('TRIPO_API_KEY is not set in this process environment.');
if (generation.status !== 'success' || !generation.task_id) throw new Error('The original Tripo generation is not complete.');
if (!rigCheck.riggable || rigCheck.rig_type !== 'biped') throw new Error('The free rig check did not approve a biped. No rig task was submitted.');
await mkdir(dir, { recursive: true });
for (const path of [manifestPath, outputPath]) {
  try { await access(path); throw new Error(`Refusing a duplicate rig task or overwrite: ${path}`); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
}

async function api(path, init = {}) {
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: { ...(init.headers || {}), Authorization: `Bearer ${apiKey}` },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok || body?.code !== 0) {
    throw new Error(`Tripo API ${path} failed with HTTP ${response.status}: ${body?.message || response.statusText || 'unknown error'}`);
  }
  return body.data;
}

const balanceData = await api('/account/balance');
const balance = Number(balanceData.balance);
if (!Number.isFinite(balance) || balance < estimatedCredits) throw new Error(`Insufficient balance for the documented ${estimatedCredits}-credit auto-rig task. No task was submitted.`);
console.log(`Available credits: ${balance}; frozen: ${balanceData.frozen}; auto-rig estimate: ${estimatedCredits}; estimated remainder: ${balance - estimatedCredits}.`);

const created = await api('/animations/rig', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ input: generation.task_id, model: 'v3.0-20260909', rig_type: 'biped', spec: 'mixamo', out_format: 'glb' }),
});
if (!created.task_id) throw new Error('Tripo auto-rig response did not include a task ID.');
const manifest = {
  task_id: created.task_id,
  status: 'queued',
  created_at: new Date().toISOString(),
  source_generation_task: generation.task_id,
  rig_check: rigCheck,
  parameters: { model: 'v3.0-20260909', rig_type: 'biped', spec: 'mixamo', out_format: 'glb' },
  estimated_credits: estimatedCredits,
  available_before_task: balance,
};
await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, { flag: 'wx' });
console.log(`Single auto-rig task accepted. Task ID: ${created.task_id}`);

let completed;
for (let attempt = 0; attempt < 180; attempt++) {
  await new Promise(resolve => setTimeout(resolve, 5000));
  const task = await api(`/tasks/${encodeURIComponent(created.task_id)}`);
  manifest.status = task.status;
  manifest.progress = task.progress ?? null;
  manifest.last_polled_at = new Date().toISOString();
  if (task.credits_consumed != null) manifest.credits_consumed = task.credits_consumed;
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`Auto-rig task ${task.status}; progress ${task.progress ?? 0}%.`);
  if (task.status === 'success') { completed = task; break; }
  if (['failed', 'cancelled', 'banned', 'expired'].includes(task.status)) {
    manifest.error = task.error || task.message || null;
    await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
    throw new Error(`Tripo auto-rig ended with ${task.status}; it will not be resubmitted automatically.`);
  }
}
if (!completed) throw new Error(`Auto-rig polling timed out; ${created.task_id} remains recorded and will not be resubmitted.`);
const modelUrl = completed.output?.model_url;
if (!modelUrl) throw new Error('Successful auto-rig task did not include output.model_url.');
const response = await fetch(modelUrl);
if (!response.ok) throw new Error(`Rigged GLB download failed with HTTP ${response.status}; the task will not be resubmitted.`);
const bytes = Buffer.from(await response.arrayBuffer());
if (bytes.length < 12 || bytes.toString('ascii', 0, 4) !== 'glTF') throw new Error('Downloaded auto-rig asset is not a valid GLB.');
await writeFile(outputPath, bytes, { flag: 'wx' });
manifest.status = 'success';
manifest.progress = 100;
manifest.completed_at = completed.completed_at || new Date().toISOString();
manifest.downloaded_file = 'generated-rigged.glb';
manifest.download_bytes = bytes.length;
manifest.credits_consumed = completed.credits_consumed ?? estimatedCredits;
await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`Saved rigged GLB: ${outputPath} (${bytes.length} bytes; ${manifest.credits_consumed} credits).`);
