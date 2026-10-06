// GEO-01 / DESIGN-01: deterministic fixtures, not real-world map/navigation evidence.
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const helpers = require('../utils/helpers')
const source = fs.readFileSync(path.join(__dirname, '../pages/map/index.js'), 'utf8')
const markup = fs.readFileSync(path.join(__dirname, '../pages/map/index.wxml'), 'utf8')
const event = dataset => ({ currentTarget: { dataset } })
function setup(options = {}) {
  let page, locationCalls = 0
  const calls = [], navigations = [], routes = [], camera = []
  const pois = options.pois || [
    { id: 'p1', name: '文化点夹具', latitude: 26.9, longitude: 100.23, poi_type: 'culture' },
    { id: 'p2', name: '商户点位夹具', latitude: 26.88, longitude: 100.23, poi_type: 'merchant', merchant_id: 'm1' },
    { id: 'bad', name: '缺少坐标', latitude: null, longitude: null, poi_type: 'landmark' }
  ]
  const merchants = options.merchants || [
    { id: 'm1', name: '商户一', latitude: 26.88, longitude: 100.23, image_url: '/m1.png', address: '后端地址', tags: ['真实标签', '手作', '第三项'] },
    { id: 'm2', name: '商户二', latitude: 26.871, longitude: 100.23, image_url: '', tags: [] }
  ]
  const api = {
    async all(url) { calls.push(url); if (options.error && url === '/map/pois') throw new Error('地点服务不可用'); if (options.questError && url === '/quests') throw new Error('任务不可用'); return url === '/map/pois' ? pois : url === '/merchants' ? merchants : [{ id: 'q1' }] },
    async request() { return { nodes: [{ poi_id: 'p1' }, { merchant_id: 'm1' }] } },
    mediaUrl(value) { return value ? 'https://fixture.invalid' + value : '' },
    track(name, payload) { calls.push({ name, payload }) }, showError(error) { calls.push({ error: error.message }) }
  }
  const platform = {
    async locate() { locationCalls++; if (options.locationError) throw new Error('位置授权被拒绝'); return { latitude: 26.87, longitude: 100.23 } },
    async navigate(point) { if (!helpers.coordinates(point)) throw new Error('坐标不可用'); navigations.push(point) }
  }
  const wx = {
    navigateTo(value) { routes.push(value.url) }, stopPullDownRefresh() {},
    createMapContext() { return { getScale({ success }) { success({ scale: 17.5 }) }, moveToLocation(value) { camera.push(value) } } }
  }
  vm.runInNewContext(source, { Page(value) { page = value }, require(id) { return ({ '../../utils/api': api, '../../utils/helpers': helpers, '../../utils/platform': platform })[id] }, wx })
  page.data = JSON.parse(JSON.stringify(page.data))
  page.setData = (value, callback) => { Object.assign(page.data, value); if (callback) callback() }
  return { page, calls, navigations, routes, camera, locationCalls: () => locationCalls }
}
test('map uses native map, covering controls and bounded native mini actions', () => {
  assert.match(markup, /<map\b[^>]*id="culture-map"/)
  assert.match(markup, /<cover-view[^>]*class="map-tool map-locate"[^>]*bindtap="locate"/)
  assert.match(markup, /enable-satellite="\{\{satellite\}\}"/)
  assert.ok([...markup.matchAll(/<button\b[^>]*>/g)].every(match => match[0].includes('size="mini"')))
  assert.doesNotMatch(markup, /月销|评分最高|9折|满30减5|推荐排序/)
  assert.doesNotMatch(markup, /map-brand|东巴寻迹/)
  assert.doesNotMatch(markup, /<button\b[^>]*class="place-main"/)
})
test('load merges published merchant media and address without duplicating mapped merchants', async () => {
  const { page, locationCalls } = setup(); await page.load()
  assert.equal(page.data.points.length, 3)
  const point = page.data.points.find(p => p.id === 'p2')
  assert.equal(point.name, '商户点位夹具')
  assert.equal(point.image_url, 'https://fixture.invalid/m1.png')
  assert.equal(point.address, '后端地址')
  assert.equal(point.display_tags.join(','), '真实标签,手作')
  assert.equal(locationCalls(), 0)
  assert.ok(page.data.visiblePoints.every(p => p.distance === '' && p.distance_m === null))
  assert.equal(page.data.loading, false)
})
test('culture, merchant and quest filters retain stable marker identity', async () => {
  const { page } = setup(); await page.load()
  page.filter(event({ type: 'culture' })); assert.equal(page.data.visiblePoints.map(p => p.id).join(), 'p1')
  page.filter(event({ type: 'merchant' })); assert.equal(page.data.visiblePoints.map(p => p.id).join(), 'p2,merchant:m2')
  assert.equal(page.data.markers[0].id, 2)
  page.filter(event({ type: 'quest' })); assert.equal(page.data.visiblePoints.map(p => p.id).join(), 'p1,p2')
  assert.ok(page.data.markers.every(marker => marker.iconPath.endsWith('marker-quest.png')))
  page.filter(event({ type: 'bad' })); assert.equal(page.data.filter, 'quest')
})
test('selecting a card or marker recenters and highlights the correct published point', async () => {
  const { page, camera } = setup(); await page.load()
  page.select(event({ id: 'merchant:m2' }))
  assert.equal(page.data.selected.id, 'merchant:m2'); assert.equal(page.data.center.latitude, 26.871)
  assert.equal(page.data.markers.find(m => m.id === 3).width, 38)
  page.marker({ detail: { markerId: '2' } }); assert.equal(page.data.selected.id, 'p2')
  assert.equal(camera.length, 2)
  page.marker({ detail: { markerId: 999 } }); assert.equal(page.data.selected.id, 'p2')
})
test('distance sorting requests explicit location and computes actual straight-line distances', async () => {
  const { page, locationCalls, camera } = setup(); await page.load()
  await page.sortPoints(event({ sort: 'distance' }))
  assert.equal(locationCalls(), 1); assert.equal(page.data.sort, 'distance')
  assert.equal(page.data.visiblePoints.map(p => p.id).join(), 'merchant:m2,p2,p1')
  assert.ok(page.data.visiblePoints[0].distance_m > 110 && page.data.visiblePoints[0].distance_m < 112)
  assert.equal(page.data.visiblePoints[0].distance, '111 m')
  assert.ok(page.data.markers[0].callout.content.includes('111 m'))
  assert.equal(camera[0].latitude, 26.87)
  await page.sortPoints(event({ sort: 'default' })); assert.equal(page.data.visiblePoints[0].id, 'p1')
  assert.equal(locationCalls(), 1)
})
test('location refusal preserves default order and allows navigation', async () => {
  const { page, navigations } = setup({ locationError: true }); await page.load()
  await page.sortPoints(event({ sort: 'distance' }))
  assert.equal(page.data.sort, 'default'); assert.equal(page.data.location, null)
  assert.equal(page.data.locating, false); assert.match(page.data.locationError, /拒绝/)
  assert.ok(page.data.visiblePoints.every(p => p.distance === ''))
  await page.navigate(event({ id: 'p2' })); assert.equal(navigations[0].id, 'p2')
})
test('navigation and details use their own card id rather than stale selected state', async () => {
  const { page, navigations, routes, calls } = setup(); await page.load()
  await page.navigate(event({ id: 'merchant:m2' })); page.detail(event({ id: 'p2' }))
  assert.equal(navigations[0].merchant_id, 'm2'); assert.equal(routes[0], '/pages/merchant/index?id=m1')
  assert.ok(calls.some(call => call.name === 'navigate' && call.payload.entity_id === 'm2'))
  page.detail(event({ id: 'p1' })); assert.equal(routes.length, 1)
  await page.navigate(event({ id: 'missing' })); assert.ok(calls.some(call => call.error === '坐标不可用'))
})
test('a later location refusal clears previously computed distances and distance sorting', async () => {
  const options = {}, { page } = setup(options); await page.load()
  await page.sortPoints(event({ sort: 'distance' })); assert.ok(page.data.visiblePoints[0].distance)
  options.locationError = true; await page.locate()
  assert.equal(page.data.location, null); assert.equal(page.data.sort, 'default')
  assert.ok(page.data.visiblePoints.every(point => point.distance === ''))
  assert.ok(page.data.markers.every(marker => !marker.callout.content.includes('\n')))
  assert.ok(page.data.center, 'Previously displayed map remains available without claiming a current user location')
})
test('zoom is bounded, gesture scale syncs and layer toggle retains selection', async () => {
  const { page } = setup(); await page.load()
  for (let i = 0; i < 20; i++) page.zoom(event({ step: 1 }))
  assert.equal(page.data.scale, 19)
  for (let i = 0; i < 20; i++) page.zoom(event({ step: -1 }))
  assert.equal(page.data.scale, 11)
  page.regionChange({ detail: { type: 'end', causedBy: 'update' } }); assert.equal(page.data.scale, 11)
  page.regionChange({ detail: { type: 'end', causedBy: 'scale' } }); assert.equal(page.data.scale, 17.5)
  page.toggleLayer(); assert.equal(page.data.satellite, true); assert.equal(page.data.selected.id, 'p1')
})
test('failed merchant image falls back without moving the selected point or losing distance', async () => {
  const { page } = setup(); await page.load(); await page.locate(); page.select(event({ id: 'p2' }))
  page.imageError(event({ id: 'p2' }))
  assert.equal(page.data.selected.id, 'p2'); assert.equal(page.data.selected.image_url, '')
  assert.equal(page.data.center.latitude, 26.88); assert.ok(page.data.selected.distance)
})
test('quest failure is explicit while published map points remain available', async () => {
  const { page } = setup({ questError: true }); await page.load()
  assert.equal(page.data.points.length, 3); assert.equal(page.data.error, ''); assert.ok(page.data.questError)
  page.filter(event({ type: 'quest' })); assert.equal(page.data.visiblePoints.length, 0)
  assert.equal(page.data.selected, null); assert.equal(page.data.markers.length, 0); assert.ok(page.data.center)
})
test('point service failure exits loading and shows a retryable error', async () => {
  const { page } = setup({ error: true }); await page.load()
  assert.equal(page.data.error, '地点服务不可用'); assert.equal(page.data.loading, false)
  assert.equal(page.data.points.length, 0)
})
test('invalid POI coordinates do not suppress a valid merchant fallback', async () => {
  const { page } = setup({ pois: [{ id: 'invalid', name: '无坐标点位', merchant_id: 'm1', latitude: null, longitude: null }] })
  await page.load(); assert.equal(page.data.points.length, 2)
  assert.equal(page.data.points[0].id, 'merchant:m1')
})
