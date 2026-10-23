<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Box,
  Camera,
  Check,
  Delete,
  Location,
  MagicStick,
  Refresh,
  UploadFilled,
} from '@element-plus/icons-vue'
import { getAiStatus } from '../api/ai'
import { listRooms } from '../api/rooms'
import { getContainerTree } from '../api/containers'
import { listCategories } from '../api/categories'
import { listTags } from '../api/tags'
import { createItem } from '../api/items'
import {
  analyzePhoto,
  deletePhoto,
  findSimilarItems,
  getPhoto,
  listPhotos,
  uploadPhoto,
} from '../api/photos'
import { photoUrl } from '../utils/format'

const router = useRouter()

const photo = ref(null)
const suggestion = ref(null)
const savedItem = ref(null)
const recent = ref([])
const rooms = ref([])
const categories = ref([])
const tags = ref([])
const containerTree = ref([])
const visionStatus = ref(null)
const analyzing = ref(false)
const saving = ref(false)
const uploading = ref(false)
const similarItems = ref([])
const similarLoading = ref(false)
const similarChecked = ref(false)
const formRef = ref()
const cameraInput = ref()
let similarSeq = 0

const form = reactive({
  name: '',
  description: '',
  category_name: '',
  tag_names: [],
  quantity: 1,
  room_id: null,
  container_id: null,
})

const rules = {
  name: [{ required: true, message: '请填写物品名称', trigger: 'blur' }],
  room_id: [{ required: true, message: '请选择房间', trigger: 'change' }],
}

const visionReady = computed(() => Boolean(visionStatus.value?.vision?.configured))
const attached = computed(() => Boolean(photo.value?.item_id))
const confidencePercent = computed(() =>
  Math.round((Number(suggestion.value?.confidence) || 0) * 100),
)

