// SHARE-01 / USER-01 / DESIGN-01: real page handlers, fake transport/clock only.
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const helpers = require('../utils/helpers')
const { renderPoster } = require('./poster-visual.cjs')
const plain = value => JSON.parse(JSON.stringify(value))
const event = (key, value) => ({ currentTarget: { dataset: { [key]: value } } })
const error = code => Object.assign(new Error('PRIVATE SERVER DETAIL: never display'), { code })
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const settle = async () => { for (let i = 0; i < 25; i++) await Promise.resolve() }
const glyphs = () => ['a', 'b', 'c', 'd'].map(id => ({ id, cn_name: '字' + id, status: 'published', image_url: '/media/' + id + '.png' }))
function harness(options = {}) {
  let page, time = 1000, sequence = 0
  const timers = new Map(), requests = [], calls = [], updates = [], toasts = [], modals = [], previews = [], tracks = [], menus = []
  const api = {
    collection: async () => glyphs(), all: async () => [], request: async () => ({ id: 'job-1', status: 'queued' }),
    mediaUrl: value => value ? 'https://fixture.invalid' + value : '',
    ...options.api
  }
  for (const name of ['collection', 'all', 'request']) {
    const implementation = api[name]
    api[name] = (...args) => { requests.push({ name, args: plain(args) }); return implementation(...args) }
  }
  api.track = (...args) => tracks.push(args)
  const defaults = async (name, args) => {
    if (name === 'downloadFile') return { statusCode: 200, tempFilePath: '/tmp/actual.png' }
    if (name === 'getImageInfo') return { type: 'png', width: 960, height: 1440 }
    if (name === 'saveImageToPhotosAlbum') return {}
    throw new Error('Unexpected platform call ' + name + JSON.stringify(args))
  }
  const platform = {
    call: async (name, args) => { calls.push({ name, args }); return options.call ? options.call(name, args, defaults) : defaults(name, args) },
    privacy: async () => { calls.push({ name: 'privacy' }); if (options.privacy) await options.privacy() },
    openSettings: async () => { calls.push({ name: 'openSettings' }) }
  }
  class Clock extends Date { static now() { return time } }
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../pages/poster/index.js'), 'utf8'), {
    Page: definition => { page = definition }, Date: Clock,
    require: name => name.endsWith('/api') ? api : name.endsWith('/helpers') ? helpers : platform,
    setTimeout: (callback, ms) => { const id = ++sequence; timers.set(id, { callback, at: time + ms, ms }); return id },
    clearTimeout: id => timers.delete(id),
    wx: {
      showToast: value => toasts.push(value), showModal: value => modals.push(value), previewImage: value => previews.push(value),
      hideShareMenu: () => menus.push('hide'), showShareMenu: value => menus.push(plain(value))
    }
  })
  page.setData = data => { updates.push(plain(data)); Object.assign(page.data, data) }
  return {
    page, timers, requests, calls, updates, toasts, modals, previews, tracks, menus,
    start: async initial => { await page.onLoad(initial || {}); return page },
    tick: async ms => {
      time += ms
      for (const [id, task] of [...timers]) if (task.at <= time) { timers.delete(id); task.callback() }
      await settle()
    },
    jobs: () => requests.filter(item => item.name === 'request' && item.args[0].startsWith('/share/'))
  }
}
async function selected(options, ids = ['c', 'a', 'b']) {
  const h = harness(options); await h.start()
  ids.forEach(id => h.page.toggle(event('id', id)))
  return h
}
const completed = (more = {}) => ({ id: 'job-1', status: 'completed', url: '/media/art.png', share_code_available: true, ...more })

