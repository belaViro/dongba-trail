const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const vm = require('node:vm')
const fs = require('node:fs')
let storage, sent, response, app
global.wx = {
  getStorageSync(key) { return storage[key] },
  setStorageSync(key, value) { storage[key] = value },
  removeStorageSync(key) { delete storage[key] },
  setClipboardData(options) { storage.clipboard = options.data },
  request(options) { sent.push(options); options.success(typeof response === 'function' ? response(options) : response) },
  uploadFile(options) { sent.push(options); options.success({ statusCode: response.statusCode, data: JSON.stringify(response.data) }) },
  navigateTo() {}, navigateBack() {}, redirectTo() {}, showToast() {}, showModal() {}
}
const session = require('../utils/session')
const api = require('../utils/api')
function page(name) {
  let definition
  const filename = path.resolve(__dirname, '../pages/' + name + '/index.js')
  vm.runInNewContext(fs.readFileSync(filename, 'utf8'), {
    require(id) { return require(path.resolve(path.dirname(filename), id)) },
    Page(value) { definition = value }, wx: global.wx, getApp() { return app }, console, Set, Map
  }, { filename })
  definition.data = JSON.parse(JSON.stringify(definition.data))
  definition.setData = value => Object.assign(definition.data, value)
  return definition
}
test.beforeEach(() => {
  storage = {}; sent = []; response = { statusCode: 200, data: {} }
  app = { globalData: { recognition: null, recognitionImage: '' } }
  session.clear()
})
test('protected actions cannot send unauthenticated requests or fake a login', async () => {
  await assert.rejects(api.request('/me/coupons', { auth: true }), error => error.code === 'AUTH_REQUIRED')
  await assert.rejects(api.upload('/tmp/real-photo.png', 'camera'), error => error.code === 'AUTH_REQUIRED')
  assert.equal(sent.length, 0)
})
test('authenticated requests and uploads carry bearer token and image scene', async () => {
  session.save({ access_token: 'test-only-token', user: { id: 'U' } })
  await api.request('/me/favorites', { auth: true })
  await api.upload('/tmp/real-photo.png', 'album')
  assert.equal(sent[0].header.Authorization, 'Bearer test-only-token')
  assert.equal(sent[1].header.Authorization, 'Bearer test-only-token')
  assert.equal(sent[1].name, 'image')
  assert.equal(sent[1].formData.scene, 'album')
})
test('server login expiry clears local identity and retains diagnostic request ID', async () => {
  session.save({ access_token: 'test-only-token', user: { id: 'U' } })
  response = { statusCode: 401, data: { code: 'SESSION_EXPIRED', request_id: 'trace-123' } }
  await assert.rejects(api.request('/auth/me'), error => error.code === 'SESSION_EXPIRED' && error.requestId === 'trace-123')
  assert.equal(session.get(), null)
  assert.equal(storage.dongba_session, undefined)
})
test('unconfigured recognition is explicit and never produces fabricated candidates', async () => {
  session.save({ access_token: 'test-only-token', user: { id: 'U' } })
  response = { statusCode: 503, data: { code: 'PROVIDER_NOT_CONFIGURED', request_id: 'trace-ai' } }
  await assert.rejects(api.upload('/tmp/image.png', 'camera'), error => error.message.includes('暂未开通') && error.requestId === 'trace-ai')
})
test('none-of-the-above feedback sends no invented character ID', async () => {
  session.save({ access_token: 'test-only-token', user: { id: 'U' } })
  const result = page('result')
  result.data.result = { request_id: 'R-real-request' }
  await result.submit({ currentTarget: { dataset: { unknown: true } } })
  assert.equal(sent[0].url.endsWith('/recognize/R-real-request/confirm'), true)
  assert.equal(sent[0].data.character_id, null)
  assert.ok(sent[0].data.comment.length)
  assert.equal(result.data.submitted, true)
})
test('generic camera entry clears stale quest recognition context', () => {
  app.globalData.activeQuest = { quest_id: 'Q-old', node_id: 'N-old' }
  const camera = page('camera')
  camera.onLoad({})
  assert.equal(app.globalData.activeQuest, null)
  camera.onLoad({ quest: 'Q-next', node: 'N-next' })
  assert.equal(app.globalData.activeQuest.quest_id, 'Q-next')
})
test('candidate confirmation supplies a string comment accepted by the server schema', async () => {
  session.save({ access_token: 'test-only-token', user: { id: 'U' } })
  const result = page('result')
  result.data.result = { request_id: 'R-request' }; result.data.selected = 'DB1'
  await result.submit({ currentTarget: { dataset: {} } })
  assert.equal(sent[0].data.character_id, 'DB1')
  assert.equal(sent[0].data.comment, '')
})
test('unpublished privacy policy cannot trigger wx.login', async () => {
  const login = page('login')
  login.data.accepted = true; login.data.policy = { published: false }
  let calls = 0
  wx.login = () => { calls += 1 }
  await login.login()
  assert.equal(calls, 0)
  assert.equal(sent.length, 0)
})
test('poster selection cannot exceed three user-owned characters', () => {
  const poster = page('poster')
  poster.data.items = ['A','B','C','D'].map(id => ({ id }))
  for (const id of ['A','B','C','D']) poster.toggle({ currentTarget: { dataset: { id } } })
  assert.equal(poster.data.selected.length, 3)
  assert.equal(poster.data.selected.includes('D'), false)
})
test('history beyond one API page remains accessible with correct offsets', async () => {
  session.save({ access_token: 'test-only-token', user: { id: 'U' } })
  response = options => {
    const offset = Number(new URL(options.url).searchParams.get('offset'))
    return { statusCode: 200, data: { items: Array.from({ length: offset === 0 ? 100 : 23 }, (_, index) => ({ request_id: 'R' + (offset + index) })), total: 123 } }
  }
  const history = await api.all('/me/history', {}, true)
  assert.equal(history.length, 123)
  assert.equal(history[122].request_id, 'R122')
  assert.equal(sent.length, 2)
  assert.equal(new URL(sent[1].url).searchParams.get('offset'), '100')
})
test('failed recognition history opens a retake dialog instead of candidate confirmation', () => {
  const history = page('history')
  history.data.items = [{ request_id: 'FAILED-R', status: 'FAILED', error_code: 'PROVIDER_NOT_CONFIGURED' }]
  let modal
  const original = wx.showModal
  wx.showModal = value => { modal = value }
  try { history.detail({ currentTarget: { dataset: { id: 'FAILED-R' } } }) }
  finally { wx.showModal = original }
  assert.ok(modal.content.includes('暂未开通'))
  assert.equal(app.globalData.recognition, null)
})
test('retake from historical result navigates to camera', () => {
  const result = page('result')
  let destination
  const original = wx.redirectTo
  wx.redirectTo = value => { destination = value.url }
  try { result.retake() } finally { wx.redirectTo = original }
  assert.equal(destination, '/pages/camera/index')
})
test('private favorites clear cached data when the user is no longer authenticated', async () => {
  const favorites = page('favorites')
  favorites.data.items = [{ id: 'old-user-private-favorite' }]
  await favorites.load()
  assert.equal(favorites.data.items.length, 0)
  assert.ok(favorites.data.error)
})
test('closed published route fallback preserves enrolled progress and pending reward', async () => {
  session.save({ access_token: 'test-only-token', user: { id: 'U' } })
  response = options => options.url.includes('/me/quests') ? {
    statusCode: 200, data: { items: [{ id: 'Q', quest_id: 'Q', name: 'Existing route', status: 'completed', completed_node_ids: ['N'], reward_pending: true, nodes: [{ id: 'N', condition: 'manual', sequence: 1 }] }], total: 1 }
  } : { statusCode: 404, data: { code: 'NOT_FOUND' } }
  const quest = page('quest'); quest.questId = 'Q'
  await quest.load()
  assert.equal(quest.data.error, '')
  assert.equal(quest.data.completed, 1)
  assert.equal(quest.data.closed, true)
  assert.equal(quest.data.progress.reward_pending, true)
})

