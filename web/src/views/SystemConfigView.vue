<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, errorText, save } from '../api'

type Config = {
  provider_name: string
  provider_endpoint: string
  provider_model: string
  provider_timeout_seconds: number
  provider_api_key_configured: boolean
  key_editable: boolean
  map_web_key: string
  map_center_longitude: number
  map_center_latitude: number
  map_default_zoom: number
}
const form = reactive({
  provider_name: 'unconfigured',
  provider_endpoint: '',
  provider_model: '',
  provider_timeout_seconds: 15,
  provider_api_key: '',
  clear_provider_api_key: false,
  map_web_key: '',
  map_center_longitude: 100.235,
  map_center_latitude: 26.875,
  map_default_zoom: 12,
})
const configured = ref(false)
const keyEditable = ref(false)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const loaded = ref(false)
function assign(value: Config) {
  form.provider_name = value.provider_name
  form.provider_endpoint = value.provider_endpoint
  form.provider_model = value.provider_model
  form.provider_timeout_seconds = value.provider_timeout_seconds
  form.map_web_key = value.map_web_key
  form.map_center_longitude = value.map_center_longitude
  form.map_center_latitude = value.map_center_latitude
  form.map_default_zoom = value.map_default_zoom
  form.provider_api_key = ''
  form.clear_provider_api_key = false
  configured.value = value.provider_api_key_configured
  keyEditable.value = value.key_editable
  loaded.value = true
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    assign(await api<Config>('/admin/system-config'))
  } catch (cause) {
    error.value = errorText(cause)
  } finally {
    loading.value = false
  }
}
async function submit() {
  saving.value = true
  error.value = ''
  try {
    assign(await save<Config>('/admin/system-config', { ...form }, 'PUT'))
    ElMessage.success('系统配置已保存，新请求立即生效；已打开的地图页面请刷新')
  } catch (cause) {
    error.value = errorText(cause)
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>

<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">AI 与系统</span>
      <h1>系统配置</h1>
    </div>
  </div>
  <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="page-alert" />
  <section v-loading="loading" class="settings-section">
    <el-form v-if="loaded" label-position="top" class="system-form">
      <div class="section-heading"><h2>视觉识别模型</h2></div>
      <el-form-item label="提供方">
        <el-select v-model="form.provider_name" aria-label="模型提供方">
          <el-option label="未启用" value="unconfigured" />
          <el-option label="火山引擎 Ark（OpenAI 兼容视觉接口）" value="volcengine-ark" />
        </el-select>
      </el-form-item>
      <el-form-item label="接口地址（HTTPS Base URL 或完整 Chat Completions 地址）">
        <el-input
          v-model="form.provider_endpoint"
          placeholder="https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        />
      </el-form-item>
      <el-form-item label="模型 ID"><el-input v-model="form.provider_model" /></el-form-item>
      <el-form-item label="请求超时（秒）">
        <el-input-number v-model="form.provider_timeout_seconds" :min="1" :max="60" :precision="1" />
      </el-form-item>
      <el-form-item label="API Key（不回显；留空表示不更改）">
        <el-input
          v-model="form.provider_api_key"
          type="password"
          show-password
          autocomplete="new-password"
          :disabled="!keyEditable || form.clear_provider_api_key"
          placeholder="输入新密钥以替换现有密钥"
        />
        <small>
          状态：{{ configured ? '已配置' : '未配置' }}。{{
            keyEditable ? '密钥加密保存在服务端。' : '服务器尚未设置加密主密钥，暂不能通过页面更换 API Key。'
          }}
        </small>
      </el-form-item>
      <el-checkbox v-model="form.clear_provider_api_key" :disabled="!!form.provider_api_key">
        清除现有模型 API Key（包括环境变量回退）
      </el-checkbox>
      <div class="section-heading"><h2>文化地图</h2></div>
      <el-form-item label="高德 JS API Web Key（浏览器公开信息）">
        <el-input v-model="form.map_web_key" placeholder="高德控制台的 Web 端 Key" />
        <small>
          新打开或刷新地图页面即生效；请在高德控制台限制授权域名。这里不填写安全密钥 / 服务端私钥。
        </small>
      </el-form-item>
      <el-form-item label="无点位时的地图中心与默认缩放">
        <div class="map-position">
          <span>经度</span>
          <el-input-number
            v-model="form.map_center_longitude"
            :min="73"
            :max="135"
            :precision="4"
            :step="0.01"
          />
          <span>纬度</span>
          <el-input-number
            v-model="form.map_center_latitude"
            :min="3"
            :max="54"
            :precision="4"
            :step="0.01"
          />
          <span>缩放</span>
          <el-input-number v-model="form.map_default_zoom" :min="3" :max="18" />
        </div>
        <small>坐标系为 GCJ-02；存在已发布点位时，地图自动适应实际点位范围。</small>
      </el-form-item>
      <div class="form-footer">
        <el-button @click="load">撤销修改</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存并生效</el-button>
      </div>
    </el-form>
    <el-empty v-else-if="!loading" description="无法读取系统配置">
      <el-button @click="load">重试</el-button>
    </el-empty>
  </section>
</template>

<style scoped>
.system-form {
  max-width: 720px;
}
.system-form .el-select {
  width: 100%;
}
.system-form small {
  display: block;
  color: #64748b;
  line-height: 1.6;
}
.system-form .section-heading:not(:first-child) {
  margin-top: 30px;
}
.map-position {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
