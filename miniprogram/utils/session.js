let current = null
function restore() {
  const saved = wx.getStorageSync('dongba_session')
  current = saved && typeof saved.access_token === 'string' && saved.user ? saved : null
  return current
}
function get() { return current }
function clearPrivateMemory() {
  const app = typeof getApp === 'function' ? getApp() : null
  if (app && app.globalData) {
    app.globalData.recognition = null; app.globalData.recognitionImage = ''; app.globalData.activeQuest = null
  }
}
function save(value) { if (current && current.user.id !== value.user.id) clearPrivateMemory(); current = value; wx.setStorageSync('dongba_session', value) }
function clear() { current = null; wx.removeStorageSync('dongba_session'); clearPrivateMemory() }
function requireLogin() {
  if (current) return true
  wx.navigateTo({ url: '/pages/login/index' })
  return false
}
module.exports = { restore, get, save, clear, requireLogin }