test('profile copies the current session ID and cannot copy a logged-out cached user', () => {
  session.save({ access_token: 'test-only-token', user: { id: 'CURRENT-U' } })
  const profile = page('profile'); profile.data.user = { id: 'STALE-U' }
  profile.copyUserId()
  assert.equal(storage.clipboard, 'CURRENT-U')
  session.clear(); delete storage.clipboard
  profile.copyUserId()
  assert.equal(storage.clipboard, undefined)
})

test('manual quest dialog exposes and copies the current tourist ID', async () => {
  session.save({ access_token: 'test-only-token', user: { id: 'CURRENT-U' } })
  const quest = page('quest'); quest.data.progress = {}; quest.data.nodes = [{ id: 'MANUAL-N', condition: 'manual' }]
  let modal
  const original = wx.showModal
  wx.showModal = value => { modal = value }
  try { await quest.checkin({ currentTarget: { dataset: { id: 'MANUAL-N' } } }) }
  finally { wx.showModal = original }
  assert.ok(modal.content.includes('CURRENT-U'))
  assert.equal(modal.confirmText, '复制编号')
  modal.success({ confirm: true })
  assert.equal(storage.clipboard, 'CURRENT-U')
  session.clear(); delete storage.clipboard
  modal.success({ confirm: true })
  assert.equal(storage.clipboard, undefined)
})

test('culture audio plays, pauses, handles completion and is destroyed on page exit', () => {
  const character = page('character')
  const calls = [], callbacks = {}
  const context = {
    play() { calls.push('play') }, pause() { calls.push('pause') }, destroy() { calls.push('destroy') },
    onEnded(callback) { callbacks.ended = callback }, onError(callback) { callbacks.error = callback }
  }
  const original = wx.createInnerAudioContext
  wx.createInnerAudioContext = () => { calls.push('create'); return context }
  try {
    character.onUnload(); character.audio()
    assert.equal(calls.length, 0)
    character.data.item = { audio_url: 'https://approved.example/culture.mp3' }
    character.audio(); assert.equal(character.data.playing, true)
    character.audio(); assert.equal(character.data.playing, false)
    character.audio(); callbacks.ended(); assert.equal(character.data.playing, false)
    character.audio(); callbacks.error(); assert.equal(character.data.playing, false)
    assert.equal(context.src, character.data.item.audio_url)
    character.onUnload(); character.onUnload()
    assert.deepEqual(calls, ['create', 'play', 'pause', 'play', 'play', 'destroy'])
    assert.equal(typeof character.audio, 'function')
  } finally { wx.createInnerAudioContext = original }
})
