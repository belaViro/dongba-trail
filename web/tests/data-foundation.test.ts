import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { apiBlob } from '../src/api'
import {
  deleteSample,
  exportSamples,
  listSamples,
  recordSampleLink,
  sampleDraft,
  sampleEditDraft,
  sampleExportPayload,
  samplePayload,
  sampleRecordLink,
  sampleValidation,
  updateSample,
  uploadSample,
  type SampleFilters,
} from '../src/samples'
import { loadRevisions, snapshotFields, snapshotText } from '../src/revisions'

// DATA-03/04, FEEDBACK-01, OPS-01/03, PRIVACY-01. Synthetic fixtures, not recognition accuracy.
const filters: SampleFilters = {
  q: '',
  review_status: '',
  character_id: '',
  recognition_id: '',
  dataset_version: '',
}
const sample = {
  id: 'synthetic-sample',
  image_uri: '/api/v1/media/private.png',
  recognition_id: 'synthetic-request',
  character_id: 'synthetic-character',
  sample_type: 'dictionary',
  scene: 'paper',
  bbox: null,
  quality_score: null,
  label_source: 'source_material',
  review_status: 'pending',
  dataset_split: 'unassigned',
  dataset_version: '',
  source_ref: '合成测试资料',
  review_note: '',
  user_id: 'synthetic-user',
  reviewed_by: null,
  reviewed_at: null,
}
const fetchMock = vi.fn<typeof fetch>()
beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('sessionStorage', { getItem: () => 'synthetic-token', removeItem: vi.fn() })
  vi.stubGlobal('window', { setTimeout, dispatchEvent: vi.fn() })
})
afterEach(() => vi.unstubAllGlobals())
function json(value: unknown, status = 200) {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(value), { status }))
}
function requestBody() {
  return JSON.parse(fetchMock.mock.calls.at(-1)![1]!.body as string)
}

describe('sample metadata boundaries', () => {
  it('clones bbox and strips identity, private media, consent and audit fields', () => {
    const row = reactive({ ...sample, bbox: [0, 0, 20, 30] })
    const draft = sampleDraft(row)
    draft.bbox[0] = 10
    expect(row.bbox).toEqual([0, 0, 20, 30])
    const payload = samplePayload({ ...row, character_id: '  synthetic-character  ', source_ref: ' 来源 ' })
    expect(payload).toMatchObject({
      character_id: 'synthetic-character',
      source_ref: '来源',
      quality_score: null,
    })
    for (const field of [
      'id',
      'image_uri',
      'recognition_id',
      'user_id',
      'reviewed_by',
      'reviewed_at',
      'consent_version',
    ]) {
      expect(payload).not.toHaveProperty(field)
    }
  })
  it('does not invent a quality score or bounding box', () => {
    const draft = sampleDraft(sample)
    expect(draft.bbox).toBeNull()
    expect(draft.quality_score).toBeNull()
    expect(sampleValidation(draft)).toBe('')
    expect(samplePayload({ ...draft, character_id: '  ', quality_score: 0 }).character_id).toBeNull()
    expect(samplePayload({ ...draft, quality_score: 0 }).quality_score).toBe(0)
  })
  it('requires explicit re-approval without changing the original row on cancellation', () => {
    const row = { ...sample, review_status: 'approved' }
    const draft = sampleEditDraft(row)
    expect(draft.review_status).toBe('pending')
    expect(row.review_status).toBe('approved')
    draft.review_status = 'approved'
    expect(samplePayload(draft).review_status).toBe('approved')
  })
  it.each([
    [{ review_status: 'approved', character_id: ' ' }, '关联词条'],
    [{ review_status: 'approved', source_ref: ' ' }, '资料来源'],
    [{ review_status: 'rejected', review_note: ' ' }, '驳回原因'],
    [{ quality_score: -1 }, '质量分'],
    [{ quality_score: 1.1 }, '质量分'],
    [{ quality_score: NaN }, '质量分'],
    [{ quality_score: Infinity }, '质量分'],
    [{ bbox: [-1, 0, 1, 1] }, '标注框'],
    [{ bbox: [0, 0, 0, 1] }, '标注框'],
    [{ bbox: [0, 0, 1.5, 1] }, '标注框'],
    [{ bbox: [0, null, 1, 1] }, '标注框'],
    [{ bbox: [0, 1] }, '标注框'],
    [{ bbox: {} }, '标注框'],
    [{ bbox: [9, 0, 2, 1] }, '图片边界'],
    [{ bbox: [0, 9, 1, 2] }, '图片边界'],
    [{ scene: ' ' }, '采集场景'],
    [{ dataset_version: 'v'.repeat(101) }, '100'],
    [{ review_status: 'unknown' }, '审核状态'],
    [{ sample_type: 'unknown' }, '样本类型'],
  ])('validates review and optional metadata: %j', (changes, message) => {
    expect(sampleValidation({ ...sampleDraft(sample), ...changes }, { width: 10, height: 10 })).toContain(
      message,
    )
  })
  it('allows bbox at the exact image boundary and explicit unreviewed data', () => {
    expect(
      sampleValidation(
        { ...sampleDraft(sample), bbox: [0, 0, 10, 10], character_id: null, source_ref: '' },
        { width: 10, height: 10 },
      ),
    ).toBe('')
  })
})

