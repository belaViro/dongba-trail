<script setup lang="ts">
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Download, Refresh, Search, Upload } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type UploadRequestOptions } from 'element-plus'
import { dateText, errorText, type Row } from '../api'
import type { Field } from '../resources'
import {
  datasetSplits,
  deleteSample,
  exportSamples,
  labelSources,
  listSamples,
  reviewStatuses,
  sampleEditDraft,
  sampleRecordLink,
  sampleScenes,
  sampleTypes,
  sampleValidation,
  updateSample,
  uploadSample,
  type SampleFilters,
} from '../samples'
import EntityForm from '../components/EntityForm.vue'
import MediaImage from '../components/MediaImage.vue'
import SampleImage from '../components/SampleImage.vue'
import StatusTag from '../components/StatusTag.vue'

// DATA-03 / FEEDBACK-01 / OPS-03 / PRIVACY-01: private, independently reviewed images.
const route = useRoute()
const router = useRouter()
const filters = reactive<SampleFilters>({
  q: '',
  review_status: '',
  character_id: '',
  recognition_id: '',
  dataset_version: '',
})
const page = ref(1)
const limit = ref(20)
const items = ref<Row[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const uploading = ref(false)
const uploadError = ref('')
let generation = 0

async function load() {
  const current = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = await listSamples(filters, page.value, limit.value)
    if (current !== generation) return
    items.value = result.items
    total.value = result.total
    if (page.value > 1 && !result.items.length) {
      page.value = Math.max(1, Math.ceil(result.total / limit.value))
      await load()
    }
  } catch (e) {
    if (current === generation) {
      items.value = []
      total.value = 0
      error.value = errorText(e)
    }
  } finally {
    if (current === generation) loading.value = false
  }
}
function search() {
  page.value = 1
  void load()
}
watch(
  () => route.query,
  (values) => {
    for (const key of Object.keys(filters) as (keyof SampleFilters)[]) {
      filters[key] = typeof values[key] === 'string' ? values[key] : ''
    }
    search()
  },
  { immediate: true },
)
onUnmounted(() => {
  generation++
})

