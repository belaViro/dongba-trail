<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ApiError, api, errorText, save } from '../api'
import {
  providerLabel,
  recognitionStatus,
  serviceStatusLabel,
  serviceStatusType,
  type ServiceStatus,
} from '../recognition-status'

// OPS-03 / SHARE-01: independent poster provider settings.
type ImageSettings = {
  image_provider_name: 'unconfigured' | 'openai-compatible'
  image_provider_endpoint: string
  image_provider_model: string
  image_provider_timeout_seconds: number
  image_provider_size: '1024x1536' | '1024x1024' | '1536x1024' | 'auto'
  image_provider_quality: 'auto' | 'low' | 'medium' | 'high' | 'standard' | 'hd'
}
type Config = {
  provider_name: string
  provider_endpoint: string
  provider_model: string
  provider_timeout_seconds: number
  provider_api_key_configured: boolean
  key_editable: boolean
  local_model_version?: string
  local_model_threads?: number
  recognition_service?: ServiceStatus
  map_web_key: string
  map_center_longitude: number
  map_center_latitude: number
  map_default_zoom: number
  image_provider_api_key_configured?: boolean
} & Partial<ImageSettings>
const imageDefaults: ImageSettings = {
  image_provider_name: 'unconfigured',
  image_provider_endpoint: '',
  image_provider_model: '',
  image_provider_timeout_seconds: 180,
  image_provider_size: '1024x1536',
  image_provider_quality: 'auto',
}
const imageErrorMessages: Record<string, string> = {
  IMAGE_PROVIDER_KEY_REQUIRED:
    '接口地址已更改，请输入该地址对应的新 API Key 后重试；为保护密钥，不会向不同地址转发已保存的密钥。',
  IMAGE_PROVIDER_UNCONFIGURED: '旅游海报 AI 尚未配置完整，请检查提供方、接口地址和 API Key。',
  IMAGE_PROVIDER_AUTH_FAILED: '旅游海报 API Key 验证失败，请检查密钥是否有效及是否有访问所选服务的权限。',
  IMAGE_PROVIDER_TIMEOUT: '读取模型超时，请稍后重试，或手动填写提供方支持的图像模型 ID。',
  IMAGE_PROVIDER_BUSY: '旅游海报服务繁忙或请求过于频繁，请稍后重试。',
}
function configErrorText(cause: unknown): string {
  if (!(cause instanceof ApiError)) return '操作失败，请重试'
  // Use a structured code when available, otherwise retain the shared API's safe mapping.
  const code = (cause as ApiError & { code?: string }).code ?? cause.message
  if (!Object.prototype.hasOwnProperty.call(imageErrorMessages, code)) return errorText(cause)
  const requestId =
    cause.requestId && /^[a-zA-Z0-9_-]{1,80}$/.test(cause.requestId) ? cause.requestId : undefined
  return errorText(new ApiError(imageErrorMessages[code]!, cause.status, requestId))
}
const form = reactive({
  provider_name: 'unconfigured',
  provider_endpoint: '',
  provider_model: '',
  provider_timeout_seconds: 15,
  provider_api_key: '',
  clear_provider_api_key: false,
  ...imageDefaults,
  image_provider_api_key: '',
  clear_image_provider_api_key: false,
  map_web_key: '',
  map_center_longitude: 100.235,
  map_center_latitude: 26.875,
  map_default_zoom: 12,
})
const configured = ref(false)
const imageConfigured = ref(false)
const keyEditable = ref(false)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const loaded = ref(false)
const activeSection = ref<'recognition' | 'poster' | 'map'>('recognition')
const savedService = ref<ServiceStatus | null>(null)
const savedProvider = ref('unconfigured')
const localModelVersion = ref('')
const localModelThreads = ref<number | null>(null)
const selectionChanged = computed(() => form.provider_name !== savedProvider.value)
// OPS-03 / AI-01: cancel hidden key edits, never the saved key or other fields.
watch(
  () => form.provider_name,
  (name) => {
    if (name !== 'volcengine-ark') {
      form.provider_api_key = ''
      form.clear_provider_api_key = false
    }
  },
  { flush: 'sync' },
)
const imageModels = ref<string[]>([])
const imageModelsLoading = ref(false)
const imageModelsLoaded = ref(false)
const imageModelsError = ref('')
let imageModelsRequest = 0
function resetImageModels() {
  imageModelsRequest++
  imageModels.value = []
  imageModelsError.value = ''
  imageModelsLoaded.value = false
  imageModelsLoading.value = false
}
watch(
  () => [
    form.image_provider_name,
    form.image_provider_endpoint,
    form.image_provider_api_key,
    form.clear_image_provider_api_key,
  ],
  resetImageModels,
  { flush: 'sync' },
)
function assign(value: Config) {
  savedProvider.value = value.provider_name
  localModelVersion.value = value.local_model_version ?? ''
  localModelThreads.value = value.local_model_threads ?? null
  savedService.value = recognitionStatus(
    value.recognition_service ?? {
      name: value.provider_name,
      kind: value.provider_name === 'db1404-local' ? 'local' : undefined,
      model: value.provider_name === 'db1404-local' ? value.local_model_version : value.provider_model,
      configured:
        value.provider_name === 'volcengine-ark' &&
        !!value.provider_endpoint &&
        !!value.provider_model &&
        value.provider_api_key_configured,
      endpoint_configured: !!value.provider_endpoint,
      timeout_seconds: value.provider_timeout_seconds,
      cpu_threads: value.local_model_threads,
    },
  )
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
  form.image_provider_name = value.image_provider_name ?? imageDefaults.image_provider_name
  form.image_provider_endpoint = value.image_provider_endpoint ?? imageDefaults.image_provider_endpoint
  form.image_provider_model = value.image_provider_model ?? imageDefaults.image_provider_model
  form.image_provider_timeout_seconds =
    value.image_provider_timeout_seconds ?? imageDefaults.image_provider_timeout_seconds
  form.image_provider_size = value.image_provider_size ?? imageDefaults.image_provider_size
  form.image_provider_quality = value.image_provider_quality ?? imageDefaults.image_provider_quality
  form.image_provider_api_key = ''
  form.clear_image_provider_api_key = false
  configured.value = value.provider_api_key_configured
  imageConfigured.value = value.image_provider_api_key_configured ?? false
  keyEditable.value = value.key_editable
  resetImageModels()
  loaded.value = true
}
async function loadImageModels() {
  if (
    imageModelsLoading.value ||
    loading.value ||
    saving.value ||
    form.image_provider_name !== 'openai-compatible'
  )
    return
  resetImageModels()
  if (!form.image_provider_endpoint.trim()) {
    imageModelsError.value = '请先填写旅游海报接口地址'
    return
  }
  const request = imageModelsRequest
  imageModelsLoading.value = true
  try {
    const result = await save<{ items: { id: string }[] }>('/admin/system-config/image-models', {
      endpoint: form.image_provider_endpoint,
      ...(form.image_provider_api_key ? { api_key: form.image_provider_api_key } : {}),
      ...(form.clear_image_provider_api_key ? { clear_api_key: true } : {}),
    })
    if (request !== imageModelsRequest) return
    if (
      !Array.isArray(result.items) ||
      result.items.some((item) => !item || typeof item.id !== 'string' || !item.id.trim())
    )
      throw new Error('Invalid model list')
    imageModels.value = [...new Set(result.items.map((item) => item.id))]
    imageModelsLoaded.value = true
  } catch (cause) {
    if (request !== imageModelsRequest) return
    imageModelsError.value =
      `读取可用模型失败：${cause instanceof ApiError ? configErrorText(cause) : '请检查接口地址和 API Key 后重试'}。` +
      '也可手动填写模型 ID。'
  } finally {
    if (request === imageModelsRequest) imageModelsLoading.value = false
  }
}
async function load() {
  resetImageModels()
  loading.value = true
  error.value = ''
  try {
    assign(await api<Config>('/admin/system-config'))
  } catch (cause) {
    error.value = configErrorText(cause)
  } finally {
    loading.value = false
  }
}
async function submit() {
  if (saving.value || loading.value) return
  resetImageModels()
  saving.value = true
  error.value = ''
  try {
    assign(
      await save<Config>(
        '/admin/system-config',
        {
          ...form,
          provider_api_key: form.provider_name === 'volcengine-ark' ? form.provider_api_key : '',
          clear_provider_api_key: form.provider_name === 'volcengine-ark' && form.clear_provider_api_key,
        },
        'PUT',
      ),
    )
    ElMessage.success('系统配置已保存，新请求立即生效；已打开的地图页面请刷新')
  } catch (cause) {
    error.value = configErrorText(cause)
  } finally {
    saving.value = false
  }
}
onMounted(load)
onBeforeUnmount(resetImageModels)
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
      <el-radio-group v-model="activeSection" aria-label="配置分类" class="section-switcher">
        <el-radio-button value="recognition">视觉识别</el-radio-button>
        <el-radio-button value="poster">旅游海报</el-radio-button>
        <el-radio-button value="map">文化地图</el-radio-button>
      </el-radio-group>
      <div class="config-panel recognition-panel" :class="{ 'is-active': activeSection === 'recognition' }">
        <div class="section-heading"><h2>视觉识别模型</h2></div>
        <div v-if="savedService" class="service-snapshot" aria-label="当前已保存服务快照">
          <div class="snapshot-heading">
            <h3>当前生效</h3>
            <el-tag :type="serviceStatusType(savedService.status)">
              {{ serviceStatusLabel(savedService.status) }}
            </el-tag>
            <span>{{ savedService.status_message }}</span>
          </div>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="当前提供方">
              {{ providerLabel(savedService.name) }}
            </el-descriptions-item>
            <el-descriptions-item v-if="savedService.kind !== 'unconfigured'" label="当前模型版本">
              {{ savedService.model || '暂未提供' }}
            </el-descriptions-item>
            <el-descriptions-item v-if="savedService.kind === 'local'" label="当前 CPU 线程数">
              {{ savedService.cpu_threads ?? '暂未提供' }}
            </el-descriptions-item>
            <el-descriptions-item v-if="savedService.kind !== 'unconfigured'" label="当前识别超时">
              {{ savedService.timeout_seconds === null ? '暂未提供' : `${savedService.timeout_seconds} 秒` }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
        <p v-if="selectionChanged" role="status" class="selection-notice">
          未保存选择：{{ providerLabel(form.provider_name) }}。保存成功后才会切换；上方仍为已保存服务快照。
        </p>
        <el-form-item label="提供方">
          <el-radio-group v-model="form.provider_name" aria-label="模型提供方" class="provider-switcher">
            <el-radio-button value="unconfigured">未启用</el-radio-button>
            <el-radio-button value="db1404-local">本地 DB1404（CPU）</el-radio-button>
            <el-radio-button value="volcengine-ark">火山引擎 Ark</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <template v-if="form.provider_name === 'db1404-local'">
          <div class="local-preview">
            <el-form-item label="本地模型版本（只读）">
              <span>{{ localModelVersion || '暂未提供' }}</span>
            </el-form-item>
            <el-form-item label="本地 CPU 线程数（只读）">
              <span>{{ localModelThreads ?? '暂未提供' }}</span>
            </el-form-item>
          </div>
          <small>以上为服务器本地配置，仅供选择预览；不代表本地模型已经加载成功。</small>
        </template>
        <small v-if="form.provider_name !== 'volcengine-ark'">
          Ark 备用地址、模型及已有 API Key 保留，不用于当前识别；切换离开 Ark
          会取消未提交的新密钥和清除动作，不会清除已有密钥。
        </small>
        <template v-if="form.provider_name === 'volcengine-ark'">
          <el-form-item label="接口地址（HTTPS Base URL 或完整 Chat Completions 地址）">
            <el-input
              v-model="form.provider_endpoint"
              aria-label="Ark 接口地址"
              placeholder="https://ark.cn-beijing.volces.com/api/v3/chat/completions"
            />
          </el-form-item>
          <el-form-item label="模型 ID">
            <el-input v-model="form.provider_model" aria-label="Ark 模型 ID" />
          </el-form-item>
          <el-form-item label="API Key（不回显；留空表示不更改）">
            <el-input
              v-model="form.provider_api_key"
              aria-label="Ark API Key"
              type="password"
              show-password
              autocomplete="new-password"
              :disabled="!keyEditable || form.clear_provider_api_key"
              placeholder="输入新密钥以替换现有密钥"
            />
            <small>
              状态：{{ configured ? '已配置' : '未配置' }}。{{
                keyEditable
                  ? '密钥加密保存在服务端。'
                  : '服务器尚未设置加密主密钥，暂不能通过页面更换 API Key。'
              }}
            </small>
          </el-form-item>
          <el-checkbox
            v-model="form.clear_provider_api_key"
            aria-label="清除 Ark API Key"
            :disabled="!!form.provider_api_key"
          >
            清除现有模型 API Key（包括环境变量回退）
          </el-checkbox>
        </template>
        <el-form-item
          v-if="['db1404-local', 'volcengine-ark'].includes(form.provider_name)"
          label="请求超时（秒）"
        >
          <el-input-number
            v-model="form.provider_timeout_seconds"
            aria-label="共用识别超时"
            :min="1"
            :max="60"
            :precision="1"
          />
          <small>本地推理与 Ark 共用此识别超时；切换提供方不会重置。</small>
        </el-form-item>
        <small>
          加载或配置状态不代表准确率或外部服务连通性；候选分数未校准，不代表准确率，仍需用户确认。
          系统不会自动切换或付费调用 Ark，只有手动选择并保存后才启用。
        </small>
      </div>
      <div class="config-panel" :class="{ 'is-active': activeSection === 'poster' }">
        <div class="section-heading"><h2>旅游海报 AI</h2></div>
        <small>独立于视觉识别模型；未启用或缺少必要配置时，旅游海报 AI 不可用。</small>
        <el-form-item label="海报提供方">
          <el-select v-model="form.image_provider_name" aria-label="旅游海报提供方">
            <el-option label="未启用" value="unconfigured" />
            <el-option label="OpenAI 兼容图像接口" value="openai-compatible" />
          </el-select>
        </el-form-item>
        <el-form-item label="海报接口地址（公开 HTTPS Base URL 或完整 Images 地址）">
          <el-input
            v-model="form.image_provider_endpoint"
            aria-label="旅游海报接口地址"
            placeholder="https://api.example.com/v1"
          />
          <small>海报采用参考图与字形素材生成完整设计，提供方和模型须支持多图 Images Edits。</small>
          <small>
            可填写 Base URL、/images/edits 或旧 /images/generations 地址；制作时使用对应的 /images/edits。
          </small>
          <small>
            更换接口地址后读取模型，请输入该地址对应的新 API Key；不会向不同地址转发已保存的密钥。
          </small>
        </el-form-item>
        <el-form-item label="海报 API Key（不回显；留空表示不更改）">
          <el-input
            v-model="form.image_provider_api_key"
            aria-label="旅游海报 API Key"
            type="password"
            autocomplete="new-password"
            :disabled="!keyEditable || form.clear_image_provider_api_key"
            placeholder="输入新密钥以替换现有密钥"
          />
          <small>
            状态：{{ imageConfigured ? '已配置' : '未配置' }}。{{
              keyEditable
                ? '密钥加密保存在服务端。'
                : '服务器尚未设置加密主密钥，暂不能通过页面更换 API Key。'
            }}
          </small>
        </el-form-item>
        <el-checkbox
          v-model="form.clear_image_provider_api_key"
          aria-label="清除海报 API Key"
          :disabled="!!form.image_provider_api_key"
        >
          清除现有海报 API Key（包括环境变量回退）
        </el-checkbox>
        <el-form-item label="海报模型 ID">
          <el-select
            v-model="form.image_provider_model"
            aria-label="旅游海报模型 ID"
            filterable
            allow-create
            default-first-option
            clearable
            :reserve-keyword="false"
            placeholder="输入模型 ID，或读取可用模型后选择"
          >
            <el-option v-for="id in imageModels" :key="id" :label="id" :value="id" />
          </el-select>
          <small>请填写支持多张参考图片的图像编辑模型 ID；模型列表不代表已验证图片编辑能力。</small>
        </el-form-item>
        <el-button
          :loading="imageModelsLoading"
          :disabled="
            loading ||
            saving ||
            form.image_provider_name !== 'openai-compatible' ||
            !form.image_provider_endpoint.trim()
          "
          @click="loadImageModels"
        >
          读取可用模型
        </el-button>
        <small>
          仅查询模型，不生成图片或保存配置。地址未变且密钥留空时使用已保存密钥；勾选清除时不使用旧密钥。
          新密钥可在保存前用于查询。
        </small>
        <el-alert
          v-if="imageModelsError"
          :title="imageModelsError"
          type="error"
          :closable="false"
          show-icon
          class="page-alert"
        />
        <small v-else-if="imageModelsLoaded">
          {{
            imageModels.length
              ? `已读取 ${imageModels.length} 个模型，请选择图像模型。`
              : '未返回可用模型，可手动填写模型 ID。'
          }}
        </small>
        <el-form-item label="海报请求超时（秒）">
          <el-input-number
            v-model="form.image_provider_timeout_seconds"
            aria-label="旅游海报请求超时"
            :min="10"
            :max="240"
            :precision="0"
          />
        </el-form-item>
        <el-form-item label="海报尺寸">
          <el-select v-model="form.image_provider_size" aria-label="旅游海报尺寸">
            <el-option label="竖版 1024 × 1536" value="1024x1536" />
            <el-option label="方形 1024 × 1024" value="1024x1024" />
            <el-option label="横版 1536 × 1024" value="1536x1024" />
            <el-option label="自动" value="auto" />
          </el-select>
        </el-form-item>
        <el-form-item label="海报质量">
          <el-select v-model="form.image_provider_quality" aria-label="旅游海报质量">
            <el-option label="自动（auto）" value="auto" />
            <el-option label="低（low）" value="low" />
            <el-option label="中（medium）" value="medium" />
            <el-option label="高（high）" value="high" />
            <el-option label="标准（standard）" value="standard" />
            <el-option label="高清（hd）" value="hd" />
          </el-select>
          <small>尺寸与质量的支持范围以所选提供方和模型为准。</small>
        </el-form-item>
      </div>
      <div class="config-panel" :class="{ 'is-active': activeSection === 'map' }">
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
      </div>
      <div class="form-footer">
        <el-button :disabled="saving || loading" @click="load">撤销修改</el-button>
        <el-button type="primary" :loading="saving" :disabled="loading" @click="submit">保存并生效</el-button>
      </div>
    </el-form>
    <el-empty v-else-if="!loading" description="无法读取系统配置">
      <el-button @click="load">重试</el-button>
    </el-empty>
  </section>
</template>

<style scoped>
.system-form {
  max-width: 760px;
}
.section-switcher {
  display: flex;
  margin-bottom: 20px;
}
.section-switcher :deep(.el-radio-button) {
  flex: 1;
}
.section-switcher :deep(.el-radio-button__inner) {
  width: 100%;
}
.config-panel {
  display: none;
  min-height: 220px;
}
.config-panel.is-active {
  display: block;
}
.service-snapshot {
  margin-bottom: 14px;
}
.snapshot-heading {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.snapshot-heading h3 {
  margin: 0;
  font-size: 14px;
}
.snapshot-heading span:last-child {
  color: #64748b;
  font-size: 13px;
}
.provider-switcher {
  display: flex;
  flex-wrap: wrap;
}
.local-preview {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(140px, 1fr);
  gap: 12px;
}
.local-preview .el-form-item {
  margin-bottom: 8px;
}
.selection-notice {
  color: #9a6700;
  line-height: 1.6;
}
.system-form .el-select {
  width: 100%;
}
.system-form small {
  display: block;
  color: #64748b;
  line-height: 1.6;
}
.config-panel .section-heading {
  margin-bottom: 16px;
}
.map-position {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
@media (max-width: 640px) {
  .local-preview {
    grid-template-columns: 1fr;
  }
  .snapshot-heading {
    align-items: flex-start;
    flex-wrap: wrap;
  }
}
</style>
