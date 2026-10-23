<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  Box,
  Collection,
  Delete,
  Edit,
  MoreFilled,
  Plus,
} from '@element-plus/icons-vue'
import { getRoom, getRoomTree, listRooms } from '../api/rooms'
import {
  createContainer,
  deleteContainer,
  moveContainer,
  updateContainer,
} from '../api/containers'
import { deleteItem, listItems } from '../api/items'
import ItemFormDialog from '../components/ItemFormDialog.vue'
import { formatDate, photoUrl, statusInfo } from '../utils/format'

const route = useRoute()
const router = useRouter()
const roomId = computed(() => Number(route.params.id))

const loading = ref(true)
const itemLoading = ref(false)
const room = ref(null)
const tree = ref([])
const selectedId = ref(null)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const itemDialogVisible = ref(false)
const editingItem = ref(null)
const rooms = ref([])

const containerDialog = reactive({
  visible: false,
  editing: null,
  parentId: null,
  name: '',
  nickname: '',
  code: '',
  description: '',
  saving: false,
})
const containerRef = ref()

const moveDialog = reactive({
  visible: false,
  container: null,
  targetRoomId: null,
  targetParentId: null,
  tree: [],
  saving: false,
})

function findPath(nodes, id, prefix = []) {
  for (const node of nodes) {
    const path = [...prefix, node.display_name || node.name]
    if (node.id === id) return path
    if (node.children?.length) {
      const found = findPath(node.children, id, path)
      if (found) return found
    }
  }
  return null
}

const selectedPath = computed(() =>
  selectedId.value ? findPath(tree.value, selectedId.value) : null,
)
const breadcrumb = computed(() => {
  if (!room.value) return []
  return [room.value.name, ...(selectedPath.value || [])]
})

async function loadRoom() {
  const [detail, treeData] = await Promise.all([
    getRoom(roomId.value),
    getRoomTree(roomId.value),
  ])
  room.value = detail.room
  tree.value = treeData.tree || []
}

async function loadItems() {
  itemLoading.value = true
  try {
    const params = {
      room_id: roomId.value,
      page: page.value,
      page_size: pageSize.value,
    }
    if (selectedId.value) params.container_id = selectedId.value
    const data = await listItems(params)
    items.value = data.items
    total.value = data.total
  } finally {
    itemLoading.value = false
  }
}

async function loadAll() {
  loading.value = true
  try {
    await loadRoom()
    await loadItems()
  } finally {
    loading.value = false
  }
}

function selectNode(data) {
  selectedId.value = data?.id ?? null
  page.value = 1
  loadItems()
}

function onPageChange(value) {
  page.value = value
  loadItems()
}

function onSizeChange(value) {
  pageSize.value = value
  page.value = 1
  loadItems()
}

function openCreateRoot() {
  Object.assign(containerDialog, {
    visible: true,
    editing: null,
    parentId: null,
    name: '',
    nickname: '',
    code: '',
    description: '',
  })
}

function openCreateChild(parent) {
  Object.assign(containerDialog, {
    visible: true,
    editing: null,
    parentId: parent.id,
    name: '',
    nickname: '',
    code: '',
    description: '',
  })
}

function openEditContainer(node) {
  Object.assign(containerDialog, {
    visible: true,
    editing: node,
    parentId: node.parent_id,
    name: node.name,
    nickname: node.nickname || '',
    code: node.code || '',
    description: node.description || '',
  })
}

async function submitContainer() {
  containerDialog.saving = true
  try {
    if (containerDialog.editing) {
      await updateContainer(containerDialog.editing.id, {
        name: containerDialog.name,
        nickname: containerDialog.nickname,
        code: containerDialog.code,
        description: containerDialog.description,
      })
      ElMessage.success('容器已更新')
    } else {
      await createContainer({
        room_id: roomId.value,
        name: containerDialog.name,
        nickname: containerDialog.nickname,
        parent_id: containerDialog.parentId,
        code: containerDialog.code,
        description: containerDialog.description,
      })
      ElMessage.success('容器已创建')
    }
    containerDialog.visible = false
    await loadRoom()
  } finally {
    containerDialog.saving = false
  }
}

