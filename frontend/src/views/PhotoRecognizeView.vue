<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Box,
  Camera,
  Check,
  Delete,
  Grid,
  Location,
  MagicStick,
  Refresh,
  UploadFilled,
} from '@element-plus/icons-vue'
import { getAiStatus } from '../api/ai'
import { listRooms } from '../api/rooms'
import { getContainerTree, listContainers } from '../api/containers'
import { listCategories } from '../api/categories'
import { listTags } from '../api/tags'
import { createItem, createItemsBatch, moveItem } from '../api/items'
import {
  analyzePhoto,
  batchDeletePhotos,
  deletePhoto,
  detectPhoto,
  findSimilarItems,
  getPhoto,
  listPhotos,
  setPrimaryPhoto,
  uploadPhoto,
} from '../api/photos'
import { photoUrl, COLOR_FAMILIES } from '../utils/format'
import { downscalePhoto } from '../utils/image'

const router = useRouter()

// ===== 页面状态 =====
// photo：当前查看的照片；batch：本次待入库的照片批次；savedItem：刚入库的物品
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
// 拍照模式：single 压缩到 480p 走单件识别；multi 保留原图走多物品切割
const captureMode = ref('single')
const uploaderRef = ref()
const resultPanel = ref()
const batch = ref([])
// 一句话操作：command 为用户输入，targetItem 为选中的已有相似物品
const command = ref('')
const commandInput = ref()
const commandRunning = ref(false)
const targetItem = ref(null)
const allContainers = ref(null)
// el-upload 多选时会连续触发 change，用定时器合并成一次上传
let pendingFiles = []
let pendingTimer = null
// 连续上传时合并成功提示，避免一次弹多条
let toastTimer = null
let toastCount = 0
// 相似物品匹配的请求序号，用于丢弃过期响应
let similarSeq = 0

const form = reactive({
  name: '',
  description: '',
  category_name: '',
  tag_names: [],
  quantity: 1,
  color_family: '',
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

/** 预加载房间、分类、标签等表单选项。 */
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

/** 加载「最近上传」：后端会过滤掉未入库的临时裁切图。 */
async function loadRecent() {
  const data = await listPhotos({ page: 1, page_size: 24 })
  recent.value = data.items || []
}

/** 加载指定房间的容器树，供容器选择器使用。 */
async function loadTree(roomId) {
  if (!roomId) {
    containerTree.value = []
    return
  }
  const data = await getContainerTree(roomId)
  containerTree.value = data.tree || []
}

/** 切换房间时清空容器选择并重新加载容器树。 */
async function onRoomChange(roomId) {
  form.container_id = null
  await loadTree(roomId)
}

async function loadContainerIndex() {
  if (!allContainers.value) allContainers.value = await listContainers()
  return allContainers.value
}

/** 从「放到客厅的药柜里」这类句子中识别房间和容器（名称、昵称或展示名）。 */
function resolveLocation(text) {
  const sentence = (text || '').replace(/\s+/g, '')
  const pool = allContainers.value || []
  let room = null
  for (const item of rooms.value) {
    if (item.name && item.name.length >= 2 && sentence.includes(item.name)) {
      if (!room || item.name.length > room.name.length) room = item
    }
  }

  const candidates = room ? pool.filter((row) => row.room_id === room.id) : pool
  let best = null
  for (const row of candidates) {
    const keys = new Set()
    for (const key of [row.name, row.nickname, row.display_name]) {
      if (!key) continue
      keys.add(key)
      const plain = key.replace(/[（(][^（()）]*[）)]/g, '').trim()
      if (plain) keys.add(plain)
    }
    for (const key of keys) {
      if (key.length < 2 || !sentence.includes(key)) continue
      if (!best || key.length > best.length) best = { row, length: key.length }
    }
  }

  if (best) {
    const container = best.row
    if (!room) room = rooms.value.find((item) => item.id === container.room_id) || null
    return { room, container }
  }
  return { room, container: null }
}

/** 在相似物品里选定「就是这个」，之后的一句话指令会作用于它。 */
async function chooseTarget(item) {
  targetItem.value = targetItem.value?.id === item.id ? null : item
  if (!targetItem.value) return
  ElMessage.success(`已选择已有物品「${item.name}」，一句话指令将作用于它`)
  await nextTick()
  commandInput.value?.focus()
}

/**
 * 执行一句话指令：从「放到客厅的药柜」里解析房间/容器。
 * 选中已有物品时先确认再移动；否则把位置回填表单并创建新物品。
 */
async function runCommand() {
  const text = command.value.trim()
  if (!text) {
    ElMessage.warning('请输入一句话指令，例如「放到客厅的药柜」')
    return
  }
  if (!photo.value) return

  commandRunning.value = true
  try {
    await loadContainerIndex()
    const { room, container } = resolveLocation(text)
    if (!room) {
      ElMessage.warning('没看出要放到哪里，请带上房间名，例如「放到客厅的药柜」')
      return
    }
    const locationText = [room.name, container?.display_name].filter(Boolean).join(' / ')

    if (targetItem.value) {
      try {
        await ElMessageBox.confirm(
          `把「${targetItem.value.name}」移动到「${locationText}」吗？`,
          '确认移动',
          { type: 'warning', confirmButtonText: '移动', cancelButtonText: '取消' },
        )
      } catch {
        return
      }
      await moveItem(targetItem.value.id, {
        room_id: room.id,
        container_id: container?.id || null,
      })
      ElMessage.success(`已把「${targetItem.value.name}」移动到「${locationText}」`)
      targetItem.value = null
      command.value = ''
      if (photo.value) await loadSimilar(photo.value.id)
      return
    }

    form.room_id = room.id
    await loadTree(room.id)
    form.container_id = container?.id || null
    try {
      await formRef.value.validate()
    } catch {
      ElMessage.warning('请先补全物品名称，再执行指令')
      return
    }
    await save()
  } catch {
    // 请求层已提示错误
  } finally {
    commandRunning.value = false
  }
}

/** 用 AI 识别结果填充入库表单（房间/容器需要用户确认）。 */
function fillForm(data) {
  if (!data) return
  form.name = data.name || ''
  form.description = data.description || ''
  form.category_name = data.category || ''
  form.tag_names = Array.isArray(data.tags) ? [...data.tags] : []
  form.quantity = Number.isFinite(data.quantity) ? data.quantity : 1
  form.color_family = data.color_family || ''
}

/** 解析模型给出的「房间/容器/子容器」位置提示并反填表单。 */
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
    const plain = part.replace(/[（(][^（()）]*[）)]$/, '').trim()
    const node = nodes.find(
      (item) =>
        item.name === part ||
        item.nickname === part ||
        item.display_name === part ||
        item.name === plain,
    )
    if (!node) break
    matchedId = node.id
    nodes = node.children || []
  }
  form.container_id = matchedId
}

