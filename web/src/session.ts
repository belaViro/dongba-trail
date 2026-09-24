import { reactive } from 'vue'
import { api, tokenStore, type User } from './api'

export const session = reactive<{ user: User | null; initialized: boolean }>({
  user: null,
  initialized: false,
})
let pending: Promise<void> | undefined
export async function restoreSession() {
  if (session.initialized) return
  if (!pending)
    pending = (async () => {
      if (tokenStore.get()) {
        try {
          const user = await api<User>('/auth/me')
          if (['admin', 'operator', 'merchant'].includes(user.role)) session.user = user
          else {
            tokenStore.clear()
            session.user = null
          }
        } catch (error) {
          tokenStore.clear()
          session.user = null
        }
      }
      session.initialized = true
    })().finally(() => {
      pending = undefined
    })
  await pending
}
export function endSession() {
  tokenStore.clear()
  session.user = null
  session.initialized = true
}
export function homePath() {
  return session.user?.role === 'merchant' ? '/merchant/dashboard' : '/admin/dashboard'
}
