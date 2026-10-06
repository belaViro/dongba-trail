const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
const session = require('../../utils/session')
Page({
  data: { result: null, image: '', candidates: [], selected: '', busy: false, error: '', comment: '', submitted: false, attachImage: false, preview: null, previewLoading: false, previewError: '', merchants: [], merchantsLoading: false, merchantsError: '', saved: false, favoriteBusy: false, favoriteLoading: false, favoriteError: '', playing: false, feedbackOpen: false },
  async onLoad() {
    this._unloaded = false; this._previewSequence = 0; this._details = new Map()
    const app = getApp(); const result = app.globalData.recognition
    if (!result) { this.setData({ error: '识别结果已失效，请重新拍摄' }); return }
    if (result.status === 'FAILED') { this.setData({ error: api.errorFrom(503, { code: result.error_code }).message }); return }
    const candidates = helpers.uniqueCharacters(result.candidates || []).slice(0,5).map((item, index) => Object.assign({}, item, { image_url: api.mediaUrl(item.image_url), score_text: helpers.score(item.provider_score), rank: index + 1 }))
    this.setData({ result, image: app.globalData.recognitionImage || '', candidates, selected: '', feedbackOpen: !candidates.length })
    if (!candidates.length) return
    // AI-03: the first candidate is a preview, never an automatic confirmation.
    await Promise.all([this.loadPreview(candidates[0].id), this.loadCandidateImages()])
  },
  onShow() {
    if (this.data.preview && this.data.preview.available && !this.data.previewLoading && !this.data.favoriteBusy && (!this.data.favoriteLoading || !session.get())) return this.loadFavorite(this.data.preview.id, this._previewSequence)
  },
  onHide() { this.stopAudio(); this.setData({ playing: false }) },
  onUnload() { this._unloaded = true; this._previewSequence++; this.stopAudio() },
  currentPreview(id, sequence) { return !this._unloaded && this._previewSequence === sequence && this.data.preview && this.data.preview.id === id },
  async publishedCharacter(id) {
    if (!this._details) this._details = new Map()
    if (!this._details.has(id)) {
      const request = api.request('/characters/' + encodeURIComponent(id)).then(detail => Object.assign({}, detail, {
        id, image_url: api.mediaUrl(detail.image_url), audio_url: api.mediaUrl(detail.audio_url),
        variants: (detail.variants || []).map(value => Object.assign({}, value, { image_url: api.mediaUrl(value.image_url) })),
        display_tags: [...new Set([detail.category_l1, detail.category_l2, ...(detail.tags || [])].filter(Boolean))].slice(0,3)
      })).catch(error => { this._details.delete(id); throw error })
      this._details.set(id, request)
    }
    return this._details.get(id)
  },
  async loadCandidateImages() {
    const candidates = await Promise.all(this.data.candidates.map(async candidate => {
      if (candidate.image_url) return candidate
      try {
        const detail = await this.publishedCharacter(candidate.id)
        return Object.assign({}, candidate, { image_url: detail.image_url })
      } catch (_) { return candidate }
    }))
    if (!this._unloaded) this.setData({ candidates })
  },
  async loadPreview(id) {
    const candidate = this.data.candidates.find(item => item.id === id)
    if (!candidate || this._unloaded) return
    const sequence = this._previewSequence = (this._previewSequence || 0) + 1
    this.stopAudio()
    this.setData({ preview: Object.assign({}, candidate, { available: false, variants: [], display_tags: [] }), previewLoading: true, previewError: '', merchants: [], merchantsLoading: true, merchantsError: '', saved: false, favoriteBusy: false, favoriteLoading: false, favoriteError: '', playing: false })
    try {
      const detail = await this.publishedCharacter(id)
      if (!this.currentPreview(id, sequence)) return
      this.setData({ preview: Object.assign({}, detail, { rank: candidate.rank, score_text: candidate.score_text, available: true }), previewLoading: false })
      await Promise.all([this.loadMerchants(id, sequence), this.loadFavorite(id, sequence)])
    } catch (_) {
      if (this.currentPreview(id, sequence)) this.setData({ previewLoading: false, previewError: '该词条的已发布内容暂不可用，可重试或选择其他候选。', merchantsLoading: false })
    }
  },
  async loadMerchants(id, sequence) {
    try {
      const merchants = await api.collection('/characters/' + encodeURIComponent(id) + '/nearby', { limit: 6 })
      if (!this.currentPreview(id, sequence)) return
      // REC-01: no unsolicited location request or unscoped/fabricated distances.
      this.setData({ merchants: merchants.slice(0,6).map(item => Object.assign({}, item, { image_url: api.mediaUrl(item.image_url), display_tags: (item.tags || []).slice(0,2) })), merchantsLoading: false })
    } catch (_) {
      if (this.currentPreview(id, sequence)) this.setData({ merchantsLoading: false, merchantsError: '关联商户暂时无法加载' })
    }
  },
  async loadFavorite(id, sequence) {
    if (!this.currentPreview(id, sequence)) return
    const identity = session.get(), readSequence = this._favoriteSequence = (this._favoriteSequence || 0) + 1
    const current = () => this.currentPreview(id, sequence) && this._favoriteSequence === readSequence
    this.setData({ saved: false, favoriteError: '', favoriteLoading: !!identity })
    if (!identity) return
    try {
      const favorites = await api.all('/me/favorites', {}, true)
      if (current() && session.get() === identity) this.setData({ saved: favorites.some(item => helpers.identifier(item) === id) })
    } catch (_) {
      if (current() && session.get() === identity) this.setData({ favoriteError: '收藏状态暂不可用，请重试' })
    } finally {
      if (current()) this.setData({ favoriteLoading: false })
    }
  },
  async favorite() {
    const item = this.data.preview
    if (!item || !item.available || this.data.favoriteBusy || this.data.favoriteLoading || !session.requireLogin()) return
    const sequence = this._previewSequence, saved = this.data.saved, identity = session.get()
    if (this.data.favoriteError) return this.loadFavorite(item.id, sequence)
    this.setData({ favoriteBusy: true })
    try {
      await api.request('/me/favorites/' + encodeURIComponent(item.id), { method: saved ? 'DELETE' : 'PUT', auth: true })
      if (this.currentPreview(item.id, sequence)) this.setData({ saved: session.get() === identity ? !saved : false })
    } catch (error) { if (this.currentPreview(item.id, sequence)) api.showError(error) }
    finally { if (this.currentPreview(item.id, sequence)) this.setData({ favoriteBusy: false }) }
  },
  stopAudio() {
    if (this.audioContext) { const audio = this.audioContext; this.audioContext = null; audio.destroy() }
  },
  audio() {
    if (!this.data.preview || !this.data.preview.audio_url || this._unloaded) return
    if (!this.audioContext) {
      const audio = this.audioContext = wx.createInnerAudioContext()
      audio.src = this.data.preview.audio_url
      audio.onEnded(() => { if (this.audioContext === audio && !this._unloaded) this.setData({ playing: false }) })
      audio.onError(() => { if (this.audioContext === audio && !this._unloaded) { this.setData({ playing: false }); api.showError(new Error('音频暂时无法播放')) } })
    }
    if (this.data.playing) this.audioContext.pause(); else this.audioContext.play()
    this.setData({ playing: !this.data.playing })
  },
  choose(event) {
    const id = event.currentTarget.dataset.id
    if (this.data.busy || !this.data.candidates.some(item => item.id === id)) return
    this.setData({ selected: id })
    return this.loadPreview(id)
  },
  retryPreview() { if (this.data.preview) { this._details.delete(this.data.preview.id); return this.loadPreview(this.data.preview.id) } },
  previewImage(event) {
    const source = event.currentTarget.dataset.src
    if (source) wx.previewImage({ current: source, urls: [source] })
  },
  photoError() { this.setData({ image: '' }) },
  merchantImageError(event) { this.setData({ merchants: this.data.merchants.map(item => item.id === event.currentTarget.dataset.id ? Object.assign({}, item, { image_url: '' }) : item) }) },
  merchant(event) {
    const id = event.currentTarget.dataset.id
    if (this.data.merchants.some(item => item.id === id)) wx.navigateTo({ url: '/pages/merchant/index?id=' + encodeURIComponent(id) + '&recognition_id=' + encodeURIComponent(this.data.result.request_id) })
  },
  nearby() {
    if (this.data.preview && this.data.preview.available) wx.navigateTo({ url: '/pages/merchants/index?character_id=' + encodeURIComponent(this.data.preview.id) + '&recognition_id=' + encodeURIComponent(this.data.result.request_id) })
  },
  toggleFeedback() {
    this.setData({ feedbackOpen: !this.data.feedbackOpen }, () => {
      if (this.data.feedbackOpen) wx.pageScrollTo({ selector: '#feedback-panel', duration: 200 })
    })
  },
  comment(event) { this.setData({ comment: event.detail.value }) },
  attachmentConsent(event) { this.setData({ attachImage: event.detail.value.includes('attach') }) },
  retake() {
    const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : []
    const previous = pages[pages.length - 2]
    if (previous && previous.route === 'pages/home/index') {
      wx.navigateBack()
    } else wx.switchTab({ url: '/pages/home/index' })
  },
  async submit(event) {
    const characterId = event.currentTarget.dataset.unknown ? null : this.data.selected
    if (this.data.busy || !this.data.result || (!event.currentTarget.dataset.unknown && !characterId)) return
    this.setData({ busy: true, error: '' })
    try {
      const payload = { comment: this.data.comment || (characterId ? '' : '候选均不匹配，请人工复核') }
      if (characterId) payload.character_id = characterId
      if (this.data.attachImage) {
        if (!this.data.image) throw new Error('本次照片已失效，请重新拍摄后提交附图')
        await api.uploadFeedbackImage(this.data.result.request_id, this.data.image, true)
      }
      await api.request('/recognize/' + encodeURIComponent(this.data.result.request_id) + '/confirm', { method: 'POST', auth: true, data: payload })
      const app = getApp()
      if (characterId) {
        if (app.globalData.activeQuest) {
          const quest = app.globalData.activeQuest
          try {
            await api.request('/quests/' + encodeURIComponent(quest.quest_id) + '/checkin', { method: 'POST', auth: true, data: { node_id: quest.node_id, recognition_id: this.data.result.request_id } })
            app.globalData.activeQuest = null
          } catch (error) { api.showError(error) }
        }
        wx.redirectTo({ url: '/pages/character/index?id=' + encodeURIComponent(characterId) + '&recognition_id=' + encodeURIComponent(this.data.result.request_id) })
      } else { this.stopAudio(); this.setData({ submitted: true, playing: false }) }
    } catch (error) { this.setData({ error: error.message, requestId: error.requestId || '' }) }
    finally { this.setData({ busy: false }) }
  }
})
