// GEO-01 / DESIGN-01: real published points; never fabricate ratings or offers.
const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
const platform = require('../../utils/platform')
const isMerchant = point => !!point.merchant_id || point.poi_type === 'merchant'
Page({
  data: { loading: true, error: '', questError: '', points: [], visiblePoints: [], markers: [], center: null, selected: null, filter: 'all', sort: 'default', scale: 15, satellite: false, location: null, locationError: '', locating: false },
  onLoad() { this.load() },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  async load() {
    this.setData({ loading: true, error: '', questError: '' })
    try {
      const [pois, merchants, routes] = await Promise.all([
        api.all('/map/pois'), api.all('/merchants'),
        api.all('/quests').then(quests => Promise.all(quests.map(quest => api.request('/quests/' + encodeURIComponent(quest.id))))).catch(() => {
          this.setData({ questError: '任务地点暂时未能同步，其他地点仍可浏览。' }); return []
        })
      ])
      const questPois = new Set(), questMerchants = new Set()
      routes.forEach(route => (route.nodes || []).forEach(node => { if (node.poi_id) questPois.add(node.poi_id); if (node.merchant_id) questMerchants.add(node.merchant_id) }))
      const merchantById = new Map(merchants.map(merchant => [merchant.id, merchant]))
      const mappedMerchants = new Set(pois.filter(helpers.coordinates).map(point => point.merchant_id).filter(Boolean))
      const points = pois.concat(merchants.filter(merchant => !mappedMerchants.has(merchant.id)).map(merchant => Object.assign({}, merchant, { id: 'merchant:' + merchant.id, merchant_id: merchant.id, poi_type: 'merchant' }))).filter(helpers.coordinates).map((point, index) => {
        const merchant = merchantById.get(point.merchant_id) || {}
        const tags = point.tags && point.tags.length ? point.tags : (merchant.tags || [])
        return Object.assign({}, point, {
          latitude: Number(point.latitude), longitude: Number(point.longitude), marker_id: index + 1,
          address: point.address || merchant.address || '', image_url: api.mediaUrl(point.image_url || merchant.image_url),
          display_tags: Array.from(new Set(tags)).slice(0, 2),
          type_label: isMerchant(point) ? '文化商户' : point.poi_type === 'quest' ? '任务点' : '文化地点',
          is_quest: questPois.has(point.id) || questMerchants.has(point.merchant_id) || point.poi_type === 'quest'
        })
      })
      this.setData({ points }); this.filterPoints()
    } catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  filter(event) {
    const filter = event.currentTarget.dataset.type
    if (!['all', 'culture', 'merchant', 'quest'].includes(filter)) return
    this.setData({ filter }); this.filterPoints(true)
  },
  filterPoints(recenter = false) {
    const type = this.data.filter
    const visiblePoints = this.data.points.filter(point => type === 'all' || (type === 'merchant' ? isMerchant(point) : type === 'culture' ? !isMerchant(point) && ['culture', 'landmark', 'attraction'].includes(point.poi_type) : point.is_quest))
      .map(point => { const meters = helpers.metersBetween(this.data.location, point); return Object.assign({}, point, { distance_m: meters, distance: helpers.distance(meters) }) })
    if (this.data.sort === 'distance' && this.data.location) visiblePoints.sort((a, b) => a.distance_m - b.distance_m || a.marker_id - b.marker_id)
    const selected = visiblePoints.find(point => this.data.selected && point.id === this.data.selected.id) || visiblePoints[0] || null
    const center = recenter ? selected || this.data.location || this.data.center : this.data.center || this.data.location || selected
    this.setData({ visiblePoints, selected, center }); this.updateMarkers()
  },
  updateMarkers() {
    const markers = this.data.visiblePoints.map(point => {
      const selected = this.data.selected && this.data.selected.id === point.id
      const kind = this.data.filter === 'quest' || (!isMerchant(point) && point.is_quest) ? 'quest' : isMerchant(point) ? 'merchant' : 'culture'
      const name = point.name.length > 12 ? point.name.slice(0, 12) + '…' : point.name
      return { id: point.marker_id, latitude: point.latitude, longitude: point.longitude, width: selected ? 38 : 30, height: selected ? 46 : 36,
        iconPath: '/assets/marker-' + kind + '.png', zIndex: selected ? 10 : 1,
        callout: { content: name + (point.distance ? '\n' + point.distance : ''), color: selected ? '#a43122' : '#33473e', fontSize: 12, borderRadius: 8, borderWidth: 1, borderColor: selected ? '#d6a68e' : '#e3e9e3', bgColor: '#ffffff', padding: 8, display: 'ALWAYS' }
      }
    })
    this.setData({ markers })
  },
  marker(event) { this.selectPoint(this.data.visiblePoints.find(point => point.marker_id === Number(event.detail.markerId))) },
  select(event) { this.selectPoint(this.data.visiblePoints.find(point => point.id === event.currentTarget.dataset.id)) },
  selectPoint(point) {
    if (!point) return
    this.setData({ selected: point, center: { latitude: point.latitude, longitude: point.longitude } }, () => this.recenter(point)); this.updateMarkers()
  },
  async locate() {
    if (this.data.locating) return false
    this.setData({ locating: true, locationError: '' })
    try {
      const location = await platform.locate()
      if (!helpers.coordinates(location)) throw new Error('未获得可用位置，请稍后重试')
      this.setData({ location, center: location }, () => this.recenter(location)); this.filterPoints(); return true
    } catch (error) {
      this.setData({ location: null, sort: 'default', locationError: error.message }); this.filterPoints(); return false
    }
    finally { this.setData({ locating: false }) }
  },
  async sortPoints(event) {
    const sort = event.currentTarget.dataset.sort
    if (!['default', 'distance'].includes(sort)) return
    // The permission prompt only follows an explicit location/distance action.
    if (sort === 'distance' && !this.data.location && !await this.locate()) return
    this.setData({ sort }); this.filterPoints()
  },
  toggleLayer() { this.setData({ satellite: !this.data.satellite }) },
  recenter(point) {
    if (!this.mapContext) this.mapContext = wx.createMapContext('culture-map', this)
    this.mapContext.moveToLocation({ latitude: Number(point.latitude), longitude: Number(point.longitude) })
  },
  zoom(event) {
    const step = Number(event.currentTarget.dataset.step)
    if (step === 1 || step === -1) this.setData({ scale: Math.max(11, Math.min(19, this.data.scale + step)) })
  },
  regionChange(event) {
    const detail = event.detail || {}
    if ((detail.type || event.type) !== 'end' || detail.causedBy === 'update') return
    if (!this.mapContext) this.mapContext = wx.createMapContext('culture-map', this)
    this.mapContext.getScale({ success: value => { if (Number.isFinite(value.scale)) this.setData({ scale: Math.max(11, Math.min(19, value.scale)) }) } })
  },
  imageError(event) {
    const points = this.data.points.map(point => point.id === event.currentTarget.dataset.id ? Object.assign({}, point, { image_url: '' }) : point)
    this.setData({ points }); this.filterPoints()
  },
  async navigate(event) {
    const id = event.currentTarget.dataset.id
    const point = id ? this.data.points.find(value => value.id === id) : this.data.selected
    try { await platform.navigate(point); if (point && point.merchant_id) api.track('navigate', { entity_type: 'merchants', entity_id: point.merchant_id }) }
    catch (error) { api.showError(error) }
  },
  detail(event) {
    const id = event && event.currentTarget.dataset.id
    const point = id ? this.data.points.find(value => value.id === id) : this.data.selected
    if (point && point.merchant_id) wx.navigateTo({ url: '/pages/merchant/index?id=' + encodeURIComponent(point.merchant_id) })
  }
})
