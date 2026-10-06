// DATA-03 / FEEDBACK-01: exercise real blob loading/layout, not recognition accuracy.
const { chromium } = require('@playwright/test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const http = require('node:http')
const root = path.resolve(__dirname, '../dist')
const output = path.resolve(__dirname, '../../runtime/feedback-drawer-browser')
const png = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAACAAAAAYCAIAAAAUMWhjAAAAM0lEQVR4nO3RwQ0AMAjDwJTJGb0jmE9+vgGCZF6yaZrqejxw4A+QiZCJkImQiZCJUD3RB24jALCu/Sv2AAAAAElFTkSuQmCC',
  'base64',
)
const mime = {
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.html': 'text/html',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
}
async function main() {
  fs.mkdirSync(output, { recursive: true })
  const server = http.createServer((req, res) => {
    let file = path.resolve(root, '.' + decodeURIComponent(new URL(req.url, 'http://localhost').pathname))
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory())
      file = path.join(root, 'index.html')
    res.setHeader('Content-Type', mime[path.extname(file)] || 'application/octet-stream')
    fs.createReadStream(file).pipe(res)
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  let browser
  try {
    browser = await chromium.launch({ channel: 'msedge', headless: true })
    const page = await browser.newPage({ viewport: { width: 1360, height: 1000 } })
    const errors = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.addInitScript(() => sessionStorage.setItem('dongba_access_token', 'fixture-only-token'))
    let mode = 'image'
    let imageRequests = 0
    let decision = 'pending'
    let ragCase = null
    let listRequests = 0
    let mutations = 0
    await page.route('**/api/v1/**', async (route) => {
      const url = new URL(route.request().url())
      const endpoint = url.pathname.replace('/api/v1', '')
      assert.equal(route.request().headers().authorization, 'Bearer fixture-only-token')
      const feedback = {
        id: 'fixture-feedback',
        recognition_id: 'fixture-recognition',
        status: decision,
        character_id: 'fixture-word',
        comment: '合成测试反馈：这个字应为房屋，请结合原图核验。',
        created_at: '2026-09-27T02:00:00Z',
        rag_status: ragCase?.status || 'not_indexed',
        rag_case: ragCase,
        rag_updated_at: ragCase?.updated_at,
        recognition: { observed_text: '合成识别文本', candidates: [] },
        sample: mode === 'missing' ? null : { id: 'fixture-sample', bbox: null },
      }
      if (endpoint === '/admin/samples/fixture-sample/image') {
        imageRequests++
        return route.fulfill(
          mode === 'denied'
            ? { status: 403, contentType: 'application/json', body: JSON.stringify({ code: 'FORBIDDEN' }) }
            : { status: 200, contentType: 'image/png', body: png },
        )
      }
      let data
      if (endpoint === '/auth/me')
        data = { id: 'fixture-admin', username: 'fixture', role: 'admin', display_name: 'Fixture operator' }
      else if (endpoint === '/admin/feedback') {
        listRequests++
        data = { items: [feedback], total: 1 }
      } else if (endpoint === '/admin/feedback/fixture-feedback' && route.request().method() === 'PATCH') {
        const payload = route.request().postDataJSON()
        assert.equal(payload.review_note, '')
        decision = payload.status
        mutations++
        if (decision === 'approved')
          ragCase = { id: 'fixture-case', status: 'indexed', updated_at: '2026-09-27T02:01:00Z' }
        data = { ...feedback, status: decision, rag_status: ragCase?.status || 'not_indexed' }
      } else if (endpoint === '/admin/feedback/fixture-feedback') data = feedback
      else if (endpoint === '/admin/characters')
        data = { items: [{ id: 'fixture-word', cn_name: '房屋' }], total: 1 }
      else if (endpoint.startsWith('/admin/rag/cases/fixture-case/')) {
        mutations++
        ragCase = {
          ...ragCase,
          status: endpoint.endsWith('/deprecate') ? 'deprecated' : 'indexed',
          updated_at: `2026-09-27T02:0${mutations}:00Z`,
        }
        data = ragCase
      } else throw new Error('Unexpected API request: ' + endpoint)
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) })
    })
    const address = `http://127.0.0.1:${server.address().port}/admin/feedback`
    async function open() {
      await page.goto(address)
      await page.getByRole('button', { name: '核验处理', exact: true }).click()
    }
    await open()
    const image = page.getByAltText('样本原图')
    await image.waitFor({ state: 'visible' })
    await page.waitForFunction(() => {
      const img = document.querySelector('.sample-image-frame img')
      return img && img.complete && img.naturalWidth === 32 && img.getBoundingClientRect().width > 100
    })
    const box = await image.boundingBox()
    assert.ok(box.width > 100 && box.height > 100)
    assert.match(await image.getAttribute('src'), /^blob:/)
    await page.waitForFunction(
      () =>
        ![...document.querySelectorAll('.feedback-drawer .el-loading-mask')].some(
          (el) => getComputedStyle(el).display !== 'none' && getComputedStyle(el).visibility !== 'hidden',
        ),
    )
    await page.screenshot({ path: path.join(output, 'visible.png'), fullPage: true })
    mode = 'missing'
    const requestsBeforeMissing = imageRequests
    await open()
    await page.getByText('未保存附图，原图无法恢复', { exact: true }).waitFor()
    assert.equal(await page.getByAltText('样本原图').count(), 0)
    assert.equal(imageRequests, requestsBeforeMissing)
    mode = 'denied'
    await open()
    await page.getByText('当前账号没有此操作权限', { exact: true }).waitFor()
    const beforeRetry = imageRequests
    mode = 'image'
    await page.getByRole('button', { name: '重新加载', exact: true }).click()
    await page.getByAltText('样本原图').waitFor({ state: 'visible' })
    assert.equal(imageRequests, beforeRetry + 1)
    const drawer = page.locator('.feedback-drawer')
    async function ready() {
      await page.waitForFunction(() => {
        const drawer = document.querySelector('.feedback-drawer')
        if (!drawer) return false
        const rect = drawer.getBoundingClientRect()
        return (
          Math.abs(rect.right - innerWidth) < 2 &&
          ![...drawer.querySelectorAll('.el-loading-mask')].some(
            (el) => getComputedStyle(el).display !== 'none' && getComputedStyle(el).visibility !== 'hidden',
          )
        )
      })
    }
    async function status(value) {
      await drawer.locator('.review-overview').filter({ hasText: value }).waitFor()
      await ready()
    }
    async function more(label) {
      await ready()
      await drawer.getByRole('button', { name: '更多操作', exact: true }).click()
      await page.getByRole('menuitem', { name: label, exact: true }).click()
    }
    async function close() {
      await drawer.locator('.el-drawer__close-btn').click()
      await drawer.waitFor({ state: 'hidden' })
    }
    async function width() {
      await ready()
      const geometry = await drawer.evaluate((el) => ({
        width: el.getBoundingClientRect().width,
        right: el.getBoundingClientRect().right,
        viewport: innerWidth,
        scroll: el.querySelector('.el-drawer__body').scrollWidth,
        client: el.querySelector('.el-drawer__body').clientWidth,
      }))
      assert.ok(Math.abs(geometry.width - Math.min(1120, geometry.viewport)) < 2, JSON.stringify(geometry))
      assert.ok(Math.abs(geometry.right - geometry.viewport) < 2, JSON.stringify(geometry))
      assert.ok(geometry.scroll <= geometry.client + 1, JSON.stringify(geometry))
    }
    await ready()
    assert.equal(await page.locator('.el-drawer').count(), 1)
    assert.equal(await drawer.locator('.el-drawer__close-btn').count(), 1)
    assert.equal(await page.getByRole('button', { name: '返回列表', exact: true }).count(), 0)
    assert.equal(await drawer.getByRole('button', { name: '关闭', exact: true }).count(), 0)
    assert.equal(await drawer.locator('.review-overview .el-tag').count(), 1)
    assert.equal(await drawer.locator('.request-meta').getAttribute('open'), null)
    assert.equal(await drawer.getByText('fixture-word', { exact: false }).count(), 0)
    await width()
    await page.setViewportSize({ width: 1920, height: 1080 })
    await width()
    await page.screenshot({ path: path.join(output, 'review-wide.png'), fullPage: true })
    await page.setViewportSize({ width: 1360, height: 1000 })
    await width()
    const evidenceBox = await drawer.locator('.evidence-column').boundingBox()
    const decisionBox = await drawer.locator('.decision-column').boundingBox()
    assert.ok(decisionBox.x >= evidenceBox.x + evidenceBox.width, 'desktop columns must not overlap')
    await drawer.getByRole('button', { name: '采纳并生效', exact: true }).click()
    await status('已采纳 · 已生效')
    const beforeMaintenance = listRequests
    await more('停用此纠错')
    const confirm = page.locator('.el-message-box')
    await confirm.getByRole('button', { name: '确认停用', exact: true }).click()
    await confirm.getByText('请填写停用原因', { exact: true }).waitFor()
    assert.equal(mutations, 1, 'blank disable reason must not mutate')
    await confirm.getByPlaceholder('请输入停用原因').fill('合成测试停用')
    await confirm.getByRole('button', { name: '确认停用', exact: true }).click()
    await status('已采纳 · 已停用')
    await page.locator('.el-table').getByText('已停用', { exact: true }).waitFor({ state: 'attached' })
    assert.ok(listRequests > beforeMaintenance)
    assert.equal(await drawer.locator('.review-footer').count(), 0)
    await page.screenshot({ path: path.join(output, 'maintenance-desktop.png'), fullPage: true })
    await more('重新启用')
    await status('已采纳 · 已生效')
    await more('更新识别参考')
    await drawer.locator('.request-meta summary').click()
    await drawer.locator('.request-meta .state-time').filter({ hasText: '10:04' }).waitFor()
    await close()
    await page.getByLabel('搜索纠错', { exact: true }).fill('房屋')
    await page.getByRole('button', { name: '查询', exact: true }).click()
    const trigger = page.getByRole('button', { name: '查看详情', exact: true })
    await trigger.click()
    await ready()
    await page.keyboard.press('Escape')
    await drawer.waitFor({ state: 'hidden' })
    assert.equal(await page.getByLabel('搜索纠错', { exact: true }).inputValue(), '房屋')
    assert.ok(await trigger.evaluate((el) => el === document.activeElement), 'restore opener focus')
    await page.screenshot({ path: path.join(output, 'list-desktop.png'), fullPage: true })
    decision = 'pending'
    ragCase = null
    mode = 'missing'
    await page.setViewportSize({ width: 390, height: 844 })
    await open()
    await drawer.getByText('未保存附图，原图无法恢复', { exact: true }).waitFor()
    await width()
    const mobileEvidence = await drawer.locator('.evidence-column').boundingBox()
    const mobileDecision = await drawer.locator('.decision-column').boundingBox()
    assert.ok(mobileDecision.y >= mobileEvidence.y + mobileEvidence.height, 'mobile columns must stack')
    assert.ok(mobileDecision.x >= 0 && mobileDecision.x + mobileDecision.width <= 390)
    const action = drawer.getByRole('button', { name: '驳回', exact: true })
    assert.ok(await action.isVisible())
    const footerBox = await drawer.locator('.review-footer').boundingBox()
    assert.ok(footerBox.y >= 0 && footerBox.y + footerBox.height <= 844, 'review actions stay in view')
    await page.screenshot({ path: path.join(output, 'review-mobile.png'), fullPage: true })
    await action.click()
    await status('已驳回')
    assert.equal(mutations, 5)
    assert.deepEqual(errors, [])
    console.log(
      JSON.stringify({
        checks: 28,
        passed: true,
        naturalSize: [32, 24],
        renderedSize: [box.width, box.height],
        syntheticData: true,
      }),
    )
  } finally {
    if (browser) await browser.close()
    await new Promise((resolve) => server.close(resolve))
  }
}
main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
