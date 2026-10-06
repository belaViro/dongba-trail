// AUTH-01 / CONTENT-01 / FEEDBACK-01 / PRIVACY-01, D-053: copy only, not accuracy.
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const api = require('../utils/api')

test('remote errors never expose Chinese or English implementation messages', () => {
  for (const body of [
    { code: 'UNKNOWN', message: '数据库异常 /srv/private.py' },
    { message: 'Traceback internal SQL' },
    { code: 'constructor', detail: '内部字段' },
  ]) assert.equal(api.errorFrom(503, body).message, '请求未完成，请稍后重试')
  assert.equal(api.errorFrom(422, { detail: 'private_field' }).message, '提交内容不符合要求，请检查后重试')
})
test('known errors retain useful guidance and safe support IDs', () => {
  const error = api.errorFrom(503, { code: 'PROVIDER_UNAVAILABLE', request_id: 'request-test' })
  assert.equal(error.message, '识别服务暂时不可用，请稍后再试')
  assert.equal(error.requestId, 'request-test')
  assert.equal(api.errorFrom(503, { request_id: 'SQL /srv/internal.py' }).requestId, undefined)
})
test('upload failures hide platform internals but retain cancellation diagnostics', async () => {
  const previous = global.wx
  global.wx = {
    getStorageSync() { return { access_token: 'fixture-only' } },
    setStorageSync() {}, removeStorageSync() {},
    uploadFile(options) { options.fail({ errMsg: 'uploadFile:fail internal host path' }) },
  }
  try {
    require('../utils/session').save({ access_token: 'fixture-only', user: { id: 'fixture-user' } })
    await assert.rejects(api.upload('/fixture.png', 'camera'), error => {
      assert.equal(error.message, '图片上传失败，请检查网络后重试')
      assert.equal(error.errMsg, 'uploadFile:fail internal host path')
      return true
    })
  } finally { require('../utils/session').clear(); global.wx = previous }
})
test('page templates contain product guidance rather than development notes', () => {
  const pages = path.resolve(__dirname, '../pages')
  for (const name of fs.readdirSync(pages)) {
    const file = path.join(pages, name, 'index.wxml')
    if (fs.existsSync(file)) assert.doesNotMatch(fs.readFileSync(file, 'utf8'), /参考图|后台字段|统计接口|待实现|尚未接入|暂未接入|占位播放|自动训练模型/, name)
  }
  assert.doesNotMatch(fs.readFileSync(path.join(pages, 'poster/index.wxml'), 'utf8'), /小程序码|二维码|AI\s*(?:辅助|生成)?\s*背景|code-note/i)
  assert.match(fs.readFileSync(path.join(pages, 'privacy/index.wxml'), 'utf8'), /相关授权服务暂不可用/)
  assert.match(fs.readFileSync(path.join(pages, 'result/index.wxml'), 'utf8'), /attachImage/)
})
