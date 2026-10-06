import { api, apiBlob, query, save, type Collection, type Row } from './api'

// DATA-03 / FEEDBACK-01: labels remain subject to an explicit human review.
export const sampleScenes = [
  { value: 'paper', label: '纸质资料' },
  { value: 'shop_sign', label: '店铺招牌' },
  { value: 'wall', label: '墙面' },
  { value: 'wood', label: '木刻' },
  { value: 'product', label: '商品' },
  { value: 'screen', label: '屏幕' },
  { value: 'other', label: '其他' },
]

export const sampleTypes = [
  { value: 'dictionary', label: '字典原图' },
  { value: 'augmented', label: '增强图片' },
  { value: 'real_photo', label: '实拍图片' },
]
export const labelSources = [
  { value: 'source_material', label: '原始资料' },
  { value: 'manual', label: '人工标注' },
  { value: 'user_correction', label: '用户纠错' },
]
export const datasetSplits = [
  { value: 'unassigned', label: '未分配' },
  { value: 'train', label: '训练集' },
  { value: 'val', label: '验证集' },
  { value: 'test', label: '测试集' },
]
export const reviewStatuses = [
  { value: 'pending', label: '待审核' },
  { value: 'approved', label: '已通过' },
  { value: 'rejected', label: '已驳回' },
]
export const sampleFields = [
  'character_id',
  'sample_type',
  'scene',
  'bbox',
  'quality_score',
  'label_source',
  'review_status',
  'dataset_split',
  'dataset_version',
  'source_ref',
  'review_note',
] as const

export function sampleDraft(row: Row): Row {
  return Object.fromEntries(
    sampleFields.map((key) => [
      key,
      key === 'bbox'
        ? row.bbox
          ? [...row.bbox]
          : null
        : (row[key] ?? (['character_id', 'quality_score'].includes(key) ? null : '')),
    ]),
  )
}

export function sampleEditDraft(row: Row): Row {
  const draft = sampleDraft(row)
  // An ordinary save must not silently re-approve an edited, approved label.
  if (draft.review_status === 'approved') draft.review_status = 'pending'
  return draft
}

export function samplePayload(form: Row): Row {
  return Object.fromEntries(
    sampleFields.map((key) => [
      key,
      key === 'character_id'
        ? form[key]?.trim() || null
        : key === 'quality_score'
          ? (form[key] ?? null)
          : typeof form[key] === 'string'
            ? form[key].trim()
            : form[key],
    ]),
  )
}

export function sampleValidation(form: Row, dimensions?: { width: number; height: number }): string {
  for (const [key, options] of [
    ['sample_type', sampleTypes],
    ['label_source', labelSources],
    ['review_status', reviewStatuses],
    ['dataset_split', datasetSplits],
  ] as const) {
    if (!options.some((option) => option.value === form[key]))
      return '请选择有效的样本类型、标注来源、审核状态和数据集划分'
  }
  if (!form.scene?.trim()) return '请填写采集场景'
  for (const [key, limit] of [
    ['character_id', 64],
    ['scene', 100],
    ['dataset_version', 100],
    ['source_ref', 1000],
    ['review_note', 2000],
  ] as const) {
    if ((form[key]?.trim().length || 0) > limit) return `${key}不能超过${limit}个字符`
  }
  if (form.review_status === 'approved' && (!form.character_id?.trim() || !form.source_ref?.trim()))
    return '审核通过前请填写关联词条和资料来源'
  if (form.review_status === 'rejected' && !form.review_note?.trim()) return '请填写驳回原因'
  if (
    form.quality_score != null &&
    (!Number.isFinite(form.quality_score) || form.quality_score < 0 || form.quality_score > 1)
  )
    return '质量分需要在0到1之间'
  if (form.bbox != null) {
    const values = form.bbox as number[]
    if (
      !Array.isArray(values) ||
      values.length !== 4 ||
      values.some((value) => !Number.isInteger(value)) ||
      values[0]! < 0 ||
      values[1]! < 0 ||
      values[2]! <= 0 ||
      values[3]! <= 0
    )
      return '标注框需要填写非负整数坐标及大于0的宽高'
    if (
      dimensions &&
      (values[0]! + values[2]! > dimensions.width || values[1]! + values[3]! > dimensions.height)
    )
      return '标注框不能超出图片边界'
  }
  return ''
}

export interface SampleFilters {
  q: string
  review_status: string
  character_id: string
  recognition_id: string
  dataset_version: string
}

export function sampleExportPayload(filters: SampleFilters, status: string, limit: number): Row {
  if (!reviewStatuses.some((option) => option.value === status)) throw new Error('请选择明确的导出审核状态')
  if (!Number.isInteger(limit) || limit < 1 || limit > 10000) throw new Error('导出上限需要为1到10000的整数')
  return {
    q: filters.q.trim(),
    character_id: filters.character_id.trim() || null,
    recognition_id: filters.recognition_id.trim() || null,
    dataset_version: filters.dataset_version.trim() || null,
    review_status: status,
    limit,
  }
}

export function listSamples(filters: SampleFilters, page: number, limit: number) {
  return api<Collection>(
    `/admin/samples?${query({
      ...Object.fromEntries(Object.entries(filters).map(([key, value]) => [key, value.trim()])),
      offset: (page - 1) * limit,
      limit,
    })}`,
  )
}

export function uploadSample(file: File) {
  const body = new FormData()
  body.append('file', file)
  return api<Row>('/admin/samples/upload', { method: 'POST', body })
}

export function updateSample(id: string, form: Row) {
  return save<Row>(`/admin/samples/${encodeURIComponent(id)}`, samplePayload(form), 'PATCH')
}

export function deleteSample(id: string) {
  return api(`/admin/samples/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export function exportSamples(filters: SampleFilters, status = 'approved', limit = 1000) {
  return apiBlob('/admin/samples/export', {
    method: 'POST',
    body: JSON.stringify(sampleExportPayload(filters, status, limit)),
  })
}

export function sampleRecordLink(resource: 'recognitions' | 'feedback', recognitionId: string) {
  // The records API supports q, not a recognition_id filter.
  return { path: `/admin/${resource}`, query: { q: recognitionId } }
}

export function recordSampleLink(resource: string, row: Row) {
  const recognitionId =
    resource === 'recognitions' ? row.request_id : resource === 'feedback' ? row.recognition_id : null
  return recognitionId ? { path: '/admin/feedback', query: { q: String(recognitionId) } } : null
}
