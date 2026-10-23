import { createRouter, createWebHistory } from 'vue-router'
import AdminLayout from '../layouts/AdminLayout.vue'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/',
    component: AdminLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('../views/DashboardView.vue'),
        meta: { title: '收纳概览' },
      },
      {
        path: 'rooms',
        name: 'rooms',
        component: () => import('../views/RoomsView.vue'),
        meta: { title: '房间管理' },
      },
      {
        path: 'rooms/:id',
        name: 'room-detail',
        component: () => import('../views/RoomDetailView.vue'),
        meta: { title: '房间详情' },
      },
      {
        path: 'items',
        name: 'items',
        component: () => import('../views/ItemsView.vue'),
        meta: { title: '物品管理' },
      },
      {
        path: 'categories',
        name: 'categories',
        component: () => import('../views/CategoriesView.vue'),
        meta: { title: '物品分类' },
      },
      {
        path: 'tags',
        name: 'tags',
        component: () => import('../views/TagsView.vue'),
        meta: { title: '标签管理' },
      },
      {
        path: 'ai',
        name: 'ai',
        component: () => import('../views/AiChatView.vue'),
        meta: { title: 'AI 收纳助手' },
      },
      {
        path: 'ai/prompts',
        name: 'ai-prompts',
        component: () => import('../views/AiPromptsView.vue'),
        meta: { title: 'AI 提示词' },
      },
      {
        path: 'recognize',
        name: 'recognize',
        component: () => import('../views/PhotoRecognizeView.vue'),
        meta: { title: '拍照识物' },
      },
      {
        path: 'photos',
        name: 'photos',
        component: () => import('../views/PhotosView.vue'),
        meta: { title: '图片管理' },
      },
      {
        path: 'logs',
        name: 'logs',
        component: () => import('../views/LogsView.vue'),
        meta: { title: '操作日志' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = localStorage.getItem('guiwei_token')
  if (!to.meta.public && !token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && token) {
    return { name: 'dashboard' }
  }
  document.title = `${to.meta.title || '管理后台'} · 归位`
  return true
})

export default router
