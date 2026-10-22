<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowDown,
  Box,
  Camera,
  Collection,
  DataBoard,
  Document,
  Expand,
  Fold,
  House,
  MagicStick,
  PriceTag,
} from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import { changePassword } from '../api/auth'

const route = useRoute()
const router = useRouter()
const store = useAuthStore()

const collapsed = ref(window.innerWidth < 1024)
const pwdVisible = ref(false)
const pwdSaving = ref(false)
const pwdRef = ref()
const pwdForm = reactive({ old_password: '', new_password: '', confirm: '' })

const menus = [
  { path: '/dashboard', title: '收纳概览', icon: DataBoard },
  { path: '/rooms', title: '房间与容器', icon: House },
  { path: '/items', title: '物品管理', icon: Box },
  { path: '/categories', title: '物品分类', icon: Collection },
  { path: '/tags', title: '标签管理', icon: PriceTag },
  { path: '/recognize', title: '拍照识物', icon: Camera },
  { path: '/ai', title: 'AI 收纳助手', icon: MagicStick },
  { path: '/logs', title: '操作日志', icon: Document },
]

const activeMenu = computed(() =>
  route.path.startsWith('/rooms') ? '/rooms' : route.path,
)
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

function onResize() {
  if (window.innerWidth < 1024) collapsed.value = true
}

onMounted(() => {
  window.addEventListener('resize', onResize)
  if (!store.admin) store.fetchMe().catch(() => {})
})

onBeforeUnmount(() => window.removeEventListener('resize', onResize))
</script>

<template>
  <el-container class="admin-shell">
    <el-aside :width="collapsed ? '72px' : '238px'" class="aside">
      <div class="brand" @click="router.push('/dashboard')">
        <div class="brand-mark"><el-icon :size="20"><Box /></el-icon></div>
        <div v-show="!collapsed" class="brand-text">
          <strong>归位</strong>
          <span>GUIWEI</span>
        </div>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="false"
        router
        class="nav"
        background-color="transparent"
        text-color="#a9c2bb"
        active-text-color="#ffffff"
      >
        <el-menu-item v-for="menu in menus" :key="menu.path" :index="menu.path">
          <el-icon><component :is="menu.icon" /></el-icon>
          <template #title>{{ menu.title }}</template>
        </el-menu-item>
      </el-menu>

      <div v-show="!collapsed" class="aside-foot">
        <span class="dot" />
        <span>DeepSeek 驱动 · 全操作可对话</span>
      </div>
    </el-aside>

    <el-container class="body">
      <el-header class="topbar" height="66px">
        <div class="topbar-left">
          <el-button text circle @click="collapsed = !collapsed">
            <el-icon :size="18">
              <Expand v-if="collapsed" />
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
  overflow: hidden;
}

.aside {
  background: #14332c;
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  overflow: hidden;
}

.brand {
  height: 66px;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 0 18px;
  cursor: pointer;
  flex: none;
}

.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #4f9d8b, #2f7d6d);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.25);
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.1;
  color: #fff;
}

.brand-text strong {
  font-size: 17px;
  letter-spacing: 0.08em;
}

.brand-text span {
  font-size: 9px;
  letter-spacing: 0.32em;
  color: #8fb3a9;
  margin-top: 4px;
}

.nav {
  border-right: none;
  padding: 6px 10px;
  flex: 1;
  overflow-y: auto;
}

.nav :deep(.el-menu-item) {
  height: 46px;
  border-radius: 10px;
  margin-bottom: 4px;
  font-size: 13.5px;
}

.nav :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.06);
}

.nav :deep(.el-menu-item.is-active) {
  background: rgba(255, 255, 255, 0.12);
  font-weight: 600;
  position: relative;
}

.nav :deep(.el-menu-item.is-active)::before {
  content: '';
  position: absolute;
  left: -10px;
  top: 13px;
  bottom: 13px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: #63b3a0;
}

.nav :deep(.el-menu--collapse .el-menu-item) {
  justify-content: center;
  padding: 0 !important;
}

.aside-foot {
  flex: none;
  padding: 16px 18px 20px;
  font-size: 11.5px;
  color: #7fa399;
  display: flex;
  align-items: center;
  gap: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  margin: 0 12px;
}

.aside-foot .dot {
  background: #5ec2a8;
  box-shadow: 0 0 0 4px rgba(94, 194, 168, 0.12);
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
  .main {
    padding: 14px;
  }
  .user-name {
    display: none;
  }
  .page-crumb-sub {
    display: none;
  }
}
</style>
