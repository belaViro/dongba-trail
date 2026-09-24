<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, errorText, save } from '../api'
const weights = [
  { key: 'cultural_relevance', label: '文化相关性' },
  { key: 'distance_score', label: '距离' },
  { key: 'merchant_quality', label: '商户质量' },
  { key: 'coupon_activity', label: '优惠与活动' },
  { key: 'user_behavior_match', label: '行为匹配' },
  { key: 'operation_weight', label: '运营权重' },
]
const form = reactive<Record<string, number>>({})
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const loaded = ref(false)
const total = computed(
  () => Math.round(weights.reduce((sum, weight) => sum + (form[weight.key] || 0), 0) * 100) / 100,
)
async function load() {
  loading.value = true
  error.value = ''
  try {
    const values = await api('/admin/settings')
    for (const weight of weights) form[weight.key] = Number(values[weight.key]) * 100
    loaded.value = true
  } catch (e) {
    error.value = errorText(e)
  } finally {
    loading.value = false
  }
}
async function submit() {
  if (total.value !== 100) {
    error.value = '推荐权重合计必须为100%'
    return
  }
  saving.value = true
  error.value = ''
  try {
    await save(
      '/admin/settings',
      Object.fromEntries(weights.map((weight) => [weight.key, form[weight.key]! / 100])),
      'PATCH',
    )
    ElMessage.success('推荐配置已保存')
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
      <span class="eyebrow">运营配置</span>
      <h1>推荐配置</h1>
    </div>
  </div>
  <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="page-alert" />
  <section v-loading="loading" class="settings-section">
    <div class="section-heading">
      <h2>商户推荐权重</h2>
      <el-tag v-if="loaded" :type="total === 100 ? 'success' : 'danger'">合计 {{ total }}%</el-tag>
    </div>
    <el-form v-if="loaded" label-position="top">
      <div v-for="weight in weights" :key="weight.key" class="weight-row">
        <span>{{ weight.label }}</span>
        <el-slider v-model="form[weight.key]" :min="0" :max="100" :step="1" :aria-label="weight.label" />
        <el-input-number
          v-model="form[weight.key]"
          :min="0"
          :max="100"
          :precision="0"
          controls-position="right"
          :aria-label="weight.label + '百分比'"
        />
        <span>%</span>
      </div>
      <div class="form-footer">
        <el-button @click="load">重置</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存配置</el-button>
      </div>
    </el-form>
    <el-empty v-else-if="!loading" description="无法读取推荐配置">
      <el-button @click="load">重试</el-button>
    </el-empty>
  </section>
</template>
