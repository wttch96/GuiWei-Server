<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ChatDotRound,
  Delete,
  MagicStick,
  Promotion,
  Tools,
} from '@element-plus/icons-vue'
import { chat, getAiStatus, getSessionMessages, getTools } from '../api/ai'
import { useAuthStore } from '../stores/auth'
import { prettyJson } from '../utils/format'

const auth = useAuthStore()

const SESSION_KEY = 'guiwei_ai_session'
const suggestions = [
  '看看我家现在有哪些房间和容器',
  '把「电视遥控器」放到客厅/电视柜/第一层抽屉',
  '帮我盘点一下书房里都有什么',
  '有哪些物品借出去了还没归还？',
  '给所有药品打上「常用」标签',
]

const status = ref(null)
const tools = ref([])
const messages = ref([])
const input = ref('')
const sending = ref(false)
const historyLoading = ref(false)
const toolsVisible = ref(false)
const scrollRef = ref(null)
const sessionId = ref(localStorage.getItem(SESSION_KEY) || '')
const userInitial = computed(() => (auth.adminName || '管').slice(0, 1).toUpperCase())

async function loadStatus() {
  const [aiStatus, toolList] = await Promise.all([
    getAiStatus().catch(() => null),
    getTools().catch(() => []),
  ])
  status.value = aiStatus
  tools.value = toolList
}

async function loadHistory() {
  if (!sessionId.value) return
  historyLoading.value = true
  try {
    const rows = await getSessionMessages(sessionId.value)
    messages.value = rows.map((row) => ({
      role: row.role,
      content: row.content,
      tool_calls: row.tool_trace || [],
    }))
    await scrollToBottom()
  } catch {
    sessionId.value = ''
    localStorage.removeItem(SESSION_KEY)
  } finally {
    historyLoading.value = false
  }
}

async function scrollToBottom() {
  await nextTick()
  const el = scrollRef.value
  if (el) el.scrollTop = el.scrollHeight
}

