const config = require('../config')
const session = require('./session')
const helpers = require('./helpers')
const errors = {
  AUTH_REQUIRED: '请先登录后继续', SESSION_EXPIRED: '登录已过期，请重新登录',
  WECHAT_NOT_CONFIGURED: '微信登录服务暂未开通', PROVIDER_NOT_CONFIGURED: '识别服务暂未开通',
  DICTIONARY_NOT_READY: '字典内容正在审核，暂时无法识别', PROVIDER_TIMEOUT: '识别等待超时，请稍后重试',
  PROVIDER_UNAVAILABLE: '识别服务暂时不可用，请稍后再试', PROVIDER_INVALID_RESPONSE: '未获得有效识别结果，请重新拍摄',
  IMAGE_TOO_LARGE: '图片超过上传大小限制', INVALID_IMAGE: '图片无法读取，请重新选择',
  UNSUPPORTED_IMAGE: '请选择 JPEG、PNG 或 WebP 图片', IMAGE_TOO_SMALL: '目标过小，请靠近后重拍',
  IMAGE_BLURRY: '图片较模糊，请保持稳定后重拍', IMAGE_TOO_DARK: '光线较暗，请调整后重拍',
  IMAGE_OVEREXPOSED: '图片过亮，请避开强光后重拍', RATE_LIMITED: '操作过于频繁，请稍后再试',
  COUPON_OUT_OF_STOCK: '优惠券已领完', COUPON_EXPIRED: '优惠券已过期', CLAIM_LIMIT_REACHED: '已达到领取上限',
  OUTSIDE_GEOFENCE: '尚未到达任务地点', PRIVACY_NOT_CONFIGURED: '隐私保护指引尚未发布，暂时无法上传'
}
Object.assign(errors, {
  INVALID_PROVIDER_RESPONSE: '未获得有效识别结果，请重新拍摄', PROVIDER_ERROR: '识别服务暂时异常，请稍后重试',
  PRIVACY_NOT_PUBLISHED: '隐私保护指引尚未发布，暂时无法登录', PRIVACY_REQUIRED: '请阅读并同意隐私保护指引',
  WECHAT_UNAVAILABLE: '微信登录服务暂时不可用', WECHAT_CODE_INVALID: '微信登录凭据已失效，请重新登录',
  ACCOUNT_UNAVAILABLE: '当前账号不可用，请联系运营方', FORBIDDEN: '当前账号没有操作权限',
  NOT_FOUND: '内容不存在或已下架', CHARACTER_NOT_FOUND: '东巴字内容已下架', RECOGNITION_NOT_FOUND: '识别记录不存在或已清除',
  CLAIM_LIMIT: '已达到优惠券领取上限', SOLD_OUT: '优惠券已领完', NOT_ACTIVE: '当前活动尚未开始或已结束',
  COUPON_UNAVAILABLE: '优惠券暂不可使用', QR_INVALID: '二维码与当前任务不匹配',
  RECOGNITION_REQUIRED: '请先识别并确认本节点对应的东巴字', REDEMPTION_REQUIRED: '请先在指定商户完成优惠券核销',
  JOIN_REQUIRED: '请先加入寻迹路线', QUEST_NO_NODES: '路线暂不可用，请稍后重试', MANUAL_REQUIRED: '此节点需要现场运营人员确认',
  CANDIDATE_INVALID: '候选项已失效，请重新识别', FEEDBACK_REVIEWED: '该反馈已完成审核，不能再修改',
  CHARACTER_NOT_COLLECTED: '请选择已确认或收藏的东巴字', CHARACTER_IMAGE_UNAVAILABLE: '所选东巴字暂缺可用字形图片',
  POSTER_FONT_UNAVAILABLE: '海报服务暂时不可用', WECHAT_SHARE_UNAVAILABLE: '小程序分享码暂时生成失败，请稍后重试',
  IMAGE_PROVIDER_UNCONFIGURED: 'AI 海报暂未开放，请稍后再来',
  IMAGE_PROVIDER_AUTH_FAILED: 'AI 海报服务暂不可用，请稍后重试',
  IMAGE_PROVIDER_BUSY: '创作人数较多，请稍后重试',
  IMAGE_PROVIDER_TIMEOUT: '本次创作超时，请稍后重新生成',
  IMAGE_PROVIDER_UNAVAILABLE: 'AI 创作暂未完成，请稍后重试',
  IMAGE_PROVIDER_INVALID_RESPONSE: '本次未生成可用图片，请重试',
  POSTER_REQUEST_CONFLICT: '创作内容已变更，请重新生成',
  LOCATION_REQUIRED: '请授权当前位置后重试', PLACE_NOT_CONFIGURED: '任务地点尚未提供已确认坐标', INVALID_REQUEST: '提交内容不完整，请检查后重试',
  SAMPLE_NOT_FOUND: '图片样本不存在或已删除', SAMPLE_CONSENT_REQUIRED: '请先同意保存本次照片作为纠错附图'
})
function errorFrom(status, body) {
  const code = body && body.code || 'REQUEST_FAILED'
  const error = new Error(Object.prototype.hasOwnProperty.call(errors, code) ? errors[code] : status === 422 ? '提交内容不符合要求，请检查后重试' : '请求未完成，请稍后重试')
  error.code = code; error.requestId = body && typeof body.request_id === 'string' && /^[a-zA-Z0-9_-]{1,80}$/.test(body.request_id) ? body.request_id : undefined; error.status = status
  if (status === 401) session.clear()
  return error
}
function request(path, options) {
  const opts = options || {}
  return new Promise((resolve, reject) => {
    const auth = session.get()
    if (opts.auth && !auth) { reject(errorFrom(401, { code: 'AUTH_REQUIRED' })); return }
    wx.request({
      url: config.apiBase + path, method: opts.method || 'GET', data: opts.data,
      timeout: config.requestTimeout,
      header: Object.assign({ 'Content-Type': 'application/json' }, auth ? { Authorization: 'Bearer ' + auth.access_token } : {}),
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) resolve(response.data)
        else reject(errorFrom(response.statusCode, response.data))
      },
      fail() { const error = new Error('网络连接失败，请检查网络后重试'); error.code = 'NETWORK_ERROR'; reject(error) }
    })
  })
}
function upload(filePath, scene, options) {
  const opts = options || {}
  const formData = { scene: scene === 'album' ? 'album' : 'camera' }
  if (opts.sampleConsent === true) {
    formData.sample_consent = 'true'
    formData.sample_scene = opts.sampleScene || 'other'
  }
  return uploadImage('/recognize', filePath, formData)
}
function uploadFeedbackImage(recognitionId, filePath, consent) {
  if (consent !== true) return Promise.reject(errorFrom(422, { code: 'SAMPLE_CONSENT_REQUIRED' }))
  return uploadImage('/recognize/' + encodeURIComponent(recognitionId) + '/image', filePath, { sample_consent: 'true' })
}
function uploadImage(path, filePath, formData) {
  return new Promise((resolve, reject) => {
    const auth = session.get()
    if (!auth) { reject(errorFrom(401, { code: 'AUTH_REQUIRED' })); return }
    wx.uploadFile({
      url: config.apiBase + path, filePath, name: 'image',
      formData, timeout: config.recognitionTimeout,
      header: { Authorization: 'Bearer ' + auth.access_token },
      success(response) {
        let body
        try { body = JSON.parse(response.data) } catch (_) { reject(errorFrom(502, {})); return }
        if (response.statusCode >= 200 && response.statusCode < 300) resolve(body)
        else reject(errorFrom(response.statusCode, body))
      },
      fail(error) {
        const detail = error && error.errMsg ? error.errMsg : ''
        const failure = new Error('图片上传失败，请检查网络后重试')
        failure.code = 'NETWORK_ERROR'
        failure.errMsg = detail
        reject(failure)
      }
    })
  })
}
function downloadPrivate(path, options) {
  const opts = options || {}
  return new Promise((resolve, reject) => {
    const auth = session.get()
    if (!auth) { reject(errorFrom(401, { code: 'AUTH_REQUIRED' })); return }
    wx.downloadFile({
      url: config.apiBase + path, timeout: config.requestTimeout,
      header: { Authorization: 'Bearer ' + auth.access_token },
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) resolve(response.tempFilePath)
        else reject(errorFrom(response.statusCode, { code: response.statusCode === 401 ? 'SESSION_EXPIRED' : opts.errorCode || 'COUPON_UNAVAILABLE' }))
      },
      fail() { reject(new Error((opts.label || '券码') + '加载失败，请检查网络后重试')) }
    })
  })
}
function mediaUrl(value) {
  if (!value) return ''
  // SHARE-01: old completed jobs may cache an internal URL. Retry the same PNG
  // through the configured API origin; never submit a new paid generation.
  const legacy = /^https?:\/\/(?:127\.0\.0\.1|localhost|\[::1\])(?::\d+)?(\/api\/v1\/media\/[a-f0-9]{32}\.png)$/.exec(value)
  if (legacy) value = legacy[1]
  if (/^https?:\/\//.test(value) || value.startsWith('wxfile:') || value.startsWith('/assets/')) return value
  return config.apiBase.replace(/\/api\/v1\/?$/, '') + '/' + value.replace(/^\//, '')
}
function collection(path, params, auth) { return request(path + helpers.query(params), { auth }).then(helpers.items) }
async function all(path, params, auth) {
  const result = []
  let offset = 0
  while (true) {
    const page = await request(path + helpers.query(Object.assign({}, params || {}, { offset, limit: 100 })), { auth })
    const batch = helpers.items(page)
    result.push(...batch)
    offset += batch.length
    if (!batch.length || !page.total || offset >= page.total) return result
    if (batch.length < 100) return result
  }
}
function track(event, values) {
  if (!session.get()) return Promise.resolve()
  const eventId = Date.now().toString(36) + '-' + Math.random().toString(36).slice(2)
  return request('/events', { method: 'POST', auth: true, data: Object.assign({ event, event_id: eventId }, values || {}) }).catch(() => {})
}
function showError(error) { wx.showToast({ title: error.message || '操作失败', icon: 'none', duration: 3500 }) }
module.exports = { request, upload, uploadFeedbackImage, downloadPrivate, collection, all, mediaUrl, track, showError, errorFrom }
