const test = require('node:test')
const assert = require('node:assert/strict')

global.wx = {}
const image = require('../utils/image')

test('fit keeps the photo aspect ratio and centers it in the stage', () => {
  const fitted = image.fit(4000, 3000, 375, 480)
  assert.equal(Math.round(fitted.width), 375)
  assert.equal(Math.round(fitted.height), 281)
  assert.equal(Math.round(fitted.left), 0)
  assert.equal(Math.round(fitted.top), 99)
  assert.ok(fitted.scale > 0 && fitted.scale < 1)
  const invalid = image.fit(null, undefined, 375, 480)
  assert.ok(Number.isFinite(invalid.width) && invalid.width > 0)
  assert.ok(Number.isFinite(invalid.height) && invalid.height > 0)
})

test('targetSize bounds the long edge and never upscales small crops', () => {
  assert.deepEqual(image.targetSize(2155, 2155), { width: 1200, height: 1200 })
  assert.deepEqual(image.targetSize(4000, 3000), { width: 1200, height: 900 })
  assert.deepEqual(image.targetSize(300, 300), { width: 300, height: 300 })
  assert.deepEqual(image.targetSize(229, 180), { width: 229, height: 180 })
  assert.deepEqual(image.targetSize(1200, 1200), { width: 1200, height: 1200 })
})

test('image info resolves dimensions, and crop fails explicitly without canvas support', async () => {
  wx.getImageInfo = options => options.success({ width: '640', height: 480 })
  assert.deepEqual(await image.info('/tmp/a.png'), { width: 640, height: 480, path: '/tmp/a.png' })
  wx.getImageInfo = options => options.fail({ errMsg: 'read fail' })
  assert.equal(await image.info('/tmp/a.png'), null)
  delete wx.getImageInfo
  assert.equal(await image.info('/tmp/a.png'), null)
  await assert.rejects(
    image.crop({}, '/tmp/a.png', { x: 0, y: 0, width: 10, height: 10 }, { width: 10, height: 10 }),
    /裁剪/
  )
})

test('crop draws only the requested source region and exports a high-quality jpg', async () => {
  const calls = []
  wx.createCanvasContext = () => ({
    drawImage: (...args) => calls.push(args),
    draw(_keep, callback) { callback() }
  })
  wx.canvasToTempFilePath = options => { calls.push(options); options.success({ tempFilePath: '/out.jpg' }) }
  const path = await image.crop({}, '/src.png', { x: 10, y: 20, width: 30, height: 40 }, { width: 512, height: 512 })
  assert.equal(path, '/out.jpg')
  assert.deepEqual(calls[0], ['/src.png', 10, 20, 30, 40, 0, 0, 512, 512])
  assert.equal(calls[1].canvasId, 'crop-canvas')
  assert.equal(calls[1].fileType, 'jpg')
  assert.equal(calls[1].quality, 0.95)
  assert.equal(calls[1].destWidth, 512)
})
