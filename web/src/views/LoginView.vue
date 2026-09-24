<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Compass, Lock, User } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import type { FormInstance } from 'element-plus'
import { api, errorText, tokenStore, type User as UserType } from '../api'
import { homePath, session } from '../session'
const router = useRouter()
const setup = ref(false)
const checking = ref(true)
const busy = ref(false)
const error = ref('')
const formRef = ref<FormInstance>()
const form = reactive({ username: '', password: '', display_name: '' })
const setupSecret = ref('')
async function check() {
  checking.value = true
  error.value = ''
  try {
    const data = await api<{ setup_required: boolean }>('/auth/setup-status')
    setup.value = data.setup_required
  } catch (e) {
    error.value = errorText(e)
  } finally {
    checking.value = false
  }
}
async function submit() {
  if (!(await formRef.value?.validate().catch(() => false))) return
  busy.value = true
  error.value = ''
  try {
    const result = await api<{ access_token: string; user: UserType }>(
      setup.value ? '/auth/setup' : '/auth/login',
      {
        method: 'POST',
        body: JSON.stringify(setup.value ? form : { username: form.username, password: form.password }),
        headers: setup.value && setupSecret.value ? { 'X-Setup-Secret': setupSecret.value } : undefined,
      },
    )
    tokenStore.set(result.access_token)
    const user = result.user || (await api<UserType>('/auth/me'))
    if (!['admin', 'operator', 'merchant'].includes(user.role)) {
      tokenStore.clear()
      throw new Error('该账号无管理工作台访问权限')
    }
    session.user = user
    session.initialized = true
    await router.replace(homePath())
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = false
  }
}
onMounted(check)
</script>
<template>
  <div class="login-page">
    <header class="login-brand">
      <el-icon><Compass /></el-icon>
      <span>东巴寻迹 · 丽江</span>
    </header>
    <main class="login-main">
      <div class="login-heading">
        <span class="eyebrow">管理工作台</span>
        <h1>{{ setup ? '创建管理员' : '登录工作台' }}</h1>
      </div>
      <el-skeleton v-if="checking" :rows="4" animated />
      <template v-else>
        <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="form-alert" />
        <el-form ref="formRef" :model="form" label-position="top" @submit.prevent="submit">
          <el-form-item
            v-if="setup"
            label="管理员姓名"
            prop="display_name"
            :rules="[{ required: true, message: '请输入姓名', trigger: 'blur' }]"
          >
            <el-input v-model="form.display_name" autocomplete="name" size="large" />
          </el-form-item>
          <el-form-item
            label="登录账号"
            prop="username"
            :rules="[{ required: true, message: '请输入账号', trigger: 'blur' }]"
          >
            <el-input v-model="form.username" :prefix-icon="User" autocomplete="username" size="large" />
          </el-form-item>
          <el-form-item
            label="密码"
            prop="password"
            :rules="[
              { required: true, message: '请输入密码', trigger: 'blur' },
              ...(setup ? [{ min: 12, message: '密码至少12位', trigger: 'blur' }] : []),
            ]"
          >
            <el-input
              v-model="form.password"
              :prefix-icon="Lock"
              type="password"
              show-password
              :autocomplete="setup ? 'new-password' : 'current-password'"
              size="large"
            />
          </el-form-item>
          <el-form-item v-if="setup" label="初始化授权码（可选）">
            <el-input v-model="setupSecret" type="password" show-password autocomplete="off" size="large" />
          </el-form-item>
          <el-button type="primary" native-type="submit" size="large" :loading="busy" class="login-submit">
            {{ setup ? '创建并进入工作台' : '登录' }}
          </el-button>
        </el-form>
        <el-button v-if="error" text class="login-retry" @click="check">重新连接</el-button>
      </template>
    </main>
    <footer class="login-footer">文化有源 · 寻迹有据</footer>
  </div>
</template>
