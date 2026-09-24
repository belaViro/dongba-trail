import { createRequire } from 'node:module';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

const require = createRequire(resolve('web/package.json'));
const { chromium } = require('@playwright/test');
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  await page.goto(process.env.DONGBA_E2E_BASE_URL || 'http://127.0.0.1:5317', { waitUntil: 'networkidle' });
  if (!(await page.title()).includes('东巴寻迹')) throw new Error('Refusing to inspect an unrelated application');
  await mkdir('runtime/e2e', { recursive: true });
  await page.screenshot({ path: 'runtime/e2e/dongba-login.png', fullPage: true });
  console.log(await page.locator('body').innerText());
  console.log(JSON.stringify(await page.locator('input').evaluateAll(inputs => inputs.map(input => ({
    type: input.type, id: input.id, placeholder: input.placeholder,
  })))));
} finally {
  await browser.close();
}
