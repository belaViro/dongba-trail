<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Row } from '../api'
import { validPoiCoordinates } from '../map-coordinates'

// GEO-01: Web Key is public in browser bundles. Restrict domains in the AMap console.
// A security JS code must never be placed in browser code or VITE_ variables.
let key = ''
let sdkKey = ''
let center: [number, number] = [100.235, 26.875]
let zoom = 12
const props = defineProps<{ points: Row[]; unavailable?: boolean }>()
const container = ref<HTMLElement | null>(null)
const mapError = ref('')
type Marker = { on: (event: string, handler: () => void) => void }
type MapInstance = {
  add: (pins: Marker[]) => void
  remove: (pins: Marker[]) => void
  setFitView: (pins: Marker[], immediately?: boolean, avoid?: number[], maxZoom?: number) => void
  setCenter: (point: number[]) => void
  on: (event: string, handler: () => void) => void
  destroy: () => void
}
type AMapAPI = {
  Map: new (container: HTMLElement, options: Record<string, unknown>) => MapInstance
  Marker: new (options: Record<string, unknown>) => Marker
  InfoWindow: new (options: Record<string, unknown>) => { open: (map: MapInstance, point: number[]) => void }
}
declare global {
  interface Window {
    AMap?: AMapAPI
  }
}
let map: MapInstance | undefined
let markers: Marker[] = []
let disposed = false
let ready = false
let timeout: ReturnType<typeof setTimeout> | undefined

function renderPoints() {
  if (!map || !window.AMap) return
  if (markers.length) map.remove(markers)
  markers = []
  for (const point of props.points) {
    if (!validPoiCoordinates(point)) continue
    // Backend and AMap both use GCJ-02; no WGS-84 conversion.
    const position = [Number(point.longitude), Number(point.latitude)]
    const pin = new window.AMap.Marker({ position, title: String(point.name || '文化地图点位') })
    pin.on('click', () => {
      // Never interpolate backend content into HTML.
      const popup = document.createElement('div')
      const name = document.createElement('strong')
      name.textContent = String(point.name || '文化地图点位')
      popup.append(name)
      if (String(point.id || '').startsWith('OPS_')) {
        const demo = document.createElement('p')
        demo.textContent = '运营演示点位（非实地核验）'
        popup.append(demo)
      }
      if (point.poi_type) {
        const category = document.createElement('p')
        category.textContent = String(point.poi_type)
        popup.append(category)
      }
      new window.AMap!.InfoWindow({ content: popup, offset: [0, -26] }).open(map!, position)
    })
    markers.push(pin)
  }
  if (markers.length) {
    map.add(markers)
    map.setFitView(markers, false, [36, 36, 36, 36], 15)
  } else map.setCenter(center)
}
async function loadMap() {
  try {
    const response = await fetch('/api/v1/public/map-config', { cache: 'no-store' })
    if (!response.ok) throw new Error('Map config unavailable')
    const config = await response.json()
    key = String(config.web_key || '').trim()
    center = [Number(config.center_longitude), Number(config.center_latitude)]
    zoom = Number(config.default_zoom)
  } catch {
    if (!disposed) mapError.value = 'Map configuration is unavailable.'
    return
  }
  if (disposed) return
  if (!container.value || !key) {
    mapError.value = '地图暂不可用，请稍后重试或联系管理员。'
    return
  }
  const initialize = () => {
    if (disposed || !container.value || !window.AMap) return
    sdkKey = key
    try {
      map = new window.AMap.Map(container.value, {
        zoom,
        center,
        viewMode: '2D',
        scrollWheel: false,
        resizeEnable: true,
      })
      map.on('complete', () => {
        ready = true
        if (timeout) clearTimeout(timeout)
        mapError.value = ''
      })
      map.on('error', () => {
        mapError.value = '高德地图底图不可用，请检查 Key、安全密钥及域名授权。'
      })
      renderPoints()
      timeout = setTimeout(() => {
        if (!disposed && !ready) mapError.value = '地图底图加载超时，请检查高德 Key、安全密钥及网络。'
      }, 12000)
    } catch {
      mapError.value = '地图加载失败，请稍后重试。'
    }
  }
  if (window.AMap) {
    if (sdkKey && sdkKey !== key) {
      // AMap's global SDK retains its boot-time key across SPA route changes.
      window.location.reload()
      return
    }
    initialize()
    return
  }
  const callback = `__dongba_amap_${Math.random().toString(36).slice(2)}`
  const globals = window as unknown as Record<string, unknown>
  globals[callback] = () => {
    delete globals[callback]
    initialize()
  }
  const script = document.createElement('script')
  script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(key)}&callback=${callback}`
  script.async = true
  script.onerror = () => {
    delete globals[callback]
    if (!disposed) mapError.value = '地图加载失败，请检查网络后重试。'
  }
  document.head.append(script)
  timeout = setTimeout(() => {
    if (!disposed && !map) mapError.value = '地图暂不可用，请稍后重试。'
  }, 12000)
}
onMounted(loadMap)
watch(() => props.points, renderPoints)
onBeforeUnmount(() => {
  disposed = true
  if (timeout) clearTimeout(timeout)
  map?.destroy()
  map = undefined
  markers = []
})
</script>

<template>
  <div class="poi-map">
    <div ref="container" class="poi-map-canvas" aria-label="丽江文化地图点位交互地图" role="region" />
    <div v-if="mapError" class="poi-map-message" role="status">{{ mapError }}</div>
    <div v-else-if="unavailable" class="poi-map-message" role="status">地点信息暂不可用，请稍后重试。</div>
    <div v-else-if="!points.some(validPoiCoordinates)" class="poi-map-message" role="status">
      暂无已发布的文化地图坐标点位
    </div>
    <div class="poi-map-caption">文化地图 · 演示点位不代表实地核验</div>
  </div>
</template>

<style scoped>
.poi-map {
  position: relative;
  flex: 1;
  min-height: 340px;
  width: 100%;
  background: #e8eee9;
  isolation: isolate;
}
.poi-map-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.poi-map-message {
  position: absolute;
  left: 50%;
  top: 45%;
  transform: translate(-50%, -50%);
  z-index: 2;
  padding: 10px 16px;
  border-radius: 8px;
  color: #324451;
  background: #fffffff0;
  box-shadow: 0 4px 18px #1b2a3822;
  text-align: center;
  max-width: 92%;
  font-size: 12px;
}
.poi-map-caption {
  position: absolute;
  bottom: 12px;
  left: 12px;
  z-index: 2;
  padding: 5px 8px;
  border-radius: 5px;
  background: #ffffffeb;
  color: #415367;
  font-size: 10px;
  max-width: 80%;
  pointer-events: none;
}
@media (max-width: 720px) {
  .poi-map {
    min-height: 290px;
  }
}
</style>
