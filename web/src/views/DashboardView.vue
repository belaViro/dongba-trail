<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  ArrowRight,
  Collection,
  Compass,
  Document,
  Location,
  Refresh,
  Shop,
  Tickets,
  TrendCharts,
  User,
} from '@element-plus/icons-vue'
import { api, dateText, errorText, type Collection as CollectionData, type Row } from '../api'
import MediaImage from '../components/MediaImage.vue'
import PoiMap from '../components/PoiMap.vue'
import { session } from '../session'

const merchant = computed(() => session.user?.role === 'merchant')
const prefix = computed(() => (merchant.value ? '/merchant' : '/admin'))
const stats = ref<Row | null>(null)
const provider = ref<Row | null>(null)
const profile = ref<Row | null>(null)
const error = ref('')
const loading = ref(false)
const updated = ref('')
const period = ref(merchant.value ? 30 : 7)
const reviewCounts = ref<{ label: string; count: number | null; path: string }[]>([])
const locationRows = ref<Row[]>([])
const pointsUnavailable = ref(false)
const featureRows = ref<Row[]>([])

const metrics = computed(() =>
  merchant.value
    ? [
        { key: 'merchant_impressions', label: '曝光次数', icon: TrendCharts, tone: 'cyan' },
        { key: 'merchant_views', label: '详情访问', icon: Document, tone: 'blue' },
        { key: 'navigations', label: '导航到店', icon: Compass, tone: 'indigo' },
        { key: 'coupon_claims', label: '领取优惠券', icon: Tickets, tone: 'amber' },
        { key: 'redemptions', label: '核销次数', icon: Collection, tone: 'red' },
      ]
    : [
        { key: 'users', label: '用户总数', icon: User, tone: 'blue' },
        { key: 'active_users_today', label: '今日活跃', icon: TrendCharts, tone: 'cyan' },
        { key: 'recognitions', label: '识别请求', icon: Collection, tone: 'indigo' },
        { key: 'merchant_views', label: '商户访问', icon: Shop, tone: 'red' },
        { key: 'coupon_claims', label: '优惠券领取', icon: Tickets, tone: 'amber' },
        { key: 'redemptions', label: '到店核销', icon: Compass, tone: 'green' },
      ],
)
const days = computed<Row[]>(() => stats.value?.daily || [])
const visibleDays = computed(() => {
  if (!days.value.length) return []
  const newest = new Date(String(days.value.at(-1)?.date))
  const start = new Date(newest)
  start.setDate(start.getDate() - period.value + 1)
  return days.value.filter((row) => new Date(String(row.date)) >= start)
})
const sources = computed<Row[]>(() => stats.value?.sources || [])
const sourceMax = computed(() => Math.max(1, ...sources.value.map((row) => Number(row.count || 0))))
const chartMax = computed(() =>
  Math.max(
    1,
    ...visibleDays.value.flatMap((row) => [
      Number(row.recognitions || 0),
      Number(row.coupon_claims || 0),
      Number(row.redemptions || 0),
    ]),
  ),
)
const chartSeries = computed(() =>
  merchant.value
    ? [
        { key: 'coupon_claims', label: '领券', color: '#16a36f' },
        { key: 'redemptions', label: '核销', color: '#df4a3c' },
      ]
    : [
        { key: 'recognitions', label: '识别请求', color: '#2878db' },
        { key: 'coupon_claims', label: '领券', color: '#16a36f' },
        { key: 'redemptions', label: '核销', color: '#df4a3c' },
      ],
)
const funnel = computed(() => [
  { label: '商户曝光', key: 'merchant_impressions' },
  { label: '详情访问', key: 'merchant_views' },
  { label: '发起导航', key: 'navigations' },
  { label: '领取优惠券', key: 'coupon_claims' },
  { label: '到店核销', key: 'redemptions' },
])
const funnelMax = computed(() =>
  Math.max(1, ...funnel.value.map((row) => Number(stats.value?.[row.key] || 0))),
)
const providerSuccess = computed(() => {
  if (!provider.value?.recent_requests) return null
  return Math.max(
    0,
    (1 - Number(provider.value.recent_errors || 0) / Number(provider.value.recent_requests)) * 100,
  )
})
function value(key: string) {
  return stats.value?.[key] === undefined || stats.value?.[key] === null
    ? '—'
    : Number(stats.value[key]).toLocaleString('zh-CN')
}
async function collection(path: string) {
  return api<CollectionData>(`${path}${path.includes('?') ? '&' : '?'}limit=8`)
}
async function load() {
  loading.value = true
  error.value = ''
  reviewCounts.value = []
  locationRows.value = []
  pointsUnavailable.value = false
  const baseRequests = [
    api<Row>(`${prefix.value}/stats`),
    ...(merchant.value ? [api<Row>('/merchant/profile')] : [api<Row>('/admin/provider')]),
  ]
  const baseResults = await Promise.allSettled(baseRequests)
  if (baseResults[0]?.status === 'fulfilled') {
    stats.value = baseResults[0].value
    updated.value = new Date().toISOString()
  } else if (baseResults[0]?.status === 'rejected') error.value = errorText(baseResults[0].reason)
  if (baseResults[1]?.status === 'fulfilled') {
    if (merchant.value) profile.value = baseResults[1].value
    else provider.value = baseResults[1].value
  }
  if (merchant.value) {
    const results = await Promise.allSettled([
      collection('/merchant/products'),
      collection('/merchant/coupons'),
      collection('/merchant/redemptions'),
    ])
    featureRows.value = results[0]?.status === 'fulfilled' ? results[0].value.items : []
    reviewCounts.value = [
      {
        label: '当前商品',
        count: results[0]?.status === 'fulfilled' ? results[0].value.total : null,
        path: '/merchant/products',
      },
      {
        label: '有效优惠券',
        count: results[1]?.status === 'fulfilled' ? results[1].value.total : null,
        path: '/merchant/coupons',
      },
      {
        label: '核销记录',
        count: results[2]?.status === 'fulfilled' ? results[2].value.total : null,
        path: '/merchant/redemptions',
      },
    ]
  } else {
    const reviews = [
      { label: '字典草稿', resource: 'characters', status: 'draft' },
      { label: '商户草稿', resource: 'merchants', status: 'draft' },
      { label: '文化标签申请', resource: 'tag-claims', status: 'pending' },
      { label: '识别纠错', resource: 'feedback', status: 'pending' },
    ]
    const results = await Promise.allSettled([
      ...reviews.map((item) => collection(`/admin/${item.resource}?status=${item.status}`)),
      api<CollectionData>('/map/pois?limit=100'),
      collection('/admin/activities?status=published'),
    ])
    reviewCounts.value = reviews.map((item, i) => ({
      label: item.label,
      path: `/admin/${item.resource}`,
      count: results[i]?.status === 'fulfilled' ? results[i].value.total : null,
    }))
    const poiResult = results[4]
    const activityResult = results[5]
    pointsUnavailable.value = poiResult?.status !== 'fulfilled'
    locationRows.value = poiResult?.status === 'fulfilled' ? poiResult.value.items : []
    // Public POI listing is paginated. Fetch every published point, never silently truncate at 8.
    if (poiResult?.status === 'fulfilled') {
      for (let offset = locationRows.value.length; offset < poiResult.value.total; offset += 100) {
        try {
          const page = await api<CollectionData>(`/map/pois?limit=100&offset=${offset}`)
          locationRows.value.push(...page.items)
          if (!page.items.length) break
        } catch {
          pointsUnavailable.value = true
          break
        }
      }
    }
    featureRows.value = activityResult?.status === 'fulfilled' ? activityResult.value.items : []
  }
  loading.value = false
}
onMounted(load)
</script>

