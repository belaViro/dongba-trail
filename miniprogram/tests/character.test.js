// CONTENT-01 / REC-01 / DESIGN-01: association layout and existing route contracts.
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const root = path.resolve(__dirname, '../pages/character')
const markup = fs.readFileSync(path.join(root, 'index.wxml'), 'utf8')
function harness({ loggedIn = false, character = {}, characters = [] } = {}) {
  let page
  const routes = [], calls = [], events = []
  const api = {
    mediaUrl(value) { return value ? 'https://media.example.test' + value : '' },
    async request(url, options) { calls.push({ url, options }); return { id: 'word-1', cn_name: '测试词条', ...character } },
    async collection() { return [] }, async all() { return characters },
    track(name) { events.push(name) }, showError(error) { throw error }
  }
  vm.runInNewContext(fs.readFileSync(path.join(root, 'index.js'), 'utf8'), {
    Page(value) { page = value },
    require(name) { return name.endsWith('/api') ? api : name.endsWith('/session') ? { get: () => loggedIn, requireLogin: () => loggedIn } : require('../utils/helpers') },
    wx: { navigateTo({ url }) { routes.push(url) }, switchTab({ url }) { routes.push(url) } }
  })
  page.data = { ...page.data }; page.setData = values => Object.assign(page.data, values)
  page.characterId = '字/1'
  return { page, routes, calls, events }
}
test('D-064 removes the writing card without removing published culture and source', () => {
  assert.doesNotMatch(markup, /这个字怎么写|item\.variants|variant-track/)
  assert.match(markup, /item\.culture_detail/)
  assert.match(markup, /item\.source_ref/)
  assert.match(markup, /wx:if="{{item.audio_url}}"/)
  assert.match(markup, /暂无词条音频/)
  assert.doesNotMatch(markup, /评分|月销|领券|<video|pinyin/)
})
test('D-065 main glyph is static without fullscreen preview or tap hints', () => {
  assert.match(markup, /<view class="hero-glyph"[^>]*><glyph-image src="{{item.image_url}}"/)
  assert.doesNotMatch(markup, /<button class="hero-glyph"|bindtap="preview"|glyph-caption|glyph-pressed|轻触字形|字形大图/)
  assert.doesNotMatch(fs.readFileSync(path.join(root, 'index.js'), 'utf8'), /wx\.previewImage/)
  assert.equal(harness().page.preview, undefined)
})
test('D-064 related words render real image fields and retain navigation', () => {
  assert.match(markup, /class="related-word"[^>]*data-id="{{item.id}}"[^>]*bindtap="related"/)
  assert.match(markup, /class="related-glyph"><glyph-image src="{{item.image_url}}"/)
  const { page, routes } = harness()
  page.related({ currentTarget: { dataset: { id: 'related/2' } } })
  assert.deepEqual(routes, ['/pages/character/index?id=related%2F2'])
})
test('D-064 loading normalizes hero and related media without mutating variant records', async () => {
  const variants = [{ image_url: '/media/original.png', source_ref: 'published source' }]
  const { page, events } = harness({
    character: { image_url: '/media/main.png', category_l1: '测试分类', variants },
    characters: [{ id: 'word-1', category_l1: '测试分类' }, { id: 'word-2', category_l1: '测试分类', image_url: '/media/related.png' }, { id: 'word-3', category_l1: '测试分类' }, { id: 'word-4', category_l1: '其他分类' }]
  })
  await page.load()
  assert.equal(page.data.loading, false); assert.equal(page.data.error, '')
  assert.equal(page.data.item.image_url, 'https://media.example.test/media/main.png')
  assert.equal(page.data.item.variants, variants)
  assert.equal(page.data.related.length, 2)
  assert.equal(page.data.related[0].image_url, 'https://media.example.test/media/related.png')
  assert.equal(page.data.related[1].image_url, '')
  assert.deepEqual(events, ['character_detail'])
})
test('D-064 bottom actions retain favorites, nearby merchants and poster entry', () => {
  assert.match(markup, /class="favorite-action[^>]*bindtap="favorite"/)
  assert.match(markup, /class="nearby-action" bindtap="nearby"/)
  assert.match(markup, /class="primary poster-action" bindtap="share"/)
  const { page, routes } = harness({ loggedIn: true })
  page.share(); page.quests()
  assert.deepEqual(routes, ['/pages/poster/index?character_id=%E5%AD%97%2F1', '/pages/quests/index'])
})
test('D-064 favorite uses distinct local outline/filled stars, not a box or font glyph', () => {
  assert.doesNotMatch(markup, /bookmark-icon/)
  assert.match(markup, /<image class="favorite-icon" src="{{saved \? '\/assets\/icons\/favorite-filled.png' : '\/assets\/icons\/favorite-outline.png'}}" mode="aspectFit"/)
  const icons = ['favorite-outline.png', 'favorite-filled.png'].map(name => fs.readFileSync(path.join(root, '../../assets/icons', name)))
  for (const png of icons) {
    assert.equal(png.subarray(1, 4).toString(), 'PNG')
    assert.equal(png.readUInt32BE(16), 72); assert.equal(png.readUInt32BE(20), 72)
    assert.ok(png.length < 5000)
  }
  assert.notDeepEqual(icons[0], icons[1])
})
test('D-064 guest cannot silently favorite or enter authenticated poster generation', async () => {
  const { page, routes, calls } = harness()
  await page.favorite(); page.share()
  assert.equal(routes.length, 0); assert.equal(calls.length, 0)
})
test('D-064 favorite toggle keeps escaped id, authentication and busy state', async () => {
  const { page, calls } = harness({ loggedIn: true })
  await page.favorite(); assert.equal(page.data.saved, true)
  await page.favorite(); assert.equal(page.data.saved, false)
  assert.deepEqual(calls.map(call => call.options.method), ['PUT', 'DELETE'])
  assert.ok(calls.every(call => call.url === '/me/favorites/%E5%AD%97%2F1' && call.options.auth))
  assert.equal(page.data.favoriteBusy, false)
})
test('merchant and product rows use explicit mini sizing, not native wide-button defaults', () => {
  const rows = [...markup.matchAll(/<button\b[^>]*class="merchant-row"[^>]*>/g)]
  assert.equal(rows.length, 2)
  assert.ok(rows.every(([tag]) => /size="mini"/.test(tag)))
  assert.equal((markup.match(/class="association-copy"/g) || []).length, 2)
  assert.match(markup, /<button size="mini" class="association-more" bindtap="nearby"/)
})
test('merchants retain their own ids; products navigate by merchant_id, not product id', () => {
  assert.match(markup, /wx:for="{{merchants}}"[^>]*data-id="{{item.id}}"[^>]*bindtap="merchant"/)
  assert.match(markup, /wx:for="{{products}}"[^>]*data-id="{{item.merchant_id}}"[^>]*bindtap="merchant"/)
})
test('missing merchant data and absent products remain explicit rather than filled with examples', () => {
  assert.match(markup, /wx:if="{{!merchants.length}}"[^>]*>暂未关联文化地点/)
  assert.match(markup, /class="section paper-card association-section product-section" wx:if="{{products.length}}"/)
  assert.match(markup, /{{item.price}}/)
})
test('association navigation preserves escaped ids and original recognition binding', () => {
  let page
  const routes = []
  vm.runInNewContext(fs.readFileSync(path.join(root, 'index.js'), 'utf8'), {
    Page(value) { page = value }, require() { return {} }, wx: { navigateTo(value) { routes.push(value.url) } }
  })
  page.characterId = '字/1'; page.recognitionId = 'request/2'
  page.merchant({ currentTarget: { dataset: { id: 'merchant/3' } } }); page.nearby()
  assert.deepEqual(routes, ['/pages/merchant/index?id=merchant%2F3&recognition_id=request%2F2', '/pages/merchants/index?character_id=%E5%AD%97%2F1&recognition_id=request%2F2'])
})
