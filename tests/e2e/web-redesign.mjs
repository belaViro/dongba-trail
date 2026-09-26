/** FIXTURE-ONLY browser verification. Not real integration or recognition accuracy.
 * DESIGN-01 / AUTH-02 / MERCHANT-02 / DATA-01 / DATA-03 / COUPON-02 / OPS-02/03.
 * Run: node tests/e2e/web-redesign.mjs [--baseline]
 * No credentials read; all API requests are fulfilled locally, never forwarded.
 */
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { dirname, resolve, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const require = createRequire(resolve(root, 'web/package.json'))
const { chromium, expect } = require('@playwright/test')
const base = process.env.WEB_REDESIGN_URL || 'http://127.0.0.1:5320'
assert.ok(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(base).hostname), 'Local dev server only')
const baseline = process.argv.includes('--baseline')
const output = resolve(root, 'runtime/web-redesign', new Date().toISOString().replace(/[:.]/g, '-') + (baseline ? '-baseline' : ''))
await mkdir(output, { recursive: true })
const desktop = { width: 1672, height: 941 }
const mobile = { width: 390, height: 844 }
const timestamp = '2026-09-26T02:00:00Z'
/** @typedef {{items: Array<Record<string, unknown>>, total: number}} Collection */
/** @typedef {{date:string, recognitions:number, coupon_claims:number, redemptions:number}} Daily */
/** @type {Daily[]} */
const daily = Array.from({ length: 90 }, (_, i) => ({
  date: new Date(Date.UTC(2026, 6, 29 + i)).toISOString().slice(0, 10),
  recognitions: 18 + i % 13, coupon_claims: 8 + i % 7, redemptions: 3 + i % 5,
}))
const stats = {
  users: 1284, active_users_today: 76, recognitions: 2148, confirmed_recognitions: 1860,
  recognition_candidates: 2050, recognition_failures: 98, merchant_impressions: 3680,
  merchant_views: 1456, navigations: 624, coupon_claims: 980, redemptions: 450,
  quest_completions: 61, events: { poster_generate: 28, share: 35 }, daily,
  sources: [{ character_id: 'FIXTURE_MOUNTAIN', count: 480 }, { character_id: 'FIXTURE_WATER', count: 310 }],
}
const provider = { configured: true, name: 'synthetic-fixture', model: 'not-a-real-model',
  recent_requests: 42, recent_errors: 2, p95_latency_ms: 812, timeout_seconds: 20 }
