// DATA-01: real deployed UI, short-lived session received only through an SSH pipe.
import { createRequire } from 'node:module'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { createInterface } from 'node:readline'
import { spawn } from 'node:child_process'
import assert from 'node:assert/strict'

const require = createRequire(resolve('web/package.json'))
const { chromium, expect: baseExpect } = require('@playwright/test')
const expect = baseExpect.configure({ timeout: 15000 })
const base = 'http://127.0.0.1:18081'
const artifacts = resolve('runtime/sit-v1/browser')
await mkdir(artifacts, { recursive: true })
const ssh = spawn('ssh.exe', ['-T', '-L', '18081:127.0.0.1:8080',
  '-o', 'ExitOnForwardFailure=yes', '-o', 'StrictHostKeyChecking=yes',
  '-o', 'ConnectTimeout=15', '-o', 'PubkeyAuthentication=no',
  '-o', 'NumberOfPasswordPrompts=1', 'root@39.96.83.196',
  'cd /home/admin/dongba-trail && .venv/bin/python scripts/sit_browser_session.py --confirm-database dongba',
], { stdio: ['inherit', 'pipe', 'inherit'], windowsHide: true })
const input = createInterface({ input: ssh.stdout })
const session = await new Promise((resolve, reject) => {
  const timeout = setTimeout(() => { ssh.kill(); reject(new Error('Session pipe timed out')) }, 150000)
  input.once('line', line => {
    clearTimeout(timeout)
    try { resolve(JSON.parse(line)) } catch { reject(new Error('Invalid session pipe')) }
  })
})
input.close()
assert.ok(session.access_token && session.user?.role === 'admin', 'Expected scoped administrator session')
const checks = []
const errors = []
const browser = await chromium.launch({
  headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
})
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'zh-CN' })
const page = await context.newPage()
page.on('pageerror', error => errors.push(error.message))
await context.addInitScript(({ token, user }) => {
  sessionStorage.setItem('dongba_access_token', token)
  sessionStorage.setItem('dongba_user', JSON.stringify(user))
}, { token: session.access_token, user: session.user })
try {
  await page.goto(`${base}/admin/characters`, { waitUntil: 'networkidle' })
  assert.ok((await page.title()).includes('东巴寻迹'))
  await expect(page.getByRole('heading', { name: '东巴字典', exact: true })).toBeVisible()
  const search = page.getByPlaceholder(/搜索/).first()
  await search.fill('【SIT-DCT-')
  await search.press('Enter')
  await expect(page.getByText('【SIT-DCT-001】基础单字展示', { exact: true })).toBeVisible()
  await expect(page.locator('.el-loading-mask:visible')).toHaveCount(0)
  await expect.poll(async () => page.locator('.el-table__body img').evaluateAll(images =>
    images.length > 0 && images.every(image => image.complete && image.naturalWidth > 0)
  )).toBe(true)
  const names = await page.locator('.el-table__body').innerText()
  assert.ok(names.includes('SIT-DCT-012') && names.includes('SIT-DCT-001'))
  checks.push({ id: 'TC-UI-001', status: 'PASS', detail: 'Twelve standard dictionary names and loaded PNG thumbnails' })
  await page.screenshot({ path: resolve(artifacts, 'TC-UI-001-dictionary-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  const width = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }))
  assert.ok(width.document <= width.viewport + 1, 'Mobile document has horizontal overflow')
  await page.screenshot({ path: resolve(artifacts, 'TC-UI-002-dictionary-mobile.png'), fullPage: true })
  checks.push({ id: 'TC-UI-002', status: 'PASS', detail: '390px mobile document has no horizontal page overflow' })
  await page.setViewportSize({ width: 1440, height: 1000 })
  for (const [module, heading, marker, caseId] of [
    ['merchants', '商户管理', '【SIT-MCH-', 'TC-UI-003'],
    ['products', '商品管理', '【SIT-PRD-', 'TC-UI-004'],
    ['coupons', '优惠券', '【SIT-CPN-', 'TC-UI-005'],
  ]) {
    await page.goto(`${base}/admin/${module}`, { waitUntil: 'networkidle' })
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible()
    await page.getByPlaceholder(/搜索/).first().fill(marker)
    await page.getByPlaceholder(/搜索/).first().press('Enter')
    await expect(page.locator('.el-table__body').getByText(new RegExp(marker.replace(/[【]/g, '【') + '001'))).toBeVisible()
    await expect(page.locator('.el-loading-mask:visible')).toHaveCount(0)
    await page.screenshot({ path: resolve(artifacts, `${caseId}-${module}.png`), fullPage: true })
    checks.push({ id: caseId, status: 'PASS', detail: `${module}: standard test rows visible` })
  }
  assert.deepEqual(errors, [])
  checks.push({ id: 'TC-UI-006', status: 'PASS', detail: 'No browser JavaScript exceptions on inspected pages' })
} catch (error) {
  checks.push({ id: 'TC-UI-RUN', status: 'FAIL', detail: String(error.message).slice(0, 1200) })
  await page.screenshot({ path: resolve(artifacts, 'failure.png'), fullPage: true }).catch(() => {})
  process.exitCode = 1
} finally {
  await context.request.post(`${base}/api/v1/auth/logout`, {
    headers: { Authorization: `Bearer ${session.access_token}` },
  }).catch(() => {})
  await browser.close()
  await writeFile(resolve(artifacts, 'result.json'), JSON.stringify({ checks, errors }, null, 2))
  console.log(JSON.stringify({ checks }, null, 2))
}
