<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Box,
  Camera,
  Collection,
  House,
  MagicStick,
  PriceTag,
  Refresh,
  TrendCharts,
} from '@element-plus/icons-vue'
import { getOverview } from '../api/stats'
import { getAiStatus } from '../api/ai'
import { formatDate, photoUrl } from '../utils/format'

const router = useRouter()
const loading = ref(true)
const stats = ref(null)
const aiStatus = ref(null)

const cards = computed(() => {
  const counts = stats.value?.counts || {}
  return [
    { key: 'rooms', label: '房间', value: counts.rooms ?? 0, icon: House, tone: '#2f7d6d' },
    { key: 'containers', label: '容器', value: counts.containers ?? 0, icon: Collection, tone: '#5b8def' },
    { key: 'items', label: '物品总数', value: counts.items ?? 0, icon: Box, tone: '#e6a23c' },
    { key: 'quantity', label: '物品件数', value: stats.value?.quantity_total ?? 0, icon: TrendCharts, tone: '#9b59b6' },
  ]
})

const roomRows = computed(() => {
  const rows = stats.value?.items_by_room || []
  const max = Math.max(1, ...rows.map((row) => row.count))
  return rows.map((row) => ({
    ...row,
    percent: Math.round((row.count / max) * 100),
  }))
})

const chatReady = computed(() => Boolean(aiStatus.value?.chat_configured))
const visionReady = computed(() => Boolean(aiStatus.value?.vision?.configured))

