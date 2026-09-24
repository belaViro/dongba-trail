const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
const session = require('../../utils/session')
const samples = require('../../utils/samples')
Page({
  data: { loading: true, error: '', items: [], previewing: '', deleting: '' },
  onShow() { this.load() },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  onUnload() { this.disposeImages() },
  disposeImages() {
    Object.keys(this._images || {}).forEach(id => this.removeImage(id))
  },
  removeImage(id) {
    const file = this._images && this._images[id]
    if (file && wx.getFileSystemManager) wx.getFileSystemManager().unlink({ filePath: file, fail() {} })
    if (this._images) delete this._images[id]
  },
  async load() {
    this.disposeImages(); this._images = {}
    this.setData({ items: [], error: '', loading: false, previewing: '' })
    const auth = session.get()
    if (!auth) { this.setData({ error: '请登录后查看图片样本' }); return }
    this.setData({ loading: true })
    try {
      const items = await api.all('/me/samples', {}, true)
      if (!session.get() || session.get().access_token !== auth.access_token) return
      this.setData({ items: items.map(item => Object.assign({}, item, {
        date: helpers.date(item.created_at), scene_text: samples.sceneLabel(item.scene),
        review_text: samples.reviewStates[item.review_status] || '待人工复核'
      })) })
    } catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  async preview(event) {
    const id = event.currentTarget.dataset.id
    const auth = session.get()
    if (!auth || this.data.previewing || !this.data.items.some(item => item.id === id)) return
    this.setData({ previewing: id })
    try {
      const image = await api.downloadPrivate('/me/samples/' + encodeURIComponent(id) + '/image', { errorCode: 'SAMPLE_NOT_FOUND', label: '图片样本' })
      this._images = this._images || {}; this._images[id] = image
      if (!session.get() || session.get().access_token !== auth.access_token || !this.data.items.some(item => item.id === id)) { this.removeImage(id); return }
      wx.previewImage({ current: image, urls: [image], fail() { api.showError(new Error('图片预览失败，请重试')) } })
    } catch (error) { api.showError(error) }
    finally { this.setData({ previewing: '' }) }
  },
  remove(event) {
    const id = event.currentTarget.dataset.id
    if (this.data.deleting || !this.data.items.some(item => item.id === id)) return
    wx.showModal({ title: '删除图片样本', content: '将删除这张图片及其样本资料。识别历史和已收藏的东巴字会保留。', confirmColor: '#b84e40', success: async response => {
      if (!response.confirm) return
      this.setData({ deleting: id })
      try {
        await api.request('/me/samples/' + encodeURIComponent(id), { method: 'DELETE', auth: true })
        this.removeImage(id)
        this.setData({ items: this.data.items.filter(item => item.id !== id) })
        wx.showToast({ title: '图片样本已删除' })
      } catch (error) { api.showError(error) }
      finally { this.setData({ deleting: '' }) }
    } })
  }
})
