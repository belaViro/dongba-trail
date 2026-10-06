// @vitest-environment ./tests/component-environment.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ElMessage } from 'element-plus'
import * as apiClient from '../src/api'
import SystemConfigView from '../src/views/SystemConfigView.vue'
import { all, button, flush, mount, text, type HostNode } from './component-harness'

// OPS-03 / SHARE-01; AUTH-02 / GEO-01 regression. All requests are fixtures,
// not evidence of provider connectivity, generation, or recognition accuracy.
vi.mock('element-plus', () => ({ ElMessage: { success: vi.fn() } }))

const configPath = '/api/v1/admin/system-config'
const modelsPath = `${configPath}/image-models`
const legacyConfig = {
  provider_name: 'volcengine-ark',
  provider_endpoint: 'https://recognition.example.test/v1/chat/completions',
  provider_model: 'recognition-fixture',
  provider_timeout_seconds: 25,
  provider_api_key_configured: false,
  key_editable: true,
  map_web_key: 'fixture-public-map-key',
  map_center_longitude: 100.3,
  map_center_latitude: 26.9,
  map_default_zoom: 14,
}
const imageConfig = {
  image_provider_name: 'openai-compatible',
  image_provider_endpoint: 'https://images.example.test/v1/images/generations',
  image_provider_model: 'poster-fixture',
  image_provider_timeout_seconds: 90,
  image_provider_size: '1536x1024',
  image_provider_quality: 'hd',
  image_provider_api_key_configured: true,
}
const config = (overrides: Record<string, unknown> = {}) => ({
  ...legacyConfig,
  ...imageConfig,
  ...overrides,
})
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
const http = vi.fn<typeof fetch>()
let instance: ReturnType<typeof mount> | undefined

beforeEach(() => {
  vi.resetAllMocks()
  http.mockRejectedValue(new Error('Unexpected request in isolated fixture test'))
  vi.stubGlobal('fetch', http)
  vi.stubGlobal('sessionStorage', { getItem: () => null, removeItem: vi.fn() })
  vi.stubGlobal('window', { setTimeout, dispatchEvent: vi.fn() })
})
afterEach(() => {
  instance?.unmount()
  instance = undefined
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  // No fixture path can accidentally exercise paid generation or an external URL.
  for (const [path, init] of http.mock.calls) {
    expect([configPath, modelsPath]).toContain(path)
    if (path === modelsPath) expect(init?.method).toBe('POST')
  }
})

async function open(value: Record<string, unknown> = config()) {
  http.mockResolvedValueOnce(response(value))
  instance = mount(SystemConfigView)
  await flush()
  return instance.root
}
function field(root: HostNode, label: string) {
  const element = all(root, (n) => n.props['aria-label'] === label)[0]
  if (!element) throw new Error(`Missing field: ${label}`)
  return element
}
function formItem(root: HostNode, label: string) {
  const element = all(root, (n) => n.type === 'el-form-item' && n.props.label === label)[0]
  if (!element) throw new Error(`Missing form item: ${label}`)
  return element
}
function input(root: HostNode, label: string) {
  return all(formItem(root, label), (n) => n.type === 'el-input')[0]!
}
async function change(element: HostNode, value: unknown) {
  element.props['onUpdate:modelValue'](value)
  await flush()
}
async function click(root: HostNode, label: string) {
  await button(root, label).props.onClick()
  await flush()
}
function options(element: HostNode) {
  return all(element, (n) => n.type === 'el-option').map((n) => n.props.value)
}
function alerts(root: HostNode) {
  return all(root, (n) => n.type === 'el-alert')
    .map((n) => String(n.props.title))
    .join('\n')
}
function lastRequest() {
  const [path, init] = http.mock.calls.at(-1)!
  return { path, method: init?.method, body: init?.body ? JSON.parse(String(init.body)) : undefined }
}