function formatSize(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

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

async function loadRecent() {
  const data = await listPhotos({ page: 1, page_size: 24 })
  recent.value = data.items || []
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

function fillForm(data) {
  if (!data) return
  form.name = data.name || ''
  form.description = data.description || ''
  form.category_name = data.category || ''
  form.tag_names = Array.isArray(data.tags) ? [...data.tags] : []
  form.quantity = Number.isFinite(data.quantity) ? data.quantity : 1
}

async function applyLocationHint(hint) {
  if (!hint) return
  const room = rooms.value.find((item) => hint.startsWith(item.name))
  if (!room) return
  form.room_id = room.id
  await loadTree(room.id)
  const parts = hint
    .slice(room.name.length)
    .replace(/^[\s/／]+/, '')
    .split(/[/／]/)
    .map((part) => part.trim())
    .filter(Boolean)
  let nodes = containerTree.value
  let matchedId = null
  for (const part of parts) {
    const node = nodes.find((item) => item.name === part)
    if (!node) break
    matchedId = node.id
    nodes = node.children || []
  }
  form.container_id = matchedId
}

function clearSimilar() {
  similarSeq += 1
  similarItems.value = []
  similarLoading.value = false
  similarChecked.value = false
}

async function loadSimilar(photoId) {
  const seq = ++similarSeq
  similarLoading.value = true
  similarChecked.value = false
  try {
    const data = await findSimilarItems(photoId)
    if (seq !== similarSeq || photo.value?.id !== photoId) return
    similarItems.value = data.items || []
    if (data.suggestion) suggestion.value = data.suggestion
    similarChecked.value = true
  } catch {
    if (seq === similarSeq) {
      similarItems.value = []
      similarChecked.value = true
    }
  } finally {
    if (seq === similarSeq) similarLoading.value = false
  }
}

function openSimilar(item) {
  router.push(`/items?edit=${item.id}`)
}

async function selectPhoto(row) {
  photo.value = row
  savedItem.value = null
  clearSimilar()
  formRef.value?.clearValidate()

  // 图片管理列表不返回识图全文，需要时再取详情
  let detail = row
  if (row.has_ai_result && !row.ai_result) {
    try {
      detail = await getPhoto(row.id)
      if (photo.value?.id === row.id) photo.value = detail
    } catch {
      detail = row
    }
  }

  suggestion.value = detail.ai_result || null
  if (detail.ai_result) {
    fillForm(detail.ai_result)
    await applyLocationHint(detail.ai_result.location_hint)
    if (detail.has_ai_result) loadSimilar(detail.id)
  } else {
    Object.assign(form, {
      name: '',
      description: '',
      category_name: '',
      tag_names: [],
      quantity: 1,
      room_id: null,
      container_id: null,
    })
    containerTree.value = []
  }
}

async function handleFile(file) {
  if (!file) return
  uploading.value = true
  try {
    const uploaded = await uploadPhoto(file)
    await selectPhoto(uploaded)
    const existing = recent.value.findIndex((row) => row.id === uploaded.id)
    if (existing >= 0) recent.value.splice(existing, 1)
    recent.value.unshift(uploaded)
    ElMessage.success('照片已上传，点击「AI 识别」开始分析')
  } catch {
    // 请求层已提示错误
  } finally {
    uploading.value = false
  }
}

function uploadRequest(options) {
  return handleFile(options.file)
}

function triggerCamera() {
  cameraInput.value?.click()
}

async function onCameraPick(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  await handleFile(file)
}

function retake() {
  resetWorkspace()
  triggerCamera()
}

async function analyze() {
  if (!photo.value) return
  if (visionStatus.value && !visionReady.value) {
    ElMessage.warning('视觉模型未配置，请填写 DEEPSEEK_API_KEY（或 VISION_*）后重启后端')
    return
  }
  analyzing.value = true
  try {
    const data = await analyzePhoto(photo.value.id)
    photo.value = data.photo
    suggestion.value = data.suggestion
    savedItem.value = null
    fillForm(data.suggestion)
    await applyLocationHint(data.suggestion?.location_hint)
    const row = recent.value.find((item) => item.id === data.photo.id)
    if (row) Object.assign(row, data.photo)
    similarSeq += 1
    similarLoading.value = false
    similarItems.value = data.similar_items || []
    similarChecked.value = true
    ElMessage.success('识别完成，请确认信息后入库')
  } catch {
    // 请求层已提示错误
  } finally {
    analyzing.value = false
  }
}

async function save() {
  if (!photo.value) return
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      room_id: form.room_id,
      container_id: form.container_id || null,
      description: form.description,
      quantity: Number(form.quantity) || 0,
      tag_names: form.tag_names,
      photo_ids: [photo.value.id],
      ai_summary: suggestion.value?.description || '',
    }
    if (form.category_name) payload.category_name = form.category_name
    const item = await createItem(payload)
    savedItem.value = item
    const row = recent.value.find((entry) => entry.id === photo.value.id)
    if (row) row.item_id = item.id
    ElMessage.success('已保存为物品')
  } catch {
    // 请求层已提示错误
  } finally {
    saving.value = false
  }
}

function resetWorkspace() {
  photo.value = null
  suggestion.value = null
  savedItem.value = null
  containerTree.value = []
  clearSimilar()
  formRef.value?.clearValidate()
  Object.assign(form, {
    name: '',
    description: '',
    category_name: '',
    tag_names: [],
    quantity: 1,
    room_id: null,
    container_id: null,
  })
}

