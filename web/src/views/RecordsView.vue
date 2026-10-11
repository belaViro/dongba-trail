<script setup lang="ts">
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { api, dateText, errorText, query, save, type Collection, type Row } from '../api'
import StatusTag from '../components/StatusTag.vue'
import ExportButton from '../components/ExportButton.vue'
import { session } from '../session'
import { recordSampleLink, sampleRecordLink } from '../samples'
import {
  providerLabel,
  recognitionStatus,
  serviceStatusLabel,
  serviceStatusType,
  type ProviderStatus,
} from '../recognition-status'
const props = defineProps<{ resource: string }>()
const route = useRoute()
const router = useRouter()
const titles: Record<string, string> = {
  feedback: '识别纠错',
  'tag-claims': '文化标签审核',
  recognitions: '识别记录',
  audit: '操作审计',
  provider: '识别服务',
  redemptions: '核销记录',
}
const columns: Record<string, { key: string; label: string; width?: number }[]> = {
  feedback: [
    { key: 'recognition_id', label: '识别请求', width: 200 },
    { key: 'character_id', label: '确认词条' },
    { key: 'comment', label: '用户反馈' },
    { key: 'status', label: '状态', width: 110 },
    { key: 'created_at', label: '提交时间', width: 180 },
  ],
  'tag-claims': [
    { key: 'merchant_id', label: '商户' },
    { key: 'character_id', label: '东巴字' },
    { key: 'status', label: '审核状态', width: 110 },
    { key: 'review_note', label: '审核意见' },
    { key: 'created_at', label: '申请时间', width: 180 },
  ],
  recognitions: [
    { key: 'request_id', label: '请求编号', width: 220 },
    { key: 'status', label: '结果状态', width: 120 },
    { key: 'provider', label: '提供方' },
    { key: 'model', label: '模型' },
    { key: 'latency_ms', label: '耗时（ms）', width: 110 },
    { key: 'created_at', label: '请求时间', width: 180 },
  ],
  audit: [
    { key: 'action', label: '操作' },
    { key: 'user_id', label: '操作者' },
    { key: 'entity_type', label: '资源类型', width: 120 },
    { key: 'entity_id', label: '资源编号' },
    { key: 'created_at', label: '操作时间', width: 180 },
  ],
  redemptions: [
    { key: 'code', label: '核销码' },
    { key: 'title', label: '优惠券' },
    { key: 'user_id', label: '领取用户' },
    { key: 'verified_at', label: '核销时间', width: 180 },
    { key: 'status', label: '状态', width: 110 },
  ],
}
const labels: Record<string, string> = {
  id: '编号',
  request_id: '请求编号',
  recognition_id: '识别请求',
  user_id: '用户编号',
  character_id: '东巴字编号',
  merchant_id: '商户编号',
  status: '状态',
  review_note: '审核意见',
  reviewed_by: '审核人',
  reviewed_at: '审核时间',
  created_at: '创建时间',
  comment: '用户反馈',
  provider: '提供方',
  model: '模型',
  candidates: '识别候选',
  latency_ms: '耗时（ms）',
  scene: '识别场景',
  error_code: '错误码',
  confirmed_character_id: '用户确认词条',
  action: '操作',
  entity_type: '资源类型',
  entity_id: '资源编号',
  detail: '操作详情',
  code: '核销码',
  coupon_id: '优惠券编号',
  redeemed_at: '核销时间',
  configured: '服务配置',
  name: '提供方',
  endpoint_configured: '服务地址已配置',
  timeout_seconds: '超时（秒）',
  unconfigured_reason: '不可用原因',
  model_version: '模型版本',
  enabled: '是否启用',
  available: '是否可用',
}
const items = ref<Row[]>([])
const total = ref(0)
const provider = ref<Partial<ProviderStatus> | null>(null)
const service = computed(() => (provider.value ? recognitionStatus(provider.value) : null))
const statisticsScoped = computed(
  () =>
    provider.value?.statistics_scope === 'current_provider_and_model' &&
    provider.value.statistics_limit === 1000,
)
function metric(value: number | null | undefined, unit: string): string {
  return statisticsScoped.value && typeof value === 'number' && Number.isFinite(value) && value >= 0
    ? `${value} ${unit}`
    : '暂无数据'
}
const loading = ref(false)
const error = ref('')
const filter = reactive({ q: '', status: '', page: 1, limit: 20 })
const endpoint = computed(
  () => `/${session.user?.role === 'merchant' ? 'merchant' : 'admin'}/${props.resource}`,
)
const reviewable = computed(() => ['feedback', 'tag-claims'].includes(props.resource))
const sampleRelated = computed(() => ['feedback', 'recognitions'].includes(props.resource))
function showSamples(row: Row) {
  const target = recordSampleLink(props.resource, row)
  if (target) void router.push(target)
}
const detail = ref<Row | null>(null)
const detailOpen = ref(false)
function openDetail(row: Row) {
  detail.value = row
  detailOpen.value = true
}
const review = reactive({
  visible: false,
  row: null as Row | null,
  status: 'approved',
  review_note: '',
  busy: false,
  error: '',
})
let generation = 0
async function load() {
  const current = ++generation
  loading.value = true
  error.value = ''
  try {
    if (props.resource === 'provider') {
      const result = await api<Partial<ProviderStatus>>(endpoint.value)
      if (current === generation) provider.value = result
    } else {
      const data = await api<Collection>(
        `${endpoint.value}?${query({ q: filter.q, status: filter.status, offset: (filter.page - 1) * filter.limit, limit: filter.limit })}`,
      )
      if (current !== generation) return
      items.value = data.items
      total.value = data.total
    }
  } catch (e) {
    if (current === generation) {
      items.value = []
      total.value = 0
      provider.value = null
      error.value = errorText(e)
    }
  } finally {
    if (current === generation) loading.value = false
  }
}
function search() {
  filter.page = 1
  void load()
}
function openReview(row: Row) {
  Object.assign(review, { visible: true, row, status: 'approved', review_note: '', error: '' })
}
async function submitReview() {
  if (review.status === 'rejected' && !review.review_note.trim()) {
    review.error = '请填写驳回原因'
    return
  }
  review.busy = true
  review.error = ''
  try {
    await save(
      `${endpoint.value}/${review.row?.id}`,
      { status: review.status, review_note: review.review_note },
      'PATCH',
    )
    review.visible = false
    ElMessage.success('审核结果已保存')
    await load()
  } catch (e) {
    review.error = errorText(e)
  } finally {
    review.busy = false
  }
}
function display(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}
// Samples link through the supported records q filter; query-only navigation also reloads.
watch(
  () => [props.resource, route.query.q],
  () => {
    filter.q = typeof route.query.q === 'string' ? route.query.q : ''
    filter.status = ''
    detailOpen.value = false
    review.visible = false
    search()
  },
  { immediate: true },
)
onUnmounted(() => {
  generation++
})
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">{{ resource === 'redemptions' ? '经营管理' : '运营管理' }}</span>
      <h1>{{ titles[resource] }}</h1>
    </div>
    <div class="heading-actions">
      <ExportButton
        v-if="['feedback', 'recognitions', 'audit', 'tag-claims'].includes(resource)"
        :resource="resource"
        :search="filter.q"
        :status="filter.status"
      />
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </div>
  </div>
  <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="page-alert" />
  <section v-if="resource === 'provider'" v-loading="loading" class="settings-section">
    <template v-if="provider && service">
      <div class="section-heading">
        <h2>服务状态</h2>
        <el-tag :type="serviceStatusType(service.status)">
          {{ serviceStatusLabel(service.status) }}
        </el-tag>
      </div>
      <el-alert
        :title="service.status_message"
        :type="serviceStatusType(service.status)"
        :closable="false"
        show-icon
        class="page-alert"
      />
      <el-descriptions :column="1" border>
        <el-descriptions-item label="当前提供方">{{ providerLabel(service.name) }}</el-descriptions-item>
        <el-descriptions-item label="服务类型">
          {{
            service.kind === 'local'
              ? '本地 CPU 推理'
              : service.kind === 'external'
                ? '外部 API 服务'
                : '未启用'
          }}
        </el-descriptions-item>
        <el-descriptions-item label="当前模型版本">
          {{ service.kind === 'unconfigured' ? '未启用' : service.model || '暂未提供' }}
        </el-descriptions-item>
        <el-descriptions-item v-if="service.kind === 'external'" label="接口地址配置">
          {{
            service.endpoint_configured === null
              ? '暂未提供'
              : service.endpoint_configured
                ? '已配置'
                : '未配置'
          }}
        </el-descriptions-item>
        <el-descriptions-item v-if="service.kind !== 'unconfigured'" label="识别超时">
          {{ service.timeout_seconds === null ? '暂未提供' : `${service.timeout_seconds} 秒` }}
        </el-descriptions-item>
        <el-descriptions-item v-if="service.kind === 'local'" label="CPU 线程数">
          {{ service.cpu_threads ?? '暂未提供' }}
        </el-descriptions-item>
        <el-descriptions-item label="自动付费兜底">不启用；仅支持手动切换并保存提供方</el-descriptions-item>
        <el-descriptions-item label="候选分数">未校准，仅供参考，不代表准确率</el-descriptions-item>
        <el-descriptions-item label="最近请求数">
          {{ metric(provider.recent_requests, '次') }}
        </el-descriptions-item>
        <el-descriptions-item label="最近失败数">
          {{ metric(provider.recent_errors, '次') }}
        </el-descriptions-item>
        <el-descriptions-item label="成功请求 P95 耗时">
          {{ metric(provider.p95_latency_ms, '毫秒') }}
        </el-descriptions-item>
      </el-descriptions>
      <p>统计范围：仅当前提供方、当前模型的最近最多 1000 条请求；P95 仅统计成功请求。</p>
      <p v-if="!statisticsScoped">暂未提供此统计口径的数据，不展示口径不明的旧统计。</p>
      <p v-if="service.kind === 'local'">本地模型“已加载”仅证明加载成功，不代表识别准确率。</p>
      <p v-else-if="service.kind === 'external'">外部服务“已配置”仅表示配置完整，未探测连接。</p>
      <p>刷新仅读取状态和统计，不调用付费识别 API；无自动付费兜底。候选仍需用户确认。</p>
    </template>
    <el-empty v-else-if="!loading" description="服务状态不可用" />
  </section>
  <template v-else>
    <div class="table-tools">
      <el-input
        v-model="filter.q"
        :prefix-icon="Search"
        clearable
        placeholder="搜索记录"
        aria-label="搜索记录"
        @keyup.enter="search"
        @clear="search"
      />
      <el-select
        v-if="reviewable"
        v-model="filter.status"
        clearable
        placeholder="全部状态"
        aria-label="状态筛选"
        @change="search"
      >
        <el-option label="待审核" value="pending" />
        <el-option label="已通过" value="approved" />
        <el-option label="已驳回" value="rejected" />
      </el-select>
      <el-button @click="search">查询</el-button>
      <div class="tools-spacer" />
      <span class="record-total">共 {{ total }} 条</span>
    </div>
    <el-table
      v-loading="loading"
      :data="items"
      :empty-text="error ? '数据加载失败' : '暂无记录'"
      class="data-table"
    >
      <el-table-column
        v-for="column in columns[resource]"
        :key="column.key"
        :prop="column.key"
        :label="column.label"
        :width="column.width"
        :min-width="column.width ? undefined : 150"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <StatusTag v-if="column.key === 'status'" :value="row[column.key]" />
          <span v-else-if="column.key.endsWith('_at')">{{ dateText(row[column.key]) }}</span>
          <span v-else>{{ display(row[column.key]) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" :width="sampleRelated ? 220 : reviewable ? 140 : 90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button v-if="reviewable" link type="primary" @click="openReview(row)">审核</el-button>
          <el-button v-if="recordSampleLink(resource, row)" link type="primary" @click="showSamples(row)">
            纠错与附图
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="pagination">
      <el-pagination
        v-model:current-page="filter.page"
        v-model:page-size="filter.limit"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="prev, pager, next, sizes"
        background
        @current-change="load"
        @size-change="search"
      />
    </div>
  </template>
  <el-drawer v-model="detailOpen" title="记录详情" size="min(720px, 100vw)">
    <div v-if="detail && recordSampleLink(resource, detail)" class="detail-status">
      <el-button type="primary" plain @click="showSamples(detail)">查看纠错与附图</el-button>
      <el-button
        v-if="resource === 'feedback'"
        @click="router.push(sampleRecordLink('recognitions', detail.recognition_id))"
      >
        查看识别记录
      </el-button>
    </div>
    <el-descriptions v-if="detail" :column="1" border>
      <el-descriptions-item v-for="(value, key) in detail" :key="key" :label="labels[key] || key">
        <StatusTag v-if="key === 'status'" :value="String(value)" />
        <span v-else class="detail-text">
          {{ String(key).endsWith('_at') ? dateText(value) : display(value) }}
        </span>
      </el-descriptions-item>
    </el-descriptions>
  </el-drawer>
  <el-dialog v-model="review.visible" title="审核记录" width="min(500px, 94vw)" :close-on-click-modal="false">
    <el-button
      v-if="review.row && recordSampleLink(resource, review.row)"
      link
      type="primary"
      @click="showSamples(review.row)"
    >
      查看纠错与附图
    </el-button>
    <el-alert v-if="review.error" :title="review.error" type="error" :closable="false" class="form-alert" />
    <el-form label-position="top">
      <el-form-item label="审核结果">
        <el-radio-group v-model="review.status">
          <el-radio-button value="approved">通过</el-radio-button>
          <el-radio-button value="rejected">驳回</el-radio-button>
          <el-radio-button value="pending">待审核</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="审核意见" :required="review.status === 'rejected'">
        <el-input v-model="review.review_note" type="textarea" :rows="4" maxlength="2000" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="review.visible = false">取消</el-button>
      <el-button type="primary" :loading="review.busy" @click="submitReview">提交审核</el-button>
    </template>
  </el-dialog>
</template>
