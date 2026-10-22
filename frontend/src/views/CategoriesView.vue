<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Plus } from '@element-plus/icons-vue'
import {
  createCategory,
  deleteCategory,
  listCategories,
  updateCategory,
} from '../api/categories'

const loading = ref(true)
const categories = ref([])
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(null)
const formRef = ref()
const form = reactive({ name: '', description: '', color: '#5b8def', sort_order: 0 })

const rules = {
  name: [{ required: true, message: '请输入分类名称', trigger: 'blur' }],
}

async function load() {
  loading.value = true
  try {
    categories.value = await listCategories()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, { name: '', description: '', color: '#5b8def', sort_order: 0 })
  dialogVisible.value = true
}

function openEdit(row) {
  editing.value = row
  Object.assign(form, {
    name: row.name,
    description: row.description || '',
    color: row.color || '#5b8def',
    sort_order: row.sort_order || 0,
  })
  dialogVisible.value = true
}

async function submit() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (editing.value) {
      await updateCategory(editing.value.id, { ...form })
      ElMessage.success('分类已更新')
    } else {
      await createCategory({ ...form })
      ElMessage.success('分类已创建')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(
    `确定删除分类「${row.name}」吗？该分类下的 ${row.item_count} 件物品会变为未分类。`,
    '删除分类',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await deleteCategory(row.id)
  ElMessage.success('分类已删除')
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="page-head">
      <div>
        <h1 class="page-title">物品分类</h1>
        <p class="page-sub">每件物品只能属于一个分类，是检索物品最重要的维度</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增分类</el-button>
    </div>

    <section class="panel panel--flush">
      <el-table :data="categories" style="width: 100%">
        <el-table-column label="分类" min-width="200">
          <template #default="{ row }">
            <div class="cat-cell">
              <span class="cat-dot" :style="{ background: row.color || '#5b8def' }" />
              <span class="cat-name">{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="描述" min-width="260">
          <template #default="{ row }">
            <span class="muted">{{ row.description || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="物品数" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" type="info">{{ row.item_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="排序" width="90" align="center">
          <template #default="{ row }">{{ row.sort_order }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button text size="small" :icon="Edit" @click="openEdit(row)" />
            <el-button text size="small" type="danger" :icon="Delete" @click="remove(row)" />
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有分类" :image-size="76">
            <el-button type="primary" size="small" @click="openCreate">创建分类</el-button>
          </el-empty>
        </template>
      </el-table>
    </section>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑分类' : '新增分类'"
      width="440px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="分类名称" prop="name">
          <el-input v-model="form.name" placeholder="例如：电子产品、日用品" maxlength="80" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="颜色">
              <el-color-picker v-model="form.color" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="排序">
              <el-input-number v-model="form.sort_order" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.cat-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cat-dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  flex: none;
}

.cat-name {
  font-weight: 560;
}
</style>
