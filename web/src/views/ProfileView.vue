<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { api, errorText, save, type Row } from '../api'
import { initialForm, resources } from '../resources'
import EntityForm from '../components/EntityForm.vue'
import StatusTag from '../components/StatusTag.vue'
const profile = ref<Row | null>(null)
const form = ref<Row>({})
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const editor = ref<InstanceType<typeof EntityForm>>()
const fields = resources.merchants!.fields.filter(
  (field) => !['character_ids', 'tags'].includes(field.key) && !field.operationsOnly,
)
async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api('/merchant/profile')
    profile.value = data
    form.value = initialForm({ ...resources.merchants!, fields }, data)
  } catch (e) {
    error.value = errorText(e)
  } finally {
    loading.value = false
  }
}
async function submit() {
  if (!(await editor.value?.validate()?.catch(() => false))) return
  saving.value = true
  error.value = ''
  try {
    profile.value = await save('/merchant/profile', form.value, 'PATCH')
    ElMessage.success('资料已提交审核')
    await load()
  } catch (e) {
    error.value = errorText(e)
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">门店工作台</span>
      <h1>门店资料</h1>
    </div>
    <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
  </div>
  <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="page-alert" />
  <section v-loading="loading" class="profile-section">
    <template v-if="profile">
      <div class="section-heading">
        <h2>{{ profile.name }}</h2>
        <StatusTag :value="profile.status" />
      </div>
      <EntityForm ref="editor" v-model="form" :fields="fields" merchant editing />
      <div class="form-footer">
        <el-button type="primary" :loading="saving" @click="submit">保存并提交审核</el-button>
      </div>
    </template>
    <el-empty v-else-if="!loading" description="暂无关联门店" />
  </section>
</template>
