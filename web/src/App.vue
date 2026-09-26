<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowRight,
  CircleCheck as Verified,
  Close,
  Collection,
  Compass,
  DataAnalysis,
  Document,
  Files,
  Location,
  Menu,
  Operation,
  Picture,
  Search,
  Setting,
  Shop,
  SwitchButton,
  Tickets,
  User,
  Wallet,
} from '@element-plus/icons-vue'
import { api, errorText } from './api'
import { endSession, session } from './session'
const route = useRoute()
const router = useRouter()
const mobileMenu = ref(false)
const merchant = computed(() => session.user?.role === 'merchant')
const menu = computed(() =>
  merchant.value
    ? [
        {
          title: '门店工作台',
          items: [
            { path: 'dashboard', title: '经营概览', icon: DataAnalysis },
            { path: 'profile', title: '门店资料', icon: Shop },
            { path: 'tag-claims', title: '文化标签', icon: Collection },
          ],
        },
        {
          title: '经营管理',
          items: [
            { path: 'products', title: '商品管理', icon: Picture },
            { path: 'coupons', title: '优惠券', icon: Tickets },
            { path: 'activities', title: '体验活动', icon: Compass },
            { path: 'redeem', title: '到店核销', icon: Verified },
            { path: 'redemptions', title: '核销记录', icon: Document },
          ],
        },
      ]
    : [
        { title: '工作台', items: [{ path: 'dashboard', title: '运营概览', icon: DataAnalysis }] },
        {
          title: '内容中心',
          items: [
            { path: 'characters', title: '东巴字典', icon: Collection },
            { path: 'samples', title: '图片样本', icon: Picture },
            { path: 'feedback', title: '识别纠错', icon: Files },
          ],
        },
        {
          title: '商户与地图',
          items: [
            { path: 'merchants', title: '商户管理', icon: Shop },
            { path: 'pois', title: '文化地图点位', icon: Location },
            { path: 'products', title: '商品管理', icon: Picture },
            { path: 'tag-claims', title: '文化标签审核', icon: Verified },
          ],
        },
        {
          title: '运营活动',
          items: [
            { path: 'coupons', title: '优惠券', icon: Tickets },
            { path: 'activities', title: '体验活动', icon: Compass },
            { path: 'quests', title: '寻迹路线', icon: Location },
            { path: 'quest-nodes', title: '任务节点', icon: Operation },
          ],
        },
        {
          title: 'AI与系统',
          items: [
            { path: 'recognitions', title: '识别记录', icon: Document },
            { path: 'provider', title: '识别服务', icon: Wallet },
            { path: 'settings', title: '推荐配置', icon: Setting },
            ...(session.user?.role === 'admin'
              ? [{ path: 'system-config', title: '系统配置', icon: Setting }]
              : []),
            ...(session.user?.role === 'admin' ? [{ path: 'users', title: '账号与权限', icon: User }] : []),
            { path: 'audit', title: '操作审计', icon: Files },
          ],
        },
      ],
)
const current = computed(() =>
  menu.value.flatMap((group) => group.items).find((item) => route.path.endsWith(`/${item.path}`)),
)
const prefix = computed(() => (merchant.value ? '/merchant' : '/admin'))
const accountName = computed(() => session.user?.display_name || session.user?.username || '')
const accountInitial = computed(() => Array.from(accountName.value.trim())[0] || '·')
const navigationQuery = ref('')
type NavigationSuggestion = { value: string; path: string; group: string }
function findNavigation(query: string, done: (items: NavigationSuggestion[]) => void) {
  const term = query.trim().toLocaleLowerCase()
  done(
    menu.value.flatMap((group) =>
      group.items
        .filter((item) => `${group.title} ${item.title}`.toLocaleLowerCase().includes(term))
        .map((item) => ({ value: item.title, path: `${prefix.value}/${item.path}`, group: group.title })),
    ),
  )
}
function openNavigation(item: Record<string, unknown>) {
  // AUTH-02: search is local navigation, restricted to the current role's menu.
  const allowed = menu.value.some((group) =>
    group.items.some((entry) => `${prefix.value}/${entry.path}` === item.path),
  )
  if (!allowed || typeof item.path !== 'string') return
  navigationQuery.value = ''
  mobileMenu.value = false
  void router.push(item.path)
}
async function logout() {
  try {
    await api('/auth/logout', { method: 'POST' })
    endSession()
    await router.replace('/login')
  } catch (error) {
    ElMessage.error(errorText(error))
  }
}
</script>
<template>
  <router-view v-if="route.meta.public" />
  <div v-else class="workspace" :class="{ 'is-merchant': merchant }" @keydown.esc="mobileMenu = false">
    <div v-if="mobileMenu" class="sidebar-scrim" @click="mobileMenu = false" />
    <aside id="workspace-navigation" class="sidebar" :class="{ 'is-open': mobileMenu }">
      <router-link :to="`${prefix}/dashboard`" class="brand" @click="mobileMenu = false">
        <span class="brand-copy">
          <strong>
            东巴寻迹·丽江
            <span class="brand-seal" aria-hidden="true">东巴</span>
          </strong>
          <small>{{ merchant ? '商户管理平台' : '文旅数字化运营管理平台' }}</small>
        </span>
      </router-link>
      <el-button
        class="sidebar-close"
        :icon="Close"
        circle
        aria-label="关闭导航"
        @click="mobileMenu = false"
      />
      <nav aria-label="主导航">
        <section v-for="group in menu" :key="group.title" class="nav-group">
          <p>{{ group.title }}</p>
          <router-link
            v-for="item in group.items"
            :key="item.path"
            :to="`${prefix}/${item.path}`"
            @click="mobileMenu = false"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </router-link>
        </section>
      </nav>
      <div class="sidebar-footer">
        <span>在丽江</span>
        <strong>{{ merchant ? '遇见更好的自己' : '让文化与生活相逢' }}</strong>
        <small>文化有源 · 寻迹有据</small>
      </div>
    </aside>
    <div class="workspace-main">
      <header class="topbar">
        <div class="topbar-heading">
          <el-button
            class="mobile-toggle"
            :icon="Menu"
            circle
            aria-label="打开导航"
            aria-controls="workspace-navigation"
            :aria-expanded="mobileMenu"
            @click="mobileMenu = !mobileMenu"
          />
          <div class="topbar-copy">
            <p class="cultural-slogan">
              {{ merchant ? '让更多人看见你的文化　让丽江更有温度' : '传承东巴文化　让世界看见丽江' }}
            </p>
            <div class="breadcrumb">
              <span>{{ merchant ? '商户中心' : '运营中心' }}</span>
              <el-icon><ArrowRight /></el-icon>
              <strong>{{ current?.title || '工作台' }}</strong>
            </div>
          </div>
        </div>
        <el-autocomplete
          v-model="navigationQuery"
          class="navigation-search"
          popper-class="navigation-search-results"
          :fetch-suggestions="findNavigation"
          :prefix-icon="Search"
          :debounce="0"
          clearable
          fit-input-width
          placeholder="搜索功能菜单…"
          aria-label="搜索当前账号可访问的功能菜单"
          @select="openNavigation"
        >
          <template #default="{ item }">
            <span class="navigation-result-title">{{ item.value }}</span>
            <small>{{ item.group }}</small>
          </template>
        </el-autocomplete>
        <div class="account-area">
          <span class="account-avatar" aria-hidden="true">{{ accountInitial }}</span>
          <div class="account-copy">
            <span class="account-name" :title="accountName">{{ accountName }}</span>
            <span class="account-role">
              {{ merchant ? '商户账号' : session.user?.role === 'admin' ? '运营管理员' : '运营人员' }}
            </span>
          </div>
          <el-tooltip content="退出登录">
            <el-button :icon="SwitchButton" circle aria-label="退出登录" @click="logout" />
          </el-tooltip>
        </div>
      </header>
      <main class="page-content"><router-view :key="route.path" /></main>
      <footer class="workspace-footer">
        <span>东巴寻迹 · 丽江</span>
        <span>文化有源 · 寻迹有据</span>
      </footer>
    </div>
  </div>
</template>
