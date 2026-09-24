const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
const session = require('../../utils/session')
Page({
  data: { loading: true, error: '', items: [], filter: 'all', all: [] },
  onShow() { this.load() },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const quests = await api.all('/quests')
      const enrolled = session.get() ? await api.collection('/me/quests', {}, true) : []
      const known = new Set(quests.map(item => item.id))
      const combined = quests.concat(enrolled.filter(item => !known.has(item.quest_id || item.id)))
      const all = combined.map(item => {
        const progress = enrolled.find(value => (value.quest_id || value.id) === item.id)
        return Object.assign({}, item, { progress, start_date: helpers.date(item.start_at), end_date: helpers.date(item.end_at), completed: progress && progress.completed_node_ids ? progress.completed_node_ids.length : 0 })
      })
      this.setData({ all }); this.applyFilter()
    } catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  filter(event) {
    const filter = event.currentTarget.dataset.type
    if (filter === 'mine' && !session.requireLogin()) return
    this.setData({ filter }); this.applyFilter()
  },
  applyFilter() { this.setData({ items: this.data.all.filter(item => this.data.filter === 'all' || !!item.progress) }) },
  detail(event) { wx.navigateTo({ url: '/pages/quest/index?id=' + encodeURIComponent(event.currentTarget.dataset.id) }) },
  stamps() { if (session.requireLogin()) wx.navigateTo({ url: '/pages/stamps/index' }) }
})
