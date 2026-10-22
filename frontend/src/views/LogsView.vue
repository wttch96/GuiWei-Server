<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { listLogs } from '../api/logs'
import { formatDate, prettyJson } from '../utils/format'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filters = reactive({
  entity_type: '',
  source: '',
})

const ENTITY_OPTIONS = [
  { value: 'room', label: '房间' },
  { value: 'container', label: '容器' },
  { value: 'item', label: '物品' },
  { value: 'category', label: '分类' },
  { value: 'tag', label: '标签' },
  { value: 'photo', label: '照片' },
]

const SOURCE_OPTIONS = [
  { value: 'api', label: '后台操作' },
  { value: 'ai', label: 'AI 操作' },
  { value: 'system', label: '系统' },
]

const ACTION_LABELS = {
  create: '创建',
  update: '更新',
  delete: '删除',
  move: '移动',
  upload: '上传',
  attach: '关联',
  set_primary: '设为主图',
  set_tags: '设置标签',
}

function entityLabel(type) {
  return ENTITY_OPTIONS.find((item) => item.value === type)?.label || type || '—'
}

function sourceLabel(source) {
  return SOURCE_OPTIONS.find((item) => item.value === source)?.label || source || '—'
}

function actionLabel(action) {
  return ACTION_LABELS[action] || action
}

function sourceType(source) {
  if (source === 'ai') return 'primary'
  if (source === 'system') return 'info'
  return 'success'
}

function detailSummary(detail) {
  if (!detail || !Object.keys(detail).length) return '—'
  return Object.entries(detail)
    .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : value}`)
    .join(' · ')
}

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filters.entity_type) params.entity_type = filters.entity_type
    if (filters.source) params.source = filters.source
    const data = await listLogs(params)
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function onPageChange(value) {
  page.value = value
  load()
}

function onSizeChange(value) {
  pageSize.value = value
  page.value = 1
  load()
}

function reset() {
  filters.entity_type = ''
  filters.source = ''
  page.value = 1
  load()
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">操作日志</h1>
        <p class="page-sub">记录后台与 AI 对数据的每一次改动，方便回溯</p>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <section class="panel filter-panel">
      <div class="toolbar">
        <el-select
          v-model="filters.entity_type"
          placeholder="全部对象"
          clearable
          style="width: 140px"
          @change="search"
        >
          <el-option
            v-for="option in ENTITY_OPTIONS"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-select
          v-model="filters.source"
          placeholder="全部来源"
          clearable
          style="width: 140px"
          @change="search"
        >
          <el-option
            v-for="option in SOURCE_OPTIONS"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-button @click="reset">重置</el-button>
        <span class="spacer" />
        <span class="muted total-hint">共 {{ total }} 条记录</span>
      </div>
    </section>

    <section class="panel panel--flush">
      <el-table v-loading="loading" :data="rows" style="width: 100%">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="log-detail">
              <pre class="mono">{{ prettyJson(row.detail) }}</pre>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="165">
          <template #default="{ row }">
            <span class="mono time-cell">{{ formatDate(row.created_at, 'YYYY-MM-DD HH:mm:ss') }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="sourceType(row.source)">
              {{ sourceLabel(row.source) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110">
          <template #default="{ row }">
            <span class="action-cell">{{ actionLabel(row.action) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="对象" width="150">
          <template #default="{ row }">
            <span class="soft-tag">{{ entityLabel(row.entity_type) }}</span>
            <span v-if="row.entity_id" class="muted id-cell">#{{ row.entity_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="详情" min-width="320">
          <template #default="{ row }">
            <span class="muted detail-cell">{{ detailSummary(row.detail) }}</span>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无操作记录" :image-size="76" />
        </template>
      </el-table>

      <div class="pager">
        <el-pagination
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.filter-panel {
  padding: 16px 20px;
}

.total-hint {
  font-size: 12px;
}

.time-cell {
  font-size: 11.5px;
  color: var(--ink-2);
}

.action-cell {
  font-weight: 550;
}

.id-cell {
  font-size: 11.5px;
  margin-left: 6px;
}

.detail-cell {
  font-size: 12px;
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-detail {
  padding: 10px 18px 14px 48px;
}

.log-detail pre {
  margin: 0;
  padding: 12px 14px;
  border-radius: 10px;
  background: #f7faf9;
  border: 1px solid var(--line);
  color: #344a44;
  font-size: 11.5px;
  line-height: 1.6;
  max-height: 260px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding: 16px 20px;
}
</style>
