<script setup lang="ts">
import { computed } from 'vue'
import { statusLabels } from '../resources'
const props = defineProps<{ value?: string }>()
const type = computed(() =>
  ['published', 'approved', 'indexed', 'active', 'success', 'used', 'redeemed'].includes(props.value || '')
    ? 'success'
    : ['disabled', 'deprecated', 'rejected', 'failed', 'expired'].includes(props.value || '')
      ? 'danger'
      : ['pending', 'draft', 'needs_confirmation'].includes(props.value || '')
        ? 'warning'
        : 'info',
)
</script>
<template>
  <el-tag :type="type" effect="light" size="small">{{ statusLabels[value || ''] || value || '—' }}</el-tag>
</template>
