import request from './request'

export const chat = (data) => request.post('/ai/chat', data, { timeout: 180000 })
export const getAiStatus = () => request.get('/ai/status')
export const getSessionMessages = (sessionId) =>
  request.get(`/ai/sessions/${sessionId}/messages`)
export const getTools = () => request.get('/ai/tools')
