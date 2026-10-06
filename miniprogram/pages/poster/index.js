// SHARE-01 / USER-01 / DESIGN-01: approved glyphs and retry-safe artwork jobs.
const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
const platform = require('../../utils/platform')
const POLL_INTERVAL = 2000
const POLL_LIMIT = 5 * 60 * 1000
const captions = ['在丽江，收藏时光里的美好。', '把旅途的片刻，留在这一页。', '山水有相逢，此刻值得珍藏。', '这一程的喜欢，写成一张印记。']
const styles = [
  { id: 'paper', name: '东巴纸风', detail: '温润 · 纸色', mark: '纸' },
  { id: 'mountain', name: '雪山风', detail: '清远 · 青白', mark: '山' },
  { id: 'old-town', name: '古城风', detail: '暖调 · 古城', mark: '城' },
  { id: 'minimal', name: '简约风', detail: '留白 · 墨色', mark: '简' }
]
let requestSequence = 0
function requestToken() {
  requestSequence += 1
  return 'poster-' + Date.now().toString(36) + '-' + requestSequence.toString(36) + '-' + Math.random().toString(36).slice(2, 12)
}
function message(error) {
  const messages = {
    AUTH_REQUIRED: '请先登录，再来制作印记。', SESSION_EXPIRED: '登录已过期，请重新登录。',
    FORBIDDEN: '当前账号暂时无法制作海报。', ACCOUNT_UNAVAILABLE: '当前账号暂时不可用。',
    NETWORK_ERROR: '网络连接中断，请重试原任务。',
    CHARACTER_NOT_COLLECTED: '请选择已收藏或识别确认的东巴字。',
    CHARACTER_NOT_FOUND: '所选东巴字已下架，请重新选择。',
    CHARACTER_IMAGE_UNAVAILABLE: '所选东巴字暂缺字形图片，请换一个字。',
    DICTIONARY_NOT_READY: '已审核的字形暂未准备好，请稍后再来。',
    PROVIDER_NOT_CONFIGURED: '海报生成暂未开通，请稍后再来。',
    POSTER_NOT_CONFIGURED: '海报生成暂未开通，请稍后再来。',
    POSTER_PROVIDER_NOT_CONFIGURED: '海报生成暂未开通，请稍后再来。',
    IMAGE_PROVIDER_UNCONFIGURED: '海报生成暂未开通，请稍后再来。',
    IMAGE_PROVIDER_AUTH_FAILED: '海报生成暂时不可用，请稍后再来。',
    IMAGE_PROVIDER_BUSY: '海报制作较忙，请稍后重试原任务。',
    IMAGE_PROVIDER_TIMEOUT: '海报生成超时，请查询原任务，或修改内容后重新制作。',
    IMAGE_PROVIDER_UNAVAILABLE: '海报生成暂时不可用，请稍后再试。',
    IMAGE_PROVIDER_INVALID_RESPONSE: '暂未取得可用海报，请查询原任务，或修改内容后重新制作。',
    PROVIDER_UNAVAILABLE: '海报生成暂时不可用，请稍后再试。',
    PROVIDER_TIMEOUT: '海报生成用时较长，请稍后查询原任务。',
    POSTER_FONT_UNAVAILABLE: '海报生成暂时不可用，请稍后再试。',
    POSTER_REFERENCE_UNAVAILABLE: '海报暂时无法制作，请稍后再试',
    POSTER_BACKGROUND_UNAVAILABLE: '此风格暂时不可用，请换一种风格。',
    RATE_LIMITED: '操作有些频繁，请稍后再试。',
    INVALID_REQUEST: '请检查选字和文案后重试。',
    REQUEST_ID_CONFLICT: '此任务内容已变化，请修改后重新制作。',
    POSTER_REQUEST_CONFLICT: '此任务内容已变化，请修改后重新制作。',
    NOT_FOUND: '原任务暂时无法查询，请稍后再试。',
    POSTER_JOB_NOT_FOUND: '原任务暂时无法查询，请稍后再试。',
    IMAGE_DOWNLOAD_FAILED: '海报已生成，图片下载失败。重试只会下载原图。',
    INVALID_JOB: '暂未取得海报结果，请重试原任务。'
  }
  if (error && Object.prototype.hasOwnProperty.call(messages, error.code)) return messages[error.code]
  if (error && error.status === 401) return messages.AUTH_REQUIRED
  if (error && error.status === 403) return messages.FORBIDDEN
  if (error && error.status === 404) return messages.POSTER_JOB_NOT_FOUND
  return '海报暂未完成，请稍后查询原任务，或修改内容后重新制作。'
}
function jobError(code) { return Object.assign(new Error(), { code }) }

