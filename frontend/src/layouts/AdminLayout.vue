<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowDown, Expand, Fold, MagicStick } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import { changePassword } from '../api/auth'
import SideNav from '../components/SideNav.vue'

const route = useRoute()
const router = useRouter()
const store = useAuthStore()

const mobileQuery = '(max-width: 767px)'
const isMobile = ref(window.matchMedia(mobileQuery).matches)
const mobileNav = ref(false)
const collapsed = ref(window.innerWidth < 1024)
const pwdVisible = ref(false)
const pwdSaving = ref(false)
const pwdRef = ref()
const pwdForm = reactive({ old_password: '', new_password: '', confirm: '' })

const pageTitle = computed(() => route.meta.title || '管理后台')
const initial = computed(() => (store.adminName || '管').slice(0, 1))

const validateConfirm = (_rule, value, callback) => {
  if (!value) return callback(new Error('请再次输入新密码'))
  if (value !== pwdForm.new_password) return callback(new Error('两次输入的密码不一致'))
  callback()
}

const pwdRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirm: [{ validator: validateConfirm, trigger: 'blur' }],
}

function openPassword() {
  Object.assign(pwdForm, { old_password: '', new_password: '', confirm: '' })
  pwdVisible.value = true
}

async function submitPassword() {
  await pwdRef.value.validate()
  pwdSaving.value = true
  try {
    await changePassword({
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password,
    })
    ElMessage.success('密码已更新')
    pwdVisible.value = false
  } finally {
    pwdSaving.value = false
  }
}

function onCommand(command) {
  if (command === 'password') openPassword()
  if (command === 'logout') {
    store.logout()
    router.replace('/login')
  }
}

let lastDesktop = window.innerWidth >= 1024

function onResize() {
  const mobile = window.matchMedia(mobileQuery).matches
  if (mobile !== isMobile.value) {
    isMobile.value = mobile
    mobileNav.value = false
  }
  const desktop = window.innerWidth >= 1024
  if (desktop !== lastDesktop) {
    collapsed.value = !desktop
    lastDesktop = desktop
  }
}

function toggleNav() {
  if (isMobile.value) mobileNav.value = true
  else collapsed.value = !collapsed.value
}

onMounted(() => {
  window.addEventListener('resize', onResize)
  if (!store.admin) store.fetchMe().catch(() => {})
})

onBeforeUnmount(() => window.removeEventListener('resize', onResize))

watch(
  () => route.path,
  () => {
    mobileNav.value = false
  },
)
</script>

<template>
  <el-container class="admin-shell">
    <el-aside v-if="!isMobile" :width="collapsed ? '72px' : '238px'" class="aside">
      <SideNav :collapsed="collapsed" />
    </el-aside>

    <el-drawer
      v-model="mobileNav"
      direction="ltr"
      size="248px"
      :with-header="false"
      class="mobile-nav-drawer"
      append-to-body
    >
      <SideNav @navigate="mobileNav = false" />
    </el-drawer>

    <el-container class="body">
      <el-header class="topbar" height="66px">
        <div class="topbar-left">
          <el-button text circle @click="toggleNav">
            <el-icon :size="18">
              <Expand v-if="isMobile || collapsed" />
              <Fold v-else />
            </el-icon>
          </el-button>
          <div>
            <div class="page-crumb">{{ pageTitle }}</div>
            <div class="page-crumb-sub">智能收纳 · 管理后台</div>
          </div>
        </div>
        <div class="topbar-right">
          <el-button circle class="ai-btn" @click="router.push('/ai')">
            <el-icon><MagicStick /></el-icon>
          </el-button>
          <el-dropdown trigger="click" @command="onCommand">
            <span class="user-chip">
              <el-avatar :size="30" class="avatar">{{ initial }}</el-avatar>
              <span class="user-name">{{ store.adminName }}</span>
              <el-icon class="muted"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>

    <el-dialog v-model="pwdVisible" title="修改密码" width="420px" append-to-body>
      <el-form ref="pwdRef" :model="pwdForm" :rules="pwdRules" label-position="top">
        <el-form-item label="原密码" prop="old_password">
          <el-input v-model="pwdForm.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="pwdForm.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm">
          <el-input v-model="pwdForm.confirm" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="pwdSaving" @click="submitPassword">
          保存
        </el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<style scoped>
.admin-shell {
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
}

.aside {
  background: #14332c;
  transition: width 0.2s ease;
  overflow: hidden;
}

.body {
  min-width: 0;
}

.topbar {
  background: #fff;
  border-bottom: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex: none;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-crumb {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.2;
}

.page-crumb-sub {
  font-size: 11px;
  color: var(--muted);
  margin-top: 3px;
  letter-spacing: 0.02em;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.ai-btn {
  color: var(--brand);
  border-color: var(--brand-line);
  background: var(--brand-soft);
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px 4px 4px;
  border-radius: 999px;
  transition: background 0.15s;
}

.user-chip:hover {
  background: #f4f8f6;
}

.avatar {
  background: var(--brand);
  font-size: 13px;
}

.user-name {
  font-size: 13px;
  color: var(--ink-2);
}

.main {
  padding: 24px;
  overflow-y: auto;
  background: var(--bg);
}

@media (max-width: 640px) {
  .topbar {
    padding: 0 12px;
  }
  .main {
    padding: 14px 12px;
  }
  .user-name {
    display: none;
  }
  .page-crumb-sub {
    display: none;
  }
  .topbar-right {
    gap: 8px;
  }
}
</style>
