// Test the media export primitive without running AI inference or loading a GLB.
// Start VELA's existing server first: npm run serve
// Then: npm run test:creator
import { chromium } from 'playwright';

const origin = process.env.VELA_URL || 'http://127.0.0.1:4174';
const browser = await chromium.launch({
  headless: true,
  args: ['--autoplay-policy=no-user-gesture-required']
});
try {
  const page = await browser.newPage({ acceptDownloads: true });
  page.on('dialog', dialog => dialog.dismiss());
  await page.goto(origin, { waitUntil: 'domcontentloaded' });
  const result = await page.evaluate(async () => {
    const { VelaCreatorRecorder } = await import('/creator-recorder.mjs');
    if (!VelaCreatorRecorder.isSupported()) {
      return { skipped: true, reason: 'MediaRecorder/captureStream unavailable in this browser' };
    }
    const source = document.createElement('canvas');
    source.width = 720;
    source.height = 1280;
    const ctx = source.getContext('2d');
    ctx.fillStyle = '#ed2546';
    ctx.fillRect(0, 0, source.width, source.height);
    const ac = new AudioContext();
    await ac.resume();
    const gain = ac.createGain();
    gain.gain.value = 0.05;
    const oscillator = ac.createOscillator();
    oscillator.frequency.value = 440;
    oscillator.connect(gain);
    gain.connect(ac.destination);
    oscillator.start();
    const recorder = new VelaCreatorRecorder({
      renderCanvas: source,
      audioContext: ac,
      audioOutputNode: gain
    });
    const recording = recorder.start();
    await new Promise(resolve => setTimeout(resolve, 1700));
    recorder.stop(true);
    const blob = await recording;
    oscillator.stop();
    await ac.close();
    return { skipped: false, bytes: blob.size, type: blob.type, width: 720, height: 1280 };
  });
  console.log(JSON.stringify(result, null, 2));
  if (!result.skipped && (result.bytes < 10000 || !result.type.startsWith('video/webm'))) {
    throw new Error('Creator media export did not produce a valid-sized WebM recording');
  }
  if (result.skipped) throw new Error(result.reason);
  console.log('OVERALL STEP RESULT: SUCCESS');
} catch (error) {
  console.error(error);
  console.error('OVERALL STEP RESULT: FAILED');
  process.exitCode = 1;
} finally {
  await browser.close();
}
