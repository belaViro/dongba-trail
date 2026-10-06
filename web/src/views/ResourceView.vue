<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Download, Edit, Plus, Refresh, Search, More } from '@element-plus/icons-vue'
import QRCode from 'qrcode'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, dateText, errorText, query, save, type Collection, type Row } from '../api'
import { session } from '../session'
import { initialForm, payloadFor, resources, statusOptions } from '../resources'
import EntityForm from '../components/EntityForm.vue'
import StatusTag from '../components/StatusTag.vue'
import MediaImage from '../components/MediaImage.vue'
import ExportButton from '../components/ExportButton.vue'
import RevisionHistory from '../components/RevisionHistory.vue'
const props = defineProps<{ resource: string }>()
const config = computed(() => resources[props.resource]!)
const merchant = computed(() => session.user?.role === 'merchant')
const endpoint = computed(() => `/${merchant.value ? 'merchant' : 'admin'}/${props.resource}`)
const items = ref<Row[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const filter = reactive({ q: '', status: '', page: 1, limit: 20 })
const showEditor = ref(false)
const editing = ref<Row | null>(null)
const form = ref<Row>({})
const editor = ref<InstanceType<typeof EntityForm>>()
const saving = ref(false)
const formError = ref('')
const detail = ref<Row | null>(null)
const showDetail = ref(false)
const historyId = ref('')
const showHistory = ref(false)
function openHistory(row: Row) {
  historyId.value = row.id
  showHistory.value = true
}
const qr = reactive({ visible: false, image: '', name: '', id: '', loading: false, error: '' })
async function showQr(row: Row) {
  Object.assign(qr, { visible: true, image: '', name: row.name, id: row.id, loading: true, error: '' })
  try {
    if (!row.qr_token) throw new Error('该节点尚未生成扫码口令')
    qr.image = await QRCode.toDataURL(row.qr_token, { width: 800, margin: 4, errorCorrectionLevel: 'M' })
  } catch (error) {
    qr.error = errorText(error)
  } finally {
    qr.loading = false
  }
}
function downloadQr() {
  const link = document.createElement('a')
  link.href = qr.image
  link.download = `dongba-quest-${qr.id}.png`
  link.click()
}
function handleCommand(command: string, row: Row) {
  if (command === 'delete') void remove(row)
  else if (command === 'history') openHistory(row)
  else if (command === 'qr') void showQr(row)
  else if (command === 'manual') Object.assign(manual, { visible: true, node: row, user_id: '', error: '' })
  else if (['published', 'draft', 'active'].includes(command)) void changeStatus(row, command)
}
function openDetail(row: Row) {
  detail.value = row
  showDetail.value = true
}
const manual = reactive({ visible: false, node: null as Row | null, user_id: '', busy: false, error: '' })
const roleNames: Record<string, string> = {
  admin: '管理员',
  operator: '运营人员',
  merchant: '商户',
  tourist: '游客',
}
const conditionNames: Record<string, string> = {
  recognition: '识别',
  qr: '扫码',
  geofence: '到达地点',
  coupon: '核销',
  manual: '人工确认',
}
const columns = computed(() =>
  config.value.columns.filter((c) => !(merchant.value && c.key === 'merchant_id')),
)
async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api<Collection>(
      `${endpoint.value}?${query({ q: filter.q, status: filter.status, offset: (filter.page - 1) * filter.limit, limit: filter.limit })}`,
    )
    items.value = data.items
    total.value = data.total
  } catch (e) {
    error.value = errorText(e)
  } finally {
    loading.value = false
  }
}
function search() {
  filter.page = 1
  void load()
}
function edit(row?: Row) {
  editing.value = row || null
  form.value = initialForm(config.value, row)
  formError.value = ''
  showEditor.value = true
}
async function submit() {
  if (!(await editor.value?.validate()?.catch(() => false))) return
  if (
    form.value.start_at &&
    form.value.end_at &&
    new Date(form.value.end_at) <= new Date(form.value.start_at)
  ) {
    formError.value = '结束时间必须晚于开始时间'
    return
  }
  if (props.resource === 'users' && form.value.role === 'merchant' && !form.value.merchant_id) {
    formError.value = '商户账号必须关联门店'
    return
  }
  saving.value = true
  formError.value = ''
  try {
    await save(
      `${endpoint.value}${editing.value ? `/${encodeURIComponent(editing.value.id)}` : ''}`,
      payloadFor(config.value, form.value, merchant.value, !!editing.value),
      editing.value ? 'PATCH' : 'POST',
    )
    showEditor.value = false
    ElMessage.success('已保存')
    await load()
  } catch (e) {
    formError.value = errorText(e)
  } finally {
    saving.value = false
  }
}
async function remove(row: Row) {
  try {
    await ElMessageBox.confirm(
      `确认停用“${row.cn_name || row.name || row.title || row.username || row.id}”？现有业务记录会保留。`,
      '停用确认',
      { confirmButtonText: '停用', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await api(`${endpoint.value}/${encodeURIComponent(row.id)}`, { method: 'DELETE' })
    ElMessage.success('已停用')
    await load()
  } catch (e) {
    ElMessage.error(errorText(e))
  }
}
async function changeStatus(row: Row, status: string) {
  try {
    await save(`${endpoint.value}/${encodeURIComponent(row.id)}`, { status }, 'PATCH')
    ElMessage.success(status === 'published' ? '已审核并发布' : '状态已更新')
    await load()
  } catch (e) {
    ElMessage.error(errorText(e))
  }
}
function display(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  if (Array.isArray(value))
    return value.map((v) => (typeof v === 'object' ? JSON.stringify(v) : v)).join('、') || '—'
  return String(value)
}
async function completeManual() {
  if (!manual.user_id.trim() || !manual.node) {
    manual.error = '请输入游客用户编号'
    return
  }
  manual.busy = true
  manual.error = ''
  try {
    await save(`/admin/quests/${manual.node.quest_id}/complete-node`, {
      user_id: manual.user_id.trim(),
      node_id: manual.node.id,
    })
    manual.visible = false
    ElMessage.success('节点已确认完成')
  } catch (e) {
    manual.error = errorText(e)
  } finally {
    manual.busy = false
  }
}
onMounted(load)
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">{{ config.group }}</span>
      <h1>{{ config.title }}</h1>
    </div>
    <div class="heading-actions">
      <ExportButton
        v-if="resource === 'characters' && !merchant"
        resource="characters"
        :search="filter.q"
        :status="filter.status"
      />
      <el-button type="primary" :icon="Plus" @click="edit()">新增{{ config.singular }}</el-button>
    </div>
  </div>
  <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="page-alert" />
  <div class="table-tools">
    <el-input
      v-model="filter.q"
      :prefix-icon="Search"
      clearable
      :placeholder="`搜索${config.singular}`"
      aria-label="搜索"
      @keyup.enter="search"
      @clear="search"
    />
    <el-select
      v-model="filter.status"
      placeholder="全部状态"
      clearable
      aria-label="状态筛选"
      @change="search"
    >
      <el-option
        v-for="status in props.resource === 'users'
          ? [
              { label: '正常', value: 'active' },
              { label: '已停用', value: 'disabled' },
            ]
          : statusOptions"
        :key="status.value"
        :label="status.label"
        :value="status.value"
      />
    </el-select>
    <el-button @click="search">查询</el-button>
    <div class="tools-spacer" />
    <span class="record-total">共 {{ total }} 条</span>
    <el-tooltip content="刷新"><el-button :icon="Refresh" aria-label="刷新" @click="load" /></el-tooltip>
  </div>
  <el-table
    v-loading="loading"
    :data="items"
    row-key="id"
    class="data-table"
    :empty-text="error ? '数据加载失败' : '暂无记录'"
  >
    <el-table-column
      v-for="column in columns"
      :key="column.key"
      :prop="column.key"
      :label="column.label"
      :width="column.width"
      :min-width="column.width ? undefined : 155"
      show-overflow-tooltip
    >
      <template #default="{ row }">
        <StatusTag v-if="column.type === 'status'" :value="row[column.key]" />
        <MediaImage
          v-else-if="column.type === 'image' && row[column.key]"
          class="table-thumb"
          :src="row[column.key]"
          preview
          fit="contain"
        />
        <span v-else-if="column.type === 'image'" class="image-absent">—</span>
        <span v-else-if="column.type === 'date'">{{ dateText(row[column.key]) }}</span>
        <span v-else-if="column.type === 'money'">¥{{ Number(row[column.key] || 0).toFixed(2) }}</span>
        <el-button
          v-else-if="['cn_name', 'name', 'title', 'username'].includes(column.key)"
          link
          class="row-title"
          @click="openDetail(row)"
        >
          {{ row[column.key] }}
        </el-button>
        <span v-else>
          {{ roleNames[row[column.key]] || conditionNames[row[column.key]] || row[column.key] || '—' }}
        </span>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="154" fixed="right">
      <template #default="{ row }">
        <div class="row-actions">
          <el-tooltip content="编辑">
            <el-button :icon="Edit" text aria-label="编辑" @click="edit(row)" />
          </el-tooltip>
          <el-dropdown trigger="click" @command="(command: string) => handleCommand(command, row)">
            <el-button :icon="More" text aria-label="更多操作" />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="resource === 'characters' && !merchant" command="history">
                  历史版本
                </el-dropdown-item>
                <template v-if="!merchant">
                  <el-dropdown-item
                    v-if="resource === 'users'"
                    command="active"
                    :disabled="row.status === 'active'"
                  >
                    启用账号
                  </el-dropdown-item>
                  <template v-else>
                    <el-dropdown-item v-if="row.status !== 'published'" command="published">
                      审核并发布
                    </el-dropdown-item>
                    <el-dropdown-item command="draft" :disabled="row.status === 'draft'">
                      退回草稿
                    </el-dropdown-item>
                  </template>
                </template>
                <el-dropdown-item v-if="resource === 'quest-nodes' && row.condition === 'qr'" command="qr">
                  任务二维码
                </el-dropdown-item>
                <el-dropdown-item
                  v-if="resource === 'quest-nodes' && row.condition === 'manual'"
                  command="manual"
                >
                  人工确认打卡
                </el-dropdown-item>
                <el-dropdown-item command="delete" :disabled="row.status === 'disabled'" divided>
                  {{ resource === 'users' ? '停用账号' : '下架停用' }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
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
  <el-drawer
    v-model="showEditor"
    :title="`${editing ? '编辑' : '新增'}${config.singular}`"
    size="min(760px, 100vw)"
    destroy-on-close
    :close-on-click-modal="false"
  >
    <el-alert
      v-if="formError"
      :title="formError"
      type="error"
      :closable="false"
      show-icon
      class="form-alert"
    />
    <EntityForm
      ref="editor"
      v-model="form"
      :fields="config.fields"
      :editing="!!editing"
      :merchant="merchant"
    />
    <template #footer>
      <el-button @click="showEditor = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
    </template>
  </el-drawer>
  <el-drawer v-model="showDetail" :title="`${config.singular}详情`" size="min(680px, 100vw)">
    <template v-if="detail">
      <div class="detail-status">
        <StatusTag :value="detail.status" />
        <span>{{ detail.id }}</span>
        <el-button
          v-if="resource === 'characters' && !merchant"
          link
          type="primary"
          @click="openHistory(detail)"
        >
          历史版本
        </el-button>
      </div>
      <el-descriptions :column="1" border>
        <el-descriptions-item
          v-for="field in config.fields.filter((f) => f.key !== 'password')"
          :key="field.key"
          :label="field.label"
        >
          <MediaImage
            v-if="field.type === 'image' && detail[field.key]"
            :src="detail[field.key]"
            class="detail-image"
            fit="contain"
            preview
          />
          <audio
            v-else-if="field.key === 'audio_url' && detail[field.key]"
            controls
            :src="detail[field.key]"
          />
          <div v-else-if="field.type === 'variants'" class="detail-variants">
            <div v-for="variant in detail[field.key]" :key="variant.image_url">
              <MediaImage :src="variant.image_url" fit="contain" preview />
              <p>{{ variant.source_ref }}</p>
            </div>
          </div>
          <span v-else class="detail-text">
            {{ field.type === 'datetime' ? dateText(detail[field.key]) : display(detail[field.key]) }}
          </span>
        </el-descriptions-item>
      </el-descriptions>
    </template>
  </el-drawer>
  <el-drawer v-model="showHistory" title="词条历史版本" size="min(780px, 100vw)" destroy-on-close>
    <RevisionHistory
      v-if="showHistory"
      :key="`${resource}/${historyId}`"
      :resource="resource"
      :entity-id="historyId"
    />
  </el-drawer>
  <el-dialog v-model="manual.visible" title="人工确认打卡" width="min(460px, 94vw)">
    <el-alert v-if="manual.error" :title="manual.error" type="error" :closable="false" class="form-alert" />
    <el-form label-position="top">
      <el-form-item label="节点"><el-input :model-value="manual.node?.name" disabled /></el-form-item>
      <el-form-item label="游客用户编号"><el-input v-model="manual.user_id" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="manual.visible = false">取消</el-button>
      <el-button type="primary" :loading="manual.busy" @click="completeManual">确认完成</el-button>
    </template>
  </el-dialog>
  <el-dialog v-model="qr.visible" title="任务二维码" width="min(450px, 94vw)">
    <el-alert v-if="qr.error" :title="qr.error" type="error" :closable="false" show-icon />
    <div v-loading="qr.loading" class="quest-qr">
      <h2>{{ qr.name }}</h2>
      <img v-if="qr.image" :src="qr.image" alt="任务节点二维码" />
    </div>
    <template #footer>
      <el-button @click="qr.visible = false">关闭</el-button>
      <el-button type="primary" :icon="Download" :disabled="!qr.image" @click="downloadQr">
        下载二维码
      </el-button>
    </template>
  </el-dialog>
</template>
