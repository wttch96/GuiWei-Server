<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Camera, Plus, Star, StarFilled, Delete, Picture } from '@element-plus/icons-vue'
import { listRooms } from '../api/rooms'
import { getContainerTree } from '../api/containers'
import { listCategories } from '../api/categories'
import { listTags } from '../api/tags'
import { createItem, getItem, updateItem } from '../api/items'
import { deletePhoto, setPrimaryPhoto, uploadPhoto } from '../api/photos'
import { COLOR_FAMILIES, STATUS_OPTIONS, photoUrl } from '../utils/format'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  item: { type: Object, default: null },
  defaultRoomId: { type: [Number, String], default: null },
  defaultContainerId: { type: [Number, String], default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const formRef = ref()
const cameraInput = ref()
const rooms = ref([])
const categories = ref([])
const tags = ref([])
const containerTree = ref([])
const existingPhotos = ref([])
const newPhotos = ref([])
const loading = ref(false)
const saving = ref(false)
const savedFlag = ref(false)

const form = reactive({
  name: '',
  room_id: null,
  container_id: null,
  category_name: '',
  tag_names: [],
  description: '',
  quantity: 1,
  unit: '件',
  status: 'in_stock',
  color_family: '',
})

const rules = {
  name: [{ required: true, message: '请输入物品名称', trigger: 'blur' }],
  room_id: [{ required: true, message: '请选择房间', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }],
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) init()
  },
)

async function init() {
  loading.value = true
  savedFlag.value = false
  newPhotos.value = []
  existingPhotos.value = []
  formRef.value?.clearValidate()
  try {
    const [roomList, categoryList, tagList] = await Promise.all([
      listRooms(),
      listCategories(),
      listTags(),
    ])
    rooms.value = roomList
    categories.value = categoryList
    tags.value = tagList

    if (props.item) {
      const detail = await getItem(props.item.id)
      Object.assign(form, {
        name: detail.name,
        room_id: detail.room_id,
        container_id: detail.container_id,
        category_name: detail.category?.name || '',
        tag_names: detail.tags.map((tag) => tag.name),
        description: detail.description || '',
        quantity: detail.quantity,
        unit: detail.unit || '件',
        status: detail.status || 'in_stock',
        color_family: detail.color_family || '',
      })
      existingPhotos.value = detail.photos || []
      containerTree.value = []
      if (form.room_id) await loadTree(form.room_id)
    } else {
      Object.assign(form, {
        name: '',
        room_id: props.defaultRoomId || null,
        container_id: props.defaultContainerId || null,
        category_name: '',
        tag_names: [],
        description: '',
        quantity: 1,
        unit: '件',
        status: 'in_stock',
        color_family: '',
      })
      containerTree.value = []
      if (form.room_id) await loadTree(form.room_id)
    }
  } finally {
    loading.value = false
  }
}

async function loadTree(roomId) {
  if (!roomId) {
    containerTree.value = []
    return
  }
  const data = await getContainerTree(roomId)
  containerTree.value = data.tree || []
}

async function onRoomChange(roomId) {
  form.container_id = null
  await loadTree(roomId)
}

async function uploadFile(file) {
  const photo = await uploadPhoto(file)
  newPhotos.value.push(photo)
  return photo
}

function uploadRequest(options) {
  return uploadFile(options.file)
}

function triggerCamera() {
  cameraInput.value?.click()
}

async function onCameraPick(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (file) {
    try {
      await uploadFile(file)
    } catch {
      // 请求层已提示错误
    }
  }
}

async function removePhoto(photo) {
  await ElMessageBox.confirm('确定删除这张照片吗？', '删除照片', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await deletePhoto(photo.id)
  existingPhotos.value = existingPhotos.value.filter((item) => item.id !== photo.id)
  newPhotos.value = newPhotos.value.filter((item) => item.id !== photo.id)
  ElMessage.success('照片已删除')
}

async function makePrimary(photo) {
  await setPrimaryPhoto(photo.id)
  existingPhotos.value.forEach((item) => {
    item.is_primary = item.id === photo.id
  })
  newPhotos.value.forEach((item) => {
    item.is_primary = item.id === photo.id
  })
  ElMessage.success('已设为主图')
}

async function submit() {
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      room_id: form.room_id,
      container_id: form.container_id || null,
      description: form.description,
      quantity: Number(form.quantity) || 0,
      unit: form.unit || '件',
      status: form.status,
      color_family: form.color_family || '',
      tag_names: form.tag_names,
    }
    if (form.category_name) payload.category_name = form.category_name
    else if (props.item) payload.category_id = null
    if (newPhotos.value.length) payload.photo_ids = newPhotos.value.map((p) => p.id)

    let saved
    if (props.item) saved = await updateItem(props.item.id, payload)
    else saved = await createItem(payload)

    savedFlag.value = true
    ElMessage.success(props.item ? '物品已更新' : '物品已创建')
    emit('saved', saved)
    visible.value = false
  } finally {
    saving.value = false
  }
}

async function handleClosed() {
  if (!savedFlag.value && newPhotos.value.length) {
    const pending = [...newPhotos.value]
    newPhotos.value = []
    for (const photo of pending) {
      deletePhoto(photo.id).catch(() => {})
    }
  }
}