async function removeCurrent() {
  if (!photo.value) return
  try {
    await ElMessageBox.confirm('确定删除这张照片吗？删除后无法恢复。', '删除照片', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  const id = photo.value.id
  await deletePhoto(id)
  recent.value = recent.value.filter((row) => row.id !== id)
  resetWorkspace()
  ElMessage.success('照片已删除')
}

onMounted(async () => {
  visionStatus.value = await getAiStatus().catch(() => null)
  await Promise.all([loadOptions(), loadRecent()])
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">拍照识物</h1>
        <p class="page-sub">拍照后 AI 识别名称、分类与标签，并查找描述相近的已有物品</p>
      </div>
      <el-tag
        v-if="visionStatus"
        size="small"
        :type="visionReady ? 'success' : 'info'"
        effect="plain"
      >
        {{ visionReady ? `视觉模型 · ${visionStatus.vision.model}` : '视觉模型未配置' }}
      </el-tag>
    </div>

    <el-alert
      v-if="visionStatus && !visionReady"
      type="warning"
      show-icon
      :closable="false"
      title="识图功能尚未启用"
      description="识图使用 DeepSeek 多模态模型（deepseek-flash）。请填写 DEEPSEEK_API_KEY，或在 backend/.env 中单独配置 VISION_API_BASE / VISION_API_KEY / VISION_MODEL 后重启服务。"
    />

    <div class="recognize-grid">
      <section class="panel upload-panel">
        <div class="panel-head">
          <span class="panel-title">1 · 上传照片</span>
          <el-button
            v-if="photo"
            text
            size="small"
            :icon="Refresh"
            :loading="analyzing"
            @click="analyze"
          >
            重新识别
          </el-button>
        </div>

        <input
          ref="cameraInput"
          class="camera-input"
          type="file"
          accept="image/*"
          capture="environment"
          @change="onCameraPick"
        />

        <template v-if="!photo">
          <el-upload
            class="uploader"
            drag
            :show-file-list="false"
            :http-request="uploadRequest"
            accept="image/jpeg,image/png,image/webp,image/gif"
          >
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="upload-text">拖拽照片到这里，或<em>点击选择</em></div>
            <div class="upload-hint">支持 JPG / PNG / WEBP / GIF，单张不超过 20MB</div>
          </el-upload>

          <div class="camera-row">
            <el-button :icon="Camera" :loading="uploading" @click="triggerCamera">
              拍照
            </el-button>
            <span class="camera-hint">手机端会直接打开后置摄像头</span>
          </div>
        </template>

        <div v-else class="preview-wrap">
          <el-image
            :src="photoUrl(photo)"
            fit="contain"
            class="preview"
            :preview-src-list="[photoUrl(photo)]"
            preview-teleported
            hide-on-click-modal
          />
          <div class="file-meta">
            <span>{{ photo.original_name || '未命名图片' }}</span>
            <span>{{ photo.width }} × {{ photo.height }} · {{ formatSize(photo.size) }}</span>
          </div>
          <el-tag v-if="attached" size="small" type="success" effect="plain">
            已关联物品 #{{ photo.item_id }}
          </el-tag>
          <div class="preview-actions">
            <el-button
              v-if="attached"
              @click="router.push(`/items?edit=${photo.item_id}`)"
            >
              查看物品
            </el-button>
            <el-button :icon="Camera" @click="retake">重拍</el-button>
            <el-button :icon="UploadFilled" @click="resetWorkspace">更换照片</el-button>
            <el-button type="danger" plain :icon="Delete" @click="removeCurrent">删除</el-button>
          </div>
        </div>
      </section>

      <section class="panel result-panel">
        <div class="panel-head">
          <span class="panel-title">2 · 识别与入库</span>
          <el-button
            v-if="photo && !savedItem"
            type="primary"
            :icon="MagicStick"
            :loading="analyzing"
            @click="analyze"
          >
            AI 识别
          </el-button>
        </div>

        <el-empty
          v-if="!photo"
          description="先上传一张物品照片"
          :image-size="84"
        />

        <div v-else-if="savedItem" class="saved-card">
          <div class="saved-icon"><el-icon :size="26"><Check /></el-icon></div>
          <h3>{{ savedItem.name }} 已入库</h3>
          <p>{{ savedItem.location_path || '未指定位置' }}</p>
          <div class="saved-actions">
            <el-button @click="resetWorkspace">继续识别</el-button>
            <el-button
              type="primary"
              @click="router.push(`/items?edit=${savedItem.id}`)"
            >
              查看物品
            </el-button>
          </div>
        </div>

        <template v-else>
          <div v-if="suggestion" class="ai-card">
            <div class="ai-card-head">
              <span class="ai-badge">
                <el-icon><MagicStick /></el-icon>
                AI 建议
              </span>
              <span class="confidence">置信度 {{ confidencePercent }}%</span>
            </div>
            <div class="ai-facts">
              <span v-if="suggestion.category" class="fact">分类 · {{ suggestion.category }}</span>
              <span v-if="suggestion.location_hint" class="fact">
                建议位置 · {{ suggestion.location_hint }}
              </span>
            </div>
            <p v-if="suggestion.description" class="ai-desc">{{ suggestion.description }}</p>
            <div v-if="suggestion.tags?.length" class="ai-tags">
              <el-tag
                v-for="tag in suggestion.tags"
                :key="tag"
                size="small"
                effect="plain"
                type="success"
              >
                {{ tag }}
              </el-tag>
            </div>
            <p v-if="suggestion.raw_text" class="ai-raw">
              图中文字：{{ suggestion.raw_text }}
            </p>
          </div>

          <el-alert
            v-else
            class="manual-tip"
            type="info"
            :closable="false"
            show-icon
            title="也可以跳过识别，直接手动填写信息入库"
          />

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-position="top"
            class="result-form"
          >
            <el-form-item label="物品名称" prop="name">
              <el-input v-model="form.name" placeholder="例如：无线充电器" maxlength="200" />
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
                    <el-option
                      v-for="room in rooms"
                      :key="room.id"
                      :label="room.name"
                      :value="room.id"
                    />
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
                    <el-option
                      v-for="tag in tags"
                      :key="tag.id"
                      :label="tag.name"
                      :value="tag.name"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="数量">
              <el-input-number v-model="form.quantity" :min="0" :max="999999" />
            </el-form-item>

            <el-form-item label="描述">
              <el-input
                v-model="form.description"
                type="textarea"
                :rows="3"
                maxlength="2000"
                show-word-limit
              />
            </el-form-item>

            <div class="form-actions">
              <span v-if="attached" class="muted attached-hint">
                照片已关联物品 #{{ photo.item_id }}，如需更换请到物品编辑页操作
              </span>
              <span v-else />
              <el-button
                type="primary"
                :loading="saving"
                :disabled="analyzing || attached"
                @click="save"
              >
                保存为物品
              </el-button>
            </div>
          </el-form>
        </template>
      </section>
    </div>

    <section
      v-if="photo && !savedItem && (similarChecked || similarLoading)"
      v-loading="similarLoading"
      class="panel similar-panel"
    >
      <div class="panel-head">
        <div>
          <span class="panel-title">相似物品</span>
          <p class="similar-sub">按 AI 生成的描述匹配现有物品，可用于避免重复入库</p>
        </div>
        <el-tag
          v-if="similarItems.length"
          size="small"
          type="success"
          effect="plain"
        >
          {{ similarItems.length }} 件相近
        </el-tag>
      </div>

      <div v-if="similarItems.length" class="similar-grid">
        <button
          v-for="item in similarItems"
          :key="item.id"
          type="button"
          class="similar-card"
          @click="openSimilar(item)"
        >
          <el-image
            v-if="item.primary_photo"
            :src="photoUrl(item.primary_photo)"
            fit="cover"
            class="similar-thumb"
          />
          <div v-else class="similar-thumb similar-thumb-empty">
            <el-icon :size="22"><Box /></el-icon>
          </div>
          <div class="similar-info">
            <div class="similar-title-row">
              <strong>{{ item.name }}</strong>
              <span class="similar-score">
                {{ Math.round((item.similarity || 0) * 100) }}%
              </span>
            </div>
            <div class="similar-location">
              <el-icon><Location /></el-icon>
              <span>{{ item.location_path || '未指定位置' }}</span>
            </div>
            <div v-if="item.match_reasons?.length" class="similar-reasons">
              {{ item.match_reasons.join(' · ') }}
            </div>
          </div>
        </button>
      </div>

      <div v-else-if="!similarLoading" class="similar-empty">
        没有找到描述相近的已有物品，可以直接保存为新物品。
      </div>
    </section>

    <section v-if="recent.length" class="panel">
      <div class="panel-head">
        <span class="panel-title">最近上传</span>
        <el-button text size="small" :icon="Refresh" @click="loadRecent">刷新</el-button>
      </div>
      <div class="recent-grid">
        <button
          v-for="row in recent"
          :key="row.id"
          class="recent-tile"
          :class="{ active: photo?.id === row.id }"
          @click="selectPhoto(row)"
        >
          <img :src="photoUrl(row)" alt="" />
          <span v-if="row.has_ai_result" class="recent-badge">AI</span>
          <span v-if="row.item_id" class="recent-badge linked">已入库</span>
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.recognize-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.15fr);
  gap: 18px;
  align-items: start;
}

.upload-panel,
.result-panel {
  min-height: 420px;
}

.uploader {
  width: 100%;
}

.uploader :deep(.el-upload) {
  width: 100%;
}

.uploader :deep(.el-upload-dragger) {
  width: 100%;
  min-height: 320px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border-radius: 14px;
  border-color: #cfdfda;
  background: #fbfdfc;
  transition: all 0.15s;
}

.uploader :deep(.el-upload-dragger:hover) {
  border-color: var(--brand);
  background: var(--brand-soft);
}

.upload-icon {
  font-size: 40px;
  color: var(--brand);
  margin-bottom: 8px;
}

.upload-text {
  font-size: 14px;
  color: var(--ink-2);
}

.upload-text em {
  color: var(--brand);
  font-style: normal;
  font-weight: 600;
}

.upload-hint {
  font-size: 11.5px;
  color: var(--muted);
}

.camera-input {
  display: none;
}

.camera-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}

.camera-hint {
  font-size: 11.5px;
  color: var(--muted);
}

.preview-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preview {
  width: 100%;
  height: 320px;
  border-radius: 14px;
  background: #f2f6f4;
  border: 1px solid var(--line);
}

.file-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 11.5px;
  color: var(--muted);
}

