<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Plus } from '@element-plus/icons-vue'
import { createTag, deleteTag, listTags, updateTag } from '../api/tags'

const loading = ref(true)
const tags = ref([])
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(null)
const formRef = ref()
const form = reactive({ name: '', color: '#8b8b8b' })

const rules = {
  name: [{ required: true, message: '请输入标签名称', trigger: 'blur' }],
}

async function load() {
  loading.value = true
  try {
    tags.value = await listTags()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, { name: '', color: '#8b8b8b' })
  dialogVisible.value = true
}

function openEdit(row) {
  editing.value = row
  Object.assign(form, { name: row.name, color: row.color || '#8b8b8b' })
  dialogVisible.value = true
}

async function submit() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (editing.value) {
      await updateTag(editing.value.id, { ...form })
      ElMessage.success('标签已更新')
    } else {
      await createTag({ ...form })
      ElMessage.success('标签已创建')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(
    `确定删除标签「${row.name}」吗？它会从 ${row.item_count} 件物品上移除。`,
    '删除标签',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await deleteTag(row.id)
  ElMessage.success('标签已删除')
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-head">
      <div>
        <h1 class="page-title">标签管理</h1>
        <p class="page-sub">标签可以自由组合，用于描述状态、季节、使用频率等</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增标签</el-button>
    </div>

    <section class="panel tag-cloud-panel">
      <div v-if="tags.length" class="tag-cloud">
        <div v-for="tag in tags" :key="tag.id" class="tag-chip">
          <span class="tag-dot" :style="{ background: tag.color || '#8b8b8b' }" />
          <span class="tag-name">{{ tag.name }}</span>
          <span class="tag-count">{{ tag.item_count }}</span>
          <span class="tag-actions">
            <el-button text circle size="small" :icon="Edit" @click="openEdit(tag)" />
            <el-button text circle size="small" type="danger" :icon="Delete" @click="remove(tag)" />
          </span>
        </div>
      </div>
      <el-empty v-else description="还没有标签" :image-size="76">
        <el-button type="primary" size="small" @click="openCreate">创建标签</el-button>
      </el-empty>
    </section>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑标签' : '新增标签'"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="标签名称" prop="name">
          <el-input v-model="form.name" placeholder="例如：常用、备用、冬季" maxlength="40" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="form.color" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tag-cloud-panel {
  min-height: 180px;
}

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.tag-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--line);
  background: #fbfdfc;
  border-radius: 999px;
  padding: 7px 8px 7px 14px;
  transition: border-color 0.15s;
}

.tag-chip:hover {
  border-color: var(--brand-line);
}

.tag-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.tag-name {
  font-size: 13px;
  font-weight: 550;
}

.tag-count {
  font-size: 11px;
  color: var(--muted);
  background: #eef4f2;
  border-radius: 999px;
  padding: 0 7px;
  line-height: 18px;
}

.tag-actions {
  display: flex;
  opacity: 0;
  transition: opacity 0.15s;
}

.tag-chip:hover .tag-actions {
  opacity: 1;
}

.tag-actions :deep(.el-button) {
  margin-left: 0;
}
</style>
