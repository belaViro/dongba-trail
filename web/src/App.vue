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
  OfficeBuilding,
  Operation,
  Picture,
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
  <div v-else class="workspace">
    <div v-if="mobileMenu" class="sidebar-scrim" @click="mobileMenu = false" />
    <aside class="sidebar" :class="{ 'is-open': mobileMenu }">
      <router-link :to="`${prefix}/dashboard`" class="brand" @click="mobileMenu = false">
        <span class="brand-symbol">
          <el-icon><Compass /></el-icon>
        </span>
        <span>
          <strong>东巴寻迹</strong>
          <small>丽江 · {{ merchant ? '商户中心' : '运营中心' }}</small>
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
        <el-icon><OfficeBuilding /></el-icon>
        <span>{{ merchant ? '商户工作空间' : '文化与在地生活' }}</span>
      </div>
    </aside>
    <div class="workspace-main">
      <header class="topbar">
        <div class="breadcrumb">
          <el-button
            class="mobile-toggle"
            :icon="Menu"
            circle
            aria-label="打开导航"
            @click="mobileMenu = !mobileMenu"
          />
          <span>{{ merchant ? '商户中心' : '运营中心' }}</span>
          <el-icon><ArrowRight /></el-icon>
          <strong>{{ current?.title || '工作台' }}</strong>
        </div>
        <div class="account-area">
          <span class="account-role">
            {{ merchant ? '商户' : session.user?.role === 'admin' ? '管理员' : '运营人员' }}
          </span>
          <span class="account-name">{{ session.user?.display_name || session.user?.username }}</span>
          <el-tooltip content="退出登录">
            <el-button :icon="SwitchButton" circle aria-label="退出登录" @click="logout" />
          </el-tooltip>
        </div>
      </header>
      <main class="page-content"><router-view :key="route.path" /></main>
      <footer class="workspace-footer">
        <span>东巴寻迹 · 丽江</span>
        <span>管理工作台</span>
      </footer>
    </div>
  </div>
</template>