async function removeContainer(node) {
  await ElMessageBox.confirm(
    `确定删除容器「${node.name}」吗？容器内必须没有子容器和物品。`,
    '删除容器',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await deleteContainer(node.id)
  ElMessage.success('容器已删除')
  if (selectedId.value === node.id) selectedId.value = null
  await loadRoom()
  await loadItems()
}

async function openMove(node) {
  Object.assign(moveDialog, {
    visible: true,
    container: node,
    targetRoomId: roomId.value,
    targetParentId: null,
    tree: [],
  })
  if (!rooms.value.length) rooms.value = await listRooms()
  await loadMoveTree(roomId.value)
}

async function loadMoveTree(targetRoomId) {
  if (!targetRoomId) {
    moveDialog.tree = []
    return
  }
  const data = await getRoomTree(targetRoomId)
  moveDialog.tree = data.tree || []
}

async function submitMove() {
  if (!moveDialog.targetRoomId) {
    ElMessage.warning('请选择目标房间')
    return
  }
  moveDialog.saving = true
  try {
    await moveContainer(moveDialog.container.id, {
      target_room_id: moveDialog.targetRoomId,
      target_parent_id: moveDialog.targetParentId || null,
    })
    ElMessage.success('容器已移动')
    moveDialog.visible = false
    await loadRoom()
    await loadItems()
  } finally {
    moveDialog.saving = false
  }
}

function onContainerCommand(command, node) {
  if (command === 'add-child') openCreateChild(node)
  if (command === 'edit') openEditContainer(node)
  if (command === 'move') openMove(node)
  if (command === 'delete') removeContainer(node)
}

function openCreateItem() {
  editingItem.value = null
  itemDialogVisible.value = true
}

function openEditItem(row) {
  editingItem.value = row
  itemDialogVisible.value = true
}

async function onItemSaved() {
  await loadRoom()
  await loadItems()
}

async function removeItem(row) {
  await ElMessageBox.confirm(`确定删除物品「${row.name}」吗？`, '删除物品', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await deleteItem(row.id)
  ElMessage.success('物品已删除')
  await loadRoom()
  await loadItems()
}

onMounted(loadAll)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-head">
      <div>
        <el-button text :icon="ArrowLeft" class="back-btn" @click="router.push('/rooms')">
          返回房间列表
        </el-button>
        <h1 class="page-title room-title">
          <span
            v-if="room"
            class="room-dot"
            :style="{ background: room.color || '#2f7d6d' }"
          />
          {{ room?.name || '房间' }}
        </h1>
        <p class="page-sub">
          {{ room?.description || '管理这个房间里的容器和物品' }}
        </p>
      </div>
      <div class="toolbar">
        <el-button :icon="Plus" @click="openCreateRoot">添加容器</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreateItem">新增物品</el-button>
      </div>
    </div>

    <div class="detail-layout">
      <aside class="panel tree-panel">
        <div class="panel-head">
          <span class="panel-title">容器结构</span>
          <el-button text size="small" :icon="Plus" @click="openCreateRoot">顶层</el-button>
        </div>

        <button
          class="all-items"
          :class="{ active: !selectedId }"
          @click="selectNode(null)"
        >
          <span><el-icon><Box /></el-icon> 全部物品</span>
          <span class="count">{{ room?.item_count ?? 0 }}</span>
        </button>

        <el-tree
          v-if="tree.length"
          :data="tree"
          node-key="id"
          :props="{ label: 'display_name', children: 'children' }"
          highlight-current
          :current-node-key="selectedId"
          :expand-on-click-node="false"
          default-expand-all
          @node-click="selectNode"
        >
          <template #default="{ data }">
            <div class="tree-node">
              <span class="tree-label">
                <el-icon class="tree-icon"><Collection /></el-icon>
                <span class="tree-name">{{ data.name }}</span>
                <span v-if="data.nickname" class="tree-nick">{{ data.nickname }}</span>
                <span v-if="data.item_count" class="tree-count">{{ data.item_count }}</span>
              </span>
              <el-dropdown
                trigger="click"
                @click.stop
                @command="(command) => onContainerCommand(command, data)"
              >
                <el-button text circle size="small" class="node-more" @click.stop>
                  <el-icon><MoreFilled /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="add-child">添加子容器</el-dropdown-item>
                    <el-dropdown-item command="edit">编辑</el-dropdown-item>
                    <el-dropdown-item command="move">移动</el-dropdown-item>
                    <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-tree>

        <div v-else class="tree-empty">
          <el-icon :size="26"><Collection /></el-icon>
          <p>还没有容器</p>
          <el-button size="small" :icon="Plus" @click="openCreateRoot">创建第一个容器</el-button>
        </div>

        <div class="tree-tip">
          容器可以无限嵌套，例如「衣柜 / 顶层收纳盒」。也可以起昵称，例如「柜子A」的昵称设为「药柜」。
        </div>
      </aside>

      <section class="panel items-panel">
        <div class="panel-head">
          <div>
            <div class="panel-title">
              {{ selectedId ? selectedPath?.[selectedPath.length - 1] : '房间内全部物品' }}
            </div>
            <el-breadcrumb separator="/" class="crumb">
              <el-breadcrumb-item v-for="(part, index) in breadcrumb" :key="index">
                {{ part }}
              </el-breadcrumb-item>
            </el-breadcrumb>
          </div>
          <el-tag effect="plain" type="info">共 {{ total }} 件</el-tag>
        </div>

        <el-table v-loading="itemLoading" :data="items" style="width: 100%">
          <el-table-column label="物品" min-width="220">
            <template #default="{ row }">
              <div class="item-cell">
                <div class="item-thumb">
                  <img v-if="row.primary_photo" :src="photoUrl(row.primary_photo)" alt="" />
                  <el-icon v-else><Box /></el-icon>
                </div>
                <div style="min-width: 0">
                  <div class="item-name">{{ row.name }}</div>
                  <div class="item-desc">{{ row.location_path }}</div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="分类" width="120">
            <template #default="{ row }">
              <span v-if="row.category" class="soft-tag">{{ row.category.name }}</span>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="标签" min-width="140">
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
          <el-table-column label="数量" width="80" align="center">
            <template #default="{ row }">{{ row.quantity }}{{ row.unit }}</template>
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
              <span class="muted">{{ formatDate(row.updated_at, 'MM-DD HH:mm') }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="110" fixed="right">
            <template #default="{ row }">
              <el-button text size="small" :icon="Edit" @click="openEditItem(row)" />
              <el-button
                text
                size="small"
                type="danger"
                :icon="Delete"
                @click="removeItem(row)"
              />
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="这个位置还没有物品" :image-size="72">
              <el-button type="primary" size="small" @click="openCreateItem">添加物品</el-button>
            </el-empty>
          </template>
        </el-table>

        <div class="pager">
          <el-pagination
            :current-page="page"
            :page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            background
            @current-change="onPageChange"
            @size-change="onSizeChange"
          />
        </div>
      </section>
    </div>

    <ItemFormDialog
      v-model="itemDialogVisible"
      :item="editingItem"
      :default-room-id="roomId"
      :default-container-id="selectedId"
      @saved="onItemSaved"
    />

    <el-dialog
      v-model="containerDialog.visible"
      :title="containerDialog.editing ? '编辑容器' : '新增容器'"
      width="460px"
      :close-on-click-modal="false"
    >
      <el-form label-position="top">
        <el-form-item label="容器名称" required>
          <el-input v-model="containerDialog.name" placeholder="例如：柜子A、上层抽屉" maxlength="80" />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input
            v-model="containerDialog.nickname"
            placeholder="可选，例如：药柜、换季衣物"
            maxlength="80"
          />
        </el-form-item>
        <el-form-item label="位置编码">
          <el-input v-model="containerDialog.code" placeholder="可选，例如 A-01" maxlength="40" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="containerDialog.description" type="textarea" :rows="3" />
        </el-form-item>
        <div v-if="!containerDialog.editing && containerDialog.parentId" class="parent-hint">
          将创建在当前选中容器的下一级
        </div>
      </el-form>
      <template #footer>
        <el-button @click="containerDialog.visible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="containerDialog.saving"
          :disabled="!containerDialog.name.trim()"
          @click="submitContainer"
        >
          保存
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="moveDialog.visible" title="移动容器" width="460px">
      <el-form label-position="top">
        <el-form-item label="目标房间" required>
          <el-select
            v-model="moveDialog.targetRoomId"
            style="width: 100%"
            @change="(value) => { moveDialog.targetParentId = null; loadMoveTree(value) }"
          >
            <el-option v-for="item in rooms" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标父容器">
          <el-tree-select
            v-model="moveDialog.targetParentId"
            :data="moveDialog.tree"
            :props="{ label: 'display_name', children: 'children' }"
            node-key="id"
            check-strictly
            clearable
            default-expand-all
            placeholder="留空表示放到房间顶层"
            style="width: 100%"
          />
        </el-form-item>
        <div class="parent-hint">
          移动会连同所有子容器和其中的物品一起迁移。
        </div>
      </el-form>
      <template #footer>
        <el-button @click="moveDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="moveDialog.saving" @click="submitMove">
          确认移动
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.back-btn {
  padding-left: 0;
  margin-bottom: 8px;
  color: var(--muted);
}

.room-title {
  display: flex;
  align-items: center;
  gap: 9px;
}

.room-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.detail-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.tree-panel {
  position: sticky;
  top: 0;
}

.all-items {
  width: 100%;
  border: 1px solid var(--line);
  background: #fbfdfc;
  border-radius: 10px;
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-family: inherit;
  font-size: 13px;
  color: var(--ink-2);
  cursor: pointer;
  margin-bottom: 10px;
  transition: all 0.15s;
}

.all-items span:first-child {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.all-items:hover,
.all-items.active {
  border-color: var(--brand-line);
  background: var(--brand-soft);
  color: var(--brand-deep);
}

.all-items .count {
  font-size: 12px;
  color: var(--muted);
}

.tree-node {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-width: 0;
  padding-right: 4px;
}

.tree-label {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  font-size: 13px;
}

.tree-icon {
  color: #7fa79c;
  font-size: 14px;
}

.tree-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-nick {
  flex-shrink: 0;
  max-width: 96px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  color: var(--muted);
}

.tree-count {
  background: #eef4f2;
  color: var(--brand-deep);
  font-size: 10.5px;
  padding: 0 6px;
  border-radius: 999px;
  line-height: 17px;
}

.node-more {
  opacity: 0;
  transition: opacity 0.15s;
}

.tree-node:hover .node-more {
  opacity: 1;
}

.tree-empty {
  text-align: center;
  color: var(--muted);
  padding: 26px 0 18px;
  font-size: 12.5px;
}

.tree-empty p {
  margin: 8px 0 12px;
}

.tree-tip {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed var(--line);
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.7;
}

.items-panel {
  min-width: 0;
}

.crumb {
  margin-top: 7px;
  font-size: 11.5px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.parent-hint {
  font-size: 11.5px;
  color: var(--muted);
  background: #f7faf9;
  border-radius: 8px;
  padding: 9px 12px;
}

:deep(.el-tree-node__content) {
  height: 38px;
  border-radius: 8px;
}

:deep(.el-tree-node__content:hover) {
  background: #f5faf8;
}

:deep(.el-tree-node.is-current > .el-tree-node__content) {
  background: var(--brand-soft);
}

@media (max-width: 1000px) {
  .detail-layout {
    grid-template-columns: 1fr;
  }
  .tree-panel {
    position: static;
  }
}
</style>