Page({
  data: {
    loading: true, loadError: '', error: '', items: [], selected: [], selectedItems: [],
    styles, template: 'paper', caption: captions[0], captionLength: Array.from(captions[0]).length,
    image: '', generating: false, saving: false, shareCode: false, status: 'draft', canRetry: false, terminalFailure: false
  },
  onLoad(options) {
    this._disposed = false
    this._visible = true
    this._epoch = 0
    this.initialId = (options || {}).character_id
    if (wx.hideShareMenu) wx.hideShareMenu()
    return this.load()
  },
  onShow() {
    this._visible = true
    if (this._attempt && this.data.generating && !this._busy) return this.runAttempt()
  },
  onHide() { this._visible = false; this.clearPoll() },
  onUnload() { this._disposed = true; this._visible = false; this._epoch += 1; this.clearPoll() },
  clearPoll() {
    if (this._timer != null) clearTimeout(this._timer)
    this._timer = null
  },
  async load() {
    if (this.data.generating || this.data.saving) return
    this.invalidate()
    const epoch = this._epoch
    this.setData({ loading: true, loadError: '', items: [], selected: [], selectedItems: [] })
    try {
      // Both personal lists stay authenticated; public details expose published entries only.
      const [favorites, history] = await Promise.all([api.collection('/me/favorites', {}, true), api.all('/me/history', {}, true)])
      const existing = new Set(favorites.map(helpers.identifier))
      const ids = Array.from(new Set(history.map(value => value.confirmed_character_id).filter(Boolean))).filter(id => !existing.has(id))
      const details = await Promise.all(ids.map(id => api.request('/characters/' + encodeURIComponent(id)).catch(error => {
        if (error.status === 404 || error.code === 'CHARACTER_NOT_FOUND' || error.code === 'NOT_FOUND') return null
        throw error
      })))
      if (this._disposed || epoch !== this._epoch) return
      const items = helpers.uniqueCharacters(favorites.concat(details.filter(Boolean)))
        .filter(value => !value.status || value.status === 'published')
        .map(value => Object.assign({}, value, { image_url: api.mediaUrl(value.image_url), selectable: !!api.mediaUrl(value.image_url) }))
      const selected = this.initialId && items.some(value => value.id === this.initialId && value.image_url) ? [this.initialId] : []
      this.initialId = null
      this.setData({ items })
      this.setSelection(selected)
    } catch (error) {
      if (!this._disposed && epoch === this._epoch) this.setData({ loadError: error.code === 'NETWORK_ERROR' ? '暂时无法加载已收藏的字，请检查网络后重试。' : message(error) })
    } finally {
      if (!this._disposed && epoch === this._epoch) this.setData({ loading: false })
    }
  },
  invalidate() {
    this.clearPoll()
    this._epoch = (this._epoch || 0) + 1
    this._attempt = null
    this.setData({ image: '', shareCode: false, status: 'draft', error: '', canRetry: false, terminalFailure: false })
    if (wx.hideShareMenu) wx.hideShareMenu()
  },
  setSelection(selected) {
    const items = this.data.items.map(item => Object.assign({}, item, { selected: selected.includes(item.id), order: selected.indexOf(item.id) + 1 }))
    // A gallery filter would silently change the user's order.
    const selectedItems = selected.map(id => items.find(item => item.id === id)).filter(Boolean)
    this.setData({ selected, selectedItems, items })
  },
  toggle(event) {
    if (this.data.generating || this.data.saving) return
    const id = event.currentTarget.dataset.id
    if (!this.data.items.some(item => item.id === id && item.selectable !== false)) return
    const selected = this.data.selected.slice()
    const index = selected.indexOf(id)
    if (index >= 0) selected.splice(index, 1)
    else if (selected.length < 3) selected.push(id)
    else { wx.showToast({ title: '最多选择 3 个东巴字', icon: 'none' }); return }
    this.invalidate()
    this.setSelection(selected)
  },
  resetSelection() {
    if (this.data.generating || this.data.saving || !this.data.selected.length) return
    this.invalidate()
    this.setSelection([])
  },
  template(event) {
    const template = event.currentTarget.dataset.template
    if (this.data.generating || this.data.saving || template === this.data.template || !styles.some(style => style.id === template)) return
    this.invalidate()
    this.setData({ template })
  },
  captionInput(event) {
    if (this.data.generating || this.data.saving) return this.data.caption
    const caption = Array.from(String(event.detail.value || '')).slice(0, 50).join('')
    if (caption !== this.data.caption) {
      this.invalidate()
      this.setData({ caption, captionLength: Array.from(caption).length })
    }
    return caption
  },
  swapCaption() {
    if (this.data.generating || this.data.saving) return
    const next = (captions.indexOf(this.data.caption) + 1) % captions.length
    this.captionInput({ detail: { value: captions[next] } })
  },
  generate() {
    if (this.data.generating || this.data.saving || this.data.loading || this.data.image || !this.data.selected.length || this.data.selected.length > 3) return
    // Only the explicit “重新生成” action replaces a confirmed terminal job.
    // Network/HTTP failures never set this flag and always keep their accepted ID/token.
    if (this._attempt && this._attempt.terminalFailure) this._attempt = null
    // Match the server's whitespace normalization, visibly, before freezing the job payload.
    const caption = this._attempt ? this._attempt.payload.caption : Array.from(this.data.caption.replace(/\s+/g, ' ').trim()).slice(0, 50).join('')
    this.setData({ caption, captionLength: Array.from(caption).length })
    if (!this._attempt) {
      this._attempt = {
        payload: { character_ids: this.data.selected.slice(), template: this.data.template, caption, request_id: requestToken() },
        jobId: '', result: null
      }
    }
    // Transient retry keeps the exact payload/token or GETs the accepted job.
    this._deadline = Date.now() + POLL_LIMIT
    this.setData({ generating: true, error: '', canRetry: false, terminalFailure: false, status: this._attempt.result ? 'downloading' : 'submitting' })
    return this.runAttempt()
  },
  schedulePoll() {
    this.clearPoll()
    if (this._disposed || !this._visible || !this.data.generating) return
    if (Date.now() >= this._deadline) { this.pauseAttempt(); return }
    this._timer = setTimeout(() => { this._timer = null; this.runAttempt() }, Math.min(POLL_INTERVAL, this._deadline - Date.now()))
  },
  pauseAttempt() {
    this.clearPoll()
    this.setData({ generating: false, status: 'paused', canRetry: true, error: '等待已超过五分钟。可继续查询原任务，无需重新生成。' })
  },
  async runAttempt() {
    if (this._disposed || !this._visible || this._busy || !this._attempt) return
    if (Date.now() >= this._deadline) { this.pauseAttempt(); return }
    const attempt = this._attempt, epoch = this._epoch
    const current = () => !this._disposed && epoch === this._epoch && this._attempt === attempt
    this._busy = true
    try {
      let result = attempt.result
      if (!result) {
        result = attempt.jobId
          ? await api.request('/share/poster/jobs/' + encodeURIComponent(attempt.jobId), { auth: true })
          : await api.request('/share/poster/jobs', { method: 'POST', auth: true, data: attempt.payload })
      }
      if (!current()) return
      if (!result || !result.id || !['queued', 'generating', 'completed', 'failed'].includes(result.status) || (attempt.jobId && attempt.jobId !== result.id)) throw jobError('INVALID_JOB')
      attempt.jobId = result.id
      if (result.status === 'failed') { attempt.terminalFailure = true; throw jobError(result.error_code) }
      if (result.status === 'completed') {
        if (!result.url) throw jobError('INVALID_JOB')
        attempt.result = result
        this.setData({ status: 'downloading' })
        if (!this._visible) return
        const image = await this.download(result.url)
        if (!current()) return
        this.clearPoll()
        this.setData({ image, shareCode: result.share_code_available === true, generating: false, status: 'completed', error: '', canRetry: false })
        if (wx.showShareMenu) wx.showShareMenu({ menus: ['shareAppMessage'] })
      } else {
        this.setData({ status: result.status })
        this.schedulePoll()
      }
    } catch (error) {
      if (current()) {
        this.clearPoll()
        const terminalFailure = attempt.terminalFailure === true
        let explanation = message(error)
        if (terminalFailure) explanation = explanation.replace('请稍后重试原任务', '可稍后重新生成').replace('请查询原任务，或修改内容后重新制作', '可稍后重新生成').replace('请稍后查询原任务，或修改内容后重新制作', '可稍后重新生成').replace('请稍后查询原任务', '可稍后重新生成')
        this.setData({ generating: false, status: 'failed', error: explanation, canRetry: true, terminalFailure })
      }
    } finally { this._busy = false }
  },
  async download(url) {
    try {
      const result = await platform.call('downloadFile', { url: api.mediaUrl(url) })
      if (result.statusCode !== 200 || !result.tempFilePath) throw jobError('IMAGE_DOWNLOAD_FAILED')
      // A 200 can contain an HTML error. Require an actual decodable PNG before exposing save/share.
      const info = await platform.call('getImageInfo', { src: result.tempFilePath })
      if (String(info.type).toLowerCase() !== 'png' || !(info.width > 0 && info.height > 0)) throw jobError('IMAGE_DOWNLOAD_FAILED')
      return result.tempFilePath
    } catch (_) { throw jobError('IMAGE_DOWNLOAD_FAILED') }
  },
  preview() { if (this.data.image) wx.previewImage({ current: this.data.image, urls: [this.data.image] }) },
  async save() {
    if (!this.data.image || this.data.saving || this.data.generating) return
    const image = this.data.image
    this.setData({ saving: true })
    try {
      await platform.privacy()
      if (this._disposed) return
      await platform.call('saveImageToPhotosAlbum', { filePath: image })
      if (this._disposed) return
      wx.showToast({ title: '海报已保存' })
      api.track('share', { entity_type: 'characters', entity_id: this.data.selected[0] })
    } catch (error) {
      if (!this._disposed && !/cancel/i.test(error.errMsg || '')) {
        if (/auth|deny|denied|permission/i.test(error.errMsg || '')) {
          wx.showModal({ title: '需要相册权限', content: '允许保存到相册后，即可收藏这张海报。', confirmText: '打开设置', success: result => {
            if (result.confirm && !this._disposed) platform.openSettings().catch(() => wx.showToast({ title: '暂时无法打开设置', icon: 'none' }))
          } })
        } else wx.showToast({ title: '未能保存，请确认隐私授权后重试', icon: 'none' })
      }
    } finally { if (!this._disposed) this.setData({ saving: false }) }
  },
  onShareAppMessage() {
    if (!this.data.image) return { title: '东巴寻迹 · 丽江', path: '/pages/home/index' }
    const id = this.data.selected[0]
    api.track('share', { entity_type: 'characters', entity_id: id })
    return { title: this.data.caption || '我的东巴印记 · 丽江', path: '/pages/character/index?id=' + encodeURIComponent(id), imageUrl: this.data.image }
  }
})