test('loads authorized favorites/history, only confirmed published details, no arbitrary deep-link selection', async () => {
  const h = harness({ api: {
    collection: async () => [...glyphs(), { id: 'hidden', status: 'draft', image_url: '/x.png' }],
    all: async () => [{ confirmed_character_id: 'e' }, { confirmed_character_id: 'e' }, { confirmed_character_id: 'a' }, { predicted_character_id: 'unconfirmed' }, { confirmed_character_id: 'gone' }],
    request: async url => url.endsWith('gone') ? Promise.reject(error('CHARACTER_NOT_FOUND')) : { id: 'e', image_url: '/e.png', status: 'published' }
  } })
  await h.start({ character_id: 'unconfirmed' })
  assert.deepEqual(h.requests.slice(0, 2).map(r => r.args), [['/me/favorites', {}, true], ['/me/history', {}, true]])
  assert.deepEqual(h.requests.filter(r => r.name === 'request').map(r => r.args[0]), ['/characters/e', '/characters/gone'])
  assert.deepEqual(plain(h.page.data.items.map(i => i.id)), ['a', 'b', 'c', 'd', 'e'])
  assert.deepEqual(plain(h.page.data.selected), [])
  assert.equal(h.page.data.loading, false)
})
test('approved initial character selects exactly one; missing images cannot be selected', async () => {
  const h = harness({ api: { collection: async () => [...glyphs(), { id: 'missing', status: 'published' }] } })
  await h.start({ character_id: 'b' })
  h.page.toggle(event('id', 'missing')); h.page.toggle(event('id', 'forged'))
  assert.deepEqual(plain(h.page.data.selected), ['b'])
})
test('authorization failure produces unavailable state without exposing backend messages', async () => {
  const h = harness({ api: { collection: async () => { throw error('AUTH_REQUIRED') } } })
  await h.start()
  assert.match(h.page.data.loadError, /请先登录/)
  assert.equal(h.page.data.items.length, 0)
  assert.doesNotMatch(renderPoster(h.page.data), /PRIVATE|generate-button/)
})
test('history detail network failure is not silently treated as removed content', async () => {
  const h = harness({ api: { all: async () => [{ confirmed_character_id: 'e' }], request: async () => { throw error('NETWORK_ERROR') } } })
  await h.start()
  assert.match(h.page.data.loadError, /网络/)
})
test('selection, removal, re-addition and actual WXML preserve click order rather than gallery order', async () => {
  const h = await selected()
  assert.deepEqual(plain(h.page.data.selectedItems.map(i => i.id)), ['c', 'a', 'b'])
  h.page.toggle(event('id', 'd'))
  assert.equal(h.page.data.selected.length, 3)
  assert.match(h.toasts.at(-1).title, /最多/)
  h.page.toggle(event('id', 'a')); h.page.toggle(event('id', 'a'))
  assert.deepEqual(plain(h.page.data.selected), ['c', 'b', 'a'])
  assert.deepEqual(plain(h.page.data.selectedItems.map(i => i.order)), [1, 2, 3])
  const html = renderPoster(h.page.data)
  const selectedIds = [...html.matchAll(/class="selected-glyph" data-id="([^"]+)"/g)].map(m => m[1])
  assert.deepEqual(selectedIds, ['c', 'b', 'a'])
  const draft = html.slice(html.indexOf('class="draft-glyphs"'))
  assert.ok(draft.indexOf('字c') < draft.indexOf('字b') && draft.indexOf('字b') < draft.indexOf('字a'))
})
test('caption handler limits Chinese and supplementary characters to 50; WXML enforces maxlength', async () => {
  const h = await selected()
  assert.equal(h.page.captionInput({ detail: { value: '文'.repeat(60) } }), '文'.repeat(50))
  assert.equal(h.page.data.captionLength, 50)
  const emoji = h.page.captionInput({ detail: { value: '🌄'.repeat(51) } })
  assert.equal(Array.from(emoji).length, 50)
  assert.equal(h.page.data.captionLength, 50)
  assert.match(renderPoster(h.page.data), /maxlength="50"/)
  h.page.captionInput({ detail: { value: '' } })
  assert.equal(h.page.data.captionLength, 0)
})
test('caption swap cycles travel copy without deriving cultural meanings from glyphs', async () => {
  const h = await selected(), original = h.page.data.caption, seen = new Set()
  for (let n = 0; n < 4; n++) { h.page.swapCaption(); seen.add(h.page.data.caption); assert.ok(h.page.data.captionLength <= 50) }
  assert.equal(seen.size, 4); assert.equal(h.page.data.caption, original)
  assert.doesNotMatch([...seen].join(''), /坚守|守护|象征|寓意|字a|字b|字c/)
})
test('generate visibly normalizes newlines and whitespace exactly once and retries the normalized caption', async () => {
  let n = 0
  const h = await selected({ api: { request: async () => { if (++n === 1) throw error('NETWORK_ERROR'); return completed() } } })
  h.page.captionInput({ detail: { value: '  在丽江，\n\t收藏  时光\r\n里的\u3000美好。  ' } })
  await h.page.generate()
  const expected = '在丽江， 收藏 时光 里的 美好。'
  assert.equal(h.page.data.caption, expected); assert.equal(h.page.data.captionLength, Array.from(expected).length)
  assert.equal(h.jobs()[0].args[1].data.caption, expected)
  assert.ok(renderPoster(h.page.data).includes(expected))
  await h.page.generate(); assert.deepEqual(h.jobs()[0].args, h.jobs()[1].args)
  assert.equal(h.page.onShareAppMessage().title, expected)
})
test('whitespace-only caption visibly becomes empty, never an undisclosed replacement', async () => {
  const h = await selected(); h.page.captionInput({ detail: { value: '\n \t\u3000' } }); await h.page.generate()
  assert.equal(h.page.data.caption, ''); assert.equal(h.page.data.captionLength, 0); assert.equal(h.jobs()[0].args[1].data.caption, '')
})
test('four honest style options; invalid templates and same-value edits do not invalidate', async () => {
  const h = await selected()
  assert.deepEqual(plain(h.page.data.styles.map(s => s.id)), ['paper', 'mountain', 'old-town', 'minimal'])
  for (const style of h.page.data.styles) { h.page.template(event('template', style.id)); assert.equal(h.page.data.template, style.id) }
  h.page.setData({ image: 'kept' }); h.page.template(event('template', 'minimal')); h.page.template(event('template', 'invented'))
  h.page.captionInput({ detail: { value: h.page.data.caption } })
  assert.equal(h.page.data.image, 'kept')
  const html = renderPoster(h.page.data)
  assert.equal((html.match(/data-template=/g) || []).length, 4)
  assert.match(html, /风格意向 · 非成品预览/)
  const swatches = html.slice(html.indexOf('class="templates"'), html.indexOf('class="editor-section caption-section"'))
  assert.doesNotMatch(swatches, /<img/)
})
test('POST sends ordered IDs, exact caption/template and unique retry token with authorization', async () => {
  const h = await selected()
  h.page.template(event('template', 'old-town')); h.page.captionInput({ detail: { value: '这一程。' } })
  await h.page.generate()
  const [url, opts] = h.jobs()[0].args
  assert.equal(url, '/share/poster/jobs'); assert.equal(opts.method, 'POST'); assert.equal(opts.auth, true)
  assert.deepEqual(opts.data.character_ids, ['c', 'a', 'b']); assert.equal(opts.data.template, 'old-town'); assert.equal(opts.data.caption, '这一程。')
  assert.match(opts.data.request_id, /^poster-[a-z0-9-]+$/)
  assert.equal(h.page.data.status, 'queued'); assert.equal(h.timers.size, 1); assert.equal([...h.timers.values()][0].ms, 2000)
})
test('each style change clears the previous art and starts a new job with the selected style', async () => {
  const h = await selected({ api: { request: async () => completed() } })
  const styles = ['paper', 'mountain', 'old-town', 'minimal', 'paper']
  for (const style of styles) {
    h.page.template(event('template', style))
    assert.equal(h.page.data.image, '')
    await h.page.generate()
    assert.equal(h.page.data.status, 'completed')
    assert.ok(h.page.data.image)
  }
  const payloads = h.jobs().map(job => job.args[1].data)
  assert.deepEqual(payloads.map(value => value.template), styles)
  assert.equal(new Set(payloads.map(value => value.request_id)).size, styles.length)
})
test('queued/generating poll every two seconds, completed downloads and validates actual PNG', async () => {
  let n = 0
  const h = await selected({ api: { request: async () => [ { id: 'job-1', status: 'queued' }, { id: 'job-1', status: 'generating' }, completed() ][n++] } })
  await h.page.generate(); await h.tick(1999); assert.equal(h.jobs().length, 1)
  await h.tick(1); assert.equal(h.page.data.status, 'generating')
  await h.tick(2000)
  assert.equal(h.page.data.status, 'completed'); assert.equal(h.page.data.image, '/tmp/actual.png'); assert.equal(h.page.data.generating, false)
  assert.equal(h.page.data.shareCode, true); assert.equal(h.timers.size, 0)
  assert.deepEqual(h.jobs().slice(1).map(r => r.args), [['/share/poster/jobs/job-1', { auth: true }], ['/share/poster/jobs/job-1', { auth: true }]])
  assert.deepEqual(h.calls.map(c => c.name), ['downloadFile', 'getImageInfo'])
  assert.equal(h.calls[0].args.url, 'https://fixture.invalid/media/art.png')
  assert.deepEqual(h.menus.at(-1), { menus: ['shareAppMessage'] })
})
test('generating blocks every edit, reset, reload, save and duplicate POST handler', async () => {
  const wait = deferred()
  const h = await selected({ api: { request: () => wait.promise } }), before = plain(h.page.data)
  const pending = h.page.generate()
  h.page.toggle(event('id', 'c')); h.page.template(event('template', 'mountain')); h.page.captionInput({ detail: { value: 'changed' } }); h.page.swapCaption(); h.page.resetSelection()
  await h.page.load(); await h.page.save(); await h.page.generate()
  assert.deepEqual(plain(h.page.data.selected), before.selected); assert.equal(h.page.data.template, before.template); assert.equal(h.page.data.caption, before.caption)
  assert.equal(h.jobs().length, 1); assert.equal(h.calls.length, 0)
  const html = renderPoster(h.page.data)
  assert.match(html, /<textarea[^>]*disabled/)
  assert.ok([...html.matchAll(/<button[^>]+>/g)].every(m => /disabled/.test(m[0])))
  wait.resolve({ id: 'job-1', status: 'queued' }); await pending
})
test('no selection never submits; draft cannot preview, save, or expose share button', async () => {
  const h = harness(); await h.start(); await h.page.generate(); await h.page.save(); h.page.preview()
  assert.equal(h.jobs().length, 0); assert.equal(h.calls.length, 0); assert.equal(h.previews.length, 0)
  const html = renderPoster(h.page.data)
  assert.match(html, /本地草稿/); assert.match(html, /非生成作品/); assert.doesNotMatch(html, /open-type="share"|class="save-button"/)
  assert.equal(h.page.onShareAppMessage().imageUrl, undefined)
})
test('hide cancels timers; show resumes GET without creating another job', async () => {
  const h = await selected(); await h.page.generate(); h.page.onHide(); assert.equal(h.timers.size, 0)
  await h.tick(3000); assert.equal(h.jobs().length, 1)
  await h.page.onShow(); assert.equal(h.jobs().length, 2); assert.equal(h.jobs()[1].args[0], '/share/poster/jobs/job-1')
  assert.equal(h.timers.size, 1)
})
test('hide during POST stores completion but defers download until show', async () => {
  const wait = deferred(), h = await selected({ api: { request: () => wait.promise } })
  const pending = h.page.generate(); h.page.onHide(); wait.resolve(completed()); await pending
  assert.equal(h.calls.length, 0); assert.equal(h.timers.size, 0); assert.equal(h.page.data.status, 'downloading')
  await h.page.onShow(); assert.equal(h.page.data.image, '/tmp/actual.png'); assert.equal(h.jobs().length, 1)
})
test('hide/show during an in-flight GET does not run overlapping requests', async () => {
  const wait = deferred(); let n = 0
  const h = await selected({ api: { request: () => ++n === 1 ? { id: 'job-1', status: 'queued' } : wait.promise } })
  await h.page.generate(); await h.tick(2000); h.page.onHide(); await h.page.onShow()
  assert.equal(h.jobs().length, 2); wait.resolve({ id: 'job-1', status: 'generating' }); await settle()
  assert.equal(h.timers.size, 1)
})
test('unload cancels timers and ignores pending POST result without setData or download', async () => {
  const wait = deferred(), h = await selected({ api: { request: () => wait.promise } })
  const pending = h.page.generate(); h.page.onUnload(); const count = h.updates.length
  wait.resolve(completed()); await pending
  assert.equal(h.updates.length, count); assert.equal(h.calls.length, 0); assert.equal(h.timers.size, 0)
})
test('unload ignores pending download and never enables save/share', async () => {
  const wait = deferred(), h = await selected({ api: { request: async () => completed() }, call: (name, args, defaults) => name === 'downloadFile' ? wait.promise : defaults(name, args) })
  const pending = h.page.generate(); await settle(); h.page.onUnload(); const count = h.updates.length
  wait.resolve({ statusCode: 200, tempFilePath: '/tmp/late.png' }); await pending
  assert.equal(h.updates.length, count); assert.equal(h.page.data.image, ''); assert.equal(h.menus.at(-1), 'hide')
})
test('unload during personal list loading ignores late data', async () => {
  const wait = deferred(), h = harness({ api: { collection: () => wait.promise } })
  const pending = h.start(); h.page.onUnload(); const count = h.updates.length; wait.resolve(glyphs()); await pending
  assert.equal(h.updates.length, count)
})
test('five-minute bound stops polling and manual retry queries the same job', async () => {
  const h = await selected(); await h.page.generate(); await h.tick(300000)
  assert.equal(h.page.data.status, 'paused'); assert.equal(h.page.data.generating, false); assert.equal(h.timers.size, 0); assert.equal(h.jobs().length, 1)
  await h.page.generate(); assert.equal(h.jobs().length, 2); assert.equal(h.jobs()[1].args[0], '/share/poster/jobs/job-1')
})
test('time spent hidden counts toward deadline; showing after five minutes cannot poll indefinitely', async () => {
  const h = await selected(); await h.page.generate(); h.page.onHide(); await h.tick(301000); await h.page.onShow()
  assert.equal(h.page.data.status, 'paused'); assert.equal(h.jobs().length, 1)
})
test('ambiguous POST failure retries identical payload/token, including caption and order', async () => {
  let n = 0
  const h = await selected({ api: { request: async () => { if (++n === 1) throw error('NETWORK_ERROR'); return { id: 'job-1', status: 'queued' } } } })
  await h.page.generate(); assert.equal(h.page.data.status, 'failed'); assert.match(h.page.data.error, /网络/)
  await h.page.generate(); assert.deepEqual(h.jobs()[0].args, h.jobs()[1].args)
})
test('GET failure retries same job; confirmed terminal failure offers explicit regeneration only', async () => {
  let n = 0
  const h = await selected({ api: { request: async () => { if (++n === 2) throw error('NETWORK_ERROR'); return n === 1 ? { id: 'job-1', status: 'queued' } : { id: 'job-1', status: 'failed', error_code: 'PROVIDER_NOT_CONFIGURED' } } } })
  await h.page.generate(); await h.tick(2000)
  assert.equal(h.page.data.terminalFailure, false)
  assert.match(renderPoster(h.page.data), /重试原任务/)
  await h.page.generate()
  assert.equal(h.jobs().filter(r => r.args[1].method === 'POST').length, 1)
  assert.match(h.page.data.error, /暂未开通/); assert.equal(h.page.data.image, ''); assert.equal(h.timers.size, 0)
  assert.equal(h.page.data.terminalFailure, true)
  const html = renderPoster(h.page.data)
  assert.match(html, />重新生成<\/button>/); assert.match(html, /可能产生费用/)
  await h.tick(300000); h.page.onHide(); await h.page.onShow()
  assert.equal(h.jobs().filter(r => r.args[1].method === 'POST').length, 1)
  const original = h.jobs()[0].args[1].data
  await h.page.generate()
  const replacement = h.jobs().filter(r => r.args[1].method === 'POST')[1].args[1].data
  assert.notEqual(replacement.request_id, original.request_id)
  assert.deepEqual(plain(replacement.character_ids), plain(original.character_ids))
  assert.equal(replacement.caption, original.caption)
})
test('terminal POST result requires an explicit new request; ambiguous replacement retry keeps its token', async () => {
  let n = 0
  const h = await selected({ api: { request: async () => {
    if (++n === 1) return { id: 'job-1', status: 'failed', error_code: 'IMAGE_PROVIDER_TIMEOUT' }
    if (n === 2) throw error('NETWORK_ERROR')
    return { id: 'job-2', status: 'queued' }
  } } })
  await h.page.generate(); assert.equal(h.page.data.terminalFailure, true)
  assert.doesNotMatch(h.page.data.error, /查询原任务/)
  await h.tick(300000); assert.equal(h.jobs().length, 1)
  await h.page.generate(); assert.equal(h.page.data.terminalFailure, false)
  await h.page.generate()
  const payloads = h.jobs().map(r => r.args[1].data)
  assert.notEqual(payloads[0].request_id, payloads[1].request_id)
  assert.deepEqual(plain(payloads[1]), plain(payloads[2]))
  assert.equal(h.page._attempt.jobId, 'job-2')
})
test('download retry fetches original result without POST or GET', async () => {
  let n = 0
  const h = await selected({ api: { request: async () => completed() }, call: (name, args, defaults) => name === 'downloadFile' && ++n === 1 ? Promise.reject(error('NETWORK_ERROR')) : defaults(name, args) })
  await h.page.generate(); assert.match(h.page.data.error, /只会下载原图/); assert.equal(h.page.data.image, '')
  await h.page.generate(); assert.equal(h.jobs().length, 1); assert.equal(h.page.data.image, '/tmp/actual.png')
})
test('cached loopback poster retries download over the real configured origin without a new job', async () => {
  const realApi = require('../utils/api'), config = require('../config')
  const media = '/api/v1/media/' + 'b'.repeat(32) + '.png'
  let downloads = 0
  const h = await selected({
    api: { request: async () => completed({ url: 'http://127.0.0.1:8010' + media }), mediaUrl: realApi.mediaUrl },
    call: (name, args, defaults) => name === 'downloadFile' && ++downloads === 1 ? Promise.reject(error('NETWORK_ERROR')) : defaults(name, args)
  })
  await h.page.generate()
  assert.match(h.page.data.error, /只会下载原图/)
  await h.page.generate()
  const calls = h.calls.filter(call => call.name === 'downloadFile')
  assert.equal(calls.length, 2)
  for (const call of calls) assert.equal(call.args.url, config.apiBase.replace(/\/api\/v1\/?$/, '') + media)
  assert.equal(h.jobs().length, 1)
  assert.equal(h.page.data.image, '/tmp/actual.png')
})
test('invalid downloaded images never become completed artwork', async () => {
  for (const invalid of [{ statusCode: 500 }, { statusCode: 200 }, { type: 'jpeg', width: 100, height: 100 }, { type: 'png', width: 0, height: 100 }]) {
    const h = await selected({ api: { request: async () => completed() }, call: (name, args, defaults) => (name === 'downloadFile' && 'statusCode' in invalid) || (name === 'getImageInfo' && 'type' in invalid) ? invalid : defaults(name, args) })
    await h.page.generate(); assert.equal(h.page.data.image, ''); assert.equal(h.page.data.status, 'failed'); assert.match(h.page.data.error, /下载失败/)
  }
})
test('malformed completed result or unknown state is unavailable, not a fabricated preview', async () => {
  for (const result of [completed({ url: '' }), { id: 'job-1', status: 'imagined' }, null]) {
    const h = await selected({ api: { request: async () => result } }); await h.page.generate()
    assert.equal(h.page.data.status, 'failed'); assert.equal(h.page.data.image, ''); assert.equal(h.calls.length, 0)
  }
})
test('unknown server errors do not leak internal text', async () => {
  const h = await selected({ api: { request: async () => { throw error('PRIVATE_CODE') } } }); await h.page.generate()
  assert.doesNotMatch(h.page.data.error, /PRIVATE|SERVER/)
})
test('missing poster reference preflight shows neutral guidance and retries the original request token', async () => {
  let attempts = 0
  const h = await selected({ api: { request: async () => {
    if (++attempts === 1) throw error('POSTER_REFERENCE_UNAVAILABLE')
    return completed()
  } } })
  await h.page.generate()
  assert.equal(h.page.data.error, '海报暂时无法制作，请稍后再试')
  assert.equal(h.page.data.image, ''); assert.equal(h.page.data.generating, false)
  const html = renderPoster(h.page.data)
  assert.match(html, /海报暂时无法制作，请稍后再试/)
  assert.doesNotMatch(html, /POSTER_REFERENCE_UNAVAILABLE|PRIVATE|参考图|AI\s*(?:辅助|生成)?\s*背景/i)
  const original = h.jobs()[0].args[1].data
  await h.page.generate()
  assert.equal(h.jobs().length, 2); assert.deepEqual(h.jobs()[1].args[1].data, original)
  assert.equal(h.page.data.status, 'completed'); assert.equal(h.page.data.image, '/tmp/actual.png')
})
test('all new provider job codes and request conflicts map to safe actionable copy', async () => {
  for (const code of ['IMAGE_PROVIDER_UNCONFIGURED', 'IMAGE_PROVIDER_AUTH_FAILED', 'IMAGE_PROVIDER_BUSY', 'IMAGE_PROVIDER_TIMEOUT', 'IMAGE_PROVIDER_UNAVAILABLE', 'IMAGE_PROVIDER_INVALID_RESPONSE', 'POSTER_REFERENCE_UNAVAILABLE', 'POSTER_REQUEST_CONFLICT', 'constructor']) {
    const h = await selected({ api: { request: async () => ({ id: 'job-1', status: 'failed', error_code: code }) } })
    await h.page.generate()
    assert.equal(typeof h.page.data.error, 'string'); assert.ok(h.page.data.error.length > 5)
    assert.doesNotMatch(h.page.data.error, /IMAGE_PROVIDER|POSTER_REFERENCE|PRIVATE|constructor/)
    if (code === 'IMAGE_PROVIDER_UNCONFIGURED') assert.match(h.page.data.error, /暂未开通/)
    if (code === 'POSTER_REFERENCE_UNAVAILABLE') assert.equal(h.page.data.error, '海报暂时无法制作，请稍后再试')
    if (code === 'POSTER_REQUEST_CONFLICT') assert.match(h.page.data.error, /修改/)
    assert.equal(h.page.data.generating, false); assert.equal(h.page._attempt.jobId, 'job-1')
  }
})
test('poll 401/403/404 and transient failures retain accepted job id and never create another billed job', async () => {
  for (const status of [401, 403, 404, 408, 503]) {
    let n = 0
    const h = await selected({ api: { request: async () => {
      if (++n === 1) return { id: 'job-1', status: 'queued' }
      if (n === 2) throw Object.assign(error('REQUEST_FAILED'), { status })
      return completed()
    } } })
    await h.page.generate(); await h.tick(2000)
    assert.equal(h.page.data.generating, false); assert.equal(h.page.data.status, 'failed'); assert.equal(h.page._attempt.jobId, 'job-1'); assert.equal(h.timers.size, 0)
    if (status === 401) assert.match(h.page.data.error, /登录/)
    if (status === 404) assert.match(h.page.data.error, /原任务/)
    await h.page.generate(); assert.equal(h.jobs().filter(r => r.args[1].method === 'POST').length, 1); assert.equal(h.page.data.status, 'completed')
  }
})
for (const shareCodeAvailable of [false, true]) {
  test(`completed preview/share omit implementation annotations (share code: ${shareCodeAvailable})`, async () => {
    const h = await selected({ api: { request: async () => completed({ share_code_available: shareCodeAvailable }) } }); await h.page.generate()
    assert.equal(h.page.data.shareCode, shareCodeAvailable)
    h.page.preview(); assert.deepEqual(plain(h.previews[0]), { current: '/tmp/actual.png', urls: ['/tmp/actual.png'] })
    const share = h.page.onShareAppMessage(); assert.equal(share.imageUrl, '/tmp/actual.png'); assert.equal(share.path, '/pages/character/index?id=c'); assert.equal(share.title, h.page.data.caption)
    const html = renderPoster(h.page.data); assert.doesNotMatch(html, /小程序码|二维码|AI\s*(?:辅助|生成)?\s*背景|code-note/i); assert.match(html, /open-type="share"/); assert.doesNotMatch(html.replace(/src="[^"]*"/g, ''), /class="draft-preview|微博|QQ|复制链接/)
    assert.match(html, /<button[^>]*class="preview-button"[^>]*data-handler="preview"><img/)
    assert.match(html, /class="save-button"[^>]*data-handler="save"/)
    await h.page.generate(); assert.equal(h.jobs().length, 1)
  })
}
test('every meaningful edit clears image/share code and retry identity, then creates a unique new request', async () => {
  for (const edit of [p => p.toggle(event('id', 'a')), p => p.template(event('template', 'mountain')), p => p.captionInput({ detail: { value: '新文案' } }), p => p.swapCaption()]) {
    const h = await selected({ api: { request: async () => completed() } }); await h.page.generate(); const token = h.jobs()[0].args[1].data.request_id
    edit(h.page)
    assert.equal(h.page.data.image, ''); assert.equal(h.page.data.shareCode, false); assert.equal(h.page.data.status, 'draft'); assert.equal(h.page._attempt, null); assert.equal(h.menus.at(-1), 'hide')
    await h.page.generate(); assert.notEqual(h.jobs()[1].args[1].data.request_id, token)
  }
})
test('clear resets both selected render lists and completed image, leaves caption editable', async () => {
  const h = await selected({ api: { request: async () => completed() } }); await h.page.generate(); h.page.resetSelection()
  assert.deepEqual(plain(h.page.data.selected), []); assert.deepEqual(plain(h.page.data.selectedItems), []); assert.ok(h.page.data.items.every(item => !item.selected && item.order === 0))
  assert.equal(h.page.data.image, ''); assert.equal(h.page.data.shareCode, false); assert.equal(h.page.data.status, 'draft')
  await h.page.generate(); assert.equal(h.jobs().length, 1)
})
test('save requests privacy, uses actual PNG, blocks duplicate save and edits until done', async () => {
  const wait = deferred(), h = await selected({ api: { request: async () => completed() }, call: (name, args, defaults) => name === 'saveImageToPhotosAlbum' ? wait.promise : defaults(name, args) })
  await h.page.generate(); const pending = h.page.save(); await settle()
  h.page.resetSelection(); h.page.swapCaption(); h.page.template(event('template', 'mountain')); await h.page.save()
  assert.equal(h.page.data.selected.length, 3); assert.equal(h.page.data.template, 'paper')
  assert.equal(h.calls.filter(c => c.name === 'saveImageToPhotosAlbum').length, 1)
  assert.equal(h.calls.find(c => c.name === 'saveImageToPhotosAlbum').args.filePath, '/tmp/actual.png')
  assert.equal(h.calls.at(-2).name, 'privacy'); wait.resolve({}); await pending
  assert.equal(h.page.data.saving, false); assert.equal(h.toasts.at(-1).title, '海报已保存')
})
test('denied album permission offers settings; cancellation is silent and does not track success', async () => {
  for (const reason of ['saveImageToPhotosAlbum:fail auth deny', 'saveImageToPhotosAlbum:fail cancel']) {
    const h = await selected({ api: { request: async () => completed() }, call: (name, args, defaults) => name === 'saveImageToPhotosAlbum' ? Promise.reject({ errMsg: reason }) : defaults(name, args) })
    await h.page.generate(); await h.page.save()
    assert.equal(h.tracks.length, 0); assert.equal(h.page.data.saving, false)
    if (reason.includes('deny')) { assert.equal(h.modals.length, 1); h.modals[0].success({ confirm: true }); assert.equal(h.calls.at(-1).name, 'openSettings') }
    else assert.equal(h.modals.length, 0)
  }
})
test('privacy refusal never attempts album write or claims save success', async () => {
  const h = await selected({ api: { request: async () => completed() }, privacy: async () => { throw error('PRIVACY_REQUIRED') } })
  await h.page.generate(); await h.page.save(); assert.equal(h.calls.filter(c => c.name === 'saveImageToPhotosAlbum').length, 0); assert.equal(h.tracks.length, 0)
})
test('unload during privacy prompt prevents saving and late setData', async () => {
  const wait = deferred(), h = await selected({ api: { request: async () => completed() }, privacy: () => wait.promise })
  await h.page.generate(); const pending = h.page.save(); h.page.onUnload(); const count = h.updates.length; wait.resolve(); await pending
  assert.equal(h.updates.length, count); assert.equal(h.calls.filter(c => c.name === 'saveImageToPhotosAlbum').length, 0)
})