describe('poster settings and existing configuration', () => {
  it('defaults missing poster fields, separates sections, and does not discover or generate on mount', async () => {
    const root = await open(legacyConfig)
    expect(all(root, (n) => n.type === 'h2').map(text)).toEqual(['视觉识别模型', '旅游海报 AI', '文化地图'])
    for (const [label, value] of Object.entries({
      旅游海报提供方: 'unconfigured',
      旅游海报接口地址: '',
      '旅游海报模型 ID': '',
      旅游海报请求超时: 180,
      旅游海报尺寸: '1024x1536',
      旅游海报质量: 'auto',
      '旅游海报 API Key': '',
      '清除海报 API Key': false,
    }))
      expect(field(root, label).props.modelValue).toBe(value)
    expect(options(field(root, '旅游海报模型 ID'))).toEqual([])
    expect(text(formItem(root, '海报 API Key（不回显；留空表示不更改）'))).toContain('未配置')
    expect(button(root, '读取可用模型').props.disabled).toBe(true)
    expect(all(root, (n) => n.type === 'el-button').map((n) => text(n).trim())).toEqual([
      '读取可用模型',
      '撤销修改',
      '保存并生效',
    ])
    expect(http).toHaveBeenCalledTimes(1)
    expect(lastRequest()).toEqual({ path: configPath, method: undefined, body: undefined })
  })

  it('loads saved settings and independent status without copying any raw response keys', async () => {
    const root = await open(
      config({
        provider_api_key: 'fixture-unexpected-recognition-key',
        image_provider_api_key: 'fixture-unexpected-image-key',
      }),
    )
    expect(field(root, '旅游海报提供方').props.modelValue).toBe('openai-compatible')
    expect(field(root, '旅游海报接口地址').props.modelValue).toBe(imageConfig.image_provider_endpoint)
    expect(field(root, '旅游海报模型 ID').props.modelValue).toBe('poster-fixture')
    expect(field(root, '旅游海报请求超时').props.modelValue).toBe(90)
    expect(field(root, '旅游海报尺寸').props.modelValue).toBe('1536x1024')
    expect(field(root, '旅游海报质量').props.modelValue).toBe('hd')
    expect(field(root, '旅游海报 API Key').props).toMatchObject({
      type: 'password',
      autocomplete: 'new-password',
      modelValue: '',
    })
    expect(input(root, 'API Key（不回显；留空表示不更改）').props.modelValue).toBe('')
    expect(text(formItem(root, '海报 API Key（不回显；留空表示不更改）'))).toContain('已配置')
    expect(text(formItem(root, 'API Key（不回显；留空表示不更改）'))).toContain('未配置')
    expect(text(root)).not.toContain('fixture-unexpected')
  })

  it('offers only contract choices and permits a manually entered model without inventing one', async () => {
    const root = await open()
    expect(options(field(root, '旅游海报提供方'))).toEqual(['unconfigured', 'openai-compatible'])
    expect(options(field(root, '旅游海报尺寸'))).toEqual(['1024x1536', '1024x1024', '1536x1024', 'auto'])
    expect(options(field(root, '旅游海报质量'))).toEqual(['auto', 'low', 'medium', 'high', 'standard', 'hd'])
    expect(field(root, '旅游海报请求超时').props).toMatchObject({ min: 10, max: 240, precision: 0 })
    const model = field(root, '旅游海报模型 ID')
    expect(model.props).toHaveProperty('filterable')
    expect(model.props).toHaveProperty('allow-create')
    await change(model, 'my-manual-image-model')
    expect(model.props.modelValue).toBe('my-manual-image-model')
    expect(http).toHaveBeenCalledTimes(1)
  })

  it('saves image edits with recognition and map edits, accepts server normalization, and wipes both keys', async () => {
    const root = await open()
    await change(field(root, '旅游海报接口地址'), 'https://custom.example.test/v1')
    await change(field(root, '旅游海报模型 ID'), 'manual-fixture-model')
    await change(field(root, '旅游海报请求超时'), 240)
    await change(field(root, '旅游海报尺寸'), '1024x1024')
    await change(field(root, '旅游海报质量'), 'high')
    await change(field(root, '旅游海报 API Key'), 'fixture-new-image-key')
    await change(input(root, 'API Key（不回显；留空表示不更改）'), 'fixture-new-recognition-key')
    await change(input(root, '模型 ID'), 'changed-recognition-model')
    await change(input(root, '高德 JS API Web Key（浏览器公开信息）'), 'changed-public-map-key')
    const saved = config({
      image_provider_endpoint: 'https://custom.example.test/v1/images/generations',
      image_provider_model: 'manual-fixture-model',
      image_provider_timeout_seconds: 240,
      image_provider_size: '1024x1024',
      image_provider_quality: 'high',
      provider_model: 'changed-recognition-model',
      provider_api_key_configured: true,
      map_web_key: 'changed-public-map-key',
    })
    http.mockResolvedValueOnce(response(saved))
    await click(root, '保存并生效')
    const {
      provider_api_key_configured: _recognitionStatus,
      key_editable: _editable,
      image_provider_api_key_configured: _imageStatus,
      ...expected
    } = saved
    expect(lastRequest()).toEqual({
      path: configPath,
      method: 'PUT',
      body: {
        ...expected,
        image_provider_endpoint: 'https://custom.example.test/v1',
        provider_api_key: 'fixture-new-recognition-key',
        clear_provider_api_key: false,
        image_provider_api_key: 'fixture-new-image-key',
        clear_image_provider_api_key: false,
      },
    })
    expect(field(root, '旅游海报接口地址').props.modelValue).toBe(saved.image_provider_endpoint)
    expect(field(root, '旅游海报 API Key').props.modelValue).toBe('')
    expect(input(root, 'API Key（不回显；留空表示不更改）').props.modelValue).toBe('')
    expect(field(root, '清除海报 API Key').props.modelValue).toBe(false)
    expect(ElMessage.success).toHaveBeenCalledWith('系统配置已保存，新请求立即生效；已打开的地图页面请刷新')
    expect(http).toHaveBeenCalledTimes(2)
  })

  it.each([false, true])(
    'retains a blank key or explicitly clears it (clear=%s), without changing recognition',
    async (clear) => {
      const root = await open()
      await change(field(root, '清除海报 API Key'), clear)
      expect(field(root, '旅游海报 API Key').props.disabled).toBe(clear)
      http.mockResolvedValueOnce(response(config({ image_provider_api_key_configured: !clear })))
      await click(root, '保存并生效')
      expect(lastRequest().body).toMatchObject({
        image_provider_api_key: '',
        clear_image_provider_api_key: clear,
        provider_api_key: '',
        clear_provider_api_key: false,
      })
      expect(field(root, '清除海报 API Key').props.modelValue).toBe(false)
      expect(text(formItem(root, '海报 API Key（不回显；留空表示不更改）'))).toContain(
        clear ? '未配置' : '已配置',
      )
    },
  )

  it('prevents conflicting replacement and clearing, independently from the recognition key', async () => {
    const root = await open()
    await change(field(root, '旅游海报 API Key'), 'fixture-unsaved-key')
    expect(field(root, '清除海报 API Key').props.disabled).toBe(true)
    expect(input(root, 'API Key（不回显；留空表示不更改）').props.disabled).toBe(false)
    await change(field(root, '旅游海报 API Key'), '')
    expect(field(root, '清除海报 API Key').props.disabled).toBe(false)
    await change(field(root, '清除海报 API Key'), true)
    expect(field(root, '旅游海报 API Key').props.disabled).toBe(true)
  })

  it('disables key replacement without key_editable but permits non-secret settings and stored-key lookup', async () => {
    const root = await open(config({ key_editable: false }))
    expect(field(root, '旅游海报 API Key').props.disabled).toBe(true)
    expect(input(root, 'API Key（不回显；留空表示不更改）').props.disabled).toBe(true)
    expect(text(root)).toContain('暂不能通过页面更换 API Key')
    http.mockResolvedValueOnce(response({ items: [] }))
    await click(root, '读取可用模型')
    expect(lastRequest().body).toEqual({ endpoint: imageConfig.image_provider_endpoint })
    await change(field(root, '旅游海报请求超时'), 10)
    http.mockResolvedValueOnce(response(config({ key_editable: false, image_provider_timeout_seconds: 10 })))
    await click(root, '保存并生效')
    expect(lastRequest().body).toMatchObject({
      image_provider_timeout_seconds: 10,
      image_provider_api_key: '',
      provider_api_key: '',
    })
  })

  it('also defaults a legacy save response and sends defaults rather than undefined fields', async () => {
    const root = await open(legacyConfig)
    http.mockResolvedValueOnce(response(legacyConfig))
    await click(root, '保存并生效')
    expect(lastRequest().body).toMatchObject({
      image_provider_name: 'unconfigured',
      image_provider_endpoint: '',
      image_provider_model: '',
      image_provider_timeout_seconds: 180,
      image_provider_size: '1024x1536',
      image_provider_quality: 'auto',
      image_provider_api_key: '',
      clear_image_provider_api_key: false,
    })
    expect(field(root, '旅游海报请求超时').props.modelValue).toBe(180)
    expect(field(root, '旅游海报模型 ID').props.modelValue).toBe('')
  })
})

