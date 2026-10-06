import { api, query, save } from './api'

export type RagCaseStatus = string

export interface RagCase {
  id: string
  text?: string
  question?: string
  answer?: string
  character_id?: string | null
  scene?: string | null
  image_uri?: string | null
  sample_id?: string | null
  status?: RagCaseStatus
  review_note?: string | null
  reviewed_by?: string | null
  reviewed_at?: string | null
  created_at?: string | null
  updated_at?: string | null
  [key: string]: unknown
}

export interface RagCaseFilters {
  q: string
  status: string
  character_id: string
  scene: string
}

export interface RagCaseCollection {
  items: RagCase[]
  total: number
}

export interface RagStats {
  total?: number
  approved?: number
  pending?: number
  rejected?: number
  deprecated?: number
  indexed?: number
  [key: string]: unknown
}

export interface RagSearchResult {
  items: RagCase[]
  total?: number
  [key: string]: unknown
}

export type RagCasePayload = Record<string, unknown>

export function listRagCases(filters: RagCaseFilters, page: number, limit: number) {
  return api<RagCaseCollection>(
    `/admin/rag/cases?${query({
      q: filters.q,
      status: filters.status,
      character_id: filters.character_id,
      scene: filters.scene,
      offset: (page - 1) * limit,
      limit,
    })}`,
  )
}

export function getRagStats() {
  return api<RagStats>('/admin/rag/stats')
}

export function createRagCase(payload: RagCasePayload) {
  return save<RagCase>('/admin/rag/cases', payload)
}

export function updateRagCase(id: string, payload: RagCasePayload) {
  return save<RagCase>(`/admin/rag/cases/${encodeURIComponent(id)}`, payload, 'PATCH')
}

export function reviewRagCase(id: string, status: 'approved' | 'rejected', review_note: string) {
  return save<RagCase>(`/admin/rag/cases/${encodeURIComponent(id)}/review`, { status, review_note })
}

export function deprecateRagCase(id: string, reason: string) {
  return save<RagCase>(`/admin/rag/cases/${encodeURIComponent(id)}/deprecate`, { reason })
}

export function reindexRagCase(id: string) {
  return api<RagCase>(`/admin/rag/cases/${encodeURIComponent(id)}/reindex`, { method: 'POST' })
}

export function rebuildRagIndex() {
  return api<Record<string, unknown>>('/admin/rag/rebuild', { method: 'POST' })
}

export function searchRagCases(text: string, limit: number) {
  return save<RagSearchResult>('/admin/rag/search', { text, limit })
}
