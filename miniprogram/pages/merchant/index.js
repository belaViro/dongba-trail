const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
const platform = require('../../utils/platform')
const session = require('../../utils/session')
Page({
  data: { loading: true, error: '', item: null, products: [], coupons: [], activities: [], claiming: '' },
  onLoad(options) { this.merchantId = options.id; this.recognitionId = options.recognition_id; this.load() },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const [item, products, coupons, activities] = await Promise.all([
        api.request('/merchants/' + encodeURIComponent(this.merchantId)),
        api.collection('/products', { merchant_id: this.merchantId }),
        api.collection('/coupons', { merchant_id: this.merchantId }),
        api.collection('/activities', { merchant_id: this.merchantId })
      ])
      item.image_url = api.mediaUrl(item.image_url)
      this.setData({ item, products: products.map(value => Object.assign({}, value, { image_url: api.mediaUrl(value.image_url) })), coupons: coupons.map(value => Object.assign({}, value, { end_date: helpers.date(value.end_at) })), activities: activities.map(value => Object.assign({}, value, { start_date: helpers.date(value.start_at), end_date: helpers.date(value.end_at) })) })
      api.track('merchant_detail', { entity_type: 'merchants', entity_id: this.merchantId, recognition_id: this.recognitionId || null })
    } catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  async navigate() {
    try { await platform.navigate(this.data.item); api.track('navigate', { entity_type: 'merchants', entity_id: this.merchantId, recognition_id: this.recognitionId || null }) }
    catch (error) { api.showError(error) }
  },
  call() { if (this.data.item.phone) wx.makePhoneCall({ phoneNumber: this.data.item.phone, fail() {} }) },
  async claim(event) {
    if (!session.requireLogin() || this.data.claiming) return
    const id = event.currentTarget.dataset.id; this.setData({ claiming: id })
    try {
      await api.request('/coupons/' + encodeURIComponent(id) + '/claim' + helpers.query({ recognition_id: this.recognitionId }), { method: 'POST', auth: true })
      wx.showToast({ title: '领取成功', icon: 'success' })
    } catch (error) { api.showError(error) }
    finally { this.setData({ claiming: '' }) }
  },
  wallet() { if (session.requireLogin()) wx.navigateTo({ url: '/pages/coupons/index' }) },
  onShareAppMessage() { return { title: this.data.item ? this.data.item.name : '丽江文化商户', path: '/pages/merchant/index?id=' + encodeURIComponent(this.merchantId) } }
})
