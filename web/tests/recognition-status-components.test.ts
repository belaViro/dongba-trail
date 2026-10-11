// @vitest-environment ./tests/component-environment.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import SystemConfigView from '../src/views/SystemConfigView.vue'
import RecordsView from '../src/views/RecordsView.vue'
import type { ProviderStatus, ServiceStatus } from '../src/recognition-status'
import { all, button, flush, mount, text, type HostNode } from './component-harness'

// OPS-03 / AI-01: isolated HTTP fixtures, not connectivity, loading or accuracy evidence.
vi.mock('element-plus', () => ({ ElMessage: { success: vi.fn() } }))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }), useRouter: () => ({ push: vi.fn() }) }))

const configPath = '/api/v1/admin/system-config'
const providerPath = '/api/v1/admin/provider'
const http = vi.fn<typeof fetch>()
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
const local: ServiceStatus = {
  name: 'db1404-local',
  kind: 'local',
  model: 'local-fixture-v2',
  configured: true,
  status: 'ready',
  status_message: '本地模型已加载，可处理识别请求。',
  endpoint_configured: null,
  timeout_seconds: 25,
  cpu_threads: 2,
  automatic_fallback: false,
  calibrated_confidence: false,
}
const ark: ServiceStatus = {
  ...local,
  name: 'volcengine-ark',
  kind: 'external',
  model: 'ark-backup-fixture',
  status: 'configured',
  status_message: '外部服务配置完整，未探测连接。',
  endpoint_configured: true,
  cpu_threads: null,
}
const disabled: ServiceStatus = {
  ...local,
  name: 'unconfigured',
  kind: 'unconfigured',
  configured: false,
  model: '',
  status: 'unconfigured',
  status_message: '识别服务未启用。',
  timeout_seconds: null,
  cpu_threads: null,
}
const config = (service: ServiceStatus = local, overrides: Record<string, unknown> = {}) => ({
  provider_name: service.name,
  provider_endpoint: 'https://ark.example.test/v1/chat/completions',
  provider_model: 'ark-backup-fixture',
  provider_timeout_seconds: 25,
  provider_api_key_configured: true,
  key_editable: true,
  local_model_version: 'local-fixture-v2',
  local_model_threads: 2,
  recognition_service: service,
  image_provider_name: 'openai-compatible',
  image_provider_endpoint: 'https://poster.example.test/v1/images/edits',
  image_provider_model: 'poster-fixture',
  image_provider_timeout_seconds: 180,
  image_provider_size: '1024x1536',
  image_provider_quality: 'auto',
  image_provider_api_key_configured: true,
  map_web_key: 'fixture-public-map-key',
  map_center_longitude: 100.3,
  map_center_latitude: 26.9,
  map_default_zoom: 14,
  ...overrides,
})
const statistics = (service: ServiceStatus = local): ProviderStatus => ({
  ...service,
  recent_requests: 8,
  recent_errors: 2,
  p95_latency_ms: 780,
  statistics_scope: 'current_provider_and_model',
  statistics_limit: 1000,
})
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
  vi.unstubAllGlobals()
  for (const [path, init] of http.mock.calls) {
    expect([configPath, providerPath]).toContain(path)
    expect([undefined, 'PUT']).toContain(init?.method)
  }
})
async function openConfig(value = config()) {
  http.mockResolvedValueOnce(response(value))
  instance = mount(SystemConfigView)
  await flush()
  return instance.root
}
async function openProvider(value: Partial<ProviderStatus> & Record<string, unknown> = statistics()) {
  http.mockResolvedValueOnce(response(value))
  instance = mount(RecordsView, { resource: 'provider' })
  await flush()
  return instance.root
}
function field(root: HostNode, label: string) {
  const found = all(root, (n) => n.props['aria-label'] === label)[0]
  if (!found) throw new Error(`Missing field: ${label}`)
  return found
}
function item(root: HostNode, label: string) {
  const found = all(
    root,
    (n) => ['el-form-item', 'el-descriptions-item'].includes(n.type) && n.props.label === label,
  )[0]
  if (!found) throw new Error(`Missing item: ${label}`)
  return found
}
const snapshot = (root: HostNode) => field(root, '当前已保存服务快照')
const notices = (root: HostNode) =>
  all(root, (n) => n.props.role === 'status')
    .map(text)
    .join(' ')
const alerts = (root: HostNode) =>
  all(root, (n) => n.type === 'el-alert')
    .map((n) => n.props.title)
    .join(' ')
