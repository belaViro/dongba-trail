export type Row = Record<string, any>
export interface Collection {
  items: Row[]
  total: number
}
export interface User {
  id: string
  username: string
  display_name: string
  role: string
  merchant_id?: string
}

const TOKEN_KEY = 'dongba_access_token'
const messages: Record<string, string> = {
  FEEDBACK_CHARACTER_REQUIRED: '请先选择核验后的正确词条，再采纳纠错',
  RAG_FEEDBACK_WORKFLOW_REQUIRED: '请前往纠错审核处理这条反馈',
  RATE_LIMITED: '请求较频繁，请稍后重试',
  LOCATION_REQUIRED: '发布商户前请填写经过核对的门店坐标',
  LOCATION_INCOMPLETE: '经度和纬度需要同时填写',
  GLYPH_REQUIRED: '发布词条前请上传字形图片或同字异形图片',
  EXPORT_TOO_LARGE: '导出结果过大，请缩小筛选范围后重试',
  EXPORT_UNAVAILABLE: '当前记录暂不支持导出',
  AUTH_REQUIRED: '请先登录',
  SESSION_EXPIRED: '登录已过期，请重新登录',
  ACCOUNT_UNAVAILABLE: '该账号已停用',
  INVALID_CREDENTIALS: '账号或密码不正确',
  LOGIN_RATE_LIMITED: '登录尝试过多，请15分钟后重试',
  FORBIDDEN: '当前账号没有此操作权限',
  CROSS_MERCHANT: '无权核销其他门店优惠券',
  SETUP_DISABLED: '初始化未开放或授权码无效',
  SETUP_COMPLETE: '管理员已创建，请重新登录',
  DATABASE_NOT_MIGRATED: '服务尚未完成初始化',
  INVALID_ENTITY: '资料格式不符合要求，请检查表单',
  INVALID_USER: '账号资料格式不符合要求',
  NOT_FOUND: '记录不存在或已不可用',
  USER_NOT_FOUND: '用户不存在',
  ID_EXISTS: '该编号已存在',
  USERNAME_EXISTS: '该账号已被使用',
  IMMUTABLE_ID: '记录编号不可修改',
  MERCHANT_REQUIRED: '商户账号必须关联门店',
  INVALID_MERCHANT: '关联门店不可用',
  PASSWORD_REQUIRED: '请设置账号密码',
  RESERVED_USERNAME: '该账号前缀不可使用',
  SELF_LOCKOUT: '不能停用或降低当前管理员账号权限',
  REVIEW_INCOMPLETE: '审核前需要填写文化摘要和资料来源',
  REVIEW_REQUIRED: '发布需要运营审核',
  TAG_REVIEW_REQUIRED: '文化标签关联需要运营审核',
  REVIEW_NOTE_REQUIRED: '请填写驳回原因',
  NODE_INCOMPLETE: '任务节点缺少对应的东巴字、商户或点位',
  QUEST_IN_USE: '已有游客参与，不能修改当前路线规则',
  COUPON_IN_USE: '优惠券已被领取，不能修改使用规则和有效期',
  STOCK_BELOW_CLAIMED: '库存不能少于已领取数量',
  COUPON_NOT_FOUND: '该核销码不存在或不属于当前门店',
  COUPON_UNAVAILABLE: '该优惠券无法核销',
  NOT_ACTIVE: '当前不在有效期内或尚未发布',
  FEEDBACK_REVIEWED: '该反馈已审核，不能修改',
  INVALID_WEIGHTS: '推荐权重必须在0到100%之间，合计100%',
  JOIN_REQUIRED: '该游客尚未加入路线',
  MANUAL_NOT_ALLOWED: '该节点不支持人工确认',
  MANUAL_REQUIRED: '该节点需要运营人员确认',
  NODE_NOT_FOUND: '任务节点不存在',
  QUEST_NO_NODES: '路线尚未配置有效节点',
  SOLD_OUT: '优惠券已领完',
  MEDIA_NOT_FOUND: '图片不存在或无权访问',
  FILE_TOO_LARGE: '图片文件过大',
  INVALID_IMAGE: '图片格式无效',
  INVALID_SAMPLE: '样本信息不符合要求，请检查表单',
  SAMPLE_REVIEW_INCOMPLETE: '审核通过需要关联已审核或已发布词条，并填写资料来源',
  SAMPLE_IMAGE_UNAVAILABLE: '样本图片不可用，请检查记录或缩小导出范围',
  INVALID_SAMPLE_BBOX: '标注框不能超出图片边界',
  INVALID_RAG_CASE: '纠错信息不符合要求，请检查后重试',
  RAG_CASE_NOT_FOUND: '识别参考不存在或已不可用',
  RAG_DATABASE_UNAVAILABLE: '识别参考暂不可用，请稍后重试或联系管理员',
  RAG_IMAGE_UNAVAILABLE: '案例图片不存在或已不可用',
  RAG_REVIEW_NOTE_REQUIRED: '请填写处理原因',
  RAG_INDEX_UNAVAILABLE: '识别参考暂不可用，请稍后重试',
  RAG_REBUILD_RUNNING: '识别参考正在更新，请稍后再试',
  IMAGE_PROVIDER_UNCONFIGURED: '请先配置并启用海报生图服务',
  IMAGE_PROVIDER_KEY_REQUIRED: '接口地址已更改，请输入对应的 API Key 后读取模型',
  IMAGE_PROVIDER_AUTH_FAILED: '生图服务鉴权失败，请检查密钥与权限',
  IMAGE_PROVIDER_BUSY: '生图服务繁忙或额度受限，请稍后重试',
  IMAGE_PROVIDER_TIMEOUT: '生图服务响应超时，请稍后重试',
  IMAGE_PROVIDER_UNAVAILABLE: '暂时无法连接生图服务，请检查配置',
  IMAGE_PROVIDER_INVALID_RESPONSE: '生图服务未返回有效结果，请检查接口与模型',
  CONFIG_ENCRYPTION_UNAVAILABLE: '服务端尚未配置可用的密钥加密环境，请联系管理员',
}
export const tokenStore = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (token: string) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public requestId?: string,
  ) {
    super(message)
  }
}

