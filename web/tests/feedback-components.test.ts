// @vitest-environment ./tests/component-environment.ts
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { all, button, flush, mount, text } from './component-harness'
import FeedbackView from '../src/views/FeedbackView.vue'

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  save: vi.fn(),
  success: vi.fn(),
  prompt: vi.fn(),
  confirm: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }))
vi.mock('element-plus', () => ({
  ElMessage: { success: mocks.success },
  ElMessageBox: { confirm: mocks.confirm, prompt: mocks.prompt },
}))
vi.mock('../src/api', async (original) => ({
  ...(await original<typeof import('../src/api')>()),
  api: mocks.api,
  save: mocks.save,
}))
vi.mock('../src/components/SampleImage.vue', () => ({ default: { render: () => null } }))
let instance: ReturnType<typeof mount> | undefined
let feedback: Record<string, any>
beforeEach(() => {
  vi.resetAllMocks()
  mocks.prompt.mockResolvedValue({ value: '需重新核对' })
  mocks.confirm.mockResolvedValue('confirm')
  feedback = {
    id: 'fb',
    recognition_id: 'req',
    status: 'pending',
    character_id: 'word',
    comment: '识别有误',
    rag_status: 'not_indexed',
    sample: null,
    recognition: { observed_text: '原识别', candidates: [] },
  }
  mocks.api.mockImplementation(async (path: string) => {
    if (path.startsWith('/admin/characters?'))
      return { items: [{ id: 'word', cn_name: '正确词条' }], total: 1 }
    if (path === '/admin/feedback/fb') return { ...feedback }
    if (path.startsWith('/admin/feedback?')) return { items: [{ ...feedback }], total: 1 }
    throw new Error(`Unexpected request: ${path}`)
  })
  mocks.save.mockImplementation(async (_path, payload) => {
    feedback = {
      ...feedback,
      ...payload,
      rag_status: payload.status === 'approved' ? 'indexed' : 'not_indexed',
    }
    return { ...feedback }
  })
})
afterEach(() => instance?.unmount())
async function open() {
  instance = mount(FeedbackView)
  await flush()
  const table = all(instance.root, (n) => n.type === 'el-table')[0]!
  await table.props.onRowDblclick(feedback)
  await flush()
  return instance.root
}
it('explains that missing correction images were not retained rather than pretending to load one', async () => {
  const root = await open()
  const empty = all(root, (n) => n.type === 'el-empty')[0]!
  expect(empty.props.description).toBe('未保存附图，原图无法恢复')
  expect(text(root)).not.toContain('不能用字典图片代替')
})
it('uses a wide drawer review workspace with one close control and no duplicate page navigation', async () => {
  const root = await open()
  const drawer = all(root, (n) => n.type === 'el-drawer')[0]!
  expect(drawer.props.title).toBe('纠错详情与核验')
  expect(drawer.props.size).toBe('min(1120px, 100vw)')
  expect(all(root, (n) => n.type === 'el-button' && text(n) === '返回列表')).toHaveLength(0)
  expect(all(root, (n) => n.props.class === 'review-page')).toHaveLength(0)
})
it('can retry an initially failed detail load from the page refresh action', async () => {
  const original = mocks.api.getMockImplementation()!
  let failed = true
  mocks.api.mockImplementation(async (path: string) => {
    if (path === '/admin/feedback/fb' && failed) throw new Error('暂时断网')
    return original(path)
  })
  const root = await open()
  expect(
    all(root, (n) => n.type === 'el-alert').some((n) => String(n.props.title).includes('暂时断网')),
  ).toBe(true)
  failed = false
  await button(root, '刷新状态').props.onClick()
  await flush()
  expect(text(root)).toContain('采纳并生效')
  expect(mocks.api.mock.calls.filter(([path]) => path === '/admin/feedback/fb')).toHaveLength(2)
})
it('adopts in one action and displays indexed without a second review', async () => {
  const root = await open()
  await button(root, '采纳并生效').props.onClick()
  await flush()
  expect(mocks.save).toHaveBeenCalledWith(
    '/admin/feedback/fb',
    { status: 'approved', character_id: 'word', review_note: '' },
    'PATCH',
  )
  expect(text(root)).toContain('已生效')
  expect(text(root)).not.toContain('发布案例')
})
it('allows rejection without a note and never calls RAG creation', async () => {
  const root = await open()
  await button(root, '驳回').props.onClick()
  await flush()
  expect(mocks.save).toHaveBeenCalledTimes(1)
  expect(mocks.save).toHaveBeenCalledWith(
    '/admin/feedback/fb',
    expect.objectContaining({ status: 'rejected', review_note: '' }),
    'PATCH',
  )
  expect(text(root)).toContain('已驳回')
})
it('keeps the decision actionable and reports failure when indexing is unavailable', async () => {
  mocks.save.mockRejectedValue(new Error('识别参考暂不可用'))
  const root = await open()
  await button(root, '采纳并生效').props.onClick()
  await flush()
  expect(mocks.success).not.toHaveBeenCalled()
  expect(
    all(root, (n) => n.type === 'el-alert').some((n) => String(n.props.title).includes('尚未确认采纳成功')),
  ).toBe(true)
  expect(button(root, '采纳并生效').props.loading).toBe(false)
})
it('requires the operator to select a word for text-only feedback', async () => {
  feedback.character_id = null
  const root = await open()
  await button(root, '采纳并生效').props.onClick()
  expect(mocks.save).not.toHaveBeenCalled()
  expect(
    all(root, (n) => n.type === 'el-alert').some((n) => n.props.title === '请选择核验后的已发布词条'),
  ).toBe(true)
})
it('removes the duplicate navigation and redirects legacy routes', () => {
  const app = readFileSync('src/App.vue', 'utf8')
  const router = readFileSync('src/router.ts', 'utf8')
  expect(app).not.toContain("path: 'samples'")
  expect(app).not.toContain("path: 'rag-cases'")
  expect(router).not.toContain("import('./views/SamplesView.vue')")
  expect(router).not.toContain("import('./views/RagCasesView.vue')")
  expect(router).toContain("path: '/admin/rag-cases', redirect: '/admin/feedback'")
})