describe('explicit, non-generating model discovery', () => {
  it.each(['https://images.example.test/v1', imageConfig.image_provider_endpoint])(
    'posts the entered endpoint unchanged, uses the stored key, and never auto-selects (%s)',
    async (endpoint) => {
      const root = await open(config({ image_provider_endpoint: endpoint }))
      http.mockResolvedValueOnce(
        response({ items: [{ id: 'model-b' }, { id: 'model-a' }, { id: 'model-b' }] }),
      )
      await click(root, '读取可用模型')
      expect(lastRequest()).toEqual({ path: modelsPath, method: 'POST', body: { endpoint } })
      expect(options(field(root, '旅游海报模型 ID'))).toEqual(['model-b', 'model-a'])
      expect(field(root, '旅游海报模型 ID').props.modelValue).toBe('poster-fixture')
      expect(text(root)).toContain('已读取 2 个模型')
      expect(ElMessage.success).not.toHaveBeenCalled()
      await change(field(root, '旅游海报模型 ID'), 'model-a')
      expect(field(root, '旅游海报模型 ID').props.modelValue).toBe('model-a')
      expect(http).toHaveBeenCalledTimes(2)
    },
  )

  it('uses an unsaved masked image key only for lookup without saving or sending the recognition key', async () => {
    const root = await open()
    await change(input(root, 'API Key（不回显；留空表示不更改）'), 'fixture-recognition-only')
    await change(field(root, '旅游海报 API Key'), 'fixture-image-only')
    http.mockResolvedValueOnce(response({ items: [{ id: 'discovered-fixture' }] }))
    await click(root, '读取可用模型')
    expect(lastRequest()).toEqual({
      path: modelsPath,
      method: 'POST',
      body: {
        endpoint: imageConfig.image_provider_endpoint,
        api_key: 'fixture-image-only',
      },
    })
    expect(field(root, '旅游海报 API Key').props).toMatchObject({
      modelValue: 'fixture-image-only',
      type: 'password',
    })
    expect(text(root)).not.toContain('fixture-image-only')
    expect(http).toHaveBeenCalledTimes(2)
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('sends a pending clear instruction instead of silently falling back to the stored key', async () => {
    const root = await open()
    await change(field(root, '清除海报 API Key'), true)
    http.mockResolvedValueOnce(response({ items: [] }))
    await click(root, '读取可用模型')
    expect(lastRequest().body).toEqual({ endpoint: imageConfig.image_provider_endpoint, clear_api_key: true })
    expect(field(root, '清除海报 API Key').props.modelValue).toBe(true)
    expect(text(root)).toContain('未返回可用模型，可手动填写模型 ID')
    await change(field(root, '旅游海报模型 ID'), 'manual-after-empty-list')
    http.mockResolvedValueOnce(
      response(
        config({ image_provider_model: 'manual-after-empty-list', image_provider_api_key_configured: false }),
      ),
    )
    await click(root, '保存并生效')
    expect(lastRequest().body.image_provider_model).toBe('manual-after-empty-list')
  })

  it('does not query when disabled or missing an endpoint, and never queries on edits', async () => {
    const root = await open(legacyConfig)
    await click(root, '读取可用模型')
    await change(field(root, '旅游海报提供方'), 'openai-compatible')
    await change(field(root, '旅游海报接口地址'), '   ')
    expect(button(root, '读取可用模型').props.disabled).toBe(true)
    await click(root, '读取可用模型')
    expect(alerts(root)).toContain('请先填写旅游海报接口地址')
    await change(field(root, '旅游海报接口地址'), 'https://new.example.test/v1')
    expect(button(root, '读取可用模型').props.disabled).toBe(false)
    expect(alerts(root)).toBe('')
    expect(http).toHaveBeenCalledTimes(1)
  })

  it('explains the changed-address key rule and never supplies a stored key to a new address', async () => {
    const root = await open()
    await change(field(root, '旅游海报接口地址'), 'https://different.example.test/v1')
    expect(text(root)).toContain('请输入该地址对应的新 API Key')
    expect(text(root)).toContain('不会向不同地址转发已保存的密钥')
    http.mockResolvedValueOnce(
      response({ code: 'IMAGE_PROVIDER_KEY_REQUIRED', message: 'fixture-private-response' }, 422),
    )
    await click(root, '读取可用模型')
    expect(lastRequest()).toEqual({
      path: modelsPath,
      method: 'POST',
      body: { endpoint: 'https://different.example.test/v1' },
    })
    expect(alerts(root)).toContain('读取可用模型失败')
    expect(alerts(root)).not.toContain('fixture-private-response')
    await change(field(root, '旅游海报 API Key'), 'fixture-new-origin-key')
    http.mockResolvedValueOnce(response({ items: [{ id: 'new-origin-model' }] }))
    await click(root, '读取可用模型')
    expect(lastRequest().body).toEqual({
      endpoint: 'https://different.example.test/v1',
      api_key: 'fixture-new-origin-key',
    })
    expect(alerts(root)).toBe('')
    expect(http).toHaveBeenCalledTimes(3)
  })

  it.each([
    ['IMAGE_PROVIDER_KEY_REQUIRED', '请输入该地址对应的新 API Key'],
    ['IMAGE_PROVIDER_UNCONFIGURED', '请检查提供方、接口地址和 API Key'],
    ['IMAGE_PROVIDER_AUTH_FAILED', '请检查密钥是否有效'],
    ['IMAGE_PROVIDER_TIMEOUT', '读取模型超时，请稍后重试'],
    ['IMAGE_PROVIDER_BUSY', '服务繁忙或请求过于频繁，请稍后重试'],
  ])(
    'locally translates %s without echoing remote detail, retaining a safe request ID',
    async (code, message) => {
      const root = await open()
      // The shared API owns transport/error codes; the view supports its optional code field.
      vi.spyOn(apiClient, 'save').mockRejectedValueOnce(
        Object.assign(new apiClient.ApiError('fixture-private-upstream-detail', 502, 'fixture-request'), {
          code,
        }),
      )
      await click(root, '读取可用模型')
      expect(alerts(root)).toContain(message)
      expect(alerts(root)).toContain('请求编号 fixture-request')
      expect(alerts(root)).not.toMatch(/IMAGE_PROVIDER_|fixture-private-upstream-detail/)
      expect(button(root, '读取可用模型').props.loading).toBe(false)
    },
  )

  it('supports a code-only API error without accepting an unsafe request ID', async () => {
    const root = await open()
    vi.spyOn(apiClient, 'save').mockRejectedValueOnce(
      new apiClient.ApiError('IMAGE_PROVIDER_AUTH_FAILED', 502, 'private /internal.py'),
    )
    await click(root, '读取可用模型')
    expect(alerts(root)).toContain('请检查密钥是否有效')
    expect(alerts(root)).not.toMatch(/IMAGE_PROVIDER_|internal\.py/)
  })

  it('preserves helpful shared API messages when no structured code is provided', async () => {
    const root = await open()
    vi.spyOn(apiClient, 'save').mockRejectedValueOnce(
      new apiClient.ApiError('请为新接口地址输入 API Key', 422, 'shared-request'),
    )
    await click(root, '读取可用模型')
    expect(alerts(root)).toContain('请为新接口地址输入 API Key')
    expect(alerts(root)).toContain('请求编号 shared-request')
  })

  it.each([
    ['IMAGE_PROVIDER_KEY_REQUIRED', 422, '接口地址已更改'],
    ['IMAGE_PROVIDER_UNCONFIGURED', 503, '配置'],
    ['IMAGE_PROVIDER_AUTH_FAILED', 502, '密钥'],
    ['IMAGE_PROVIDER_TIMEOUT', 504, '超时'],
    ['IMAGE_PROVIDER_BUSY', 502, '繁忙'],
  ])(
    'shows helpful %s guidance through the actual shared API error mapping',
    async (code, status, message) => {
      const root = await open()
      http.mockResolvedValueOnce(
        response(
          { code, message: 'fixture-private-provider-response', request_id: 'shared-api-request' },
          status,
        ),
      )
      await click(root, '读取可用模型')
      expect(alerts(root)).toContain(message)
      expect(alerts(root)).toContain('请求编号 shared-api-request')
      expect(alerts(root)).not.toMatch(/fixture-private-provider-response|IMAGE_PROVIDER_|请求未完成/)
      expect(button(root, '读取可用模型').props.loading).toBe(false)
    },
  )

  it.each([
    [503, '请求未完成，请稍后重试'],
    [422, '提交内容不符合要求，请检查后重试'],
    [403, '当前账号没有此操作权限'],
  ])('shows a safe actionable error for HTTP %s and clears it on retry', async (status, message) => {
    const root = await open()
    http.mockResolvedValueOnce(
      response(
        {
          code: status === 403 ? 'FORBIDDEN' : 'UNKNOWN_PROVIDER_FAILURE',
          message: 'fixture-private-key /srv/private.py',
          detail: 'upstream private response',
          request_id: 'fixture-request',
        },
        status,
      ),
    )
    await click(root, '读取可用模型')
    expect(alerts(root)).toContain('读取可用模型失败')
    expect(alerts(root)).toContain(message)
    expect(alerts(root)).toContain('fixture-request')
    expect(alerts(root)).toContain('也可手动填写模型 ID')
    expect(alerts(root)).not.toMatch(/fixture-private-key|private\.py|upstream private/)
    expect(button(root, '读取可用模型').props.loading).toBe(false)
    http.mockResolvedValueOnce(response({ items: [{ id: 'retry-model' }] }))
    await click(root, '读取可用模型')
    expect(alerts(root)).toBe('')
    expect(options(field(root, '旅游海报模型 ID'))).toEqual(['retry-model'])
  })

  it('handles a network failure without reflecting the raw exception', async () => {
    const root = await open()
    http.mockRejectedValueOnce(new Error('fixture-private-key network internals'))
    await click(root, '读取可用模型')
    expect(alerts(root)).toContain('无法连接服务，请检查网络后重试')
    expect(alerts(root)).not.toContain('fixture-private-key')
    await change(field(root, '旅游海报 API Key'), 'fixture-corrected-key')
    expect(alerts(root)).toBe('')
  })

  it.each([null, {}, { items: null }, { items: [{ id: 1 }] }, { items: [{ id: ' ' }] }])(
    'rejects a malformed list safely rather than inventing selectable models: %j',
    async (body) => {
      const root = await open()
      http.mockResolvedValueOnce(response(body))
      await click(root, '读取可用模型')
      expect(alerts(root)).toContain('读取可用模型失败')
      expect(alerts(root)).not.toMatch(/TypeError|Invalid model list|undefined|null/)
      expect(options(field(root, '旅游海报模型 ID'))).toEqual([])
      expect(field(root, '旅游海报模型 ID').props.modelValue).toBe('poster-fixture')
      expect(button(root, '读取可用模型').props.loading).toBe(false)
    },
  )

  it('clears previous options on a failed refresh and keeps manual model entry available', async () => {
    const root = await open()
    http.mockResolvedValueOnce(response({ items: [{ id: 'old-model' }] }))
    await click(root, '读取可用模型')
    http.mockResolvedValueOnce(new Response('<html>private proxy failure</html>'))
    await click(root, '读取可用模型')
    expect(options(field(root, '旅游海报模型 ID'))).toEqual([])
    expect(alerts(root)).toContain('暂时无法读取内容，请稍后重试')
    expect(alerts(root)).not.toContain('private proxy')
    await change(field(root, '旅游海报模型 ID'), 'manual-after-error')
    expect(field(root, '旅游海报模型 ID').props.modelValue).toBe('manual-after-error')
  })

  it.each([
    ['旅游海报接口地址', 'https://other.example.test/v1'],
    ['旅游海报 API Key', 'fixture-replacement-key'],
    ['清除海报 API Key', true],
    ['旅游海报提供方', 'unconfigured'],
  ])(
    'discards late lookup results when %s changes, without issuing an automatic request',
    async (label, value) => {
      const root = await open()
      let finish!: (value: Response) => void
      http.mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            finish = resolve
          }),
      )
      const pending = button(root, '读取可用模型').props.onClick()
      await flush()
      expect(button(root, '读取可用模型').props.loading).toBe(true)
      await click(root, '读取可用模型')
      expect(http).toHaveBeenCalledTimes(2)
      await change(field(root, label), value)
      finish(response({ items: [{ id: 'stale-model' }] }))
      await pending
      await flush()
      expect(options(field(root, '旅游海报模型 ID'))).toEqual([])
      expect(alerts(root)).toBe('')
      expect(button(root, '读取可用模型').props.loading).toBe(false)
      expect(http).toHaveBeenCalledTimes(2)
    },
  )

  it('does not let an old failure overwrite the results of a newer explicit lookup', async () => {
    const root = await open()
    let finish!: (value: Response) => void
    http.mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          finish = resolve
        }),
    )
    const pending = button(root, '读取可用模型').props.onClick()
    await change(field(root, '旅游海报接口地址'), 'https://other.example.test/v1')
    http.mockResolvedValueOnce(response({ items: [{ id: 'new-model' }] }))
    await click(root, '读取可用模型')
    finish(response({ message: 'old failure' }, 503))
    await pending
    await flush()
    expect(options(field(root, '旅游海报模型 ID'))).toEqual(['new-model'])
    expect(alerts(root)).toBe('')
  })
})