<template>
  <div class="cultural-dashboard" :class="{ 'merchant-dashboard': merchant }">
    <section v-if="merchant" class="merchant-identity dashboard-card">
      <MediaImage v-if="profile?.image_url" class="merchant-cover" :src="profile.image_url" fit="cover" />
      <div v-else class="merchant-cover merchant-cover-fallback" />
      <div class="merchant-copy">
        <span class="dashboard-kicker">商户经营工作台</span>
        <h1>{{ profile?.name || session.user?.display_name || '门店资料待完善' }}</h1>
        <div class="merchant-tags">
          <span v-for="tag in (profile?.tags || []).slice(0, 3)" :key="tag">{{ tag }}</span>
          <span v-if="!(profile?.tags || []).length">东巴文化体验</span>
        </div>
        <p>
          <el-icon><Location /></el-icon>
          {{ profile?.address || '请完善门店地址' }}
        </p>
        <p>{{ profile?.opening_hours || '营业时间待完善' }}</p>
        <small>{{ profile?.description || '完善门店故事，让游客更了解你的文化体验。' }}</small>
      </div>
      <router-link to="/merchant/profile" class="identity-action">编辑资料</router-link>
    </section>

    <section v-else class="dashboard-welcome">
      <div>
        <span class="dashboard-kicker">东巴寻迹 · 文旅数字化运营管理平台</span>
        <h1>欢迎回来，{{ session.user?.display_name || '运营管理员' }}</h1>
        <p>用数字技术传承东巴文化，让更多人遇见更好的丽江。</p>
      </div>
      <div class="welcome-date">
        <span>山水之间 · 文化相连</span>
        <small>{{ updated ? `数据更新于 ${dateText(updated)}` : '数据加载中' }}</small>
      </div>
    </section>

    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="page-alert" />

    <div v-loading="loading" class="dashboard-metrics" :class="{ 'merchant-metrics': merchant }">
      <article v-for="metric in metrics" :key="metric.key" class="dashboard-metric">
        <span class="metric-icon" :class="`tone-${metric.tone}`">
          <el-icon><component :is="metric.icon" /></el-icon>
        </span>
        <div>
          <span>{{ metric.label }}</span>
          <strong>{{ value(metric.key) }}</strong>
        </div>
        <small>累计数据</small>
      </article>
    </div>

    <div class="dashboard-layout">
      <section class="dashboard-card trend-panel">
        <header class="dashboard-section-title">
          <div>
            <i></i>
            <h2>{{ merchant ? '流量与转化趋势' : '运营数据趋势' }}</h2>
          </div>
          <div class="period-tabs" aria-label="趋势周期">
            <button
              v-for="daysCount in [7, 30, 90]"
              :key="daysCount"
              :class="{ active: period === daysCount }"
              @click="period = daysCount"
            >
              近{{ daysCount }}天
            </button>
          </div>
        </header>
        <div class="chart-legend">
          <span v-for="series in chartSeries" :key="series.key">
            <i :style="{ background: series.color }"></i>
            {{ series.label }}
          </span>
        </div>
        <div
          v-if="visibleDays.length"
          class="bar-chart"
          role="img"
          :aria-label="`近${period}天每日识别请求、领券及核销柱状图`"
        >
          <div class="chart-axis" aria-hidden="true">
            <span>{{ chartMax }}</span>
            <span>{{ Math.round(chartMax / 2) }}</span>
            <span>0</span>
          </div>
          <div class="chart-scroll">
            <div class="chart-days">
              <div v-for="(day, index) in visibleDays" :key="day.date" class="chart-day">
                <div class="chart-bars">
                  <el-tooltip
                    v-for="series in chartSeries"
                    :key="series.key"
                    :content="`${day.date} · ${series.label} ${day[series.key] || 0}`"
                  >
                    <span
                      class="chart-bar"
                      :style="{
                        height: `${(Math.max(0, Number(day[series.key] || 0)) / chartMax) * 100}%`,
                        backgroundColor: series.color,
                      }"
                      tabindex="0"
                    />
                  </el-tooltip>
                </div>
                <span class="chart-date">
                  {{
                    index % (period === 7 ? 1 : period === 30 ? 5 : 15) === 0 ? String(day.date).slice(5) : ''
                  }}
                </span>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无趋势数据" :image-size="82" />
        <p class="dashboard-note">按日统计所选时段内的业务记录。</p>
      </section>

      <section class="dashboard-card action-panel">
        <header class="dashboard-section-title">
          <div>
            <i></i>
            <h2>{{ merchant ? '经营快捷入口' : '待审核事项' }}</h2>
          </div>
        </header>
        <router-link
          v-for="item in reviewCounts"
          :key="item.path"
          :to="item.path"
          class="dashboard-action-row"
        >
          <span>{{ item.label }}</span>
          <strong>{{ item.count ?? '—' }}</strong>
          <el-icon><ArrowRight /></el-icon>
        </router-link>
        <p v-if="!merchant" class="dashboard-note">按当前审核状态统计待处理事项。</p>
      </section>

      <section v-if="!merchant" class="dashboard-card map-panel">
        <header class="dashboard-section-title">
          <div>
            <i></i>
            <h2>丽江文旅点位概览</h2>
          </div>
          <router-link to="/admin/pois">
            管理点位
            <el-icon><ArrowRight /></el-icon>
          </router-link>
        </header>
        <PoiMap :points="locationRows" :unavailable="pointsUnavailable" />
      </section>

      <section v-else class="dashboard-card funnel-panel">
        <header class="dashboard-section-title">
          <div>
            <i></i>
            <h2>商户转化路径</h2>
          </div>
        </header>
        <div v-for="stage in funnel" :key="stage.key" class="funnel-row">
          <span>{{ stage.label }}</span>
          <div class="funnel-track">
            <i :style="{ width: `${(Number(stats?.[stage.key] || 0) / funnelMax) * 100}%` }"></i>
          </div>
          <strong>{{ value(stage.key) }}</strong>
        </div>
        <p class="dashboard-note">来源归因仍有业务缺口；这里只展示已采集的阶段总量。</p>
      </section>

      <section class="dashboard-card source-panel">
        <header class="dashboard-section-title">
          <div>
            <i></i>
            <h2>识别来源东巴字 Top{{ merchant ? 5 : 10 }}</h2>
          </div>
        </header>
        <div v-if="sources.length" class="dashboard-source-list">
          <div
            v-for="(source, index) in sources.slice(0, merchant ? 5 : 10)"
            :key="source.character_id"
            class="dashboard-source-row"
          >
            <span class="source-rank">{{ index + 1 }}</span>
            <strong>{{ source.cn_name || source.character_id }}</strong>
            <div><i :style="{ width: `${(Number(source.count) / sourceMax) * 100}%` }"></i></div>
            <b>{{ source.count }}</b>
          </div>
        </div>
        <el-empty v-else description="暂无来源数据" :image-size="70" />
        <p class="dashboard-note">包含曝光、访问与导航次数，不等同于独立访客数。</p>
      </section>

      <section v-if="!merchant" class="dashboard-card provider-panel">
        <header class="dashboard-section-title">
          <div>
            <i></i>
            <h2>AI 识别服务健康度</h2>
          </div>
          <router-link to="/admin/provider">
            查看详情
            <el-icon><ArrowRight /></el-icon>
          </router-link>
        </header>
        <div class="provider-status">
          <span :class="{ online: provider?.configured }"></span>
          <strong>{{ provider?.configured ? '服务已配置' : '服务未配置' }}</strong>
          <small>{{ provider?.model || provider?.name || '状态不可用' }}</small>
        </div>
        <div class="provider-facts">
          <div>
            <span>近期请求</span>
            <strong>{{ provider?.recent_requests ?? '—' }}</strong>
          </div>
          <div>
            <span>请求成功率</span>
            <strong>{{ providerSuccess === null ? '—' : `${providerSuccess.toFixed(1)}%` }}</strong>
          </div>
          <div>
            <span>P95 响应时间</span>
            <strong>{{ provider?.p95_latency_ms == null ? '—' : `${provider.p95_latency_ms}ms` }}</strong>
          </div>
        </div>
        <p class="dashboard-note">请求成功率反映服务响应情况，不代表识别准确率。</p>
      </section>

      <section class="dashboard-card feature-panel">
        <header class="dashboard-section-title">
          <div>
            <i></i>
            <h2>{{ merchant ? '热门商品' : '近期活动' }}</h2>
          </div>
          <router-link :to="merchant ? '/merchant/products' : '/admin/activities'">
            查看全部
            <el-icon><ArrowRight /></el-icon>
          </router-link>
        </header>
        <div v-if="featureRows.length" class="feature-list">
          <article v-for="row in featureRows.slice(0, 4)" :key="row.id">
            <MediaImage v-if="row.image_url" :src="row.image_url" fit="cover" />
            <span v-else class="feature-placeholder">
              <el-icon><component :is="merchant ? Shop : Compass" /></el-icon>
            </span>
            <div>
              <strong>{{ row.name || row.title || row.id }}</strong>
              <small>
                {{
                  merchant && row.price != null
                    ? `¥${Number(row.price).toFixed(2)}`
                    : row.start_at
                      ? dateText(row.start_at)
                      : row.status || '运营内容'
                }}
              </small>
            </div>
          </article>
        </div>
        <el-empty v-else :description="merchant ? '暂无商品' : '暂无已发布活动'" :image-size="70" />
      </section>
    </div>

    <el-button class="dashboard-refresh" :icon="Refresh" :loading="loading" round @click="load">
      刷新数据
    </el-button>
  </div>
