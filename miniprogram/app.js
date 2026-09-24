const session = require('./utils/session')
App({
  globalData: { recognition: null, recognitionImage: '', activeQuest: null },
  onLaunch() {
    session.restore()
    if (wx.onNeedPrivacyAuthorization) {
      wx.onNeedPrivacyAuthorization(resolve => {
        this.globalData.privacyResolve = resolve
        wx.navigateTo({ url: '/pages/privacy/index?authorize=1' })
      })
    }
  }
})
