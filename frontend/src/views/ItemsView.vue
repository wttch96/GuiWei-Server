<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Box, Delete, Edit, Plus, Refresh, Search } from '@element-plus/icons-vue'
import { listItems, deleteItem, getItem } from '../api/items'
import { listRooms } from '../api/rooms'
import { listCategories } from '../api/categories'
import { listTags } from '../api/tags'
import ItemFormDialog from '../components/ItemFormDialog.vue'
import {
  COLOR_FAMILIES,
  STATUS_OPTIONS,
  formatDate,
  isExpired,
  photoUrl,
  statusInfo,
} from '../utils/format'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const rooms = ref([])
const categories = ref([])
const tags = ref([])
const dialogVisible = ref(false)
const dialogItem = ref(null)

const filters = reactive({
  q: '',
  room_id: null,
  category_id: null,
  tag_id: null,
  status: '',
  color_family: '',
})

async function loadOptions() {
  const [roomList, categoryList, tagList] = await Promise.all([
    listRooms(),
    listCategories(),
    listTags(),
  ])
  rooms.value = roomList
  categories.value = categoryList
  tags.value = tagList
}

async function load() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      sort: 'updated_at',
      order: 'desc',
    }
    if (filters.q) params.q = filters.q
    if (filters.room_id) params.room_id = filters.room_id
    if (filters.category_id) params.category_id = filters.category_id
    if (filters.tag_id) params.tag_id = filters.tag_id
    if (filters.status) params.status = filters.status
    if (filters.color_family) params.color_family = filters.color_family
    const data = await listItems(params)
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  Object.assign(filters, {
    q: '',
    room_id: null,
    category_id: null,
    tag_id: null,
    status: '',
    color_family: '',
  })
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

function openCreate() {
  dialogItem.value = null
  dialogVisible.value = true
}

function openEdit(row) {
  dialogItem.value = row
  dialogVisible.value = true
}

async function onSaved() {
  await load()
}

async function remove(row) {
  await ElMessageBox.confirm(
    `确定删除物品「${row.name}」吗？关联的照片也会一起删除。`,
    '删除物品',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await deleteItem(row.id)
  ElMessage.success('物品已删除')
  if (items.value.length === 1 && page.value > 1) page.value -= 1
  await load()
}

async function handleQuery() {
  const { q, new: isNew, edit } = route.query
  let consumed = false
  if (typeof q === 'string' && q) {
    filters.q = q
    page.value = 1
    await load()
    consumed = true
  }
  if (isNew) {
    openCreate()
    consumed = true
  }
  if (edit) {
    const detail = await getItem(Number(edit))
    openEdit(detail)
    consumed = true
  }
  if (consumed) router.replace({ path: '/items' })
}

onMounted(async () => {
  await loadOptions()
  await load()
  await handleQuery()
})

watch(
  () => route.query,
  (value, oldValue) => {
    if (value !== oldValue) handleQuery()
  },
)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">物品管理</h1>
        <p class="page-sub">按名称、房间、分类、标签快速找到物品</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增物品</el-button>
    </div>

    <section class="panel filter-panel">
      <div class="toolbar">
        <el-input
          v-model="filters.q"
          placeholder="搜索名称、描述、分类、标签、色系"
          :prefix-icon="Search"
          clearable
          style="width: 260px"
          @keyup.enter="search"
          @clear="search"
        />
        <el-select v-model="filters.room_id" placeholder="全部房间" clearable style="width: 140px">
          <el-option v-for="room in rooms" :key="room.id" :label="room.name" :value="room.id" />
        </el-select>
        <el-select
          v-model="filters.category_id"
          placeholder="全部分类"
          clearable
          style="width: 140px"
        >
          <el-option
            v-for="category in categories"
            :key="category.id"
            :label="category.name"
            :value="category.id"
          />
        </el-select>
        <el-select v-model="filters.tag_id" placeholder="全部标签" clearable style="width: 130px">
          <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
        </el-select>
        <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 120px">
          <el-option
            v-for="status in STATUS_OPTIONS"
            :key="status.value"
            :label="status.label"
            :value="status.value"
          />
        </el-select>
        <el-select
          v-model="filters.color_family"
          placeholder="全部色系"
          clearable
          style="width: 120px"
        >
          <el-option
            v-for="color in COLOR_FAMILIES"
            :key="color"
            :label="color"
            :value="color"
          />
        </el-select>
        <el-button type="primary" :icon="Search" @click="search">查询</el-button>
        <el-button :icon="Refresh" @click="reset">重置</el-button>
      </div>
    </section>

    <section class="panel panel--flush">
      <el-table v-loading="loading" :data="items" style="width: 100%">
        <el-table-column label="物品" min-width="260">
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
        <el-table-column label="位置" min-width="190">
          <template #default="{ row }">
            <span class="muted">{{ row.location_path }}</span>
          </template>
        </el-table-column>
        <el-table-column label="分类" width="120">
          <template #default="{ row }">
            <span v-if="row.category" class="soft-tag">{{ row.category.name }}</span>
            <span v-else class="muted">未分类</span>
          </template>
        </el-table-column>
        <el-table-column label="色系" width="90">
          <template #default="{ row }">
            <span v-if="row.color_family" class="soft-tag">{{ row.color_family }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="过期时间" width="140">
          <template #default="{ row }">
            <template v-if="row.expiry_date">
              <span :class="{ expired: isExpired(row.expiry_date) }">
                {{ row.expiry_date }}
              </span>
              <el-tag
                v-if="isExpired(row.expiry_date)"
                size="small"
                type="danger"
                effect="plain"
                style="margin-left: 4px"
              >
                已过期
              </el-tag>
            </template>
            <span v-else class="muted">—</span>
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
        <el-table-column label="数量" width="90" align="center">
          <template #default="{ row }">{{ row.quantity }} {{ row.unit }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="statusInfo(row.status).type" effect="light">
              {{ statusInfo(row.status).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新于" width="140">
          <template #default="{ row }">
            <span class="muted">{{ formatDate(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button text size="small" :icon="Edit" @click="openEdit(row)" />
            <el-button text size="small" type="danger" :icon="Delete" @click="remove(row)" />
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="没有找到物品" :image-size="76">
            <el-button type="primary" size="small" @click="openCreate">添加物品</el-button>
          </el-empty>
        </template>
      </el-table>

      <div class="pager">
        <el-pagination
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </section>

    <ItemFormDialog v-model="dialogVisible" :item="dialogItem" @saved="onSaved" />
  </div>
</template>

<style scoped>
.filter-panel {
  padding: 16px 20px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding: 16px 20px;
}

.expired {
  color: #d9534f;
  font-weight: 600;
}
</style>
