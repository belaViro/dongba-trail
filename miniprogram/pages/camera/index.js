const api = require('../../utils/api')
const platform = require('../../utils/platform')
const session = require('../../utils/session')
const config = require('../../config')
const samples = require('../../utils/samples')
Page({
  data: { allowed: false, image: '', scene: 'camera', flash: 'off', busy: false, error: '', requestId: '', cameraError: false, sampleConsent: false, sampleSceneIndex: 0, sampleScenes: samples.scenes },
  onLoad(options) {
    getApp().globalData.activeQuest = options.quest && options.node ? { quest_id: options.quest, node_id: options.node } : null
  },
  async authorize() {
    if (!session.requireLogin()) return
    this.setData({ error: '' })
    try {
      const policy = await api.request('/privacy')
      if (!policy.published) throw new Error('隐私保护指引尚未发布，暂时无法上传图片')
      if (wx.getStorageSync('dongba_privacy_version') !== policy.version) {
        wx.navigateTo({ url: '/pages/privacy/index?authorize=1' }); return
      }
      await platform.privacy()
      this.setData({ allowed: true })
    } catch (error) { this.setData({ error: error.message }) }
  },
  cameraError() { this.setData({ cameraError: true, error: '相机未获得授权，可从相册选取，或前往微信设置开启相机权限' }) },
  settings() { platform.openSettings().catch(api.showError) },
  flash() { this.setData({ flash: this.data.flash === 'off' ? 'torch' : 'off' }) },
  capture() {
    if (!this.data.allowed || this.data.busy) return
    wx.createCameraContext().takePhoto({
      quality: 'high',
      success: response => this.setData({ image: response.tempImagePath, scene: 'camera', error: '', flash: 'off', sampleConsent: false, sampleSceneIndex: 0 }),
      fail: () => this.setData({ error: '拍照失败，请重试或从相册选择' })
    })
  },
  async album() {
    if (!this.data.allowed) { await this.authorize(); if (!this.data.allowed) return }
    try {
      const result = await platform.call('chooseMedia', { count: 1, mediaType: ['image'], sourceType: ['album'], sizeType: ['compressed'] })
      const file = result.tempFiles[0]
      if (file.size > config.maxImageBytes) throw new Error('图片过大，请选择不超过 8 MB 的图片')
      this.setData({ image: file.tempFilePath, scene: 'album', error: '', sampleConsent: false, sampleSceneIndex: 0 })
    } catch (error) { if (!/cancel/.test(error.errMsg || '')) this.setData({ error: error.message || '无法访问相册，请检查授权后重试' }) }
  },
  retake() { this.setData({ image: '', error: '', requestId: '', sampleConsent: false, sampleSceneIndex: 0 }) },
  sampleConsent(event) { if (!this.data.busy) this.setData({ sampleConsent: event.detail.value === true }) },
  sampleScene(event) {
    const index = Number(event.detail.value)
    if (!this.data.busy && samples.scenes[index]) this.setData({ sampleSceneIndex: index })
  },
  async recognize() {
    if (this.data.busy || !this.data.image) return
    this.setData({ busy: true, error: '', requestId: '' })
    try {
      const result = await api.upload(this.data.image, this.data.scene, { sampleConsent: this.data.sampleConsent, sampleScene: samples.scenes[this.data.sampleSceneIndex].value })
      const app = getApp()
      app.globalData.recognition = result; app.globalData.recognitionImage = this.data.image
      wx.navigateTo({ url: '/pages/result/index' })
    } catch (error) { this.setData({ error: error.message, requestId: error.requestId || '' }) }
    finally { this.setData({ busy: false }) }
  },
  policy() { wx.navigateTo({ url: '/pages/privacy/index' }) }
})
