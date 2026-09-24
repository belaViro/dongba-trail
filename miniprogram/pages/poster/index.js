const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
const platform = require('../../utils/platform')
Page({
  data: { loading: true, error: '', items: [], selected: [], template: 'paper', image: '', generating: false, saving: false, shareCode: false },
  onLoad(options) { this.initialId = options.character_id; this.load() },
  async load() {
    this.setData({ loading: true, error: '', items: [], selected: [], image: '' })
    try {
      const [favorites, history] = await Promise.all([api.collection('/me/favorites', {}, true), api.all('/me/history', {}, true)])
      const existing = new Set(favorites.map(helpers.identifier))
      const confirmed = Array.from(new Set(history.map(value => value.confirmed_character_id).filter(Boolean))).filter(id => !existing.has(id))
      const details = await Promise.all(confirmed.map(id => api.request('/characters/' + encodeURIComponent(id)).catch(() => null)))
      const items = helpers.uniqueCharacters(favorites.concat(details.filter(Boolean))).map(value => Object.assign({}, value, { image_url: api.mediaUrl(value.image_url) }))
      const selected = this.initialId && items.some(value => value.id === this.initialId) ? [this.initialId] : []
      this.setData({ items: items.map(value => Object.assign({}, value, { selected: selected.includes(value.id) })), selected })
    } catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  toggle(event) {
    if (this.data.generating) return
    const id = event.currentTarget.dataset.id
    let selected = this.data.selected.slice()
    if (selected.includes(id)) selected = selected.filter(value => value !== id)
    else if (selected.length < 3) selected.push(id)
    else { api.showError(new Error('最多选择 3 个东巴字')); return }
    this.setData({ selected, image: '', items: this.data.items.map(value => Object.assign({}, value, { selected: selected.includes(value.id) })) })
  },
  template(event) { if (!this.data.generating) this.setData({ template: event.currentTarget.dataset.template, image: '' }) },
  async download(url) {
    const result = await platform.call('downloadFile', { url: api.mediaUrl(url) })
    if (result.statusCode !== 200) throw new Error('海报暂时无法下载')
    return result.tempFilePath
  },
  async generate() {
    if (this.data.generating || this.data.selected.length < 1 || this.data.selected.length > 3) return
    this.setData({ generating: true, error: '', image: '' })
    try {
      const result = await api.request('/share/poster', { method: 'POST', auth: true, data: { character_ids: this.data.selected, template: this.data.template } })
      if (!result.url) throw new Error('海报服务暂未返回可用图片')
      const image = await this.download(result.url)
      this.setData({ image, shareCode: !!result.share_code_available })
    } catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ generating: false }) }
  },
  preview() { if (this.data.image) wx.previewImage({ urls: [this.data.image] }) },
  async save() {
    if (!this.data.image || this.data.saving) return
    this.setData({ saving: true })
    try {
      await platform.privacy()
      await platform.call('saveImageToPhotosAlbum', { filePath: this.data.image })
      wx.showToast({ title: '海报已保存' })
      api.track('share', { entity_type: 'characters', entity_id: this.data.selected[0] })
    } catch (error) {
      if (!/cancel/.test(error.errMsg || '')) {
        wx.showModal({ title: '无法保存海报', content: '请在微信设置中允许保存到相册后重试。', confirmText: '打开设置', success: result => { if (result.confirm) platform.openSettings() } })
      }
    } finally { this.setData({ saving: false }) }
  },
  onShareAppMessage() {
    const character = this.data.items.find(value => value.id === this.data.selected[0])
    api.track('share', character ? { entity_type: 'characters', entity_id: character.id } : {})
    return { title: '我的东巴印记 · 丽江', path: character ? '/pages/character/index?id=' + encodeURIComponent(character.id) : '/pages/home/index', imageUrl: this.data.image || undefined }
  }
})
