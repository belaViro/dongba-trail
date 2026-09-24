import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { api, ApiError, errorText, query, save } from '../src/api'
import { initialForm, payloadFor, resources } from '../src/resources'

const data = new Map<string, string>()
beforeEach(() => {
  vi.stubGlobal('sessionStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
  vi.stubGlobal('window', { setTimeout, dispatchEvent: vi.fn() })
  data.set('dongba_access_token', 'test-access-token')
})
afterEach(() => {
  vi.unstubAllGlobals()
  data.clear()
})

describe('HTTP contract', () => {
  it('authenticates and submits the exact API payload', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 'coupon-1' }), { status: 200 }))
    vi.stubGlobal('fetch', fetch)
    const result = await save('/merchant/coupons', { stock: 4 })
    expect(result.id).toBe('coupon-1')
    const [url, options] = fetch.mock.calls[0]!
    expect(url).toBe('/api/v1/merchant/coupons')
    expect(options.headers.get('Authorization')).toBe('Bearer test-access-token')
    expect(options.headers.get('Content-Type')).toBe('application/json')
    expect(JSON.parse(options.body)).toEqual({ stock: 4 })
  })
  it('does not turn a backend rejection into a successful write', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: 'CROSS_MERCHANT',
            message: '无权核销其他门店优惠券',
            request_id: 'request-test',
          }),
          { status: 403 },
        ),
      ),
    )
    try {
      await save('/coupons/verify', { code: 'test' })
      expect.unreachable()
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect(errorText(error)).toContain('无权核销')
      expect(errorText(error)).toContain('request-test')
    }
  })
  it('clears an expired session and notifies the router', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ message: '会话已过期' }), { status: 401 })),
    )
    await expect(api('/admin/users')).rejects.toThrow('会话已过期')
    expect(data.has('dongba_access_token')).toBe(false)
    expect(window.dispatchEvent).toHaveBeenCalledOnce()
  })
  it('does not set JSON content type on image multipart uploads', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ url: '/api/v1/media/test.png' }), { status: 200 }))
    vi.stubGlobal('fetch', fetch)
    await api('/media', { method: 'POST', body: new FormData() })
    expect(fetch.mock.calls[0]![1].headers.has('Content-Type')).toBe(false)
  })
  it('keeps explicit unavailable failures visible', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(api('/admin/stats')).rejects.toThrow('无法连接服务')
  })
  it('preserves zero pagination offsets and safely encodes filters', () => {
    expect(query({ q: '茶 & 酒', offset: 0, status: '', limit: 20 })).toBe(
      'q=%E8%8C%B6+%26+%E9%85%92&offset=0&limit=20',
    )
  })
})

describe('business form boundaries', () => {
  it('does not fabricate zero coordinates for an unlocated merchant', () => {
    const form = initialForm(resources.merchants!)
    expect(form.latitude).toBeNull()
    expect(form.longitude).toBeNull()
  })
  it('does not let a merchant assign ownership or authoritative culture associations', () => {
    const form = initialForm(resources.products!, {
      merchant_id: 'other-owner',
      character_ids: ['invented'],
      name: '商品',
      price: 4,
    })
    const payload = payloadFor(resources.products!, form, true, false)
    expect(payload).not.toHaveProperty('merchant_id')
    expect(payload).not.toHaveProperty('character_ids')
    expect(payload.name).toBe('商品')
    const merchant = payloadFor(
      resources.merchants!,
      initialForm(resources.merchants!, { operation_weight: 1, merchant_quality: 1 }),
      true,
      true,
    )
    expect(merchant).not.toHaveProperty('operation_weight')
    expect(merchant).not.toHaveProperty('merchant_quality')
    expect(merchant).not.toHaveProperty('tags')
  })
  it('keeps existing passwords and immutable dictionary IDs out of update payloads', () => {
    const account = payloadFor(
      resources.users!,
      initialForm(resources.users!, { username: 'operator' }),
      false,
      true,
    )
    expect(account).not.toHaveProperty('password')
    const character = payloadFor(
      resources.characters!,
      initialForm(resources.characters!, { id: 'fixed-id' }),
      false,
      true,
    )
    expect(character).not.toHaveProperty('id')
  })
  it('copies mutable variants so cancelling edits cannot mutate table data', () => {
    const record = reactive({
      variants: [{ image_url: 'original.png', source_ref: '审核资料' }],
      tags: ['nature'],
    })
    const draft = initialForm(resources.characters!, record)
    draft.variants[0].source_ref = 'changed'
    draft.tags.push('new')
    expect(record.variants[0]?.source_ref).toBe('审核资料')
    expect(record.tags).toEqual(['nature'])
  })
  it('represents empty optional relations as null', () => {
    const payload = payloadFor(resources.quests!, initialForm(resources.quests!), false, false)
    expect(payload.reward_coupon_id).toBeNull()
  })
  it('lets the server generate omitted QR tokens without sending an invalid empty token', () => {
    const payload = payloadFor(
      resources['quest-nodes']!,
      initialForm(resources['quest-nodes']!),
      false,
      false,
    )
    expect(payload.qr_token).toBeNull()
  })
})
