<script setup lang="ts">
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, Refresh, Search } from '@element-plus/icons-vue'
import { api, dateText, errorText, query, save, type Collection, type Row } from '../api'
import SampleImage from '../components/SampleImage.vue'

// FEEDBACK-01 / OPS-03 / D-054: shared drawer interaction; one review decision.
const route = useRoute()
const filters = reactive({ q: '', status: '' })
const page = ref(1)
const rows = ref<Row[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const visible = ref(false)
const detail = ref<Row | null>(null)
const detailLoading = ref(false)
const detailError = ref('')
const detailId = ref('')
const busy = ref(false)
const prompting = ref(false)
const characters = ref<Row[]>([])
const form = reactive({ character_id: '', review_note: '', reason: '' })
const labels: Record<string, string> = { pending: '待审核', approved: '已采纳', rejected: '已驳回' }
let listGeneration = 0
let detailGeneration = 0
function ragLabel(row: Row) {
  if (row.status !== 'approved') return row.status === 'rejected' ? '未入库' : '待核验'
  if (row.rag_status === 'unavailable') return '识别参考暂不可用'
  return (
    ({ indexed: '已生效', approved: '已生效', deprecated: '已停用' } as Record<string, string>)[
      row.rag_status
    ] || '待生效'
  )
}
function ragTone(row: Row) {
  if (row.status !== 'approved' || row.rag_status === 'deprecated') return 'info'
  return ['indexed', 'approved'].includes(row.rag_status) ? 'success' : 'warning'
}
const selectedWord = computed(
  () =>
    characters.value.find((row) => row.id === detail.value?.character_id)?.cn_name ||
    detail.value?.rag_case?.character_name ||
    '词条暂不可用',
)
const needsSync = computed(
  () =>
    detail.value?.status === 'approved' &&
    !['indexed', 'approved', 'deprecated'].includes(detail.value.rag_status),
)
const canMaintain = computed(
  () =>
    detail.value?.status === 'approved' &&
    detail.value?.rag_case &&
    detail.value.rag_status !== 'unavailable',
)

async function load() {
  const current = ++listGeneration
  loading.value = true
  error.value = ''
  try {
    const data = await api<Collection>(
      `/admin/feedback?${query({ ...filters, offset: (page.value - 1) * 20, limit: 20 })}`,
    )
    if (current !== listGeneration) return
    rows.value = data.items
    total.value = data.total
  } catch (e) {
    if (current === listGeneration) error.value = `列表刷新失败：${errorText(e)}`
  } finally {
    if (current === listGeneration) loading.value = false
  }
}
function search() {
  page.value = 1
  void load()
}
async function open(row: Row) {
  if (busy.value || prompting.value) return
  visible.value = true
  detailId.value = row.id
  detail.value = null
  characters.value = []
  Object.assign(form, { character_id: '', review_note: '', reason: '' })
  await loadDetail(row.id, true)
}
function closeReview(done: () => void) {
  if (busy.value || prompting.value) return
  detailGeneration++
  detailLoading.value = false
  done()
}
async function loadDetail(id: string, resetForm = false) {
  const current = ++detailGeneration
  detailLoading.value = true
  detailError.value = ''
  try {
    const data = await api<Row>(`/admin/feedback/${encodeURIComponent(id)}`)
    if (current !== detailGeneration) return
    detail.value = data
    if (resetForm)
      Object.assign(form, {
        character_id: data.character_id || '',
        review_note: data.review_note || '',
        reason: '',
      })
    if (!resetForm) return
    const choices: Row[] = []
    let offset = 0
    while (true) {
      const collection = await api<Collection>(
        `/admin/characters?${query({ status: 'published', offset, limit: 100 })}`,
      )
      if (current !== detailGeneration) return
      choices.push(...collection.items)
      offset += collection.items.length
      if (!collection.items.length || offset >= collection.total) break
    }
    characters.value = choices
  } catch (e) {
    if (current === detailGeneration) detailError.value = `详情刷新失败：${errorText(e)}`
  } finally {
    if (current === detailGeneration) detailLoading.value = false
  }
}
async function refresh() {
  if (busy.value || prompting.value) return
  await Promise.all([
    load(),
    visible.value && detailId.value ? loadDetail(detailId.value, !detail.value) : Promise.resolve(),
  ])
}
function applyResult(id: string, result: Row) {
  // Ignore pre-mutation reads and retain confirmed state if a subsequent refresh fails.
  listGeneration++
  detailGeneration++
  rows.value = rows.value.map((row) => (row.id === id ? { ...row, ...result } : row))
  if (detail.value?.id === id) detail.value = { ...detail.value, ...result }
}
async function review(status: 'approved' | 'rejected') {
  if (!detail.value || busy.value || detailLoading.value || prompting.value) return
  detailError.value = ''
  if (status === 'approved' && !characters.value.some((row) => row.id === form.character_id)) {
    detailError.value = '请选择核验后的已发布词条'
    return
  }
  busy.value = true
  const id = detail.value.id
  try {
    const result = await save<Row>(
      `/admin/feedback/${encodeURIComponent(id)}`,
      { status, character_id: form.character_id || null, review_note: form.review_note.trim() },
      'PATCH',
    )
    applyResult(id, result)
    ElMessage.success(status === 'approved' ? '已采纳并生效' : '已驳回')
    await Promise.all([loadDetail(id, true), load()])
  } catch (e) {
    detailError.value = `${errorText(e)}${status === 'approved' ? '；尚未确认采纳成功，请刷新核对或重试。' : ''}`
  } finally {
    busy.value = false
  }
}
async function maintain(action: 'deprecate' | 'reindex') {
  if (!canMaintain.value || busy.value || detailLoading.value) return
  if (action === 'deprecate' && !form.reason.trim()) {
    detailError.value = '请填写停用原因'
    return
  }
  busy.value = true
  detailError.value = ''
  const id = detail.value!.id
  try {
    const result = await save<Row>(
      `/admin/rag/cases/${encodeURIComponent(detail.value!.rag_case.id)}/${action}`,
      action === 'deprecate' ? { reason: form.reason.trim() } : {},
    )
    applyResult(id, {
      rag_case: result,
      rag_case_id: result.id,
      rag_status: result.status,
      rag_updated_at: result.updated_at,
    })
    form.reason = ''
    ElMessage.success(action === 'deprecate' ? '已停用，后续识别不再使用此纠错' : '识别参考已更新')
    await Promise.all([loadDetail(id), load()])
  } catch (e) {
    detailError.value = errorText(e)
  } finally {
    busy.value = false
  }
}
async function deleteEvidence() {
  if (!detail.value?.sample || busy.value) return
  try {
    await ElMessageBox.confirm('永久删除纠错附图？保留文字反馈和审核记录。', '删除附图', { type: 'warning' })
  } catch {
    return
  }
  busy.value = true
  const id = detail.value.id
  try {
    await api(`/admin/samples/${encodeURIComponent(detail.value.sample.id)}`, { method: 'DELETE' })
    applyResult(id, { sample: null })
    await Promise.all([loadDetail(id), load()])
    ElMessage.success('附图已删除')
  } catch (e) {
    detailError.value = errorText(e)
  } finally {
    busy.value = false
  }
}
async function moreAction(command: string) {
  if (busy.value || detailLoading.value || prompting.value) return
  if (command === 'delete-image') {
    prompting.value = true
    try {
      await deleteEvidence()
    } finally {
      prompting.value = false
    }
    return
  }
  if (command === 'reindex') return maintain('reindex')
  if (command !== 'deprecate' || !canMaintain.value) return
  prompting.value = true
  try {
    const result = await ElMessageBox.prompt('停用后，此纠错不再用于识别。', '停用纠错', {
      inputType: 'textarea',
      inputPlaceholder: '请输入停用原因',
      inputValidator: (value: string) => !!value?.trim() || '请填写停用原因',
      confirmButtonText: '确认停用',
      cancelButtonText: '取消',
      closeOnClickModal: false,
    })
    form.reason = result.value.trim()
  } catch {
    return
  } finally {
    prompting.value = false
  }
  await maintain('deprecate')
}
watch(
  () => route.query.q,
  () => {
    filters.q = typeof route.query.q === 'string' ? route.query.q : ''
    search()
  },
  { immediate: true },
)
onUnmounted(() => {
  listGeneration++
  detailGeneration++
})
</script>

<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">运营管理 / 用户反馈</span>
      <h1>纠错审核</h1>
      <p class="page-description">查看用户反馈，核验并处理识别纠错。</p>
    </div>
    <div class="heading-actions">
      <el-button :icon="Refresh" :loading="loading" :disabled="busy || prompting" @click="refresh">
        刷新
      </el-button>
    </div>
  </div>
  <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="page-alert" />
  <section class="settings-section feedback-list">
    <div class="filters">
      <el-input
        v-model="filters.q"
        aria-label="搜索纠错"
        placeholder="搜索反馈内容、识别请求编号"
        clearable
        @keyup.enter="search"
      />
      <el-select
        v-model="filters.status"
        aria-label="审核结果筛选"
        placeholder="全部审核结果"
        clearable
        @change="search"
      >
        <el-option v-for="(label, value) in labels" :key="value" :value="value" :label="label" />
      </el-select>
      <el-button :icon="Search" type="primary" @click="search">查询</el-button>
    </div>
    <div class="list-caption">
      <strong>纠错记录</strong>
      <span>生效状态表示该纠错当前是否用于后续识别。</span>
    </div>
    <el-table v-loading="loading" :data="rows" empty-text="暂无纠错反馈" @row-dblclick="open">
      <el-table-column label="用户反馈" min-width="280">
        <template #default="{ row }">
          <div class="feedback-summary">{{ row.comment || '用户选择了纠正词条，未补充说明' }}</div>
          <div class="record-reference" :title="row.recognition_id">识别请求 · {{ row.recognition_id }}</div>
        </template>
      </el-table-column>
      <el-table-column label="审核结果" width="105">
        <template #default="{ row }">
          <el-tag
            :type="row.status === 'approved' ? 'success' : row.status === 'rejected' ? 'danger' : 'warning'"
            effect="plain"
          >
            {{ labels[row.status] || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="生效状态" min-width="180">
        <template #default="{ row }">
          <el-tag :type="ragTone(row)">{{ ragLabel(row) }}</el-tag>
          <div v-if="row.rag_updated_at" class="state-time">更新于 {{ dateText(row.rag_updated_at) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="提交时间" width="170">
        <template #default="{ row }">{{ dateText(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :disabled="busy" @click="open(row)">
            {{ row.status === 'pending' ? '核验处理' : '查看详情' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      v-model:current-page="page"
      :page-size="20"
      :total="total"
      layout="total, prev, pager, next"
      @current-change="load"
    />
  </section>
  <el-drawer
    v-model="visible"
    title="纠错详情与核验"
    class="feedback-drawer"
    size="min(1120px, 100vw)"
    destroy-on-close
    :close-on-click-modal="false"
    :close-on-press-escape="!busy && !prompting"
    :before-close="closeReview"
  >
    <div class="review-toolbar">
      <div v-if="detail" class="review-overview">
        <el-tag
          :type="
            detail.status === 'approved'
              ? ragTone(detail)
              : detail.status === 'rejected'
                ? 'danger'
                : 'warning'
          "
          effect="plain"
        >
          {{ labels[detail.status] || detail.status }}
          <template v-if="detail.status === 'approved'">· {{ ragLabel(detail) }}</template>
        </el-tag>
      </div>
      <div class="review-tools">
        <el-button :icon="Refresh" :loading="detailLoading" :disabled="busy || prompting" @click="refresh">
          刷新状态
        </el-button>
        <el-dropdown
          v-if="detail && (canMaintain || detail.sample)"
          trigger="click"
          :disabled="busy || detailLoading || prompting"
          @command="moreAction"
        >
          <el-button :disabled="busy || detailLoading || prompting">
            更多操作
            <el-icon class="more-icon"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-if="canMaintain" command="reindex">
                {{ detail.rag_status === 'deprecated' ? '重新启用' : '更新识别参考' }}
              </el-dropdown-item>
              <el-dropdown-item
                v-if="canMaintain && detail.rag_status !== 'deprecated'"
                command="deprecate"
                class="danger-action"
              >
                停用此纠错
              </el-dropdown-item>
              <el-dropdown-item
                v-if="detail.sample"
                command="delete-image"
                :divided="!!canMaintain"
                class="danger-action"
              >
                删除附图
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>
    <div v-loading="detailLoading" class="review-content">
      <el-alert
        v-if="detailError"
        :title="detailError"
        type="error"
        :closable="false"
        show-icon
        class="page-alert"
      />
      <template v-if="detail">
        <div v-if="needsSync" class="sync-notice">
          <span>
            {{
              detail.rag_status === 'unavailable'
                ? '识别参考暂不可用，请稍后重试。'
                : '此纠错尚未生效，请重试。'
            }}
          </span>
          <el-button
            type="primary"
            link
            :loading="busy"
            :disabled="detailLoading || prompting"
            @click="review('approved')"
          >
            重试生效
          </el-button>
        </div>
        <div class="review-grid">
          <section class="evidence-column">
            <h2>纠错附图</h2>
            <SampleImage v-if="detail.sample" :sample-id="detail.sample.id" :bbox="detail.sample.bbox" />
            <el-empty v-else description="未保存附图，原图无法恢复" :image-size="64" />
          </section>
          <div class="decision-column">
            <section class="review-section">
              <h2>用户反馈</h2>
              <p class="user-feedback">{{ detail.comment || '用户未补充文字说明' }}</p>
              <dl class="evidence-fields">
                <div>
                  <dt>原识别结果</dt>
                  <dd>{{ detail.recognition?.observed_text || '未返回识别文本' }}</dd>
                  <dd v-if="detail.recognition?.candidates?.length" class="candidate-text">
                    候选：{{
                      detail.recognition.candidates
                        .map((item: Row) => item.cn_name || '未命名词条')
                        .join('、')
                    }}
                  </dd>
                </div>
              </dl>
            </section>
            <section
              v-if="
                detail.status === 'pending' ||
                detail.status === 'approved' ||
                detail.character_id ||
                detail.review_note
              "
              class="review-section decision-section"
            >
              <el-form
                v-if="detail.status === 'pending'"
                label-position="top"
                class="review-form"
                @submit.prevent
              >
                <el-form-item label="正确词条">
                  <el-select
                    v-model="form.character_id"
                    filterable
                    placeholder="采纳前请选择正确词条"
                    :disabled="busy || detailLoading || prompting"
                    class="full-width"
                  >
                    <el-option
                      v-for="word in characters"
                      :key="word.id"
                      :value="word.id"
                      :label="word.cn_name"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="备注（选填）">
                  <el-input
                    v-model="form.review_note"
                    type="textarea"
                    :rows="3"
                    :maxlength="2000"
                    show-word-limit
                    :disabled="busy || prompting"
                    placeholder="填写核验说明或驳回原因"
                  />
                </el-form-item>
              </el-form>
              <dl v-else class="evidence-fields">
                <div v-if="detail.status === 'approved' || detail.character_id">
                  <dt>核验词条</dt>
                  <dd>{{ selectedWord }}</dd>
                </div>
                <div v-if="detail.review_note">
                  <dt>备注</dt>
                  <dd>{{ detail.review_note }}</dd>
                </div>
              </dl>
            </section>
            <details class="request-meta">
              <summary>更多信息</summary>
              <dl class="evidence-fields">
                <div>
                  <dt>识别请求</dt>
                  <dd>{{ detail.recognition_id }}</dd>
                </div>
                <div>
                  <dt>提交时间</dt>
                  <dd>{{ dateText(detail.created_at) }}</dd>
                </div>
                <div v-if="detail.rag_updated_at">
                  <dt>状态更新时间</dt>
                  <dd class="state-time">{{ dateText(detail.rag_updated_at) }}</dd>
                </div>
                <div v-if="detail.rag_case?.deprecated_reason">
                  <dt>停用原因</dt>
                  <dd>{{ detail.rag_case.deprecated_reason }}</dd>
                </div>
              </dl>
            </details>
          </div>
        </div>
      </template>
    </div>
    <template v-if="detail?.status === 'pending'" #footer>
      <div class="review-footer">
        <el-button
          type="danger"
          plain
          :disabled="busy || detailLoading || prompting"
          @click="review('rejected')"
        >
          驳回
        </el-button>
        <el-button
          type="primary"
          :loading="busy"
          :disabled="detailLoading || prompting"
          @click="review('approved')"
        >
          采纳并生效
        </el-button>
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.feedback-list {
  width: 100%;
  max-width: none;
  min-width: 0;
}
.page-description {
  color: var(--ink-soft);
  font-size: 14px;
  margin-top: 8px;
  line-height: 1.6;
}
.filters {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}
.filters .el-input {
  max-width: 380px;
}
.filters .el-select {
  width: 170px;
}
.list-caption {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}
.list-caption span,
.record-reference,
.state-time {
  font-size: 12px;
  color: var(--ink-soft);
}
.feedback-summary {
  font-weight: 500;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.record-reference {
  margin-top: 5px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.state-time {
  margin-top: 6px;
}
.review-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-bottom: 20px;
}
.review-tools {
  display: flex;
  gap: 10px;
  margin-left: auto;
}
.more-icon {
  margin-left: 6px;
}
.danger-action {
  color: var(--el-color-danger);
}
.review-content {
  min-height: 180px;
}
.review-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 28px;
  align-items: start;
}
.evidence-column,
.decision-column {
  min-width: 0;
}
.evidence-column h2,
.review-section h2 {
  font-size: 15px;
  margin: 0 0 16px;
}
.decision-column {
  display: grid;
  gap: 22px;
}
.evidence-fields {
  margin: 0;
  display: grid;
  gap: 14px;
}
.evidence-fields dt {
  color: var(--ink-soft);
  font-size: 12px;
  margin-bottom: 6px;
}
.evidence-fields dd {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.evidence-fields .candidate-text {
  margin-top: 6px;
  color: var(--ink-soft);
  font-size: 13px;
}
.user-feedback {
  margin: 0 0 18px;
  background: #f5f8fc;
  padding: 12px;
  border-left: 3px solid var(--el-color-primary);
  border-radius: 4px;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.review-form .el-form-item:last-child {
  margin-bottom: 0;
}
.request-meta {
  border-top: 1px solid #edf0f5;
  padding-top: 14px;
  color: var(--ink-soft);
  font-size: 12px;
}
.request-meta summary {
  cursor: pointer;
  padding: 4px 0;
}
.request-meta .evidence-fields {
  margin-top: 16px;
}
.full-width {
  width: 100%;
}
.sync-notice {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px;
  margin-bottom: 18px;
  background: var(--el-color-warning-light-9);
  border-radius: 6px;
  font-size: 13px;
}
.review-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.review-footer .el-button {
  margin-left: 0;
}
@media (max-width: 760px) {
  .review-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 24px;
  }
  .review-toolbar {
    gap: 12px;
  }
  .review-tools {
    gap: 8px;
  }
  .review-footer .el-button {
    flex: 1;
  }
  .list-caption {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }
  .filters .el-input {
    max-width: none;
  }
}
</style>
