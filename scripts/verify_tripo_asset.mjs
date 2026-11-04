import { chromium } from 'playwright';

const baseUrl = process.env.VELA_URL || 'http://127.0.0.1:4174';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 412, height: 915 }, deviceScaleFactor: 1 });
const errors = [];
page.on('pageerror', error => errors.push(error.message));

try {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !document.querySelector('#speak')?.disabled, null, { timeout: 90000 });
  const defaultAvatar = await page.evaluate(() => window.talkingHead?.avatar?.url);
  if (!defaultAvatar?.includes('avaturn.glb')) throw new Error(`Unexpected initial avatar: ${defaultAvatar}`);

  const results = [];
  for (const name of ['generated-original.glb', 'generated-rigged.glb']) {
    await page.locator('#characterFile').setInputFiles(`assets/tripo/vela-photoreal/${name}`);
    await page.getByText(`${name}:`, { exact: false }).waitFor({ timeout: 60000 });
    const compatibility = await page.locator('#compatibility').textContent();
    const currentAvatar = await page.evaluate(() => window.talkingHead?.avatar?.url);
    if (!compatibility.includes('Not activated') || !compatibility.includes('No facial morph targets')) {
      throw new Error(`${name} was not accurately rejected for missing facial morphs: ${compatibility}`);
    }
    if (currentAvatar !== defaultAvatar) throw new Error(`${name} replaced the active avatar despite missing facial morphs`);
    results.push({ file: name, compatibility, activeAvatar: currentAvatar });
  }

  await page.screenshot({ path: 'assets/tripo/vela-photoreal/verification/tripo-import-diagnostic.png', fullPage: true });
  if (errors.length) throw new Error(`Browser errors: ${errors.join('; ')}`);
  console.log(JSON.stringify({ defaultAvatar, results, mobileViewport: await page.evaluate(() => [innerWidth, innerHeight]), errors }, null, 2));
} finally {
  await browser.close();
}
