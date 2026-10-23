<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Download, Picture, Refresh, Search } from '@element-plus/icons-vue'
import { batchDeletePhotos, deletePhoto, listPhotos } from '../api/photos'
import { formatBytes, formatDate, photoDownloadUrl, photoUrl } from '../utils/format'

const router = useRouter()

const loading = ref(false)
const photos = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(24)
const selected = ref([])
const summary = ref({ count: 0, size: 0, unattached_count: 0, unattached_size: 0 })

const filters = reactive({
  q: '',
  status: 'all',
  sort: 'newest',
})

const previewList = computed(() => photos.value.map((photo) => photoUrl(photo)))
const pageAllSelected = computed(
  () => photos.value.length > 0 && selected.value.length === photos.value.length,
)
const pageIndeterminate = computed(
  () => selected.value.length > 0 && selected.value.length < photos.value.length,
)

const EXT_BY_MIME = {
  'image/jpeg': 'jpg',
  'image/png': 'png',
  'image/webp': 'webp',
  'image/gif': 'gif',
}

function displayName(photo) {
  if (photo.original_name) return photo.original_name
  return `photo-${photo.id}.${EXT_BY_MIME[photo.mime_type] || 'jpg'}`
}

async function load() {
  loading.value = true
  try {
    const data = await listPhotos({
      page: page.value,
      page_size: pageSize.value,
      q: filters.q,
      status: filters.status,
      sort: filters.sort,
    })
    photos.value = data.items || []
    total.value = data.total || 0
    summary.value = data.summary || summary.value
    const visible = new Set(photos.value.map((photo) => photo.id))
    selected.value = selected.value.filter((id) => visible.has(id))
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  selected.value = []
  load()
}

function reset() {
  filters.q = ''
  filters.status = 'all'
  filters.sort = 'newest'
  search()
}

function onPageChange(value) {
  page.value = value
  selected.value = []
  load()
}

function onSizeChange(value) {
  pageSize.value = value
  page.value = 1
  selected.value = []
  load()
}

function toggleSelect(id, checked) {
  if (checked) {
    if (!selected.value.includes(id)) selected.value = [...selected.value, id]
  } else {
    selected.value = selected.value.filter((item) => item !== id)
  }
}

function togglePage(checked) {
  selected.value = checked ? photos.value.map((photo) => photo.id) : []
}

function openItem(photo) {
  if (photo.item_id) router.push(`/items?edit=${photo.item_id}`)
}

function download(photo) {
  const link = document.createElement('a')
  link.href = photoDownloadUrl(photo.id)
  link.download = displayName(photo)
  document.body.appendChild(link)
  link.click()
  link.remove()
}

async function removeOne(photo) {
  await ElMessageBox.confirm(
    `确定删除「${displayName(photo)}」吗？文件会从磁盘移除。`,
    '删除图片',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await deletePhoto(photo.id)
  ElMessage.success('图片已删除')
  if (photos.value.length === 1 && page.value > 1) page.value -= 1
  selected.value = selected.value.filter((id) => id !== photo.id)
  await load()
}

async function removeSelected() {
  const ids = [...selected.value]
  if (!ids.length) return
  await ElMessageBox.confirm(
    `确定删除选中的 ${ids.length} 张图片吗？文件会从磁盘移除，且无法恢复。`,
    '批量删除',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  const result = await batchDeletePhotos(ids)
  ElMessage.success(`已删除 ${result.deleted} 张图片`)
  const remaining = total.value - result.deleted
  if (remaining > 0 && remaining <= (page.value - 1) * pageSize.value) {
    page.value = Math.max(1, page.value - 1)
  }
  selected.value = []
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">图片管理</h1>
        <p class="page-sub">统一查看、下载与清理已上传的图片文件</p>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <section class="panel stats-panel">
      <div class="stat">
        <span class="stat-label">图片总数</span>
        <strong>{{ summary.count }}</strong>
      </div>
      <div class="stat">
        <span class="stat-label">占用空间</span>
        <strong>{{ formatBytes(summary.size) }}</strong>
      </div>
      <div class="stat">
        <span class="stat-label">未关联物品</span>
        <strong>{{ summary.unattached_count }} 张</strong>
        <span class="stat-extra">{{ formatBytes(summary.unattached_size) }}</span>
      </div>
    </section>

    <section class="panel filter-panel">
      <div class="toolbar">
        <el-input
          v-model="filters.q"
          placeholder="按文件名搜索"
          :prefix-icon="Search"
          clearable
          style="width: 220px"
          @keyup.enter="search"
          @clear="search"
        />
        <el-radio-group v-model="filters.status" @change="search">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="attached">已关联</el-radio-button>
          <el-radio-button value="unattached">未关联</el-radio-button>
        </el-radio-group>
        <el-select v-model="filters.sort" style="width: 130px" @change="search">
          <el-option label="最新上传" value="newest" />
          <el-option label="最早上传" value="oldest" />
          <el-option label="体积从大到小" value="largest" />
          <el-option label="体积从小到大" value="smallest" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="search">查询</el-button>
        <el-button :icon="Refresh" @click="reset">重置</el-button>
        <span class="spacer" />
        <el-checkbox
          :model-value="pageAllSelected"
          :indeterminate="pageIndeterminate"
          :disabled="!photos.length"
          @change="togglePage"
        >
          全选本页
        </el-checkbox>
        <el-button
          type="danger"
          plain
          :icon="Delete"
          :disabled="!selected.length"
          @click="removeSelected"
        >
          删除选中{{ selected.length ? `（${selected.length}）` : '' }}
        </el-button>
      </div>
    </section>

    <section v-loading="loading" class="panel">
      <div v-if="photos.length" class="photo-grid">
        <article
          v-for="(photo, index) in photos"
          :key="photo.id"
          class="photo-card"
          :class="{ 'is-selected': selected.includes(photo.id) }"
        >
          <div class="photo-frame">
            <el-image
              :src="photoUrl(photo)"
              fit="cover"
              :preview-src-list="previewList"
              :initial-index="index"
              preview-teleported
              hide-on-click-modal
              class="photo-img"
            />
            <el-checkbox
              class="photo-check"
              :model-value="selected.includes(photo.id)"
              @change="(checked) => toggleSelect(photo.id, checked)"
              @click.stop
            />
            <span v-if="photo.is_primary" class="primary-badge">主图</span>
          </div>
          <div class="photo-meta">
            <div class="photo-name" :title="displayName(photo)">{{ displayName(photo) }}</div>
            <div class="photo-sub">
              <span>{{ formatBytes(photo.size) }}</span>
              <span>{{ photo.width }}×{{ photo.height }}</span>
            </div>
            <div class="photo-sub">
              <span>{{ formatDate(photo.created_at) }}</span>
              <el-tag
                v-if="photo.item_name"
                size="small"
                effect="plain"
                class="item-tag"
                @click="openItem(photo)"
              >
                {{ photo.item_name }}
              </el-tag>
              <span v-else class="muted">未关联</span>
            </div>
            <div class="photo-actions">
              <el-button text size="small" :icon="Download" @click="download(photo)">
                下载
              </el-button>
              <el-button text size="small" type="danger" :icon="Delete" @click="removeOne(photo)">
                删除
              </el-button>
            </div>
          </div>
        </article>
      </div>

      <el-empty v-else-if="!loading" description="没有符合条件的图片" :image-size="86">
        <el-icon :size="22" class="empty-icon"><Picture /></el-icon>
      </el-empty>

      <div v-if="total" class="pager">
        <el-pagination
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          :page-sizes="[12, 24, 48, 96]"
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
.stats-panel {
  display: flex;
  gap: 36px;
  flex-wrap: wrap;
  padding: 16px 20px;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 12px;
  color: var(--muted);
}

.stat strong {
  font-size: 20px;
  font-weight: 650;
  letter-spacing: -0.01em;
}

.stat-extra {
  font-size: 11.5px;
  color: var(--muted);
}

.filter-panel {
  padding: 16px 20px;
}

.photo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px;
}

.photo-card {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--line);
  border-radius: 14px;
  overflow: hidden;
  background: #fff;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.photo-card:hover {
  border-color: var(--brand-line);
  box-shadow: 0 6px 20px rgba(34, 92, 80, 0.08);
}

.photo-card.is-selected {
  border-color: var(--brand);
  box-shadow: 0 0 0 2px var(--brand-soft);
}

.photo-frame {
  position: relative;
  aspect-ratio: 4 / 3;
  background: #f2f6f4;
}

.photo-img {
  width: 100%;
  height: 100%;
  display: block;
  cursor: zoom-in;
}

.photo-check {
  position: absolute;
  left: 8px;
  top: 8px;
  z-index: 1;
  padding: 2px 6px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(4px);
}

.primary-badge {
  position: absolute;
  right: 8px;
  top: 8px;
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--brand);
  color: #fff;
  font-size: 10.5px;
}

.photo-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px 8px;
  min-width: 0;
}

.photo-name {
  font-size: 12.5px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.photo-sub {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  color: var(--muted);
  min-width: 0;
}

.item-tag {
  max-width: 110px;
  cursor: pointer;
}

.item-tag :deep(.el-tag__content) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.photo-actions {
  display: flex;
  justify-content: flex-end;
  gap: 2px;
  margin-top: 2px;
  border-top: 1px dashed var(--line);
  padding-top: 4px;
}

.photo-actions :deep(.el-button) {
  padding: 2px 6px;
  height: auto;
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 18px;
}

.empty-icon {
  color: var(--brand);
}

@media (max-width: 640px) {
  .photo-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 10px;
  }
  .stats-panel {
    gap: 20px;
  }
}
</style>
