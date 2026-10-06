const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
const recognition = require('../../utils/recognition')
const platform = require('../../utils/platform')
const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
Page({
  data: { loading: true, error: '', characters: [], merchants: [], today: null, heroTop: 36, todayText: '', location: null, locating: false, locationError: '' },
  onLoad() {
    const now = new Date()
    try {
      const rect = wx.getMenuButtonBoundingClientRect ? wx.getMenuButtonBoundingClientRect() : null
      const win = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync()
      const statusBarHeight = Number(win.statusBarHeight) || 0
      // MINI-01: title fits left of the native capsule instead of below it.
      const top = rect && Number(rect.top) > 0 ? Number(rect.top) : statusBarHeight + 4
      this.setData({ heroTop: Math.max(statusBarHeight + 4, top), todayText: `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日 ${weekdays[now.getDay()]}` })
    } catch (error) {
      this.setData({ todayText: `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日 ${weekdays[now.getDay()]}` })
    }
    this.load()
    // Never prompt for location on entry; only reuse an existing authorization.
    if (wx.getSetting) wx.getSetting({ success: settings => {
      if (!this.disposed && settings.authSetting && settings.authSetting['scope.userLocation']) this.locate()
    } })
  },
  onUnload() { this.disposed = true; this.loadVersion = (this.loadVersion || 0) + 1 },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  async load() {
    const version = this.loadVersion = (this.loadVersion || 0) + 1
    const location = this.data.location
    this.setData({ loading: true, error: '' })
    try {
      const [characters, merchants] = await Promise.all([api.collection('/characters', { limit: 8 }), location ? api.all('/merchants', { limit: 100 }) : api.collection('/merchants', { limit: 4 })])
      if (version !== this.loadVersion || this.disposed) return
      const today = characters.length ? helpers.normalizeCharacter(characters[new Date().getDate() % characters.length]) : null
      if (today) today.image_url = api.mediaUrl(today.image_url)
      const nearby = merchants.map(item => {
        const meters = helpers.metersBetween(location, item)
        return Object.assign({}, item, { image_url: api.mediaUrl(item.image_url), distance_m: meters, distance: helpers.distance(meters), displayTags: (Array.isArray(item.tags) ? item.tags : []).slice(0, 3) })
      })
      if (location) nearby.sort((a, b) => (a.distance_m === null ? Infinity : a.distance_m) - (b.distance_m === null ? Infinity : b.distance_m))
      const visible = nearby.slice(0, 4)
      this.setData({ characters, today, merchants: visible })
      visible.forEach(item => api.track('merchant_impression', { entity_type: 'merchants', entity_id: item.id }))
    } catch (error) { if (version === this.loadVersion && !this.disposed) this.setData({ error: error.message }) }
    finally { if (version === this.loadVersion && !this.disposed) this.setData({ loading: false }) }
  },
  async locate() {
    if (this.data.locating) return
    this.setData({ locating: true, locationError: '' })
    try {
      const location = await platform.locate()
      if (this.disposed) return
      if (!helpers.coordinates(location)) throw new Error('暂未获取到有效位置')
      this.setData({ location })
      await this.load()
    } catch (error) {
      if (!this.disposed) {
        // Invalidate a refresh using an old location when authorization is lost.
        if (this.data.location) { this.loadVersion = (this.loadVersion || 0) + 1; this.setData({ loading: false }) }
        this.setData({ location: null, locationError: error.message, merchants: this.data.merchants.map(item => Object.assign({}, item, { distance: '', distance_m: null })) })
      }
    } finally { if (!this.disposed) this.setData({ locating: false }) }
  },
  merchantImageError(event) { this.setData({ merchants: this.data.merchants.map(item => item.id === event.currentTarget.dataset.id ? Object.assign({}, item, { imageFailed: true }) : item) }) },
  camera() { return recognition.chooseCamera() },
  character() { if (this.data.today) wx.navigateTo({ url: '/pages/character/index?id=' + encodeURIComponent(this.data.today.id) }) },
  merchant(event) { wx.navigateTo({ url: '/pages/merchant/index?id=' + encodeURIComponent(event.currentTarget.dataset.id) }) },
  map() { wx.switchTab({ url: '/pages/map/index' }) },
  quests() { wx.switchTab({ url: '/pages/quests/index' }) },
  catalog() { wx.navigateTo({ url: '/pages/catalog/index' }) },
  more() { wx.navigateTo({ url: '/pages/merchants/index' }) },
  onShareAppMessage() { return { title: '东巴寻迹 · 丽江', path: '/pages/home/index' } }
})
