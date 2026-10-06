// QUEST-01 / QUEST-02 / DESIGN-01, D-057: minimal UI, unchanged task/reward rules.
const test = require('node:test')
const assert = require('node:assert/strict')
const vm = require('node:vm')
const { children, tree, read } = require('./visual-preview.cjs')
const { questDetailFixture } = require('./quest-detail-fixtures.cjs')
const render = data => children(tree('pages/quest/index.wxml'), data)
const buttons = html => [...html.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/g)].map(match => ({ attrs: match[1], text: match[2].replace(/<[^>]*>/g, '') }))
const tap = id => ({ currentTarget: { dataset: { id } } })
function pageWith(points = []) {
  let page
  const errors = [], routes = [], navigated = [], requests = []
  const services = {
    api: { all: async url => { assert.equal(url, '/map/pois'); return points }, showError: error => errors.push(error.message), request: async (...args) => requests.push(args), collection: async () => [], track() {} },
    platform: { navigate: async point => navigated.push(point) },
    session: { requireLogin: () => true, get: () => null }
  }
  vm.runInNewContext(read('pages/quest/index.js'), {
    Page: value => { page = value },
    require: name => services[name.split('/').pop()] || {},
    wx: { navigateTo: value => routes.push(value.url) }
  })
  page.data = questDetailFixture(); page.questId = page.data.item.id
  page.setData = values => Object.assign(page.data, values)
  return { page, errors, routes, navigated, requests, services }
}
for (const [id, expected] of [['both', '导航'], ['poi', '导航'], ['merchant', '查看地点'], ['manual', null]]) {
  test('one relevant location action per node: ' + id, () => {
    const data = questDetailFixture()
    data.nodes = data.nodes.filter(node => node.id === id)
    const links = buttons(render(data)).filter(button => /class="location-button"/.test(button.attrs))
    assert.equal(links.length, expected ? 1 : 0)
    if (expected) {
      assert.equal(links[0].text, expected)
      assert.match(links[0].attrs, new RegExp('data-id="' + (id === 'merchant' ? 'fixture-shop' : id) + '"'))
    }
  })
}
test('remove advance reward prompts and duplicate method/count labels', () => {
  const html = render(questDetailFixture())
  assert.doesNotMatch(html, /完成全部节点|查看任务地点|导航至任务地点|个节点|class="tag"/)
  assert.match(html.replace(/<[^>]*>/g, ''), /0 \/ 5/)
  assert.match(html, /沿途印记/)
  assert.doesNotMatch(html, /class="[^"]*\bnotice\b/)
})
test('all five check-in methods remain distinct and actionable', () => {
  const actions = buttons(render(questDetailFixture())).filter(button => button.attrs.includes('node-button'))
  assert.deepEqual(actions.map(button => button.text), ['扫码打卡', '到达打卡', '拍照识字', '查看确认方式', '验证核销'])
  assert.ok(actions.every(button => !button.attrs.includes('disabled')))
})
test('completed nodes cannot check in twice and still allow location access', () => {
  const data = questDetailFixture()
  data.nodes = [{ ...data.nodes[0], completed: true }]
  const actions = buttons(render(data))
  assert.equal(actions.filter(button => button.text === '导航').length, 1)
  const done = actions.find(button => button.attrs.includes('node-button'))
  assert.equal(done.text, '已获得'); assert.match(done.attrs, /disabled/)
})
test('closed routes and busy actions keep check-in disabled', () => {
  for (const overrides of [{ closed: true }, { busy: 'both' }]) {
    const html = render(questDetailFixture(overrides))
    assert.ok(buttons(html).filter(button => button.attrs.includes('node-button')).every(button => button.attrs.includes('disabled')))
    if (overrides.closed) assert.match(html, /路线当前未开放/)
  }
})
test('guests keep enrollment and no speculative reward notice', () => {
  const html = render(questDetailFixture({ progress: null }))
  assert.equal(buttons(html).filter(button => button.text === '加入寻迹').length, 1)
  assert.doesNotMatch(html, /完成全部节点|重试领取奖励/)
})
test('issued rewards retain one wallet notice and completed state', () => {
  const html = render(questDetailFixture({ reward: { title: '测试体验券' }, progress: { status: 'completed', reward_pending: false } }))
  assert.equal((html.match(/class="[^"]*\bnotice\b/g) || []).length, 1)
  assert.match(html, /寻迹奖励已到账/)
  assert.match(html, /测试体验券/)
  assert.match(html, /查看券/)
  assert.match(html, /已完成本次寻迹/)
  assert.doesNotMatch(html, /重试领取奖励/)
})
test('pending rewards retain the recovery action without duplicate guidance', () => {
  const html = render(questDetailFixture({ progress: { status: 'completed', reward_pending: true }, busy: 'reward' }))
  assert.equal((html.match(/class="[^"]*\bnotice\b/g) || []).length, 1)
  assert.match(html, /奖励正在补充中/)
  const retry = buttons(html).find(button => button.text === '重试领取奖励')
  assert.match(retry.attrs, /disabled/); assert.match(retry.attrs, /loading/)
})
test('navigation uses the configured published POI without completing a node', async () => {
  const point = { id: 'fixture-poi', latitude: 26.87, longitude: 100.23 }
  const { page, navigated, requests, errors } = pageWith([point])
  await page.navigateNode(tap('both'))
  assert.deepEqual(navigated, [point]); assert.equal(requests.length, 0); assert.equal(errors.length, 0)
})
test('missing POIs remain explicitly unavailable instead of using made-up coordinates', async () => {
  const { page, navigated, errors } = pageWith()
  await page.navigateNode(tap('poi'))
  assert.equal(navigated.length, 0); assert.deepEqual(errors, ['任务地点暂不可导航，请联系现场运营人员'])
})
test('merchant-only and earned-reward links preserve their destinations', () => {
  const { page, routes } = pageWith()
  page.merchant(tap('fixture/shop')); page.wallet()
  assert.deepEqual(routes, ['/pages/merchant/index?id=fixture%2Fshop', '/pages/coupons/index'])
})
test('pending reward retry still uses the existing server check-in endpoint', async () => {
  const { page, requests } = pageWith()
  page.data.progress = { reward_pending: true, completed_node_ids: ['both'] }
  page.load = async () => { page.data.progress.reward_pending = false }
  await page.retryReward()
  assert.equal(requests.length, 1)
  assert.deepEqual(JSON.parse(JSON.stringify(requests[0])), ['/quests/fixture-route/checkin', { method: 'POST', auth: true, data: { node_id: 'both' } }])
  assert.equal(page.data.busy, '')
})
test('route journal highlights only the first unfinished ordered node without locking others', async () => {
  const { page, services } = pageWith()
  const source = [{ id: 'last', sequence: 3 }, { id: 'first', sequence: 1 }, { id: 'next', sequence: 2 }]
  services.session.get = () => ({ user: { id: 'fixture-user' } })
  services.api.collection = async () => [{ quest_id: page.questId, completed_node_ids: ['first'], status: 'enrolled' }]
  services.api.request = async () => ({ id: page.questId, nodes: source })
  await page.load()
  assert.deepEqual(Array.from(page.data.nodes, node => node.id), ['first', 'next', 'last'])
  assert.deepEqual(Array.from(page.data.nodes.filter(node => node.is_next), node => node.id), ['next'])
  assert.equal(page.data.completed, 1); assert.equal(page.data.percent, 33)
  assert.equal(page.data.nodes[2].completed, false)
  assert.deepEqual(source.map(node => node.id), ['last', 'first', 'next'])
  assert.equal(buttons(render(page.data)).filter(button => button.attrs.includes('node-button') && !button.attrs.includes('disabled')).length, 2)
})
test('all-complete routes have no suggested incomplete node', async () => {
  const { page, services } = pageWith()
  services.session.get = () => ({ user: {} })
  services.api.collection = async () => [{ quest_id: page.questId, completed_node_ids: ['only'], status: 'completed' }]
  services.api.request = async () => ({ id: page.questId, nodes: [{ id: 'only', sequence: 1 }] })
  await page.load()
  assert.equal(page.data.nodes.filter(node => node.is_next).length, 0)
  assert.equal(page.data.percent, 100)
})
test('decorative image failure keeps the title and business actions', () => {
  const { page, requests } = pageWith()
  page.onHeroError()
  const html = render(page.data)
  assert.doesNotMatch(html, /class="route-hero-image"/)
  assert.match(html, /寻迹详情布局示例/)
  assert.equal(buttons(html).filter(button => button.attrs.includes('node-button')).length, 5)
  assert.equal(requests.length, 0)
})
