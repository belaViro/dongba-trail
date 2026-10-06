// AI-03 / CONTENT-01 / REC-01 / DESIGN-01: fixture behavior, not AI accuracy.
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const helpers = require('../utils/helpers')
const source = fs.readFileSync(path.join(__dirname, '../pages/result/index.js'), 'utf8')
const markup = fs.readFileSync(path.join(__dirname, '../pages/result/index.wxml'), 'utf8')
const tick = () => new Promise(resolve => setImmediate(resolve))
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
const event = id => ({ currentTarget: { dataset: { id } } })
const candidate = (id, provider_score) => ({ character_id: id, cn_name: '候选' + id, provider_score })
const detail = id => ({ id, cn_name: '已发布' + id, image_url: '/glyph-' + id + '.png', audio_url: '/audio-' + id + '.mp3', category_l1: '分类', category_l2: '子类', tags: ['分类', '标签'], culture_summary: '夹具摘要', culture_detail: '夹具正文', source_ref: '测试来源', variants: [{ image_url: '/variant.png', source_ref: '字形来源' }] })
function setup(options = {}) {
  let resultPage, writes = 0
  const calls = [], routes = [], audio = [], errors = [], previews = [], scrolls = []
  const identity = { user: { id: 'fixture-user' } }
  const app = { globalData: { recognition: options.result === undefined ? { request_id: 'request/1', status: 'NEED_USER_CONFIRM', candidates: [candidate('A', 0.682), candidate('B', null)] } : options.result, recognitionImage: '/local-photo.jpg' } }
  const api = {
    mediaUrl: value => value ? 'media:' + value : '',
    request: async (url, config = {}) => { calls.push({ url, ...config }); if (options.request) return options.request(url, config); return url.startsWith('/characters/') ? detail(decodeURIComponent(url.split('/').pop())) : {} },
    collection: async (url, config) => { calls.push({ url, config }); if (options.collection) return options.collection(url, config); return [{ id: 'M1', name: '关联商户', image_url: '/merchant.png', tags: ['甲', '乙', '丙'] }] },
    all: async (url, config, auth) => { calls.push({ url, config, auth }); return options.all ? options.all() : [{ character_id: 'A' }] },
    showError: error => errors.push(error.message), errorFrom: () => new Error('识别服务不可用'),
    uploadFeedbackImage: async () => { throw new Error('Unexpected upload') }
  }
  const wx = {
    navigateTo: value => routes.push(value.url), redirectTo: value => routes.push(value.url), switchTab: value => routes.push(value.url),
    previewImage: value => previews.push(value), pageScrollTo: value => scrolls.push(value),
    createInnerAudioContext() { const context = { plays: 0, pauses: 0, destroys: 0, play() { this.plays++ }, pause() { this.pauses++ }, destroy() { this.destroys++ }, onEnded(fn) { this.ended = fn }, onError(fn) { this.error = fn } }; audio.push(context); return context }
  }
  vm.runInNewContext(source, {
    require(id) { if (id.endsWith('/api')) return api; if (id.endsWith('/helpers')) return helpers; if (id.endsWith('/session')) return { get: () => options.loggedIn ? identity : null, requireLogin: () => !!options.loggedIn }; throw new Error(id) },
    Page(value) { resultPage = value }, getApp: () => app, wx, console, Map, Set
  })
  resultPage.data = JSON.parse(JSON.stringify(resultPage.data))
  resultPage.setData = (data, callback) => { Object.assign(resultPage.data, data); writes++; if (callback) callback() }
  return { page: resultPage, calls, routes, audio, errors, previews, scrolls, app, writes: () => writes }
}
test('first candidate is only a preview; published content/media are cached and missing scores stay absent', async () => {
  const { page, calls } = setup()
  await page.onLoad()
  assert.equal(page.data.selected, '')
  assert.equal(page.data.preview.id, 'A')
  assert.equal(page.data.preview.available, true)
  assert.equal(page.data.preview.score_text, '68.2%')
  assert.equal(page.data.candidates[1].score_text, '')
  assert.equal(page.data.preview.culture_detail, '夹具正文')
  assert.equal(page.data.preview.variants[0].image_url, 'media:/variant.png')
  assert.deepEqual(Array.from(page.data.preview.display_tags), ['分类', '子类', '标签'])
  assert.equal(page.data.candidates[1].image_url, 'media:/glyph-B.png')
  assert.equal(calls.filter(call => call.url === '/characters/A').length, 1)
  assert.ok(calls.every(call => !call.url.includes('/confirm') && !call.url.includes('/favorites')))
})
test('deduplicates and caps candidates at five without discarding an explicit zero score', async () => {
  const { page } = setup({ result: { request_id: 'r', candidates: [candidate('A', 0), candidate('A', 0), ...['B','C','D','E','F'].map(id => candidate(id, null))] } })
  await page.onLoad()
  assert.equal(page.data.candidates.length, 5)
  assert.equal(page.data.preview.score_text, '0.0%')
  assert.deepEqual(Array.from(page.data.candidates, item => item.rank), [1,2,3,4,5])
})
test('explicit choice changes published preview and scoped merchants without confirming', async () => {
  const { page, calls } = setup({ loggedIn: true })
  await page.onLoad(); assert.equal(page.data.saved, true)
  await page.choose(event('B'))
  assert.equal(page.data.selected, 'B'); assert.equal(page.data.preview.rank, 2)
  assert.equal(page.data.saved, false)
  assert.ok(calls.some(call => call.url === '/characters/B/nearby'))
  assert.ok(calls.every(call => !call.url.includes('/confirm')))
  const count = calls.length
  await page.choose(event('not-a-candidate')); page.data.busy = true; await page.choose(event('A'))
  assert.equal(calls.length, count); assert.equal(page.data.selected, 'B')
})
test('published detail failure never substitutes generated or candidate cultural content', async () => {
  const { page, calls } = setup({ request: async () => { throw new Error('not published') } })
  await page.onLoad()
  assert.equal(page.data.preview.available, false)
  assert.match(page.data.previewError, /已发布内容暂不可用/)
  assert.equal(page.data.previewLoading, false); assert.equal(page.data.merchantsLoading, false)
  assert.equal(page.data.merchants.length, 0)
  assert.ok(calls.every(call => !call.url.endsWith('/nearby')))
})
test('merchant failure is isolated from available dictionary content', async () => {
  const { page } = setup({ collection: async () => { throw new Error('offline') } })
  await page.onLoad()
  assert.equal(page.data.preview.available, true)
  assert.equal(page.data.merchants.length, 0)
  assert.match(page.data.merchantsError, /暂时无法加载/)
})
test('late old detail cannot overwrite a newly selected candidate', async () => {
  const pending = deferred()
  const { page } = setup({ request: url => url === '/characters/A' ? pending.promise : Promise.resolve(detail('B')) })
  const loading = page.onLoad(); await tick(); await page.choose(event('B'))
  pending.resolve(detail('A')); await loading
  assert.equal(page.data.preview.id, 'B'); assert.equal(page.data.selected, 'B')
})
test('late merchant and favorite responses cannot overwrite the new preview', async () => {
  const oldMerchants = deferred(), oldFavorites = deferred(); let favoriteReads = 0
  const { page } = setup({ loggedIn: true, collection: url => url.includes('/A/') ? oldMerchants.promise : Promise.resolve([{ id: 'B-shop' }]), all: () => ++favoriteReads === 1 ? oldFavorites.promise : Promise.resolve([]) })
  const loading = page.onLoad(); await tick(); await page.choose(event('B'))
  oldMerchants.resolve([{ id: 'A-shop' }]); oldFavorites.resolve([{ character_id: 'A' }]); await loading
  assert.equal(page.data.merchants[0].id, 'B-shop'); assert.equal(page.data.saved, false)
})
test('unload prevents pending content writes', async () => {
  const pending = deferred()
  const { page, writes } = setup({ request: () => pending.promise })
  const loading = page.onLoad(); page.onUnload(); const count = writes()
  pending.resolve(detail('A')); await loading
  assert.equal(writes(), count)
})
test('logout invalidates an in-flight favorite read and onShow does not duplicate active reads', async () => {
  const pending = deferred(), options = { loggedIn: true, all: () => pending.promise }
  const { page, calls } = setup(options)
  const loading = page.onLoad(); await tick(); page.onShow()
  assert.equal(calls.filter(call => call.url === '/me/favorites').length, 1)
  options.loggedIn = false; page.onShow()
  pending.resolve([{ character_id: 'A' }]); await loading
  assert.equal(page.data.saved, false); assert.equal(page.data.favoriteLoading, false)
})
test('retry refreshes a failed published detail and missing audio stays unavailable', async () => {
  let failed = true
  const { page, audio } = setup({ request: async url => { if (failed) throw new Error('offline'); return { ...detail(url.split('/').pop()), audio_url: '', variants: [] } } })
  await page.onLoad(); failed = false; await page.retryPreview()
  assert.equal(page.data.previewError, ''); assert.equal(page.data.preview.available, true)
  assert.equal(page.data.preview.variants.length, 0)
  page.audio(); assert.equal(audio.length, 0)
})
test('favorite respects auth and status, performs only PUT/DELETE, never recognition confirmation', async () => {
  const unauthenticated = setup(); await unauthenticated.page.onLoad(); await unauthenticated.page.favorite()
  assert.ok(unauthenticated.calls.every(call => !call.url.includes('/favorites')))
  const { page, calls } = setup({ loggedIn: true }); await page.onLoad()
  await page.favorite(); assert.equal(page.data.saved, false)
  await page.favorite(); assert.equal(page.data.saved, true)
  assert.deepEqual(calls.filter(call => call.method).map(call => [call.url, call.method, call.auth]), [['/me/favorites/A', 'DELETE', true], ['/me/favorites/A', 'PUT', true]])
  assert.equal(page.data.selected, '')
})
test('unknown favorite state is retried instead of blindly toggled', async () => {
  let reads = 0
  const { page, calls } = setup({ loggedIn: true, all: async () => { if (++reads === 1) throw new Error('offline'); return [] } })
  await page.onLoad(); assert.match(page.data.favoriteError, /重试/)
  await page.favorite(); assert.equal(page.data.favoriteError, '')
  assert.equal(calls.filter(call => call.method).length, 0)
  await page.favorite(); assert.equal(calls.at(-1).method, 'PUT')
})
test('audio uses published media, toggles, and releases contexts on choice/hide/unload', async () => {
  const { page, audio, errors } = setup(); await page.onLoad()
  page.audio(); assert.equal(audio[0].src, 'media:/audio-A.mp3'); assert.equal(audio[0].plays, 1)
  page.audio(); assert.equal(audio[0].pauses, 1)
  page.audio(); audio[0].ended(); assert.equal(page.data.playing, false)
  await page.choose(event('B')); assert.equal(audio[0].destroys, 1)
  page.audio(); audio[0].error(); assert.equal(errors.length, 0)
  audio[1].error(); assert.equal(errors.length, 1); assert.equal(page.data.playing, false)
  page.onHide(); assert.equal(audio[1].destroys, 1)
  page.audio(); page.onUnload(); assert.equal(audio[2].destroys, 1)
})
test('routes keep original recognition binding and only allow displayed merchant IDs', async () => {
  const { page, routes } = setup(); await page.onLoad()
  page.nearby(); page.merchant(event('M1')); page.merchant(event('other'))
  assert.deepEqual(routes, ['/pages/merchants/index?character_id=A&recognition_id=request%2F1', '/pages/merchant/index?id=M1&recognition_id=request%2F1'])
})
test('feedback toggle preserves explicit attachment consent and entered comment; photo failure is honest', async () => {
  const { page, scrolls, previews } = setup(); await page.onLoad()
  assert.equal(page.data.attachImage, false)
  page.comment({ detail: { value: '人工复核说明' } }); page.attachmentConsent({ detail: { value: ['attach'] } })
  page.toggleFeedback(); page.toggleFeedback(); page.toggleFeedback()
  assert.equal(page.data.comment, '人工复核说明'); assert.equal(page.data.attachImage, true)
  assert.equal(scrolls.length, 2)
  page.previewImage({ currentTarget: { dataset: { src: '/local-photo.jpg' } } }); assert.equal(previews[0].current, '/local-photo.jpg')
  page.photoError(); assert.equal(page.data.image, '')
  page.merchantImageError(event('M1')); assert.equal(page.data.merchants[0].image_url, '')
})
test('empty/failed/expired results stay explicit and never invent candidates', async () => {
  for (const result of [null, { status: 'FAILED' }, { status: 'UNKNOWN', candidates: [], request_id: 'r' }]) {
    const { page, calls } = setup({ result }); await page.onLoad()
    assert.equal(page.data.preview, null); assert.equal(page.data.candidates.length, 0); assert.equal(calls.length, 0)
    if (result && result.status === 'UNKNOWN') assert.equal(page.data.feedbackOpen, true)
    else assert.ok(page.data.error)
  }
})
test('markup uses bounded mini buttons and avoids unbacked video, sales, ratings or confident claims', () => {
  assert.ok([...markup.matchAll(/<button\b([^>]*)>/g)].every(match => /size="mini"/.test(match[1])))
  assert.match(markup, /不代表准确率/)
  assert.match(markup, /disabled="{{!selected \|\| busy}}"/)
  assert.doesNotMatch(markup, /<video\b|96\.8%|月销|评分|满30减5|置信度/)
})
