<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Camera, ChatDotRound, Check, Refresh } from '@element-plus/icons-vue'
import { getPrompts, resetPrompt, updatePrompt } from '../api/ai'
import { formatDate } from '../utils/format'

const icons = { chat: ChatDotRound, vision: Camera }

const prompts = ref([])
const drafts = reactive({})
const loading = ref(false)
const savingKey = ref('')
const resettingKey = ref('')

function isDirty(item) {
  return (drafts[item.key] || '') !== item.content
}

async function load() {
  loading.value = true
  try {
    const rows = await getPrompts()
    prompts.value = rows
    for (const row of rows) {
      drafts[row.key] = row.content
    }
  } finally {
    loading.value = false
  }
}

async function save(item) {
  const content = (drafts[item.key] || '').trim()
  if (content.length < 20) {
    ElMessage.warning('提示词至少需要 20 个字符')
    return
  }
  savingKey.value = item.key
  try {
    const data = await updatePrompt(item.key, content)
    Object.assign(item, data)
    drafts[item.key] = data.content
    ElMessage.success('提示词已保存，新的请求会立即使用')
  } finally {
    savingKey.value = ''
  }
}

async function reset(item) {
  try {
    await ElMessageBox.confirm(
      `恢复「${item.title}」的内置默认内容？当前自定义内容会被清除。`,
      '恢复默认',
      {
        type: 'warning',
        confirmButtonText: '恢复默认',
        cancelButtonText: '取消',
      },
    )
  } catch {
    return
  }
  resettingKey.value = item.key
  try {
    const data = await resetPrompt(item.key)
    Object.assign(item, data)
    drafts[item.key] = data.content
    ElMessage.success('已恢复默认提示词')
  } finally {
    resettingKey.value = ''
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">AI 提示词</h1>
        <p class="page-sub">
          自定义 AI 对话与拍照识图的行为。保存后立即生效，无需重启服务。
        </p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="load">重新加载</el-button>
    </div>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="提示词保存在本地数据库中"
      description="修改只影响之后发起的对话与识图请求；历史会话和已有识图结果不会变化。清空数据库或点击「恢复默认」即可回到内置版本。"
    />

    <section
      v-for="item in prompts"
      :key="item.key"
      v-loading="loading"
      class="panel prompt-panel"
    >
      <div class="panel-head prompt-head">
        <div class="prompt-title-row">
          <span class="prompt-icon">
            <el-icon :size="18"><component :is="icons[item.key]" /></el-icon>
          </span>
          <div>
            <div class="panel-title">{{ item.title }}</div>
            <p class="prompt-desc">{{ item.description }}</p>
          </div>
        </div>
        <div class="prompt-tags">
          <el-tag v-if="isDirty(item)" size="small" type="warning" effect="plain">
            未保存
          </el-tag>
          <el-tag
            size="small"
            :type="item.is_custom ? 'success' : 'info'"
            effect="plain"
          >
            {{ item.is_custom ? '已自定义' : '内置默认' }}
          </el-tag>
          <span v-if="item.updated_at" class="prompt-time">
            {{ formatDate(item.updated_at) }}
          </span>
        </div>
      </div>

      <el-input
        v-model="drafts[item.key]"
        type="textarea"
        :rows="item.key === 'chat' ? 15 : 13"
        :maxlength="item.max_length"
        show-word-limit
        spellcheck="false"
        resize="vertical"
        class="prompt-input"
      />

      <div class="prompt-foot">
        <span class="prompt-hint">{{ item.hint }}</span>
        <div class="prompt-actions">
          <el-button
            :icon="Refresh"
            :disabled="!item.is_custom"
            :loading="resettingKey === item.key"
            @click="reset(item)"
          >
            恢复默认
          </el-button>
          <el-button
            type="primary"
            :icon="Check"
            :disabled="!isDirty(item)"
            :loading="savingKey === item.key"
            @click="save(item)"
          >
            保存
          </el-button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.prompt-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.prompt-head {
  align-items: flex-start;
  margin-bottom: 0;
}

.prompt-title-row {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  min-width: 0;
}

.prompt-icon {
  flex: none;
  width: 36px;
  height: 36px;
  border-radius: 11px;
  display: grid;
  place-items: center;
  background: var(--brand-soft);
  color: var(--brand);
}

.prompt-desc {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--muted);
}

.prompt-tags {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 6px;
  flex: none;
}

.prompt-time {
  font-size: 11px;
  color: var(--muted);
}

.prompt-input :deep(.el-textarea__inner) {
  font-family: 'JetBrains Mono', 'Cascadia Code', Consolas, monospace;
  font-size: 12.5px;
  line-height: 1.68;
  padding: 14px 16px;
  border-radius: 12px;
  background: #fbfdfc;
}

.prompt-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}

.prompt-hint {
  min-width: 0;
  max-width: 720px;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--muted);
}

.prompt-actions {
  display: flex;
  gap: 8px;
}

.prompt-actions :deep(.el-button) {
  margin-left: 0;
}

@media (max-width: 640px) {
  .prompt-head {
    flex-direction: column;
    gap: 10px;
  }
  .prompt-tags {
    justify-content: flex-start;
  }
  .prompt-foot {
    flex-direction: column;
    align-items: stretch;
  }
  .prompt-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .prompt-actions :deep(.el-button) {
    width: 100%;
  }
}
</style>
