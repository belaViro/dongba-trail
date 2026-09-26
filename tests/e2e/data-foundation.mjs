// DATA-01/03/04, FEEDBACK-01, OPS-01/03 and PRIVACY-01.
// Isolated MySQL UI fixtures only; no real recognition/cultural accuracy claims.
import { createRequire } from 'node:module'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { randomBytes } from 'node:crypto'
import assert from 'node:assert/strict'

const require = createRequire(resolve('web/package.json'))
const { chromium, expect: baseExpect } = require('@playwright/test')
const expect = baseExpect.configure({ timeout: 15000 })
const base = 'http://127.0.0.1:5317'
const api = 'http://127.0.0.1:8011/api/v1'
const directory = resolve('runtime/e2e/data-foundation')
await mkdir(directory, { recursive: true })
const credentials = JSON.parse(await readFile('runtime/e2e/credentials.json', 'utf8'))
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE })
const context = await browser.newContext({ viewport: { width: 1440, height: 960 }, locale: 'zh-CN' })
const page = await context.newPage()
const checks = []
const errors = []
page.on('pageerror', error => errors.push(error.message))
const id = `DATA_${Date.now()}`
const original = `合成旧词条${id}`
let token
const pass = label => { checks.push(label); console.log(`PASS ${label}`) }
async function request(path, body, auth = token, method = body === undefined ? 'GET' : 'POST', status = 200) {
  const response = await fetch(`${api}${path}`, { method, headers: {
    ...(auth ? { Authorization: `Bearer ${auth}` } : {}),
    ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
  }, body: body === undefined ? undefined : JSON.stringify(body) })
  const data = await response.json()
  assert.equal(response.status, status, `${method} ${path}: ${data.code || ''}`)
  return data
}
async function loadedImages(locator, count) {
  await expect(locator).toHaveCount(count)
  for (let i = 0; i < count; i++) await expect.poll(() => locator.nth(i).evaluate(img => img.naturalWidth)).toBe(256)
}
async function shot(name) {
  await expect(page.locator('.el-loading-mask:visible')).toHaveCount(0)
  await page.screenshot({ path: resolve(directory, `${name}.png`), fullPage: true, animations: 'disabled' })
}
async function select(label, option, scope = page) {
  await scope.getByLabel(label, { exact: true }).click()
  await page.getByRole('option', { name: option, exact: true }).click()
}
try {
  await page.goto(`${base}/login`, { waitUntil: 'networkidle' })
  assert.ok((await page.title()).includes('东巴寻迹'))
  await page.getByLabel('登录账号', { exact: true }).fill(credentials.username)
  await page.getByLabel('密码', { exact: true }).fill(credentials.password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.waitForURL('**/admin/dashboard')
  token = await page.evaluate(() => sessionStorage.getItem('dongba_access_token'))
  assert.ok(token)

  // Clearly labelled synthetic images, generated entirely locally.
  const canvasPage = await context.newPage()
  await canvasPage.setContent('<canvas width="256" height="256"></canvas>')
  for (const [name, color] of [['old', '#176b63'], ['new', '#953c36']]) {
    const bytes = await canvasPage.evaluate(({ name, color }) => {
      const canvas = document.querySelector('canvas'), ctx = canvas.getContext('2d')
      ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, 256, 256)
      ctx.strokeStyle = color; ctx.lineWidth = 8; ctx.strokeRect(20, 20, 216, 216)
      ctx.fillStyle = color; ctx.font = 'bold 24px Arial'; ctx.fillText('TEST ONLY', 48, 110)
      ctx.fillText(name.toUpperCase(), 93, 150)
      return canvas.toDataURL('image/png').split(',')[1]
    }, { name, color })
    await writeFile(resolve(directory, `${name}.png`), Buffer.from(bytes, 'base64'))
  }
  await canvasPage.close()
  await page.goto(`${base}/admin/characters`, { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: '新增词条' }).click()
  let drawer = page.getByRole('dialog')
  await drawer.getByLabel('词条编号', { exact: true }).fill(id)
  await drawer.getByLabel('中文释义', { exact: true }).fill(original)
  await drawer.getByLabel('文化摘要', { exact: true }).fill('旧版本摘要，仅供合成验收')
  await drawer.getByLabel('文化故事', { exact: true }).fill('旧版本故事，不是真实东巴文化')
  await drawer.getByLabel('资料来源', { exact: true }).fill('synthetic:old-source')
  await drawer.locator('input[type=file]').first().setInputFiles(resolve(directory, 'old.png'))
  await loadedImages(drawer.locator('img'), 1)
  const oldImage = await drawer.getByPlaceholder('图片地址').inputValue()
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  const first = await request(`/admin/characters/${id}/revisions`)
  assert.equal(first.total, 1)
  assert.equal(first.items[0].snapshot.cn_name, original)
  // Add an old reviewed variant, then edit current content in the browser.
  await request(`/admin/characters/${id}`, { status: 'published', variants: [{ image_url: oldImage, source_ref: 'synthetic:old-variant' }] }, token, 'PATCH')
  await page.reload({ waitUntil: 'networkidle' })
  let row = page.getByRole('row').filter({ hasText: original })
  await row.getByRole('button', { name: '编辑', exact: true }).click()
  drawer = page.getByRole('dialog')
  await drawer.getByLabel('中文释义', { exact: true }).fill(`合成新词条${id}`)
  await drawer.getByLabel('文化摘要', { exact: true }).fill('新版本摘要')
  await drawer.getByLabel('文化故事', { exact: true }).fill('新版本故事')
  await drawer.getByLabel('资料来源', { exact: true }).fill('synthetic:new-source')
  await drawer.locator('input[type=file]').first().setInputFiles(resolve(directory, 'new.png'))
  await expect(drawer.getByPlaceholder('图片地址').first()).not.toHaveValue(oldImage)
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  row = page.getByRole('row').filter({ hasText: `合成新词条${id}` })
  await row.getByRole('button', { name: '更多操作' }).click()
  await page.getByRole('menuitem', { name: '历史版本', exact: true }).click()
  drawer = page.getByRole('dialog', { name: '词条历史版本' })
  await drawer.getByLabel('历史版本', { exact: true }).click()
  await page.getByRole('option', { name: /^版本 2 · 发布/ }).click()
  await expect(drawer).toContainText(original)
  await expect(drawer).toContainText('旧版本故事，不是真实东巴文化')
  await expect(drawer).toContainText('synthetic:old-source')
  await expect(drawer).toContainText('synthetic:old-variant')
  await loadedImages(drawer.locator('img'), 2)
  await shot('revision-desktop')
  await page.setViewportSize({ width: 390, height: 844 })
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await shot('revision-mobile')
  await page.setViewportSize({ width: 1440, height: 960 })
  pass('UI word edit preserves selectable old text, glyph, variant, source and reviewer; desktop/mobile images loaded')

  await page.goto(`${base}/admin/samples`, { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: '图片样本', exact: true })).toBeVisible()
  const uploaded = page.waitForResponse(r => r.url().endsWith('/admin/samples/upload') && r.request().method() === 'POST')
  await page.locator('input[type=file]').setInputFiles(resolve(directory, 'old.png'))
  const sample = await (await uploaded).json()
  assert.ok(sample.id)
  drawer = page.getByRole('dialog', { name: '样本预览与复核' })
  await loadedImages(drawer.getByAltText('样本原图'), 1)
  await drawer.getByLabel('关联词条（通过需已审核或已发布）', { exact: true }).click()
  await page.getByRole('option').filter({ hasText: `合成新词条${id}` }).click()
  await drawer.getByLabel('资料来源', { exact: true }).fill(`synthetic:${id}`)
  await drawer.getByLabel('数据集版本', { exact: true }).fill(id)
  await select('本次审核结果', '已通过', drawer)
  await drawer.getByRole('button', { name: '保存元数据与审核' }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByLabel('数据集版本筛选', { exact: true }).fill(id)
  await page.getByRole('button', { name: '查询', exact: true }).click()
  row = page.getByRole('row').filter({ hasText: sample.id })
  await expect(row).toContainText('已通过')
  await loadedImages(row.locator('img'), 1)
  await row.getByRole('button', { name: '预览 / 复核' }).click()
  drawer = page.getByRole('dialog', { name: '样本预览与复核' })
  await loadedImages(drawer.getByAltText('样本原图'), 1)
  await shot('sample-review-desktop')
  await page.setViewportSize({ width: 390, height: 844 })
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await shot('sample-review-mobile')
  await page.setViewportSize({ width: 1440, height: 960 })
  await drawer.getByRole('button', { name: '取消', exact: true }).click()
  await page.getByRole('button', { name: '筛选导出', exact: true }).click()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: '下载ZIP', exact: true }).click()
  await (await download).saveAs(resolve(directory, 'approved.zip'))
  pass('UI sample upload, authorized image preview, manual review, dataset filtering and ZIP download')
  await row.getByRole('button', { name: '删除', exact: true }).click()
  await page.getByRole('button', { name: '永久删除', exact: true }).click()
  await expect(row).toHaveCount(0)
  await request(`/admin/samples/${sample.id}/image`, undefined, token, 'GET', 404)
  pass('UI sample delete removes authenticated image endpoint')

  const username = `data_${Date.now()}`, password = randomBytes(24).toString('base64url')
  await request('/admin/users', { username, password, display_name: '合成留样游客', role: 'tourist' })
  const tourist = await request('/auth/login', { username, password }, null)
  const body = new FormData()
  body.append('image', new Blob([await readFile(resolve(directory, 'old.png'))], { type: 'image/png' }), 'synthetic.png')
  body.append('sample_consent', 'true'); body.append('sample_scene', 'paper')
  const failed = await fetch(`${api}/recognize`, { method: 'POST', headers: { Authorization: `Bearer ${tourist.access_token}` }, body })
  assert.equal(failed.status, 503)
  const failure = await failed.json()
  const own = await request('/me/samples', undefined, tourist.access_token)
  assert.equal(own.total, 1)
  await page.goto(`${base}/admin/recognitions?q=${failure.request_id}`, { waitUntil: 'networkidle' })
  const recognitionRow = page.getByRole('row').filter({ hasText: failure.request_id })
  await recognitionRow.getByRole('button', { name: '图片样本', exact: true }).click()
  await page.waitForURL('**/admin/samples?recognition_id=*')
  await loadedImages(page.getByRole('row').filter({ hasText: own.items[0].id }).locator('img'), 1)
  await shot('linked-sample')
  await request('/me/history', undefined, tourist.access_token, 'DELETE')
  await page.getByRole('button', { name: '刷新', exact: true }).click()
  await expect(page.getByRole('row').filter({ hasText: own.items[0].id })).toHaveCount(0)
  await request(`/me/samples/${own.items[0].id}/image`, undefined, tourist.access_token, 'GET', 404)
  pass('Unavailable provider remains unavailable; consented image linked from recognition; clearing history removes sample')
  assert.deepEqual(errors, [])
  pass('No browser runtime exceptions')
  await writeFile(resolve(directory, 'result.json'), JSON.stringify({ run: id, checks, browserErrors: errors }, null, 2))
} catch (error) {
  await page.screenshot({ path: resolve(directory, 'failure.png'), fullPage: true }).catch(() => {})
  throw error
} finally { await browser.close() }
