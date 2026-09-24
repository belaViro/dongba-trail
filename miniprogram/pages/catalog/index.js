const api = require('../../utils/api')
Page({
  data: { loading: true, error: '', items: [], search: '' },
  onLoad() { this.load() },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  search(event) { this.setData({ search: event.detail.value }) },
  async load() {
    this.setData({ loading: true, error: '' })
    try { this.setData({ items: (await api.all('/products', { q: this.data.search })).map(item => Object.assign({}, item, { image_url: api.mediaUrl(item.image_url) })) }) }
    catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  merchant(event) { wx.navigateTo({ url: '/pages/merchant/index?id=' + encodeURIComponent(event.currentTarget.dataset.id) }) }
})
