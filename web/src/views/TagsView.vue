<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { api, dateText, errorText, save, type Collection, type Row } from '../api'
import StatusTag from '../components/StatusTag.vue'
const items = ref<Row[]>([])
const characters = ref<Row[]>([])
const loading = ref(false)
const error = ref('')
const total = ref(0)
const page = ref(1)
const applying = reactive({ visible: false, character_id: '', busy: false, error: '', loading: false })
async function load() {
  loading.value = true
  error.value = ''
  try {
    const result = await api<Collection>(`/merchant/tag-claims?offset=${(page.value - 1) * 20}&limit=20`)
    items.value = result.items
    total.value = result.total
  } catch (e) {
    error.value = errorText(e)
  } finally {
    loading.value = false
  }
}
async function lookup(q = '') {
  applying.loading = true
  try {
    const result = await api<Collection>(`/characters?q=${encodeURIComponent(q)}&limit=100`)
    characters.value = result.items
  } catch (e) {
    applying.error = errorText(e)
  } finally {
    applying.loading = false
  }
}
function openApply() {
  applying.visible = true
  applying.character_id = ''
  applying.error = ''
  void lookup()
}
async function submit() {
  if (!applying.character_id) {
    applying.error = '请选择关联东巴字'
    return
  }
  applying.busy = true
  applying.error = ''
  try {
    await save('/merchant/tag-claims', { character_id: applying.character_id })
    applying.visible = false
    ElMessage.success('申请已提交')
    await load()
  } catch (e) {
    applying.error = errorText(e)
  } finally {
    applying.busy = false
  }
}
onMounted(load)
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">门店工作台</span>
      <h1>文化标签</h1>
    </div>
    <el-button type="primary" :icon="Plus" @click="openApply">申请关联</el-button>
  </div>
  <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="page-alert" />
  <div class="table-tools">
    <span class="record-total">共 {{ total }} 条申请</span>
    <div class="tools-spacer" />
    <el-button :icon="Refresh" aria-label="刷新" @click="load" />
  </div>
  <el-table v-loading="loading" :data="items" class="data-table" empty-text="暂无标签申请">
    <el-table-column prop="character_id" label="东巴字" min-width="180">
      <template #default="{ row }">{{ row.cn_name || row.character_id }}</template>
    </el-table-column>
    <el-table-column label="审核状态" width="120">
      <template #default="{ row }"><StatusTag :value="row.status" /></template>
    </el-table-column>
    <el-table-column prop="review_note" label="审核意见" min-width="200" />
    <el-table-column label="申请时间" width="180">
      <template #default="{ row }">{{ dateText(row.created_at) }}</template>
    </el-table-column>
  </el-table>
  <div class="pagination">
    <el-pagination
      v-model:current-page="page"
      :page-size="20"
      :total="total"
      layout="prev, pager, next"
      background
      @current-change="load"
    />
  </div>
  <el-dialog
    v-model="applying.visible"
    title="申请文化标签"
    width="min(500px, 94vw)"
    :close-on-click-modal="false"
  >
    <el-alert
      v-if="applying.error"
      :title="applying.error"
      type="error"
      :closable="false"
      class="form-alert"
    />
    <el-form label-position="top">
      <el-form-item label="关联东巴字" required>
        <el-select
          v-model="applying.character_id"
          filterable
          remote
          :remote-method="lookup"
          :loading="applying.loading"
          placeholder="搜索已发布东巴字"
        >
          <el-option
            v-for="character in characters"
            :key="character.id"
            :label="character.cn_name"
            :value="character.id"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="applying.visible = false">取消</el-button>
      <el-button type="primary" :loading="applying.busy" @click="submit">提交申请</el-button>
    </template>
  </el-dialog>
</template>
