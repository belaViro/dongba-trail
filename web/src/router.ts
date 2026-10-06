import { createRouter, createWebHistory } from 'vue-router'
import { homePath, restoreSession, session } from './session'
import { resources } from './resources'

const LoginView = () => import('./views/LoginView.vue')
const DashboardView = () => import('./views/DashboardView.vue')
const ResourceView = () => import('./views/ResourceView.vue')
const RecordsView = () => import('./views/RecordsView.vue')
const ProfileView = () => import('./views/ProfileView.vue')
const RedeemView = () => import('./views/RedeemView.vue')
const SettingsView = () => import('./views/SettingsView.vue')
const SystemConfigView = () => import('./views/SystemConfigView.vue')
const TagsView = () => import('./views/TagsView.vue')
const FeedbackView = () => import('./views/FeedbackView.vue')

const routes = [
  { path: '/', redirect: () => homePath() },
  { path: '/login', component: LoginView, meta: { public: true } },
  { path: '/admin', redirect: '/admin/dashboard' },
  { path: '/merchant', redirect: '/merchant/dashboard' },
  { path: '/admin/dashboard', component: DashboardView },
  { path: '/merchant/dashboard', component: DashboardView },
  { path: '/merchant/profile', component: ProfileView },
  { path: '/merchant/redeem', component: RedeemView },
  { path: '/merchant/tag-claims', component: TagsView },
  { path: '/admin/settings', component: SettingsView },
  { path: '/admin/system-config', component: SystemConfigView },
  { path: '/admin/feedback', component: FeedbackView },
  {
    path: '/admin/samples',
    redirect: (to: { query: Record<string, any> }) => ({
      path: '/admin/feedback',
      query: { q: to.query.recognition_id || to.query.q || '' },
    }),
  },
  { path: '/admin/rag-cases', redirect: '/admin/feedback' },
  ...Object.keys(resources).map((resource) => ({
    path: `/admin/${resource}`,
    component: ResourceView,
    props: { resource },
  })),
  ...['products', 'coupons', 'activities'].map((resource) => ({
    path: `/merchant/${resource}`,
    component: ResourceView,
    props: { resource },
  })),
  ...['tag-claims', 'recognitions', 'audit', 'provider'].map((resource) => ({
    path: `/admin/${resource}`,
    component: RecordsView,
    props: { resource },
  })),
  { path: '/merchant/redemptions', component: RecordsView, props: { resource: 'redemptions' } },
  { path: '/:pathMatch(.*)*', redirect: () => homePath() },
]
export const router = createRouter({ history: createWebHistory(), routes })
router.beforeEach(async (to) => {
  await restoreSession()
  if (to.meta.public) return session.user ? homePath() : true
  if (!session.user) return { path: '/login', query: { redirect: to.fullPath } }
  if (session.user.role === 'merchant' && !to.path.startsWith('/merchant/')) return '/merchant/dashboard'
  if (to.path === '/admin/system-config' && session.user.role !== 'admin') return '/admin/dashboard'
  if (['admin', 'operator'].includes(session.user.role) && !to.path.startsWith('/admin/'))
    return '/admin/dashboard'
  if (!['admin', 'operator', 'merchant'].includes(session.user.role)) return '/login'
  if (session.user.role !== 'admin' && to.path === '/admin/users') return '/admin/dashboard'
  return true
})
window.addEventListener('session-expired', () => {
  session.user = null
  void router.replace('/login')
})
