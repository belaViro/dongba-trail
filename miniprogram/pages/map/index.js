const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
const platform = require('../../utils/platform')
Page({
  data: { loading: true, error: '', points: [], visiblePoints: [], markers: [], center: null, selected: null, filter: 'all', location: null, locationError: '' },
  onLoad() { this.load() },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const [pois, merchants, quests] = await Promise.all([api.all('/map/pois'), api.all('/merchants'), api.all('/quests')])
      const routes = await Promise.all(quests.map(quest => api.request('/quests/' + encodeURIComponent(quest.id))))
      const questPois = new Set(), questMerchants = new Set()
      routes.forEach(route => (route.nodes || []).forEach(node => { if (node.poi_id) questPois.add(node.poi_id); if (node.merchant_id) questMerchants.add(node.merchant_id) }))
      const mappedMerchants = new Set(pois.map(point => point.merchant_id).filter(Boolean))
      const points = pois.concat(merchants.filter(merchant => !mappedMerchants.has(merchant.id)).map(merchant => Object.assign({}, merchant, { id: 'merchant:' + merchant.id, merchant_id: merchant.id, poi_type: 'merchant' }))).filter(helpers.coordinates).map((point, index) => Object.assign({}, point, { marker_id: index + 1, image_url: api.mediaUrl(point.image_url), is_quest: questPois.has(point.id) || questMerchants.has(point.merchant_id) }))
      this.setData({ points }); this.filterPoints()
    } catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  filter(event) { this.setData({ filter: event.currentTarget.dataset.type }); this.filterPoints() },
  filterPoints() {
    const type = this.data.filter
    const visiblePoints = this.data.points.filter(point => type === 'all' || (type === 'merchant' ? !!point.merchant_id || point.poi_type === 'merchant' : type === 'culture' ? !point.merchant_id && ['culture','landmark','attraction'].includes(point.poi_type) : point.is_quest || point.poi_type === type))
    const markers = visiblePoints.map(point => ({
      id: point.marker_id, latitude: Number(point.latitude), longitude: Number(point.longitude), width: 26, height: 32,
      iconPath: '/assets/marker-' + (point.merchant_id || point.poi_type === 'merchant' ? 'merchant' : point.poi_type === 'quest' ? 'quest' : 'culture') + '.png',
      callout: { content: point.name, color: '#244437', fontSize: 12, borderRadius: 4, borderWidth: 1, borderColor: '#d4e3d7', bgColor: '#ffffff', padding: 8, display: 'ALWAYS' }
    }))
    this.setData({ visiblePoints, markers, selected: visiblePoints[0] || null, center: this.data.location || visiblePoints[0] || null })
  },
  marker(event) { this.setData({ selected: this.data.points.find(point => point.marker_id === event.detail.markerId) || null }) },
  select(event) { this.setData({ selected: this.data.points.find(point => point.id === event.currentTarget.dataset.id) || null }) },
  async locate() {
    try { const location = await platform.locate(); this.setData({ location, center: location, locationError: '' }) }
    catch (error) { this.setData({ locationError: error.message }) }
  },
  async navigate(event) {
    const id = event.currentTarget.dataset.id
    const point = id ? this.data.points.find(value => value.id === id) : this.data.selected
    try { await platform.navigate(point); if (point.merchant_id) api.track('navigate', { entity_type: 'merchants', entity_id: point.merchant_id }) }
    catch (error) { api.showError(error) }
  },
  detail() { if (this.data.selected && this.data.selected.merchant_id) wx.navigateTo({ url: '/pages/merchant/index?id=' + encodeURIComponent(this.data.selected.merchant_id) }) }
})
