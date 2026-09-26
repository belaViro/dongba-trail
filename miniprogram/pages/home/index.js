const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
const recognition = require('../../utils/recognition')
Page({
  data: { loading: true, error: '', characters: [], merchants: [], today: null },
  onLoad() { this.load() },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const [characters, merchants] = await Promise.all([api.collection('/characters', { limit: 8 }), api.collection('/merchants', { limit: 4 })])
      const today = characters.length ? helpers.normalizeCharacter(characters[new Date().getDate() % characters.length]) : null
      if (today) today.image_url = api.mediaUrl(today.image_url)
      this.setData({ characters, today, merchants: merchants.map(item => Object.assign({}, item, { image_url: api.mediaUrl(item.image_url), distance: helpers.distance(item.distance_m) })) })
      merchants.forEach(item => api.track('merchant_impression', { entity_type: 'merchants', entity_id: item.id }))
    } catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  camera() { recognition.chooseCamera() },
  character() { if (this.data.today) wx.navigateTo({ url: '/pages/character/index?id=' + encodeURIComponent(this.data.today.id) }) },
  merchant(event) { wx.navigateTo({ url: '/pages/merchant/index?id=' + encodeURIComponent(event.currentTarget.dataset.id) }) },
  map() { wx.switchTab({ url: '/pages/map/index' }) },
  quests() { wx.switchTab({ url: '/pages/quests/index' }) },
  catalog() { wx.navigateTo({ url: '/pages/catalog/index' }) },
  more() { wx.navigateTo({ url: '/pages/merchants/index' }) },
  onShareAppMessage() { return { title: '东巴寻迹 · 丽江', path: '/pages/home/index' } }
})
