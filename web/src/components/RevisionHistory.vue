<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { dateText, errorText } from '../api'
import { loadRevisions, revisionActions, snapshotFields, snapshotText, type Revision } from '../revisions'
import MediaImage from './MediaImage.vue'
import StatusTag from './StatusTag.vue'

const props = defineProps<{ resource: string; entityId: string }>()
const items = ref<Revision[]>([])
const total = ref(0)
const selectedId = ref('')
const loading = ref(false)
const error = ref('')
const selected = computed(() => items.value.find((item) => item.id === selectedId.value))
const fields = computed(() => (selected.value ? snapshotFields(selected.value.snapshot, props.resource) : []))
let generation = 0
async function load() {
  const current = ++generation
  loading.value = true
  error.value = ''
  items.value = []
  total.value = 0
  selectedId.value = ''
  try {
    const result = await loadRevisions(props.resource, props.entityId)
    if (current !== generation) return
    items.value = [...result.items].sort((a, b) => b.version - a.version)
    total.value = result.total
    selectedId.value = items.value[0]?.id || ''
  } catch (e) {
    if (current === generation) error.value = errorText(e)
  } finally {
    if (current === generation) loading.value = false
  }
}
watch(() => [props.resource, props.entityId], load, { immediate: true })
onUnmounted(() => {
  generation++
})
</script>

<template>
  <div v-loading="loading">
    <el-alert
      title="只读历史快照，不会覆盖当前词条。迁移基线之前的历史未记录，不作推测。"
      type="info"
      :closable="false"
      class="page-alert"
    />
    <div class="section-heading">
      <span>共 {{ total }} 个版本</span>
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新历史</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="page-alert" />
    <el-empty v-else-if="!loading && !items.length" description="暂无可查询的历史版本" />
    <template v-if="items.length">
      <el-select v-model="selectedId" aria-label="历史版本" class="version-select">
        <el-option
          v-for="item in items"
          :key="item.id"
          :value="item.id"
          :label="`版本 ${item.version} · ${revisionActions[item.action] || item.action} · ${dateText(item.created_at)}`"
        />
      </el-select>
      <template v-if="selected">
        <el-descriptions :column="1" border class="revision-meta">
          <el-descriptions-item label="修订编号">{{ selected.id }}</el-descriptions-item>
          <el-descriptions-item label="词条编号">{{ selected.entity_id }}</el-descriptions-item>
          <el-descriptions-item label="版本 / 操作">
            {{ selected.version }} / {{ revisionActions[selected.action] || selected.action }}
          </el-descriptions-item>
          <el-descriptions-item label="操作者">
            {{ selected.actor_id || '未记录（基线）' }}
          </el-descriptions-item>
          <el-descriptions-item label="修订时间">{{ dateText(selected.created_at) }}</el-descriptions-item>
        </el-descriptions>
        <h3>当时完整内容</h3>
        <el-descriptions :column="1" border>
          <el-descriptions-item v-for="field in fields" :key="field.key" :label="field.label">
            <template v-if="field.type === 'image' && selected.snapshot[field.key]">
              <MediaImage :src="selected.snapshot[field.key]" class="detail-image" preview />
              <p class="detail-text">{{ selected.snapshot[field.key] }}</p>
            </template>
            <div
              v-else-if="field.type === 'variants' && Array.isArray(selected.snapshot[field.key])"
              class="revision-variants"
            >
              <span v-if="!selected.snapshot[field.key].length">—</span>
              <div v-for="(variant, index) in selected.snapshot[field.key]" :key="index">
                <MediaImage v-if="variant.image_url" :src="variant.image_url" class="detail-image" preview />
                <p class="detail-text">{{ snapshotText(variant) }}</p>
              </div>
            </div>
            <StatusTag v-else-if="field.key === 'status'" :value="selected.snapshot[field.key]" />
            <span v-else class="detail-text">
              {{
                field.key.endsWith('_at')
                  ? dateText(selected.snapshot[field.key])
                  : snapshotText(selected.snapshot[field.key])
              }}
            </span>
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </template>
  </div>
</template>

<style scoped>
.version-select {
  width: 100%;
  margin-bottom: 20px;
}
.revision-meta {
  margin-bottom: 24px;
}
.revision-variants {
  display: grid;
  gap: 16px;
}
.revision-variants p {
  margin: 8px 0 0;
}
</style>
