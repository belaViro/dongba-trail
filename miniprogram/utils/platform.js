function call(method, options) {
  return new Promise((resolve, reject) => wx[method](Object.assign({}, options || {}, { success: resolve, fail: reject })))
}
async function privacy() {
  if (!wx.requirePrivacyAuthorize) return
  try { await call('requirePrivacyAuthorize') }
  catch (_) { throw new Error('需要同意微信隐私保护指引后继续') }
}
async function locate() {
  await privacy()
  try { return await call('getLocation', { type: 'gcj02', isHighAccuracy: true }) }
  catch (_) { throw new Error('未获得位置授权，可在微信设置中开启后重试') }
}
async function navigate(place) {
  const { coordinates } = require('./helpers')
  if (!coordinates(place)) throw new Error('该地点尚未提供可用坐标')
  await privacy()
  return call('openLocation', { latitude: Number(place.latitude), longitude: Number(place.longitude), name: place.name, address: place.address || '', scale: 17 })
}
function openSettings() { return call('openSetting') }
module.exports = { call, privacy, locate, navigate, openSettings }