async function change(root: HostNode, label: string, value: unknown) {
  field(root, label).props['onUpdate:modelValue'](value)
  await flush()
}
async function click(root: HostNode, label: string) {
  await button(root, label).props.onClick()
  await flush()
}
function savedBody() {
  const [path, init] = http.mock.calls.at(-1)!
  expect(path).toBe(configPath)
  expect(init?.method).toBe('PUT')
  return JSON.parse(String(init?.body))
}

describe('saved recognition service and provider selection', () => {
  it('separates the local saved snapshot, read-only server preview and editable shared timeout', async () => {
    const root = await openConfig(
      config(local, { local_model_version: 'server-preview-v3', local_model_threads: 4 }),
    )
    expect(text(snapshot(root))).toContain('local-fixture-v2')
    expect(text(snapshot(root))).toContain('本地模型已加载')
    expect(text(snapshot(root))).not.toContain('ark-backup-fixture')
    expect(text(item(root, '当前识别超时'))).toBe('25 秒')
    expect(text(item(root, '本地模型版本（只读）'))).toBe('server-preview-v3')
    expect(text(item(root, '本地 CPU 线程数（只读）'))).toBe('4')
    for (const label of ['本地模型版本（只读）', '本地 CPU 线程数（只读）'])
      expect(all(item(root, label), (n) => n.type.startsWith('el-input'))).toHaveLength(0)
    for (const label of ['Ark 接口地址', 'Ark 模型 ID', 'Ark API Key', '清除 Ark API Key'])
      expect(all(root, (n) => n.props['aria-label'] === label)).toHaveLength(0)
    expect(field(root, '共用识别超时').props.modelValue).toBe(25)
    expect(text(root)).toContain('本地推理与 Ark 共用此识别超时')
    expect(text(root)).toContain('不会自动切换或付费调用 Ark')
    expect(text(root)).toContain('未校准，不代表准确率')
    expect(field(root, '模型提供方').type).toBe('el-radio-group')
    expect(
      all(field(root, '模型提供方'), (n) => n.type === 'el-radio-button').map((n) => n.props.value),
    ).toEqual(['unconfigured', 'db1404-local', 'volcengine-ark'])
    expect(notices(root)).toBe('')
    expect(http).toHaveBeenCalledTimes(1)
  })

  it('shows unsaved local and disabled selections without replacing the saved Ark snapshot', async () => {
    const root = await openConfig(config(ark))
    await change(root, '模型提供方', 'db1404-local')
    expect(notices(root)).toContain('未保存选择：本地 DB1404')
    expect(text(snapshot(root))).toContain('ark-backup-fixture')
    expect(text(snapshot(root))).toContain('未探测连接')
    expect(text(item(root, '本地模型版本（只读）'))).toBe('local-fixture-v2')
    await change(root, '模型提供方', 'unconfigured')
    expect(notices(root)).toContain('未保存选择：未启用')
    expect(text(snapshot(root))).toContain('ark-backup-fixture')
    expect(all(root, (n) => n.props['aria-label'] === '共用识别超时')).toHaveLength(0)
    await change(root, '模型提供方', 'volcengine-ark')
    expect(notices(root)).toBe('')
    expect(http).toHaveBeenCalledTimes(1)
  })

  it('preserves edited Ark fields and shared timeout across local save and return to Ark', async () => {
    const root = await openConfig()
    await change(root, '共用识别超时', 38)
    await change(root, '模型提供方', 'volcengine-ark')
    expect(field(root, '共用识别超时').props.modelValue).toBe(38)
    expect(field(root, 'Ark 接口地址').props.modelValue).toBe(config().provider_endpoint)
    expect(field(root, 'Ark 模型 ID').props.modelValue).toBe('ark-backup-fixture')
    await change(root, 'Ark 接口地址', 'https://edited.example.test/v1')
    await change(root, 'Ark 模型 ID', 'edited-ark-fixture')
    await change(root, '模型提供方', 'db1404-local')
    const saved = config(
      { ...local, timeout_seconds: 38 },
      {
        provider_endpoint: 'https://edited.example.test/v1',
        provider_model: 'edited-ark-fixture',
        provider_timeout_seconds: 38,
      },
    )
    http.mockResolvedValueOnce(response(saved))
    await click(root, '保存并生效')
    expect(savedBody()).toMatchObject({
      provider_name: 'db1404-local',
      provider_endpoint: saved.provider_endpoint,
      provider_model: saved.provider_model,
      provider_timeout_seconds: 38,
      provider_api_key: '',
      clear_provider_api_key: false,
      image_provider_endpoint: saved.image_provider_endpoint,
      image_provider_model: saved.image_provider_model,
      image_provider_api_key: '',
      clear_image_provider_api_key: false,
      map_web_key: saved.map_web_key,
      map_center_longitude: 100.3,
      map_center_latitude: 26.9,
      map_default_zoom: 14,
    })
    for (const key of ['recognition_service', 'local_model_version', 'local_model_threads'])
      expect(savedBody()).not.toHaveProperty(key)
    expect(text(item(root, '当前识别超时'))).toBe('38 秒')
    expect(text(snapshot(root))).not.toContain('edited-ark-fixture')
    await change(root, '模型提供方', 'volcengine-ark')
    expect(field(root, 'Ark 接口地址').props.modelValue).toBe(saved.provider_endpoint)
    expect(field(root, 'Ark 模型 ID').props.modelValue).toBe(saved.provider_model)
    expect(field(root, '共用识别超时').props.modelValue).toBe(38)
    expect(text(item(root, 'API Key（不回显；留空表示不更改）'))).toContain('已配置')
    expect(http).toHaveBeenCalledTimes(2)
  })

  it.each(['replace', 'clear'])(
    'cancels hidden key %s without saving or discarding other form edits',
    async (action) => {
      const root = await openConfig(config(ark))
      await change(root, 'Ark 接口地址', 'https://unsaved.example.test/v1')
      await change(root, 'Ark 模型 ID', 'unsaved-ark-model')
      await change(root, '共用识别超时', 40)
      await change(
        root,
        action === 'replace' ? 'Ark API Key' : '清除 Ark API Key',
        action === 'replace' ? 'fixture-unsaved-key' : true,
      )
      await change(root, '模型提供方', 'db1404-local')
      await change(root, '模型提供方', 'volcengine-ark')
      expect(field(root, 'Ark 接口地址').props.modelValue).toBe('https://unsaved.example.test/v1')
      expect(field(root, 'Ark 模型 ID').props.modelValue).toBe('unsaved-ark-model')
      expect(field(root, '共用识别超时').props.modelValue).toBe(40)
      expect(field(root, 'Ark API Key').props.modelValue).toBe('')
      expect(field(root, '清除 Ark API Key').props.modelValue).toBe(false)
      expect(text(item(root, 'API Key（不回显；留空表示不更改）'))).toContain('已配置')
      expect(text(snapshot(root))).toContain('ark-backup-fixture')
      expect(text(item(root, '当前识别超时'))).toBe('25 秒')
      expect(http).toHaveBeenCalledTimes(1)
    },
  )

  it.each([
    ['db1404-local', 'replace'],
    ['db1404-local', 'clear'],
    ['unconfigured', 'replace'],
    ['unconfigured', 'clear'],
  ])('cancels only pending key %s/%s when hiding Ark and saving', async (name, action) => {
    const root = await openConfig(config(ark))
    await change(
      root,
      action === 'replace' ? 'Ark API Key' : '清除 Ark API Key',
      action === 'replace' ? 'fixture-unsaved-key' : true,
    )
    await change(root, '模型提供方', name)
    http.mockResolvedValueOnce(response(config(name === 'db1404-local' ? local : disabled)))
    await click(root, '保存并生效')
    expect(savedBody()).toMatchObject({
      provider_name: name,
      provider_api_key: '',
      clear_provider_api_key: false,
      provider_endpoint: config().provider_endpoint,
      provider_model: 'ark-backup-fixture',
      provider_timeout_seconds: 25,
    })
    await change(root, '模型提供方', 'volcengine-ark')
    expect(field(root, 'Ark API Key').props.modelValue).toBe('')
    expect(field(root, '清除 Ark API Key').props.modelValue).toBe(false)
    expect(text(item(root, 'API Key（不回显；留空表示不更改）'))).toContain('已配置')
    expect(field(root, 'Ark 模型 ID').props.modelValue).toBe('ark-backup-fixture')
    expect(field(root, '共用识别超时').props.modelValue).toBe(25)
  })

  it.each(['replace', 'clear'])(
    'still permits an explicit Ark key %s while Ark is visible',
    async (action) => {
      const root = await openConfig()
      await change(root, '模型提供方', 'volcengine-ark')
      await change(
        root,
        action === 'replace' ? 'Ark API Key' : '清除 Ark API Key',
        action === 'replace' ? 'fixture-new-key' : true,
      )
      http.mockResolvedValueOnce(response(config(ark, { provider_api_key_configured: action === 'replace' })))
      await click(root, '保存并生效')
      expect(savedBody()).toMatchObject({
        provider_name: 'volcengine-ark',
        provider_api_key: action === 'replace' ? 'fixture-new-key' : '',
        clear_provider_api_key: action === 'clear',
      })
      expect(field(root, 'Ark API Key').props.modelValue).toBe('')
      expect(field(root, '清除 Ark API Key').props.modelValue).toBe(false)
      expect(text(snapshot(root))).toContain('ark-backup-fixture')
      expect(notices(root)).toBe('')
    },
  )

  it('keeps the saved snapshot on save failure and restores fields on explicit undo', async () => {
    const root = await openConfig()
    await change(root, '模型提供方', 'volcengine-ark')
    await change(root, 'Ark 模型 ID', 'unsaved-model')
    http.mockResolvedValueOnce(response({ message: 'private-error' }, 503))
    await click(root, '保存并生效')
    expect(text(snapshot(root))).toContain('local-fixture-v2')
    expect(notices(root)).toContain('未保存选择')
    expect(field(root, 'Ark 模型 ID').props.modelValue).toBe('unsaved-model')
    expect(alerts(root)).not.toContain('private-error')
    expect(alerts(root)).not.toBe('')
    http.mockResolvedValueOnce(response(config()))
    await click(root, '撤销修改')
    expect(notices(root)).toBe('')
    await change(root, '模型提供方', 'volcengine-ark')
    expect(field(root, 'Ark 模型 ID').props.modelValue).toBe('ark-backup-fixture')
  })

  it('accepts saved unavailable local status instead of claiming the server preview is ready', async () => {
    const root = await openConfig(config(ark))
    await change(root, '模型提供方', 'db1404-local')
    http.mockResolvedValueOnce(
      response(
        config({
          ...local,
          configured: false,
          status: 'unavailable',
          status_message: '本地模型不可用，请联系管理员。',
        }),
      ),
    )
    await click(root, '保存并生效')
    expect(text(snapshot(root))).toContain('服务不可用')
    expect(text(snapshot(root))).not.toContain('本地模型已加载')
    expect(notices(root)).toBe('')
  })

  it('degrades legacy local responses without presenting the backup Ark model as local', async () => {
    const root = await openConfig(
      config(local, {
        recognition_service: undefined,
        local_model_version: undefined,
        local_model_threads: undefined,
      }),
    )
    expect(text(item(root, '当前模型版本'))).toBe('暂未提供')
    expect(text(item(root, '本地模型版本（只读）'))).toBe('暂未提供')
    expect(text(item(root, '本地 CPU 线程数（只读）'))).toBe('暂未提供')
    expect(text(snapshot(root))).not.toContain('ark-backup-fixture')
    expect(text(snapshot(root))).not.toContain('本地模型已加载')
    expect(text(snapshot(root))).toContain('未提供本地模型加载状态')
    expect(field(root, '共用识别超时').props.modelValue).toBe(25)
    await change(root, '模型提供方', 'volcengine-ark')
    expect(field(root, 'Ark 模型 ID').props.modelValue).toBe('ark-backup-fixture')
  })
})

