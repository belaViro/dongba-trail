const api = require('../../utils/api')
const session = require('../../utils/session')
Page({
  data: { user: null, error: '', loading: false, counts: { favorites: 0, stamps: 0, coupons: 0 } },
  onShow() { this.load() },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  async load() {
    const current = session.get(); this.setData({ user: current && current.user || null, error: '', loading: !!current, counts: { favorites: null, stamps: null, coupons: null } })
    if (!current) return
    try {
      const [user, favorites, stamps, coupons] = await Promise.all([api.request('/auth/me', { auth: true }), api.collection('/me/favorites', {}, true), api.collection('/me/stamps', {}, true), api.collection('/me/coupons', {}, true)])
      this.setData({ user, counts: { favorites: favorites.length, stamps: stamps.length, coupons: coupons.filter(value => value.status === 'available').length } })
    } catch (error) { this.setData({ error: error.message, user: session.get() ? this.data.user : null }) }
    finally { this.setData({ loading: false }) }
  },
  login() { wx.navigateTo({ url: '/pages/login/index' }) },
  copyUserId() {
    if (!session.requireLogin()) return
    wx.setClipboardData({ data: session.get().user.id })
  },
  open(event) { if (session.requireLogin()) wx.navigateTo({ url: '/pages/' + event.currentTarget.dataset.page + '/index' }) },
  privacy() { wx.navigateTo({ url: '/pages/privacy/index' }) },
  logout() {
    wx.showModal({ title: '退出登录', content: '确认退出当前账号？', success: async result => {
      if (!result.confirm) return
      try { await api.request('/auth/logout', { method: 'POST', auth: true }); session.clear(); getApp().globalData.recognition = null; getApp().globalData.recognitionImage = ''; this.load() }
      catch (error) { api.showError(error) }
    } })
  }
})