const selected = ref<Row | null>(null)
const form = ref<Row>({})
const editorOpen = ref(false)
const editor = ref<InstanceType<typeof EntityForm>>()
const saving = ref(false)
const formError = ref('')
const dimensions = ref<{ width: number; height: number }>()
const fields = computed<Field[]>(() => [
  {
    key: 'character_id',
    label: '关联词条（通过需已审核或已发布）',
    type: 'relation',
    resource: 'characters',
    required: form.value.review_status === 'approved',
  },
  { key: 'sample_type', label: '样本类型', type: 'select', options: sampleTypes, required: true },
  { key: 'label_source', label: '标注来源', type: 'select', options: labelSources, required: true },
  { key: 'scene', label: '采集场景', required: true },
  { key: 'quality_score', label: '质量分（未评测留空）', type: 'number', min: 0, max: 1, precision: 3 },
  {
    key: 'source_ref',
    label: '资料来源',
    type: 'textarea',
    required: form.value.review_status === 'approved',
  },
  {
    key: 'dataset_split',
    label: '数据集划分（仅管理，不触发训练）',
    type: 'select',
    options: datasetSplits,
    required: true,
  },
  { key: 'dataset_version', label: '数据集版本' },
  { key: 'review_status', label: '本次审核结果', type: 'select', options: reviewStatuses, required: true },
  {
    key: 'review_note',
    label: '审核意见 / 驳回原因',
    type: 'textarea',
    required: form.value.review_status === 'rejected',
  },
])
const hasBbox = computed({
  get: () => form.value.bbox != null,
  set: (enabled: boolean) => {
    form.value.bbox = enabled ? [null, null, null, null] : null
  },
})
const previewBbox = computed(() => {
  const bbox = form.value.bbox
  return Array.isArray(bbox) && bbox.every((value) => Number.isInteger(value)) ? bbox : null
})
function edit(row: Row) {
  selected.value = row
  form.value = sampleEditDraft(row)
  dimensions.value = undefined
  formError.value = ''
  editorOpen.value = true
}
async function upload(options: UploadRequestOptions) {
  uploading.value = true
  uploadError.value = ''
  try {
    const row = await uploadSample(options.file)
    edit(row)
    ElMessage.success('图片已上传，当前为待审核样本，请补齐元数据')
    await load()
    return row
  } catch (e) {
    uploadError.value = errorText(e)
    throw e
  } finally {
    uploading.value = false
  }
}
async function submit() {
  if (!selected.value || saving.value) return
  formError.value = sampleValidation(form.value, dimensions.value)
  if (formError.value || !(await editor.value?.validate()?.catch(() => false))) return
  saving.value = true
  try {
    await updateSample(selected.value.id, form.value)
    editorOpen.value = false
    ElMessage.success('样本元数据及审核结果已保存')
    await load()
  } catch (e) {
    formError.value = errorText(e)
  } finally {
    saving.value = false
  }
}
const deleting = ref('')
async function remove(row: Row) {
  if (deleting.value) return
  try {
    await ElMessageBox.confirm(
      `确认永久删除样本“${row.id}”及其私有图片？此操作不可撤销，删除审计会保留。`,
      '删除样本',
      {
        confirmButtonText: '永久删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }
  deleting.value = row.id
  try {
    await deleteSample(row.id)
    ElMessage.success('样本及私有图片已删除')
    await load()
  } catch (e) {
    ElMessage.error(errorText(e))
  } finally {
    deleting.value = ''
  }
}

const exporting = reactive({
  visible: false,
  status: 'approved',
  limit: 1000,
  busy: false,
  error: '',
  filters: { ...filters },
})
function openExport() {
  Object.assign(exporting, {
    visible: true,
    status: filters.review_status || 'approved',
    error: '',
    filters: { ...filters },
  })
}
async function download() {
  if (exporting.busy) return
  exporting.busy = true
  exporting.error = ''
  try {
    const result = await exportSamples(exporting.filters, exporting.status, exporting.limit)
    const url = URL.createObjectURL(result.blob)
    try {
      const link = document.createElement('a')
      link.href = url
      link.download = `dongba-samples-${exporting.status}.zip`
      link.click()
    } finally {
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    }
    exporting.visible = false
    ElMessage.success('ZIP已下载；请核对manifest.json中的数量、审核状态及截断标记')
  } catch (e) {
    exporting.error = errorText(e)
  } finally {
    exporting.busy = false
  }
}
function label(options: { value: string; label: string }[], value: string) {
  return options.find((option) => option.value === value)?.label || value || '—'
}
</script>

<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">内容中心</span>
      <h1>图片样本</h1>
    </div>
    <div class="heading-actions">
      <el-button :icon="Download" @click="openExport">筛选导出</el-button>
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      <el-upload
        :show-file-list="false"
        accept="image/jpeg,image/png,image/webp"
        :disabled="uploading"
        :http-request="upload"
      >
        <el-button type="primary" :icon="Upload" :loading="uploading">上传样本</el-button>
      </el-upload>
    </div>
  </div>
  <el-alert
    title="样本图片仅供授权人员查看。用户纠错不等于已审核标注；文字反馈审核与图片样本审核相互独立。"
    type="info"
    :closable="false"
    show-icon
    class="page-alert"
  />
  <el-alert v-if="uploadError" :title="uploadError" type="error" :closable="false" class="page-alert" />
  <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="page-alert" />
  <div class="table-tools sample-filters">
    <el-input
      v-model="filters.q"
      :prefix-icon="Search"
      clearable
      maxlength="200"
      placeholder="搜索样本 / 来源"
      aria-label="搜索样本"
      @keyup.enter="search"
      @clear="search"
    />
    <el-select
      v-model="filters.review_status"
      clearable
      placeholder="全部审核状态"
      aria-label="审核状态筛选"
      @change="search"
    >
      <el-option v-for="option in reviewStatuses" :key="option.value" v-bind="option" />
    </el-select>
    <el-input
      v-model="filters.character_id"
      clearable
      maxlength="64"
      placeholder="关联词条编号"
      aria-label="词条筛选"
      @keyup.enter="search"
      @clear="search"
    />
    <el-input
      v-model="filters.recognition_id"
      clearable
      maxlength="64"
      placeholder="识别请求编号"
      aria-label="识别请求筛选"
      @keyup.enter="search"
      @clear="search"
    />
    <el-input
      v-model="filters.dataset_version"
      clearable
      maxlength="100"
      placeholder="数据集版本"
      aria-label="数据集版本筛选"
      @keyup.enter="search"
      @clear="search"
    />
    <el-button @click="search">查询</el-button>
    <span class="record-total">共 {{ total }} 条</span>
  </div>
  <el-table
    v-loading="loading"
    :data="items"
    :empty-text="error ? '数据加载失败' : '暂无样本'"
    class="data-table"
  >
    <el-table-column label="图片" width="88">
      <template #default="{ row }">
        <MediaImage
          :src="`/api/v1/admin/samples/${encodeURIComponent(row.id)}/image`"
          class="sample-thumbnail"
          preview
        />
      </template>
    </el-table-column>
    <el-table-column prop="id" label="样本编号" min-width="170" show-overflow-tooltip />
    <el-table-column prop="character_id" label="关联词条" min-width="150" show-overflow-tooltip />
    <el-table-column label="类型 / 场景" min-width="170">
      <template #default="{ row }">
        {{ label(sampleTypes, row.sample_type) }} / {{ label(sampleScenes, row.scene) }}
      </template>
    </el-table-column>
    <el-table-column label="审核状态" width="110">
      <template #default="{ row }"><StatusTag :value="row.review_status" /></template>
    </el-table-column>
    <el-table-column prop="dataset_version" label="数据集版本" min-width="130" show-overflow-tooltip />
    <el-table-column prop="source_ref" label="资料来源" min-width="160" show-overflow-tooltip />
    <el-table-column label="操作" width="250" fixed="right">
      <template #default="{ row }">
        <el-button link type="primary" @click="edit(row)">预览 / 复核</el-button>
        <el-button
          v-if="row.recognition_id"
          link
          type="primary"
          @click="router.push(sampleRecordLink('recognitions', row.recognition_id))"
        >
          识别
        </el-button>
        <el-button
          v-if="row.recognition_id"
          link
          type="primary"
          @click="router.push(sampleRecordLink('feedback', row.recognition_id))"
        >
          反馈
        </el-button>
        <el-button link type="danger" :disabled="!!deleting" @click="remove(row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>
  <div class="pagination">
    <el-pagination
      v-model:current-page="page"
      v-model:page-size="limit"
      :total="total"
      :page-sizes="[20, 50, 100]"
      layout="prev, pager, next, sizes"
      background
      @current-change="load"
      @size-change="search"
    />
  </div>

  <el-drawer
    v-model="editorOpen"
    title="样本预览与复核"
    size="min(780px, 100vw)"
    destroy-on-close
    :close-on-click-modal="false"
    :close-on-press-escape="!saving"
    :show-close="!saving"
  >
    <template v-if="selected">
      <div class="detail-status">
        <StatusTag :value="selected.review_status" />
        <span>{{ selected.id }}</span>
      </div>
      <SampleImage
        :key="selected.id"
        :sample-id="selected.id"
        :bbox="previewBbox"
        @dimensions="dimensions = $event"
      />
      <el-descriptions :column="1" border>
        <el-descriptions-item label="识别请求">
          <template v-if="selected.recognition_id">
            <span class="detail-text">{{ selected.recognition_id }}</span>
            <el-button
              link
              type="primary"
              @click="router.push(sampleRecordLink('recognitions', selected.recognition_id))"
            >
              查看识别
            </el-button>
            <el-button
              link
              type="primary"
              @click="router.push(sampleRecordLink('feedback', selected.recognition_id))"
            >
              查看文字反馈
            </el-button>
          </template>
          <span v-else>运营上传资料（无关联识别）</span>
        </el-descriptions-item>
        <el-descriptions-item label="留样用户">{{ selected.user_id || '—' }}</el-descriptions-item>
        <el-descriptions-item label="同意留样版本">
          {{ selected.consent_version || '不适用（运营资料）' }}
        </el-descriptions-item>
        <el-descriptions-item label="上次审核人 / 时间">
          {{ selected.reviewed_by || '—' }} / {{ dateText(selected.reviewed_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="创建 / 更新时间">
          {{ dateText(selected.created_at) }} / {{ dateText(selected.updated_at) }}
        </el-descriptions-item>
      </el-descriptions>
      <el-alert
        v-if="selected.review_status === 'approved'"
        title="已通过样本的本次编辑默认回到待审核。若要再次通过，请明确选择“已通过”并复核全部标注及来源。取消不会改变原状态。"
        type="warning"
        :closable="false"
        class="page-alert"
      />
      <el-alert v-if="formError" :title="formError" type="error" :closable="false" class="form-alert" />
      <fieldset :disabled="saving" class="sample-fields">
        <EntityForm ref="editor" v-model="form" :fields="fields" />
        <p class="muted">
          常用采集场景：paper / shop_sign / wall / wood / product / screen /
          other。未检测的框、未评测的质量分请留空。
        </p>
        <el-checkbox v-model="hasBbox">填写人工核对的标注框（保存PNG的像素坐标）</el-checkbox>
        <div v-if="hasBbox" class="bbox-fields">
          <label v-for="(name, index) in ['X', 'Y', '宽度', '高度']" :key="name">
            {{ name }}
            <el-input-number
              v-model="form.bbox[index]"
              :aria-label="`标注框${name}`"
              :min="index < 2 ? 0 : 1"
              :precision="0"
              controls-position="right"
            />
          </label>
        </div>
      </fieldset>
    </template>
    <template #footer>
      <el-button :disabled="saving" @click="editorOpen = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存元数据与审核</el-button>
    </template>
  </el-drawer>

  <el-dialog
    v-model="exporting.visible"
    title="筛选导出样本"
    width="min(540px, 94vw)"
    :close-on-click-modal="false"
    :close-on-press-escape="!exporting.busy"
    :show-close="!exporting.busy"
  >
    <el-alert
      title="导出ZIP包含manifest.json和私有图片。默认仅导出已通过样本；未审/驳回样本不作为权威标注。数据集划分不会触发训练。"
      type="info"
      :closable="false"
      class="page-alert"
    />
    <p class="detail-text">
      搜索：{{ exporting.filters.q || '全部' }}；词条：{{
        exporting.filters.character_id || '全部'
      }}；识别：{{ exporting.filters.recognition_id || '全部' }}；版本：{{
        exporting.filters.dataset_version || '全部'
      }}
    </p>
    <el-alert
      v-if="exporting.error"
      :title="exporting.error"
      type="error"
      :closable="false"
      class="form-alert"
    />
    <el-form label-position="top" :disabled="exporting.busy">
      <el-form-item label="导出审核状态">
        <el-select v-model="exporting.status" aria-label="导出审核状态">
          <el-option v-for="option in reviewStatuses" :key="option.value" v-bind="option" />
        </el-select>
      </el-form-item>
      <el-form-item label="最多导出数量（超出时请缩小筛选范围）">
        <el-input-number v-model="exporting.limit" :min="1" :max="10000" :precision="0" />
      </el-form-item>
    </el-form>
    <el-alert
      v-if="exporting.status !== 'approved'"
      title="本次显式导出未通过审核的样本，清单将保留其真实状态。"
      type="warning"
      :closable="false"
    />
    <template #footer>
      <el-button :disabled="exporting.busy" @click="exporting.visible = false">取消</el-button>
      <el-button type="primary" :loading="exporting.busy" @click="download">下载ZIP</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.sample-filters {
  flex-wrap: wrap;
}
.sample-thumbnail {
  width: 56px;
  height: 56px;
}
.sample-fields {
  border: 0;
  padding: 20px 0 0;
  margin: 0;
  min-width: 0;
}
.bbox-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}
.bbox-fields label {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.bbox-fields .el-input-number {
  width: 100%;
}
</style>
