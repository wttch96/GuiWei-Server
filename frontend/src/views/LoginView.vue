<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Box, Lock, User } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const store = useAuthStore()

const formRef = ref()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

const rules = {
  username: [{ required: true, message: '请输入管理员账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  await formRef.value.validate()
  loading.value = true
  try {
    await store.login(form)
    ElMessage.success('欢迎回来')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
    router.replace(redirect)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-shell">
    <section class="brand-panel">
      <div class="brand-top">
        <div class="logo"><el-icon :size="24"><Box /></el-icon></div>
        <div class="logo-text">
          <strong>归位</strong>
          <span>GUIWEI · SMART STORAGE</span>
        </div>
      </div>

      <div class="hero">
        <h1>让每一件物品<br />都有归处。</h1>
        <p class="hero-sub">
          房间、容器、物品，三层结构清晰可见。<br />
          拍照识物、智能分类、对话整理，都由 AI 完成。
        </p>
        <div class="feature-row">
          <div class="feature"><span>01</span>多级容器收纳</div>
          <div class="feature"><span>02</span>DeepSeek 智能分类</div>
          <div class="feature"><span>03</span>自然语言操作</div>
        </div>
      </div>

      <div class="brand-foot">AI-powered home inventory</div>
      <div class="glow glow-a" />
      <div class="glow glow-b" />
    </section>

    <section class="form-panel">
      <div class="form-card">
        <div class="form-head">
          <h2>管理员登录</h2>
          <p>使用服务器端创建的账号进入后台</p>
        </div>

        <el-form ref="formRef" :model="form" :rules="rules" size="large" @submit.prevent>
          <el-form-item prop="username">
            <el-input v-model="form.username" placeholder="管理员账号" :prefix-icon="User" />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              show-password
              placeholder="密码"
              :prefix-icon="Lock"
              @keyup.enter="submit"
            />
          </el-form-item>
          <el-button class="submit" type="primary" :loading="loading" @click="submit">
            进入后台
          </el-button>
        </el-form>

        <div class="form-hint">
          <span class="dot" />
          系统仅有一个管理员，账号与密码均加密保存在数据库中
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.login-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  background: #f6f9f8;
}

.brand-panel {
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(circle at 18% 18%, rgba(99, 179, 160, 0.35), transparent 46%),
    radial-gradient(circle at 82% 84%, rgba(47, 125, 109, 0.55), transparent 52%),
    linear-gradient(145deg, #173b33 0%, #102a24 58%, #0d211d 100%);
  color: #fff;
  padding: 44px 54px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.brand-top {
  display: flex;
  align-items: center;
  gap: 13px;
  z-index: 2;
}

.logo {
  width: 44px;
  height: 44px;
  border-radius: 13px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #65b8a4, #2f7d6d);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.28);
}

.logo-text {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.logo-text strong {
  font-size: 19px;
  letter-spacing: 0.12em;
}

.logo-text span {
  font-size: 9px;
  color: #8fb8ad;
  letter-spacing: 0.26em;
}

.hero {
  position: relative;
  z-index: 2;
  max-width: 520px;
}

.hero h1 {
  margin: 0;
  font-size: clamp(38px, 4.2vw, 60px);
  line-height: 1.18;
  font-weight: 650;
  letter-spacing: -0.03em;
}

.hero-sub {
  margin: 24px 0 34px;
  color: #a9c8bf;
  font-size: 14.5px;
  line-height: 1.9;
}

.feature-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.feature {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.05);
  color: #c7ddd7;
  font-size: 12px;
  backdrop-filter: blur(6px);
}

.feature span {
  color: #66c3ab;
  font-weight: 700;
  font-size: 10px;
  letter-spacing: 0.08em;
}

.brand-foot {
  position: relative;
  z-index: 2;
  font-size: 10px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: #5e8a7e;
}

.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(2px);
  pointer-events: none;
}

.glow-a {
  width: 420px;
  height: 420px;
  right: -160px;
  top: 16%;
  border: 1px solid rgba(255, 255, 255, 0.07);
  box-shadow: 0 0 0 70px rgba(255, 255, 255, 0.018), 0 0 0 140px rgba(255, 255, 255, 0.012);
}

.glow-b {
  width: 220px;
  height: 220px;
  left: -70px;
  bottom: 8%;
  background: radial-gradient(circle, rgba(96, 190, 166, 0.18), transparent 68%);
}

.form-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  background:
    radial-gradient(circle at 80% 10%, rgba(47, 125, 109, 0.06), transparent 40%),
    #f6f9f8;
}

.form-card {
  width: min(400px, 100%);
}

.form-head h2 {
  margin: 0;
  font-size: 26px;
  letter-spacing: -0.02em;
}

.form-head p {
  margin: 9px 0 34px;
  color: var(--muted);
  font-size: 13px;
}

.submit {
  width: 100%;
  height: 46px;
  margin-top: 6px;
  border-radius: 10px;
  font-size: 15px;
  letter-spacing: 0.06em;
  box-shadow: 0 10px 24px rgba(47, 125, 109, 0.25);
}

.form-hint {
  margin-top: 26px;
  padding-top: 20px;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 11.5px;
  display: flex;
  align-items: center;
  gap: 8px;
  line-height: 1.6;
}

.form-hint .dot {
  background: #8bb8aa;
  flex: none;
}

@media (max-width: 900px) {
  .login-shell {
    grid-template-columns: 1fr;
  }
  .brand-panel {
    display: none;
  }
  .form-panel {
    padding: 24px;
    min-height: 100vh;
  }
}
</style>
