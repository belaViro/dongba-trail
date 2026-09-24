const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
Page({
  data: { loading: true, error: '', items: [], busy: '' },
  onShow() { this.load() },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  async load() {
    this.setData({ loading: true, error: '', items: [] })
    try { this.setData({ items: (await api.collection('/me/favorites', {}, true)).map(item => Object.assign(helpers.normalizeCharacter(item), { image_url: api.mediaUrl(item.image_url) })) }) }
    catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  detail(event) { wx.navigateTo({ url: '/pages/character/index?id=' + encodeURIComponent(event.currentTarget.dataset.id) }) },
  async remove(event) {
    if (this.data.busy) return
    const id = event.currentTarget.dataset.id
    this.setData({ busy: id })
    try { await api.request('/me/favorites/' + encodeURIComponent(id), { method: 'DELETE', auth: true }); this.setData({ items: this.data.items.filter(value => value.id !== id) }) }
    catch (error) { api.showError(error) }
    finally { this.setData({ busy: '' }) }
  },
  poster() { wx.navigateTo({ url: '/pages/poster/index' }) }
})
