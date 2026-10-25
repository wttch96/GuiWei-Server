import request from './request'

export const listItems = (params) => request.get('/items', { params })
export const getItem = (id) => request.get(`/items/${id}`)
export const createItem = (data) => request.post('/items', data)
// 多物品检测后的批量入库：后端逐条校验，单条失败不影响其它条目
export const createItemsBatch = (items) =>
  request.post('/items/batch', { items }, { timeout: 120000 })
export const updateItem = (id, data) => request.put(`/items/${id}`, data)
export const moveItem = (id, data) => request.post(`/items/${id}/move`, data)
export const deleteItem = (id) => request.delete(`/items/${id}`)
