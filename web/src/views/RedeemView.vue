<script setup lang="ts">
import { nextTick, onUnmounted, reactive, ref } from 'vue'
import { Check, Camera } from '@element-plus/icons-vue'
import { dateText, errorText, save, type Row } from '../api'
const form = reactive({ code: '' })
const busy = ref(false)
const error = ref('')
const result = ref<Row | null>(null)
const scanning = ref(false)
const scannerError = ref('')
const video = ref<HTMLVideoElement>()
let stream: MediaStream | undefined
let scannerFrame: number | undefined
async function submit() {
  if (!form.code.trim()) {
    error.value = '请输入核销码'
    return
  }
  busy.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await save('/coupons/verify', { code: form.code.trim() })
    form.code = ''
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = false
  }
}
function releaseCamera() {
  stream?.getTracks().forEach((track) => track.stop())
  stream = undefined
  if (scannerFrame) cancelAnimationFrame(scannerFrame)
}
function stopScan() {
  releaseCamera()
  scanning.value = false
}
async function startScan() {
  scannerError.value = ''
  scanning.value = true
  try {
    const Scanner = (
      window as unknown as {
        BarcodeDetector?: new (options: { formats: string[] }) => {
          detect: (video: HTMLVideoElement) => Promise<{ rawValue: string }[]>
        }
      }
    ).BarcodeDetector
    if (!Scanner) throw new Error('当前浏览器暂不支持扫码，请输入核销码')
    const detector = new Scanner({ formats: ['qr_code'] })
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
    await nextTick()
    if (!scanning.value || !video.value) {
      stopScan()
      return
    }
    video.value.srcObject = stream
    await video.value.play()
    const scan = async () => {
      if (!scanning.value || !video.value) return
      try {
        const codes = await detector.detect(video.value)
        if (codes[0]?.rawValue) {
          form.code = codes[0].rawValue
          stopScan()
          return
        }
        scannerFrame = requestAnimationFrame(scan)
      } catch {
        scannerError.value = '无法读取二维码，请输入核销码'
        releaseCamera()
      }
    }
    void scan()
  } catch (e) {
    scannerError.value = errorText(e)
    releaseCamera()
  }
}
onUnmounted(stopScan)
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">经营管理</span>
      <h1>到店核销</h1>
    </div>
    <router-link to="/merchant/redemptions"><el-button>核销记录</el-button></router-link>
  </div>
  <section class="redeem-section">
    <div class="section-heading"><h2>优惠券核销</h2></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="form-alert" />
    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="核销码">
        <el-input
          v-model="form.code"
          size="large"
          clearable
          placeholder="请输入游客出示的核销码"
          autocomplete="off"
          maxlength="200"
        />
      </el-form-item>
      <div class="redeem-actions">
        <el-button type="primary" native-type="submit" :icon="Check" :loading="busy" size="large">
          确认核销
        </el-button>
        <el-button :icon="Camera" size="large" @click="startScan">扫码</el-button>
      </div>
    </el-form>
    <div v-if="result" class="redemption-result">
      <el-result
        icon="success"
        :title="result.already_redeemed || result.already_verified ? '该券已核销' : '核销成功'"
      />
      <el-descriptions :column="1" border>
        <el-descriptions-item label="优惠券">
          {{ result.title || result.coupon?.title || result.coupon_id || result.claim?.coupon_id || '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="核销时间">
          {{ dateText(result.verified_at || result.redeemed_at || result.claim?.redeemed_at) }}
        </el-descriptions-item>
        <el-descriptions-item v-if="result.code || result.claim?.code" label="核销码">
          {{ result.code || result.claim?.code }}
        </el-descriptions-item>
      </el-descriptions>
    </div>
  </section>
  <el-dialog v-model="scanning" title="扫描核销码" width="min(500px, 94vw)" @closed="stopScan">
    <el-alert v-if="scannerError" :title="scannerError" type="warning" :closable="false" show-icon />
    <video v-show="!scannerError" ref="video" class="scanner-video" autoplay playsinline muted />
    <template #footer><el-button @click="stopScan">关闭</el-button></template>
  </el-dialog>
</template>
