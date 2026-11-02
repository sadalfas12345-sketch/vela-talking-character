import { chromium } from 'playwright';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 412, height: 915 }, deviceScaleFactor: 1 });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
await page.goto('http://127.0.0.1:4174', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(12000);
const result = await page.evaluate(() => ({
  ready: !document.querySelector('#speak')?.disabled,
  status: document.querySelector('#statusText')?.textContent,
  panelWidth: Math.round(document.querySelector('.panel')?.getBoundingClientRect().width || 0),
  viewport: innerWidth
}));
await page.screenshot({ path: 'artifacts-mobile.png', fullPage: true });
console.log(JSON.stringify({ result, errors }, null, 2));
await browser.close();
