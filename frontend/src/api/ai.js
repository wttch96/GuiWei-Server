import request from './request'

export const chat = (data) => request.post('/ai/chat', data, { timeout: 180000 })
// 对话 / 视觉识图 / 多物品检测的能力状态
export const getAiStatus = () => request.get('/ai/status')
// DeepSeek 账户余额；refresh=true 时跳过后端 60 秒缓存
export const getAiBalance = (refresh = false) =>
  request.get('/ai/balance', { params: refresh ? { refresh: 1 } : {} })
export const getSessionMessages = (sessionId) =>
  request.get(`/ai/sessions/${sessionId}/messages`)
export const getSessions = () => request.get('/ai/sessions')
export const removeSession = (sessionId) =>
  request.delete(`/ai/sessions/${sessionId}`)
export const getPrompts = () => request.get('/ai/prompts')
export const updatePrompt = (key, content) =>
  request.put(`/ai/prompts/${key}`, { content })
export const resetPrompt = (key) => request.post(`/ai/prompts/${key}/reset`)
export const getTools = () => request.get('/ai/tools')