async function request(path: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers)
  const token = tokenStore.get()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 25000)
  let response: Response
  try {
    response = await fetch(`/api/v1${path}`, { ...options, headers, signal: controller.signal })
  } catch (error) {
    throw new ApiError(
      error instanceof Error && error.name === 'AbortError'
        ? '请求超时，请稍后重试'
        : '无法连接服务，请检查网络后重试',
      0,
    )
  } finally {
    clearTimeout(timeout)
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    if (response.status === 401 && !path.startsWith('/auth/')) {
      tokenStore.clear()
      window.dispatchEvent(new Event('session-expired'))
    }
    throw new ApiError(
      Object.prototype.hasOwnProperty.call(messages, body?.code)
        ? messages[body.code]
        : response.status === 422
          ? '提交内容不符合要求，请检查后重试'
          : '请求未完成，请稍后重试',
      response.status,
      typeof body?.request_id === 'string' && /^[a-zA-Z0-9_-]{1,80}$/.test(body.request_id)
        ? body.request_id
        : undefined,
    )
  }
  return response
}

export async function api<T = Row>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await request(path, options)
  if (response.status === 204) return null as T
  try {
    return (await response.json()) as T
  } catch {
    throw new ApiError('暂时无法读取内容，请稍后重试', response.status)
  }
}

export async function apiBlob(path: string, options: RequestInit = {}) {
  const response = await request(path, options)
  return { blob: await response.blob(), headers: response.headers }
}

export const save = <T = Row>(path: string, data: Row, method = 'POST') =>
  api<T>(path, { method, body: JSON.stringify(data) })
export function errorText(error: unknown): string {
  if (error instanceof ApiError)
    return `${error.message}${error.requestId ? ` · 请求编号 ${error.requestId}` : ''}`
  return error instanceof Error ? error.message : '操作失败，请重试'
}
export function query(params: Record<string, string | number | undefined>) {
  return new URLSearchParams(
    Object.entries(params)
      .filter(([, value]) => value !== undefined && value !== '')
      .map(([key, value]) => [key, String(value)]),
  ).toString()
}
export function dateText(value: unknown): string {
  if (!value) return '—'
  const date = new Date(String(value))
  return Number.isNaN(date.valueOf()) ? String(value) : date.toLocaleString('zh-CN', { hour12: false })
}
