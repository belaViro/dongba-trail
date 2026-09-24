<script setup lang="ts">
import { ref } from 'vue'
import { Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { errorText, save } from '../api'
const props = defineProps<{ resource: string; search?: string; status?: string }>()
const busy = ref(false)
async function exportRecords() {
  busy.value = true
  try {
    const result = await save<{
      filename: string
      content_type: string
      content: string
      row_count: number
      truncated: boolean
    }>(`/admin/exports/${props.resource}`, {
      q: props.search || '',
      status: props.status || null,
      limit: 10000,
    })
    const url = URL.createObjectURL(
      new Blob([result.content.startsWith('\uFEFF') ? result.content : '\uFEFF' + result.content], {
        type: result.content_type,
      }),
    )
    const link = document.createElement('a')
    link.href = url
    link.download = result.filename
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    if (result.truncated) ElMessage.warning(`已导出${result.row_count}条，结果达到导出上限，请缩小筛选范围`)
    else ElMessage.success(`已导出${result.row_count}条记录`)
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    busy.value = false
  }
}
</script>
<template><el-button :icon="Download" :loading="busy" @click="exportRecords">导出记录</el-button></template>