.file-meta span:first-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ai-card {
  border: 1px solid var(--brand-line);
  background: linear-gradient(140deg, #f4faf8, #fbfdfc);
  border-radius: 14px;
  padding: 14px 16px;
  margin-bottom: 16px;
}

.ai-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 9px;
}

.ai-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--brand-deep);
  font-size: 12.5px;
  font-weight: 600;
}

.confidence {
  font-size: 11px;
  color: var(--muted);
}

.ai-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.fact {
  font-size: 11.5px;
  color: var(--brand-deep);
  background: #e5f1ed;
  border-radius: 999px;
  padding: 3px 9px;
}

.ai-desc {
  margin: 0 0 9px;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--ink-2);
}

.ai-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ai-raw {
  margin: 9px 0 0;
  font-size: 11.5px;
  color: var(--muted);
}

.manual-tip {
  margin-bottom: 16px;
}

.result-form {
  margin-top: 4px;
}

.form-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 4px;
}

.attached-hint {
  font-size: 11.5px;
}

.saved-card {
  height: 340px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.saved-icon {
  width: 54px;
  height: 54px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  background: var(--brand-soft);
  color: var(--brand);
  margin-bottom: 14px;
}

.saved-card h3 {
  margin: 0;
  font-size: 17px;
}

.saved-card p {
  margin: 7px 0 20px;
  color: var(--muted);
  font-size: 12.5px;
}

.saved-actions {
  display: flex;
  gap: 8px;
}

.recent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: 10px;
}

