const api = require('./api')
const platform = require('./platform')
const session = require('./session')
const config = require('../config')

async function chooseCamera(options) {
  const opts = options || {}
  try {
    const result = await platform.call('chooseImage', {
      count: 1,
      sourceType: ['camera'],
      sizeType: ['compressed']
    })
    const path = result.tempFilePaths && result.tempFilePaths[0]
    const file = result.tempFiles && result.tempFiles[0]
    const tempPath = path || (file && file.tempFilePath)
    if (!tempPath) throw new Error('未取得图片，请重新拍摄')
    if (file && file.size > config.maxImageBytes) throw new Error('图片过大，请选择不超过 8 MB 的图片')
    const app = getApp()
    app.globalData.activeQuest = opts.quest && opts.node ? {
      quest_id: opts.quest,
      node_id: opts.node
    } : null
    app.globalData.recognitionImage = tempPath
    if (!session.requireLogin()) return
    if (wx.showLoading) wx.showLoading({ title: '正在识别', mask: true })
    app.globalData.recognition = await api.upload(tempPath, 'camera')
    wx.navigateTo({ url: '/pages/result/index' })
  } catch (error) {
    if (!/cancel/i.test(error.errMsg || '')) api.showError(error)
  } finally {
    if (wx.hideLoading) wx.hideLoading()
  }
}

module.exports = { chooseCamera }