/** 清空相似物品结果；递增序号可让在途请求作废。 */
function clearSimilar() {
  similarSeq += 1
  similarItems.value = []
  similarLoading.value = false
  similarChecked.value = false
}

/** 复用已保存的识图结果查找相似物品（不会再次调用视觉模型）。 */
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

/** 打开相似物品的编辑页，便于直接复用或修改已有记录。 */
function openSimilar(item) {
  router.push(`/items?edit=${item.id}`)
}

/** 切换到某张照片：同步预览、识图结果、相似物品与表单。 */
async function activatePhoto(row) {
  photo.value = row
  targetItem.value = null
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
      color_family: '',
      room_id: null,
      container_id: null,
    })
    containerTree.value = []
  }
}

/** 从「最近上传」选图时，用这张照片开一个新批次。 */
function selectPhoto(row) {
  batch.value = [row]
  return activatePhoto(row)
}

/** 只把照片移出本批次，不删除文件。 */
function removeFromBatch(row) {
  batch.value = batch.value.filter((entry) => entry.id !== row.id)
}

// ============ 多物品检测（YOLO-World） ============
const detecting = ref(false)
const detections = ref([])
const detectionRoomId = ref(null)
const detectionContainerId = ref(null)
const detectionTree = ref([])
const batchSaving = ref(false)
const detectProgress = reactive({ done: 0, total: 0 })

const detectionAvailable = computed(() => Boolean(visionStatus.value?.detection?.installed))
const checkedDetections = computed(() =>
  detections.value.filter((entry) => entry.checked && !entry.createdItem),
)

/** 多物品入库时使用的容器树。 */
async function loadDetectionTree(roomId) {
  if (!roomId) {
    detectionTree.value = []
    return
  }
  const data = await getContainerTree(roomId)
  detectionTree.value = data.tree || []
}

/** 多物品入库切换房间时清空容器选择。 */
async function onDetectionRoomChange(roomId) {
  detectionContainerId.value = null
  await loadDetectionTree(roomId)
}

/** 删除本批次未入库的裁切图（临时文件），避免留在图片库和磁盘上。 */
function discardUnsavedCrops() {
  const ids = []
  for (const entry of detections.value) {
    if (entry.analysisPhoto) ids.push(entry.analysisPhoto.id)
    if (!entry.createdItem) ids.push(entry.photo.id)
  }
  detections.value = []
  detectProgress.done = 0
  detectProgress.total = 0
  if (ids.length) batchDeletePhotos(ids).catch(() => {})
}

