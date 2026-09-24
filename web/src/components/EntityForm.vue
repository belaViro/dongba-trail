<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Delete, Plus, Upload } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules, type UploadRequestOptions } from 'element-plus'
import { api, errorText, type Collection, type Row } from '../api'
import type { Field } from '../resources'
import MediaImage from './MediaImage.vue'
const props = defineProps<{ modelValue: Row; fields: Field[]; editing?: boolean; merchant?: boolean }>()
const formRef = ref<FormInstance>()
const relations = reactive<Record<string, Row[]>>({})
const loading = reactive<Record<string, boolean>>({})
const lookupVersions: Record<string, number> = {}
const fields = computed(() =>
  props.fields.filter(
    (f) =>
      !(props.merchant && (['merchant_id', 'character_ids', 'tags'].includes(f.key) || f.operationsOnly)),
  ),
)
const rules = computed<FormRules>(() =>
  Object.fromEntries(
    fields.value
      .filter((f) => f.required || (f.key === 'password' && !props.editing))
      .map((f) => [
        f.key,
        [
          { required: true, message: `请填写${f.label}`, trigger: ['blur', 'change'] },
          ...(f.key === 'password' ? [{ min: 12, message: '密码至少12位', trigger: 'blur' }] : []),
        ],
      ]),
  ),
)
async function lookup(field: Field, search = '') {
  if (!field.resource) return
  const version = (lookupVersions[field.key] || 0) + 1
  lookupVersions[field.key] = version
  loading[field.key] = true
  try {
    const prefix = props.merchant ? '' : '/admin'
    const data = await api<Collection>(
      `${prefix}/${field.resource}?limit=100&q=${encodeURIComponent(search)}`,
    )
    if (lookupVersions[field.key] === version) relations[field.key] = data.items
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    if (lookupVersions[field.key] === version) loading[field.key] = false
  }
}
watch(
  fields,
  () => {
    for (const f of fields.value) if (f.type === 'relation') void lookup(f)
  },
  { immediate: true },
)
async function upload(field: Field, options: UploadRequestOptions, variant?: Row) {
  const data = new FormData()
  data.append('file', options.file)
  try {
    const result = await api<{ url: string }>('/media', { method: 'POST', body: data })
    if (variant) variant.image_url = result.url
    else props.modelValue[field.key] = result.url
    options.onSuccess(result)
  } catch (error) {
    ElMessage.error(errorText(error))
    options.onError(
      Object.assign(new Error(errorText(error)), { status: 0, method: 'POST', url: '/api/v1/media' }),
    )
  }
}
defineExpose({
  validate: () => formRef.value?.validate(),
  clearValidate: () => formRef.value?.clearValidate(),
})
</script>
<template>
  <el-form
    ref="formRef"
    :model="modelValue"
    :rules="rules"
    label-position="top"
    class="entity-form"
    @submit.prevent
  >
    <el-form-item
      v-for="field in fields"
      :key="field.key"
      :label="field.label"
      :prop="field.key"
      :class="{ 'form-wide': ['textarea', 'image', 'variants'].includes(field.type || '') }"
    >
      <el-input
        v-if="!field.type || ['text', 'password', 'textarea'].includes(field.type)"
        v-model="modelValue[field.key]"
        :type="field.type === 'textarea' ? 'textarea' : field.type === 'password' ? 'password' : 'text'"
        :rows="field.key === 'culture_detail' ? 5 : 3"
        :show-password="field.type === 'password'"
        :disabled="editing && field.key === 'id'"
        :autocomplete="field.type === 'password' ? 'new-password' : 'off'"
        :placeholder="field.key === 'password' && editing ? '留空保留现有密码' : ''"
        :maxlength="field.type === 'textarea' ? 12000 : 2000"
      />
      <el-input-number
        v-else-if="field.type === 'number' || field.type === 'money'"
        v-model="modelValue[field.key]"
        :min="field.min"
        :max="field.max"
        :precision="
          field.precision ??
          (field.type === 'money' ? 2 : ['latitude', 'longitude'].includes(field.key) ? 6 : 0)
        "
        :step="field.precision === 2 ? 0.05 : 1"
        controls-position="right"
      />
      <el-select
        v-else-if="field.type === 'select'"
        v-model="modelValue[field.key]"
        :aria-label="field.label"
      >
        <el-option
          v-for="option in field.options"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <el-select
        v-else-if="field.type === 'relation'"
        v-model="modelValue[field.key]"
        filterable
        remote
        clearable
        :multiple="field.multiple"
        :loading="loading[field.key]"
        :remote-method="(q: string) => lookup(field, q)"
        :aria-label="field.label"
      >
        <el-option
          v-for="item in relations[field.key] || []"
          :key="item.id"
          :label="item.cn_name || item.name || item.title || item.display_name || item.id"
          :value="item.id"
        />
      </el-select>
      <el-select
        v-else-if="field.type === 'tags'"
        v-model="modelValue[field.key]"
        multiple
        filterable
        allow-create
        default-first-option
        :aria-label="field.label"
      />
      <el-date-picker
        v-else-if="field.type === 'datetime'"
        v-model="modelValue[field.key]"
        type="datetime"
        value-format="YYYY-MM-DDTHH:mm:ssZ"
        format="YYYY-MM-DD HH:mm"
        :aria-label="field.label"
      />
      <div v-else-if="field.type === 'image'" class="media-field">
        <MediaImage
          v-if="modelValue[field.key]"
          :src="modelValue[field.key]"
          preview
          fit="cover"
          class="image-preview"
        />
        <el-input v-model="modelValue[field.key]" placeholder="图片地址" :aria-label="field.label" />
        <el-upload
          :show-file-list="false"
          accept="image/jpeg,image/png,image/webp"
          :http-request="(options: UploadRequestOptions) => upload(field, options)"
        >
          <el-button :icon="Upload">上传</el-button>
        </el-upload>
      </div>
      <div v-else-if="field.type === 'variants'" class="variants-field">
        <div v-for="(variant, index) in modelValue[field.key]" :key="index" class="variant-row">
          <MediaImage v-if="variant.image_url" :src="variant.image_url" fit="contain" class="variant-image" />
          <el-input v-model="variant.image_url" placeholder="字形图片地址" aria-label="异形图片地址" />
          <el-input v-model="variant.source_ref" placeholder="来源" aria-label="异形来源" />
          <el-upload
            :show-file-list="false"
            accept="image/jpeg,image/png,image/webp"
            :http-request="(options: UploadRequestOptions) => upload(field, options, variant)"
          >
            <el-button :icon="Upload" aria-label="上传异形图片" />
          </el-upload>
          <el-button :icon="Delete" aria-label="删除异形" @click="modelValue[field.key].splice(index, 1)" />
        </div>
        <el-button :icon="Plus" plain @click="modelValue[field.key].push({ image_url: '', source_ref: '' })">
          添加字形
        </el-button>
      </div>
    </el-form-item>
  </el-form>
</template>
