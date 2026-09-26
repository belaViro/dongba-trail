import { api, type Row } from './api'
import { resources } from './resources'

// DATA-04 / OPS-01: use the saved entity, never merge it with current CRUD data.
export interface Revision {
  id: string
  entity_id: string
  resource: string
  version: number
  action: string
  actor_id: string | null
  created_at: string
  snapshot: Row
}
export interface RevisionCollection {
  items: Revision[]
  total: number
}
export function loadRevisions(resource: string, id: string) {
  return api<RevisionCollection>(`/admin/${encodeURIComponent(resource)}/${encodeURIComponent(id)}/revisions`)
}
export const revisionActions: Record<string, string> = {
  baseline: '迁移基线',
  create: '新建',
  update: '修改',
  review: '审核',
  publish: '发布',
  disable: '停用',
  delete: '停用',
}
const metadataLabels: Record<string, string> = {
  id: '词条编号',
  character_id: '东巴字编号',
  status: '审核 / 发布状态',
  reviewed_by: '审核人',
  reviewed_at: '审核时间',
  review_note: '审核意见',
  created_at: '创建时间',
  updated_at: '更新时间',
}
export function snapshotFields(snapshot: Row, resource: string) {
  const configured = resources[resource]?.fields || []
  return Object.keys(snapshot).map((key) => {
    const field = configured.find((item) => item.key === key)
    return { key, label: metadataLabels[key] || field?.label || key, type: field?.type }
  })
}
export function snapshotText(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  return typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)
}
