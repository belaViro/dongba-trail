const api = require('../../utils/api')
Page({
  data: { loading: true, error: '', policy: null, authorize: false },
  onLoad(options) { this.setData({ authorize: options.authorize === '1' }); this.load() },
  async load() {
    this.setData({ loading: true, error: '' })
    try { this.setData({ policy: await api.request('/privacy') }) }
    catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  agree() {
    if (!this.data.policy || !this.data.policy.published) return
    wx.setStorageSync('dongba_privacy_version', this.data.policy.version)
    const app = getApp()
    if (app.globalData.privacyResolve) { app.globalData.privacyResolve({ event: 'agree', buttonId: 'agree-privacy' }); app.globalData.privacyResolve = null }
    wx.navigateBack()
  },
  onUnload() {
    const app = getApp()
    if (this.data.authorize && app.globalData.privacyResolve) { app.globalData.privacyResolve({ event: 'disagree' }); app.globalData.privacyResolve = null }
  },
  openWechat() { if (wx.openPrivacyContract) wx.openPrivacyContract({ fail: () => api.showError(new Error('暂时无法打开微信隐私指引，请稍后重试')) }) }
})