async function send(text) {
  const message = (text ?? input.value).trim()
  if (!message || sending.value) return
  if (status.value && !status.value.chat_configured) {
    ElMessage.warning('尚未配置 DEEPSEEK_API_KEY，请先在 backend/.env 中配置')
    return
  }
  messages.value.push({ role: 'user', content: message })
  input.value = ''
  sending.value = true
  await scrollToBottom()
  try {
    const result = await chat({
      message,
      session_id: sessionId.value || null,
    })
    sessionId.value = result.session_id
    localStorage.setItem(SESSION_KEY, result.session_id)
    messages.value.push({
      role: 'assistant',
      content: result.reply,
      tool_calls: result.tool_calls || [],
    })
  } catch {
    // 请求层已提示错误，保留用户消息便于重试
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

async function newSession() {
  if (messages.value.length) {
    try {
      await ElMessageBox.confirm(
        '开始新会话后，当前对话将不再显示（历史仍保留在服务端）。',
        '新会话',
        {
          type: 'warning',
          confirmButtonText: '开始新会话',
          cancelButtonText: '取消',
        },
      )
    } catch {
      return
    }
  }
  messages.value = []
  sessionId.value = ''
  localStorage.removeItem(SESSION_KEY)
  input.value = ''
}

function toolOk(call) {
  return !(call?.result && call.result.ok === false)
}

onMounted(async () => {
  await loadStatus()
  await loadHistory()
  await scrollToBottom()
})
</script>

<template>
  <div class="page chat-page">
    <div class="page-head">
      <div>
        <h1 class="page-title">AI 收纳助手</h1>
        <p class="page-sub">用自然语言完成查询、归类、移动与盘点，所有操作都会真实落库</p>
      </div>
      <div class="toolbar">
        <el-tag v-if="status" size="small" :type="status.chat_configured ? 'success' : 'info'" effect="plain">
          {{ status.chat_configured ? status.model || 'DeepSeek' : '未配置模型' }}
        </el-tag>
        <el-button :icon="Tools" @click="toolsVisible = true">可用工具 {{ tools.length }}</el-button>
        <el-button :icon="Delete" @click="newSession">新会话</el-button>
      </div>
    </div>

    <el-alert
      v-if="status && !status.chat_configured"
      type="warning"
      show-icon
      :closable="false"
      title="AI 对话尚未启用"
      description="在 backend/.env 中填写 DEEPSEEK_API_KEY 后重启后端服务即可使用。"
    />

    <section class="panel chat-panel" v-loading="historyLoading">
      <div ref="scrollRef" class="chat-scroll">
        <div v-if="!messages.length" class="chat-empty">
          <div class="orb"><el-icon :size="26"><MagicStick /></el-icon></div>
          <h2>今天想整理哪里？</h2>
          <p>可以直接让我找东西、换位置、加分类，或者来一次全屋盘点。</p>
          <div class="suggestions">
            <button
              v-for="item in suggestions"
              :key="item"
              class="suggestion"
              :disabled="sending"
              @click="send(item)"
            >
              <el-icon><ChatDotRound /></el-icon>
              <span>{{ item }}</span>
            </button>
          </div>
        </div>

        <template v-else>
          <div
            v-for="(message, index) in messages"
            :key="index"
            class="msg"
            :class="message.role"
          >
            <div v-if="message.role === 'assistant'" class="avatar assistant-avatar">
              <el-icon><MagicStick /></el-icon>
            </div>
            <div class="msg-body">
              <div v-if="message.content" class="bubble">
                {{ message.content }}
              </div>

              <div v-if="message.tool_calls?.length" class="trace">
                <div class="trace-head">
                  <el-icon><Tools /></el-icon>
                  调用 {{ message.tool_calls.length }} 个工具
                </div>
                <el-collapse class="trace-collapse">
                  <el-collapse-item
                    v-for="(call, callIndex) in message.tool_calls"
                    :key="callIndex"
                    :name="`${index}-${callIndex}`"
                  >
                    <template #title>
                      <span class="trace-name mono">{{ call.tool }}</span>
                      <el-tag
                        size="small"
                        effect="plain"
                        :type="toolOk(call) ? 'success' : 'danger'"
                        class="trace-tag"
                      >
                        {{ toolOk(call) ? '成功' : '失败' }}
                      </el-tag>
                    </template>
                    <div class="trace-label">参数</div>
                    <pre class="trace-code">{{ prettyJson(call.args) }}</pre>
                    <div class="trace-label">结果</div>
                    <pre class="trace-code">{{ prettyJson(call.result) }}</pre>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </div>
            <div v-if="message.role === 'user'" class="avatar user-avatar">
              {{ userInitial }}
            </div>
          </div>

          <div v-if="sending" class="msg assistant">
            <div class="avatar assistant-avatar"><el-icon><MagicStick /></el-icon></div>
            <div class="bubble typing">
              <span /><span /><span />
            </div>
          </div>
        </template>
      </div>

      <div class="composer">
        <el-input
          v-model="input"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 5 }"
          resize="none"
          maxlength="4000"
          placeholder="例如：把玄关的雨伞放到储物间/门后挂钩，并标记为常用"
          @keydown.enter.exact.prevent="send()"
        />
        <div class="composer-foot">
          <span class="composer-hint">Enter 发送 · Shift + Enter 换行 · 删除类操作会先向你确认</span>
          <el-button
            type="primary"
            :icon="Promotion"
            :loading="sending"
            :disabled="!input.trim()"
            @click="send()"
          >
            发送
          </el-button>
        </div>
      </div>
    </section>

    <el-drawer v-model="toolsVisible" title="AI 可调用的工具" size="440px">
      <p class="drawer-sub">
        AI 只能通过下列工具读写数据，与后台操作共用同一套服务层，行为保持一致。
      </p>
      <el-collapse>
        <el-collapse-item v-for="tool in tools" :key="tool.name" :name="tool.name">
          <template #title>
            <span class="mono tool-name">{{ tool.name }}</span>
          </template>
          <p class="tool-desc">{{ tool.description }}</p>
          <pre v-if="tool.parameters" class="trace-code">{{ prettyJson(tool.parameters) }}</pre>
        </el-collapse-item>
      </el-collapse>
    </el-drawer>
  </div>
</template>

<style scoped>
.chat-page {
  height: calc(100vh - 114px);
}

.chat-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.chat-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 22px 22px 10px;
  scroll-behavior: smooth;
}

.chat-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 20px 10px;
}

