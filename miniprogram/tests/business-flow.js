const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const origin = process.env.DONGBA_NATIVE_TEST_URL
assert.ok(origin && /^http:\/\/127\.0\.0\.1:\d+$/.test(origin), 'Isolated local test server required')
const config = require('../config')
config.apiBase = origin + '/api/v1'
const storage = new Map(), navigation = [], notices = [], downloads = new Map()
const app = { globalData: { recognition: null, recognitionImage: '', activeQuest: null } }
global.getApp = () => app
let modalTask = null
const png = fs.readFileSync(path.resolve(__dirname, '../assets/marker-culture.png'))
const requestApi = async (route, options = {}) => {
  const response = await fetch(origin + '/api/v1' + route, {
    method: options.method || 'GET',
    headers: Object.assign(options.data ? { 'Content-Type': 'application/json' } : {}, options.token ? { Authorization: 'Bearer ' + options.token } : {}),
    body: options.data ? JSON.stringify(options.data) : undefined
  })
  const data = await response.json()
  assert.ok(response.ok, route + ': ' + JSON.stringify(data))
  return data
}
global.wx = {
  getStorageSync(key) { return storage.get(key) },
  setStorageSync(key, value) { storage.set(key, value) },
  removeStorageSync(key) { storage.delete(key) },
  request(options) {
    fetch(options.url, { method: options.method, headers: options.header, body: options.data ? JSON.stringify(options.data) : undefined })
      .then(async response => options.success({ statusCode: response.status, data: await response.json() }))
      .catch(options.fail)
  },
  uploadFile(options) {
    const body = new FormData()
    body.append(options.name, new Blob([png], { type: 'image/png' }), 'test-only.png')
    body.append('scene', options.formData.scene)
    fetch(options.url, { method: 'POST', headers: options.header, body })
      .then(async response => options.success({ statusCode: response.status, data: await response.text() }))
      .catch(options.fail)
  },
  login(options) { options.success({ code: 'test-only-code-exchange' }) },
  requirePrivacyAuthorize(options) { options.success({}) },
  navigateTo(options) { navigation.push(options.url) },
  redirectTo(options) { navigation.push(options.url) },
  navigateBack() { navigation.push('back') },
  showToast(options) { notices.push(options.title) },
  showModal(options) { modalTask = Promise.resolve(options.success && options.success({ confirm: true })) },
  setClipboardData(options) { storage.set('clipboard', options.data) },
  scanCode(options) { options.success({ result: 'test-only-qr-token-123456' }) },
  getLocation(options) { options.success({ latitude: 26.87, longitude: 100.23 }) },
  openLocation(options) { storage.set('navigated-point', options); options.success({}) },
  showActionSheet(options) { options.success({ tapIndex: 0 }) },
  downloadFile(options) {
    fetch(options.url, { headers: options.header }).then(async response => {
      const file = 'test-memory://' + downloads.size + '.png'
      downloads.set(file, Buffer.from(await response.arrayBuffer()))
      options.success({ statusCode: response.status, tempFilePath: file })
    }).catch(options.fail)
  },
  saveImageToPhotosAlbum(options) { assert.ok(downloads.has(options.filePath)); options.success({}) },
  stopPullDownRefresh() {}
}
function loadPage(name) {
  const filename = path.resolve(__dirname, '../pages/' + name + '/index.js')
  let definition
  vm.runInNewContext(fs.readFileSync(filename, 'utf8'), {
    require(id) { return require(path.resolve(path.dirname(filename), id)) },
    Page(value) { definition = value },
    wx: global.wx, getApp: () => app, console, Set, Map
  }, { filename })
  definition.data = JSON.parse(JSON.stringify(definition.data))
  definition.setData = values => Object.assign(definition.data, values)
  return definition
}
const tap = id => ({ currentTarget: { dataset: { id } } })
async function main() {
  const setup = await requestApi('/auth/setup', { method: 'POST', data: { username: 'native_test_admin', password: 'test-only-password-789', display_name: 'Native test admin' } })
  const admin = setup.access_token
  const create = (kind, data) => requestApi('/admin/' + kind, { method: 'POST', token: admin, data: Object.assign({ status: 'published' }, data) })
  const form = new FormData(); form.append('file', new Blob([png], { type: 'image/png' }), 'test-only.png')
  const upload = await fetch(origin + '/api/v1/media', { method: 'POST', headers: { Authorization: 'Bearer ' + admin }, body: form }).then(value => value.json())
  await create('characters', { id: 'TEST_NATIVE', cn_name: '测试专用词条', culture_summary: '隔离测试内容，不用于实际文化解释', source_ref: 'test:isolated-native-flow', image_url: upload.url, category_l1: '测试' })
  const merchant = await create('merchants', { name: '隔离测试商户', latitude: 26.87, longitude: 100.23, character_ids: ['TEST_NATIVE'] })
  await create('products', { name: '测试文创', description: '隔离商品内容', price: 12.5, merchant_id: merchant.id, character_ids: ['TEST_NATIVE'] })
  const poi = await create('pois', { name: '隔离测试地点', latitude: 26.87, longitude: 100.23, poi_type: 'attraction' })
  const period = { start_at: new Date(Date.now() - 86400000).toISOString(), end_at: new Date(Date.now() + 86400000).toISOString() }
  await create('activities', Object.assign({ name: '测试体验活动', description: '隔离活动内容', capacity: 12, merchant_id: merchant.id }, period))
  const coupon = await create('coupons', Object.assign({ merchant_id: merchant.id, title: '测试券', rule: '隔离测试专用', stock: 20, per_user_limit: 2 }, period))
  const quest = await create('quests', Object.assign({ name: '隔离测试路线', reward_coupon_id: coupon.id }, period))
  const nodes = {}
  for (const [sequence, condition] of ['recognition','qr','geofence','coupon','manual'].entries()) {
    nodes[condition] = await create('quest-nodes', { name: '测试节点 ' + condition, quest_id: quest.id, sequence: sequence + 1, condition, character_id: condition === 'recognition' ? 'TEST_NATIVE' : null, merchant_id: ['qr','coupon'].includes(condition) ? merchant.id : null, poi_id: condition === 'geofence' ? poi.id : null, qr_token: condition === 'qr' ? 'test-only-qr-token-123456' : null })
  }
  const merchantUser = await requestApi('/admin/users', { method: 'POST', token: admin, data: { username: 'native_test_merchant', password: 'test-only-password-789', display_name: '测试商户账号', role: 'merchant', merchant_id: merchant.id } })
  assert.equal(merchantUser.merchant_id, merchant.id)

  const login = loadPage('login')
  await login.load(); login.data.accepted = true; await login.login()
  assert.equal(login.data.error, '')
  const session = require('../utils/session')
  assert.equal(session.get().user.role, 'tourist')
  const home = loadPage('home'); await home.load(); assert.equal(home.data.error, ''); assert.equal(home.data.today.id, 'TEST_NATIVE')
  const catalog = loadPage('catalog'); await catalog.load(); assert.equal(catalog.data.items.length, 1)
  const route = loadPage('quest'); route.onLoad({ id: quest.id }); await route.load(); await route.join()
  assert.ok(route.data.progress)

  const camera = loadPage('camera')
  camera.onLoad({ quest: quest.id, node: nodes.recognition.id })
  await camera.authorize(); assert.equal(camera.data.allowed, true)
  camera.data.image = '/isolated-test-image.png'
  await camera.recognize()
  assert.equal(camera.data.error, '')
  assert.equal(app.globalData.recognition.status, 'NEED_USER_CONFIRM')
  const result = loadPage('result'); await result.onLoad(); result.choose(tap('TEST_NATIVE'))
  await result.submit({ currentTarget: { dataset: {} } })
  assert.equal(result.data.error, '')
  assert.equal(app.globalData.activeQuest, null)
  const recognitionId = app.globalData.recognition.request_id
  const character = loadPage('character'); character.characterId = 'TEST_NATIVE'; character.recognitionId = recognitionId
  await character.load(); assert.equal(character.data.error, ''); assert.equal(character.data.merchants[0].id, merchant.id)
  await character.favorite(); assert.equal(character.data.saved, true)
  await character.correct()
  assert.equal(app.globalData.recognition.request_id, recognitionId)

  const shop = loadPage('merchant'); shop.merchantId = merchant.id; shop.recognitionId = recognitionId
  await shop.load(); assert.equal(shop.data.error, ''); await shop.claim(tap(coupon.id))
  assert.equal(shop.data.products.length, 1); assert.equal(shop.data.activities.length, 1)
  await shop.navigate(); assert.equal(storage.get('navigated-point').longitude, 100.23)
  const wallet = loadPage('coupons'); await wallet.load()
  assert.equal(wallet.data.items.length, 1)
  const claim = wallet.data.items[0]
  await wallet.code(tap(claim.id))
  assert.equal(wallet.data.qrError, '')
  assert.ok(wallet.data.qrImage)
  assert.ok(downloads.get(wallet.data.qrImage).length > 100)
  wallet.copyCode(); assert.equal(storage.get('clipboard'), claim.code)
  const seller = await requestApi('/auth/login', { method: 'POST', data: { username: 'native_test_merchant', password: 'test-only-password-789' } })
  const verified = await requestApi('/coupons/verify', { method: 'POST', token: seller.access_token, data: { code: claim.code } })
  assert.equal(verified.status, 'used')
  await wallet.load(); wallet.filter({ currentTarget: { dataset: { type: 'used' } } }); assert.equal(wallet.data.items.length, 1)
  await route.load()
  for (const type of ['qr','geofence','coupon']) await route.checkin(tap(nodes[type].id))
  await route.navigateNode(tap(nodes.geofence.id))
  assert.equal(storage.get('navigated-point').latitude, 26.87)
  await route.checkin(tap(nodes.manual.id)); await modalTask
  assert.equal(storage.get('clipboard'), session.get().user.id)
  await requestApi('/admin/quests/' + quest.id + '/complete-node', { method: 'POST', token: admin, data: { user_id: storage.get('clipboard'), node_id: nodes.manual.id } })
  await route.load()
  assert.equal(route.data.completed, 5)
  assert.equal(route.data.progress.status, 'completed')
  assert.ok(route.data.reward)
  const stamps = loadPage('stamps'); await stamps.load(); assert.equal(stamps.data.items.length, 5)
  const profile = loadPage('profile'); await profile.load(); assert.equal(profile.data.counts.stamps, 5)
  storage.delete('clipboard'); profile.copyUserId(); assert.equal(storage.get('clipboard'), session.get().user.id)

  const map = loadPage('map'); await map.load(); assert.equal(map.data.error, '')
  map.data.filter = 'quest'; map.filterPoints()
  assert.ok(map.data.visiblePoints.some(point => point.id === poi.id))
  const poster = loadPage('poster'); await poster.load(); poster.toggle(tap('TEST_NATIVE')); await poster.generate()
  assert.equal(poster.data.error, ''); assert.ok(poster.data.image); assert.equal(poster.data.shareCode, false)
  assert.ok(downloads.get(poster.data.image).length > 1000)
  await poster.save()
  assert.ok(poster.onShareAppMessage().path.includes('TEST_NATIVE'))

  const history = loadPage('history'); await history.load(); assert.equal(history.data.items.length, 1)
  history.clear(); await modalTask
  assert.equal(history.data.items.length, 0)
  const favorites = loadPage('favorites'); await favorites.load(); assert.equal(favorites.data.items.length, 1)
  assert.ok(navigation.some(url => url.includes('/pages/character/index?id=TEST_NATIVE')))
  console.log('PASS: native controllers -> real isolated HTTP API -> login/upload/confirm/correction/detail/recommendation/claim/authenticated QR/redeem/five quest methods/reward/map/poster/save/share/history deletion.')
  console.log('Fixtures only for WeChat code exchange, recognition provider and OS camera/location/share APIs; no real recognition accuracy, WeChat service or MySQL acceptance is claimed.')
}
main().catch(error => { console.error(error.stack); console.error('UI messages:', notices); process.exitCode = 1 })
