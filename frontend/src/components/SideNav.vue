<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Box,
  Camera,
  Collection,
  DataBoard,
  Document,
  House,
  MagicStick,
  Picture,
  PriceTag,
} from '@element-plus/icons-vue'

defineProps({
  collapsed: { type: Boolean, default: false },
})
const emit = defineEmits(['navigate'])

const route = useRoute()
const router = useRouter()

const menus = [
  { path: '/dashboard', title: '收纳概览', icon: DataBoard },
  { path: '/rooms', title: '房间与容器', icon: House },
  { path: '/items', title: '物品管理', icon: Box },
  { path: '/categories', title: '物品分类', icon: Collection },
  { path: '/tags', title: '标签管理', icon: PriceTag },
  { path: '/recognize', title: '拍照识物', icon: Camera },
  { path: '/photos', title: '图片管理', icon: Picture },
  { path: '/ai', title: 'AI 收纳助手', icon: MagicStick },
  { path: '/logs', title: '操作日志', icon: Document },
]

const activeMenu = computed(() =>
  route.path.startsWith('/rooms') ? '/rooms' : route.path,
)

function go(path) {
  router.push(path)
  emit('navigate')
}
</script>

<template>
  <div class="side-nav">
    <div class="brand" @click="go('/dashboard')">
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
      @select="emit('navigate')"
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
  </div>
</template>

<style scoped>
.side-nav {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #14332c;
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
</style>
