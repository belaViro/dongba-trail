const session = require('./utils/session')
App({
  globalData: { recognition: null, recognitionImage: '', activeQuest: null },
  onLaunch() {
    session.restore()
    if (wx.onNeedPrivacyAuthorization) {
      wx.onNeedPrivacyAuthorization(resolve => {
        const pages = getCurrentPages()
        const page = pages[pages.length - 1]
        if (page && page.onPrivacyAuthorizationNeeded) {
          page.onPrivacyAuthorizationNeeded(resolve)
          return
        }
        this.globalData.privacyResolve = resolve
        wx.navigateTo({ url: '/pages/privacy/index?authorize=1' })
      })
    }
  }
})
