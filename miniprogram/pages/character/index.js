const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
const session = require('../../utils/session')
Page({
  data: { loading: true, error: '', item: null, merchants: [], related: [], products: [], saved: false, playing: false, favoriteBusy: false },
  onLoad(options) { this.characterId = options.id; this.recognitionId = options.recognition_id; this.setData({ recognitionId: options.recognition_id || '' }); this.load() },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  onUnload() { if (this.audioContext) { this.audioContext.destroy(); this.audioContext = null } },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const item = await api.request('/characters/' + encodeURIComponent(this.characterId))
      item.id = helpers.identifier(item); item.image_url = api.mediaUrl(item.image_url); item.audio_url = api.mediaUrl(item.audio_url)
      this.setData({ item })
      api.track('character_detail', { entity_type: 'characters', entity_id: item.id, recognition_id: this.recognitionId || null })
      const [merchants, products, related] = await Promise.all([
        api.collection('/characters/' + encodeURIComponent(item.id) + '/nearby'),
        api.collection('/products', { character_id: item.id, limit: 6 }),
        api.all('/characters')
      ])
      this.setData({ merchants: merchants.map(value => Object.assign({}, value, { image_url: api.mediaUrl(value.image_url), distance: helpers.distance(value.distance_m) })), products: products.map(value => Object.assign({}, value, { image_url: api.mediaUrl(value.image_url) })), related: related.filter(value => helpers.identifier(value) !== item.id && ((item.category_l1 && value.category_l1 === item.category_l1) || (value.tags || []).some(tag => (item.tags || []).includes(tag)))).slice(0,4).map(value => Object.assign({}, helpers.normalizeCharacter(value), { image_url: api.mediaUrl(value.image_url) })) })
      merchants.forEach(value => api.track('merchant_impression', { entity_type: 'merchants', entity_id: value.id, recognition_id: this.recognitionId || null }))
      if (session.get()) {
        const favorites = await api.collection('/me/favorites', {}, true)
        this.setData({ saved: favorites.some(value => helpers.identifier(value) === item.id) })
      }
    } catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  async favorite() {
    if (!session.requireLogin() || this.data.favoriteBusy) return
    this.setData({ favoriteBusy: true })
    try { await api.request('/me/favorites/' + encodeURIComponent(this.characterId), { method: this.data.saved ? 'DELETE' : 'PUT', auth: true }); this.setData({ saved: !this.data.saved }) }
    catch (error) { api.showError(error) }
    finally { this.setData({ favoriteBusy: false }) }
  },
  audio() {
    if (!this.data.item || !this.data.item.audio_url) return
    if (!this.audioContext) {
      this.audioContext = wx.createInnerAudioContext(); this.audioContext.src = this.data.item.audio_url
      this.audioContext.onEnded(() => this.setData({ playing: false }))
      this.audioContext.onError(() => { this.setData({ playing: false }); api.showError(new Error('音频暂时无法播放')) })
    }
    if (this.data.playing) this.audioContext.pause(); else this.audioContext.play()
    this.setData({ playing: !this.data.playing })
  },
  related(event) { wx.navigateTo({ url: '/pages/character/index?id=' + encodeURIComponent(event.currentTarget.dataset.id) }) },
  merchant(event) { wx.navigateTo({ url: '/pages/merchant/index?id=' + encodeURIComponent(event.currentTarget.dataset.id) + '&recognition_id=' + encodeURIComponent(this.recognitionId || '') }) },
  nearby() { wx.navigateTo({ url: '/pages/merchants/index?character_id=' + encodeURIComponent(this.characterId) + '&recognition_id=' + encodeURIComponent(this.recognitionId || '') }) },
  quests() { wx.switchTab({ url: '/pages/quests/index' }) },
  share() { if (session.requireLogin()) wx.navigateTo({ url: '/pages/poster/index?character_id=' + encodeURIComponent(this.characterId) }) },
  async correct() {
    if (!session.requireLogin()) return
    try {
      const history = await api.all('/me/history', {}, true)
      const record = history.find(value => value.request_id === this.recognitionId)
      if (!record) throw new Error('原识别记录已清除，请重新识别')
      const app = getApp()
      if (!app.globalData.recognition || app.globalData.recognition.request_id !== record.request_id) app.globalData.recognitionImage = ''
      app.globalData.recognition = record; app.globalData.activeQuest = null
      wx.navigateTo({ url: '/pages/result/index' })
    } catch (error) { api.showError(error) }
  },
  onShareAppMessage() { return { title: (this.data.item ? this.data.item.cn_name + ' · ' : '') + '东巴寻迹', path: '/pages/character/index?id=' + encodeURIComponent(this.characterId) } }
})
