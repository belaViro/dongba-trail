// @vitest-environment ./tests/component-environment.ts
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { all, button, flush, mount } from './component-harness'
import RagCasesView from '../src/views/RagCasesView.vue'

const mocks = vi.hoisted(() => ({ list: vi.fn(), stats: vi.fn(), create: vi.fn(), search: vi.fn() }))
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn() },
  ElMessageBox: { confirm: vi.fn() },
}))
vi.mock('../src/rag', async (original) => ({
  ...(await original<typeof import('../src/rag')>()),
  listRagCases: mocks.list,
  getRagStats: mocks.stats,
  createRagCase: mocks.create,
  searchRagCases: mocks.search,
}))
vi.mock('../src/components/MediaImage.vue', () => ({ default: { render: () => null } }))
let instance: ReturnType<typeof mount> | undefined
beforeEach(() => {
  vi.resetAllMocks()
  mocks.list.mockResolvedValue({ items: [], total: 0 })
  mocks.stats.mockResolvedValue({ total: 0 })
  mocks.create.mockResolvedValue({ id: 'case', status: 'pending' })
})
afterEach(() => instance?.unmount())

it('requires a published dictionary ID and submits optional text as strings, not null', async () => {
  instance = mount(RagCasesView)
  const { root } = instance
  await flush()
  button(root, '新增案例').props.onClick()
  await flush()
  const dialog = all(root, (n) => n.type === 'el-dialog' && n.props.modelValue)[0]!
  const inputs = all(dialog, (n) => n.type === 'el-input')
  inputs[0]!.props['onUpdate:modelValue']('房屋')
  inputs[1]!.props['onUpdate:modelValue']('纠正文本')
  await button(root, '保存案例').props.onClick()
  expect(mocks.create).not.toHaveBeenCalled()
  inputs[2]!.props['onUpdate:modelValue']('CHAR_TEST')
  await button(root, '保存案例').props.onClick()
  await flush()
  expect(mocks.create).toHaveBeenCalledWith(
    expect.objectContaining({
      text: '房屋',
      answer: '纠正文本',
      character_id: 'CHAR_TEST',
      scene: '',
      image_uri: '',
      sample_id: null,
    }),
  )
  expect(mocks.list).toHaveBeenCalledTimes(2)
})

it('shows unavailable database failures rather than pretending the library is empty', async () => {
  mocks.list.mockRejectedValue(new Error('RAG 数据库暂时不可用'))
  instance = mount(RagCasesView)
  await flush()
  const alerts = all(instance.root, (n) => n.type === 'el-alert')
  expect(alerts.some((n) => String(n.props.title).includes('RAG 数据库暂时不可用'))).toBe(true)
})