describe('existing load, save, and undo UX', () => {
  it('recovers from an initial safe load failure through the existing retry action', async () => {
    http.mockResolvedValueOnce(response({ message: 'private load detail' }, 503))
    instance = mount(SystemConfigView)
    const { root } = instance
    await flush()
    expect(alerts(root)).toBe('请求未完成，请稍后重试')
    expect(all(root, (n) => n.type === 'el-form')).toHaveLength(0)
    http.mockResolvedValueOnce(response(config()))
    await click(root, '重试')
    expect(alerts(root)).toBe('')
    expect(field(root, '旅游海报模型 ID').props.modelValue).toBe('poster-fixture')
  })

  it('keeps edits on a safe save failure and clears keys only after a successful retry', async () => {
    const root = await open()
    await change(field(root, '旅游海报 API Key'), 'fixture-unsaved-key')
    http.mockResolvedValueOnce(response({ message: 'fixture-unsaved-key internal save detail' }, 422))
    await click(root, '保存并生效')
    expect(alerts(root)).toBe('提交内容不符合要求，请检查后重试')
    expect(field(root, '旅游海报 API Key').props.modelValue).toBe('fixture-unsaved-key')
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(button(root, '保存并生效').props.loading).toBe(false)
    http.mockResolvedValueOnce(response(config()))
    await click(root, '保存并生效')
    expect(alerts(root)).toBe('')
    expect(field(root, '旅游海报 API Key').props.modelValue).toBe('')
  })

  it('keeps the saving indicator and prevents duplicate saves or model lookups while saving', async () => {
    const root = await open()
    let finish!: (value: Response) => void
    http.mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          finish = resolve
        }),
    )
    const pending = button(root, '保存并生效').props.onClick()
    await flush()
    expect(button(root, '保存并生效').props.loading).toBe(true)
    expect(button(root, '撤销修改').props.disabled).toBe(true)
    expect(button(root, '读取可用模型').props.disabled).toBe(true)
    await click(root, '保存并生效')
    await click(root, '读取可用模型')
    expect(http).toHaveBeenCalledTimes(2)
    finish(response(config()))
    await pending
    await flush()
    expect(button(root, '保存并生效').props.loading).toBe(false)
    expect(button(root, '撤销修改').props.disabled).toBe(false)
  })

  it('undo reloads server values and removes both raw keys, clear flags, and discovered options', async () => {
    const root = await open()
    await change(field(root, '旅游海报 API Key'), 'fixture-discarded-image-key')
    await change(input(root, 'API Key（不回显；留空表示不更改）'), 'fixture-discarded-recognition-key')
    await change(field(root, '旅游海报模型 ID'), 'discarded-model')
    http.mockResolvedValueOnce(response({ items: [{ id: 'discarded-list-model' }] }))
    await click(root, '读取可用模型')
    http.mockResolvedValueOnce(response(config()))
    await click(root, '撤销修改')
    expect(lastRequest()).toEqual({ path: configPath, method: undefined, body: undefined })
    expect(field(root, '旅游海报 API Key').props.modelValue).toBe('')
    expect(input(root, 'API Key（不回显；留空表示不更改）').props.modelValue).toBe('')
    expect(field(root, '旅游海报模型 ID').props.modelValue).toBe('poster-fixture')
    expect(options(field(root, '旅游海报模型 ID'))).toEqual([])
    await change(field(root, '清除海报 API Key'), true)
    const recognitionClear = all(root, (n) => n.type === 'el-checkbox' && !n.props['aria-label'])[0]!
    await change(recognitionClear, true)
    http.mockResolvedValueOnce(response(config()))
    await click(root, '撤销修改')
    expect(field(root, '清除海报 API Key').props.modelValue).toBe(false)
    expect(recognitionClear.props.modelValue).toBe(false)
  })
})