/** 对当前照片执行 YOLOE 检测：切割多件物品并逐件触发 AI 识别。 */
async function runDetection() {
  if (!photo.value || detecting.value) return
  if (!detectionAvailable.value) {
    ElMessage.warning(
      '后端未安装多物品检测依赖，请在 backend 下执行：pip install -r requirements-yolo.txt',
    )
    return
  }
  detecting.value = true
  discardUnsavedCrops()
  try {
    const data = await detectPhoto(photo.value.id)
    detections.value = (data.detections || []).map((row) => ({
      key: String(row.photo.id),
      label: row.label,
      labelZh: row.label_zh || row.label,
      confidence: row.confidence,
      photo: row.photo,
      analysisPhoto: row.analysis_photo || null,
      checked: true,
      state: 'pending',
      name: '',
      description: '',
      category_name: '',
      color_family: '',
      suggestion: null,
      createdItem: null,
    }))
    if (detectionRoomId.value == null) detectionRoomId.value = form.room_id
    if (detectionContainerId.value == null) detectionContainerId.value = form.container_id
    await loadDetectionTree(detectionRoomId.value)
    if (!detections.value.length) {
      ElMessage.info('没有检测到物品，可在 .env 调整 YOLO_CLASSES 或改用单件识别')
      return
    }
    if (data.limit && detections.value.length >= Number(data.limit)) {
      ElMessage.info(
        `检测到 ${detections.value.length} 件，已达到单张上限 ${data.limit}；可调整 backend/.env 的 YOLO_MAX_OBJECTS`,
      )
    }
    if (!visionReady.value) {
      detections.value.forEach((entry) => {
        entry.state = 'error'
        entry.name = entry.labelZh || entry.label
      })
      ElMessage.info('视觉模型未配置：已按检测标签生成，可手动修改名称后入库')
      return
    }
    ElMessage.success(`检测到 ${detections.value.length} 件物品，正在逐件识别…`)
    await analyzeDetections(detections.value)
  } catch {
    // 请求层已提示错误
  } finally {
    detecting.value = false
  }
}

/** 逐件调用视觉模型补充名称/分类，控制并发避免一次打满接口。 */
async function analyzeDetections(entries) {
  const queue = entries.filter((entry) => !entry.createdItem && entry.state === 'pending')
  detectProgress.done = 0
  detectProgress.total = queue.length
  let cursor = 0
  const worker = async () => {
    while (cursor < queue.length) {
      const entry = queue[cursor]
      cursor += 1
      entry.state = 'analyzing'
      // 识别用白底抠图（如有），保存仍用原图裁切
      const analysisId = entry.analysisPhoto?.id || entry.photo.id
      try {
        const data = await analyzePhoto(analysisId)
        entry.suggestion = data.suggestion
        entry.name = data.suggestion?.name || entry.labelZh || entry.label
        entry.description = data.suggestion?.description || ''
        entry.category_name = data.suggestion?.category || ''
        entry.color_family = data.suggestion?.color_family || ''
        entry.state = 'ready'
      } catch {
        entry.state = 'error'
        entry.name = entry.name || entry.labelZh || entry.label
      } finally {
        // 识别完成即删除临时分析图，避免残留
        if (entry.analysisPhoto) {
          deletePhoto(entry.analysisPhoto.id).catch(() => {})
          entry.analysisPhoto = null
        }
        detectProgress.done += 1
      }
    }
  }
  await Promise.all([worker(), worker()])
}

/** 把勾选的检测结果批量入库，并删除未勾选的临时裁切图。 */
async function saveDetections() {
  const targets = checkedDetections.value
  if (!targets.length) {
    ElMessage.warning('请至少勾选一件物品')
    return
  }
  if (!detectionRoomId.value) {
    ElMessage.warning('请选择要入库的房间')
    return
  }
  if (targets.some((entry) => entry.state === 'analyzing')) {
    ElMessage.warning('还有物品正在识别，请稍候再入库')
    return
  }

  batchSaving.value = true
  try {
    const payload = targets.map((entry) => ({
      name: (entry.name || entry.labelZh || entry.label || '未命名物品').trim(),
      room_id: detectionRoomId.value,
      container_id: detectionContainerId.value || null,
      description: entry.description || '',
      quantity: 1,
      color_family: entry.color_family || '',
      category_name: entry.category_name || undefined,
      ai_summary: entry.suggestion?.description || '',
      photo_ids: [entry.photo.id],
    }))
    const result = await createItemsBatch(payload)
    const created = result.created || []
    const failed = result.failed || []
    for (const row of created) {
      const entry = targets[row.index]
      if (entry) entry.createdItem = row.item
    }
    if (created.length) {
      ElMessage.success(`已入库 ${created.length} 件物品`)
      await loadRecent()
    }
    if (failed.length) {
      const names = failed.map((row) => row.name || `第 ${row.index + 1} 件`).join('、')
      ElMessage.warning(`${failed.length} 件入库失败：${names}`)
      for (const row of failed) {
        const entry = targets[row.index]
        if (entry) entry.state = 'error'
      }
    }

    // 未勾选的裁切图不会入库，直接删除，避免出现在图片库
    const leftoverIds = detections.value
      .filter((entry) => !entry.createdItem && !entry.checked)
      .flatMap((entry) => [
        entry.photo.id,
        ...(entry.analysisPhoto ? [entry.analysisPhoto.id] : []),
      ])
    if (leftoverIds.length) {
      await batchDeletePhotos(leftoverIds).catch(() => {})
      detections.value = detections.value.filter(
        (entry) => entry.createdItem || entry.checked,
      )
    }
  } catch {
    // 请求层已提示错误
  } finally {
    batchSaving.value = false
  }
}