it('keeps a supplied rejection note', async () => {
  const root = await open()
  const note = all(root, (n) => n.type === 'el-input' && n.props.type === 'textarea')[0]!
  note.props['onUpdate:modelValue'](' 信息无法核实 ')
  await button(root, '驳回').props.onClick()
  expect(mocks.save).toHaveBeenCalledWith(
    '/admin/feedback/fb',
    expect.objectContaining({ review_note: '信息无法核实' }),
    'PATCH',
  )
})

function approved() {
  feedback.status = 'approved'
  feedback.rag_status = 'indexed'
  feedback.rag_case = { id: 'case', status: 'indexed', updated_at: '2026-09-27T10:00:00Z' }
  mocks.save.mockImplementation(async (path: string) => {
    const status = path.endsWith('/deprecate') ? 'deprecated' : 'indexed'
    feedback = {
      ...feedback,
      rag_status: status,
      rag_updated_at: '2026-09-27T10:01:00Z',
      rag_case: { id: 'case', status, updated_at: '2026-09-27T10:01:00Z' },
    }
    return { ...feedback.rag_case }
  })
}
it('refreshes list and detail after disable, enable and repeated reindex', async () => {
  approved()
  const root = await open()
  const menu = all(root, (n) => n.type === 'el-dropdown')[0]!
  await menu.props.onCommand('deprecate')
  await flush()
  const table = () => all(root, (n) => n.type === 'el-table')[0]!.props.data[0]
  expect(table().status).toBe('approved')
  expect(table().rag_status).toBe('deprecated')
  expect(text(root)).toContain('已停用')
  await menu.props.onCommand('reindex')
  await flush()
  expect(table().rag_status).toBe('indexed')
  await menu.props.onCommand('reindex')
  await flush()
  expect(table().rag_updated_at).toBe('2026-09-27T10:01:00Z')
  expect(mocks.api.mock.calls.filter(([path]) => path.startsWith('/admin/feedback?'))).toHaveLength(4)
  expect(mocks.api.mock.calls.filter(([path]) => path === '/admin/feedback/fb')).toHaveLength(4)
})
it('retains server-confirmed maintenance state and exposes refresh errors', async () => {
  approved()
  const root = await open()
  const menu = all(root, (n) => n.type === 'el-dropdown')[0]!
  mocks.api.mockRejectedValue(new Error('网络断开'))
  await menu.props.onCommand('deprecate')
  await flush()
  expect(text(root)).toContain('已停用')
  expect(all(root, (n) => n.type === 'el-table')[0]!.props.data[0].rag_status).toBe('deprecated')
  const errors = all(root, (n) => n.type === 'el-alert')
    .map((n) => n.props.title)
    .join(' ')
  expect(errors).toContain('列表刷新失败')
  expect(errors).toContain('详情刷新失败')
})

