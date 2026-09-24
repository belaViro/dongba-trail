const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
const platform = require('../../utils/platform')
Page({
  data: { loading: true, error: '', items: [], search: '', location: null, locationError: '' },
  onLoad(options) { this.characterId = options.character_id; this.recognitionId = options.recognition_id; this.setData({ characterId: options.character_id || '' }); this.load() },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  search(event) { this.setData({ search: event.detail.value }) },
  async locate() {
    try { this.setData({ location: await platform.locate(), locationError: '' }); this.load() }
    catch (error) { this.setData({ locationError: error.message }) }
  },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const path = this.characterId ? '/characters/' + encodeURIComponent(this.characterId) + '/nearby' : '/merchants'
      const params = Object.assign({ q: this.data.search, limit: 100 }, this.data.location ? { latitude: this.data.location.latitude, longitude: this.data.location.longitude } : {})
      const items = await (this.characterId ? api.collection(path, params) : api.all(path, params))
      const search = this.data.search.trim().toLowerCase()
      const values = items.filter(item => !search || [item.name, item.address].concat(item.tags || []).join(' ').toLowerCase().includes(search)).map(item => {
        const meters = item.distance_m === undefined ? helpers.metersBetween(this.data.location, item) : item.distance_m
        return Object.assign({}, item, { image_url: api.mediaUrl(item.image_url), distance: helpers.distance(meters), distance_m: meters })
      })
      if (!this.characterId && this.data.location) values.sort((a,b) => (a.distance_m === null ? Infinity : a.distance_m) - (b.distance_m === null ? Infinity : b.distance_m))
      this.setData({ items: values })
      items.forEach(item => api.track('merchant_impression', { entity_type: 'merchants', entity_id: item.id, recognition_id: this.recognitionId || null }))
    } catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  detail(event) { wx.navigateTo({ url: '/pages/merchant/index?id=' + encodeURIComponent(event.currentTarget.dataset.id) + '&recognition_id=' + encodeURIComponent(this.recognitionId || '') }) }
})
