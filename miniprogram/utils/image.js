// MINI-01 / AI-01, D-065: normalize phone photos before recognition.
// Camera and album images are captured at original resolution (compressed
// copies lost the strokes that distinguish similar Dongba glyphs), then
// downscaled locally to a bounded long edge so uploads stay small enough.
// Small crops are never upscaled: interpolation cannot add lost strokes and
// would only make a blurry glyph look like a different character.
const MAX_EDGE = 1200
// Offscreen canvas reserved for cropping; must cover the largest crop we export.
const CANVAS_EDGE = 1200

function fit(width, height, maxWidth, maxHeight) {
  const safeWidth = Number(width) > 0 ? Number(width) : 1
  const safeHeight = Number(height) > 0 ? Number(height) : 1
  const scale = Math.min(maxWidth / safeWidth, maxHeight / safeHeight)
  return {
    width: safeWidth * scale,
    height: safeHeight * scale,
    left: (maxWidth - safeWidth * scale) / 2,
    top: (maxHeight - safeHeight * scale) / 2,
    scale
  }
}

function targetSize(width, height, maxEdge) {
  const limit = Number(maxEdge) > 0 ? Number(maxEdge) : MAX_EDGE
  const sourceWidth = Math.max(1, Math.round(Number(width) || 1))
  const sourceHeight = Math.max(1, Math.round(Number(height) || 1))
  const longest = Math.max(sourceWidth, sourceHeight)
  const scale = longest > limit ? limit / longest : 1
  return { width: Math.max(1, Math.round(sourceWidth * scale)), height: Math.max(1, Math.round(sourceHeight * scale)) }
}

function info(path) {
  return new Promise(resolve => {
    if (!wx.getImageInfo) { resolve(null); return }
    wx.getImageInfo({ src: path, success: value => resolve({ width: Number(value.width) || 0, height: Number(value.height) || 0, path: value.path || path }), fail: () => resolve(null) })
  })
}

function crop(page, path, region, size) {
  return new Promise((resolve, reject) => {
    if (!wx.createCanvasContext || !wx.canvasToTempFilePath) { reject(new Error('当前微信版本暂不支持裁剪，请更新微信后重试')); return }
    const context = wx.createCanvasContext('crop-canvas', page)
    context.drawImage(path, region.x, region.y, region.width, region.height, 0, 0, size.width, size.height)
    context.draw(false, () => {
      wx.canvasToTempFilePath({
        canvasId: 'crop-canvas', x: 0, y: 0, width: size.width, height: size.height,
        destWidth: size.width, destHeight: size.height, fileType: 'jpg', quality: 0.95,
        success: result => resolve(result.tempFilePath),
        fail: () => reject(new Error('图片裁剪失败，请重新拍摄'))
      }, page)
    })
  })
}

module.exports = { MAX_EDGE, CANVAS_EDGE, fit, targetSize, info, crop }
