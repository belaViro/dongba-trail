// COUPON-01 / D-079: merchant coupon claim state is durable in the page and restored from the wallet.
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

const root = path.resolve(__dirname, '../pages/merchant')
const source = fs.readFileSync(path.join(root, 'index.js'), 'utf8')
const markup = fs.readFileSync(path.join(root, 'index.wxml'), 'utf8')

function harness({ loggedIn = true, claims = [], claimError = null } = {}) {
  let page
  const calls = [], toasts = [], errors = []
  const coupons = [{ id: 'coupon/1', title: '体验券', rule: '到店使用', end_at: '2026-12-31T00:00:00+00:00' }]
  const api = {
    async request(url, options) {
      calls.push({ url, options })
      if (url.includes('/claim')) {
        if (claimError) throw claimError
        return { id: 'claim-1', coupon_id: 'coupon/1' }
      }
      return { id: 'merchant/1', name: '测试商户', tags: [] }
    },
    async collection(url, params, auth) {
      calls.push({ url, params, auth })
      if (url === '/coupons') return coupons
      if (url === '/me/coupons') return claims
      return []
    },
    mediaUrl: value => value || '',
    track() {},
    showError: error => errors.push(error.message)
  }
  const services = {
    api,
    helpers: { date: value => value.slice(0, 10), query: values => values.recognition_id ? '?recognition_id=' + encodeURIComponent(values.recognition_id) : '' },
    platform: {},
    session: { get: () => loggedIn ? { user: { id: 'tourist' } } : null, requireLogin: () => loggedIn }
  }
  vm.runInNewContext(source, {
    Page: value => { page = value },
    require: name => services[name.split('/').pop()],
    wx: { showToast: value => toasts.push(value), navigateTo() {}, stopPullDownRefresh() {} },
    Promise,
    Set
  })
  page.data = { ...page.data }
  page.setData = values => Object.assign(page.data, values)
  page.merchantId = 'merchant/1'
  page.recognitionId = 'recognition/1'
  return { page, calls, toasts, errors }
}

test('logged-in merchant detail restores already-claimed coupons from the wallet', async () => {
  const { page, calls } = harness({ claims: [{ id: 'claim-1', coupon_id: 'coupon/1', status: 'available' }] })
  await page.load()
  assert.equal(page.data.coupons[0].claimed, true)
  assert.equal(calls.filter(call => call.url === '/me/coupons').length, 1)
})

test('a successful claim immediately changes the button state and blocks repeat requests', async () => {
  const { page, calls, toasts } = harness()
  await page.load()
  const event = { currentTarget: { dataset: { id: 'coupon/1' } } }
  await page.claim(event)
  await page.claim(event)
  assert.equal(page.data.coupons[0].claimed, true)
  assert.equal(calls.filter(call => call.url.includes('/claim')).length, 1)
  assert.equal(toasts.length, 1)
  assert.equal(toasts[0].title, '领取成功')
  assert.equal(toasts[0].icon, 'success')
})

test('claim-limit response recovers stale UI to the claimed state', async () => {
  const error = Object.assign(new Error('已达到优惠券领取上限'), { code: 'CLAIM_LIMIT' })
  const { page, errors } = harness({ claimError: error })
  await page.load()
  await page.claim({ currentTarget: { dataset: { id: 'coupon/1' } } })
  assert.equal(page.data.coupons[0].claimed, true)
  assert.deepEqual(errors, ['已达到优惠券领取上限'])
})

test('coupon button renders claimed copy and remains disabled after receipt', () => {
  assert.match(markup, /disabled="{{item\.claimed \|\| !!claiming}}"/)
  assert.match(markup, /{{item\.claimed \? '已领取' : '领取'}}/)
})