/** 合并连续上传的成功提示，避免多张照片时弹出一串 Toast。 */
function notifyUploaded(count) {
  toastCount += count
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    const total = toastCount
    toastCount = 0
    ElMessage.success(
      total > 1
        ? `已上传 ${total} 张照片，正在识别最新一张，可点缩略图切换`
        : '照片已上传，正在自动识别…',
    )
  }, 250)
}

/** 批量上传：单件模式压缩到 480p，多件模式保留原图供 YOLO 切割。 */
async function handleFiles(files, { compress = true, mode = 'single' } = {}) {
  const list = Array.from(files || []).filter(Boolean)
  if (!list.length) return
  uploading.value = true
  const uploaded = []
  try {
    for (const file of list) {
      try {
        const prepared = compress ? await downscalePhoto(file) : file
        uploaded.push(await uploadPhoto(prepared))
      } catch {
        // 单张失败不影响其余照片
      }
    }
    if (!uploaded.length) return
    // 已入库的照片不再参与新一批，避免把两张不同物品的照片混在一起
    const base = batch.value.filter((row) => !row.item_id)
    const known = new Set(base.map((row) => row.id))
    batch.value = [...base, ...uploaded.filter((row) => !known.has(row.id))]
    const fresh = new Set(uploaded.map((row) => row.id))
    recent.value = [
      ...uploaded.slice().reverse(),
      ...recent.value.filter((row) => !fresh.has(row.id)),
    ]
    // 连拍时一次返回多张，最后一张才是刚拍的；以它作为当前照片和主图
    await activatePhoto(uploaded[uploaded.length - 1])
    notifyUploaded(uploaded.length)
    scrollToResult()

    if (mode === 'multi') {
      if (detectionAvailable.value) {
        runDetection()
      } else {
        ElMessage.warning(
          '未安装多物品检测依赖，照片已按原图上传；安装 requirements-yolo.txt 后可重新识别',
        )
      }
      return
    }
    // 单件：拍完先自动识别一次，用户随后可用一句话指令把物品放到指定位置
    if (visionReady.value) analyze()
  } finally {
    uploading.value = false
  }
}

/** el-upload 多选时会逐个触发 change，稍作合并后一次性处理。 */
function onUploadChange(_file, uploadFiles) {
  pendingFiles = uploadFiles.map((item) => item.raw).filter(Boolean)
  clearTimeout(pendingTimer)
  pendingTimer = setTimeout(() => {
    const files = pendingFiles
    pendingFiles = []
    uploaderRef.value?.clearFiles()
    if (files.length) handleFiles(files)
  }, 30)
}