describe('recognition service status and scoped statistics', () => {
  it('renders explicit local status and scoped metrics with safe limitations', async () => {
    const root = await openProvider({ ...statistics(), unexpected_private_field: 'fixture-private-value' })
    expect(text(item(root, '当前提供方'))).toBe('本地 DB1404 模型（CPU）')
    expect(text(item(root, '服务类型'))).toBe('本地 CPU 推理')
    expect(text(item(root, '当前模型版本'))).toBe('local-fixture-v2')
    expect(text(item(root, 'CPU 线程数'))).toBe('2')
    expect(text(item(root, '识别超时'))).toBe('25 秒')
    expect(text(item(root, '最近请求数'))).toBe('8 次')
    expect(text(item(root, '最近失败数'))).toBe('2 次')
    expect(text(item(root, '成功请求 P95 耗时'))).toBe('780 毫秒')
    expect(text(root)).toContain('仅当前提供方、当前模型的最近最多 1000 条请求')
    expect(text(root)).toContain('P95 仅统计成功请求')
    expect(text(root)).toContain('未校准，仅供参考，不代表准确率')
    expect(text(root)).toContain('仅证明加载成功，不代表识别准确率')
    expect(text(root)).not.toMatch(
      /fixture-private-value|unexpected_private_field|current_provider_and_model|automatic_fallback/,
    )
    expect(all(root, (n) => n.props.label === '接口地址配置')).toHaveLength(0)
    expect(http).toHaveBeenCalledTimes(1)
  })

  it('reports Ark configuration rather than tested connectivity and does not show CPU fields', async () => {
    const root = await openProvider(statistics(ark))
    expect(text(root)).toContain('已配置（未探测连接）')
    expect(text(item(root, '当前提供方'))).toBe('火山引擎 Ark（外部服务）')
    expect(text(item(root, '接口地址配置'))).toBe('已配置')
    expect(all(root, (n) => n.props.label === 'CPU 线程数')).toHaveLength(0)
    expect(text(root)).toContain('不调用付费识别 API')
    http.mockResolvedValueOnce(response(statistics(ark)))
    await click(root, '刷新')
    expect(http).toHaveBeenCalledTimes(2)
    expect(http.mock.calls.every(([path, init]) => path === providerPath && !init?.method)).toBe(true)
  })

  it.each([local, ark])('shows unavailable %s even if a configuration flag is true', async (service) => {
    const root = await openProvider(
      statistics({
        ...service,
        configured: true,
        status: 'unavailable',
        status_message: '服务暂不可用，请联系管理员。',
      }),
    )
    expect(text(all(root, (n) => n.type === 'el-tag')[0]!)).toBe('服务不可用')
    expect(alerts(root)).toContain('服务暂不可用，请联系管理员。')
  })

  it('shows disabled state, zero counts and missing successful latency without inventing a value', async () => {
    const root = await openProvider({
      ...statistics(disabled),
      recent_requests: 0,
      recent_errors: 0,
      p95_latency_ms: null,
    })
    expect(text(item(root, '当前提供方'))).toBe('未启用')
    expect(text(item(root, '当前模型版本'))).toBe('未启用')
    expect(text(item(root, '最近请求数'))).toBe('0 次')
    expect(text(item(root, '最近失败数'))).toBe('0 次')
    expect(text(item(root, '成功请求 P95 耗时'))).toBe('暂无数据')
    expect(all(root, (n) => ['CPU 线程数', '接口地址配置', '识别超时'].includes(n.props.label))).toHaveLength(
      0,
    )
    expect(alerts(root)).toContain('识别服务未启用')
  })

  it('does not reuse unscoped legacy metrics or a legacy local Ark model', async () => {
    const root = await openProvider({
      name: 'db1404-local',
      model: 'ark-backup-fixture',
      configured: true,
      recent_requests: 999,
      recent_errors: 3,
      p95_latency_ms: 222,
    })
    expect(text(item(root, '当前模型版本'))).toBe('暂未提供')
    expect(text(item(root, '最近请求数'))).toBe('暂无数据')
    expect(text(item(root, '最近失败数'))).toBe('暂无数据')
    expect(text(item(root, '成功请求 P95 耗时'))).toBe('暂无数据')
    expect(text(root)).toContain('不展示口径不明的旧统计')
    expect(text(root)).not.toContain('ark-backup-fixture')
    expect(text(all(root, (n) => n.type === 'el-tag')[0]!)).toBe('服务不可用')
  })

  it('keeps legacy Ark configuration useful without claiming a connectivity probe', async () => {
    const root = await openProvider({ name: 'volcengine-ark', model: 'legacy-ark', configured: true })
    expect(text(item(root, '当前模型版本'))).toBe('legacy-ark')
    expect(text(root)).toContain('已配置（未探测连接）')
    expect(text(item(root, '接口地址配置'))).toBe('暂未提供')
  })

  it('clears a stale service on failed refresh and can recover explicitly', async () => {
    const root = await openProvider()
    http.mockResolvedValueOnce(response({}, 503))
    await click(root, '刷新')
    expect(text(root)).not.toContain('local-fixture-v2')
    expect(all(root, (n) => n.type === 'el-empty')[0]!.props.description).toBe('服务状态不可用')
    expect(alerts(root)).not.toBe('')
    http.mockResolvedValueOnce(response(statistics()))
    await click(root, '刷新')
    expect(text(root)).toContain('local-fixture-v2')
  })
})