async function load() {
  loading.value = true
  try {
    const [overview, status] = await Promise.all([
      getOverview(),
      getAiStatus().catch(() => null),
    ])
    stats.value = overview
    aiStatus.value = status
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-head">
      <div>
        <h1 class="page-title">收纳概览</h1>
        <p class="page-sub">房间、容器与物品的全景视图</p>
      </div>
      <div class="toolbar">
        <el-button :icon="Refresh" @click="load">刷新</el-button>
        <el-button :icon="Camera" @click="router.push('/recognize')">拍照识物</el-button>
        <el-button type="primary" :icon="Box" @click="router.push('/items?new=1')">
          新增物品
        </el-button>
      </div>
    </div>

    <div class="stat-grid">
      <div v-for="card in cards" :key="card.key" class="stat-card">
        <div class="stat-icon" :style="{ background: card.tone + '18', color: card.tone }">
          <el-icon><component :is="card.icon" /></el-icon>
        </div>
        <div class="stat-value">{{ card.value }}</div>
        <div class="stat-label">{{ card.label }}</div>
      </div>
    </div>

    <div class="two-col">
      <section class="panel">
        <div class="panel-head">
          <span class="panel-title">房间物品分布</span>
          <el-button text size="small" @click="router.push('/rooms')">管理房间 →</el-button>
        </div>
        <div v-if="roomRows.length" class="room-list">
          <div v-for="row in roomRows" :key="row.id" class="room-row" @click="router.push(`/rooms/${row.id}`)">
            <div class="room-label">
              <span class="room-dot" :style="{ background: row.color || '#2f7d6d' }" />
              <span>{{ row.name }}</span>
            </div>
            <div class="room-bar">
              <div
                class="room-bar-inner"
                :style="{ width: row.percent + '%', background: row.color || '#2f7d6d' }"
              />
            </div>
            <span class="room-count">{{ row.count }}</span>
          </div>
        </div>
        <el-empty v-else description="还没有房间，先创建一个吧" :image-size="80">
          <el-button type="primary" @click="router.push('/rooms')">去创建</el-button>
        </el-empty>
      </section>

      <section class="panel ai-panel">
        <div class="panel-head">
          <span class="panel-title">AI 助手</span>
          <el-button text size="small" @click="router.push('/ai')">打开对话 →</el-button>
        </div>

        <div class="ai-status">
          <div class="ai-orb"><el-icon><MagicStick /></el-icon></div>
          <div>
            <div class="ai-title">{{ chatReady ? 'DeepSeek 已就绪' : '等待配置对话模型' }}</div>
            <div class="ai-sub">
              {{ chatReady ? aiStatus?.model || 'deepseek-chat' : '在 backend/.env 配置 DEEPSEEK_API_KEY' }}
            </div>
          </div>
        </div>

        <div class="ai-checks">
          <div class="check-row">
            <span class="dot" :class="{ off: !chatReady }" />
            对话与工具调用
            <el-tag size="small" :type="chatReady ? 'success' : 'info'" effect="plain">
              {{ chatReady ? '可用' : '未配置' }}
            </el-tag>
          </div>
          <div class="check-row">
            <span class="dot" :class="{ off: !visionReady }" />
            拍照识图
            <el-tag size="small" :type="visionReady ? 'success' : 'info'" effect="plain">
              {{ visionReady ? '可用' : '未配置' }}
            </el-tag>
          </div>
        </div>

        <div class="quick-grid">
          <button class="quick" @click="router.push('/rooms')">
            <el-icon><House /></el-icon><span>房间与容器</span>
          </button>
          <button class="quick" @click="router.push('/items')">
            <el-icon><Box /></el-icon><span>物品管理</span>
          </button>
          <button class="quick" @click="router.push('/categories')">
            <el-icon><Collection /></el-icon><span>分类</span>
          </button>
          <button class="quick" @click="router.push('/tags')">
            <el-icon><PriceTag /></el-icon><span>标签</span>
          </button>
        </div>
      </section>
    </div>

    <section class="panel">
      <div class="panel-head">
        <span class="panel-title">最近更新</span>
        <el-button text size="small" @click="router.push('/items')">查看全部 →</el-button>
      </div>
      <el-table
        v-if="stats?.recent_items?.length"
        :data="stats.recent_items"
        style="width: 100%"
        @row-click="(row) => router.push(`/items?edit=${row.id}`)"
      >
        <el-table-column label="物品" min-width="240">
          <template #default="{ row }">
            <div class="item-cell">
              <div class="item-thumb">
                <img v-if="row.primary_photo" :src="photoUrl(row.primary_photo)" alt="" />
                <el-icon v-else><Box /></el-icon>
              </div>
              <div style="min-width: 0">
                <div class="item-name">{{ row.name }}</div>
                <div class="item-desc">{{ row.description || '暂无描述' }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="位置" min-width="200">
          <template #default="{ row }">
            <span class="muted">{{ row.location_path }}</span>
          </template>
        </el-table-column>
        <el-table-column label="分类" width="130">
          <template #default="{ row }">
            <span v-if="row.category" class="soft-tag">{{ row.category.name }}</span>
            <span v-else class="muted">未分类</span>
          </template>
        </el-table-column>
        <el-table-column label="标签" min-width="160">
          <template #default="{ row }">
            <el-tag
              v-for="tag in row.tags"
              :key="tag.id"
              size="small"
              effect="plain"
              :style="{ marginRight: '4px', borderColor: tag.color, color: tag.color }"
            >
              {{ tag.name }}
            </el-tag>
            <span v-if="!row.tags.length" class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="更新于" width="150" align="right">
          <template #default="{ row }">
            <span class="muted">{{ formatDate(row.updated_at) }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="还没有物品" :image-size="80">
        <el-button type="primary" @click="router.push('/items?new=1')">添加第一件物品</el-button>
      </el-empty>
    </section>
  </div>
</template>

<style scoped>
.two-col {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);
  gap: 18px;
}

.room-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.room-row {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr) 42px;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 8px;
  transition: background 0.15s;
}

.room-row:hover {
  background: #f7faf9;
}

.room-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.room-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: none;
}

.room-bar {
  height: 8px;
  border-radius: 999px;
  background: #f0f4f2;
  overflow: hidden;
}

.room-bar-inner {
  height: 100%;
  border-radius: 999px;
  min-width: 3px;
  transition: width 0.3s;
}

.room-count {
  text-align: right;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-2);
}

.ai-panel {
  display: flex;
  flex-direction: column;
}

.ai-status {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border-radius: 14px;
  background: linear-gradient(120deg, #f0f7f5, #f8fbfa);
  border: 1px solid var(--brand-line);
}

.ai-orb {
  width: 44px;
  height: 44px;
  border-radius: 13px;
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 20px;
  background: linear-gradient(135deg, #5fae9b, #2f7d6d);
  box-shadow: 0 8px 20px rgba(47, 125, 109, 0.25);
  flex: none;
}

.ai-title {
  font-weight: 600;
  font-size: 14px;
}

.ai-sub {
  color: var(--muted);
  font-size: 11.5px;
  margin-top: 4px;
  word-break: break-all;
}

.ai-checks {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  margin: 16px 2px 18px;
}

.check-row {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12.5px;
  color: var(--ink-2);
}

.dot.off {
  background: #c8d1ce;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-top: auto;
}

.quick {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 11px;
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--ink-2);
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;
}

.quick:hover {
  border-color: var(--brand-line);
  background: var(--brand-soft);
  color: var(--brand-deep);
}

.quick .el-icon {
  font-size: 17px;
  color: var(--brand);
}

:deep(.el-table__row) {
  cursor: pointer;
}

@media (max-width: 1000px) {
  .two-col {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .quick-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .room-row {
    grid-template-columns: 90px 1fr 32px;
  }
}
</style>
