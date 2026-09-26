// @vitest-environment ./tests/component-environment.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { all, button, flush, mount, text } from './component-harness'
import SamplesView from '../src/views/SamplesView.vue'
import RecordsView from '../src/views/RecordsView.vue'
import RevisionHistory from '../src/components/RevisionHistory.vue'

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  list: vi.fn(),
  upload: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  export: vi.fn(),
  push: vi.fn(),
  confirm: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
  route: { query: {} as Record<string, string> },
}))
vi.mock('vue-router', () => ({ useRoute: () => mocks.route, useRouter: () => ({ push: mocks.push }) }))
vi.mock('element-plus', () => ({
  ElMessage: { success: mocks.success, error: mocks.error },
  ElMessageBox: { confirm: mocks.confirm },
}))
vi.mock('../src/api', async (original) => ({
  ...(await original<typeof import('../src/api')>()),
  api: mocks.api,
}))
vi.mock('../src/samples', async (original) => ({
  ...(await original<typeof import('../src/samples')>()),
  listSamples: mocks.list,
  uploadSample: mocks.upload,
  updateSample: mocks.update,
  deleteSample: mocks.remove,
  exportSamples: mocks.export,
}))
vi.mock('../src/components/EntityForm.vue', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    default: defineComponent({
      inheritAttrs: false,
      setup(_, { attrs, expose }) {
        expose({ validate: () => Promise.resolve(true) })
        return () => h('entity-form', attrs)
      },
    }),
  }
})
vi.mock('../src/components/SampleImage.vue', () => ({
  default: { props: ['sampleId', 'bbox'], render: () => null },
}))
vi.mock('../src/components/MediaImage.vue', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    default: defineComponent({
      inheritAttrs: false,
      setup:
        (_, { attrs }) =>
        () =>
          h('media-image', attrs),
    }),
  }
})

const sample = {
  id: 'synthetic-sample',
  recognition_id: 'synthetic-request',
  character_id: 'synthetic-character',
  image_uri: '/api/v1/media/private.png',
  sample_type: 'dictionary',
  scene: 'paper',
  bbox: null,
  quality_score: null,
  label_source: 'source_material',
  review_status: 'pending',
  dataset_split: 'unassigned',
  dataset_version: '',
  source_ref: '合成测试来源',
  review_note: '',
}
const mounted: ReturnType<typeof mount>[] = []
function view(component: Parameters<typeof mount>[0], props = {}) {
  const instance = mount(component, props)
  mounted.push(instance)
  return instance.root
}
beforeEach(() => {
  vi.clearAllMocks()
  mocks.route = reactive({ query: {} })
  mocks.list.mockResolvedValue({ items: [], total: 0 })
  mocks.api.mockResolvedValue({ items: [], total: 0 })
  mocks.upload.mockResolvedValue({ ...sample })
  mocks.update.mockResolvedValue({ ...sample })
})
afterEach(() => {
  for (const instance of mounted.splice(0)) instance.unmount()
})

describe('sample page wiring (in-memory components, not browser acceptance)', () => {
  it('honors recognition deep links and reloads when only route query changes', async () => {
    mocks.route.query = { recognition_id: 'first-request' }
    const root = view(SamplesView)
    await flush()
    expect(mocks.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ recognition_id: 'first-request' }),
      1,
      20,
    )
    expect(button(root, '上传样本')).toBeTruthy()
    expect(button(root, '筛选导出')).toBeTruthy()
    mocks.route.query = { recognition_id: 'second-request' }
    await flush()
    expect(mocks.list).toHaveBeenCalledTimes(2)
    expect(mocks.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ recognition_id: 'second-request' }),
      1,
      20,
    )
  })
  it('opens uploaded metadata, validates rejection and persists explicit review', async () => {
    const root = view(SamplesView)
    await flush()
    const upload = all(root, (element) => element.type === 'el-upload')[0]!
    await upload.props.httpRequest({ file: new File(['fixture'], 'synthetic.png') })
    await flush()
    expect(mocks.upload).toHaveBeenCalledOnce()
    const formNode = all(root, (element) => element.type === 'entity-form')[0]!
    const form = formNode.props.modelValue
    form.review_status = 'rejected'
    form.review_note = ' '
    await button(root, '保存元数据与审核').props.onClick()
    await flush()
    expect(mocks.update).not.toHaveBeenCalled()
    expect(
      all(root, (element) => element.type === 'el-alert').some(
        (element) => element.props.title === '请填写驳回原因',
      ),
    ).toBe(true)
    form.review_note = '合成资料需要补充来源'
    await button(root, '保存元数据与审核').props.onClick()
    await flush()
    expect(mocks.update).toHaveBeenCalledWith(
      sample.id,
      expect.objectContaining({ review_status: 'rejected', review_note: '合成资料需要补充来源' }),
    )
    expect(all(root, (element) => element.type === 'el-drawer')[0]!.props.modelValue).toBe(false)
  })
  it('keeps the edit drawer open and shows backend review rejection', async () => {
    mocks.update.mockRejectedValueOnce(new Error('关联词条不可审核'))
    const root = view(SamplesView)
    await flush()
    await all(root, (element) => element.type === 'el-upload')[0]!.props.httpRequest({
      file: new File(['fixture'], 'synthetic.png'),
    })
    await flush()
    await button(root, '保存元数据与审核').props.onClick()
    await flush()
    expect(all(root, (element) => element.type === 'el-drawer')[0]!.props.modelValue).toBe(true)
    expect(
      all(root, (element) => element.type === 'el-alert').some(
        (element) => element.props.title === '关联词条不可审核',
      ),
    ).toBe(true)
  })
  it('defaults export to approved and passes the captured non-status filters', async () => {
    mocks.export.mockRejectedValueOnce(new Error('样本图片不可用'))
    mocks.route.query = { recognition_id: 'req', dataset_version: 'v1' }
    const root = view(SamplesView)
    await flush()
    button(root, '筛选导出').props.onClick()
    await flush()
    const select = all(root, (element) => element.props['aria-label'] === '导出审核状态')[0]!
    expect(select.props.modelValue).toBe('approved')
    select.props['onUpdate:modelValue']('pending')
    await button(root, '下载ZIP').props.onClick()
    await flush()
    expect(mocks.export).toHaveBeenCalledWith(
      expect.objectContaining({ recognition_id: 'req', dataset_version: 'v1' }),
      'pending',
      1000,
    )
    expect(
      all(root, (element) => element.type === 'el-alert').some(
        (element) => element.props.title === '样本图片不可用',
      ),
    ).toBe(true)
  })
  it('shows unavailable list failures instead of old rows', async () => {
    mocks.list.mockRejectedValueOnce(new Error('服务不可用'))
    const root = view(SamplesView)
    await flush()
    expect(all(root, (element) => element.type === 'el-table')[0]!.props.data).toEqual([])
    expect(
      all(root, (element) => element.type === 'el-alert').some(
        (element) => element.props.title === '服务不可用',
      ),
    ).toBe(true)
  })
})

