import type { Row } from './api'

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
  'character_id', 'sample_type', 'scene', 'bbox', 'quality_score', 'label_source',
  'review_status', 'dataset_split', 'dataset_version', 'source_ref', 'review_note',
] as const

export function sampleDraft(row: Row): Row {
  return Object.fromEntries(sampleFields.map((key) => [key,
    key === 'bbox' ? (row.bbox ? [...row.bbox] : null) : row[key] ?? (
      ['character_id', 'quality_score'].includes(key) ? null : ''
    ),
  ]))
}

export function samplePayload(form: Row): Row {
  return Object.fromEntries(sampleFields.map((key) => [key,
    key === 'character_id' ? form[key] || null :
      key === 'quality_score' ? form[key] ?? null :
        typeof form[key] === 'string' ? form[key].trim() : form[key],
  ]))
}

export function sampleValidation(form: Row, dimensions?: { width: number; height: number }): string {
  if (form.review_status === 'approved' && (!form.character_id || !form.source_ref?.trim()))
    return '审核通过前请填写关联词条和资料来源'
  if (form.review_status === 'rejected' && !form.review_note?.trim())
    return '请填写驳回原因'
  if (form.quality_score != null && (!Number.isFinite(form.quality_score) || form.quality_score < 0 || form.quality_score > 1))
    return '质量分需要在0到1之间'
  if (form.bbox != null) {
    const values = form.bbox as number[]
    if (values.length !== 4 || values.some((value) => !Number.isInteger(value)) ||
      values[0]! < 0 || values[1]! < 0 || values[2]! <= 0 || values[3]! <= 0)
      return '标注框需要填写非负整数坐标及大于0的宽高'
    if (dimensions && (values[0]! + values[2]! > dimensions.width || values[1]! + values[3]! > dimensions.height))
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
  return {
    q: filters.q.trim(),
    character_id: filters.character_id || null,
    recognition_id: filters.recognition_id.trim() || null,
    dataset_version: filters.dataset_version.trim() || null,
    review_status: status || null,
    limit,
  }
}