.orb {
  width: 58px;
  height: 58px;
  border-radius: 17px;
  display: grid;
  place-items: center;
  color: #fff;
  background: linear-gradient(135deg, #5fae9b, #2f7d6d);
  box-shadow: 0 12px 28px rgba(47, 125, 109, 0.28);
  margin-bottom: 18px;
}

.chat-empty h2 {
  margin: 0;
  font-size: 19px;
  font-weight: 650;
}

.chat-empty p {
  margin: 8px 0 22px;
  color: var(--muted);
  font-size: 13px;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 9px;
  max-width: 660px;
}

.suggestion {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--line);
  background: #fbfdfc;
  color: var(--ink-2);
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 12.5px;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s;
}

.suggestion:hover:not(:disabled) {
  border-color: var(--brand-line);
  background: var(--brand-soft);
  color: var(--brand-deep);
}

.suggestion:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.suggestion .el-icon {
  color: var(--brand);
}

.msg {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  align-items: flex-start;
}

.msg.user {
  justify-content: flex-end;
}

.msg-body {
  max-width: min(78%, 760px);
  min-width: 0;
}

.msg.user .msg-body {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.avatar {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  flex: none;
  display: grid;
  place-items: center;
  font-size: 13px;
  font-weight: 600;
}

.assistant-avatar {
  background: linear-gradient(135deg, #5fae9b, #2f7d6d);
  color: #fff;
}

.user-avatar {
  background: #e8f2ef;
  color: var(--brand-deep);
}

.bubble {
  padding: 11px 14px;
  border-radius: 13px;
  font-size: 13.5px;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
}

.assistant .bubble {
  background: #f5f9f7;
  border: 1px solid var(--line);
  border-top-left-radius: 4px;
  color: var(--ink);
}

.user .bubble {
  background: var(--brand);
  color: #fff;
  border-top-right-radius: 4px;
}

.typing {
  display: flex;
  gap: 4px;
  align-items: center;
  min-width: 54px;
}

.typing span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #99b3ac;
  animation: blink 1.2s infinite ease-in-out;
}

.typing span:nth-child(2) {
  animation-delay: 0.18s;
}

.typing span:nth-child(3) {
  animation-delay: 0.36s;
}

@keyframes blink {
  0%, 80%, 100% {
    opacity: 0.35;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-2px);
  }
}

.trace {
  margin-top: 8px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: #fcfdfd;
  padding: 9px 12px;
  max-width: 100%;
}

.trace-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--muted);
  margin-bottom: 2px;
}

.trace-collapse {
  border: none;
}

.trace-collapse :deep(.el-collapse-item__header) {
  height: 32px;
  border-bottom: none;
  font-size: 12px;
  background: transparent;
  gap: 8px;
}

.trace-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
  background: transparent;
}

.trace-collapse :deep(.el-collapse-item__content) {
  padding-bottom: 8px;
}

.trace-name {
  color: var(--brand-deep);
  font-weight: 600;
}

.trace-tag {
  margin-left: 8px;
}

.trace-label {
  font-size: 10.5px;
  color: var(--muted);
  margin: 6px 0 3px;
  letter-spacing: 0.04em;
}

.trace-code {
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f2f6f4;
  color: #344a44;
  font-family: 'JetBrains Mono', 'Cascadia Code', Consolas, monospace;
  font-size: 11px;
  line-height: 1.55;
  max-height: 190px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.composer {
  flex: none;
  border-top: 1px solid var(--line);
  padding: 12px 16px 14px;
  background: #fff;
  border-radius: 0 0 16px 16px;
}

.composer :deep(.el-textarea__inner) {
  box-shadow: none;
  border: 1px solid var(--line);
  padding: 10px 12px;
  font-size: 13.5px;
  line-height: 1.7;
  background: #fbfdfc;
}

.composer :deep(.el-textarea__inner:focus) {
  border-color: var(--brand-line);
  background: #fff;
}

.composer-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
}

.composer-hint {
  font-size: 11px;
  color: var(--muted);
}

.drawer-sub {
  margin: 0 0 14px;
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.7;
}

.tool-name {
  color: var(--brand-deep);
  font-weight: 600;
  font-size: 12.5px;
}

.tool-desc {
  margin: 0 0 8px;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--ink-2);
}

@media (max-width: 640px) {
  .chat-page {
    height: calc(100vh - 94px);
  }
  .chat-scroll {
    padding: 14px 12px 8px;
  }
  .msg-body {
    max-width: 84%;
  }
  .composer-hint {
    display: none;
  }
}
</style>
