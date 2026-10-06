// QUEST-01 / QUEST-02 / DESIGN-01: live-data presentation, no client-side awards.
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const { questView } = require('../utils/quest-view')
const { makeQuestFixture } = require('./quest-fixtures')
const fixture = () => makeQuestFixture().feature.item
function pageWith(api = {}, user = null) {
  let page
  const requests = [], routes = []
  const session = { get: () => user, requireLogin: () => !!user }
  const services = { all: async () => [fixture()], collection: async () => [], mediaUrl: value => value || '', request: async url => { requests.push(url); return fixture() }, ...api }
  vm.runInNewContext(fs.readFileSync(path.resolve(__dirname, '../pages/quests/index.js'), 'utf8'), {
    Page: value => { page = value }, require: name => name.endsWith('/api') ? services : name.endsWith('/session') ? session : name.endsWith('/quest-view') ? { questView } : { date: value => value || '' },
    wx: { navigateTo: value => routes.push(value.url), switchTab: value => routes.push(value.url), getWindowInfo: () => ({ statusBarHeight: 44 }), getMenuButtonBoundingClientRect: () => ({ top: 48 }) }
  })
  page.setData = values => Object.assign(page.data, values)
  return { page, requests, routes }
}
test('orbit uses actual nodes, stable sequence, and only completed ids belonging to this route', () => {
  const item = fixture(), before = JSON.stringify(item)
  item.nodes.reverse()
  const result = questView(item, { completed_node_ids: ['fixture-node-0', 'unknown', 'fixture-node-0'] })
  assert.equal(result.total, 3); assert.equal(result.completed, 1)
  assert.equal(result.next.id, 'fixture-node-1'); assert.equal(result.nodes[0].sequence, 1)
  assert.equal(item.nodes[0].sequence, 3)
  item.nodes.reverse(); assert.equal(JSON.stringify(item), before)
})
test('empty, one-node, twelve-node and large routes do not pad with invented tasks', () => {
  for (const count of [0, 1, 3, 8, 9, 10, 11, 12, 13, 30]) {
    const result = makeQuestFixture(count, { guest: true }).feature
    assert.equal(result.nodes.length, count); assert.equal(result.completed, 0)
    assert.equal(result.compact, count > 12)
    assert.equal(result.dense, count >= 9 && count <= 12)
    assert.ok(result.nodes.every(node => !/NaN/.test(node.orbit_style)))
  }
})
test('time boundaries and unpublished enrollment remain read-only presentations', () => {
  const now = Date.parse('2026-09-28T00:00:00Z')
  assert.equal(questView({ ...fixture(), start_at: '2026-09-29T00:00:00Z' }, null, now).closed, true)
  assert.equal(questView({ ...fixture(), end_at: '2026-09-28T00:00:00Z' }, null, now).closed, true)
  assert.equal(questView({ ...fixture(), unavailable: true }, {}, now).action_label, '查看路线记录')
})
test('completion status is not inferred from client counters or missing tasks', () => {
  assert.equal(questView(fixture(), { completed_node_ids: fixture().nodes.map(node => node.id) }).complete, false)
  assert.equal(makeQuestFixture(3, { complete: true }).feature.next, null)
  assert.equal(makeQuestFixture(3, { complete: true }).feature.action_label, '回顾我的寻迹')
})
test('approved related media is optional and condition icons never masquerade as glyphs', () => {
  const item = fixture(), node = item.nodes[2]
  const plain = questView(item, null)
  assert.equal(plain.nodes[2].glyph_name, ''); assert.equal(plain.nodes[2].glyph_url, '')
  const enriched = questView(item, null, Date.now(), { characters: { [node.character_id]: { cn_name: '测试名称', image_url: '/published.png' } } })
  assert.equal(enriched.nodes[2].glyph_url, '/published.png'); assert.equal(enriched.nodes[2].glyph_name, '测试名称')
  assert.equal(enriched.nodes[2].place_image, '')
})
test('guest page uses public detail and reward without requesting member endpoints', async () => {
  const { page } = pageWith({ collection: async () => { throw Error('Unexpected member request') } })
  page.onLoad(); await page.load()
  assert.equal(page.data.heroTop, 48); assert.equal(page.data.feature.total, 3)
  assert.equal(page.data.feature.progress, undefined)
  assert.equal(page.data.featureError, '')
})
test('related media requests are deduplicated and missing reward is isolated', async () => {
  const calls = [], item = fixture(); item.nodes.forEach(node => { node.merchant_id = 'same' })
  const { page } = pageWith({ request: async url => {
    calls.push(url)
    if (url.startsWith('/quests/')) return item
    if (url.startsWith('/coupons/')) throw Error('Unavailable')
    return { name: '已发布商户', image_url: '/published.jpg' }
  } })
  await page.loadFeature(item)
  assert.equal(calls.filter(url => url === '/merchants/same').length, 1)
  assert.equal(page.data.feature.nodes[0].place_image, '/published.jpg')
  assert.equal(page.data.rewardUnavailable, true); assert.equal(page.data.featureError, '')
})
test('failed images clear only the matching node field and next-target copy', async () => {
  const { page } = pageWith(); page.data.feature = makeQuestFixture(3, { guest: true }).feature
  page.mediaFailed({ currentTarget: { dataset: { id: 'fixture-node-0', kind: 'place_image' } } })
  assert.equal(page.data.feature.next.place_image, '')
  assert.ok(page.data.feature.nodes[1].place_image)
  assert.equal(page.data.feature.completed, 0)
})
test('switching routes ignores slow responses from the previous selection', async () => {
  let resolveOld
  const { page } = pageWith({ request: url => url === '/quests/old' ? new Promise(resolve => { resolveOld = resolve }) : Promise.resolve({ id: 'new', nodes: [], name: 'New' }) })
  const old = page.loadFeature({ id: 'old' })
  await page.loadFeature({ id: 'new' }); resolveOld({ id: 'old', nodes: [] }); await old
  assert.equal(page.data.selectedId, 'new'); assert.equal(page.data.feature.item.id, 'new')
})
test('unload prevents late responses from restoring a disposed page', async () => {
  let resolveDetail
  const { page } = pageWith({ request: () => new Promise(resolve => { resolveDetail = resolve }) })
  const pending = page.loadFeature({ id: 'late' }); page.onUnload(); resolveDetail(fixture()); await pending
  assert.equal(page.data.feature, null)
})
test('members can still view enrolled unpublished routes and rewards', async () => {
  const record = { ...fixture(), quest_id: 'archived', nodes: fixture().nodes, status: 'enrolled', completed_node_ids: ['fixture-node-0'] }
  const { page } = pageWith({ all: async () => [], collection: async () => [record] }, { user: { id: 'member' } })
  await page.load()
  assert.equal(page.data.feature.closed, true); assert.equal(page.data.feature.completed, 1)
  assert.equal(page.data.feature.item.id, 'archived')
})
test('login gates remain on personal routes and stamp album, not the public page', () => {
  const { page, routes } = pageWith()
  page.filter({ currentTarget: { dataset: { type: 'mine' } } }); page.stamps()
  assert.equal(page.data.filter, 'all'); assert.equal(routes.length, 0)
})
test('primary, map and album actions retain existing navigation and do not award stamps', () => {
  const { page, routes } = pageWith({}, { user: { id: 'member' } })
  page.data.feature = { item: { id: 'quest/1' } }; page.continueQuest(); page.map(); page.stamps()
  assert.deepEqual(routes, ['/pages/quest/index?id=quest%2F1', '/pages/map/index', '/pages/stamps/index'])
})