.recent-tile {
  position: relative;
  aspect-ratio: 1;
  border-radius: 11px;
  overflow: hidden;
  border: 2px solid transparent;
  background: #f2f6f4;
  padding: 0;
  cursor: pointer;
  transition: border-color 0.15s, transform 0.15s;
}

.recent-tile:hover {
  transform: translateY(-1px);
}

.recent-tile.active {
  border-color: var(--brand);
}

.recent-tile img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.recent-badge {
  position: absolute;
  top: 5px;
  left: 5px;
  background: rgba(20, 51, 44, 0.78);
  color: #c9e9df;
  font-size: 9px;
  line-height: 1;
  padding: 4px 5px;
  border-radius: 5px;
}

.recent-badge.linked {
  left: auto;
  right: 5px;
  background: rgba(47, 125, 109, 0.85);
  color: #fff;
}

.similar-sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--muted);
}

.similar-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.similar-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fff;
  text-align: left;
  font-family: inherit;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, transform 0.15s;
}

.similar-card:hover {
  border-color: var(--brand-line);
  background: var(--brand-soft);
  transform: translateY(-1px);
}

.similar-thumb {
  width: 64px;
  height: 64px;
  border-radius: 9px;
  flex: none;
  background: #f2f6f4;
  overflow: hidden;
}

.similar-thumb-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--brand);
}

.similar-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.similar-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.similar-title-row strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13.5px;
}

.similar-score {
  flex: none;
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand-deep);
  font-size: 10.5px;
  font-weight: 600;
}

.similar-location {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  font-size: 11.5px;
  color: var(--muted);
}

.similar-location span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.similar-reasons {
  font-size: 11px;
  line-height: 1.5;
  color: var(--brand-deep);
}

.similar-empty {
  padding: 6px 0 2px;
  font-size: 12.5px;
  color: var(--muted);
}

@media (max-width: 1024px) {
  .recognize-grid {
    grid-template-columns: 1fr;
  }
  .upload-panel,
  .result-panel {
    min-height: 0;
  }
}

@media (max-width: 640px) {
  .similar-grid {
    grid-template-columns: 1fr;
  }
}
</style>
