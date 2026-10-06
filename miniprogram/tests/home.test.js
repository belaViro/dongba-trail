// MINI-01 / DESIGN-01 / GEO-01: fixture behavior, never real location/AI evidence.
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const helpers = require('../utils/helpers')
const root = path.resolve(__dirname, '..')
const markup = fs.readFileSync(path.join(root, 'pages/home/index.wxml'), 'utf8')
test('shipped homepage background is a JPEG below the 200 KB resource budget', () => {
  const image = fs.readFileSync(path.join(root, 'assets/home/landscape.jpg'))
  assert.equal(image.subarray(0, 3).toString('hex'), 'ffd8ff')
  assert.ok(image.length > 0 && image.length < 200000, `Background is ${image.length} bytes`)
  assert.match(markup, /\/assets\/home\/landscape\.jpg/)
  const config = JSON.parse(fs.readFileSync(path.join(root, 'project.config.json'), 'utf8'))
  assert.ok(config.packOptions.ignore.some(item => item.value === 'assets/lijiang-home-background.png'), 'Original source must not ship in the package')
})
test('today layout does not inherit native v2 button sizing and retains the detail action', () => {
  assert.match(markup, /<view\b[^>]*class="today"[^>]*bindtap="character"[^>]*aria-role="button"/)
  assert.doesNotMatch(markup, /<button\b[^>]*class="today"/)
  assert.match(markup, /<button\b[^>]*class="daily-detail"[^>]*bindtap="character"/)
  assert.match(markup, /class="daily-glyph-frame"/)
})
const homeSource = fs.readFileSync(path.join(root, 'pages/home/index.js'), 'utf8')
test('today detail opts out of the wide default native button while retaining its action', () => {
  assert.match(markup, /<button\b[^>]*class="daily-detail"[^>]*size="mini"[^>]*bindtap="character"/)
})
test('more action retains its native button and bounded mini sizing', () => {
  assert.match(markup, /<button\b[^>]*class="more-button"[^>]*size="mini"[^>]*bindtap="more"/)
})
const tick = () => new Promise(resolve => setImmediate(resolve))
function setup(options = {}) {
  let home, locationCalls = 0
  const calls = [], routes = []
  const characters = options.characters || [{ id: 'C1', cn_name: '布局夹具', category_l1: '示例', image_url: '/glyph.png', culture_summary: '仅用于布局测试' }]
  const merchants = options.merchants || [{ id: 'M1', name: '布局商户', image_url: '/shop.png', tags: ['甲', '乙', '丙', '丁'], latitude: 26.87, longitude: 100.23 }]
  const api = {
    async collection(url, params) { calls.push({ method: 'collection', url, params }); return url === '/characters' ? characters : merchants },
    async all(url, params) { calls.push({ method: 'all', url, params }); return merchants },
    mediaUrl(value) { return value ? 'https://fixture.invalid' + value : '' },
    track(event, payload) { calls.push({ event, payload }) }
  }
  const platform = { async locate() { locationCalls++; if (options.locationError) throw new Error(options.locationError); return options.location || { latitude: 26.87, longitude: 100.23 } } }
  const wx = {
    getMenuButtonBoundingClientRect: () => ({ top: 48, left: 280, height: 32 }),
    getWindowInfo: () => ({ statusBarHeight: 44, windowWidth: 375 }),
    getSetting: ({ success }) => success({ authSetting: { 'scope.userLocation': !!options.authorized } }),
    navigateTo: value => routes.push(value.url), switchTab: value => routes.push(value.url), stopPullDownRefresh() {}
  }
  vm.runInNewContext(homeSource, { Page(value) { home = value }, require(id) { return ({ '../../utils/api': api, '../../utils/helpers': helpers, '../../utils/platform': platform, '../../utils/recognition': { chooseCamera: () => 'native-camera' } })[id] }, wx })
  home.data = JSON.parse(JSON.stringify(home.data))
  home.setData = values => Object.assign(home.data, values)
  return { home, api, wx, calls, routes, locationCalls: () => locationCalls }
}
test('home content uses API data, real date and no unsolicited location prompt', async () => {
  const { home, calls, locationCalls } = setup()
  home.onLoad(); await tick()
  assert.equal(home.data.heroTop, 48)
  assert.ok(home.data.todayText.startsWith(new Date().getFullYear() + '年'))
  assert.equal(home.data.today.id, 'C1')
  assert.equal(home.data.today.image_url, 'https://fixture.invalid/glyph.png')
  assert.equal(home.data.loading, false)
  assert.equal(locationCalls(), 0)
  assert.ok(calls.some(c => c.url === '/merchants' && c.method === 'collection'))
  assert.equal(home.data.merchants[0].distance, '')
  assert.deepEqual(Array.from(home.data.merchants[0].displayTags), ['甲', '乙', '丙'])
})
test('authorized location is reused and visible impressions use displayed IDs', async () => {
  const { home, locationCalls, calls } = setup({ authorized: true })
  home.onLoad(); await tick()
  assert.equal(locationCalls(), 1)
  assert.equal(home.data.merchants[0].distance, '0 m')
  assert.ok(calls.some(c => c.method === 'all' && c.url === '/merchants'))
  assert.ok(calls.filter(c => c.event).every(c => c.payload.entity_id === 'M1'))
})
test('nearby sorting considers merchants beyond the original first four', async () => {
  const merchants = [6, 5, 4, 3, 2, 1].map(n => ({ id: 'M' + n, name: '夹具' + n, latitude: 26.87 + n * .001, longitude: 100.23 }))
  merchants.unshift({ id: 'missing', name: '坐标缺失', latitude: null, longitude: null })
  const { home, calls } = setup({ merchants })
  await home.locate()
  assert.deepEqual(Array.from(home.data.merchants, m => m.id), ['M1', 'M2', 'M3', 'M4'])
  assert.ok(home.data.merchants.every(m => m.distance_m > 0 && m.distance))
  assert.deepEqual(calls.filter(c => c.event).map(c => c.payload.entity_id), ['M1', 'M2', 'M3', 'M4'])
})
test('lost authorization invalidates a refresh started with an old location', async () => {
  const { home, api } = setup({ locationError: '未获得位置授权' })
  await home.load()
  home.data.location = { latitude: 26.87, longitude: 100.23 }
  let finishRefresh
  api.all = () => new Promise(resolve => { finishRefresh = resolve })
  const pending = home.load()
  await home.locate()
  finishRefresh([{ id: 'stale', latitude: 26.87, longitude: 100.23 }])
  await pending
  assert.equal(home.data.location, null)
  assert.equal(home.data.merchants[0].id, 'M1')
  assert.equal(home.data.merchants[0].distance, '')
  assert.equal(home.data.loading, false)
})
test('no location means no distance even if an unscoped payload includes distance_m', async () => {
  const { home } = setup({ merchants: [{ id: 'M1', distance_m: 120 }] })
  await home.load()
  assert.equal(home.data.merchants[0].distance, '')
  assert.equal(home.data.merchants[0].distance_m, null)
})
test('denied location preserves merchants and clears stale distances', async () => {
  const { home } = setup({ locationError: '未获得位置授权' })
  await home.load()
  home.data.merchants[0].distance = '120 m'
  await home.locate()
  assert.equal(home.data.locationError, '未获得位置授权')
  assert.equal(home.data.merchants.length, 1)
  assert.equal(home.data.merchants[0].distance, '')
  assert.equal(home.data.location, null)
  assert.equal(home.data.locating, false)
})
test('invalid location does not produce fictional zero distances', async () => {
  const { home } = setup({ location: { latitude: null, longitude: null } })
  await home.locate()
  assert.equal(home.data.locationError, '暂未获取到有效位置')
  assert.equal(home.data.location, null)
})
test('stale refresh cannot overwrite a newer homepage response', async () => {
  const { home, api } = setup()
  let finishFirst
  let requests = 0
  api.collection = async url => {
    if (url === '/characters') return []
    requests++
    return requests === 1 ? new Promise(resolve => { finishFirst = resolve }) : [{ id: 'new' }]
  }
  const old = home.load()
  await home.load()
  finishFirst([{ id: 'old' }]); await old
  assert.equal(home.data.merchants[0].id, 'new')
  assert.equal(home.data.loading, false)
})
test('unloading prevents pending reads and authorization callbacks from updating page', async () => {
  const { home, api, wx, locationCalls } = setup({ authorized: true })
  let finish, settings
  api.collection = url => url === '/characters' ? Promise.resolve([]) : new Promise(resolve => { finish = resolve })
  wx.getSetting = callback => { settings = callback }
  home.onLoad(); home.onUnload()
  settings.success({ authSetting: { 'scope.userLocation': true } })
  finish([{ id: 'late' }]); await tick()
  assert.equal(home.data.merchants.length, 0)
  assert.equal(locationCalls(), 0)
})
test('explicit empty and unavailable states never fill fictional content', async () => {
  const { home, api } = setup({ characters: [], merchants: [] })
  await home.load()
  assert.equal(home.data.today, null)
  assert.equal(home.data.merchants.length, 0)
  api.collection = async () => { throw new Error('服务暂不可用') }
  await home.load()
  assert.equal(home.data.error, '服务暂不可用')
  assert.equal(home.data.loading, false)
})
test('detail, quick navigation, merchant navigation and camera retain working routes', () => {
  const { home, routes } = setup()
  home.data.today = { id: '汉 字/1' }
  home.character(); home.map(); home.quests(); home.catalog(); home.more()
  home.merchant({ currentTarget: { dataset: { id: '商户/1' } } })
  assert.equal(routes[0], '/pages/character/index?id=' + encodeURIComponent('汉 字/1'))
  assert.deepEqual(routes.slice(1, 5), ['/pages/map/index', '/pages/quests/index', '/pages/catalog/index', '/pages/merchants/index'])
  assert.equal(home.camera(), 'native-camera')
  assert.match(markup, /<button\b[^>]*class="daily-detail"[^>]*bindtap="character"/)
  assert.doesNotMatch(markup, /DAILY GLYPH|NEARBY DISCOVERIES|月销|item\.rating|feature-note/)
})
test('failed merchant cover affects only its own card and preserves navigation identity', async () => {
  const { home } = setup({ merchants: [{ id: 'A' }, { id: 'B' }] })
  await home.load()
  home.merchantImageError({ currentTarget: { dataset: { id: 'B' } } })
  assert.equal(home.data.merchants[0].imageFailed, undefined)
  assert.equal(home.data.merchants[1].imageFailed, true)
  assert.equal(home.data.merchants[1].id, 'B')
})
test('all eight native tab assets exist as small PNGs and every homepage asset resolves', () => {
  const app = JSON.parse(fs.readFileSync(path.join(root, 'app.json'), 'utf8'))
  for (const tab of app.tabBar.list) for (const key of ['iconPath', 'selectedIconPath']) {
    assert.ok(tab[key])
    const bytes = fs.readFileSync(path.join(root, tab[key]))
    assert.equal(bytes.subarray(1, 4).toString(), 'PNG')
    assert.ok(bytes.length < 40 * 1024, 'Native tab icons must stay under 40KB')
  }
  for (const [, asset] of markup.matchAll(/src="(\/assets\/[^\"]+)"/g)) assert.ok(fs.existsSync(path.join(root, asset)))
})
