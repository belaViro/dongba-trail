<script setup lang="ts">
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { Picture, Refresh } from '@element-plus/icons-vue'
import { apiBlob, errorText } from '../api'
const props = defineProps<{ sampleId: string; bbox?: number[] | null }>()
const emit = defineEmits<{ dimensions: [value: { width: number; height: number }] }>()
const image = ref('')
const error = ref('')
const loading = ref(false)
const size = reactive({ width: 0, height: 0 })
let generation = 0
function release() {
  if (image.value) URL.revokeObjectURL(image.value)
  image.value = ''
}
async function load() {
  const current = ++generation
  release()
  Object.assign(size, { width: 0, height: 0 })
  error.value = ''
  loading.value = true
  try {
    const result = await apiBlob(`/admin/samples/${encodeURIComponent(props.sampleId)}/image`)
    if (current === generation) image.value = URL.createObjectURL(result.blob)
  } catch (e) {
    if (current === generation) error.value = errorText(e)
  } finally {
    if (current === generation) loading.value = false
  }
}
function loaded(event: Event) {
  const img = event.target as HTMLImageElement
  Object.assign(size, { width: img.naturalWidth, height: img.naturalHeight })
  emit('dimensions', { ...size })
}
const frameStyle = computed(() => size.width ? {
  width: `min(100%, ${Math.min(540, 460 * size.width / size.height)}px)`,
  aspectRatio: `${size.width} / ${size.height}`,
} : {})
const bboxStyle = computed(() => {
  if (!props.bbox || !size.width) return null
  const [x = 0, y = 0, width = 0, height = 0] = props.bbox
  return { left: `${x / size.width * 100}%`, top: `${y / size.height * 100}%`,
    width: `${width / size.width * 100}%`, height: `${height / size.height * 100}%` }
})
watch(() => props.sampleId, load, { immediate: true })
onUnmounted(() => { generation++; release() })
</script>
<template>
  <div v-loading="loading" class="sample-preview">
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-button v-if="error" :icon="Refresh" @click="load">重新加载</el-button>
    <div v-else-if="image" class="sample-image-frame" :style="frameStyle">
      <img :src="image" alt="样本原图" @load="loaded" @error="error = '图片无法显示'" />
      <span v-if="bboxStyle" class="sample-bbox" :style="bboxStyle" aria-label="目标标注框" />
    </div>
    <el-icon v-else class="sample-placeholder"><Picture /></el-icon>
    <span v-if="size.width" class="muted">{{ size.width }} × {{ size.height }} px</span>
  </div>
</template>

<style scoped>
.sample-preview { display: flex; flex-direction: column; align-items: center; gap: 12px; min-height: 120px; padding: 12px 0 22px; }
.sample-image-frame { position: relative; max-width: 100%; overflow: hidden; background: #f0f3f5; }
.sample-image-frame img { display: block; width: 100%; height: 100%; object-fit: contain; }
.sample-bbox { position: absolute; border: 2px solid #e44957; background: #e4495720; pointer-events: none; }
.sample-placeholder { font-size: 32px; color: #91a5a3; margin: 28px; }
</style>
