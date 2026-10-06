import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { api, apiBlob, ApiError, errorText } from '../src/api'

// AUTH-02 / FEEDBACK-01 / OPS-03 / ANALYTICS-01, D-053: client copy boundaries.
beforeEach(() => {
  vi.stubGlobal('sessionStorage', { getItem: () => null, removeItem: vi.fn() })
  vi.stubGlobal('window', { setTimeout, dispatchEvent: vi.fn() })
})
afterEach(() => vi.unstubAllGlobals())
const reply = (body: unknown, status = 503) => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })))
}

describe('public error messages', () => {
  it.each([
    { code: 'UNKNOWN', message: '数据库异常 /srv/internal.py SQL SELECT password' },
    { detail: 'Traceback /srv/internal.py' },
    { detail: [{ msg: 'ValueError DB_HOST', loc: ['body', 'private_field'] }] },
    { code: 'constructor', message: '内部字段' },
  ])('does not render remote implementation details %#', async (body) => {
    reply(body)
    await expect(api('/admin/stats')).rejects.toThrow('请求未完成，请稍后重试')
  })
  it('keeps a useful known failure and its support request ID', async () => {
    reply({ code: 'RAG_DATABASE_UNAVAILABLE', message: '内部连接串', request_id: 'request-test' })
    const failure = await api('/admin/feedback').catch((error) => error)
    expect(failure).toBeInstanceOf(ApiError)
    expect(errorText(failure)).toBe('识别参考暂不可用，请稍后重试或联系管理员 · 请求编号 request-test')
  })
  it('does not render arbitrary text through the request ID', async () => {
    reply({ request_id: 'SQL error /srv/private.py' })
    const failure = await api('/admin/stats').catch((error) => error)
    expect(errorText(failure)).toBe('请求未完成，请稍后重试')
  })
  it('provides a safe validation message without raw schema details', async () => {
    reply({ detail: [{ msg: 'Field required: business_private_field' }] }, 422)
    await expect(api('/admin/feedback')).rejects.toThrow('提交内容不符合要求，请检查后重试')
  })
  it('applies the same policy to downloads', async () => {
    reply({ message: '内部文件 /srv/uploads/private.png 不存在' })
    await expect(apiBlob('/media/private.png')).rejects.toThrow('请求未完成，请稍后重试')
  })
  it('does not display parser errors on malformed success responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>internal proxy</html>')))
    await expect(api('/admin/stats')).rejects.toThrow('暂时无法读取内容，请稍后重试')
  })
})

describe('user-facing copy', () => {
  const source = (file: string) => readFileSync(resolve('src', file), 'utf8')
  it('removes the assigned-role explanation from login', () => {
    expect(source('views/LoginView.vue')).not.toContain('商户与运营人员使用已分配的账号登录')
    expect(source('views/LoginView.vue')).toContain('请输入登录账号')
  })
  it('keeps truthful metric and demo qualifications, not development notes', () => {
    const dashboard = source('views/DashboardView.vue')
    expect(dashboard).not.toMatch(/参考图|现有接口|待后端|没有真实评测集/)
    expect(dashboard).toContain('不代表识别准确率')
    expect(source('components/PoiMap.vue')).toContain('演示点位不代表实地核验')
  })
  it('uses business status names without changing the underlying maintenance actions', () => {
    const feedback = source('views/FeedbackView.vue')
    expect(feedback).toContain('采纳并生效')
    expect(feedback).toContain('生效状态')
    expect(feedback).toContain("maintain('reindex')")
    expect(feedback).not.toMatch(/加入 RAG|RAG 当前状态|无需重复审核或发布/)
  })
})
