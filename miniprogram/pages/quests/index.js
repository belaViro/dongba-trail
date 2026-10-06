const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
const session = require('../../utils/session')
const { questView } = require('../../utils/quest-view')
Page({
  data: { loading: true, error: '', items: [], filter: 'all', all: [], heroTop: 28, feature: null, featureLoading: false, featureError: '', selectedId: '', rewardTitle: '', rewardUnavailable: false },
  onLoad() {
    try {
      const win = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync()
      const rect = wx.getMenuButtonBoundingClientRect ? wx.getMenuButtonBoundingClientRect() : null
      this.setData({ heroTop: Math.max(Number(win.statusBarHeight) + 4 || 28, rect && Number(rect.top) || 0) })
    } catch (_) { /* Keep a safe fallback on older WeChat versions. */ }
  },
  onShow() { this.load() },
  onUnload() { this.disposed = true; this.featureVersion = (this.featureVersion || 0) + 1 },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  async load() {
    const version = this.loadVersion = (this.loadVersion || 0) + 1
    this.featureVersion = (this.featureVersion || 0) + 1
    this.setData({ loading: true, error: '', all: [], items: [], feature: null, featureError: '', featureLoading: false, rewardTitle: '', rewardUnavailable: false })
    try {
      const [quests, enrolled] = await Promise.all([api.all('/quests'), session.get() ? api.collection('/me/quests', {}, true) : Promise.resolve([])])
      if (version !== this.loadVersion || this.disposed) return
      const known = new Set(quests.map(item => item.id))
      const combined = quests.concat(enrolled.filter(item => !known.has(item.quest_id || item.id)))
      const all = combined.map(item => {
        const id = item.quest_id || item.id
        const progress = enrolled.find(value => (value.quest_id || value.id) === id)
        return Object.assign({}, item, { id, progress, unavailable: !known.has(id), start_date: helpers.date(item.start_at), end_date: helpers.date(item.end_at), completed: progress && progress.completed_node_ids ? progress.completed_node_ids.length : 0 })
      })
      this.setData({ all, loading: false }); await this.applyFilter()
    } catch (error) { if (version === this.loadVersion && !this.disposed) this.setData({ error: error.message }) }
    finally { if (version === this.loadVersion && !this.disposed) this.setData({ loading: false }) }
  },
  filter(event) {
    const filter = event.currentTarget.dataset.type
    if (filter === 'mine' && !session.requireLogin()) return
    this.setData({ filter }); return this.applyFilter()
  },
  applyFilter() {
    const items = this.data.all.filter(item => this.data.filter === 'all' || !!item.progress)
    this.setData({ items })
    const selected = items.find(item => item.id === this.data.selectedId) || items.find(item => item.progress && item.progress.status !== 'completed') || items[0]
    return this.loadFeature(selected)
  },
  selectRoute(event) { return this.loadFeature(this.data.items.find(item => item.id === event.currentTarget.dataset.id)) },
  retryFeature() { return this.loadFeature(this.data.items.find(item => item.id === this.data.selectedId)) },
  async loadFeature(selected) {
    const version = this.featureVersion = (this.featureVersion || 0) + 1
    this.setData({ selectedId: selected ? selected.id : '', feature: null, featureLoading: !!selected, featureError: '', rewardTitle: '', rewardUnavailable: false })
    if (!selected) return
    try {
      // Enrollments include nodes, including previously joined unpublished routes.
      const detail = selected.progress && Array.isArray(selected.progress.nodes) ? selected.progress : await api.request('/quests/' + encodeURIComponent(selected.id))
      if (version !== this.featureVersion || this.disposed) return
      const item = Object.assign({}, selected, detail, { id: selected.id, unavailable: selected.unavailable })
      this.setData({ feature: questView(item, selected.progress), featureLoading: false })
      await Promise.all([this.loadReward(item, version), this.loadMedia(item, selected.progress, version)])
    } catch (_) { if (version === this.featureVersion && !this.disposed) this.setData({ featureError: '这条路线暂时未能加载，请稍后重试。' }) }
    finally { if (version === this.featureVersion && !this.disposed) this.setData({ featureLoading: false }) }
  },
  async loadReward(item, version) {
      if (item.reward_coupon_id) {
        try {
          const reward = await api.request('/coupons/' + encodeURIComponent(item.reward_coupon_id))
          if (version === this.featureVersion && !this.disposed) this.setData({ rewardTitle: reward.title || '', rewardUnavailable: !reward.title })
        } catch (_) {
          if (version === this.featureVersion && !this.disposed) this.setData({ rewardUnavailable: true })
        }
      }
  },
  async loadMedia(item, progress, version) {
    // Only published character/merchant endpoints; unavailable media stays a neutral icon.
    const media = { characters: {}, merchants: {} }
    const requests = []
    for (const [resource, field] of [['characters', 'character_id'], ['merchants', 'merchant_id']]) {
      for (const id of new Set((item.nodes || []).map(node => node[field]).filter(Boolean))) {
        requests.push(async () => {
          try {
            const value = await api.request('/' + resource + '/' + encodeURIComponent(id))
            media[resource][id] = Object.assign({}, value, { image_url: api.mediaUrl(value.image_url) })
          } catch (_) { /* Optional illustration failure must not hide the route. */ }
        })
      }
    }
    for (let offset = 0; offset < requests.length; offset += 4) {
      if (version !== this.featureVersion || this.disposed) return
      await Promise.all(requests.slice(offset, offset + 4).map(load => load()))
    }
    if (version === this.featureVersion && !this.disposed) this.setData({ feature: questView(item, progress, Date.now(), media) })
  },
  mediaFailed(event) {
    const { id, kind } = event.currentTarget.dataset
    if (!this.data.feature || !['glyph_url', 'place_image'].includes(kind)) return
    const feature = this.data.feature
    const nodes = feature.nodes.map(node => node.id === id ? Object.assign({}, node, { [kind]: '' }) : node)
    this.setData({ feature: Object.assign({}, feature, { nodes, next: nodes.find(node => node.is_next) || null }) })
  },
  continueQuest() { if (this.data.feature) this.detail({ currentTarget: { dataset: { id: this.data.feature.item.id } } }) },
  map() { wx.switchTab({ url: '/pages/map/index' }) },
  detail(event) { wx.navigateTo({ url: '/pages/quest/index?id=' + encodeURIComponent(event.currentTarget.dataset.id) }) },
  stamps() { if (session.requireLogin()) wx.navigateTo({ url: '/pages/stamps/index' }) }
})
