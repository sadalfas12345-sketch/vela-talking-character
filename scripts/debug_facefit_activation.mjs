import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
page.on('console', message => { if (message.type() === 'error') console.log('console.error:', message.text()); });
page.on('pageerror', error => console.log('pageerror:', error.stack));
try {
  await page.goto('http://127.0.0.1:4174', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !document.querySelector('#speak')?.disabled, null, { timeout: 90000 });
  await page.locator('#characterFile').setInputFiles('assets/tripo/vela-photoreal/vela-photoreal-facefit-prototype.glb');
  await page.waitForFunction(() => document.querySelector('#compatibility')?.textContent.includes('inspected, but activation failed'), null, { timeout: 90000 });
  console.log(await page.locator('#compatibility').textContent());
} finally { await browser.close(); }
