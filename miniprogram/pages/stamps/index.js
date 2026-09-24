const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
Page({
  data: { loading: true, error: '', items: [] },
  onShow() { this.load() },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  async load() {
    this.setData({ loading: true, error: '', items: [] })
    try { this.setData({ items: (await api.collection('/me/stamps', {}, true)).map(item => Object.assign({}, item, { date: helpers.date(item.obtained_at) })) }) }
    catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  detail(event) { wx.navigateTo({ url: '/pages/quest/index?id=' + encodeURIComponent(event.currentTarget.dataset.id) }) },
  poster() { wx.navigateTo({ url: '/pages/poster/index' }) }
})
