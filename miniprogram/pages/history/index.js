const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
const session = require('../../utils/session')
Page({
  data: { loading: true, error: '', items: [], deleting: false },
  onShow() { this.load() },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  async load() {
    this.setData({ items: [] })
    if (!session.get()) { this.setData({ loading: false, error: '请登录后查看识别历史' }); return }
    this.setData({ loading: true, error: '' })
    try {
      const items = await api.all('/me/history', {}, true)
      this.setData({ items: items.map(item => {
        const candidate = (item.candidates || []).find(value => helpers.identifier(value) === item.confirmed_character_id)
        return Object.assign({}, item, { date: helpers.date(item.created_at), name: item.status === 'FAILED' ? '识别未完成' : candidate ? candidate.cn_name : item.confirmed_character_id ? '已确认的东巴字' : item.status === 'UNKNOWN' ? '未找到可靠结果' : '待确认结果', image_url: api.mediaUrl(candidate && candidate.image_url) })
      }) })
    } catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  detail(event) {
    const item = this.data.items.find(value => value.request_id === event.currentTarget.dataset.id)
    if (!item) return
    if (item.status === 'FAILED') {
      wx.showModal({ title: '识别未完成', content: api.errorFrom(503, { code: item.error_code }).message, confirmText: '重新拍摄', success: response => { if (response.confirm) wx.navigateTo({ url: '/pages/camera/index' }) } })
      return
    }
    if (item.confirmed_character_id) wx.navigateTo({ url: '/pages/character/index?id=' + encodeURIComponent(item.confirmed_character_id) + '&recognition_id=' + encodeURIComponent(item.request_id) })
    else { getApp().globalData.recognition = item; getApp().globalData.recognitionImage = ''; wx.navigateTo({ url: '/pages/result/index' }) }
  },
  clear() {
    if (this.data.deleting) return
    wx.showModal({ title: '清空识别历史', content: '将删除全部识别记录、相关反馈及留存的图片样本，此操作无法撤销。已收藏的东巴字会保留。', confirmColor: '#b84e40', success: async response => {
      if (!response.confirm) return
      this.setData({ deleting: true })
      try {
        await api.request('/me/history', { method: 'DELETE', auth: true })
        getApp().globalData.recognition = null; getApp().globalData.recognitionImage = ''; getApp().globalData.activeQuest = null
        this.setData({ items: [] }); wx.showToast({ title: '历史已清空' })
      } catch (error) { api.showError(error) }
      finally { this.setData({ deleting: false }) }
    } })
  }
})