const allPhotos = computed(() => [...existingPhotos.value, ...newPhotos.value])
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="item ? '编辑物品' : '新增物品'"
    width="700px"
    top="6vh"
    :close-on-click-modal="false"
    append-to-body
    @closed="handleClosed"
  >
    <div v-loading="loading" class="dialog-body">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="物品名称" prop="name">
          <el-input v-model="form.name" placeholder="例如：电视遥控器" maxlength="200" />
        </el-form-item>

        <el-row :gutter="14">
          <el-col :xs="24" :sm="12">
            <el-form-item label="房间" prop="room_id">
              <el-select
                v-model="form.room_id"
                placeholder="选择房间"
                style="width: 100%"
                @change="onRoomChange"
              >
                <el-option v-for="room in rooms" :key="room.id" :label="room.name" :value="room.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="容器">
              <el-tree-select
                v-model="form.container_id"
                :data="containerTree"
                :props="{ label: 'name', children: 'children' }"
                node-key="id"
                check-strictly
                clearable
                default-expand-all
                placeholder="可留空，直接放在房间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="14">
          <el-col :xs="24" :sm="12">
            <el-form-item label="分类">
              <el-select
                v-model="form.category_name"
                filterable
                allow-create
                clearable
                default-first-option
                placeholder="选择或输入新分类"
                style="width: 100%"
              >
                <el-option
                  v-for="category in categories"
                  :key="category.id"
                  :label="category.name"
                  :value="category.name"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="标签">
              <el-select
                v-model="form.tag_names"
                multiple
                filterable
                allow-create
                clearable
                default-first-option
                placeholder="选择或输入新标签"
                style="width: 100%"
              >
                <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.name" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="14">
          <el-col :xs="12" :sm="6">
            <el-form-item label="数量" prop="quantity">
              <el-input-number v-model="form.quantity" :min="0" :max="999999" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :sm="6">
            <el-form-item label="单位">
              <el-input v-model="form.unit" placeholder="件" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :sm="6">
            <el-form-item label="色系">
              <el-select
                v-model="form.color_family"
                filterable
                allow-create
                clearable
                default-first-option
                placeholder="可选"
                style="width: 100%"
              >
                <el-option
                  v-for="color in COLOR_FAMILIES"
                  :key="color"
                  :label="color"
                  :value="color"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="12" :sm="6">
            <el-form-item label="状态">
              <el-select v-model="form.status" style="width: 100%">
                <el-option
                  v-for="status in STATUS_OPTIONS"
                  :key="status.value"
                  :label="status.label"
                  :value="status.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            maxlength="2000"
            show-word-limit
            placeholder="外观、用途、购买时间等备注"
          />
        </el-form-item>

        <el-form-item label="照片">
          <div class="photo-grid">
            <div v-for="photo in allPhotos" :key="photo.id" class="photo-tile">
              <el-image
                :src="photoUrl(photo)"
                fit="cover"
                :preview-src-list="[photoUrl(photo)]"
                preview-teleported
                class="photo-img"
              />
              <span v-if="photo.is_primary" class="primary-badge">主图</span>
              <div class="photo-actions">
                <el-button
                  text
                  circle
                  size="small"
                  title="设为主图"
                  @click="makePrimary(photo)"
                >
                  <el-icon>
                    <StarFilled v-if="photo.is_primary" />
                    <Star v-else />
                  </el-icon>
                </el-button>
                <el-button text circle size="small" title="删除" @click="removePhoto(photo)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>

            <el-upload
              :http-request="uploadRequest"
              :show-file-list="false"
              accept="image/jpeg,image/png,image/webp,image/gif"
              multiple
            >
              <div class="photo-add">
                <el-icon :size="20"><Plus /></el-icon>
                <span>上传照片</span>
              </div>
            </el-upload>

            <button type="button" class="photo-add photo-camera" @click="triggerCamera">
              <el-icon :size="20"><Camera /></el-icon>
              <span>拍照</span>
            </button>

            <input
              ref="cameraInput"
              class="camera-input"
              type="file"
              accept="image/*"
              capture="environment"
              @change="onCameraPick"
            />
          </div>
        </el-form-item>
      </el-form>

      <div class="photo-tip">
        <el-icon><Picture /></el-icon>
        支持拍照或上传 JPG / PNG / WEBP / GIF，单张不超过 20MB。上传后可到「拍照识物」做 AI 识别。
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">
        {{ item ? '保存修改' : '创建物品' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.dialog-body {
  max-height: 68vh;
  overflow-y: auto;
  padding-right: 4px;
}

.photo-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.photo-tile {
  position: relative;
  width: 84px;
  height: 84px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--line);
  background: #f6f9f8;
}

.photo-img {
  width: 100%;
  height: 100%;
  display: block;
}

.primary-badge {
  position: absolute;
  left: 0;
  top: 0;
  background: var(--brand);
  color: #fff;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 0 0 8px 0;
}

.photo-actions {
  position: absolute;
  inset: auto 0 0 0;
  display: flex;
  justify-content: space-between;
  padding: 2px;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.55));
  opacity: 0;
  transition: opacity 0.15s;
}

.photo-tile:hover .photo-actions {
  opacity: 1;
}

.photo-actions :deep(.el-button) {
  color: #fff;
  height: 22px;
  width: 22px;
}

.photo-add {
  width: 84px;
  height: 84px;
  border-radius: 10px;
  border: 1px dashed #bfd2cc;
  color: var(--brand);
  background: #f8fbfa;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 0;
  font-family: inherit;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}

.photo-add:hover {
  border-color: var(--brand);
  background: var(--brand-soft);
}

.photo-camera {
  border-style: solid;
  border-color: var(--brand-line);
}

.camera-input {
  display: none;
}

.photo-tip {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11.5px;
  color: var(--muted);
  margin-top: 2px;
}
</style>
