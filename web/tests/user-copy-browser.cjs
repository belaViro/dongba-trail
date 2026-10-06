// AUTH-02 / ANALYTICS-01 / OPS-03, D-053: synthetic browser fixtures, no live writes.
const { chromium, expect } = require('@playwright/test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const http = require('node:http')
const root = path.resolve(__dirname, '../dist')
const output = path.resolve(__dirname, '../../runtime/user-copy-browser')
const types = {
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.html': 'text/html',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
}
async function main() {
  fs.mkdirSync(output, { recursive: true })
  const server = http.createServer((req, res) => {
    let file = path.resolve(root, '.' + new URL(req.url, 'http://localhost').pathname)
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory())
      file = path.join(root, 'index.html')
    res.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream')
    fs.createReadStream(file).pipe(res)
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  let browser
  const checks = []
  try {
    browser = await chromium.launch({ channel: 'msedge', headless: true })
    for (const viewport of [
      { width: 1440, height: 960 },
      { width: 390, height: 844 },
    ]) {
      const page = await browser.newPage({ viewport })
      const errors = []
      page.on('pageerror', (error) => errors.push(error.message))
      let mode = 'login'
      await page.route('**/*', (route) =>
        new URL(route.request().url()).hostname === '127.0.0.1' ? route.continue() : route.abort(),
      )
      await page.route('**/api/v1/**', async (route) => {
        const endpoint = new URL(route.request().url()).pathname.replace('/api/v1', '')
        let data = { items: [], total: 0 },
          status = 200
        if (endpoint === '/auth/setup-status') data = { setup_required: false }
        else if (endpoint === '/auth/login') {
          status = 503
          data = {
            code: 'UNKNOWN_FAILURE',
            message: '数据库异常 /srv/private.py SQL password',
            detail: 'Traceback private configuration',
            request_id: 'copy-browser-request',
          }
        } else if (endpoint === '/auth/me')
          data = { id: 'fixture-user', username: 'fixture', display_name: '文案验证', role: 'admin' }
        else if (endpoint === '/public/map-config') data = { web_key: '' }
        else if (endpoint === '/admin/provider')
          data = { configured: false, recent_requests: 0, recent_errors: 0 }
        else if (endpoint === '/admin/stats') data = {}
        else if (mode !== 'dashboard') throw new Error('Unexpected fixture request: ' + endpoint)
        await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
      })
      const origin = `http://127.0.0.1:${server.address().port}`
      await page.goto(origin + '/login')
      await expect(page.getByRole('button', { name: '登录工作台', exact: true })).toBeVisible()
      await expect(page.locator('body')).not.toContainText('商户与运营人员使用已分配的账号登录')
      await page.getByPlaceholder('请输入登录账号').fill('fixture-user')
      await page.getByPlaceholder('请输入密码').fill('fixture-only-password')
      await page.getByRole('button', { name: '登录工作台', exact: true }).click()
      await expect(page.locator('.form-alert')).toContainText(
        '请求未完成，请稍后重试 · 请求编号 copy-browser-request',
      )
      assert.doesNotMatch(
        await page.locator('body').innerText(),
        /数据库异常|private\.py|Traceback|SQL password/,
      )
      await page.screenshot({ path: path.join(output, `login-${viewport.width}.png`), fullPage: true })
      checks.push(`login-${viewport.width}-no-role-explanation-safe-error`)
      if (viewport.width > 1000) {
        mode = 'dashboard'
        await page.evaluate(() => sessionStorage.setItem('dongba_access_token', 'fixture-only-token'))
        await page.goto(origin + '/admin/dashboard')
        await expect(page.getByText('请求成功率反映服务响应情况，不代表识别准确率。')).toBeVisible()
        await expect(page.getByText('地图暂不可用，请稍后重试或联系管理员。')).toBeVisible()
        const text = await page.locator('body').innerText()
        assert.doesNotMatch(text, /参考图|后端|现有接口|Web Key|真实评测集|模型能力/)
        assert.match(text, /演示点位不代表实地核验/)
        await page.screenshot({ path: path.join(output, 'dashboard-1440.png'), fullPage: true })
        checks.push('dashboard-product-guidance-with-truthful-unavailable-state')
      }
      assert.deepEqual(errors, [])
      await page.close()
    }
    fs.writeFileSync(path.join(output, 'checks.json'), JSON.stringify(checks, null, 2))
    console.log(JSON.stringify({ checks: checks.length, passed: checks, fixture: true }))
  } finally {
    if (browser) await browser.close()
    await new Promise((resolve) => server.close(resolve))
  }
}
main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