describe('sample API contract and authenticated media', () => {
  it('uploads a file using the dedicated multipart endpoint, not public media', async () => {
    json(sample)
    const file = new File(['synthetic bytes'], 'synthetic.png', { type: 'image/png' })
    expect(await uploadSample(file)).toEqual(sample)
    const [path, options] = fetchMock.mock.calls[0]!
    expect(path).toBe('/api/v1/admin/samples/upload')
    expect(options!.method).toBe('POST')
    expect((options!.body as FormData).get('file')).toBeInstanceOf(File)
    expect((options!.headers as Headers).get('Authorization')).toBe('Bearer synthetic-token')
    expect((options!.headers as Headers).has('Content-Type')).toBe(false)
  })
  it('sends every list filter and zero-based pagination', async () => {
    json({ items: [sample], total: 21 })
    await listSamples(
      {
        q: '  茶 & 酒  ',
        review_status: 'pending',
        character_id: '字',
        recognition_id: 'req/1',
        dataset_version: 'v2',
      },
      2,
      20,
    )
    const url = new URL(String(fetchMock.mock.calls[0]![0]), 'http://local.test')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      q: '茶 & 酒',
      review_status: 'pending',
      character_id: '字',
      recognition_id: 'req/1',
      dataset_version: 'v2',
      offset: '20',
      limit: '20',
    })
  })
  it('patches only editable metadata and deletes by encoded sample ID', async () => {
    json(sample)
    await updateSample('sample/a', sample)
    expect(fetchMock.mock.calls[0]![0]).toBe('/api/v1/admin/samples/sample%2Fa')
    expect(fetchMock.mock.calls[0]![1]!.method).toBe('PATCH')
    expect(requestBody()).toEqual(samplePayload(sample))
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    await deleteSample('sample/a')
    expect(fetchMock.mock.calls[1]![1]!.method).toBe('DELETE')
  })
  it('loads private PNG data with authorization', async () => {
    fetchMock.mockResolvedValueOnce(new Response(new Blob(['synthetic image'], { type: 'image/png' })))
    const result = await apiBlob('/admin/samples/synthetic-sample/image')
    expect(result.blob.type).toBe('image/png')
    expect((fetchMock.mock.calls[0]![1]!.headers as Headers).get('Authorization')).toBe(
      'Bearer synthetic-token',
    )
  })
  it('exports a ZIP, defaults to approved, and preserves all other filters', async () => {
    fetchMock.mockResolvedValueOnce(new Response(new Blob(['synthetic zip'], { type: 'application/zip' })))
    const result = await exportSamples({
      ...filters,
      q: ' 源 ',
      character_id: ' 字 ',
      recognition_id: ' req ',
      dataset_version: ' v1 ',
      review_status: 'pending',
    })
    expect(fetchMock.mock.calls[0]![0]).toBe('/api/v1/admin/samples/export')
    expect(result.blob.type).toBe('application/zip')
    expect(requestBody()).toEqual({
      q: '源',
      character_id: '字',
      recognition_id: 'req',
      dataset_version: 'v1',
      review_status: 'approved',
      limit: 1000,
    })
  })
  it('requires an explicit supported review status for unreviewed exports', () => {
    expect(sampleExportPayload(filters, 'pending', 10).review_status).toBe('pending')
    expect(sampleExportPayload(filters, 'rejected', 10).review_status).toBe('rejected')
    expect(() => sampleExportPayload(filters, '', 10)).toThrow('审核状态')
    for (const limit of [0, 1.5, NaN, 10001])
      expect(() => sampleExportPayload(filters, 'approved', limit)).toThrow('导出上限')
  })
  it('keeps unavailable images, missing approval data and forbidden uploads visible', async () => {
    json({ code: 'SAMPLE_IMAGE_UNAVAILABLE' }, 409)
    await expect(exportSamples(filters)).rejects.toThrow('样本图片不可用')
    json({ code: 'SAMPLE_REVIEW_INCOMPLETE' }, 422)
    await expect(updateSample(sample.id, { ...sample, review_status: 'approved' })).rejects.toThrow(
      '已审核或已发布',
    )
    json({ code: 'FORBIDDEN' }, 403)
    await expect(uploadSample(new File(['fixture'], 'test.png'))).rejects.toThrow('没有此操作权限')
  })
})

