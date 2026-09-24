const api = require('../../utils/api')
const session = require('../../utils/session')
const platform = require('../../utils/platform')
Page({
  data: { loading: true, busy: false, accepted: false, policy: null, error: '' },
  onLoad() { this.load() },
  async load() {
    this.setData({ loading: true, error: '' })
    try { this.setData({ policy: await api.request('/privacy') }) }
    catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  toggle(event) { this.setData({ accepted: event.detail.value.includes('yes') }) },
  policy() { wx.navigateTo({ url: '/pages/privacy/index' }) },
  async login() {
    if (this.data.busy || !this.data.accepted || !this.data.policy || !this.data.policy.published) return
    this.setData({ busy: true, error: '' })
    try {
      const code = await platform.call('login')
      if (!code.code) throw new Error('微信登录未返回有效凭据，请重试')
      const result = await api.request('/auth/wechat', { method: 'POST', data: { code: code.code, privacy_accepted: true } })
      session.save(result)
      wx.setStorageSync('dongba_privacy_version', this.data.policy.version)
      wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/profile/index' }) })
    } catch (error) { this.setData({ error: error.message || '微信登录失败，请检查小程序账号配置后重试', requestId: error.requestId || '' }) }
    finally { this.setData({ busy: false }) }
  }
})