/** 手机上上传完成后直接滚到第 2 步，避免误以为还停在上传页。 */
async function scrollToResult() {
  if (!window.matchMedia('(max-width: 1024px)').matches) return
  await nextTick()
  resultPanel.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

/** 打开相机/相册；mode 决定后续是否压缩、是否自动切割。 */
function triggerCamera(mode = 'single') {
  captureMode.value = mode
  cameraInput.value?.click()
}

/** 文件选择完成：按当前拍照模式交给 handleFiles。 */
async function onCameraPick(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  const mode = captureMode.value
  await handleFiles(files, { compress: mode !== 'multi', mode })
}

/** 重拍：清空当前工作区后沿用上次的拍照模式。 */
function retake() {
  resetWorkspace()
  triggerCamera(captureMode.value)
}

/** 调用视觉模型识别当前照片；切换照片后丢弃过期响应。 */
async function analyze() {
  if (!photo.value) return
  if (visionStatus.value && !visionReady.value) {
    ElMessage.warning('视觉模型未配置，请填写 DEEPSEEK_API_KEY（或 VISION_*）后重启后端')
    return
  }
  const targetId = photo.value.id
  analyzing.value = true
  try {
    const data = await analyzePhoto(targetId)
    if (photo.value?.id !== targetId) return
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

/** 保存为物品：当前照片排第一作为主图，批次内未入库的照片一并关联。 */
async function save() {
  if (!photo.value) return
  await formRef.value.validate()
  const fresh = batch.value.filter((entry) => !entry.item_id).map((entry) => entry.id)
  const activeId = photo.value.id
  // 当前查看的照片排在第一位，后端会把它设为主图
  const photoIds = fresh.includes(activeId)
    ? [activeId, ...fresh.filter((id) => id !== activeId)]
    : fresh.length
      ? fresh
      : [activeId]
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      room_id: form.room_id,
      container_id: form.container_id || null,
      description: form.description,
      quantity: Number(form.quantity) || 0,
      color_family: form.color_family,
      tag_names: form.tag_names,
      photo_ids: photoIds,
      ai_summary: suggestion.value?.description || '',
    }
    if (form.category_name) payload.category_name = form.category_name
    const item = await createItem(payload)
    // 多张照片时显式把当前照片设为主图，兼容旧后端的主图选择逻辑
    if (photoIds.length > 1) {
      try {
        await setPrimaryPhoto(photoIds[0])
      } catch {
        // 设主图失败不影响物品创建结果
      }
    }
    savedItem.value = item
    const linkedIds = new Set(payload.photo_ids)
    batch.value.forEach((entry) => {
      if (linkedIds.has(entry.id)) entry.item_id = item.id
    })
    const row = recent.value.find((entry) => entry.id === photo.value.id)
    if (row) row.item_id = item.id
    recent.value.forEach((entry) => {
      if (linkedIds.has(entry.id)) entry.item_id = item.id
    })
    ElMessage.success('已保存为物品')
  } catch {
    // 请求层已提示错误
  } finally {
    saving.value = false
  }
}

/** 重置整个识物工作区（照片、批次、表单、相似物品、检测结果）。 */
function resetWorkspace() {
  photo.value = null
  batch.value = []
  command.value = ''
  targetItem.value = null
  suggestion.value = null
  savedItem.value = null
  containerTree.value = []
  discardUnsavedCrops()
  clearSimilar()
  formRef.value?.clearValidate()
  Object.assign(form, {
    name: '',
    description: '',
    category_name: '',
    tag_names: [],
    quantity: 1,
    color_family: '',
    room_id: null,
    container_id: null,
  })
}

/** 删除当前照片；若同批次还有照片则自动切换到下一张。 */
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
  batch.value = batch.value.filter((row) => row.id !== id)
  if (batch.value.length) await activatePhoto(batch.value[0])
  else resetWorkspace()
  ElMessage.success('照片已删除')
}

onMounted(async () => {
  visionStatus.value = await getAiStatus().catch(() => null)
  await Promise.all([loadOptions(), loadRecent()])
})

