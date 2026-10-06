// OPS-01 / AUTH-02: real browser + synthetic API fixtures; never modifies live content.
const { chromium, expect } = require('@playwright/test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const http = require('node:http')
const root = path.resolve(__dirname, '../dist')
const output = path.resolve(__dirname, '../../runtime/single-publication-browser')
const mime = {
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.html': 'text/html',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
}
async function main() {
  fs.mkdirSync(output, { recursive: true })
  const server = http.createServer((req, res) => {
    let file = path.resolve(root, '.' + new URL(req.url, 'http://localhost').pathname)
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory())
      file = path.join(root, 'index.html')
    res.setHeader('Content-Type', mime[path.extname(file)] || 'application/octet-stream')
    fs.createReadStream(file).pipe(res)
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  let browser
  const checks = []
  try {
    browser = await chromium.launch({ channel: 'msedge', headless: true })
    for (const scenario of [
      { role: 'admin', status: 'draft' },
      { role: 'operator', status: 'reviewed' },
      { role: 'admin', status: 'published' },
      { role: 'operator', status: 'draft', fail: true },
      { role: 'merchant', status: 'draft' },
    ]) {
      const page = await browser.newPage({ viewport: { width: 1440, height: 960 } })
      const errors = []
      page.on('pageerror', (error) => errors.push(error.message))
      await page.addInitScript(() => sessionStorage.setItem('dongba_access_token', 'fixture-only-token'))
      const merchant = scenario.role === 'merchant'
      const endpoint = merchant ? '/merchant/products' : '/admin/characters'
      const row = {
        id: 'fixture-item',
        cn_name: '合成字典条目',
        name: '合成商品',
        status: scenario.status,
        culture_summary: '仅用于界面验证',
        source_ref: 'synthetic:browser',
        price: 1,
      }
      let writes = 0
      let reads = 0
      await page.route('**/api/v1/**', async (route) => {
        const url = new URL(route.request().url())
        const pathname = url.pathname.replace('/api/v1', '')
        let data
        let status = 200
        if (pathname === '/auth/me')
          data = { id: 'fixture-user', username: 'fixture', display_name: '合成账号', role: scenario.role }
        else if (pathname === endpoint) {
          reads++
          data = { items: [row], total: 1 }
        } else if (pathname === endpoint + '/fixture-item' && route.request().method() === 'PATCH') {
          writes++
          assert.deepEqual(route.request().postDataJSON(), { status: 'published' })
          if (scenario.fail) {
            status = 422
            data = {
              error: { code: 'REVIEW_INCOMPLETE', message: 'Source required', request_id: 'fixture-request' },
            }
          } else {
            row.status = 'published'
            data = row
          }
        } else data = { items: [], total: 0 }
        await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
      })
      await page.goto(`http://127.0.0.1:${server.address().port}${endpoint}`)
      await page.getByRole('button', { name: '更多操作', exact: true }).click()
      const publish = page.getByRole('menuitem', { name: '审核并发布', exact: true })
      await expect(page.getByRole('menuitem', { name: '审核通过', exact: true })).toHaveCount(0)
      await expect(page.getByRole('menuitem', { name: '发布', exact: true })).toHaveCount(0)
      if (merchant || scenario.status === 'published') {
        await expect(publish).toHaveCount(0)
        assert.equal(writes, 0)
      } else {
        await expect(publish).toBeVisible()
        await page.screenshot({
          path: path.join(
            output,
            `${scenario.role}-${scenario.status}${scenario.fail ? '-failure' : ''}.png`,
          ),
          fullPage: true,
        })
        await publish.click()
        if (scenario.fail) {
          await expect(page.locator('.el-message--error')).toBeVisible()
          assert.equal(row.status, 'draft')
        } else {
          await expect(page.locator('.el-table .el-tag').first()).toHaveText('已发布')
          assert.equal(writes, 1)
          assert.equal(reads, 2)
          await page.getByRole('button', { name: '更多操作', exact: true }).click()
          await expect(publish).toHaveCount(0)
        }
      }
      assert.deepEqual(errors, [])
      checks.push({ ...scenario, writes, reads, passed: true })
      await page.close()
    }
    fs.writeFileSync(
      path.join(output, 'result.json'),
      JSON.stringify({ fixture_only: true, checks }, null, 2),
    )
    console.log(JSON.stringify({ fixture_only: true, passed: checks.length, checks }))
  } finally {
    if (browser) await browser.close()
    await new Promise((resolve) => server.close(resolve))
  }
}
main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