describe('recognition / feedback cross-links', () => {
  it('links samples to existing records search rather than inventing detail APIs', () => {
    expect(sampleRecordLink('recognitions', 'req/1')).toEqual({
      path: '/admin/recognitions',
      query: { q: 'req/1' },
    })
    expect(sampleRecordLink('feedback', 'req/1')).toEqual({ path: '/admin/feedback', query: { q: 'req/1' } })
  })
  it('uses request_id for recognition rows and recognition_id for feedback rows', () => {
    expect(recordSampleLink('recognitions', { request_id: 'req' })).toEqual({
      path: '/admin/feedback',
      query: { q: 'req' },
    })
    expect(recordSampleLink('feedback', { id: 'feedback-not-request', recognition_id: 'req' })).toEqual({
      path: '/admin/feedback',
      query: { q: 'req' },
    })
    expect(recordSampleLink('feedback', {})).toBeNull()
    expect(recordSampleLink('audit', { request_id: 'req' })).toBeNull()
  })
})

describe('read-only full entity revisions', () => {
  it('reads items and total from the agreed endpoint without updating anything', async () => {
    const result = {
      items: [
        {
          id: 'revision',
          snapshot: {
            culture_detail: '完整旧文本',
            variants: [{ image_url: '/api/v1/media/old.png', source_ref: '旧来源' }],
            status: 'published',
          },
        },
      ],
      total: 1,
    }
    json(result)
    expect(await loadRevisions('characters', '字/a')).toEqual(result)
    expect(fetchMock.mock.calls[0]![0]).toBe('/api/v1/admin/characters/%E5%AD%97%2Fa/revisions')
    expect(fetchMock.mock.calls[0]![1]!.method).toBeUndefined()
  })
  it('includes every snapshot key, even fields outside the current CRUD form', () => {
    const snapshot = {
      culture_detail: '旧文本'.repeat(500),
      source_ref: '旧来源',
      image_url: 'old.png',
      variants: [],
      status: 'reviewed',
      reviewed_by: 'reviewer',
      reviewed_at: '2026-09-23T00:00:00Z',
      retired_field: { original: true },
    }
    const fields = snapshotFields(snapshot, 'characters')
    expect(fields.map((field) => field.key)).toEqual(Object.keys(snapshot))
    expect(fields.find((field) => field.key === 'image_url')?.type).toBe('image')
    expect(fields.find((field) => field.key === 'variants')?.type).toBe('variants')
    expect(snapshotText(snapshot.culture_detail)).toBe(snapshot.culture_detail)
    expect(snapshotText(snapshot.retired_field)).toContain('original')
    expect(snapshotText(0)).toBe('0')
  })
})