// 离开页面时清掉未入库的裁切图；浏览器直接关闭的情况由后端 TTL 兜底
onBeforeUnmount(discardUnsavedCrops)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">拍照识物</h1>
        <p class="page-sub">第 1 步上传照片，第 2 步确认识别结果并入库</p>
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
      <!-- 第 1 步：拍照 / 上传。单件自动压缩，多件保留原图供切割 -->
      <section class="panel upload-panel">
        <div class="panel-head">
          <span class="panel-title"><em class="step">1</em>上传照片</span>
          <div v-if="photo" class="upload-head-actions">
            <el-button
              v-if="detectionAvailable"
              text
              size="small"
              :icon="Grid"
              :loading="detecting"
              @click="runDetection"
            >
              多物品识别
            </el-button>
            <el-button
              text
              size="small"
              :icon="Refresh"
              :loading="analyzing"
              @click="analyze"
            >
              重新识别
            </el-button>
          </div>
        </div>

        <input
          ref="cameraInput"
          class="camera-input"
          type="file"
          accept="image/*"
          capture="environment"
          multiple
          @change="onCameraPick"
        />

        <template v-if="!photo">
          <div class="upload-choices">
            <el-upload
              ref="uploaderRef"
              class="uploader"
              drag
              multiple
              :auto-upload="false"
              :show-file-list="false"
              :on-change="onUploadChange"
              accept="image/jpeg,image/png,image/webp,image/gif"
            >
              <el-icon class="upload-icon"><UploadFilled /></el-icon>
              <div class="upload-text">
                <span class="drag-only">拖拽照片到这里，或<em>点击选择</em></span>
                <span class="mobile-only">从相册选择照片</span>
              </div>
              <div class="upload-hint">
                单件照片会自动压缩到 480p；JPG / PNG / WEBP / GIF，单张不超过 20MB
              </div>
            </el-upload>

            <div class="camera-row">
              <el-button
                :icon="Camera"
                :loading="uploading"
                @click="triggerCamera('single')"
              >
                拍单件
              </el-button>
              <el-button :icon="Grid" :loading="uploading" @click="triggerCamera('multi')">
                拍多件
              </el-button>
              <span class="camera-hint">单件自动压缩到 480p；多件保留原图用于切割</span>
            </div>
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
          <div v-if="batch.length > 1" class="batch-strip">
            <span class="batch-label">
              本批次 {{ batch.length }} 张，当前照片将作为主图；点 × 可移出批次
            </span>
            <div class="batch-list">
              <button
                v-for="row in batch"
                :key="row.id"
                type="button"
                class="batch-tile"
                :class="{ active: photo?.id === row.id }"
                @click="activatePhoto(row)"
              >
                <img :src="photoUrl(row)" alt="" />
                <span v-if="photo?.id === row.id" class="batch-main">主图</span>
                <span
                  v-else
                  class="batch-remove"
                  title="移出本批次"
                  @click.stop="removeFromBatch(row)"
                >
                  ×
                </span>
              </button>
            </div>
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
            <el-button
              :icon="captureMode === 'multi' ? Grid : Camera"
              :loading="uploading"
              @click="triggerCamera(captureMode)"
            >
              {{ captureMode === 'multi' ? '继续拍多件' : '继续拍单件' }}
            </el-button>
            <el-button :icon="Camera" @click="retake">重拍</el-button>
            <el-button :icon="UploadFilled" @click="resetWorkspace">更换照片</el-button>
            <el-button type="danger" plain :icon="Delete" @click="removeCurrent">删除</el-button>
          </div>
        </div>
      </section>

      <!-- 第 2 步：AI 识别结果、一句话操作与入库表单 -->
      <section ref="resultPanel" class="panel result-panel">
        <div class="panel-head">
          <span class="panel-title"><em class="step">2</em>识别与入库</span>
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
              <span v-if="suggestion.color_family" class="fact">
                色系 · {{ suggestion.color_family }}
              </span>
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

          <div class="command-box">
            <div class="command-head">
              <span class="command-title"><el-icon><MagicStick /></el-icon>一句话操作</span>
              <span class="command-hint">例如：放到客厅的药柜</span>
            </div>
            <div v-if="targetItem" class="command-target">
              <span>将作用于已有物品「{{ targetItem.name }}」</span>
              <el-button text size="small" @click="targetItem = null">取消</el-button>
            </div>
            <div class="command-row">
              <el-input
                ref="commandInput"
                v-model="command"
                placeholder="一句话说明要放到哪里，回车或点执行"
                maxlength="200"
                clearable
                @keyup.enter="runCommand"
              />
              <el-button
                type="primary"
                :loading="commandRunning"
                :disabled="analyzing"
                @click="runCommand"
              >
                执行
              </el-button>
            </div>
          </div>

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
                    :props="{ label: 'display_name', children: 'children' }"
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

            <el-row :gutter="14">
              <el-col :xs="24" :sm="12">
                <el-form-item label="色系">
                  <el-select
                    v-model="form.color_family"
                    filterable
                    allow-create
                    clearable
                    placeholder="识别后自动填充，也可手动选择"
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
              <el-col :xs="24" :sm="12">
                <el-form-item label="数量">
                  <el-input-number v-model="form.quantity" :min="0" :max="999999" />
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

    <!-- 多物品检测：YOLOE 切割结果，勾选后批量入库 -->
    <section
      v-if="detecting || detections.length"
      v-loading="detecting"
      class="panel detection-panel"
    >
      <div class="panel-head">
        <div>
          <span class="panel-title">多物品识别</span>
          <p class="similar-sub">
            YOLOE 自动检测并抠出物品，逐件识别后可一次入库；勾选要保存的物品
          </p>
        </div>
        <el-tag v-if="detectProgress.total" size="small" effect="plain">
          识别 {{ detectProgress.done }}/{{ detectProgress.total }}
        </el-tag>
      </div>

      <div v-if="detections.length" class="detection-toolbar">
        <el-select
          v-model="detectionRoomId"
          placeholder="选择房间"
          style="width: 170px"
          @change="onDetectionRoomChange"
        >
          <el-option v-for="room in rooms" :key="room.id" :label="room.name" :value="room.id" />
        </el-select>
        <el-tree-select
          v-model="detectionContainerId"
          :data="detectionTree"
          :props="{ label: 'display_name', children: 'children' }"
          node-key="id"
          check-strictly
          clearable
          default-expand-all
          placeholder="容器（可选）"
          style="width: 210px"
        />
        <span class="spacer" />
        <el-button
          type="primary"
          :loading="batchSaving"
          :disabled="!checkedDetections.length"
          @click="saveDetections"
        >
          批量入库（{{ checkedDetections.length }}）
        </el-button>
      </div>

      <div v-if="detecting && !detections.length" class="detection-loading">
        正在检测并切割物品，首次运行需要下载模型权重，请稍候…
      </div>

      <div v-else class="detection-grid">
        <article
          v-for="entry in detections"
          :key="entry.key"
          class="detection-card"
          :class="{ saved: entry.createdItem, unchecked: !entry.checked }"
        >
          <div class="detection-thumb">
            <img :src="photoUrl(entry.photo)" alt="" />
            <el-checkbox
              v-model="entry.checked"
              class="detection-check"
              :disabled="!!entry.createdItem"
            />
            <span v-if="entry.createdItem" class="detection-saved">已入库</span>
          </div>
          <div class="detection-body">
            <div class="detection-label">
              <span class="detection-class" :title="entry.label">{{ entry.labelZh || entry.label }}</span>
              <span class="muted">{{ Math.round((entry.confidence || 0) * 100) }}%</span>
            </div>
            <el-input
              v-model="entry.name"
              size="small"
              :placeholder="entry.labelZh || entry.label"
              :disabled="!!entry.createdItem"
              maxlength="200"
            />
            <div class="detection-meta">
              <el-tag v-if="entry.category_name" size="small" effect="plain">
                {{ entry.category_name }}
              </el-tag>
              <el-tag
                v-if="entry.color_family"
                size="small"
                effect="plain"
                type="success"
              >
                {{ entry.color_family }}
              </el-tag>
              <span v-if="entry.state === 'analyzing'" class="muted">识别中…</span>
              <span v-else-if="entry.state === 'error'" class="muted">识别失败，可手动填写</span>
            </div>
          </div>
        </article>
      </div>
    </section>

    <!-- 相似物品：确认是否为已有物品，可对选中的物品执行一句话指令 -->
    <section
      v-if="photo && !savedItem && (similarChecked || similarLoading)"
      v-loading="similarLoading"
      class="panel similar-panel"
    >
      <div class="panel-head">
        <div>
          <span class="panel-title">相似物品</span>
          <p class="similar-sub">
            看看是不是其中某一件：选中后，一句话指令会作用于它（例如移动到某个柜子）
          </p>
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
        <div
          v-for="item in similarItems"
          :key="item.id"
          class="similar-card"
          :class="{ 'is-target': targetItem?.id === item.id }"
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
          <div class="similar-actions">
            <el-button
              size="small"
              :type="targetItem?.id === item.id ? 'primary' : 'default'"
              @click.stop="chooseTarget(item)"
            >
              {{ targetItem?.id === item.id ? '已选择' : '就是这个' }}
            </el-button>
          </div>
        </div>
      </div>

      <div v-else-if="!similarLoading" class="similar-empty">
        没有找到描述相近的已有物品，可以直接保存为新物品。
      </div>
    </section>

    <!-- 最近上传：点击可切换到已上传的照片继续处理 -->
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
  min-width: 0;
}

