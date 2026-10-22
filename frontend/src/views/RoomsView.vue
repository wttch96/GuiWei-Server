<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Box, Collection, Edit, House, Plus } from '@element-plus/icons-vue'
import { createRoom, deleteRoom, listRooms, updateRoom } from '../api/rooms'

const router = useRouter()
const rooms = ref([])
const loading = ref(true)
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(null)
const formRef = ref()
const form = reactive({ name: '', description: '', color: '#2f7d6d' })

const rules = {
  name: [{ required: true, message: '请输入房间名称', trigger: 'blur' }],
}

async function load() {
  loading.value = true
  try {
    rooms.value = await listRooms()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, { name: '', description: '', color: '#2f7d6d' })
  dialogVisible.value = true
}

function openEdit(room) {
  editing.value = room
  Object.assign(form, {
    name: room.name,
    description: room.description || '',
    color: room.color || '#2f7d6d',
  })
  dialogVisible.value = true
}

async function submit() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (editing.value) {
      await updateRoom(editing.value.id, { ...form })
      ElMessage.success('房间已更新')
    } else {
      await createRoom({ ...form })
      ElMessage.success('房间已创建')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(room) {
  await ElMessageBox.confirm(
    `确定删除房间「${room.name}」吗？房间内必须没有容器和物品。`,
    '删除房间',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await deleteRoom(room.id)
  ElMessage.success('房间已删除')
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-head">
      <div>
        <h1 class="page-title">房间与容器</h1>
        <p class="page-sub">先创建房间，再在房间内搭建多级收纳容器</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增房间</el-button>
    </div>

    <div v-if="rooms.length" class="room-grid">
      <article
        v-for="room in rooms"
        :key="room.id"
        class="room-card"
        @click="router.push(`/rooms/${room.id}`)"
      >
        <div class="room-accent" :style="{ background: room.color }" />
        <div class="room-card-head">
          <div class="room-icon" :style="{ background: room.color + '18', color: room.color }">
            <el-icon><House /></el-icon>
          </div>
          <el-dropdown trigger="click" @click.stop>
            <el-button text circle size="small" @click.stop>
              <el-icon><Edit /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="openEdit(room)">编辑房间</el-dropdown-item>
                <el-dropdown-item divided @click="remove(room)">删除房间</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <h3 class="room-name">{{ room.name }}</h3>
        <p class="room-desc">{{ room.description || '暂无描述' }}</p>

        <div class="room-stats">
          <span><el-icon><Collection /></el-icon>{{ room.container_count }} 个容器</span>
          <span><el-icon><Box /></el-icon>{{ room.item_count }} 件物品</span>
        </div>

        <div class="room-foot">
          <span>进入房间</span>
          <span class="arrow">→</span>
        </div>
      </article>

      <button class="room-add" @click="openCreate">
        <el-icon :size="24"><Plus /></el-icon>
        <span>创建新房间</span>
      </button>
    </div>

    <section v-else class="panel">
      <el-empty description="还没有房间，从创建第一个房间开始" :image-size="90">
        <el-button type="primary" :icon="Plus" @click="openCreate">创建房间</el-button>
      </el-empty>
    </section>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑房间' : '新增房间'"
      width="460px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="房间名称" prop="name">
          <el-input v-model="form.name" placeholder="例如：客厅、卧室、书房" maxlength="80" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="这个房间主要收纳什么？"
          />
        </el-form-item>
        <el-form-item label="主题色">
          <el-color-picker v-model="form.color" />
          <span class="muted color-hint">{{ form.color }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">
          {{ editing ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.room-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 16px;
}

.room-card {
  position: relative;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 20px;
  cursor: pointer;
  overflow: hidden;
  transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
}

.room-card:hover {
  transform: translateY(-2px);
  border-color: var(--brand-line);
  box-shadow: 0 14px 32px rgba(31, 45, 42, 0.07);
}

.room-accent {
  position: absolute;
  inset: 0 0 auto 0;
  height: 4px;
}

.room-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.room-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  font-size: 19px;
}

.room-name {
  margin: 0;
  font-size: 17px;
  font-weight: 650;
}

.room-desc {
  margin: 7px 0 16px;
  color: var(--muted);
  font-size: 12.5px;
  min-height: 18px;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.room-stats {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--ink-2);
}

.room-stats span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.room-stats .el-icon {
  color: var(--brand);
}

.room-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
  font-size: 12px;
  color: var(--brand);
}

.arrow {
  transition: transform 0.15s;
}

.room-card:hover .arrow {
  transform: translateX(3px);
}

.room-add {
  border: 1px dashed #c5d6d1;
  background: #f9fcfb;
  border-radius: 16px;
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 9px;
  color: var(--brand);
  cursor: pointer;
  font-size: 13px;
  font-family: inherit;
  transition: all 0.15s;
}

.room-add:hover {
  background: var(--brand-soft);
  border-color: var(--brand);
}

.color-hint {
  margin-left: 10px;
  font-size: 12px;
}
</style>
