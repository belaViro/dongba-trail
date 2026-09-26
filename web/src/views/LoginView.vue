<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Lock, User } from '@element-plus/icons-vue'
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
      <span>东巴寻迹·丽江</span>
      <span class="brand-seal" aria-hidden="true">东巴</span>
      <small>文旅数字化管理平台</small>
    </header>
    <div class="login-layout">
      <section class="login-story" aria-label="东巴寻迹品牌介绍">
        <span class="login-story-kicker">山水之间 · 文化相连</span>
        <h1>
          传承东巴文化
          <br />
          让世界看见丽江
        </h1>
        <p>让更多人看见你的文化，让丽江更有温度。</p>
        <div class="login-story-caption">
          <span></span>
          文化有源 · 寻迹有据
        </div>
      </section>
      <main class="login-main">
        <div class="login-heading">
          <span class="eyebrow">东巴寻迹 / 管理工作台</span>
          <h2>{{ setup ? '创建管理员' : '欢迎回来' }}</h2>
          <p>{{ setup ? '完成首次初始化，开启文化运营工作台。' : '登录账号，继续你的丽江文化之旅。' }}</p>
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
              <el-input
                v-model="form.display_name"
                autocomplete="name"
                placeholder="请输入管理员姓名"
                size="large"
              />
            </el-form-item>
            <el-form-item
              label="登录账号"
              prop="username"
              :rules="[{ required: true, message: '请输入账号', trigger: 'blur' }]"
            >
              <el-input
                v-model="form.username"
                :prefix-icon="User"
                autocomplete="username"
                placeholder="请输入登录账号"
                size="large"
              />
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
                :placeholder="setup ? '请设置至少12位密码' : '请输入密码'"
                :autocomplete="setup ? 'new-password' : 'current-password'"
                size="large"
              />
            </el-form-item>
            <el-form-item v-if="setup" label="初始化授权码（可选）">
              <el-input v-model="setupSecret" type="password" show-password autocomplete="off" size="large" />
            </el-form-item>
            <el-button type="primary" native-type="submit" size="large" :loading="busy" class="login-submit">
              {{ setup ? '创建并进入工作台' : '登录工作台' }}
            </el-button>
          </el-form>
          <el-button v-if="error" text class="login-retry" @click="check">重新连接</el-button>
          <p class="login-access-note">商户与运营人员使用已分配的账号登录，系统将进入对应工作空间。</p>
        </template>
      </main>
    </div>
    <footer class="login-footer">文化有源 · 寻迹有据</footer>
  </div>
</template>
