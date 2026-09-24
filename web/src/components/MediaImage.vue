<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { Picture } from '@element-plus/icons-vue'
import { tokenStore } from '../api'
const props = withDefaults(defineProps<{ src: string; fit?: 'contain' | 'cover'; preview?: boolean }>(), {
  fit: 'contain',
  preview: false,
})
const imageSrc = ref('')
const failed = ref(false)
let objectUrl: string | undefined
let request: AbortController | undefined
function cleanup() {
  request?.abort()
  if (objectUrl) URL.revokeObjectURL(objectUrl)
  objectUrl = undefined
}
watch(
  () => props.src,
  async (src) => {
    cleanup()
    failed.value = false
    imageSrc.value = ''
    if (!src) return
    if (!src.startsWith('/api/v1/media/') && !src.startsWith('/api/v1/admin/samples/')) {
      imageSrc.value = src
      return
    }
    request = new AbortController()
    const current = request
    try {
      const token = tokenStore.get()
      const response = await fetch(src, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: current.signal,
      })
      if (!response.ok) throw new Error('图片不可用')
      const blob = await response.blob()
      if (current.signal.aborted) return
      objectUrl = URL.createObjectURL(blob)
      imageSrc.value = objectUrl
    } catch {
      if (!current.signal.aborted) failed.value = true
    }
  },
  { immediate: true },
)
onUnmounted(cleanup)
</script>
<template>
  <el-image
    v-if="!failed"
    :src="imageSrc"
    :fit="fit"
    :preview-src-list="preview && imageSrc ? [imageSrc] : []"
    preview-teleported
  >
    <template #error>
      <span class="media-fallback" title="图片不可用">
        <el-icon><Picture /></el-icon>
      </span>
    </template>
  </el-image>
  <span v-else class="media-fallback" title="图片不可用">
    <el-icon><Picture /></el-icon>
  </span>
</template>