const report = { label: 'FIXTURE-ONLY synthetic API browser verification', base, baseline,
  startedAt: new Date().toISOString(),
  limitations: ['Not real backend/MySQL/WeChat integration, server authorization, recognition accuracy or production readiness.',
    'No credentials read; all API requests intercepted. Synthetic content is not approved cultural content.',
    'Screenshots are review artifacts, not pixel-baseline comparison or human visual approval. Chromium only, not a physical phone.'],
  cases: [], screenshots: [], requests: [], unexpectedRequests: [], browserErrors: [], expectedHttpErrors: [],
}
let currentCase = ''
async function fingerprint() {
  const files = ['tests/e2e/web-redesign.mjs', 'web/package.json', 'docs/contracts/openapi.json']
  async function walk(dir) {
    for (const entry of await readdir(resolve(root, dir), { withFileTypes: true })) {
      if (entry.isDirectory()) await walk(`${dir}/${entry.name}`)
      else files.push(`${dir}/${entry.name}`)
    }
  }
  await walk('web/src')
  await walk('web/public')
  const hashes = {}
  for (const file of files.sort()) hashes[file] = createHash('sha256').update(await readFile(resolve(root, file))).digest('hex')
  return { sha256: createHash('sha256').update(JSON.stringify(hashes)).digest('hex'), files: hashes }
}
report.before = await fingerprint()
let browser
async function session(role, viewport = desktop, authenticated = true) {
  const context = await browser.newContext({ viewport, locale: 'zh-CN', timezoneId: 'Asia/Shanghai', reducedMotion: 'reduce', serviceWorkers: 'block' })
  const state = { context, role, mode: 'healthy', statsCalls: 0 }
  if (authenticated) await context.addInitScript(() => sessionStorage.setItem('dongba_access_token', 'fixture-only-dummy-token'))
  await context.route('**/*', async (route) => {
    const url = new URL(route.request().url())
    if (url.origin === new URL(base).origin || ['data:', 'blob:'].includes(url.protocol)) return route.continue()
    report.unexpectedRequests.push({ case: currentCase, url: url.href, reason: 'external blocked' })
    return route.abort('blockedbyclient')
  })
  // Offline SDK stand-in: layout/marker checks only; never asserts live AMap tiles or key validity.
  await context.route('https://webapi.amap.com/maps?**', (route) => route.fulfill({
    status: 200, contentType: 'application/javascript', body: `
      window.AMap = {
        Map: class {
          constructor(container) {
            this.container = container;
            const canvas = document.createElement('div');
            canvas.className = 'amap-fixture-canvas';
            canvas.style.cssText = 'width:100%;height:100%;background:#d7e7de';
            container.append(canvas);
          }
          on(event, fn) { if (event === 'complete') setTimeout(fn, 0) }
          add(pins) { for (const pin of pins) {
            const element = document.createElement('button');
            element.className = 'amap-fixture-marker';
            element.textContent = pin.title;
            element.style.cssText = 'position:absolute;left:50%;top:50%';
            element.onclick = pin.click;
            pin.element = element;
            this.container.append(element);
          } }
          remove(pins) { for (const pin of pins) pin.element?.remove() }
          setFitView() {}
          setCenter() {}
          destroy() { this.container.replaceChildren() }
        },
        Marker: class { constructor(options) { this.title = options.title; this.position = options.position } on(event, fn) { this.click = fn } },
        InfoWindow: class { open() {} },
      };
      window[new URL(document.currentScript.src).searchParams.get('callback')]();`,
  }))
  await context.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname.replace(/^\/api\/v1/, '')
    const method = route.request().method()
    report.requests.push({ case: currentCase, role, method, path, query: url.search, fixture: true })
    const json = (data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
    if (path === '/auth/me') return json({ id: `fixture-${role}`, username: `fixture_${role}`, display_name: `合成${role}账号`, role, merchant_id: role === 'merchant' ? 'fixture-merchant' : undefined })
    if (path.endsWith('/stats')) { state.statsCalls++; return json(stats) }
    if (path === '/admin/provider') return json(provider)
    if (path === '/map/pois') return json(state.mode === 'empty-map'
      ? { items: [], total: 0 }
      : { items: [{ id: 'fixture-poi', name: '合成文化点位', poi_type: 'culture', latitude: 26.875, longitude: 100.235, status: 'published' }], total: 1 })
    if (/^\/admin\/(characters|merchants|tag-claims|feedback|pois|activities)$/.test(path))
      return json({ items: [], total: 0 })
    if (path === '/merchant/profile')
      return json({
        id: 'fixture-merchant',
        name: '合成商户体验店',
        address: '丽江古城合成测试地址',
        business_hours: '09:00 - 22:00',
        description: '仅用于浏览器界面验收的合成商户资料。',
        tags: ['东巴文化', '文化体验'],
      })
    if (/^\/merchant\/(products|coupons|redemptions)$/.test(path))
      return json({ items: [], total: 0 })
    report.unexpectedRequests.push({ case: currentCase, method, path })
    return json({ message: `Unimplemented fixture: ${method} ${path}` }, 501)
  })
  const page = await context.newPage()
  state.page = page
  page.on('pageerror', (error) => report.browserErrors.push({ case: currentCase, kind: 'pageerror', message: error.message }))
  page.on('console', (message) => {
    if (message.type() !== 'error') return
    const entry = { case: currentCase, kind: 'console', message: message.text(), url: message.location().url }
    if (state.mode === 'error' && /503/.test(entry.message) && /\/api\/v1\/(admin|merchant)\/stats/.test(entry.url)) report.expectedHttpErrors.push(entry)
    else report.browserErrors.push(entry)
  })
  return state
}
async function settle(page) {
  await page.waitForLoadState('networkidle')
  await page.evaluate(() => document.fonts.ready)
  await expect(page.locator('.el-loading-mask:visible')).toHaveCount(0)
}
async function noOverflow(page) {
  const widths = await page.evaluate(() => ({
    viewport: innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
    offenders: [...document.querySelectorAll('*')]
      .map((element) => {
        const box = element.getBoundingClientRect()
        return { tag: element.tagName, className: element.className, left: box.left, right: box.right, width: box.width }
      })
      .filter((item) => item.right > innerWidth + 1 || item.left < -1)
      .sort((a, b) => b.right - a.right)
      .slice(0, 8),
  }))
  assert.ok(widths.document <= widths.viewport + 1 && widths.body <= widths.viewport + 1, `Horizontal body overflow: ${JSON.stringify(widths)}`)
}
async function shot(page, name) {
  await page.screenshot({ path: resolve(output, `${name}.png`), fullPage: true, animations: 'disabled' })
  report.screenshots.push(`${name}.png`)
}
async function visit(state, path) {
  await state.page.goto(`${base}${path}`, { waitUntil: 'networkidle' })
  await settle(state.page)
  await expect(state.page).toHaveURL(`${base}${path}`)
  await expect(state.page.locator('h1').first()).toBeVisible()
  await noOverflow(state.page)
}
async function check(name, state, action) {
  currentCase = name
  const errors = report.browserErrors.length
  const unexpected = report.unexpectedRequests.length
  try {
    await action()
    assert.equal(report.browserErrors.length, errors, 'Unexpected console/page error; see report')
    assert.equal(report.unexpectedRequests.length, unexpected, 'Unknown API/external request; see report')
    report.cases.push({ name, result: 'passed' })
    console.log(`PASS ${name}`)
  } catch (error) {
    report.cases.push({ name, result: 'failed', error: error.stack })
    console.error(`FAIL ${name}: ${error.message}`)
    if (state?.page) await shot(state.page, `failure-${name.replace(/[^a-z0-9-]/gi, '-')}`).catch(() => {})
  }
}
try {
  browser = await chromium.launch({
    headless: true,
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined,
  })
  report.browserVersion = browser.version()
  for (const role of ['admin', 'merchant']) {
    const state = await session(role)
    for (const [size, viewport] of Object.entries({ desktop, mobile })) {
      await state.page.setViewportSize(viewport)
      await check(`${role}-${size}-dashboard`, state, async () => {
        await visit(state, `/${role}/dashboard`)
        await expect(state.page.locator('.dashboard-metric')).toHaveCount(role === 'admin' ? 6 : 5)
        const seriesCount = role === 'admin' ? 3 : 2
        await expect(state.page.locator('.trend-panel .line-chart')).toHaveCount(0)
        await expect(state.page.locator('.trend-panel .bar-chart .chart-day')).toHaveCount(role === 'admin' ? 7 : 30)
        await expect(state.page.locator('.trend-panel .chart-bar')).toHaveCount((role === 'admin' ? 7 : 30) * seriesCount)
        if (role === 'admin') await expect(state.page.getByRole('button', { name: '近7天' })).toHaveClass(/active/)
        await state.page.getByRole('button', { name: '近7天' }).click()
        await expect(state.page.locator('.trend-panel .chart-day')).toHaveCount(7)
        await state.page.getByRole('button', { name: '近90天' }).click()
        await expect(state.page.locator('.trend-panel .chart-day')).toHaveCount(90)
        await state.page.getByRole('button', { name: '近30天' }).click()
        await expect(state.page.locator('.trend-panel .chart-day')).toHaveCount(30)
        if (role === 'admin') {
          await expect(state.page.locator('.poi-map .amap-fixture-marker')).toHaveCount(1)
          await expect(state.page.locator('.poi-map')).toContainText('仅展示后端已发布文化地图点位')
          const mapFill = await state.page.locator('.map-panel').evaluate((panel) => ({
            panel: panel.getBoundingClientRect(), map: panel.querySelector('.poi-map').getBoundingClientRect(),
          }))
          assert.ok(Math.abs(mapFill.map.bottom - mapFill.panel.bottom) <= 2, 'Map must fill card to its bottom edge')
          assert.ok(mapFill.map.height >= (size === 'desktop' ? 340 : 290), 'Map must have a usable viewport')
          assert.ok(report.requests.some((entry) => entry.path === '/map/pois'))
          assert.ok(!report.requests.some((entry) => entry.path === '/admin/merchants' && entry.query.includes('status=published')))
          if (size === 'desktop') {
            const columns = await state.page.locator('.dashboard-layout').evaluate((layout) => {
              const box = (selector) => layout.querySelector(selector).getBoundingClientRect()
              return { grid: layout.getBoundingClientRect(), provider: box('.provider-panel'), activities: box('.feature-panel') }
            })
            assert.ok(Math.abs(columns.activities.right - columns.grid.right) <= 2, 'Recent activities must fill the vacant right column')
            assert.ok(columns.activities.width > columns.provider.width * 0.9, 'Recent activities must occupy both right columns')
            assert.ok(Math.abs(columns.activities.top - columns.provider.top) <= 2, 'Activities must stay beside provider health')
          }
        }
        if (role === 'merchant') await expect(state.page.locator('.merchant-art-copy')).toHaveCount(0)
        if (size === 'desktop') {
          const layout = await state.page.locator('.sidebar').evaluate((sidebar) => {
            const nav = sidebar.querySelector('nav')?.getBoundingClientRect()
            const footer = sidebar.querySelector('.sidebar-footer')?.getBoundingClientRect()
            return { navBottom: nav?.bottom, footerTop: footer?.top }
          })
          assert.ok(layout.navBottom <= layout.footerTop + 1, `Sidebar navigation overlaps footer: ${JSON.stringify(layout)}`)
          const artwork = await state.page.locator('.sidebar').evaluate((sidebar) => getComputedStyle(sidebar, '::before').backgroundImage)
          assert.ok(!artwork.includes('lijiang-sidebar.png'), 'Baked-in menu text must not be used as sidebar artwork')
        }
        await shot(state.page, `${role}-${size}-dashboard`)
      })
    }
    if (role === 'admin') await check('admin-empty-map', state, async () => {
      state.mode = 'empty-map'
      await visit(state, '/admin/dashboard')
      await expect(state.page.locator('.poi-map')).toContainText('暂无已发布的文化地图坐标点位')
      await expect(state.page.locator('.poi-map .amap-fixture-marker')).toHaveCount(0)
      state.mode = 'healthy'
    })
    await state.context.close()
  }
} catch (error) {
  report.cases.push({ name: 'harness', result: 'failed', error: error.stack })
  console.error(error)
} finally {
  if (browser) await browser.close()
  report.after = await fingerprint()
  report.sourceStable = report.before.sha256 === report.after.sha256
  report.finishedAt = new Date().toISOString()
  report.summary = { passed: report.cases.filter((item) => item.result === 'passed').length,
    failed: report.cases.filter((item) => item.result === 'failed').length,
    unexpectedRequests: report.unexpectedRequests.length, browserErrors: report.browserErrors.length }
  report.result = report.summary.failed || report.summary.unexpectedRequests || report.summary.browserErrors || !report.sourceStable ? 'FAILED' : 'PASSED'
  await writeFile(resolve(output, 'report.json'), JSON.stringify(report, null, 2))
  await writeFile(resolve(output, 'README.md'), `# ${report.label}\n\nResult: **${report.result}**\n\nCommand: \`node tests/e2e/web-redesign.mjs${baseline ? ' --baseline' : ''}\`\n\nStarted: ${report.startedAt}\nFinished: ${report.finishedAt}\n\n${JSON.stringify(report.summary)}\n\nCode fingerprint: sha256:${report.before.sha256}\nSource stable: ${report.sourceStable}\n\n${report.limitations.map((text) => '- ' + text).join('\n')}\n\nSee report.json for case results, intercepted requests, HTTP error exceptions and per-file fingerprints.\n`)
  console.log(`${report.result}: ${JSON.stringify(report.summary)}\nEvidence: ${relative(root, output)}`)
  if (report.result !== 'PASSED') process.exitCode = 1
}