.step {
  display: inline-grid;
  place-items: center;
  width: 20px;
  height: 20px;
  margin-right: 6px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand-deep);
  font-size: 11px;
  font-style: normal;
  font-weight: 700;
  vertical-align: 1px;
}

.upload-choices {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.uploader {
  width: 100%;
}

.uploader :deep(.el-upload) {
  width: 100%;
}

.uploader :deep(.el-upload-dragger) {
  width: 100%;
  min-height: 168px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 18px 16px;
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
  font-size: 30px;
  color: var(--brand);
  margin-bottom: 2px;
}

.upload-text {
  font-size: 14px;
  color: var(--ink-2);
}

.mobile-only {
  display: none;
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
  flex-wrap: wrap;
  gap: 10px;
}

.camera-hint {
  font-size: 11.5px;
  color: var(--muted);
}

.preview-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.preview {
  width: 100%;
  max-width: 100%;
  height: 320px;
  border-radius: 14px;
  background: #f2f6f4;
  border: 1px solid var(--line);
}

.preview :deep(.el-image__inner) {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.file-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
  font-size: 11.5px;
  color: var(--muted);
}

.file-meta span:first-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.batch-strip {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.batch-label {
  font-size: 11.5px;
  color: var(--muted);
}

.batch-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.batch-tile {
  position: relative;
  width: 56px;
  height: 56px;
  padding: 0;
  border-radius: 9px;
  border: 2px solid transparent;
  background: #f2f6f4;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s;
}

.batch-main {
  position: absolute;
  left: 2px;
  bottom: 2px;
  padding: 0 4px;
  border-radius: 5px;
  background: var(--brand);
  color: #fff;
  font-size: 9.5px;
  line-height: 14px;
}

.batch-remove {
  position: absolute;
  right: 0;
  top: 0;
  width: 15px;
  height: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0 0 0 7px;
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  font-size: 12px;
  line-height: 1;
}

.batch-tile img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.batch-tile.active {
  border-color: var(--brand);
}

.batch-tile:hover {
  border-color: var(--brand-line);
}

.preview-actions :deep(.el-button) {
  margin-left: 0;
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
  overflow-wrap: anywhere;
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
  overflow-wrap: anywhere;
}

.manual-tip {
  margin-bottom: 16px;
}

.command-box {
  border: 1px solid var(--brand-line);
  border-radius: 14px;
  background: #f6fbf9;
  padding: 12px 14px;
  margin-bottom: 16px;
}

.command-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.command-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--brand-deep);
}

