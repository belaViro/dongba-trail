const api = require('../../utils/api')
const helpers = require('../../utils/helpers')
Page({
  data: { loading: true, error: '', all: [], items: [], filter: 'available', activeCoupon: null, qrImage: '', qrLoading: false, qrError: '' },
  onShow() { this.load() },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()) },
  async load() {
    this.setData({ loading: true, error: '', all: [], items: [], activeCoupon: null, qrImage: '', qrError: '' })
    try {
      const all = (await api.collection('/me/coupons', {}, true)).map(item => Object.assign({}, item, { end_date: helpers.date(item.end_at || item.coupon && item.coupon.end_at), state_text: ({ available: '待使用', used: '已使用', expired: '已过期' })[item.status] || item.status }))
      this.setData({ all }); this.applyFilter()
    } catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loading: false }) }
  },
  filter(event) { this.setData({ filter: event.currentTarget.dataset.type }); this.applyFilter() },
  applyFilter() { this.setData({ items: this.data.all.filter(item => item.status === this.data.filter) }) },
  async code(event) {
    const item = this.data.items.find(value => value.id === event.currentTarget.dataset.id)
    if (!item || item.status !== 'available') return
    this.setData({ activeCoupon: item, qrImage: '', qrError: '' })
    await this.loadCode()
  },
  async loadCode() {
    const item = this.data.activeCoupon
    if (!item || this.data.qrLoading) return
    this.setData({ qrLoading: true, qrError: '' })
    try {
      const qrImage = await api.downloadPrivate('/me/coupons/' + encodeURIComponent(item.id) + '/qr')
      if (this.data.activeCoupon && this.data.activeCoupon.id === item.id) this.setData({ qrImage })
    } catch (error) { this.setData({ qrError: error.message }) }
    finally { this.setData({ qrLoading: false }) }
  },
  copyCode() { if (this.data.activeCoupon) wx.setClipboardData({ data: this.data.activeCoupon.code }) },
  closeCode() { this.setData({ activeCoupon: null, qrImage: '', qrError: '' }) },
  merchant(event) { wx.navigateTo({ url: '/pages/merchant/index?id=' + encodeURIComponent(event.currentTarget.dataset.id) }) }
})
