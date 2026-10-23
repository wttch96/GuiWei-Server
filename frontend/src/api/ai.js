import request from './request'

export const chat = (data) => request.post('/ai/chat', data, { timeout: 180000 })
export const getAiStatus = () => request.get('/ai/status')
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