.command-hint {
  font-size: 11.5px;
  color: var(--muted);
}

.command-target {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  color: var(--brand-deep);
  background: var(--brand-soft);
  border-radius: 8px;
  padding: 4px 10px;
  margin-bottom: 8px;
}

.command-row {
  display: flex;
  gap: 8px;
  min-width: 0;
}

.command-row :deep(.el-button) {
  flex: none;
}

.command-row :deep(.el-input) {
  flex: 1;
  min-width: 0;
}

.result-form {
  margin-top: 4px;
}

.form-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
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

.upload-head-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.detection-panel {
  margin-top: 18px;
}

.detection-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 14px;
}

.detection-toolbar .spacer {
  flex: 1;
}

.detection-loading {
  padding: 32px 0;
  text-align: center;
  font-size: 12.5px;
  color: var(--muted);
}

.detection-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.detection-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fff;
  transition: opacity 0.15s, border-color 0.15s, background 0.15s;
}

.detection-card.unchecked {
  opacity: 0.55;
}

.detection-card.saved {
  border-color: var(--brand-line);
  background: #f7fbf9;
}

.detection-thumb {
  position: relative;
  flex: none;
  width: 78px;
  height: 78px;
  border-radius: 9px;
  overflow: hidden;
  background: #f2f6f4;
}

.detection-thumb img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.detection-check {
  position: absolute;
  left: 3px;
  top: 3px;
  padding: 0 4px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.86);
}

.detection-saved {
  position: absolute;
  right: 3px;
  bottom: 3px;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--brand);
  color: #fff;
  font-size: 9.5px;
  line-height: 15px;
}

.detection-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detection-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  color: var(--muted);
}

.detection-class {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
  color: var(--ink-2);
}

.detection-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 11px;
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

.similar-card.is-target {
  border-color: var(--brand);
  background: var(--brand-soft);
  box-shadow: 0 0 0 2px rgba(47, 125, 109, 0.12);
}

.similar-actions {
  flex: none;
  display: flex;
  align-items: center;
}

.similar-actions :deep(.el-button) {
  margin-left: 0;
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
    grid-template-columns: minmax(0, 1fr);
  }
  .upload-panel,
  .result-panel {
    min-height: 0;
  }
}

@media (max-width: 640px) {
  .similar-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  /* 图片按容器宽度等比缩放，避免大图把页面撑出横向滚动 */
  .preview {
    height: auto;
    aspect-ratio: 4 / 3;
    max-height: 58vh;
  }
  .preview-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .preview-actions :deep(.el-button) {
    width: 100%;
  }
  .panel-head {
    align-items: center;
  }

  /* 手机上先给拍照入口，相册选择压缩成一行，避免大块拖拽区占满首屏 */
  .upload-choices {
    gap: 10px;
  }
  .camera-row {
    order: -1;
  }
  .camera-row :deep(.el-button) {
    flex: 1;
    margin-left: 0;
  }
  .camera-hint {
    flex-basis: 100%;
    text-align: center;
  }
  .uploader :deep(.el-upload-dragger) {
    min-height: 0;
    flex-direction: row;
    gap: 8px;
    padding: 12px 14px;
  }
  .upload-icon {
    font-size: 20px;
    margin-bottom: 0;
  }
  .upload-text {
    font-size: 13px;
  }
  .drag-only,
  .upload-hint {
    display: none;
  }
  .mobile-only {
    display: inline;
  }
  .detection-toolbar {
    gap: 8px;
  }
  .detection-toolbar .el-select,
  .detection-toolbar .el-tree-select {
    flex: 1;
    min-width: 140px;
  }
  .detection-toolbar .spacer {
    display: none;
  }
  .detection-toolbar :deep(.el-button) {
    width: 100%;
  }
  .detection-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
