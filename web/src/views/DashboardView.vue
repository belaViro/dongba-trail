<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ArrowRight, Collection, Compass, Refresh, Shop, Tickets, TrendCharts } from '@element-plus/icons-vue'
import { api, dateText, errorText, type Collection as CollectionData, type Row } from '../api'
import { session } from '../session'
const merchant = computed(() => session.user?.role === 'merchant')
const prefix = computed(() => (merchant.value ? '/merchant' : '/admin'))
const stats = ref<Row | null>(null)
const provider = ref<Row | null>(null)
const error = ref('')
const loading = ref(false)
const updated = ref('')
const reviewCounts = ref<{ label: string; count: number | null; path: string }[]>([])
const metrics = computed(() =>
  merchant.value
    ? [
        { key: 'merchant_impressions', label: '商户曝光', icon: Shop },
        { key: 'merchant_views', label: '详情访问', icon: TrendCharts },
        { key: 'navigations', label: '导航次数', icon: Compass },
        { key: 'coupon_claims', label: '优惠券领取', icon: Tickets },
        { key: 'redemptions', label: '到店核销', icon: Collection },
      ]
    : [
        { key: 'users', label: '用户总数', icon: Shop },
        { key: 'recognitions', label: '识别请求', icon: Collection },
        { key: 'merchant_views', label: '商户访问', icon: TrendCharts },
        { key: 'coupon_claims', label: '优惠券领取', icon: Tickets },
        { key: 'redemptions', label: '到店核销', icon: Compass },
      ],
)
const days = computed<Row[]>(() => stats.value?.daily || [])
const sources = computed<Row[]>(() => stats.value?.sources || [])
const sourceMax = computed(() => Math.max(1, ...sources.value.map((row) => Number(row.count || 0))))
const chartMax = computed(() =>
  Math.max(
    1,
    ...days.value.flatMap((row) => [
      Number(row.recognitions || 0),
      Number(row.coupon_claims || 0),
      Number(row.redemptions || 0),
    ]),
  ),
)
const funnel = computed(() => [
  { label: '商户曝光', key: 'merchant_impressions' },
  { label: '详情访问', key: 'merchant_views' },
  { label: '发起导航', key: 'navigations' },
  { label: '优惠券领取', key: 'coupon_claims' },
  { label: '到店核销', key: 'redemptions' },
])
const funnelMax = computed(() =>
  Math.max(1, ...funnel.value.map((row) => Number(stats.value?.[row.key] || 0))),
)
function value(key: string) {
  return stats.value?.[key] === undefined ? '—' : Number(stats.value[key]).toLocaleString('zh-CN')
}
async function load() {
  loading.value = true
  error.value = ''
  const requests = [
    api<Row>(`${prefix.value}/stats`),
    ...(merchant.value ? [] : [api<Row>('/admin/provider')]),
  ]
  const results = await Promise.allSettled(requests)
  if (results[0]?.status === 'fulfilled') {
    stats.value = results[0].value
    updated.value = new Date().toISOString()
  } else if (results[0]?.status === 'rejected') error.value = errorText(results[0].reason)
  if (results[1]?.status === 'fulfilled') provider.value = results[1].value
  if (!merchant.value) {
    const reviews = [
      { label: '字典草稿', resource: 'characters', status: 'draft' },
      { label: '商户草稿', resource: 'merchants', status: 'draft' },
      { label: '文化标签申请', resource: 'tag-claims', status: 'pending' },
      { label: '识别纠错', resource: 'feedback', status: 'pending' },
    ]
    const counts = await Promise.allSettled(
      reviews.map((item) => api<CollectionData>(`/admin/${item.resource}?status=${item.status}&limit=1`)),
    )
    reviewCounts.value = reviews.map((item, i) => ({
      label: item.label,
      path: `/admin/${item.resource}`,
      count:
        counts[i]?.status === 'fulfilled'
          ? (counts[i] as PromiseFulfilledResult<CollectionData>).value.total
          : null,
    }))
  }
  loading.value = false
}
onMounted(load)
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">{{ merchant ? '门店工作台' : '运营工作台' }}</span>
      <h1>{{ merchant ? '经营概览' : '运营概览' }}</h1>
      <p v-if="updated" class="muted">截至 {{ dateText(updated) }}</p>
    </div>
    <el-button :icon="Refresh" :loading="loading" @click="load">刷新数据</el-button>
  </div>
  <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="page-alert" />
  <div v-loading="loading" class="metric-grid">
    <article
      v-for="(metric, index) in metrics"
      :key="metric.key"
      class="metric"
      :class="{ accent: index === 0 }"
    >
      <div class="metric-label">
        <span>{{ metric.label }}</span>
        <el-icon><component :is="metric.icon" /></el-icon>
      </div>
      <strong>{{ value(metric.key) }}</strong>
      <span class="metric-period">累计</span>
    </article>
  </div>
  <dl v-if="!merchant" class="operations-metrics">
    <div>
      <dt>今日活跃用户</dt>
      <dd>{{ value('active_users_today') }}</dd>
    </div>
    <div>
      <dt>用户确认识别</dt>
      <dd>{{ value('confirmed_recognitions') }}</dd>
    </div>
    <div>
      <dt>识别失败</dt>
      <dd>{{ value('recognition_failures') }}</dd>
    </div>
    <div>
      <dt>寻迹完成</dt>
      <dd>{{ value('quest_completions') }}</dd>
    </div>
    <div>
      <dt>海报生成</dt>
      <dd>{{ stats ? (stats.events?.poster_generate || 0).toLocaleString('zh-CN') : '—' }}</dd>
    </div>
    <div>
      <dt>分享操作</dt>
      <dd>{{ stats ? (stats.events?.share || 0).toLocaleString('zh-CN') : '—' }}</dd>
    </div>
  </dl>
  <div class="dashboard-columns">
    <section class="data-section trend-section">
      <div class="section-heading">
        <h2>访问与转化趋势</h2>
        <span class="muted">按日统计</span>
      </div>
      <div class="chart-legend">
        <span class="legend-recognition">识别</span>
        <span class="legend-claims">领券</span>
        <span class="legend-redemption">核销</span>
      </div>
      <div v-if="days.length" class="bar-chart" role="img" aria-label="每日识别、领券和核销次数">
        <div class="chart-axis">
          <span>{{ chartMax }}</span>
          <span>{{ chartMax / 2 }}</span>
          <span>0</span>
        </div>
        <div class="chart-days">
          <div v-for="day in days.slice(-14)" :key="day.date" class="chart-day">
            <div class="chart-bars">
              <el-tooltip
                v-for="key in ['recognitions', 'coupon_claims', 'redemptions']"
                :key="key"
                :content="`${day.date} · ${{ recognitions: '识别', coupon_claims: '领券', redemptions: '核销' }[key]} ${day[key] || 0}`"
              >
                <span
                  :class="`bar-${key}`"
                  :style="{ height: `${(Number(day[key] || 0) / chartMax) * 100}%` }"
                  tabindex="0"
                />
              </el-tooltip>
            </div>
            <span class="chart-date">{{ String(day.date).slice(5) }}</span>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无趋势数据" :image-size="86" />
    </section>
    <section class="data-section">
      <div class="section-heading">
        <h2>{{ merchant ? '门店快捷入口' : '待处理事项' }}</h2>
      </div>
      <template v-if="!merchant">
        <router-link v-for="review in reviewCounts" :key="review.path" :to="review.path" class="review-row">
          <span>{{ review.label }}</span>
          <strong>{{ review.count ?? '—' }}</strong>
          <el-icon><ArrowRight /></el-icon>
        </router-link>
      </template>
      <template v-else>
        <router-link
          v-for="link in [
            { path: '/merchant/redeem', label: '到店核销' },
            { path: '/merchant/coupons', label: '管理优惠券' },
            { path: '/merchant/profile', label: '维护门店资料' },
            { path: '/merchant/tag-claims', label: '申请文化标签' },
          ]"
          :key="link.path"
          :to="link.path"
          class="review-row"
        >
          <span>{{ link.label }}</span>
          <el-icon><ArrowRight /></el-icon>
        </router-link>
      </template>
    </section>
    <section class="data-section">
      <div class="section-heading"><h2>商户转化</h2></div>
      <div v-for="stage in funnel" :key="stage.key" class="funnel-row">
        <span>{{ stage.label }}</span>
        <div class="funnel-track">
          <span :style="{ width: `${(Number(stats?.[stage.key] || 0) / funnelMax) * 100}%` }" />
        </div>
        <strong>{{ value(stage.key) }}</strong>
      </div>
    </section>
    <section class="data-section">
      <div class="section-heading">
        <h2>东巴字来源</h2>
        <span class="muted">按访问次数</span>
      </div>
      <div v-if="sources.length" class="source-list">
        <div v-for="(source, index) in sources.slice(0, 8)" :key="source.character_id" class="source-row">
          <span class="rank">{{ String(index + 1).padStart(2, '0') }}</span>
          <div>
            <span>{{ source.cn_name || source.character_id }}</span>
            <div class="source-track">
              <span :style="{ width: `${(Number(source.count) / sourceMax) * 100}%` }" />
            </div>
          </div>
          <strong>{{ source.count }}</strong>
        </div>
      </div>
      <el-empty v-else description="暂无来源数据" :image-size="72" />
    </section>
  </div>
  <section v-if="!merchant" class="provider-strip">
    <div>
      <span class="provider-light" :class="{ online: provider?.configured }" />
      <strong>识别服务</strong>
      <el-tag :type="provider?.configured ? 'success' : 'warning'" size="small">
        {{ provider ? (provider.configured ? '已配置' : '尚未配置') : '状态不可用' }}
      </el-tag>
    </div>
    <span class="muted">{{ provider?.model || provider?.name || '—' }}</span>
    <router-link to="/admin/provider">
      查看服务状态
      <el-icon><ArrowRight /></el-icon>
    </router-link>
  </section>
</template>