describe('record query navigation', () => {
  it('loads q from links and follows query-only changes', async () => {
    mocks.route.query = { q: 'request-1' }
    view(RecordsView, { resource: 'recognitions' })
    await flush()
    expect(mocks.api).toHaveBeenLastCalledWith('/admin/recognitions?q=request-1&offset=0&limit=20')
    mocks.route.query = { q: 'request-2' }
    await flush()
    expect(mocks.api).toHaveBeenLastCalledWith('/admin/recognitions?q=request-2&offset=0&limit=20')
  })
})

describe('history selection renders original complete snapshots', () => {
  it('switches text, source, review status and authenticated images together', async () => {
    const oldText = '完整合成旧文化文本'.repeat(40)
    mocks.api.mockResolvedValueOnce({
      items: [
        {
          id: 'old',
          entity_id: 'char',
          version: 1,
          action: 'baseline',
          actor_id: null,
          snapshot: {
            culture_detail: oldText,
            source_ref: '合成旧来源',
            status: 'reviewed',
            reviewed_by: 'old-reviewer',
            image_url: '/api/v1/media/old.png',
            variants: [{ image_url: '/api/v1/media/old-variant.png', source_ref: '合成异形来源' }],
          },
        },
        {
          id: 'new',
          entity_id: 'char',
          version: 2,
          action: 'update',
          actor_id: 'operator',
          snapshot: {
            culture_detail: '合成新文本',
            source_ref: '合成新来源',
            status: 'draft',
            image_url: '/api/v1/media/new.png',
            variants: [],
          },
        },
      ],
      total: 2,
    })
    const root = view(RevisionHistory, { resource: 'characters', entityId: 'char' })
    await flush()
    expect(mocks.api).toHaveBeenCalledWith('/admin/characters/char/revisions')
    expect(text(root)).toContain('合成新文本')
    const selector = all(root, (element) => element.props['aria-label'] === '历史版本')[0]!
    expect(selector.props.modelValue).toBe('new')
    selector.props['onUpdate:modelValue']('old')
    await flush()
    expect(text(root)).toContain(oldText)
    expect(text(root)).toContain('合成旧来源')
    expect(text(root)).toContain('合成异形来源')
    expect(text(root)).toContain('old-reviewer')
    expect(text(root)).toContain('已审核')
    expect(text(root)).not.toContain('合成新文本')
    expect(
      all(root, (element) => element.type === 'media-image').map((element) => element.props.src),
    ).toEqual(['/api/v1/media/old.png', '/api/v1/media/old-variant.png'])
    expect(mocks.api).toHaveBeenCalledOnce()
  })
  it('distinguishes an unavailable API from an empty history and supports retry', async () => {
    mocks.api.mockRejectedValueOnce(new Error('历史接口不可用'))
    const root = view(RevisionHistory, { resource: 'characters', entityId: 'char' })
    await flush()
    expect(
      all(root, (element) => element.type === 'el-alert').some(
        (element) => element.props.title === '历史接口不可用',
      ),
    ).toBe(true)
    await button(root, '刷新历史').props.onClick()
    await flush()
    expect(all(root, (element) => element.type === 'el-empty')[0]!.props.description).toBe(
      '暂无可查询的历史版本',
    )
  })
})
