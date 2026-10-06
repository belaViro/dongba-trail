// MINI-01 / AI-01 / AI-03, D-065: capture with corner framing, crop, then recognize.
// The camera is a native <camera> component so the shot keeps original detail
// (compressed chooseImage copies lost Dongba stroke detail); the user frames the
// glyph with the four corner brackets and can also pick an existing album photo.
const api = require('../../utils/api')
const image = require('../../utils/image')
const session = require('../../utils/session')

const MIN_FRAME = 80
// D-065: keep this in sync with backend quality_min_edge. A crop below it is
// rejected as IMAGE_TOO_SMALL, so warn here instead of after an upload.
const MIN_SOURCE_SIDE = 200

function clamp(value, min, max) { return Math.min(max, Math.max(min, value)) }

Page({
  data: {
    view: 'camera', facing: 'back', flash: 'off', ready: false, busy: false, error: '',
    stage: null, display: null, frame: null, cropPath: '', source: '', safeTop: 0, safeBottom: 0
  },
  onLoad(options) {
    this.options = options || {}
    const app = getApp()
    app.globalData.activeQuest = this.options.quest && this.options.node ? { quest_id: this.options.quest, node_id: this.options.node } : null
    const system = wx.getWindowInfo ? wx.getWindowInfo() : (wx.getSystemInfoSync ? wx.getSystemInfoSync() : null)
    const safe = system && system.safeArea ? Math.max(0, (Number(system.screenHeight) || system.windowHeight) - system.safeArea.bottom) : 0
    this.setData({
      source: this.options.source === 'album' ? 'album' : 'camera',
      safeTop: system ? Number(system.statusBarHeight) || 0 : 0,
      safeBottom: safe
    })
    if (this.options.source === 'album') this.album()
  },
  onUnload() { this.stopped = true },
  cameraError() { this.setData({ error: '相机暂不可用，请检查相机权限或改用相册选图' }) },
  flip() { this.setData({ facing: this.data.facing === 'back' ? 'front' : 'back' }) },
  toggleFlash() { this.setData({ flash: this.data.flash === 'on' ? 'off' : 'on' }) },
  close() { wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/home/index' }) }) },
  async album() {
    if (this.data.busy) return
    this.setData({ busy: true, error: '' })
    try {
      const result = await new Promise((resolve, reject) => wx.chooseImage({ count: 1, sourceType: ['album'], sizeType: ['original'], success: resolve, fail: reject }))
      const path = result.tempFilePaths && result.tempFilePaths[0]
      if (!path) throw new Error('未取得图片，请重新选择')
      this.setData({ source: 'album' })
      await this.stage(path)
    } catch (error) {
      if (!/cancel/i.test(error.errMsg || '')) this.setData({ error: error.message || '无法读取相册图片' })
    } finally { this.setData({ busy: false }) }
  },
  shoot() {
    if (this.data.busy) return
    const context = wx.createCameraContext && wx.createCameraContext()
    if (!context) { this.setData({ error: '当前微信版本暂不支持拍照，请改用相册选图' }); return }
    this.setData({ busy: true, error: '', source: 'camera' })
    context.takePhoto({
      quality: 'high',
      success: result => { this.stage(result.tempImagePath).catch(error => this.setData({ error: error.message, busy: false })) },
      fail: () => this.setData({ busy: false, error: '拍照失败，请重试或改用相册选图' })
    })
  },
  async stage(path) {
    const info = await image.info(path)
    if (!info || !info.width || !info.height) { this.setData({ busy: false, error: '图片无法读取，请重新选择' }); return }
    const resolved = info.path || path
    const rect = this.stageRect()
    if (rect) { this.applyStage(rect, info, resolved); return }
    const measured = await this.measureStage(resolved)
    if (measured) this.applyStage(measured, info, resolved)
  },
  stageRect() {
    // The crop stage only exists after the crop view renders, so its measured
    // height is 0 on the first paint. Derive a deterministic size from the
    // window instead, reserving header/tip/action space and the status bar.
    const system = wx.getWindowInfo ? wx.getWindowInfo() : (wx.getSystemInfoSync ? wx.getSystemInfoSync() : null)
    if (!system || !system.windowWidth || !system.windowHeight) return null
    const unit = system.windowWidth / 750
    const reserved = 400 * unit + (Number(system.statusBarHeight) || 0) + (Number(this.data.safeBottom) || 0)
    return { width: system.windowWidth, height: Math.max(220, system.windowHeight - reserved) }
  },
  async measureStage(path) {
    this.setData({ view: 'crop', cropPath: path, ready: true, stage: null })
    const rect = await new Promise(resolve => {
      const measure = () => wx.createSelectorQuery().select('.crop-stage').boundingClientRect(value => resolve(value)).exec()
      if (wx.nextTick) wx.nextTick(measure); else setTimeout(measure, 0)
    })
    if (!rect || !rect.width || !rect.height) { this.setData({ busy: false, error: '页面尺寸获取失败，请重试' }); return null }
    return rect
  },
  applyStage(rect, info, path) {
    // The visible stage height cannot be measured before first paint. Only
    // trust a rect tall enough to hold a usable frame; otherwise fall back to
    // the deterministic window-derived size.
    const usable = rect && rect.width && rect.height >= MIN_FRAME * 2
    const stage = usable ? { width: rect.width, height: rect.height } : this.stageRect()
    if (!stage) { this.setData({ busy: false, error: '页面尺寸获取失败，请重试' }); return }
    const display = image.fit(info.width, info.height, stage.width, stage.height)
    const side = Math.max(1, Math.round(Math.min(display.width, display.height) * 0.72))
    const frame = {
      x: Math.round(display.left + (display.width - side) / 2),
      y: Math.round(display.top + (display.height - side) / 2),
      width: side, height: side
    }
    this.setData({ view: 'crop', cropPath: path, ready: true, busy: false, error: '', stage, display, frame })
  },
  touchStart(event) {
    const touch = event.touches && event.touches[0]
    if (!touch || !this.data.frame) return
    this.drag = { role: event.currentTarget.dataset.role || 'move', startX: touch.clientX, startY: touch.clientY, frame: Object.assign({}, this.data.frame) }
  },
  touchMove(event) {
    if (!this.drag) return
    const touch = event.touches && event.touches[0]
    if (!touch) return
    const dx = touch.clientX - this.drag.startX
    const dy = touch.clientY - this.drag.startY
    const start = this.drag.frame
    const display = this.data.display
    const bounds = { left: display.left, top: display.top, right: display.left + display.width, bottom: display.top + display.height }
    let frame
    if (this.drag.role === 'move') {
      frame = { x: clamp(start.x + dx, bounds.left, bounds.right - start.width), y: clamp(start.y + dy, bounds.top, bounds.bottom - start.height), width: start.width, height: start.height }
    } else {
      const left = start.x, top = start.y, right = start.x + start.width, bottom = start.y + start.height
      let x1 = left, y1 = top, x2 = right, y2 = bottom
      if (this.drag.role.includes('w')) x1 = clamp(left + dx, bounds.left, right - MIN_FRAME)
      if (this.drag.role.includes('e')) x2 = clamp(right + dx, left + MIN_FRAME, bounds.right)
      if (this.drag.role.includes('n')) y1 = clamp(top + dy, bounds.top, bottom - MIN_FRAME)
      if (this.drag.role.includes('s')) y2 = clamp(bottom + dy, top + MIN_FRAME, bounds.bottom)
      frame = { x: x1, y: y1, width: x2 - x1, height: y2 - y1 }
    }
    this.setData({ frame })
  },
  touchEnd() { this.drag = null },
  reset() { this.stage(this.data.cropPath) },
  retake() { this.setData({ view: 'camera', cropPath: '', ready: false, frame: null, display: null, stage: null, busy: false, error: '' }) },
  async confirm() {
    if (this.data.busy || !this.data.frame || !this.data.display) return
    // Frame size is in display pixels, so divide by the display scale to get
    // the source-pixel region. A crop below the backend floor is rejected as
    // IMAGE_TOO_SMALL, so keep the user on this page and explain instead.
    const sourceWidth = this.data.frame.width / this.data.display.scale
    const sourceHeight = this.data.frame.height / this.data.display.scale
    if (Math.round(Math.min(sourceWidth, sourceHeight)) < MIN_SOURCE_SIDE) {
      this.setData({ error: '框选范围太小，请把取景框放大到包含完整字形' })
      return
    }
    if (!session.requireLogin()) return
    this.setData({ busy: true, error: '' })
    if (wx.showLoading) wx.showLoading({ title: '正在识别', mask: true })
    try {
      const size = image.targetSize(sourceWidth, sourceHeight)
      const region = {
        x: (this.data.frame.x - this.data.display.left) / this.data.display.scale,
        y: (this.data.frame.y - this.data.display.top) / this.data.display.scale,
        width: this.data.frame.width / this.data.display.scale,
        height: this.data.frame.height / this.data.display.scale
      }
      const cropped = await image.crop(this, this.data.cropPath, region, size)
      const app = getApp()
      app.globalData.recognitionImage = cropped
      app.globalData.recognition = await api.upload(cropped, this.data.source === 'album' ? 'album' : 'camera')
      wx.navigateTo({ url: '/pages/result/index' })
    } catch (error) {
      if (!/cancel/i.test(error.errMsg || '')) this.setData({ error: error.message || '识别失败，请重试' })
    } finally {
      if (wx.hideLoading) wx.hideLoading()
      this.setData({ busy: false })
    }
  }
})