it('condenses pending status and hides internal word IDs and repeated workflow copy', async () => {
  const root = await open()
  const status = all(root, (n) => n.props.class === 'review-overview')[0]!
  expect(text(status).trim()).toBe('待审核')
  expect(text(root)).not.toMatch(/一次处理|历史决定|说明选填|采纳时必选|未填写/)
  const choices = all(root, (n) => n.type === 'el-option' && n.props.value === 'word')
  expect(choices[0]!.props.label).toBe('正确词条')
  expect(all(root, (n) => n.type === 'details')[0]!.props.open).toBeUndefined()
})

it('preserves the original decision in the compact deprecated status', async () => {
  approved()
  feedback.rag_status = 'deprecated'
  const root = await open()
  expect(text(all(root, (n) => n.props.class === 'review-overview')[0]!)).toContain('已采纳 · 已停用')
  expect(all(root, (n) => n.type === 'el-dropdown-item' && n.props.command === 'deprecate')).toHaveLength(0)
  expect(text(root)).not.toContain('未填写')
  expect(all(root, (n) => n.props.class === 'review-footer')).toHaveLength(0)
})

it('asks for a required disable reason only after selecting the menu action', async () => {
  approved()
  const root = await open()
  expect(mocks.prompt).not.toHaveBeenCalled()
  expect(all(root, (n) => n.type === 'el-input' && n.props.placeholder === '请输入停用原因')).toHaveLength(0)
  await all(root, (n) => n.type === 'el-dropdown')[0]!.props.onCommand('deprecate')
  const options = mocks.prompt.mock.calls[0]![2]
  expect(options.inputValidator('   ')).toBe('请填写停用原因')
  expect(options.inputValidator('已核对')).toBe(true)
  expect(mocks.save).toHaveBeenCalledWith('/admin/rag/cases/case/deprecate', { reason: '需重新核对' })
})

it('cancels disable without changing data and permits closing afterward', async () => {
  approved()
  mocks.prompt.mockRejectedValue('cancel')
  const root = await open()
  await all(root, (n) => n.type === 'el-dropdown')[0]!.props.onCommand('deprecate')
  expect(mocks.save).not.toHaveBeenCalled()
  const done = vi.fn()
  all(root, (n) => n.type === 'el-drawer')[0]!.props['before-close'](done)
  expect(done).toHaveBeenCalledOnce()
})

it('blocks closing during mutation and unlocks after server response', async () => {
  let resolve!: (data: unknown) => void
  mocks.save.mockImplementation(
    () =>
      new Promise((done) => {
        resolve = done
      }),
  )
  const root = await open()
  const task = button(root, '驳回').props.onClick()
  await flush()
  const drawer = all(root, (n) => n.type === 'el-drawer')[0]!
  const done = vi.fn()
  drawer.props['before-close'](done)
  expect(done).not.toHaveBeenCalled()
  expect(drawer.props['close-on-press-escape']).toBe(false)
  feedback.status = 'rejected'
  resolve({ ...feedback })
  await task
  await flush()
  drawer.props['before-close'](done)
  expect(done).toHaveBeenCalledOnce()
})

it('keeps unavailable state explicit and does not offer destructive maintenance', async () => {
  approved()
  feedback.rag_status = 'unavailable'
  const root = await open()
  expect(text(root)).toContain('识别参考暂不可用')
  expect(button(root, '重试生效')).toBeDefined()
  expect(all(root, (n) => n.type === 'el-dropdown')).toHaveLength(0)
})