</template>

<style scoped>
.cultural-dashboard {
  --dash-accent: #176fd1;
  --dash-soft: #eaf4ff;
  position: relative;
  max-width: 1640px;
  margin: 0 auto;
  color: #172033;
}
.merchant-dashboard {
  --dash-accent: #b4532b;
  --dash-soft: #fff1e8;
}
.dashboard-welcome {
  min-height: 105px;
  margin: -24px 0 14px;
  padding: 22px 34px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background:
    linear-gradient(90deg, rgba(246, 250, 255, 0.97), rgba(242, 248, 254, 0.82)),
    url('/art/lijiang-panorama.png') right center/58% 100% no-repeat;
  border-bottom: 1px solid #e5edf5;
}
.dashboard-kicker {
  display: block;
  color: var(--dash-accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  margin-bottom: 7px;
}
.dashboard-welcome h1 {
  font-size: 24px;
  margin: 0 0 5px;
}
.dashboard-welcome p {
  color: #607087;
  font-size: 13px;
}
.welcome-date {
  text-align: right;
  display: grid;
  gap: 10px;
  font-family: STKaiti, KaiTi, serif;
  font-size: 19px;
}
.welcome-date small {
  font-family: inherit;
  color: #68778c;
  font-size: 12px;
}
.dashboard-metrics {
  display: grid;
  grid-template-columns: repeat(6, minmax(130px, 1fr));
  gap: 12px;
  margin-bottom: 13px;
}
.merchant-metrics {
  grid-template-columns: repeat(5, minmax(145px, 1fr));
}
.dashboard-metric {
  min-height: 104px;
  background: #fff;
  border: 1px solid #e7ecf2;
  border-radius: 11px;
  padding: 16px;
  display: grid;
  grid-template-columns: 52px 1fr;
  column-gap: 13px;
  align-items: center;
  box-shadow: 0 5px 18px rgba(31, 55, 83, 0.04);
}
.metric-icon {
  grid-row: 1/3;
  width: 49px;
  height: 49px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 24px;
  background: linear-gradient(145deg, #4a91ef, #176fd1);
  box-shadow: 0 7px 16px rgba(23, 111, 209, 0.2);
}
.tone-cyan {
  background: linear-gradient(145deg, #38bbc9, #1296a7);
}
.tone-indigo {
  background: linear-gradient(145deg, #4e7ff5, #2854c5);
}
.tone-amber {
  background: linear-gradient(145deg, #ffb844, #f08a16);
}
.tone-red {
  background: linear-gradient(145deg, #f05f55, #d92d29);
}
.tone-green {
  background: linear-gradient(145deg, #38c395, #129b6b);
}
.dashboard-metric div {
  display: grid;
}
.dashboard-metric div span {
  font-size: 13px;
  color: #56637a;
}
.dashboard-metric strong {
  font-size: 26px;
  line-height: 1.15;
  color: #101726;
}
.dashboard-metric small {
  grid-column: 2;
  color: #8994a5;
  font-size: 11px;
}
.dashboard-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(270px, 0.85fr) minmax(270px, 0.85fr);
  gap: 13px;
}
.dashboard-card {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #e6ebf1;
  border-radius: 11px;
  box-shadow: 0 5px 20px rgba(27, 50, 77, 0.045);
  overflow: hidden;
}
.dashboard-section-title {
  height: 52px;
  padding: 0 17px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #edf0f4;
}
.dashboard-section-title > div {
  display: flex;
  align-items: center;
  gap: 10px;
}
.dashboard-section-title i {
  width: 4px;
  height: 20px;
  border-radius: 4px;
  background: #e32020;
}
.dashboard-section-title h2 {
  font-size: 16px;
}
.dashboard-section-title > a {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #708097;
  font-size: 12px;
}
.trend-panel {
  grid-column: span 2;
  min-height: 353px;
}
.chart-legend {
  display: flex;
  gap: 22px;
  padding: 14px 20px 0;
  color: #66748a;
  font-size: 12px;
}
.chart-legend span {
  display: flex;
  align-items: center;
  gap: 6px;
}
.chart-legend i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.period-tabs {
  display: flex;
  gap: 4px;
}
.period-tabs button {
  border: 0;
  border-radius: 16px;
  padding: 5px 12px;
  color: #6f7d91;
  background: #f1f4f7;
  cursor: pointer;
  font-size: 11px;
}
.period-tabs button.active {
  color: #fff;
  background: var(--dash-accent);
}
.bar-chart {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  height: 225px;
  padding: 6px 18px 8px;
}
.chart-axis {
  height: 183px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-end;
  padding-right: 8px;
  color: #8994a5;
  font-size: 10px;
}
.chart-scroll {
  min-width: 0;
  overflow-x: auto;
  overflow-y: hidden;
}
.chart-days {
  height: 207px;
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(26px, 1fr);
  width: 100%;
  min-width: max-content;
  background: repeating-linear-gradient(to bottom, #e8edf3 0 1px, transparent 1px 45px) no-repeat;
  background-size: 100% 181px;
}
.chart-day {
  min-width: 26px;
  display: grid;
  grid-template-rows: 183px 24px;
}
.chart-bars {
  display: flex;
  justify-content: center;
  align-items: flex-end;
  gap: 1px;
  padding: 0 2px;
  height: 181px;
}
.chart-bar {
  width: 28%;
  max-width: 12px;
  border-radius: 3px 3px 0 0;
  cursor: default;
}
.chart-bar:focus-visible {
  outline: 2px solid #162f4d;
  outline-offset: 2px;
}
.chart-date {
  text-align: center;
  color: #8994a5;
  font-size: 10px;
  white-space: nowrap;
  padding-top: 5px;
}
.dashboard-note {
  margin: 4px 17px 13px;
  color: #8a94a2;
  font-size: 10px;
  line-height: 1.5;
}
.action-panel {
  min-height: 353px;
}
.dashboard-action-row {
  height: 59px;
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 12px;
  padding: 0 18px;
  border-bottom: 1px solid #f0f2f5;
  font-size: 13px;
}
.dashboard-action-row:hover {
  background: var(--dash-soft);
}
.dashboard-action-row strong {
  min-width: 30px;
  height: 25px;
  border-radius: 14px;
  padding: 0 8px;
  display: grid;
  place-items: center;
  color: var(--dash-accent);
  background: var(--dash-soft);
}
.map-panel {
  grid-column: span 2;
  min-height: 390px;
  display: flex;
  flex-direction: column;
}
.map-panel > .dashboard-section-title {
  flex: none;
}
.map-visual {
  overflow: hidden;
  height: 267px;
  position: relative;
  overflow: hidden;
  background-color: #eef4ef;
  background-image:
    linear-gradient(31deg, transparent 44%, rgba(197, 213, 195, 0.55) 45%, transparent 48%),
    linear-gradient(142deg, transparent 31%, rgba(218, 225, 205, 0.65) 32%, transparent 36%),
    repeating-linear-gradient(5deg, transparent 0 37px, rgba(255, 255, 255, 0.6) 38px 42px);
}
.map-visual:before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 25% 38%, rgba(255, 255, 255, 0.85) 0 7%, transparent 8%),
    radial-gradient(circle at 69% 55%, rgba(255, 255, 255, 0.72) 0 8%, transparent 9%);
}
.map-river {
  position: absolute;
  width: 115%;
  height: 12px;
  border-radius: 50%;
  background: #9ddbed;
  opacity: 0.65;
  transform: rotate(-14deg);
  left: -8%;
  top: 49%;
}
.river-two {
  transform: rotate(34deg);
  width: 57%;
  height: 7px;
  left: 48%;
  top: 53%;
}
.map-marker {
  position: absolute;
  z-index: 2;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  gap: 5px;
  color: #26374d;
  font-size: 10px;
  font-weight: 650;
  white-space: nowrap;
}
.map-marker .el-icon {
  width: 30px;
  height: 30px;
  color: #fff;
  border-radius: 50%;
  background: #2878db;
  display: grid;
  place-items: center;
  font-size: 15px;
  box-shadow: 0 3px 10px rgba(24, 70, 115, 0.3);
  border: 2px solid #fff;
}
.map-marker.green .el-icon {
  background: #169a69;
}
.map-marker.warm .el-icon {
  background: #a45a2e;
}
.map-visual > small {
  position: absolute;
  right: 12px;
  bottom: 8px;
  z-index: 3;
  color: #66748a;
  background: rgba(255, 255, 255, 0.82);
  padding: 4px 8px;
  border-radius: 5px;
  font-size: 9px;
}
.map-empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #718096;
}
.funnel-panel {
  min-height: 320px;
}
.funnel-row {
  display: grid;
  grid-template-columns: 70px 1fr 48px;
  align-items: center;
  gap: 10px;
  padding: 13px 17px 4px;
  font-size: 11px;
}
.funnel-track {
  height: 8px;
  border-radius: 9px;
  background: #edf0f4;
  overflow: hidden;
}
.funnel-track i {
  height: 100%;
  display: block;
  border-radius: 9px;
  background: linear-gradient(90deg, var(--dash-accent), #f0a268);
}
.funnel-row strong {
  text-align: right;
}
.source-panel {
  min-height: 320px;
}
.dashboard-source-list {
  padding: 8px 17px;
}
.dashboard-source-row {
  display: grid;
  grid-template-columns: 24px minmax(58px, 0.7fr) 1fr 36px;
  align-items: center;
  gap: 8px;
  height: 37px;
  font-size: 11px;
}
.source-rank {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  background: #aab3c1;
}
.dashboard-source-row:nth-child(-n + 3) .source-rank {
  background: #e34231;
}
.dashboard-source-row > div {
  height: 7px;
  border-radius: 7px;
  background: #edf0f4;
  overflow: hidden;
}
.dashboard-source-row > div i {
  height: 100%;
  display: block;
  border-radius: 7px;
  background: linear-gradient(90deg, #4388eb, #8eb9f4);
}
.dashboard-source-row b {
  text-align: right;
  font-weight: 500;
  color: #65738a;
}
.provider-panel,
.feature-panel {
  min-height: 250px;
}
.provider-status {
  padding: 16px 18px;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 2px 9px;
  align-items: center;
}
.provider-status > span {
  grid-row: span 2;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #e14c44;
  box-shadow: 0 0 0 5px #fde9e7;
}
.provider-status > span.online {
  background: #18a66d;
  box-shadow: 0 0 0 5px #e4f7ee;
}
.provider-status small {
  color: #7c899c;
}
.provider-facts {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  margin: 0 17px;
  border: 1px solid #edf0f4;
  border-radius: 8px;
}
.provider-facts div {
  padding: 14px 9px;
  text-align: center;
  border-right: 1px solid #edf0f4;
}
.provider-facts div:last-child {
  border: 0;
}
.provider-facts span {
  display: block;
  color: #7b8798;
  font-size: 10px;
}
.provider-facts strong {
  display: block;
  margin-top: 5px;
  font-size: 17px;
}
.feature-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  padding: 14px;
}
.feature-list article {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.feature-list .el-image,
.feature-placeholder {
  width: 55px;
  height: 49px;
  border-radius: 7px;
  flex: 0 0 auto;
  background: #eef3f7;
  display: grid;
  place-items: center;
  color: var(--dash-accent);
}
.feature-list article div {
  min-width: 0;
  display: grid;
}
.feature-list strong {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
}
.feature-list small {
  color: #79869a;
  margin-top: 5px;
  font-size: 10px;
}
.merchant-identity {
  min-height: 166px;
  position: relative;
  margin-bottom: 13px;
  display: grid;
  grid-template-columns: 340px 1fr;
  overflow: hidden;
  background:
    linear-gradient(90deg, #fff 0 58%, rgba(255, 255, 255, 0.2)),
    url('/art/merchant-tea.png') right center/53% 100% no-repeat;
}
.merchant-cover {
  width: 340px;
  height: 166px;
}
.merchant-cover-fallback {
  background: url('/art/merchant-tea.png') center/cover;
}
.merchant-copy {
  padding: 14px 22px;
  z-index: 1;
  max-width: 600px;
}
.merchant-copy h1 {
  font-size: 24px;
}
.merchant-tags {
  display: flex;
  gap: 6px;
  margin: 6px 0;
}
.merchant-tags span {
  padding: 4px 10px;
  border-radius: 13px;
  background: #f8ece4;
  color: #86503a;
  font-size: 10px;
}
.merchant-copy p {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 4px 0;
  color: #5f6977;
  font-size: 11px;
}
.merchant-copy small {
  display: block;
  margin-top: 5px;
  color: #6f7887;
}
.identity-action {
  position: absolute;
  left: 250px;
  bottom: 12px;
  padding: 7px 15px;
  border-radius: 18px;
  background: rgba(28, 31, 34, 0.78);
  color: #fff;
  font-size: 11px;
}
.dashboard-refresh {
  position: absolute;
  right: 0;
  top: -4px;
}
.merchant-dashboard .dashboard-refresh {
  top: 178px;
}
.merchant-dashboard .trend-panel {
  grid-column: span 2;
}
.merchant-dashboard .feature-panel {
  grid-column: span 2;
}
/* DESIGN-01: On the operations desktop dashboard, use the vacant third column. */
.cultural-dashboard:not(.merchant-dashboard) .feature-panel {
  grid-column: span 2;
}
@media (max-width: 1180px) {
  .dashboard-metrics,
  .merchant-metrics {
    grid-template-columns: repeat(3, 1fr);
  }
  .dashboard-layout {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .trend-panel,
  .map-panel {
    grid-column: span 2;
  }
  .cultural-dashboard:not(.merchant-dashboard) .feature-panel {
    grid-column: auto;
  }
  .merchant-identity {
    grid-template-columns: 250px 1fr;
  }
  .merchant-cover {
    width: 250px;
  }
}
@media (max-width: 720px) {
  .dashboard-welcome {
    margin: -17px 0 12px;
    padding: 18px 16px;
    min-height: 126px;
    background-position: center;
  }
  .welcome-date {
    display: none;
  }
  .dashboard-welcome h1 {
    font-size: 20px;
  }
  .dashboard-refresh {
    position: static;
    margin-bottom: 12px;
  }
  .merchant-dashboard .dashboard-refresh {
    position: static;
  }
  .dashboard-metrics,
  .merchant-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
  .dashboard-metric {
    min-height: 88px;
    padding: 11px;
    grid-template-columns: 39px 1fr;
    column-gap: 8px;
  }
  .metric-icon {
    width: 38px;
    height: 38px;
    font-size: 18px;
  }
  .dashboard-metric strong {
    font-size: 20px;
  }
  .dashboard-layout {
    grid-template-columns: 1fr;
  }
  .trend-panel,
  .map-panel,
  .merchant-dashboard .trend-panel,
  .merchant-dashboard .feature-panel {
    grid-column: auto;
  }
  .dashboard-section-title {
    height: auto;
    min-height: 50px;
    gap: 10px;
    flex-wrap: wrap;
    padding: 10px 13px;
  }
  .period-tabs {
    width: 100%;
  }
  .bar-chart {
    padding: 6px 8px 8px;
  }
  .merchant-identity {
    grid-template-columns: 104px 1fr;
    min-height: 178px;
  }
  .merchant-cover {
    width: 104px;
    height: 178px;
  }
  .merchant-copy {
    padding: 13px;
  }
  .merchant-copy h1 {
    font-size: 18px;
  }
  .merchant-copy small {
    display: none;
  }
  .identity-action {
    left: 14px;
    bottom: 12px;
  }
  .dashboard-source-row {
    grid-template-columns: 22px 70px 1fr 30px;
  }
  .map-marker span {
    display: none;
  }
  .feature-list {
    grid-template-columns: 1fr;
  }
  .provider-facts {
    grid-template-columns: 1fr;
  }
  .provider-facts div {
    border-right: 0;
    border-bottom: 1px solid #edf0f4;
  }
  .provider-facts div:last-child {
    border: 0;
  }
}
</style>
