const api = require('../../utils/api')
const recognition = require('../../utils/recognition')
const helpers = require('../../utils/helpers')
const platform = require('../../utils/platform')
const session = require('../../utils/session')
Page({
  data: { loading: true, error: '', item: null, nodes: [], progress: null, completed: 0, percent: 0, busy: '', reward: null, closed: false, heroFailed: false },
  onLoad(options) { this.questId = options.id },
  onShow() { this.load() },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  async load() {
    this.setData({ loading: true, error: '', item: null, nodes: [], progress: null, reward: null })
    try {
      const enrollments = session.get() ? await api.collection('/me/quests', {}, true) : []
      const progress = enrollments.find(value => (value.quest_id || value.id) === this.questId) || null
      let item, unavailable = false
      try { item = await api.request('/quests/' + encodeURIComponent(this.questId)) }
      catch (error) {
        if (error.status !== 404 || !progress) throw error
        item = progress; unavailable = true
      }
      const closed = unavailable || (item.start_at && Date.now() < new Date(item.start_at).getTime()) || (item.end_at && Date.now() >= new Date(item.end_at).getTime())
      const completedIds = progress && progress.completed_node_ids || []
      const ordered = (item.nodes || []).slice().sort((a,b) => a.sequence - b.sequence)
      const next = ordered.find(value => !completedIds.includes(value.id))
      const nodes = ordered.map(value => Object.assign({}, value, { is_next: !!next && value.id === next.id, completed: completedIds.includes(value.id) }))
      const completed = nodes.filter(value => value.completed).length
      this.setData({ item, nodes, progress, completed, closed: !!closed, percent: nodes.length ? Math.round(completed / nodes.length * 100) : 0 })
      if (!unavailable) api.track('quest_view', { entity_type: 'quests', entity_id: this.questId })
      if (progress && progress.reward_claim_id) {
        const coupons = await api.collection('/me/coupons', {}, true)
        this.setData({ reward: coupons.find(value => value.id === progress.reward_claim_id) || null })
      }
    } catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  async join() {
    if (!session.requireLogin() || this.data.busy || this.data.closed) return
    this.setData({ busy: 'join' })
    try { await api.request('/quests/' + encodeURIComponent(this.questId) + '/join', { method: 'POST', auth: true }); await this.load() }
    catch (error) { api.showError(error) }
    finally { this.setData({ busy: '' }) }
  },
  async checkin(event) {
    if (!session.requireLogin() || this.data.busy || this.data.closed) return
    if (!this.data.progress) { api.showError(new Error('请先加入这条寻迹路线')); return }
    const node = this.data.nodes.find(value => value.id === event.currentTarget.dataset.id)
    if (!node || node.completed) return
    if (node.condition === 'recognition') {
      recognition.chooseCamera({ quest: this.questId, node: node.id }); return
    }
    if (node.condition === 'manual') {
      const userId = session.get().user.id
      wx.showModal({ title: '人工确认任务', content: '完成活动后，请向现场运营人员出示寻迹编号：' + userId, confirmText: '复制编号', cancelText: '关闭', success: result => {
        if (result.confirm && session.get() && session.get().user.id === userId) wx.setClipboardData({ data: userId })
      } })
      return
    }
    this.setData({ busy: node.id })
    try {
      let values = {}
      if (node.condition === 'qr') {
        const scan = await platform.call('scanCode', { onlyFromCamera: true, scanType: ['qrCode'] })
        values.qr_token = scan.result
      } else if (node.condition === 'geofence') values = await platform.locate()
      else if (node.condition === 'coupon') {
        const coupons = (await api.collection('/me/coupons', {}, true)).filter(value => value.status === 'used' && (!node.merchant_id || value.merchant_id === node.merchant_id) && value.verified_at && new Date(value.verified_at) >= new Date(this.data.progress.joined_at))
        if (!coupons.length) throw new Error('请先在指定商户完成优惠券核销')
        const choice = await platform.call('showActionSheet', { itemList: coupons.slice(0,6).map(value => value.title || value.code) })
        values.claim_id = coupons[choice.tapIndex].id
      }
      await api.request('/quests/' + encodeURIComponent(this.questId) + '/checkin', { method: 'POST', auth: true, data: helpers.checkinPayload(node, values) })
      wx.showToast({ title: '已获得印记', icon: 'success' }); await this.load()
    } catch (error) { if (!/cancel/.test(error.errMsg || '')) api.showError(error.message ? error : new Error('操作未完成，请检查授权或稍后重试')) }
    finally { this.setData({ busy: '' }) }
  },
  onHeroError() { this.setData({ heroFailed: true }) },
  merchant(event) { if (event.currentTarget.dataset.id) wx.navigateTo({ url: '/pages/merchant/index?id=' + encodeURIComponent(event.currentTarget.dataset.id) }) },
  async navigateNode(event) {
    const node = this.data.nodes.find(value => value.id === event.currentTarget.dataset.id)
    if (!node) return
    try {
      const points = await api.all('/map/pois')
      const point = points.find(value => value.id === node.poi_id)
      if (!point) throw new Error('任务地点暂不可导航，请联系现场运营人员')
      await platform.navigate(point)
    } catch (error) { api.showError(error) }
  },
  wallet() { wx.navigateTo({ url: '/pages/coupons/index' }) },
  async retryReward() {
    if (this.data.busy || !this.data.progress || !this.data.progress.reward_pending) return
    const nodeId = this.data.progress.completed_node_ids[0]
    if (!nodeId) return
    this.setData({ busy: 'reward' })
    try {
      await api.request('/quests/' + encodeURIComponent(this.questId) + '/checkin', { method: 'POST', auth: true, data: { node_id: nodeId } })
      await this.load()
      if (this.data.progress.reward_pending) api.showError(new Error('奖励仍待补充，请稍后重试'))
    } catch (error) { api.showError(error) }
    finally { this.setData({ busy: '' }) }
  },
  share() { if (session.requireLogin()) wx.navigateTo({ url: '/pages/poster/index' }) }
})
