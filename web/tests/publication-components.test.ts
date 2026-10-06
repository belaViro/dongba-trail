// @vitest-environment ./tests/component-environment.ts
// OPS-01 / AUTH-02: synthetic component fixtures, not live business acceptance.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { all, flush, mount, text, type HostNode } from './component-harness'
import ResourceView from '../src/views/ResourceView.vue'
import { session } from '../src/session'

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  save: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
  confirm: vi.fn(),
}))
vi.mock('element-plus', () => ({
  ElMessage: { success: mocks.success, error: mocks.error },
  ElMessageBox: { confirm: mocks.confirm },
}))
vi.mock('../src/api', async (original) => ({
  ...(await original<typeof import('../src/api')>()),
  api: mocks.api,
  save: mocks.save,
}))
vi.mock('../src/components/MediaImage.vue', () => ({ default: { render: () => null } }))
vi.mock('../src/components/EntityForm.vue', () => ({ default: { render: () => null } }))
vi.mock('../src/components/RevisionHistory.vue', () => ({ default: { render: () => null } }))

const mounted: Array<ReturnType<typeof mount>> = []
function menus(root: HostNode) {
  return all(root, (node) => node.type === 'el-dropdown-item')
}
function dropdown(root: HostNode) {
  return all(root, (node) => node.type === 'el-dropdown')[0]!
}
async function page(status = 'draft', resource = 'characters') {
  const row = reactive({ id: 'synthetic-item', cn_name: '合成条目', name: '合成内容', status })
  mocks.api.mockResolvedValue({ items: [row], total: 1 })
  const result = mount(ResourceView, { resource }, { tableRows: [row] })
  mounted.push(result)
  await flush()
  return { ...result, row }
}
beforeEach(() => {
  vi.clearAllMocks()
  mocks.save.mockReset().mockResolvedValue({})
  session.user = { id: 'synthetic-admin', username: 'synthetic', display_name: '合成管理员', role: 'admin' }
})
afterEach(() => {
  mounted.splice(0).forEach((result) => result.unmount())
  session.user = null
})

describe('single review-and-publish action', () => {
  it.each(['characters', 'merchants', 'pois', 'products', 'coupons', 'activities', 'quests', 'quest-nodes'])(
    'offers one combined publication action for %s',
    async (resource) => {
      const { root } = await page('draft', resource)
      const actions = menus(root)
      expect(actions.filter((node) => node.props.command === 'published')).toHaveLength(1)
      expect(actions.some((node) => node.props.command === 'reviewed')).toBe(false)
      expect(
        actions.find((node) => node.props.command === 'published') &&
          text(actions.find((node) => node.props.command === 'published')!).trim(),
      ).toBe('审核并发布')
    },
  )
  it.each(['admin', 'operator'] as const)('lets %s publish directly and refreshes state', async (role) => {
    session.user!.role = role
    const { root, row } = await page()
    mocks.save.mockImplementation(async () => {
      row.status = 'published'
      return { ...row }
    })
    dropdown(root).props.onCommand('published')
    await flush()
    expect(mocks.save).toHaveBeenCalledExactlyOnceWith(
      '/admin/characters/synthetic-item',
      { status: 'published' },
      'PATCH',
    )
    expect(mocks.success).toHaveBeenCalledWith('已审核并发布')
    expect(mocks.api).toHaveBeenCalledTimes(2)
    expect(menus(root).some((node) => ['reviewed', 'published'].includes(node.props.command))).toBe(false)
  })
  it('preserves legacy reviewed rows until an explicit publish action', async () => {
    const { root, row } = await page('reviewed')
    expect(row.status).toBe('reviewed')
    expect(mocks.save).not.toHaveBeenCalled()
    expect(menus(root).filter((node) => node.props.command === 'published')).toHaveLength(1)
  })
  it('has no review downgrade on published rows and ignores stale reviewed commands', async () => {
    const { root } = await page('published')
    expect(menus(root).some((node) => ['reviewed', 'published'].includes(node.props.command))).toBe(false)
    dropdown(root).props.onCommand('reviewed')
    await flush()
    expect(mocks.save).not.toHaveBeenCalled()
  })
  it('does not report publication success when backend validation fails', async () => {
    const { root, row } = await page()
    mocks.save.mockRejectedValue(new Error('缺少字形图片，不能发布'))
    dropdown(root).props.onCommand('published')
    await flush()
    expect(row.status).toBe('draft')
    expect(mocks.error).toHaveBeenCalledWith('缺少字形图片，不能发布')
    expect(mocks.success).not.toHaveBeenCalled()
    expect(menus(root).some((node) => node.props.command === 'published')).toBe(true)
  })
  it('keeps publication controls out of the merchant workspace', async () => {
    session.user!.role = 'merchant'
    const { root } = await page('draft', 'products')
    expect(menus(root).some((node) => ['reviewed', 'published', 'draft'].includes(node.props.command))).toBe(
      false,
    )
    expect(mocks.api.mock.calls[0]![0]).toMatch(/^\/merchant\/products\?/)
  })
  it('retains the separate account activation action', async () => {
    const { root } = await page('disabled', 'users')
    expect(menus(root).some((node) => node.props.command === 'active')).toBe(true)
    expect(menus(root).some((node) => ['reviewed', 'published'].includes(node.props.command))).toBe(false)
  })
})
